"""The Web Panel server: the committed panel build over HTTP and the control API over one WebSocket (ADR-0007).

Messages are JSON objects with a `type`. A client request may carry an `id`, echoed in its `result`.

Client to Runtime: `update {changes}`, `preset.save {name}`, `preset.recall {name}`,
`preset.rename {name, new_name}`, `preset.delete {name}`, `sources.list {transport}`, `preview {enabled}`.
Runtime to client: `hello {schema, settings, version, presets}` on connect, `result {id, ok, error?, ...}`,
and pushes of `settings`, `presets` and `status`. Preview frames are binary: one byte (0 Input, 1 Output), then JPEG.
"""

import asyncio
import contextlib
import hmac
import ipaddress
import json
import threading
from collections.abc import Awaitable, Callable, Coroutine
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web
from pydantic import ValidationError

from streamturbo.control import Control

PANEL_DIR = Path(__file__).resolve().parent.parent / "web_panel"
STATUS_INTERVAL = 0.25
PREVIEW_INTERVAL = 0.2


class WebServer:
    def __init__(
        self,
        control: Control,
        host: str = "127.0.0.1",
        port: int = 8765,
        token: str | None = None,
        panel_dir: Path = PANEL_DIR,
    ) -> None:
        if not _is_loopback(host) and not token:
            raise ValueError("serving the Web Panel beyond this machine requires an access token")
        self._control = control
        self._host, self._port = host, port
        self._token = token
        self._panel_dir = panel_dir.resolve()
        self._clients: dict[web.WebSocketResponse, bool] = {}  # socket -> wants preview frames
        self._sending: set[asyncio.Future[None]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopped: asyncio.Event | None = None
        self._ready = threading.Event()
        self._failure: BaseException | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._port

    @property
    def url(self) -> str:
        host = "127.0.0.1" if self._host in ("0.0.0.0", "::") else self._host
        return f"http://{host}:{self._port}/" + (f"?token={self._token}" if self._token else "")

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="streamturbo-web", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._failure is not None:
            raise self._failure

    def stop(self) -> None:
        if self._loop is not None and self._stopped is not None:
            self._loop.call_soon_threadsafe(self._stopped.set)
        if self._thread is not None:
            self._thread.join()

    def _run(self) -> None:
        try:
            asyncio.run(self._serve())
        except BaseException as error:  # reported to start() when it happens before the server is up
            self._failure = error
            self._ready.set()

    async def _serve(self) -> None:
        self._loop, self._stopped = asyncio.get_running_loop(), asyncio.Event()
        app = web.Application(middlewares=[self._guard])
        app.router.add_get("/ws", self._websocket)
        app.router.add_get("/{path:.*}", self._static)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self._host, self._port)
        await site.start()
        self._port = runner.addresses[0][1]
        unsubscribe = self._control.subscribe(self._from_control)
        pushes = [asyncio.create_task(self._push_status()), asyncio.create_task(self._push_previews())]
        self._ready.set()
        try:
            await self._stopped.wait()
        finally:
            unsubscribe()
            for task in pushes:
                task.cancel()
            for socket in list(self._clients):
                await socket.close()
            await runner.cleanup()

    @web.middleware
    async def _guard(
        self, request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
    ) -> web.StreamResponse:
        remote_needs_token = self._token and not _is_loopback(request.remote or "")
        if remote_needs_token and not hmac.compare_digest(request.query.get("token", ""), self._token or ""):
            raise web.HTTPUnauthorized(text="an access token is required")
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            raise web.HTTPForbidden(text="cross-origin requests are not allowed")  # another site in the browser
        return await handler(request)

    async def _static(self, request: web.Request) -> web.StreamResponse:
        path = (self._panel_dir / request.match_info["path"]).resolve()
        if not path.is_relative_to(self._panel_dir) or not path.is_file():
            path = self._panel_dir / "index.html"
        if not path.is_file():
            raise web.HTTPNotFound(text="the Web Panel build is missing")
        response = web.FileResponse(path)
        if path.name == "index.html":
            response.headers["Cache-Control"] = "no-cache"
        return response

    async def _websocket(self, request: web.Request) -> web.WebSocketResponse:
        socket = web.WebSocketResponse(heartbeat=10)
        await socket.prepare(request)
        self._clients[socket] = False
        try:
            hello = await self._call(lambda: {"schema": self._control.schema()} | self._control.settings())
            await socket.send_json({"type": "hello"} | hello | await self._call(self._control.presets))
            async for message in socket:
                if message.type == WSMsgType.TEXT:
                    await self._handle(socket, message.data)
        finally:
            self._clients.pop(socket, None)
        return socket

    async def _handle(self, socket: web.WebSocketResponse, text: str) -> None:
        request: dict[str, Any] = {}
        try:
            request = json.loads(text)
            data = await self._dispatch(socket, request)
            reply = {"type": "result", "id": request.get("id"), "ok": True} | (data or {})
        except (ValueError, KeyError, TypeError, OSError) as error:
            reply = {"type": "result", "id": request.get("id"), "ok": False, "error": error_text(error)}
        await socket.send_json(reply)

    async def _dispatch(self, socket: web.WebSocketResponse, request: dict[str, Any]) -> dict[str, Any] | None:
        control, kind = self._control, request["type"]
        if kind == "update":
            return {"version": await self._call(control.update, request["changes"])}
        if kind == "preset.save":
            return await self._call(control.save_preset, request["name"])
        if kind == "preset.recall":
            return {"version": await self._call(control.recall_preset, request["name"])}
        if kind == "preset.rename":
            return await self._call(control.rename_preset, request["name"], request["new_name"])
        if kind == "preset.delete":
            return await self._call(control.delete_preset, request["name"])
        if kind == "sources.list":
            transport = request["transport"]
            return {"transport": transport, "names": await self._call(control.list_sources, transport)}
        if kind == "preview":
            self._clients[socket] = bool(request["enabled"])
            return None
        raise ValueError(f"unknown message type {kind!r}")

    async def _call(self, function: Callable[..., Any], *args: Any) -> Any:
        """Control calls may block (file writes, NDI discovery), so they run off the event loop."""
        assert self._loop is not None
        return await self._loop.run_in_executor(None, function, *args)

    def _from_control(self, kind: str, payload: dict[str, Any]) -> None:
        if self._loop is not None:  # called from whichever thread made the change
            self._loop.call_soon_threadsafe(self._broadcast, {"type": kind} | payload)

    def _broadcast(self, message: dict[str, Any]) -> None:
        text = json.dumps(message)
        for socket in list(self._clients):
            self._spawn(_send(socket, text))

    def _spawn(self, sending: Coroutine[Any, Any, None]) -> None:
        task = asyncio.ensure_future(sending)
        self._sending.add(task)  # keep a reference until it finishes, or it may be collected mid-send
        task.add_done_callback(self._sending.discard)

    async def _push_status(self) -> None:
        while True:
            if self._clients:
                self._broadcast({"type": "status"} | await self._call(self._control.status))
            await asyncio.sleep(STATUS_INTERVAL)

    async def _push_previews(self) -> None:
        while True:
            if any(self._clients.values()):
                for channel, jpeg in enumerate(await self._call(self._control.previews)):
                    if jpeg is None:
                        continue
                    for socket, wanted in list(self._clients.items()):
                        if wanted:
                            self._spawn(_send(socket, bytes([channel]) + jpeg))
            await asyncio.sleep(PREVIEW_INTERVAL)


async def _send(socket: web.WebSocketResponse, data: str | bytes) -> None:
    if socket.closed:
        return
    with contextlib.suppress(ConnectionError):  # the client went away; its handler cleans up
        await (socket.send_str(data) if isinstance(data, str) else socket.send_bytes(data))


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def error_text(error: BaseException) -> str:
    """A short, readable message, e.g. `strength: Input should be less than or equal to 1`."""
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'settings'}: {e['msg']}" for e in error.errors())
    if isinstance(error, KeyError):
        return f"missing field {error}"
    return str(error)

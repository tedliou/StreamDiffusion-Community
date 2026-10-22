"""OSC Control Surface: addresses mirror Settings paths, for TouchDesigner's OSC Out CHOP/DAT.

In:  `/streamturbo/<setting path>` with one value, e.g. `/streamturbo/strength 0.5`;
     list items by index, e.g. `/streamturbo/prompts/1/weight 0.5` (the next index adds an item), or a whole
     list as JSON, `/streamturbo/prompts '[{"text": "ice", "weight": 1}]'`; `/streamturbo/prompt "ice"` sets a
     single Prompt;
     `/streamturbo/preset/recall "Glass"`, `/streamturbo/preset/save "name"`;
     `/streamturbo/sync` re-sends all Settings.
Out: every Setting at its own address whenever Settings change (from any Control Surface), list items by
     index (`prompts/0/text`),
     `/streamturbo/status/<field>` a few times a second (nested fields as `status/engines/state`),
     and `/streamturbo/error "message"` for a rejected message.
"""

import functools
import logging
import threading
from typing import Any

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

from streamturbo.control import Control, error_text
from streamturbo.settings import nested

PREFIX = "/streamturbo/"
STATUS_INTERVAL = 0.5
log = logging.getLogger(__name__)
STATUS_FIELDS = (
    "source_state",
    "throughput_fps",
    "generation_ms_p50",
    "frames_skipped",
    "settings_version",
    "error",
    "backend",
    "engines.state",
    "engines.progress",
)


class OscServer:
    def __init__(
        self,
        control: Control,
        host: str = "127.0.0.1",
        port: int = 7000,
        reply_host: str = "127.0.0.1",
        reply_port: int = 7001,
    ) -> None:
        self._control = control
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self._receive)
        self._server = ThreadingOSCUDPServer((host, port), dispatcher)
        self._client = SimpleUDPClient(reply_host, reply_port)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._unsubscribe = lambda: None

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def start(self) -> None:
        self._unsubscribe = self._control.subscribe(self._from_control)
        for target, name in ((self._server.serve_forever, "osc"), (self._push_status, "osc-status")):
            thread = threading.Thread(target=target, name=f"streamturbo-{name}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._unsubscribe()
        self._stop.set()
        self._server.shutdown()
        self._server.server_close()
        for thread in self._threads:
            thread.join()

    def _receive(self, address: str, *args: Any) -> None:
        try:
            if not address.startswith(PREFIX):
                return
            path = address.removeprefix(PREFIX)
            if path == "sync":
                self.send_settings(self._control.settings()["settings"])
            elif path == "preset/recall":
                self._control.recall_preset(str(_one(args)))
            elif path == "preset/save":
                self._control.save_preset(str(_one(args)))
            else:
                self._control.update(nested(path.replace("/", "."), _one(args)))
        except (ValueError, OSError) as error:
            self._client.send_message(f"{PREFIX}error", f"{address}: {error_text(error)}")

    def _from_control(self, kind: str, payload: dict[str, Any]) -> None:
        if kind == "settings":
            self.send_settings(payload["settings"])

    def send_settings(self, settings: dict[str, Any], prefix: str = PREFIX) -> None:
        for key, value in settings.items():
            if isinstance(value, dict):
                self.send_settings(value, f"{prefix}{key}/")
            elif isinstance(value, list):
                self.send_settings({str(index): item for index, item in enumerate(value)}, f"{prefix}{key}/")
            else:
                self._client.send_message(f"{prefix}{key}", value)

    def _push_status(self) -> None:
        while not self._stop.wait(STATUS_INTERVAL):
            try:
                status = self._control.status()
                for field in STATUS_FIELDS:
                    value = functools.reduce(lambda node, key: node[key], field.split("."), status)
                    address = f"{PREFIX}status/{field.replace('.', '/')}"
                    self._client.send_message(address, "" if value is None else value)
            except Exception:  # an unreachable reply host or a failed sample; keep reporting
                log.exception("could not send the status over OSC")


def _one(args: tuple[Any, ...]) -> Any:
    if len(args) != 1:
        raise ValueError(f"expected one value, got {len(args)}")
    return args[0]

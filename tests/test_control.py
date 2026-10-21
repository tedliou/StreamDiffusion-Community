"""Seam 1 over the control API: a fake-Backend Runtime driven through the WebSocket and OSC, as real clients would."""

import json
import queue
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

import pytest
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from websockets.exceptions import InvalidStatus
from websockets.sync.client import ClientConnection, connect

from streamturbo.control import Control
from streamturbo.control.osc import OscServer
from streamturbo.control.web import WebServer
from streamturbo.presets import PresetStore, initial_settings, load_last
from streamturbo.runtime import Runtime
from streamturbo.settings import Settings
from streamturbo.transports.memory import MemorySink, MemoryTransports, input_frame
from tests.conftest import FakeBackend
from tests.test_runtime import RED, close_to, solid, wait_until


class Panel:
    """A WebSocket client speaking the control API."""

    def __init__(self, url: str, **options: Any) -> None:
        self._connection = connect(url, **options)
        self.socket: ClientConnection = self._connection.__enter__()
        self.hello = self.next("hello")
        self._id = 0

    def next(self, kind: str, timeout: float = 5.0) -> dict[str, Any]:
        """The next JSON message of `kind`, skipping others (status pushes, preview frames)."""
        deadline = time.monotonic() + timeout
        while True:
            message = self.socket.recv(timeout=max(0.0, deadline - time.monotonic()))
            if isinstance(message, str) and (data := json.loads(message))["type"] == kind:
                return data

    def request(self, kind: str, **fields: Any) -> dict[str, Any]:
        self._id += 1
        self.socket.send(json.dumps({"type": kind, "id": self._id} | fields))
        while True:
            result = self.next("result")
            if result["id"] == self._id:
                return result

    def binary(self, timeout: float = 5.0) -> bytes:
        deadline = time.monotonic() + timeout
        while True:
            message = self.socket.recv(timeout=max(0.0, deadline - time.monotonic()))
            if isinstance(message, bytes):
                return message

    def close(self) -> None:
        self._connection.__exit__(None, None, None)


class OscListener:
    """Stands in for TouchDesigner's OSC In: collects what the Runtime sends."""

    def __init__(self) -> None:
        self.messages: queue.Queue[tuple[str, tuple[Any, ...]]] = queue.Queue()
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(lambda address, *args: self.messages.put((address, args)))
        self.server = ThreadingOSCUDPServer(("127.0.0.1", 0), dispatcher)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def wait_for(self, address: str, timeout: float = 5.0) -> tuple[Any, ...]:
        deadline = time.monotonic() + timeout
        while True:
            seen, args = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            if seen == address:
                return args

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@dataclass
class Rig:
    runtime: Runtime
    sink: MemorySink
    web: WebServer
    osc: OscServer
    osc_in: OscListener
    presets_dir: Path
    last_path: Path
    web_control: Control

    def panel(self, **options: Any) -> Panel:
        return Panel(f"ws://127.0.0.1:{self.web.port}/ws", **options)

    def osc_send(self, address: str, value: Any) -> None:
        SimpleUDPClient("127.0.0.1", self.osc.port).send_message(address, value)


@pytest.fixture
def rig(small_settings: Settings, net: MemoryTransports, tmp_path: Path) -> Iterator[Rig]:
    net.add_source("cam", repeat_fps=60).push(input_frame(solid(320, 240, RED)))
    net.add_source("cam2")
    sink = net.sink(small_settings.sink)
    presets_dir, last_path = tmp_path / "presets", tmp_path / "last-settings.toml"
    runtime = Runtime(small_settings, FakeBackend(), net)
    control = Control(runtime, PresetStore(presets_dir), net, last_path)
    osc_in = OscListener()
    web, osc = WebServer(control, port=0), OscServer(control, port=0, reply_port=osc_in.port)
    with runtime:
        web.start()
        osc.start()
        try:
            yield Rig(runtime, sink, web, osc, osc_in, presets_dir, last_path, control)
        finally:
            osc.stop()
            web.stop()
            osc_in.close()


def test_hello_carries_the_schema_settings_and_presets(rig: Rig):
    panel = rig.panel()
    hello = panel.hello

    classes = {field["path"]: field["class"] for field in hello["schema"]}
    assert classes["strength"] == "live" and classes["source.name"] == "reset"
    assert all(cls in ("live", "reset", "rebuild") for cls in classes.values())
    assert hello["settings"]["output"] == {"width": 320, "height": 240}
    assert {"name": "Glass", "bundled": True} in hello["presets"]
    panel.close()


def test_live_update_reaches_output_frames_and_every_control_surface(rig: Rig):
    panel, other = rig.panel(), rig.panel()
    result = panel.request("update", changes={"strength": 0.0})

    assert result["ok"]
    assert other.next("settings")["settings"]["strength"] == 0.0  # the other panel sees it
    assert rig.osc_in.wait_for("/streamturbo/strength") == (0.0,)  # and so does TouchDesigner
    out = rig.sink.wait_for(lambda f: f.settings_version == result["version"])
    assert close_to(out, RED)
    panel.close()
    other.close()


def test_reset_update_changes_the_output_resolution(rig: Rig):
    panel = rig.panel()
    result = panel.request("update", changes={"output": {"width": 160, "height": 120}})
    out = rig.sink.wait_for(lambda f: f.settings_version == result["version"])

    assert (out.width, out.height) == (160, 120)
    panel.close()


def test_invalid_update_is_rejected_with_a_clear_error(rig: Rig):
    panel = rig.panel()

    result = panel.request("update", changes={"strength": 3, "seed": 5})
    assert not result["ok"]
    assert result["error"].startswith("strength: ")
    assert not panel.request("update", changes={"colour": "red"})["ok"]
    assert not panel.request("teleport")["ok"]
    assert rig.runtime.settings()[0].seed == 2  # nothing of the rejected update applied
    assert panel.request("update", changes={"seed": 5})["ok"]  # and the connection still works
    panel.close()


def test_presets_save_recall_rename_and_delete(rig: Rig):
    panel, other = rig.panel(), rig.panel()
    panel.request("update", changes={"strength": 0.3, "prompt": "ice"})

    assert panel.request("preset.save", name="Ice")["ok"]
    assert {"name": "Ice", "bundled": False} in other.next("presets")["presets"]
    assert (rig.presets_dir / "Ice.toml").is_file()

    panel.request("update", changes={"strength": 0.9, "prompt": "fire"})
    recalled = panel.request("preset.recall", name="ice")  # names are case-insensitive
    assert recalled["ok"]
    settings = rig.runtime.settings()[0]
    assert (settings.strength, settings.prompt) == (0.3, "ice")

    assert panel.request("preset.rename", name="Ice", new_name="Frost")["ok"]
    assert not panel.request("preset.recall", name="Ice")["ok"]
    assert panel.request("preset.delete", name="Frost")["ok"]
    assert not (rig.presets_dir / "Frost.toml").exists()
    panel.close()
    other.close()


def test_presets_keep_the_source_and_sink(rig: Rig):
    panel = rig.panel()
    panel.request("preset.save", name="Look")
    panel.request("update", changes={"source": {"name": "cam2"}})
    panel.request("preset.recall", name="Look")

    assert rig.runtime.settings()[0].source.name == "cam2"
    assert "source" not in (rig.presets_dir / "Look.toml").read_text(encoding="utf-8")
    panel.close()


def test_bundled_presets_are_read_only(rig: Rig):
    panel = rig.panel()

    assert "bundled" in panel.request("preset.delete", name="Glass")["error"]
    assert "bundled" in panel.request("preset.save", name="glass")["error"]
    assert not panel.request("preset.save", name="../escape")["ok"]
    assert panel.request("preset.recall", name="Glass")["ok"]
    assert rig.runtime.settings()[0].strength == 0.68
    panel.close()


def test_last_used_settings_are_restored_on_the_next_launch(rig: Rig, small_settings: Settings):
    panel = rig.panel()
    panel.request("update", changes={"strength": 0.42, "source": {"name": "cam2"}})
    panel.close()

    store = PresetStore(rig.presets_dir)
    restored = initial_settings(store, rig.last_path)
    assert load_last(rig.last_path) == restored
    assert (restored.strength, restored.source.name) == (0.42, "cam2")

    with_preset = initial_settings(store, rig.last_path, preset="Glass")
    assert (with_preset.strength, with_preset.source.name) == (0.68, "cam2")


def test_osc_mirrors_settings_paths_and_recalls_presets(rig: Rig):
    panel = rig.panel()
    rig.osc_send("/streamturbo/strength", 0.25)
    rig.osc_send("/streamturbo/output/width", 640.0)  # TouchDesigner sends numbers as floats

    wait_until(lambda: rig.runtime.settings()[0].output.width == 640)
    assert rig.runtime.settings()[0].strength == 0.25
    assert panel.next("settings")["settings"]["strength"] == 0.25  # the Web Panel sees OSC changes

    rig.osc_send("/streamturbo/preset/recall", "Glass")
    wait_until(lambda: rig.runtime.settings()[0].strength == 0.68)
    panel.close()


def test_osc_reports_errors_and_status(rig: Rig):
    rig.osc_send("/streamturbo/strength", 7.0)
    (error,) = rig.osc_in.wait_for("/streamturbo/error")

    assert "strength" in error
    assert rig.runtime.settings()[0].strength == 0.68
    assert rig.osc_in.wait_for("/streamturbo/status/source_state") in (("live",), ("waiting",))


def test_status_and_preview_frames_are_pushed(rig: Rig):
    panel = rig.panel()
    status = panel.next("status")
    assert status["backend"] == "fake" and "throughput_fps" in status

    panel.request("preview", enabled=True)
    channels = set()
    while channels != {0, 1}:
        frame = panel.binary()
        assert frame[1:3] == b"\xff\xd8"  # JPEG
        channels.add(frame[0])
    panel.close()


def test_sources_are_listed(rig: Rig):
    panel = rig.panel()
    result = panel.request("sources.list", transport="ndi")

    assert result["names"] == ["cam", "cam2"]
    assert not panel.request("sources.list", transport="smoke signals")["ok"]
    panel.close()


def test_other_sites_cannot_use_the_control_api(rig: Rig):
    with pytest.raises(InvalidStatus):
        rig.panel(origin="http://evil.example")  # pyright: ignore[reportArgumentType]


def test_lan_access_needs_a_token(rig: Rig):
    with pytest.raises(ValueError, match="token"):
        WebServer(Control.__new__(Control), host="0.0.0.0", port=0)


def test_a_page_reaching_the_panel_through_another_host_name_is_refused(rig: Rig):
    # DNS rebinding: evil.example resolves to 127.0.0.1, so the request comes from loopback but names another site
    request = urllib.request.Request(f"http://127.0.0.1:{rig.web.port}/", headers={"Host": "evil.example"})
    with pytest.raises(urllib.error.HTTPError, match="403"):
        urllib.request.urlopen(request, timeout=5)


def test_a_malformed_message_gets_an_error_and_the_connection_stays_up(rig: Rig):
    panel = rig.panel()
    panel.socket.send("[1, 2]")
    assert panel.next("result")["ok"] is False
    assert panel.request("update", changes={"seed": 7})["ok"] is True


def test_a_failing_control_surface_does_not_undo_or_block_a_change(rig: Rig):
    def broken(kind: str, payload: dict[str, Any]) -> None:
        raise OSError("reply host unreachable")

    rig.web_control.subscribe(broken)
    panel = rig.panel()
    assert panel.request("update", changes={"seed": 8})["ok"] is True
    assert rig.osc_in.wait_for("/streamturbo/seed") == (8,)


def test_a_tablet_with_the_token_loads_the_whole_panel(rig: Rig):
    address = socket.gethostbyname(socket.gethostname())
    if address.startswith("127."):
        pytest.skip("this machine has no LAN address")
    web = WebServer(rig.web_control, host="0.0.0.0", port=0, token="secret")
    web.start()
    try:
        base = f"http://{address}:{web.port}"
        with pytest.raises(urllib.error.HTTPError, match="401"):
            urllib.request.urlopen(f"{base}/", timeout=5)
        tablet = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        page = tablet.open(f"{base}/?token=secret", timeout=5).read().decode()
        script = page.split('src="./', 1)[1].split('"', 1)[0]  # the page's own script, requested without ?token
        assert tablet.open(f"{base}/{script}", timeout=5).status == 200
    finally:
        web.stop()

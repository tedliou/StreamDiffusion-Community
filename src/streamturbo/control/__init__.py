"""Control: everything a Control Surface can do, in one place, so the Web Panel and OSC always agree (ADR-0008).

Surfaces never touch the pipeline. They call Control, and Control tells every subscriber about each change.
"""

import contextlib
import io
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from pydantic import ValidationError

from streamturbo import imageops
from streamturbo.frames import InputFrame, OutputFrame
from streamturbo.presets import PresetStore, save_last
from streamturbo.runtime import Runtime
from streamturbo.settings import describe
from streamturbo.transports import Transports

Listener = Callable[[str, dict[str, Any]], None]
log = logging.getLogger(__name__)

PREVIEW_WIDTH = 480


class Control:
    def __init__(
        self,
        runtime: Runtime,
        presets: PresetStore,
        transports: Transports,
        last_settings: Path | None = None,
    ) -> None:
        self._runtime = runtime
        self._presets = presets
        self._transports = transports
        self._last_settings = last_settings
        self._listeners: list[Listener] = []
        self._lock = threading.Lock()  # serialises changes, so events go out in version order
        self._listeners_lock = threading.Lock()
        self._gpu = GpuMonitor()

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Call `listener(kind, payload)` after every change; returns the unsubscribe function."""
        with self._listeners_lock:
            self._listeners.append(listener)

        def unsubscribe() -> None:
            with self._listeners_lock, contextlib.suppress(ValueError):
                self._listeners.remove(listener)

        return unsubscribe

    def schema(self) -> list[dict[str, Any]]:
        return describe()

    def settings(self) -> dict[str, Any]:
        settings, version = self._runtime.settings()
        return {"settings": settings.model_dump(), "version": version}

    def update(self, changes: Mapping[str, Any]) -> int:
        """Apply a partial, possibly nested, change. Raises ValueError and changes nothing when it is invalid."""
        with self._lock:
            version = self._runtime.update(changes)
            self._changed()
            return version

    def presets(self) -> dict[str, Any]:
        return {"presets": [asdict(info) for info in self._presets.list()]}

    def save_preset(self, name: str) -> None:
        with self._lock:
            self._presets.save(name, self._runtime.settings()[0])
        self._emit("presets", self.presets())

    def recall_preset(self, name: str) -> int:
        with self._lock:
            version = self._runtime.update(self._presets.load(name))
            self._changed()
            return version

    def rename_preset(self, name: str, new_name: str) -> None:
        with self._lock:
            self._presets.rename(name, new_name)
        self._emit("presets", self.presets())

    def delete_preset(self, name: str) -> None:
        with self._lock:
            self._presets.delete(name)
        self._emit("presets", self.presets())

    def list_sources(self, transport: str) -> list[str]:
        if transport not in ("ndi", "spout"):
            raise ValueError(f"unknown transport {transport!r}")
        return self._transports.list_senders(transport)

    def status(self) -> dict[str, Any]:
        return asdict(self._runtime.status()) | self._gpu.sample()

    def previews(self) -> tuple[bytes | None, bytes | None]:
        """JPEG thumbnails of the latest Input and Output Frames."""
        input_frame, output_frame = self._runtime.latest_frames()
        return _jpeg(input_frame), _jpeg(output_frame)

    def _changed(self) -> None:
        settings, version = self._runtime.settings()
        self._emit("settings", {"settings": settings.model_dump(), "version": version})
        if self._last_settings is not None:
            try:
                save_last(self._last_settings, settings)
            except OSError:  # the change is live either way; it just won't be restored on the next launch
                log.exception("could not save the last-used Settings")

    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        with self._listeners_lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(kind, payload)
            except Exception:  # one Control Surface failing must not fail the change or starve the others
                log.exception("a Control Surface failed to receive a %s event", kind)


def error_text(error: BaseException) -> str:
    """A short, readable message, e.g. `strength: Input should be less than or equal to 1`."""
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'settings'}: {e['msg']}" for e in error.errors())
    if isinstance(error, KeyError):
        return f"missing field {error}"
    return str(error)


def _jpeg(frame: InputFrame | OutputFrame | None) -> bytes | None:
    if frame is None:
        return None
    from PIL import Image

    row_bytes = frame.row_bytes if isinstance(frame, InputFrame) else frame.width * frame.format.bytes_per_pixel
    rgb = imageops.to_rgb(frame.data, frame.width, frame.height, row_bytes, frame.format)
    height = max(1, round(frame.height * PREVIEW_WIDTH / frame.width))
    small = F.interpolate(rgb, size=(height, PREVIEW_WIDTH), mode="area") if frame.width > PREVIEW_WIDTH else rgb
    pixels = (small[0] * 255).round().clamp(0, 255).to(torch.uint8).permute(1, 2, 0).contiguous().numpy()
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format="JPEG", quality=75)
    return buffer.getvalue()


class GpuMonitor:
    """VRAM and power through NVML; empty values where there is no NVIDIA GPU (CI)."""

    def __init__(self) -> None:
        self._handle: Any = None
        try:
            import pynvml

            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            self._handle = None

    def sample(self) -> dict[str, float | None]:
        empty: dict[str, float | None] = {"vram_used_gib": None, "vram_total_gib": None, "power_w": None}
        if self._handle is None:
            return empty
        try:
            import pynvml

            memory = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            return {
                "vram_used_gib": round(int(memory.used) / 2**30, 2),
                "vram_total_gib": round(int(memory.total) / 2**30, 2),
                "power_w": round(pynvml.nvmlDeviceGetPowerUsage(self._handle) / 1000, 1),
            }
        except Exception:
            return empty

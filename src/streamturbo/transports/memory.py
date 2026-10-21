"""In-memory Transport: a Source and Sink inside the process, for tests and `bench`."""

import threading
import time
from collections.abc import Callable

import torch

from streamturbo.frames import InputFrame, OutputFrame, PixelFormat, host_buffer


def input_frame(pixels: torch.Tensor, fmt: PixelFormat = PixelFormat.RGBA) -> InputFrame:
    """An Input Frame from (H, W, 4) uint8 pixels."""
    height, width, _ = pixels.shape
    data = host_buffer(pixels.numel())
    data.copy_(pixels.reshape(-1))
    return InputFrame(data, width, height, fmt)


class MemorySource:
    """Yields the frames pushed into it. With `repeat_fps`, it re-yields the last frame at that rate, like a camera."""

    def __init__(self, repeat_fps: float | None = None) -> None:
        self._period = 1 / repeat_fps if repeat_fps else None
        self._next_repeat = 0.0
        self._pending: list[InputFrame] = []
        self._last: InputFrame | None = None
        self._failure: Exception | None = None
        self._ready = threading.Condition()
        self.opened = 0  # times open() was called

    def push(self, frame: InputFrame) -> None:
        with self._ready:
            self._pending.append(frame)
            self._ready.notify_all()

    def fail(self, error: Exception) -> None:
        """Make the next receive() raise, as a broken connection would."""
        with self._ready:
            self._failure = error
            self._ready.notify_all()

    def open(self) -> None:
        self.opened += 1

    def receive(self, timeout: float) -> InputFrame | None:
        with self._ready:
            if self._period is not None and self._last is not None:
                timeout = min(timeout, max(0.0, self._next_repeat - time.monotonic()))
            self._ready.wait_for(lambda: self._pending or self._failure, timeout)
            if self._failure is not None:
                error, self._failure = self._failure, None
                raise error
            if self._pending:
                self._last = self._pending.pop(0)
            elif self._period is None or self._last is None or time.monotonic() < self._next_repeat:
                return None
            if self._period is not None:
                self._next_repeat = time.monotonic() + self._period
            return self._last

    def close(self) -> None:
        pass


class MemorySink:
    """Keeps every Output Frame it is sent."""

    def __init__(self, fmt: PixelFormat = PixelFormat.RGBA, delay: float = 0.0) -> None:
        self.format = fmt
        self.frames: list[OutputFrame] = []
        self._delay = delay
        self._arrived = threading.Condition()

    def open(self) -> None:
        pass

    def send(self, frame: OutputFrame) -> None:
        if self._delay:
            time.sleep(self._delay)
        with self._arrived:
            self.frames.append(frame)
            self._arrived.notify_all()

    def close(self) -> None:
        pass

    def wait_for(self, predicate: Callable[[OutputFrame], bool], timeout: float = 10.0) -> OutputFrame:
        """Block until a frame satisfying `predicate` has been sent, and return it."""
        with self._arrived:
            found = self._arrived.wait_for(lambda: next((f for f in self.frames if predicate(f)), None), timeout)
            if found is None:
                raise TimeoutError("no matching Output Frame was sent")
            return found

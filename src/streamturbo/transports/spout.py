"""Spout Transport via SpoutGL: uncompressed same-machine links (ADR-0004).

Each endpoint creates its own hidden OpenGL context in open(), on the thread that then uses it.
"""

# SpoutGL is a compiled module without type stubs, so pyright cannot see its members.
# pyright: reportAttributeAccessIssue=false

import time

import SpoutGL
import torch
from SpoutGL.enums import GL_RGBA

from streamturbo.frames import InputFrame, OutputFrame, PixelFormat, host_buffer

_POLL = 0.001  # Spout has no blocking receive without sender-side frame sync
# Without Spout frame counting every receive looks new, so copies are capped at this interval.
_MIN_INTERVAL = 1 / 120


def list_spout_senders() -> list[str]:
    receiver = SpoutGL.SpoutReceiver()
    try:
        return sorted(receiver.getSenderList())
    finally:
        receiver.releaseReceiver()


class SpoutSource:
    def __init__(self, name: str) -> None:
        self.name = name  # empty: the active sender
        self._receiver: SpoutGL.SpoutReceiver | None = None
        self._size = (0, 0)
        self._settled = False  # the first image after a (re)connection or resize comes back empty
        self._last_count = -1
        self._next_copy = 0.0
        self._buffer: torch.Tensor | None = None

    def open(self) -> None:
        receiver = SpoutGL.SpoutReceiver()
        if not receiver.createOpenGL():
            raise RuntimeError("Spout could not create an OpenGL context")
        receiver.setReceiverName(self.name)
        self._receiver, self._size, self._last_count = receiver, (0, 0), -1
        self._buffer = None

    def receive(self, timeout: float) -> InputFrame | None:
        assert self._receiver is not None
        receiver = self._receiver
        deadline = time.monotonic() + timeout
        while True:
            wait = self._next_copy - time.monotonic()
            if wait > 0:
                if wait > deadline - time.monotonic():
                    time.sleep(max(0.0, deadline - time.monotonic()))
                    return None
                time.sleep(wait)
            width, height = self._size
            if width and (self._buffer is None or self._buffer.numel() != width * height * 4):
                self._buffer = host_buffer(width * height * 4)  # reused until handed out as a frame
            buffer = self._buffer if width else None
            received = receiver.receiveImage(None if buffer is None else buffer.numpy(), GL_RGBA, False, 0)
            if receiver.isUpdated():  # connected, or the sender changed size: receive again at the new size
                self._size = (receiver.getSenderWidth(), receiver.getSenderHeight())
                self._settled = False
                continue
            if received and buffer is not None and self._is_new(receiver):
                if self._settled:
                    self._next_copy = time.monotonic() + _MIN_INTERVAL
                    self._buffer = None
                    return InputFrame(buffer, width, height, PixelFormat.RGBA)
                self._settled = True
            if time.monotonic() >= deadline:
                return None
            time.sleep(_POLL)

    def _is_new(self, receiver: SpoutGL.SpoutReceiver) -> bool:
        if not receiver.isFrameCountEnabled():
            return receiver.isFrameNew()
        count = receiver.getSenderFrame()
        new, self._last_count = count != self._last_count, count
        return new

    def close(self) -> None:
        if self._receiver is not None:
            self._receiver.releaseReceiver()
            self._receiver.closeOpenGL()
            self._receiver = None


class SpoutSink:
    format = PixelFormat.RGBA

    def __init__(self, name: str) -> None:
        self.name = name
        self._sender: SpoutGL.SpoutSender | None = None

    def open(self) -> None:
        sender = SpoutGL.SpoutSender()
        if not sender.createOpenGL():
            raise RuntimeError("Spout could not create an OpenGL context")
        sender.setSenderName(self.name)
        self._sender = sender

    def send(self, frame: OutputFrame) -> None:
        assert self._sender is not None
        if not self._sender.sendImage(frame.data.numpy(), frame.width, frame.height, GL_RGBA, False, 0):
            raise RuntimeError(f"Spout could not send to {self.name!r}")

    def close(self) -> None:
        if self._sender is not None:
            self._sender.releaseSender()
            self._sender.closeOpenGL()
            self._sender = None

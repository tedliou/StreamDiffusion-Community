"""Transport: the video link a Source or Sink uses (ADR-0004).

`open`, `receive`/`send` and `close` are always called from the one thread that owns the endpoint,
so implementations may keep thread-bound state such as an OpenGL context.
"""

from typing import Protocol

from streamturbo.frames import InputFrame, OutputFrame, PixelFormat
from streamturbo.settings import SinkSettings, SourceSettings


class Source(Protocol):
    def open(self) -> None: ...

    def receive(self, timeout: float) -> InputFrame | None:
        """The next Input Frame, or None when none arrived within `timeout` seconds.

        A Source reconnects to its sender by itself; a lost sender simply yields None.
        """
        ...

    def close(self) -> None: ...


class Sink(Protocol):
    format: PixelFormat  # the pixel format send() expects

    def open(self) -> None: ...

    def send(self, frame: OutputFrame) -> None: ...

    def close(self) -> None: ...


def create_source(settings: SourceSettings) -> Source | None:
    if settings.transport == "ndi":
        from streamturbo.transports.ndi import NdiSource

        return NdiSource(settings.name)
    if settings.transport == "spout":
        from streamturbo.transports.spout import SpoutSource

        return SpoutSource(settings.name)
    return None


def create_sink(settings: SinkSettings) -> Sink:
    if settings.transport == "ndi":
        from streamturbo.transports.ndi import NdiSink

        return NdiSink(settings.name, settings.fps)
    from streamturbo.transports.spout import SpoutSink

    return SpoutSink(settings.name)


def list_senders(transport: str, timeout: float = 2.0) -> list[str]:
    """Names of the senders currently visible on a Transport."""
    if transport == "ndi":
        from streamturbo.transports.ndi import list_ndi_senders

        return list_ndi_senders(timeout)
    if transport == "spout":
        from streamturbo.transports.spout import list_spout_senders

        return list_spout_senders()
    raise ValueError(f"unknown transport {transport!r}")

"""NDI Transport via cyndilib, whose wheel bundles the NDI runtime (ADR-0004).

Frames are received in their native UYVY (or BGRA when they carry alpha) and converted on the GPU.
They are pulled through NDI's frame synchroniser, which never blocks: cyndilib's blocking receive()
holds the GIL while NDI waits and starved the generate thread.
Output Frames are sent as UYVY, which the NDI encoder takes without a CPU conversion.
"""

import time
from fractions import Fraction

from cyndilib.finder import Finder
from cyndilib.receiver import Receiver
from cyndilib.sender import Sender
from cyndilib.video_frame import VideoFrameSync, VideoSendFrame
from cyndilib.wrapper.ndi_recv import RecvBandwidth, RecvColorFormat
from cyndilib.wrapper.ndi_structs import FourCC

from streamturbo.frames import InputFrame, OutputFrame, PixelFormat, host_buffer

_POLL = 1 / 240  # how often the frame synchroniser is checked for a new frame

_FORMATS = {
    FourCC.UYVY: PixelFormat.UYVY,
    FourCC.BGRA: PixelFormat.BGRA,
    FourCC.BGRX: PixelFormat.BGRX,
    FourCC.RGBA: PixelFormat.RGBA,
    FourCC.RGBX: PixelFormat.RGBX,
}


def matches(sender: str, wanted: str) -> bool:
    """`wanted` names a sender as "HOST (stream)" or by its stream name alone; empty matches any."""
    if not wanted:
        return True
    stream = sender[sender.find("(") + 1 : sender.rfind(")")] if "(" in sender else sender
    return wanted.casefold() in (sender.casefold(), stream.casefold())


def list_ndi_senders(timeout: float = 2.0) -> list[str]:
    with Finder() as finder:
        finder.wait_for_sources(timeout)
        return sorted(finder.get_source_names())


class NdiSource:
    def __init__(self, name: str) -> None:
        self.name = name
        self._finder: Finder | None = None
        self._receiver: Receiver | None = None
        self._frame: VideoFrameSync | None = None
        self._last_timestamp: float | None = None

    def open(self) -> None:
        self._finder = Finder()
        self._finder.open()
        self._frame = VideoFrameSync()
        self._receiver = Receiver(
            color_format=RecvColorFormat.UYVY_BGRA, bandwidth=RecvBandwidth.highest, recv_name="StreamTurbo"
        )
        self._receiver.frame_sync.set_video_frame(self._frame)
        self._last_timestamp = None

    def receive(self, timeout: float) -> InputFrame | None:
        assert self._finder is not None and self._receiver is not None and self._frame is not None
        if self._receiver.source is None and not self._connect(timeout):
            return None
        frame, sync = self._frame, self._receiver.frame_sync
        deadline = time.monotonic() + timeout
        while True:
            sync.capture_video()  # the latest frame, by reference; repeats until a new one arrives
            timestamp = frame.get_timestamp_posix()
            if frame.xres and timestamp != self._last_timestamp:
                break
            if time.monotonic() >= deadline:
                return None
            time.sleep(_POLL)
        self._last_timestamp = timestamp
        fmt = _FORMATS.get(frame.get_fourcc())
        if fmt is None:
            raise ValueError(f"unsupported NDI pixel format {frame.get_fourcc()!r}")
        pixels = frame.get_array()
        data = host_buffer(pixels.size)
        data.numpy()[:] = pixels.reshape(-1)
        del pixels  # the next capture refuses to overwrite a frame that is still viewed
        width, height = frame.get_resolution()
        return InputFrame(data, width, height, fmt, frame.get_line_stride())

    def _connect(self, timeout: float) -> bool:
        """Connect to the wanted sender once it is visible. NDI reconnects by itself after that."""
        assert self._finder is not None and self._receiver is not None
        deadline = time.monotonic() + timeout
        while True:
            for source in self._finder.iter_sources():
                if matches(source.name, self.name):
                    self._receiver.connect_to(source)
                    return True
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self._finder.wait(remaining):
                return False

    def close(self) -> None:
        if self._receiver is not None:
            self._receiver.disconnect()
            self._receiver = None
        if self._finder is not None:
            self._finder.close()
            self._finder = None


class NdiSink:
    format = PixelFormat.UYVY

    def __init__(self, name: str, fps: float) -> None:
        self.name = name
        self.fps = Fraction(fps).limit_denominator(1001)
        self._sender: Sender | None = None
        self._size: tuple[int, int] | None = None
        self._in_flight: OutputFrame | None = None  # NDI reads an async frame until the next send

    def open(self) -> None:
        pass  # the sender opens on the first frame, when its resolution is known

    def send(self, frame: OutputFrame) -> None:
        if self._size != (frame.width, frame.height):
            self._start(frame.width, frame.height)
        assert self._sender is not None
        self._sender.write_video_async(frame.data.numpy())
        self._in_flight = frame

    def _start(self, width: int, height: int) -> None:
        self.close()
        video = VideoSendFrame()
        video.set_resolution(width, height)
        video.set_fourcc(FourCC.UYVY)
        video.set_frame_rate(self.fps)
        sender = Sender(self.name, clock_video=False)
        sender.set_video_frame(video)
        sender.open()
        self._sender, self._size = sender, (width, height)

    def close(self) -> None:
        if self._sender is not None:
            self._sender.close()
            self._sender, self._size, self._in_flight = None, None, None

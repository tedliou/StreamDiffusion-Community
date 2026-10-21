"""Pipeline runtime: receive, generate and send threads joined by latest-frame mailboxes (ADR-0003)."""

import threading
import time
from collections import deque
from dataclasses import dataclass
from types import TracebackType
from typing import Literal

import torch

from streamturbo import imageops
from streamturbo.backends import Backend
from streamturbo.frames import InputFrame, OutputFrame, PixelFormat, host_buffer
from streamturbo.generation import GenerationCore
from streamturbo.mailbox import Mailbox
from streamturbo.settings import LIVE_FIELDS, Settings
from streamturbo.transports import Sink, Source

POLL = 0.05  # seconds a thread waits before re-checking whether to stop
IN_FLIGHT = 2  # Generations queued on the GPU at once: enough to overlap, few enough to keep frames fresh

METRICS_WINDOW = 120  # Output Frames the metrics are computed over

SourceState = Literal["none", "waiting", "live", "lost"]


class _Timing:
    """Marks the start and end of one Generation without blocking the generate thread."""

    def __init__(self, device: torch.device) -> None:
        self._cuda = device.type == "cuda"
        if self._cuda:
            self._start = torch.cuda.Event(enable_timing=True)
            self._end = torch.cuda.Event(enable_timing=True)
            self._start.record()
        else:
            self._began = time.perf_counter()

    def finish(self) -> None:
        if self._cuda:
            self._end.record()
        else:
            self._ms = (time.perf_counter() - self._began) * 1000

    def wait_ms(self) -> float:
        """Wait for this Generation's GPU work only (no device-wide synchronise) and return its duration."""
        if self._cuda:
            self._end.synchronize()
            return self._start.elapsed_time(self._end)
        return self._ms


@dataclass(frozen=True)
class RuntimeStatus:
    source_state: SourceState  # none: no Source (txt2img); waiting: no frame yet; lost: frames stopped
    error: str | None  # the latest Transport or Generation error, cleared when the Source comes back
    frames_received: int
    frames_sent: int
    dropped_frames: int  # replaced in a mailbox before anyone read them
    throughput_fps: float  # Output Frames per second over the recent window
    generation_ms_p50: float  # Generation Time percentiles over the recent window
    generation_ms_p95: float
    backend: str


@dataclass(frozen=True)
class _Generated:
    frame: OutputFrame
    timing: _Timing


class Runtime:
    def __init__(
        self,
        settings: Settings,
        backend: Backend,
        source: Source | None,
        sink: Sink,
        *,
        source_timeout: float = 1.0,
        reconnect_delay: float = 1.0,
    ) -> None:
        self._settings = settings
        self._settings_version = 0
        self._pending: tuple[Settings, int] | None = None  # submitted, applied between two Output Frames
        self._backend = backend
        self._core = GenerationCore(backend)
        self._source = source
        self._sink = sink
        self._inputs: Mailbox[tuple[int, InputFrame]] = Mailbox()
        self._outputs: Mailbox[_Generated] = Mailbox()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._received = self._sent = self._dropped = 0
        self._source_state: SourceState = "waiting" if source is not None else "none"
        self._error: str | None = None
        self._generation_ms: deque[float] = deque(maxlen=METRICS_WINDOW)
        self._sent_at: deque[float] = deque(maxlen=METRICS_WINDOW)
        self._source_timeout = source_timeout
        self._reconnect_delay = reconnect_delay

    def start(self) -> None:
        self._core.set_prompt(self._settings.prompt)
        self._core.set_seed(self._settings.seed)
        self._warm_up()
        loops = [self._generate_loop, self._send_loop]
        if self._source is not None:
            loops.insert(0, self._receive_loop)
        for loop in loops:
            thread = threading.Thread(target=loop, name=f"streamturbo-{loop.__name__.strip('_')}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def _warm_up(self) -> None:
        """Generate once from a black frame so kernel selection (seconds on first use) happens before going live."""
        gen = self._settings.generation
        black = InputFrame(host_buffer(gen.width * gen.height * 4).zero_(), gen.width, gen.height, PixelFormat.RGBA)
        self._generate(-1, black).timing.wait_ms()

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join()
        self._threads.clear()

    def update(self, **changes: object) -> int:
        """Submit Live Setting changes; returns the Settings version Output Frames will carry once applied."""
        if fixed := sorted(set(changes) - LIVE_FIELDS):
            raise ValueError(f"{', '.join(fixed)} cannot change while running; restart the Runtime")
        with self._lock:
            current, version = self._pending or (self._settings, self._settings_version)
            updated = Settings.model_validate({**current.model_dump(), **changes})
            self._pending = (updated, version + 1)
            return version + 1

    def _apply_pending(self) -> None:
        with self._lock:  # one step, so a concurrent update() never builds on superseded Settings
            pending, self._pending = self._pending, None
            if pending is not None:
                self._settings, self._settings_version = pending
        if pending is not None:
            self._core.set_prompt(self._settings.prompt)
            self._core.set_seed(self._settings.seed)

    def status(self) -> RuntimeStatus:
        with self._lock:
            return RuntimeStatus(
                source_state=self._source_state,
                error=self._error,
                frames_received=self._received,
                frames_sent=self._sent,
                dropped_frames=self._dropped,
                throughput_fps=_rate(self._sent_at),
                generation_ms_p50=_percentile(self._generation_ms, 0.50),
                generation_ms_p95=_percentile(self._generation_ms, 0.95),
                backend=self._backend.name,
            )

    def _record_error(self, error: Exception) -> None:
        with self._lock:
            self._error = f"{type(error).__name__}: {error}"

    def _set_source_state(self, state: SourceState, error: Exception | None = None) -> None:
        if error is not None:
            self._record_error(error)
        with self._lock:
            if state == "live" and self._source_state != "live":
                self._error = None  # a Source that comes back clears the error that took it down
            if state != "lost" or self._source_state == "live":
                self._source_state = state

    def _count(self, *, received: int = 0, dropped: int = 0) -> None:
        with self._lock:
            self._received += received
            self._dropped += dropped

    def _record_sent(self, generation_ms: float) -> None:
        with self._lock:
            self._sent += 1
            self._generation_ms.append(generation_ms)
            self._sent_at.append(time.monotonic())

    def __enter__(self) -> "Runtime":
        self.start()
        return self

    def __exit__(self, *_: type[BaseException] | BaseException | TracebackType | None) -> None:
        self.stop()

    def _receive_loop(self) -> None:
        assert self._source is not None
        source = self._source
        seq = 0
        while not self._stop.is_set():
            try:
                source.open()
                last_frame = time.monotonic()
                while not self._stop.is_set():
                    frame = source.receive(POLL)
                    now = time.monotonic()
                    if frame is None:
                        if now - last_frame > self._source_timeout:
                            self._set_source_state("lost")
                        continue
                    last_frame = now
                    self._set_source_state("live")
                    self._count(received=1, dropped=self._inputs.put((seq, frame)))
                    seq += 1
            except Exception as error:
                self._set_source_state("lost", error)
                self._stop.wait(self._reconnect_delay)
            finally:
                source.close()

    def _generate_loop(self) -> None:
        device = self._backend.device
        stream = torch.cuda.Stream(device) if device.type == "cuda" else None
        next_due = time.monotonic()
        in_flight: deque[_Timing] = deque()
        while not self._stop.is_set():
            # Wait for a free slot before taking a frame, so the frame taken is the freshest one.
            if len(in_flight) == IN_FLIGHT:
                in_flight.popleft().wait_ms()
            if self._source is not None:
                item = self._inputs.take(POLL)
                if item is None:
                    continue
            else:  # txt2img: pace Generation to the Sink's frame rate
                next_due += 1 / self._settings.sink.fps
                if self._stop.wait(max(0.0, next_due - time.monotonic())):
                    break
                next_due = max(next_due, time.monotonic() - 1 / self._settings.sink.fps)
                item = (-1, None)
            try:
                with torch.cuda.stream(stream):
                    self._apply_pending()
                    generated = self._generate(*item)
            except Exception as error:  # e.g. a CUDA error: report it and carry on with the next frame
                self._record_error(error)
                self._stop.wait(POLL)
                continue
            in_flight.append(generated.timing)
            self._count(dropped=self._outputs.put(generated))

    def _generate(self, seq: int, frame: InputFrame | None) -> _Generated:
        settings, device = self._settings, self._backend.device
        gen = settings.generation
        timing = _Timing(device)
        image = None
        if frame is not None:
            raw = frame.data.to(device, non_blocking=True)
            rgb = imageops.to_rgb(raw, frame.width, frame.height, frame.row_bytes, frame.format)
            image = imageops.fit(rgb, gen.width, gen.height, settings.fit_mode) * 2 - 1
        result = self._core.generate(image, settings.strength, gen.width, gen.height)
        out, fmt = settings.output, self._sink.format
        packed = imageops.to_bytes((result.float() + 1) / 2, out.width, out.height, fmt)
        host = host_buffer(packed.numel())
        host.copy_(packed, non_blocking=True)
        timing.finish()
        output = OutputFrame(host, out.width, out.height, fmt, seq, self._settings_version)
        return _Generated(output, timing)

    def _send_loop(self) -> None:
        sink = self._sink
        while not self._stop.is_set():
            try:
                sink.open()
                while not self._stop.is_set():
                    generated = self._outputs.take(POLL)
                    if generated is None:
                        continue
                    generation_ms = generated.timing.wait_ms()
                    sink.send(generated.frame)
                    self._record_sent(generation_ms)
            except Exception as error:
                self._record_error(error)
                self._stop.wait(self._reconnect_delay)
            finally:
                sink.close()


def _rate(times: deque[float]) -> float:
    if len(times) < 2 or times[-1] == times[0]:
        return 0.0
    return (len(times) - 1) / (times[-1] - times[0])


def _percentile(values: deque[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]

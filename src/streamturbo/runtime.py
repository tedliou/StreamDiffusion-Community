"""Pipeline runtime: receive, generate and send threads joined by latest-frame mailboxes (ADR-0003).

Settings change only through update(). The generate thread applies the latest snapshot between two Output Frames
(ADR-0008); the receive and send threads follow the applied snapshot and reopen their Transport when it changes.
"""

import dataclasses
import threading
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Literal

import torch
import torch.nn.functional as F

from streamturbo import imageops
from streamturbo.backends import Backend, BestBackend, EngineStatus
from streamturbo.frames import InputFrame, OutputFrame, PixelFormat, host_buffer
from streamturbo.generation import GenerationCore, Glide
from streamturbo.mailbox import Mailbox
from streamturbo.model_spec import SD_TURBO, ModelSpec
from streamturbo.settings import Settings, SimilarFrameSkip
from streamturbo.transports import Sink, Source, Transports

POLL = 0.05  # seconds a thread waits before re-checking whether to stop
IN_FLIGHT = 2  # Generations queued on the GPU at once: enough to overlap, few enough to keep frames fresh

METRICS_WINDOW = 120  # Output Frames the metrics are computed over
SKIP_CELL = 16  # Similar Frame Skip compares Input Frames averaged over cells of this many pixels per side

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
            self._ms = 0.0

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
    settings_version: int  # the Settings version Output Frames are generated with now
    frames_received: int
    frames_sent: int  # including frames repeated by Similar Frame Skip
    frames_skipped: int  # Output Frames repeated by Similar Frame Skip instead of generated
    dropped_frames: int  # replaced in a mailbox before anyone read them
    throughput_fps: float  # Output Frames generated per second over the recent window, repeats excluded
    generation_ms_p50: float  # Generation Time percentiles over the recent window
    generation_ms_p95: float
    backend: str  # the Backend generating now
    engines: EngineStatus  # TensorRT Engine build progress; "off" for a Backend that builds none
    generation_width: int  # the Generation Resolution in effect: below the Settings' when the Model Spec is capped
    generation_height: int


@dataclass(frozen=True)
class _Generated:
    frame: OutputFrame
    timing: _Timing  # for a repeat, the original's: sending still waits for its copy to the host
    repeated: bool = False  # the last generated Output Frame again, repeated by Similar Frame Skip


class _SimilarFrameSkip:
    """Decides whether an Input Frame is close enough to the last generated one to repeat its Output Frame.

    It compares cell averages computed on the prepare stream, so deciding waits for that frame's upload and
    conversion only, never for a Generation in flight.
    """

    def __init__(self) -> None:
        self._reference: torch.Tensor | None = None  # cell averages of the last generated Input Frame
        self._key: object = None  # everything else the last Output Frame depends on
        self._skips = 0

    def similar(self, image: torch.Tensor, key: object, settings: SimilarFrameSkip) -> bool:
        cells = F.avg_pool2d(image, SKIP_CELL, ceil_mode=True)
        reference, same_key = self._reference, key == self._key
        if (
            settings.threshold > 0
            and same_key
            and self._skips < settings.max_skips
            and reference is not None
            and reference.shape == cells.shape
            and (cells - reference).abs().mean().item() / 2 < settings.threshold  # images span [-1, 1]
        ):
            self._skips += 1  # the reference stays the generated frame, so slow drift adds up
            return True
        self._reference, self._key, self._skips = cells, key, 0
        return False


class Runtime:
    def __init__(
        self,
        settings: Settings,
        backend: Backend,
        transports: Transports,
        *,
        source_timeout: float = 1.0,
        reconnect_delay: float = 1.0,
        spec: ModelSpec = SD_TURBO,
    ) -> None:
        """`spec` is the Model Spec the Backend generates with; Low-VRAM Mode caps its Generation Resolutions."""
        self._settings = settings  # applied: what Output Frames are generated with
        self._settings_version = 0
        self._pending: tuple[Settings, int] | None = None  # submitted, applied between two Output Frames
        self._backend = backend
        self._core = GenerationCore(backend)
        self._strength = Glide(settings.strength)  # what Output Frames are generated with while gliding
        self._transports = transports
        self._sink_format = PixelFormat.RGBA  # what the open Sink takes; frames in another format are not sent
        self._inputs: Mailbox[tuple[int, InputFrame]] = Mailbox()
        self._outputs: Mailbox[_Generated] = Mailbox()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._received = self._sent = self._dropped = self._skipped = 0
        self._source_state: SourceState = "waiting"
        self._error: str | None = None
        self._last_input: InputFrame | None = None
        self._last_output: OutputFrame | None = None
        self._generation_ms: deque[float] = deque(maxlen=METRICS_WINDOW)
        self._sent_at: deque[float] = deque(maxlen=METRICS_WINDOW)
        self._source_timeout = source_timeout
        self._reconnect_delay = reconnect_delay
        self._spec = spec

    def start(self) -> None:
        self._core.set_prompts(_blend(self._settings))
        self._core.set_seed(self._settings.seed)
        self._warm_up()  # on the fallback, before an exclusive Engine build can take the GPU
        self._choose_backend()
        for loop in (self._receive_loop, self._generate_loop, self._send_loop):
            thread = threading.Thread(target=loop, name=f"streamturbo-{loop.__name__.strip('_')}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def _warm_up(self) -> None:
        """Generate once from a black frame so kernel selection (seconds on first use) happens before going live."""
        gen = self._settings.generation
        black = InputFrame(host_buffer(gen.width * gen.height * 4).zero_(), gen.width, gen.height, PixelFormat.RGBA)
        device = self._backend.device
        # On a stream of its own, as Generation runs: TensorRT synchronises extra work on the default stream.
        with torch.cuda.stream(torch.cuda.Stream(device) if device.type == "cuda" else None):
            self._generate(-1, self._prepare(black)).timing.wait_ms()
        self._core.forget_previous()  # so Temporal Smoothing never fades in from the black frame

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join()
        self._threads.clear()

    def update(self, changes: Mapping[str, Any] | None = None, /, **fields: Any) -> int:
        """Submit a partial, possibly nested, Settings change; returns the version Output Frames will carry.

        Raises ValueError (a pydantic ValidationError) and changes nothing when the result is invalid.
        """
        with self._lock:
            current, version = self._pending or (self._settings, self._settings_version)
            self._pending = (current.merged({**(changes or {}), **fields}), version + 1)
            return version + 1

    def settings(self) -> tuple[Settings, int]:
        """The latest submitted Settings and their version: what every Control Surface should show."""
        with self._lock:
            return self._pending or (self._settings, self._settings_version)

    def latest_frames(self) -> tuple[InputFrame | None, OutputFrame | None]:
        """The last Input Frame received and the last Output Frame sent, for previews."""
        with self._lock:
            return self._last_input, self._last_output

    def _apply_pending(self) -> None:
        with self._lock:  # one step, so a concurrent update() never builds on superseded Settings
            previous, pending, self._pending = self._settings, self._pending, None
            if pending is not None:
                self._settings, self._settings_version = pending
        if pending is not None:
            if self._settings.prompts != previous.prompts:
                self._core.set_prompts(_blend(self._settings), self._settings.prompt_transition)
            if self._settings.seed != previous.seed:
                self._core.set_seed(self._settings.seed)
            if self._settings.strength != self._strength.target:
                self._strength.move_to(self._settings.strength, self._settings.strength_glide)
            if _picture(self._settings) != _picture(previous):
                self._core.forget_previous()  # an unrelated picture: nothing to smooth with or lean on
        self._choose_backend()

    def _choose_backend(self) -> None:
        """Between two Generations: adopt freshly built Engines, or follow a forced Backend."""
        if isinstance(self._backend, BestBackend):
            self._backend.choose(self._settings.backend)

    def _paused(self) -> bool:
        return isinstance(self._backend, BestBackend) and self._backend.engine_status().paused

    def status(self) -> RuntimeStatus:
        with self._lock:
            width, height = self._generation_size(self._settings)
            return RuntimeStatus(
                source_state=self._source_state,
                error=self._error,
                settings_version=self._settings_version,
                frames_received=self._received,
                frames_sent=self._sent,
                frames_skipped=self._skipped,
                dropped_frames=self._dropped,
                throughput_fps=_rate(self._sent_at),
                generation_ms_p50=_percentile(self._generation_ms, 0.50),
                generation_ms_p95=_percentile(self._generation_ms, 0.95),
                backend=self._backend.name,
                engines=self._backend.engine_status()
                if isinstance(self._backend, BestBackend)
                else EngineStatus("off"),
                generation_width=width,
                generation_height=height,
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

    def _record_received(self, seq: int, frame: InputFrame) -> None:
        dropped = self._inputs.put((seq, frame))
        with self._lock:
            self._received += 1
            self._dropped += dropped
            self._last_input = frame

    def _record_sent(self, frame: OutputFrame, generation_ms: float | None) -> None:
        """`generation_ms` is None for a frame repeated by Similar Frame Skip: sent, but not generated."""
        with self._lock:
            self._sent += 1
            self._last_output = frame
            if generation_ms is None:
                self._skipped += 1
            else:
                self._generation_ms.append(generation_ms)
                self._sent_at.append(time.monotonic())

    def __enter__(self) -> "Runtime":
        self.start()
        return self

    def __exit__(self, *_: type[BaseException] | BaseException | TracebackType | None) -> None:
        self.stop()

    def _receive_loop(self) -> None:
        seq, opened = 0, None
        while not self._stop.is_set():
            wanted = self._settings.source
            source: Source | None = None
            try:
                source = self._transports.source(wanted)
                if source is None:
                    self._set_source_state("none")
                    while not self._stop.is_set() and self._settings.source == wanted:
                        self._stop.wait(POLL)
                    continue
                if wanted != opened:  # a new Source, not a reconnection
                    self._set_source_state("waiting")
                    opened = wanted
                source.open()
                last_frame = time.monotonic()
                while not self._stop.is_set() and self._settings.source == wanted:
                    frame = source.receive(POLL)
                    now = time.monotonic()
                    if frame is None:
                        if now - last_frame > self._source_timeout:
                            self._set_source_state("lost")
                        continue
                    last_frame = now
                    self._set_source_state("live")
                    self._record_received(seq, frame)
                    seq += 1
            except Exception as error:
                self._set_source_state("lost", error)
                self._stop.wait(self._reconnect_delay)
            finally:
                if source is not None:
                    source.close()

    def _generate_loop(self) -> None:
        device = self._backend.device
        stream = torch.cuda.Stream(device) if device.type == "cuda" else None
        # Uploads and converts the next Input Frame while the previous Generation still runs on `stream`.
        prepare = torch.cuda.Stream(device) if device.type == "cuda" else None
        skip = _SimilarFrameSkip()
        last: _Generated | None = None  # the last generated Output Frame, which Similar Frame Skip repeats
        next_due = time.monotonic()
        in_flight: deque[_Timing] = deque()
        while not self._stop.is_set():
            # An exclusive Engine build has the GPU: let queued Generations finish, then wait for it, leaving
            # Settings changes pending, since applying a Prompt would use the text encoder the build moved away.
            if self._paused():
                while in_flight:
                    in_flight.popleft().wait_ms()
                self._stop.wait(POLL)
                continue
            # Wait for a free slot before taking a frame, so the frame taken is the freshest one.
            if len(in_flight) == IN_FLIGHT:
                in_flight.popleft().wait_ms()
            try:
                with torch.cuda.stream(stream):
                    self._apply_pending()  # every pass, so changes apply even while no frames arrive
                    if self._settings.source.transport != "none":
                        item = self._inputs.take(POLL)
                        if item is None:
                            continue
                        seq, image = item[0], self._prepare(item[1], prepare)
                        # While a glide or transition runs, equal Input Frames still need new Output Frames.
                        settling = not (self._core.settled() and self._strength.settled())
                        key = (self._settings_version, self._backend.name, seq if settling else None)
                        with torch.cuda.stream(prepare):  # where `image` was made: no wait on a Generation
                            similar = skip.similar(image, key, self._settings.similar_frame_skip)
                        if last is not None and similar:
                            frame = dataclasses.replace(last.frame, input_seq=seq)
                            self._hand_over(_Generated(frame, last.timing, repeated=True))
                            continue
                        if stream is not None and prepare is not None:
                            stream.wait_stream(prepare)
                            image.record_stream(stream)  # allocated on `prepare`, freed after use on `stream`
                    else:  # txt2img: pace Generation to the Sink's frame rate
                        period = 1 / self._settings.sink.fps
                        next_due = max(next_due + period, time.monotonic() - period)
                        if self._stop.wait(max(0.0, next_due - time.monotonic())):
                            break
                        seq, image = -1, None
                    generated = self._generate(seq, image)
            except Exception as error:  # e.g. a CUDA error: report it and carry on with the next frame
                self._record_error(error)
                self._stop.wait(POLL)
                continue
            in_flight.append(generated.timing)
            last = generated
            self._hand_over(generated)

    def _hand_over(self, generated: "_Generated") -> None:
        dropped = self._outputs.put(generated)
        with self._lock:
            self._dropped += dropped

    def _prepare(self, frame: InputFrame, stream: torch.cuda.Stream | None = None) -> torch.Tensor:
        """Upload an Input Frame and map it onto the Generation Resolution: (1, 3, H, W) in [-1, 1]."""
        settings, device = self._settings, self._backend.device
        width, height = self._generation_size(settings)
        with torch.cuda.stream(stream):
            raw = frame.data.to(device, non_blocking=True)
            rgb = imageops.to_rgb(raw, frame.width, frame.height, frame.row_bytes, frame.format)
            return imageops.fit(rgb, width, height, settings.fit_mode) * 2 - 1

    def _generation_size(self, settings: Settings) -> tuple[int, int]:
        """The Generation Resolution in effect: the requested one, reduced to what the Model Spec accepts."""
        return self._spec.fit(settings.generation.width, settings.generation.height)

    def _generate(self, seq: int, image: torch.Tensor | None) -> _Generated:
        settings, device = self._settings, self._backend.device
        width, height = self._generation_size(settings)
        timing = _Timing(device)
        strength = self._strength.value()
        result = self._core.generate(
            image, strength, width, height, settings.temporal_smoothing, settings.temporal_coherence
        )
        out, fmt = settings.output, self._sink_format
        if settings.upscaling:
            # Resized while still in the Backend's precision: a 4x picture in float32 would cost hundreds of MiB.
            result = imageops.fit(self._backend.upscale(result), out.width, out.height, "stretch")
        packed = imageops.to_bytes((result.float() + 1) / 2, out.width, out.height, fmt)
        host = host_buffer(packed.numel())
        host.copy_(packed, non_blocking=True)
        timing.finish()
        output = OutputFrame(host, out.width, out.height, fmt, seq, self._settings_version)
        return _Generated(output, timing)

    def _send_loop(self) -> None:
        while not self._stop.is_set():
            wanted = self._settings.sink
            sink: Sink | None = None
            try:
                sink = self._transports.sink(wanted)
                self._sink_format = sink.format
                sink.open()
                while not self._stop.is_set() and self._settings.sink == wanted:
                    generated = self._outputs.take(POLL)
                    if generated is None:
                        continue
                    generation_ms = generated.timing.wait_ms()
                    if generated.frame.format != sink.format:
                        continue  # generated for the previous Sink
                    sink.send(generated.frame)
                    self._record_sent(generated.frame, None if generated.repeated else generation_ms)
            except Exception as error:
                self._record_error(error)
                self._stop.wait(self._reconnect_delay)
            finally:
                if sink is not None:
                    sink.close()


def _picture(settings: Settings) -> tuple[object, ...]:
    """What makes Input Frames a different picture: another Source, or another mapping onto the Generation."""
    return settings.source, settings.generation, settings.fit_mode


def _blend(settings: Settings) -> list[tuple[str, float]]:
    return [(prompt.text, prompt.weight) for prompt in settings.prompts]


def _rate(times: deque[float]) -> float:
    if len(times) < 2 or times[-1] == times[0]:
        return 0.0
    return (len(times) - 1) / (times[-1] - times[0])


def _percentile(values: deque[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]

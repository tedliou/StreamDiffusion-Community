"""Seam 1: the Runtime driven through the in-memory Transport with a fake Backend."""

import time

import pytest
import torch

from streamturbo.frames import PixelFormat
from streamturbo.runtime import Runtime
from streamturbo.transports.memory import MemorySink, MemorySource, input_frame
from tests.conftest import FakeBackend


def solid(width: int, height: int, rgb: tuple[int, int, int]) -> torch.Tensor:
    pixels = torch.empty(height, width, 4, dtype=torch.uint8)
    pixels[..., :3] = torch.tensor(rgb, dtype=torch.uint8)
    pixels[..., 3] = 255
    return pixels


def test_input_frame_becomes_output_frame_at_output_resolution(small_settings):
    source, sink = MemorySource(), MemorySink(PixelFormat.RGBA)
    with Runtime(small_settings, FakeBackend(), source, sink):
        source.push(input_frame(solid(640, 480, (200, 40, 40))))
        out = sink.wait_for(lambda f: f.input_seq == 0)

    assert (out.width, out.height, out.format) == (320, 240, PixelFormat.RGBA)
    assert out.data.numel() == 320 * 240 * 4


def test_slow_backend_drops_stale_frames_but_never_the_latest(small_settings):
    source, sink = MemorySource(), MemorySink()
    with Runtime(small_settings, FakeBackend(unet_delay=0.05), source, sink) as runtime:
        for _ in range(30):
            source.push(input_frame(solid(320, 240, (0, 0, 0))))
            time.sleep(0.005)
        sink.wait_for(lambda f: f.input_seq == 29)
        status = runtime.status()

    seqs = [f.input_seq for f in sink.frames]
    assert seqs == sorted(set(seqs))  # in order, no repeats
    assert len(seqs) < 30
    assert status.dropped_frames == 30 - len(seqs)


def mean_rgb(frame) -> list[float]:
    pixels = frame.data.view(frame.height, frame.width, 4)[..., :3].float()
    return pixels.mean(dim=(0, 1)).tolist()


def test_live_update_applies_to_later_output_frames(small_settings):
    source, sink = MemorySource(repeat_fps=100), MemorySink()
    with Runtime(small_settings, FakeBackend(), source, sink) as runtime:
        source.push(input_frame(solid(320, 240, (200, 40, 40))))
        version = runtime.update(strength=0.0, prompt="a different prompt")
        out = sink.wait_for(lambda f: f.settings_version >= version)

    # Strength 0 keeps the Input Frame, so the output is the input colour.
    assert out.settings_version == version
    assert all(abs(a - b) <= 3 for a, b in zip(mean_rgb(out), (200, 40, 40), strict=True))


def test_update_rejects_invalid_and_non_live_settings(small_settings):
    with Runtime(small_settings, FakeBackend(), MemorySource(), MemorySink()) as runtime:
        with pytest.raises(ValueError, match="strength"):
            runtime.update(strength=1.5)
        with pytest.raises(ValueError, match="generation"):
            runtime.update(generation={"width": 512, "height": 512})


def wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError("condition not met")
        time.sleep(0.01)


def test_source_loss_holds_last_output_frame_and_recovers(small_settings):
    source, sink = MemorySource(), MemorySink()
    with Runtime(small_settings, FakeBackend(), source, sink, source_timeout=0.2) as runtime:
        assert runtime.status().source_state == "waiting"
        source.push(input_frame(solid(320, 240, (0, 0, 0))))
        sink.wait_for(lambda f: f.input_seq == 0)
        assert runtime.status().source_state == "live"

        wait_until(lambda: runtime.status().source_state == "lost")
        held = len(sink.frames)
        time.sleep(0.3)
        assert len(sink.frames) == held  # the last Output Frame stays on the Sink

        source.push(input_frame(solid(320, 240, (0, 0, 0))))
        sink.wait_for(lambda f: f.input_seq == 1)
        assert runtime.status().source_state == "live"


def test_source_error_is_reported_and_the_source_reopened(small_settings):
    source, sink = MemorySource(), MemorySink()
    with Runtime(small_settings, FakeBackend(), source, sink, reconnect_delay=0.05) as runtime:
        source.fail(ConnectionError("sender went away"))
        wait_until(lambda: source.opened == 2)
        assert "sender went away" in (runtime.status().error or "")

        source.push(input_frame(solid(320, 240, (0, 0, 0))))
        sink.wait_for(lambda f: f.input_seq == 0)


def test_without_a_source_the_runtime_generates_txt2img_at_the_sink_rate(small_settings):
    sink = MemorySink()
    with Runtime(small_settings, FakeBackend(), None, sink) as runtime:
        time.sleep(0.5)
        status = runtime.status()

    assert status.source_state == "none"
    assert all(f.input_seq == -1 for f in sink.frames)
    # 30 fps declared on the Sink: about 15 frames in half a second, never unthrottled.
    assert 5 <= len(sink.frames) <= 20


def test_status_reports_throughput_and_generation_time(small_settings):
    source, sink = MemorySource(repeat_fps=100), MemorySink()
    with Runtime(small_settings, FakeBackend(unet_delay=0.02), source, sink) as runtime:
        source.push(input_frame(solid(320, 240, (0, 0, 0))))
        wait_until(lambda: runtime.status().frames_sent >= 10)
        status = runtime.status()

    assert status.generation_ms_p50 >= 20
    assert status.generation_ms_p95 >= status.generation_ms_p50
    assert 5 < status.throughput_fps < 50
    assert status.backend == "fake"

"""Seam 1: the Runtime driven through the in-memory Transport with a fake Backend."""

import time

import pytest
import torch

from streamturbo.frames import PixelFormat
from streamturbo.runtime import IN_FLIGHT, Runtime
from streamturbo.transports.memory import input_frame
from tests.conftest import FakeBackend

RED, BLUE, BLACK = (200, 40, 40), (40, 40, 200), (0, 0, 0)


def solid(width: int, height: int, rgb: tuple[int, int, int]) -> torch.Tensor:
    pixels = torch.empty(height, width, 4, dtype=torch.uint8)
    pixels[..., :3] = torch.tensor(rgb, dtype=torch.uint8)
    pixels[..., 3] = 255
    return pixels


def mean_rgb(frame) -> list[float]:
    pixels = frame.data.view(frame.height, frame.width, 4)[..., :3].float()
    return pixels.mean(dim=(0, 1)).tolist()


def close_to(frame, rgb: tuple[int, int, int]) -> bool:
    return all(abs(a - b) <= 3 for a, b in zip(mean_rgb(frame), rgb, strict=True))


def wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError("condition not met")
        time.sleep(0.01)


def test_input_frame_becomes_output_frame_at_output_resolution(small_settings, net):
    source, sink = net.add_source("cam"), net.sink(small_settings.sink)
    with Runtime(small_settings, FakeBackend(), net):
        source.push(input_frame(solid(640, 480, RED)))
        out = sink.wait_for(lambda f: f.input_seq == 0)

    assert (out.width, out.height, out.format) == (320, 240, PixelFormat.RGBA)
    assert out.data.numel() == 320 * 240 * 4


def test_slow_backend_drops_stale_frames_but_never_the_latest(small_settings, net):
    source, sink = net.add_source("cam"), net.sink(small_settings.sink)
    with Runtime(small_settings, FakeBackend(unet_delay=0.05), net) as runtime:
        for _ in range(30):
            source.push(input_frame(solid(320, 240, BLACK)))
            time.sleep(0.005)
        sink.wait_for(lambda f: f.input_seq == 29)
        status = runtime.status()

    seqs = [f.input_seq for f in sink.frames]
    assert seqs == sorted(set(seqs))  # in order, no repeats
    assert len(seqs) < 30
    assert status.dropped_frames == 30 - len(seqs)


def test_live_update_applies_to_the_next_output_frames_without_a_gap(small_settings, net):
    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    with Runtime(small_settings, FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        sink.wait_for(lambda f: len(sink.frames) >= 5)
        sent_before = len(sink.frames)
        version = runtime.update(strength=0.0, prompt="a different prompt")
        out = sink.wait_for(lambda f: f.settings_version == version)

    # Strength 0 keeps the Input Frame, so the output is the input colour.
    assert close_to(out, RED)
    position = next(i for i, f in enumerate(sink.frames) if f is out)
    assert position - sent_before <= IN_FLIGHT + 1  # within the frames already in flight


def test_settings_change_applies_as_one_snapshot(small_settings, net):
    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    with Runtime(small_settings, FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        sink.wait_for(lambda f: True)
        version = runtime.update(strength=0.0, output={"width": 160, "height": 120})
        sink.wait_for(lambda f: f.settings_version == version and len(sink.frames) > 3)

    for frame in sink.frames:
        if frame.settings_version == version:
            assert (frame.width, frame.height) == (160, 120) and close_to(frame, RED)
        else:
            assert (frame.width, frame.height) == (320, 240)


def test_reset_switches_to_another_source_by_name(small_settings, net):
    cam, cam2 = net.add_source("cam", repeat_fps=100), net.add_source("cam2", repeat_fps=100)
    sink = net.sink(small_settings.sink)
    with Runtime(small_settings.merged({"strength": 0.0}), FakeBackend(), net) as runtime:
        cam.push(input_frame(solid(320, 240, RED)))
        cam2.push(input_frame(solid(320, 240, BLUE)))
        assert close_to(sink.wait_for(lambda f: True), RED)
        version = runtime.update(source={"name": "cam2"})
        sink.wait_for(lambda f: f.settings_version == version and close_to(f, BLUE))
        switched = len(sink.frames)
        sink.wait_for(lambda f: len(sink.frames) > switched + 2)

    assert all(close_to(f, BLUE) for f in sink.frames[switched:])


def test_settings_apply_even_while_no_input_frames_arrive(small_settings, net):
    working = net.add_source("working", repeat_fps=100)
    sink = net.sink(small_settings.sink)
    with Runtime(small_settings, FakeBackend(), net) as runtime:  # "cam" never sends anything
        working.push(input_frame(solid(320, 240, RED)))
        time.sleep(0.2)
        assert not sink.frames
        version = runtime.update(source={"name": "working"})
        sink.wait_for(lambda f: f.settings_version == version)
        wait_until(lambda: runtime.status().source_state == "live")


def test_reset_switches_the_sink_transport(small_settings, net):
    source = net.add_source("cam", repeat_fps=100)
    spout_sink = net.sink(small_settings.sink)
    with Runtime(small_settings, FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        spout_sink.wait_for(lambda f: True)
        version = runtime.update(sink={"transport": "ndi"})
        wait_until(lambda: net.sinks["out"] is not spout_sink)
        ndi_frame = net.sinks["out"].wait_for(lambda f: f.settings_version == version)

    assert ndi_frame.format == PixelFormat.UYVY
    assert ndi_frame.data.numel() == 320 * 240 * 2


def test_invalid_updates_are_rejected_and_change_nothing(small_settings, net):
    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    with Runtime(small_settings, FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        with pytest.raises(ValueError, match="strength"):
            runtime.update(strength=1.5)
        with pytest.raises(ValueError, match="multiple of 64"):
            runtime.update(generation={"width": 500})
        with pytest.raises(ValueError, match="colour"):
            runtime.update(colour="red")
        with pytest.raises(ValueError, match="strength"):  # one bad field rejects the whole update
            runtime.update(prompt="fine", strength=-1)

        assert runtime.settings() == (small_settings, 0)
        sink.wait_for(lambda f: len(sink.frames) >= 3)  # and the Runtime keeps running
        assert runtime.status().error is None


def test_source_loss_holds_last_output_frame_and_recovers(small_settings, net):
    source, sink = net.add_source("cam"), net.sink(small_settings.sink)
    with Runtime(small_settings, FakeBackend(), net, source_timeout=0.2) as runtime:
        assert runtime.status().source_state == "waiting"
        source.push(input_frame(solid(320, 240, BLACK)))
        sink.wait_for(lambda f: f.input_seq == 0)
        assert runtime.status().source_state == "live"

        wait_until(lambda: runtime.status().source_state == "lost")
        held = len(sink.frames)
        time.sleep(0.3)
        assert len(sink.frames) == held  # the last Output Frame stays on the Sink

        source.push(input_frame(solid(320, 240, BLACK)))
        sink.wait_for(lambda f: f.input_seq == 1)
        assert runtime.status().source_state == "live"


def test_source_error_is_reported_and_the_source_reopened(small_settings, net):
    source, sink = net.add_source("cam"), net.sink(small_settings.sink)
    with Runtime(small_settings, FakeBackend(), net, reconnect_delay=0.05) as runtime:
        wait_until(lambda: source.opened == 1)
        source.fail(ConnectionError("sender went away"))
        wait_until(lambda: source.opened == 2)
        assert "sender went away" in (runtime.status().error or "")

        source.push(input_frame(solid(320, 240, BLACK)))
        sink.wait_for(lambda f: f.input_seq == 0)


def test_without_a_source_the_runtime_generates_txt2img_at_the_sink_rate(small_settings, net):
    sink = net.sink(small_settings.sink)
    with Runtime(small_settings.merged({"source": {"transport": "none"}}), FakeBackend(), net) as runtime:
        time.sleep(0.5)
        status = runtime.status()

    assert status.source_state == "none"
    assert all(f.input_seq == -1 for f in sink.frames)
    # 30 fps declared on the Sink: about 15 frames in half a second, never unthrottled.
    assert 5 <= len(sink.frames) <= 20


def test_txt2img_ignores_strength(small_settings, net):
    sink = net.sink(small_settings.sink)
    settings = small_settings.merged({"source": {"transport": "none"}, "strength": 1.0})
    with Runtime(settings, FakeBackend(), net) as runtime:
        full = sink.wait_for(lambda f: True)
        version = runtime.update(strength=0.2)
        low = sink.wait_for(lambda f: f.settings_version == version)

    assert torch.equal(full.data, low.data)


def test_generation_error_is_reported_and_generation_continues(small_settings, net):
    backend, sink = FakeBackend(), net.sink(small_settings.sink)
    with Runtime(small_settings.merged({"source": {"transport": "none"}}), backend, net) as runtime:
        sink.wait_for(lambda f: True)
        backend.failures = 1
        wait_until(lambda: runtime.status().error is not None)
        sent = runtime.status().frames_sent
        wait_until(lambda: runtime.status().frames_sent > sent + 2)

    assert "illegal memory access" in (runtime.status().error or "")


def test_status_reports_throughput_and_generation_time(small_settings, net):
    source = net.add_source("cam", repeat_fps=100)
    with Runtime(small_settings, FakeBackend(unet_delay=0.02), net) as runtime:
        source.push(input_frame(solid(320, 240, BLACK)))
        wait_until(lambda: runtime.status().frames_sent >= 10)
        status = runtime.status()

    assert status.generation_ms_p50 >= 20
    assert status.generation_ms_p95 >= status.generation_ms_p50
    assert 5 < status.throughput_fps < 50
    assert status.backend == "fake"

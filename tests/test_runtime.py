"""Seam 1: the Runtime driven through the in-memory Transport with a fake Backend."""

import itertools
import time

import pytest
import torch

from streamturbo.frames import PixelFormat
from streamturbo.runtime import IN_FLIGHT, Runtime
from streamturbo.transports.memory import MemoryTransports, input_frame
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


def pixels(frame) -> torch.Tensor:
    return frame.data.view(frame.height, frame.width, 4)[..., :3].float()


def alternating_outputs(small_settings, net, count: int = 10, **changes) -> list:
    """Output Frames for red and blue Input Frames in turn, pushed one at a time: the worst flicker there is."""
    source, sink = net.add_source("cam"), net.sink(small_settings.sink)
    with Runtime(small_settings.merged({"strength": 0.0, **changes}), FakeBackend(), net):
        for seq in range(count):
            source.push(input_frame(solid(320, 240, RED if seq % 2 == 0 else BLUE)))
            sink.wait_for(lambda f, seq=seq: f.input_seq == seq)
    return [next(f for f in sink.frames if f.input_seq == seq) for seq in range(count)]


def flicker(frames) -> float:
    """Mean absolute difference between consecutive Output Frames, 0-255."""
    return sum((pixels(a) - pixels(b)).abs().mean().item() for a, b in itertools.pairwise(frames)) / (len(frames) - 1)


def test_temporal_smoothing_off_follows_every_input_frame(small_settings, net):
    frames = alternating_outputs(small_settings, net, temporal_smoothing=0.0)

    assert all(close_to(f, RED if i % 2 == 0 else BLUE) for i, f in enumerate(frames))


def test_temporal_smoothing_lowers_frame_to_frame_difference(small_settings, net):
    off = flicker(alternating_outputs(small_settings, net, temporal_smoothing=0.0)[2:])
    on = flicker(alternating_outputs(small_settings, MemoryTransports(), temporal_smoothing=0.5)[2:])

    assert on < off / 2  # an even blend of each frame with the last thirds the swing


def test_temporal_smoothing_settles_on_a_still_input(small_settings, net):
    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    with Runtime(small_settings.merged({"strength": 0.0, "temporal_smoothing": 0.5}), FakeBackend(), net):
        source.push(input_frame(solid(320, 240, BLUE)))
        sink.wait_for(lambda f: len(sink.frames) >= 3)
        source.push(input_frame(solid(320, 240, RED)))
        sink.wait_for(lambda f: close_to(f, RED))


def test_strength_moves_in_steps_of_one_hundredth(small_settings, net):
    runtime = Runtime(small_settings, FakeBackend(), net)
    runtime.update(strength=0.456)

    assert runtime.settings()[0].strength == 0.46


def distance_from(frames, rgb: tuple[int, int, int]) -> list[float]:
    """How far each Output Frame strays from a solid colour: the Seed's noise grows with Strength."""
    return [(pixels(f) - torch.tensor(rgb, dtype=torch.float32)).abs().mean().item() for f in frames]


def test_strength_glides_to_a_new_value_over_the_glide_time(small_settings, net):
    source, sink = net.add_source("cam", repeat_fps=200), net.sink(small_settings.sink)
    settings = small_settings.merged({"strength": 0.0, "strength_glide": 0.4})
    with Runtime(settings, FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        sink.wait_for(lambda f: True)
        version = runtime.update(strength=0.5)
        time.sleep(0.8)

    distances = distance_from([f for f in sink.frames if f.settings_version == version], RED)
    assert distances[0] < distances[-1] / 2  # the first frames are still close to Strength 0
    assert len(set(distances)) > 5  # in steps, not a jump
    assert all(a <= b + 0.5 for a, b in itertools.pairwise(distances))  # never backwards
    assert distances[-1] == distances[-2]  # settled at the new Strength


GREY = (128, 128, 128)
SHADES = {"dark": -0.9, "light": 0.9, "plain": 0.0}  # how far the fake UNet darkens or brightens per Prompt


def brightness(frame) -> float:
    return pixels(frame).mean().item()


def output_after(runtime: Runtime, sink, changes=None, /, **fields):
    version = runtime.update(changes, **fields)
    return sink.wait_for(lambda f: f.settings_version == version)


@pytest.fixture
def shaded(small_settings, net):
    """A Runtime whose fake Backend shades frames by Prompt, at a low Strength so the noise stays small."""
    backend = FakeBackend()
    backend.shades = SHADES
    source, sink = net.add_source("cam", repeat_fps=200), net.sink(small_settings.sink)
    settings = small_settings.merged({"strength": 0.1, "prompts": [{"text": "plain", "weight": 1.0}]})
    with Runtime(settings, backend, net) as runtime:
        source.push(input_frame(solid(320, 240, GREY)))
        sink.wait_for(lambda f: True)
        yield runtime, sink


def blend(*entries: tuple[str, float]) -> list[dict]:
    return [{"text": text, "weight": weight} for text, weight in entries]


def test_prompt_blend_mixes_weighted_prompts_as_one(shaded):
    runtime, sink = shaded
    dark = brightness(output_after(runtime, sink, prompts=blend(("dark", 1))))
    light = brightness(output_after(runtime, sink, prompts=blend(("light", 1))))
    plain = brightness(output_after(runtime, sink, prompts=blend(("plain", 1))))
    even = brightness(output_after(runtime, sink, prompts=blend(("dark", 1), ("light", 1))))
    doubled = brightness(output_after(runtime, sink, prompts=blend(("dark", 2), ("light", 2))))
    mostly_light = brightness(output_after(runtime, sink, prompts=blend(("dark", 1), ("light", 3))))
    unweighted = brightness(output_after(runtime, sink, prompts=blend(("dark", 1), ("light", 0))))

    assert dark < plain - 10 and light > plain + 10
    assert abs(even - plain) < 1 and abs(doubled - even) < 1  # weights count relative to their total
    assert plain + 5 < mostly_light < light - 5
    assert abs(unweighted - dark) < 1


def test_prompt_change_transitions_over_the_set_duration(shaded):
    runtime, sink = shaded
    dark = brightness(output_after(runtime, sink, prompts=blend(("dark", 1))))
    light = brightness(output_after(runtime, sink, prompts=blend(("light", 1))))
    output_after(runtime, sink, prompts=blend(("dark", 1)))
    output_after(runtime, sink, prompt_transition=0.4)
    version = runtime.update(prompts=blend(("light", 1)))
    time.sleep(0.8)
    seen = [brightness(f) for f in list(sink.frames) if f.settings_version == version]

    # Starts where the last Prompt Blend left off. A slow CI runner sends its first frame some 60 ms in, so the
    # bound is a share of the way to the new Blend rather than a fixed brightness.
    assert abs(seen[0] - dark) < (light - dark) / 4
    assert len({round(b) for b in seen}) > 5  # in steps, not a snap
    assert all(a <= b + 1 for a, b in itertools.pairwise(seen))
    assert abs(seen[-1] - light) < 1


def test_a_change_during_a_transition_carries_on_from_where_the_blend_is(shaded):
    runtime, sink = shaded
    output_after(runtime, sink, prompts=blend(("dark", 1)))
    output_after(runtime, sink, prompt_transition=0.6)
    towards_light = runtime.update(prompts=blend(("light", 1)))
    time.sleep(0.3)
    back = runtime.update(prompts=blend(("dark", 1)))
    sink.wait_for(lambda f: f.settings_version == back)
    time.sleep(0.2)
    frames = [f for f in list(sink.frames) if f.settings_version in (towards_light, back)]

    steps = [abs(brightness(a) - brightness(b)) for a, b in itertools.pairwise(frames)]
    assert max(steps) < 5  # no jump when the target changes halfway


def test_a_single_prompt_is_still_accepted(small_settings, net):
    runtime = Runtime(small_settings, FakeBackend(), net)
    runtime.update(prompt="ice")

    assert [p.model_dump() for p in runtime.settings()[0].prompts] == blend(("ice", 1.0))


def test_prompts_are_changed_by_index_or_replaced_from_json(small_settings, net):
    runtime = Runtime(small_settings.merged({"prompts": blend(("ice", 1))}), FakeBackend(), net)
    runtime.update({"prompts": {"1": {"text": "fire"}}})  # the next index adds a Prompt, weight 1
    runtime.update({"prompts": {"0": {"weight": 0.5}}})
    runtime.update({"prompts": {"2": {"weight": 0.25}}})  # a Prompt added by its weight starts empty
    assert [p.model_dump() for p in runtime.settings()[0].prompts] == blend(("ice", 0.5), ("fire", 1.0), ("", 0.25))

    runtime.update(prompts='[{"text": "smoke", "weight": 2}]')
    assert [p.model_dump() for p in runtime.settings()[0].prompts] == blend(("smoke", 2.0))


def test_invalid_prompt_blends_are_rejected(small_settings, net):
    runtime = Runtime(small_settings, FakeBackend(), net)
    with pytest.raises(ValueError, match="prompts"):
        runtime.update(prompts=[])
    with pytest.raises(ValueError, match="weight"):
        runtime.update(prompts=blend(("ice", 0), ("fire", 0)))
    with pytest.raises(ValueError, match="prompts"):
        runtime.update({"prompts": {"3": {"text": "too far"}}})
    with pytest.raises(ValueError, match="prompts"):
        runtime.update(prompts="not json")

    assert runtime.settings() == (small_settings, 0)


@pytest.mark.parametrize(("fit_mode", "bars"), [("fit", True), ("fill", False), ("stretch", False)])
def test_a_non_square_generation_resolution_fits_and_upscales(small_settings, net, fit_mode, bars):
    source, sink = net.add_source("cam"), net.sink(small_settings.sink)
    wide = {"generation": {"width": 512, "height": 256}, "output": {"width": 1024, "height": 512}}
    with Runtime(small_settings.merged({**wide, "fit_mode": fit_mode, "strength": 0.0}), FakeBackend(), net):
        source.push(input_frame(solid(320, 240, RED)))  # 4:3 into 2:1
        out = sink.wait_for(lambda f: True)

    image = pixels(out)
    assert (out.width, out.height) == (1024, 512)
    centre, edges = image[:, 384:640].mean(dim=(0, 1)), torch.cat((image[:, :128], image[:, -128:]), dim=1)
    assert all(abs(a - b) <= 3 for a, b in zip(centre.tolist(), RED, strict=True))
    assert (edges.mean().item() < 3) if bars else (edges.mean(dim=(0, 1)) - torch.tensor(RED)).abs().max() <= 3


def coherence_outputs(small_settings, net, coherence: bool, count: int = 8) -> list:
    """Like `alternating_outputs`, at a Strength where the UNet runs, so Temporal Coherence can act."""
    return alternating_outputs(small_settings, net, count, strength=0.5, temporal_coherence=coherence)


def test_temporal_coherence_off_follows_every_input_frame(small_settings, net):
    frames = coherence_outputs(small_settings, net, coherence=False)

    assert all(torch.equal(a.data, b.data) for a, b in zip(frames, frames[2:], strict=False))  # same colour: same
    assert flicker(frames) > 20


def test_temporal_coherence_leans_each_generation_on_the_previous_one(small_settings, net):
    off = flicker(coherence_outputs(small_settings, net, coherence=False)[2:])
    on = flicker(coherence_outputs(small_settings, MemoryTransports(), coherence=True)[2:])

    assert on < off * 0.8


def first_output(settings, colour: tuple[int, int, int]):
    """The first Output Frame a fresh Runtime makes from one Input Frame: no earlier Generation to lean on."""
    net = MemoryTransports()
    source, sink = net.add_source(settings.source.name), net.sink(settings.sink)
    with Runtime(settings, FakeBackend(), net):
        source.push(input_frame(solid(320, 240, colour)))
        return sink.wait_for(lambda f: True)


def test_temporal_coherence_starts_afresh_on_another_source(small_settings, net):
    settings = small_settings.merged({"strength": 0.5, "temporal_coherence": True})
    cam, cam2, sink = net.add_source("cam"), net.add_source("cam2"), net.sink(settings.sink)
    with Runtime(settings, FakeBackend(), net) as runtime:
        for seq in range(3):
            cam.push(input_frame(solid(320, 240, BLUE)))
            sink.wait_for(lambda f, seq=seq: f.input_seq == seq)
        version = runtime.update(source={"name": "cam2"})
        time.sleep(0.1)
        cam2.push(input_frame(solid(320, 240, RED)))
        switched = sink.wait_for(lambda f: f.settings_version == version)

    assert torch.equal(switched.data, first_output(settings.merged({"source": {"name": "cam2"}}), RED).data)


def test_turning_temporal_coherence_off_applies_to_the_next_output_frame(small_settings, net):
    settings = small_settings.merged({"strength": 0.5, "temporal_coherence": True})
    source, sink = net.add_source("cam"), net.sink(settings.sink)
    with Runtime(settings, FakeBackend(), net) as runtime:
        for seq in range(3):
            source.push(input_frame(solid(320, 240, BLUE)))
            sink.wait_for(lambda f, seq=seq: f.input_seq == seq)
        version = runtime.update(temporal_coherence=False)
        time.sleep(0.1)
        source.push(input_frame(solid(320, 240, RED)))
        after = sink.wait_for(lambda f: f.settings_version == version)

    assert torch.equal(after.data, first_output(settings, RED).data)


def test_temporal_coherence_starts_afresh_on_another_generation_resolution(small_settings, net):
    settings = small_settings.merged({"strength": 0.5, "temporal_coherence": True})
    source, sink = net.add_source("cam"), net.sink(settings.sink)
    with Runtime(settings, FakeBackend(), net) as runtime:
        for seq in range(3):
            source.push(input_frame(solid(320, 240, BLUE)))
            sink.wait_for(lambda f, seq=seq: f.input_seq == seq)
        version = runtime.update(generation={"width": 320, "height": 256})
        time.sleep(0.1)
        source.push(input_frame(solid(320, 240, RED)))
        resized = sink.wait_for(lambda f: f.settings_version == version)

    assert torch.equal(
        resized.data, first_output(settings.merged({"generation": {"width": 320, "height": 256}}), RED).data
    )


def test_temporal_coherence_leans_on_nothing_after_strength_zero(small_settings, net):
    """At Strength 0 the UNet does not run, so there is nothing current to lean on afterwards."""
    settings = small_settings.merged({"strength": 0.5, "temporal_coherence": True})
    source, sink = net.add_source("cam"), net.sink(settings.sink)
    with Runtime(settings, FakeBackend(), net) as runtime:
        for seq in range(3):
            source.push(input_frame(solid(320, 240, BLUE)))
            sink.wait_for(lambda f, seq=seq: f.input_seq == seq)
        runtime.update(strength=0.0)
        time.sleep(0.1)
        source.push(input_frame(solid(320, 240, RED)))
        sink.wait_for(lambda f: f.input_seq == 3)
        version = runtime.update(strength=0.5)
        time.sleep(0.1)
        source.push(input_frame(solid(320, 240, RED)))
        after = sink.wait_for(lambda f: f.settings_version == version)

    assert torch.equal(after.data, first_output(settings, RED).data)


DIM_RED = (100, 40, 40)
UPSCALED_DIM_RED = (164, 104, 104)  # the fake Upscaler brightens by a quarter of the range


def upscaler_output(settings, upscaler: bool, colour: tuple[int, int, int] = DIM_RED):
    return first_output(settings.merged({"strength": 0.0, "upscaler": upscaler}), colour)


def test_the_upscaler_enlarges_output_frames_above_the_generation_resolution(small_settings):
    on, off = upscaler_output(small_settings, True), upscaler_output(small_settings, False)

    assert (on.width, on.height) == (off.width, off.height) == (320, 240)
    assert close_to(on, UPSCALED_DIM_RED)
    assert close_to(off, DIM_RED)


@pytest.mark.parametrize("output", [(256, 256), (200, 150)])
def test_the_upscaler_leaves_output_frames_no_larger_than_the_generation_resolution(small_settings, output):
    settings = small_settings.merged({"output": {"width": output[0], "height": output[1]}})

    assert torch.equal(upscaler_output(settings, True).data, upscaler_output(settings, False).data)


def test_turning_the_upscaler_off_and_on_applies_to_the_next_output_frame(small_settings, net):
    settings = small_settings.merged({"strength": 0.0, "upscaler": True})
    source, sink = net.add_source("cam", repeat_fps=100), net.sink(settings.sink)
    with Runtime(settings, FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, DIM_RED)))
        sink.wait_for(lambda f: len(sink.frames) >= 3)
        off = runtime.update(upscaler=False)
        plain = sink.wait_for(lambda f: f.settings_version == off)
        sent_before = len(sink.frames)
        on = runtime.update(upscaler=True)
        upscaled = sink.wait_for(lambda f: f.settings_version == on)

    assert close_to(plain, DIM_RED)
    assert close_to(upscaled, UPSCALED_DIM_RED)
    position = next(i for i, f in enumerate(sink.frames) if f is upscaled)
    assert position - sent_before <= IN_FLIGHT + 1  # a Live Setting: no gap in output

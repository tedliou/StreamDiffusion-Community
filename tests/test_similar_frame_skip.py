"""Seam 1: Similar Frame Skip, driven through the in-memory Transport with a fake Backend."""

import time

import torch

from streamturbo.runtime import IN_FLIGHT, Runtime
from streamturbo.transports.memory import input_frame
from tests.conftest import FakeBackend
from tests.test_runtime import BLUE, RED, close_to, distance_from, solid, wait_until


def skipping(settings, threshold=0.02, max_skips=1000):
    return settings.merged({"similar_frame_skip": {"threshold": threshold, "max_skips": max_skips}})


def test_a_static_source_repeats_the_last_output_frame_instead_of_generating(small_settings, net):
    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    with Runtime(skipping(small_settings), FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        wait_until(lambda: runtime.status().frames_skipped >= 20)
        status = runtime.status()

    assert status.frames_sent - status.frames_skipped <= IN_FLIGHT + 1  # only the first frames were generated
    assert torch.equal(sink.frames[-1].data, sink.frames[-10].data)


def test_skipping_never_freezes_output_beyond_the_maximum(small_settings, net):
    source = net.add_source("cam", repeat_fps=100)
    with Runtime(skipping(small_settings, max_skips=3), FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        wait_until(lambda: runtime.status().frames_sent >= 40)
        status = runtime.status()

    generated = status.frames_sent - status.frames_skipped
    assert 0.15 < generated / status.frames_sent < 0.4  # one forced refresh after every 3 skips


def test_a_changed_input_frame_is_generated(small_settings, net):
    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    with Runtime(skipping(small_settings.merged({"strength": 0.0})), FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        wait_until(lambda: runtime.status().frames_skipped >= 5)
        source.push(input_frame(solid(320, 240, BLUE)))
        sink.wait_for(lambda f: close_to(f, BLUE))


def test_a_settings_change_is_generated_even_while_the_source_is_static(small_settings, net):
    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    with Runtime(skipping(small_settings), FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        wait_until(lambda: runtime.status().frames_skipped >= 5)
        version = runtime.update(strength=0.0)
        assert close_to(sink.wait_for(lambda f: f.settings_version == version), RED)


def test_similar_frame_skip_is_off_at_threshold_zero(small_settings, net):
    source = net.add_source("cam", repeat_fps=100)
    with Runtime(skipping(small_settings, threshold=0.0), FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        wait_until(lambda: runtime.status().frames_sent >= 20)

    assert runtime.status().frames_skipped == 0


def test_skipping_waits_for_a_strength_glide_to_finish(small_settings, net):
    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    settings = skipping(small_settings.merged({"strength": 0.0, "strength_glide": 0.3}), threshold=0.5)
    with Runtime(settings, FakeBackend(), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        wait_until(lambda: runtime.status().frames_skipped >= 5)
        version = runtime.update(strength=0.5)
        time.sleep(0.6)

    gliding = distance_from([f for f in sink.frames if f.settings_version == version], RED)
    assert len(set(gliding)) > 5  # every step of the glide was generated, not repeated

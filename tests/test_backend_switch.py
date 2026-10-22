"""Seam 1: the Runtime on the best available Backend, with fake Engines building in the background."""

import threading

from streamturbo.backends import BestBackend
from streamturbo.runtime import Runtime
from streamturbo.transports.memory import input_frame
from tests.conftest import FakeBackend
from tests.test_runtime import RED, close_to, solid, wait_until

NEGATIVE_RED = (55, 215, 215)  # RED through a Backend that inverts its Output Frames


def test_output_starts_on_the_fallback_and_switches_when_the_engines_are_built(small_settings, net):
    ready = threading.Event()

    def build(progress):
        progress(0.5)
        ready.wait()
        return FakeBackend(name="fast", negative=True)

    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    backend = BestBackend(FakeBackend(), build)
    with Runtime(small_settings.merged({"strength": 0.0}), backend, net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        assert close_to(sink.wait_for(lambda f: True), RED)
        wait_until(lambda: runtime.status().engines.progress == 0.5)
        status = runtime.status()
        assert (status.backend, status.engines.state) == ("fake", "building")

        ready.set()
        wait_until(lambda: runtime.status().backend == "fast")
        sent = len(sink.frames)
        sink.wait_for(lambda f: len(sink.frames) > sent + 3)  # past the frames already in flight

    assert close_to(sink.frames[-1], NEGATIVE_RED)
    assert runtime.status().engines.state == "ready"


def test_a_failed_engine_build_keeps_output_on_the_fallback_and_says_why(small_settings, net):
    def build(progress):
        raise RuntimeError("TensorRT could not build the unet Engine")

    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    with Runtime(small_settings.merged({"strength": 0.0}), BestBackend(FakeBackend(), build), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        wait_until(lambda: runtime.status().engines.state == "failed")
        sent = len(sink.frames)
        sink.wait_for(lambda f: len(sink.frames) > sent + 3)
        status = runtime.status()

    assert status.backend == "fake"
    assert "could not build the unet Engine" in (status.engines.detail or "")
    assert close_to(sink.frames[-1], RED)


def test_forcing_the_pytorch_backend_builds_nothing_and_switches_back(small_settings, net):
    builds = []

    def build(progress):
        builds.append(1)
        return FakeBackend(name="fast", negative=True)

    source, sink = net.add_source("cam", repeat_fps=100), net.sink(small_settings.sink)
    settings = small_settings.merged({"strength": 0.0, "backend": "pytorch"})
    with Runtime(settings, BestBackend(FakeBackend(), build), net) as runtime:
        source.push(input_frame(solid(320, 240, RED)))
        sink.wait_for(lambda f: len(sink.frames) > 5)
        assert not builds
        assert runtime.status().engines.state == "off"

        runtime.update(backend="auto")
        wait_until(lambda: runtime.status().backend == "fast")
        version = runtime.update(backend="pytorch")
        sink.wait_for(lambda f: f.settings_version == version)
        sent = len(sink.frames)
        sink.wait_for(lambda f: len(sink.frames) > sent + 3)

    assert runtime.status().backend == "fake"
    assert close_to(sink.frames[-1], RED)
    assert len(builds) == 1

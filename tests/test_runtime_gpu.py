"""Seam 1 with the real sd-turbo PyTorch Backend (marked `gpu`, run locally)."""

import pytest
import torch

from streamturbo import weights
from streamturbo.frames import OutputFrame
from streamturbo.model_spec import SD_TURBO
from streamturbo.runtime import Runtime
from streamturbo.settings import Settings
from streamturbo.testframe import synthetic_frame
from streamturbo.transports.memory import MemorySink, MemoryTransports, input_frame

pytestmark = pytest.mark.gpu

VRAM_BUDGET_GIB = 4.0  # Glass at 1024x768 measured 2.9 GiB peak; TouchDesigner needs the rest of 8 GB


@pytest.fixture(scope="module")
def backend():
    from streamturbo.backends.pytorch import PyTorchBackend

    return PyTorchBackend(*weights.fetch_all(SD_TURBO))


GLASS = Settings.model_validate({"source": {"transport": "spout", "name": "cam"}, "sink": {"transport": "spout"}})


@pytest.fixture
def glass():
    """The Glass Preset at 1024x768 over in-memory Spout, fed with the synthetic test pattern."""
    net = MemoryTransports()
    net.add_source("cam", repeat_fps=60).push(input_frame(synthetic_frame(1024, 768)))
    return net, net.sink(GLASS.sink)


def output_for(runtime: Runtime, sink: MemorySink, **changes: object) -> torch.Tensor:
    version = runtime.update(**changes) if changes else 0
    frame: OutputFrame = sink.wait_for(lambda f: f.settings_version >= version, timeout=60)
    return frame.data.view(frame.height, frame.width, 4)[..., :3].float()


def difference(a: torch.Tensor, b: torch.Tensor) -> float:
    """Mean absolute difference in 0-255 units."""
    return (a - b).abs().mean().item()


def test_prompt_and_strength_change_the_output(backend, glass):
    net, sink = glass
    pattern = synthetic_frame(1024, 768)[..., :3].float()
    with Runtime(GLASS, backend, net) as runtime:
        base = output_for(runtime, sink)
        other_prompt = output_for(runtime, sink, prompt="a watercolor painting of a forest")
        low = output_for(runtime, sink, prompt=GLASS.prompt, strength=0.2)
        high = output_for(runtime, sink, strength=0.9)

    assert difference(base, other_prompt) > 10
    assert difference(low, pattern) < difference(high, pattern)


def test_seed_reproduces_output_and_strength_never_rerolls_noise(backend, glass):
    net, sink = glass
    with Runtime(GLASS, backend, net) as runtime:
        first = output_for(runtime, sink)
        other_seed = output_for(runtime, sink, seed=7)
        same_seed = output_for(runtime, sink, seed=2)
        output_for(runtime, sink, strength=0.4)
        strength_back = output_for(runtime, sink, strength=GLASS.strength)

    assert difference(first, other_seed) > 5
    assert difference(first, same_seed) < 0.5
    assert difference(first, strength_back) < 0.5


def test_glass_preset_stays_within_vram_budget(backend, glass):
    net, sink = glass
    torch.cuda.reset_peak_memory_stats()
    with Runtime(GLASS, backend, net):
        sink.wait_for(lambda _: len(sink.frames) >= 10, timeout=60)

    assert torch.cuda.max_memory_allocated() / 2**30 < VRAM_BUDGET_GIB

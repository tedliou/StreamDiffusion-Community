"""Seam 1 with the real sd-turbo PyTorch and TensorRT Backends (marked `gpu`, run locally)."""

import os
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from streamturbo import weights
from streamturbo.frames import OutputFrame
from streamturbo.model_spec import SD_TURBO
from streamturbo.paths import engines_dir
from streamturbo.runtime import Runtime
from streamturbo.settings import Settings
from streamturbo.testframe import synthetic_frame
from streamturbo.transports.memory import MemorySink, MemoryTransports, input_frame

pytestmark = pytest.mark.gpu

# Device memory the Runtime may take while running Glass at 1024x768, on top of what was in use before it loaded:
# TouchDesigner needs the rest of an 8 GB card.
VRAM_BUDGET_GIB = {"pytorch": 4.0, "tensorrt": 5.0}
TENSORRT_TOLERANCE = 2.0  # mean absolute difference from PyTorch, 0-255 (measured 0.3): FP16 kernels round differently
REFERENCE_TOLERANCE = 2.0  # mean absolute difference from the stored Glass reference, 0-255 (measured 0.3 at most)
REFERENCE = Path(__file__).parent / "reference" / "glass-1024x768.png"
UPDATE_REFERENCE = os.environ.get("STREAMTURBO_UPDATE_REFERENCE") == "1"


@pytest.fixture(scope="module")
def baseline_gib() -> float:
    """Device memory in use before this module loads a model (TouchDesigner, the desktop, other tests)."""
    torch.cuda.empty_cache()
    free, total = torch.cuda.mem_get_info()
    return (total - free) / 2**30


@pytest.fixture(scope="module")
def pytorch(baseline_gib):
    from streamturbo.backends.pytorch import PyTorchBackend

    return PyTorchBackend(*weights.fetch_all(SD_TURBO))


@pytest.fixture(scope="module")
def tensorrt(pytorch):
    from streamturbo.backends.tensorrt import TensorRTBackend, build_engines

    backend = TensorRTBackend(pytorch, build_engines(pytorch, SD_TURBO, engines_dir()))
    pytorch.release()  # as BestBackend does on switching; the PyTorch Backend reloads its UNet when next used
    return backend


@pytest.fixture(scope="module", params=["pytorch", "tensorrt"])
def backend(request):
    return request.getfixturevalue(request.param)


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


def glass_output(backend, width: int = 1024, height: int = 768) -> torch.Tensor:
    net = MemoryTransports()
    net.add_source("cam", repeat_fps=60).push(input_frame(synthetic_frame(width, height)))
    size = {"width": width, "height": height}
    settings = GLASS.merged({"generation": size, "output": size})
    sink = net.sink(settings.sink)
    with Runtime(settings, backend, net) as runtime:
        return output_for(runtime, sink)


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


def test_glass_preset_stays_within_vram_budget(request, backend, glass, baseline_gib):
    net, sink = glass
    with Runtime(GLASS, backend, net):
        sink.wait_for(lambda _: len(sink.frames) >= 10, timeout=60)
        free, total = torch.cuda.mem_get_info()

    assert (total - free) / 2**30 - baseline_gib < VRAM_BUDGET_GIB[request.node.callspec.params["backend"]]


def test_glass_preset_matches_the_reference_image(backend):
    output = glass_output(backend)
    if UPDATE_REFERENCE and backend.name == "pytorch":
        REFERENCE.parent.mkdir(exist_ok=True)
        Image.fromarray(output.to(torch.uint8).cpu().numpy()).save(REFERENCE)
    reference = torch.from_numpy(np.asarray(Image.open(REFERENCE).convert("RGB"))).float()

    assert difference(output, reference) < REFERENCE_TOLERANCE


# The ends of the Engine profile, a square and a portrait size: shape-specific Engine bugs show up at some sizes only.
@pytest.mark.parametrize("size", [(1024, 768), (256, 256), (1024, 1024), (512, 768)])
def test_tensorrt_output_matches_pytorch(pytorch, tensorrt, size):
    assert difference(glass_output(tensorrt, *size), glass_output(pytorch, *size)) < TENSORRT_TOLERANCE

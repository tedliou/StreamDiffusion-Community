"""Seam 1 with the real sd-turbo PyTorch and TensorRT Backends (marked `gpu`, run locally)."""

import itertools
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


@pytest.fixture(autouse=True)
def cached_memory_released():
    """Each test leaves no cached blocks behind: with TouchDesigner open, the PyTorch UNet and the Engines together
    leave little room, and spilling into system memory makes the GPU tests crawl."""
    yield
    torch.cuda.empty_cache()


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


# Glass without Strength glide, Prompt transitions, Temporal Smoothing, Temporal Coherence or the Upscaler, so the
# first Output Frame of a change shows all of it.
GLASS = Settings.model_validate(
    {
        "source": {"transport": "spout", "name": "cam"},
        "sink": {"transport": "spout"},
        "strength_glide": 0.0,
        "prompt_transition": 0.0,
        "temporal_smoothing": 0.0,
        "temporal_coherence": False,
        "upscaler": False,
    }
)
FLICKER_REDUCTION = 0.85  # Temporal Smoothing at its default must cut flicker at least this much (measured 0.79)
TRAIL_LIMIT = 2.5  # mean difference from unsmoothed output behind a fast pan, 0-255: measured 1.8 at the default
# 0.2; at 0.3 (3.0) a soft fringe shows on moving edges
# Temporal Coherence must cut warp error (Output Frames vs the previous one moved with the input) at least this much;
# measured 0.91 on the still noisy test pattern and 0.95 behind its 8 px pan (0.72 and 0.89 with Temporal Smoothing).
COHERENCE_STILL, COHERENCE_PAN = 0.95, 0.98
SHARPNESS_KEPT = 0.97  # of the detail without Temporal Coherence (measured 1.0 in the spike)


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
        low = output_for(runtime, sink, prompts=GLASS.prompts, strength=0.2)
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


# Glass as it is, and 512x512 Generations enlarged 4x by the Upscaler, the largest it is used for (spec #19).
UPSCALED_4X = {
    "generation": {"width": 512, "height": 512},
    "output": {"width": 2048, "height": 2048},
    "upscaler": True,
}


@pytest.mark.parametrize("sizes", [{}, UPSCALED_4X])
def test_glass_preset_stays_within_vram_budget(request, backend, glass, baseline_gib, sizes):
    net, sink = glass
    with Runtime(GLASS.merged(sizes), backend, net):
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


# The ends of the Engine profile, a square, a portrait and a 16:9 size: shape-specific Engine bugs show up at some
# sizes only.
@pytest.mark.parametrize("size", [(1024, 768), (256, 256), (1024, 1024), (512, 768), (1024, 576)])
def test_tensorrt_output_matches_pytorch(pytorch, tensorrt, size):
    assert difference(glass_output(tensorrt, *size), glass_output(pytorch, *size)) < TENSORRT_TOLERANCE


def pixels(frame: OutputFrame) -> torch.Tensor:
    return frame.data.view(frame.height, frame.width, 4)[..., :3].float()


def clip_outputs(backend, clip: list[torch.Tensor], **changes: object) -> list[torch.Tensor]:
    """Glass Output Frames for a clip of Input Frames, pushed one at a time so none is dropped."""
    net = MemoryTransports()
    source = net.add_source("cam")
    settings = GLASS.merged(changes)
    sink = net.sink(settings.sink)
    with Runtime(settings, backend, net):
        for seq, frame in enumerate(clip):
            source.push(input_frame(frame))
            sink.wait_for(lambda f, seq=seq: f.input_seq == seq, timeout=60)
    frames = {f.input_seq: f for f in sink.frames}
    return [pixels(frames[seq]) for seq in range(len(clip))]


def still_clip(count: int = 20) -> list[torch.Tensor]:
    """The test pattern under camera noise: the input that makes sd-turbo flicker most on a still scene."""
    pattern, generator = synthetic_frame(1024, 768), torch.Generator().manual_seed(0)
    noise = [torch.randn(768, 1024, 3, generator=generator) * 6 for _ in range(count)]
    return [torch.cat(((pattern[..., :3] + n).clamp(0, 255).to(torch.uint8), pattern[..., 3:]), -1) for n in noise]


def pan_clip(count: int = 20) -> list[torch.Tensor]:
    """The test pattern panning 8 px per frame: fast enough that blending with the last frame would trail."""
    return [torch.roll(synthetic_frame(1024, 768), shifts=8 * i, dims=1) for i in range(count)]


def flicker(frames: list[torch.Tensor]) -> float:
    """Mean frame-to-frame difference, 0-255, once Temporal Smoothing has had a few frames to settle."""
    pairs = list(itertools.pairwise(frames[5:]))
    return sum(difference(a, b) for a, b in pairs) / len(pairs)


def test_temporal_smoothing_reduces_flicker_without_a_visible_trail(backend):
    default = Settings().temporal_smoothing
    assert default > 0
    clip = still_clip()
    off, on = clip_outputs(backend, clip), clip_outputs(backend, clip, temporal_smoothing=default)
    assert flicker(on) < FLICKER_REDUCTION * flicker(off)

    clip = pan_clip()
    off, on = clip_outputs(backend, clip), clip_outputs(backend, clip, temporal_smoothing=default)
    trail = sum(difference(a, b) for a, b in zip(on[5:], off[5:], strict=True)) / len(clip[5:])
    assert trail < TRAIL_LIMIT


def warp_error(frames: list[torch.Tensor], step: int) -> float:
    """How much each Output Frame differs from the previous one moved along with the Input Frames, 0-255.

    The clips move by a known `step` pixels per frame and wrap around, so nothing is occluded.
    """
    pairs = list(itertools.pairwise(frames[5:]))
    return sum(difference(b, torch.roll(a, shifts=step, dims=1)) for a, b in pairs) / len(pairs)


LAPLACE = torch.tensor([[0.0, 1, 0], [1, -4, 1], [0, 1, 0]]).view(1, 1, 3, 3)


def sharpness(frames: list[torch.Tensor], skip: int = 5) -> float:
    """Mean absolute Laplacian of the grey picture: fine detail, which blending away boiling would soften."""
    grey = [f.mean(dim=-1)[None, None] for f in frames[skip:]]
    return sum(torch.nn.functional.conv2d(g, LAPLACE).abs().mean().item() for g in grey) / len(grey)


def test_temporal_coherence_keeps_detail_in_place_without_softening_it(backend):
    assert Settings().temporal_coherence
    for clip, step, limit in ((still_clip(), 0, COHERENCE_STILL), (pan_clip(), 8, COHERENCE_PAN)):
        off, on = clip_outputs(backend, clip), clip_outputs(backend, clip, temporal_coherence=True)
        assert warp_error(on, step) < limit * warp_error(off, step)
        assert sharpness(on) > SHARPNESS_KEPT * sharpness(off)


@pytest.mark.parametrize("size", [(1024, 768), (512, 768)])
def test_tensorrt_matches_pytorch_with_temporal_coherence(pytorch, tensorrt, size):
    """Every frame after the first leans on the one before, so the Engine's feature inputs and outputs are used."""
    width, height = size
    frames = [torch.roll(synthetic_frame(width, height), shifts=8 * i, dims=1) for i in range(4)]
    on = {"temporal_coherence": True, "generation": {"width": width, "height": height}}
    on |= {"output": {"width": width, "height": height}}
    ours, reference = clip_outputs(tensorrt, frames, **on), clip_outputs(pytorch, frames, **on)
    assert all(difference(a, b) < TENSORRT_TOLERANCE for a, b in zip(ours, reference, strict=True))


def test_a_wide_generation_resolution_fits_and_upscales(backend):
    """A 4:3 Input Frame into 1024x576 with Fit Mode fit, upscaled to 1920x1080 for the Sink."""
    net = MemoryTransports()
    net.add_source("cam", repeat_fps=60).push(input_frame(synthetic_frame(1024, 768)))
    wide = {"generation": {"width": 1024, "height": 576}, "output": {"width": 1920, "height": 1080}}
    settings = GLASS.merged({**wide, "fit_mode": "fit", "strength": 0.0})
    sink = net.sink(settings.sink)
    with Runtime(settings, backend, net) as runtime:
        frame = sink.wait_for(lambda _: True, timeout=60)
        glass = output_for(runtime, sink, strength=GLASS.strength)

    image = frame.data.view(1080, 1920, 4)[..., :3].float()
    assert (frame.width, frame.height) == (1920, 1080) and glass.shape == (1080, 1920, 3)
    assert image[:, :200].mean() < 10 and image[:, -200:].mean() < 10  # pillarboxed: 240 px bars each side
    assert image[:, 400:1520].mean() > 60  # with the picture between them


UPSCALER_SHARPNESS = 1.4  # of the detail of plain resizing (measured 1.69 on both Backends)


def test_the_upscaler_makes_enlarged_output_frames_sharper(backend):
    """512x512 Generations enlarged to 1024x1024, with and without the Upscaler."""
    net = MemoryTransports()
    net.add_source("cam", repeat_fps=60).push(input_frame(synthetic_frame(512, 512)))
    settings = GLASS.merged({"generation": {"width": 512, "height": 512}, "output": {"width": 1024, "height": 1024}})
    sink = net.sink(settings.sink)
    with Runtime(settings, backend, net) as runtime:
        off = output_for(runtime, sink)
        on = output_for(runtime, sink, upscaler=True)

    assert on.shape == off.shape == (1024, 1024, 3)
    assert sharpness([on], skip=0) > UPSCALER_SHARPNESS * sharpness([off], skip=0)


def upscaled_output(backend, generation: tuple[int, int], factor: int) -> torch.Tensor:
    width, height = generation
    net = MemoryTransports()
    net.add_source("cam", repeat_fps=60).push(input_frame(synthetic_frame(width, height)))
    sizes = {
        "generation": {"width": width, "height": height},
        "output": {"width": width * factor, "height": height * factor},
    }
    settings = GLASS.merged({**sizes, "upscaler": True})
    sink = net.sink(settings.sink)
    with Runtime(settings, backend, net) as runtime:
        return output_for(runtime, sink)


# 2x at the 512-pixel sizes the Upscaler is meant for, and 4x, where Output Frames are its picture unresized.
@pytest.mark.parametrize(("generation", "factor"), [((512, 512), 2), ((512, 384), 2), ((512, 512), 4)])
def test_tensorrt_upscaler_matches_pytorch(pytorch, tensorrt, generation, factor):
    ours, reference = upscaled_output(tensorrt, generation, factor), upscaled_output(pytorch, generation, factor)

    assert ours.shape == (generation[1] * factor, generation[0] * factor, 3)
    assert difference(ours, reference) < TENSORRT_TOLERANCE

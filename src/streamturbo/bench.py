"""`streamturbo bench`: measures the Glass workload and writes a machine-readable report.

Benchmarks are records, not tests: results are compared per milestone and never gate CI. `--matrix` runs the
quality/speed options the shipped defaults are picked from (spec #2), saving one Output Frame per option.
"""

import importlib.metadata
import json
import platform
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import torch

from streamturbo import doctor, weights
from streamturbo.backends import Backend
from streamturbo.model_spec import SD_TURBO
from streamturbo.paths import engines_dir, output_dir
from streamturbo.runtime import Runtime
from streamturbo.settings import Settings
from streamturbo.testframe import synthetic_frame
from streamturbo.transports.memory import MemorySink, MemoryTransports, input_frame

WARMUP_FRAMES = 20
BackendName = Literal["pytorch", "tensorrt"]
Precision = Literal["fp16", "int8"]

# The decision matrix: Generation Resolution x UNet precision x Output Resolution (spec #2, ticket #7).
# 896x640 stands in for the spec's 896x672: sides must be multiples of 64, and 4:3 only fits at 768 and 1024.
MATRIX_GENERATION = ((1024, 768), (896, 640), (768, 576))
MATRIX_PRECISION: tuple[Precision, ...] = ("fp16", "int8")
MATRIX_OUTPUT = ((1024, 768), (1920, 1440))
SKIP_SECONDS = 20  # per run of the Similar Frame Skip power check
SKIP_THRESHOLD = 0.01


@dataclass(frozen=True)
class Option:
    backend: BackendName
    precision: Precision
    generation: tuple[int, int]
    output: tuple[int, int]

    @property
    def name(self) -> str:
        (gw, gh), (ow, oh) = self.generation, self.output
        precision = f"-{self.precision}" if self.backend == "tensorrt" else ""
        return f"{self.backend}{precision}-gen{gw}x{gh}-out{ow}x{oh}"


class BackendCache:
    """Loads the PyTorch Backend once and the TensorRT Backend per precision, building missing Engines first."""

    def __init__(self) -> None:
        from streamturbo.backends.pytorch import PyTorchBackend

        self.pytorch = PyTorchBackend(*weights.fetch_all(SD_TURBO))
        self._loaded: tuple[Precision, Backend] | None = None
        self._failed: dict[Precision, Exception] = {}  # a failed build is not retried for every option

    def get(self, backend: BackendName, precision: Precision) -> Backend:
        if backend == "pytorch":
            return self.pytorch
        if self._loaded and self._loaded[0] == precision:
            return self._loaded[1]
        if precision in self._failed:
            raise self._failed[precision]
        from streamturbo.backends.tensorrt import TensorRTBackend, build_engines

        self._loaded = None
        torch.cuda.empty_cache()
        print(f"Preparing {precision} Engines (built once, then cached) ...", flush=True)
        try:
            paths = build_engines(self.pytorch, SD_TURBO, engines_dir(), precision)
            self._loaded = (precision, TensorRTBackend(self.pytorch, paths))
        except Exception as error:
            self._failed[precision] = error
            raise
        return self._loaded[1]


def run(
    settings: Settings,
    frames: int = 120,
    out: Path | None = None,
    backend: BackendName = "tensorrt",
    precision: Precision = "fp16",
    image: Path | None = None,
) -> Path:
    """Run the workload and return the path of the JSON report (a PNG of the last Output Frame sits beside it)."""
    out = out or output_dir() / "bench"
    out.mkdir(parents=True, exist_ok=True)
    gen = settings.generation
    option = Option(backend, precision, (gen.width, gen.height), (settings.output.width, settings.output.height))
    report, sink = _measure(BackendCache().get(backend, precision), settings, option, frames, image)
    stem = out / f"bench-{datetime.now():%Y%m%d-%H%M%S}"
    stem.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _save_png(sink, stem.with_suffix(".png"))
    return stem.with_suffix(".json")


def matrix(settings: Settings, frames: int = 120, out: Path | None = None, image: Path | None = None) -> Path:
    """Run every option of the decision matrix; returns the folder holding results.json, results.md and PNGs."""
    out = (out or output_dir() / "bench") / f"matrix-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    backends = BackendCache()
    options = [
        Option("tensorrt", precision, generation, output)
        for precision in MATRIX_PRECISION
        for generation in MATRIX_GENERATION
        for output in MATRIX_OUTPUT
    ]
    options.insert(0, Option("pytorch", "fp16", MATRIX_GENERATION[0], MATRIX_OUTPUT[0]))  # the M1/M2 baseline
    results: list[dict[str, Any]] = []
    for option in options:
        print(f"{option.name} ...", flush=True)
        try:
            report, sink = _measure(backends.get(option.backend, option.precision), settings, option, frames, image)
        except Exception as error:  # e.g. an INT8 build that fails: record it and carry on
            results.append({"option": option.name, "error": f"{type(error).__name__}: {error}"})
            _write(out, results, None)
            continue
        _save_png(sink, out / f"{option.name}.png")
        results.append({"option": option.name, "image": f"{option.name}.png"} | report)
        _write(out, results, None)
    skip = similar_frame_skip_power(backends.get("tensorrt", "fp16"), settings, image)
    _write(out, results, skip)
    return out


def similar_frame_skip_power(backend: Backend, settings: Settings, image: Path | None = None) -> dict[str, Any]:
    """Average GPU power on a static Source with Similar Frame Skip off, then on."""
    result: dict[str, Any] = {"seconds": SKIP_SECONDS, "threshold": SKIP_THRESHOLD}
    for label, threshold in (("off", 0.0), ("on", SKIP_THRESHOLD)):
        skip = {"similar_frame_skip": {"threshold": threshold, "max_skips": 30}}
        with _workload(backend, settings.merged(skip), image) as (runtime, _sink), _energy() as energy:
            time.sleep(SKIP_SECONDS)
            status, power = runtime.status(), energy()
        result[label] = {
            "average_power_w": round(power, 1),
            "throughput_fps": round(status.throughput_fps, 2),
            "frames_skipped": status.frames_skipped,
        }
    result["power_limit_w"] = _power_limit()
    return result


def _measure(
    backend: Backend, settings: Settings, option: Option, frames: int, image: Path | None
) -> tuple[dict[str, Any], MemorySink]:
    (gw, gh), (ow, oh) = option.generation, option.output
    settings = settings.merged(
        {
            "generation": {"width": gw, "height": gh},
            "output": {"width": ow, "height": oh},
            "similar_frame_skip": {"threshold": 0.0},  # the bench Source is static: measure every Generation
        }
    )
    with _workload(backend, settings, image) as (runtime, sink):
        _wait_sent(runtime, WARMUP_FRAMES)
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        with _energy() as energy:
            _wait_sent(runtime, WARMUP_FRAMES + frames)
            average_w = energy()
        elapsed = time.perf_counter() - started
        status = runtime.status()
    machine = doctor.collect()
    card = machine.gpus[0] if machine.gpus else None
    int8 = option.backend == "tensorrt" and option.precision == "int8"
    report = {
        "workload": "glass",
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "frames": frames,
        "throughput_fps": round(frames / elapsed, 2),
        "generation_ms": {"p50": round(status.generation_ms_p50, 2), "p95": round(status.generation_ms_p95, 2)},
        "dropped_frames": status.dropped_frames,
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3),
        "device_vram_used_gib": round(_device_used_gib(), 3),
        "average_power_w": round(average_w, 1),
        "power_limit_w": card and card.power_limit_w,
        "default_power_limit_w": card and card.default_power_limit_w,
        "gpu": card and {"name": card.name, "compute_capability": ".".join(map(str, card.compute_capability))},
        "driver": machine.driver_version,
        "backend": status.backend,
        "unet_precision": option.precision if option.backend == "tensorrt" else "fp16",
        "temporal_coherence": settings.temporal_coherence and not int8,
        "upscaler": settings.upscaling,
        "generation_resolution": [gw, gh],
        "output_resolution": [ow, oh],
        "output_format": sink.format.value,
        "input": str(image) if image else "synthetic",
        "strength": settings.strength,
        "seed": settings.seed,
        "prompts": [prompt.model_dump() for prompt in settings.prompts],
        "versions": _versions(),
    }
    if int8 and settings.temporal_coherence:
        report["temporal_coherence_note"] = "requested, but the INT8 UNet has no Temporal Coherence"
    return report, sink


@contextmanager
def _workload(backend: Backend, settings: Settings, image: Path | None) -> Iterator[tuple[Runtime, MemorySink]]:
    """A Runtime on a static Source: one Input Frame, always fresh, so Generation never waits for input."""
    gen = settings.generation
    net = MemoryTransports()
    settings = settings.merged({"source": {"transport": "ndi", "name": "bench"}})
    source = net.add_source("bench", repeat_fps=240)
    source.push(input_frame(_input_pixels(image, gen.width, gen.height)))
    sink = net.sink(settings.sink)
    sink.keep = 1  # the last Output Frame is saved; pinned memory for every frame would run to gigabytes
    with Runtime(settings, backend, net) as runtime:
        yield runtime, sink


@contextmanager
def _energy() -> Iterator[Any]:
    """Yields a function returning the average GPU power in watts since entering."""
    import pynvml

    pynvml.nvmlInit()
    try:
        gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
        energy_mj, started = pynvml.nvmlDeviceGetTotalEnergyConsumption(gpu), time.perf_counter()
        yield (
            lambda: (
                (pynvml.nvmlDeviceGetTotalEnergyConsumption(gpu) - energy_mj) / 1000 / (time.perf_counter() - started)
            )
        )
    finally:
        pynvml.nvmlShutdown()


def _power_limit() -> float | None:
    machine = doctor.collect()
    return machine.gpus[0].power_limit_w if machine.gpus else None


def _device_used_gib() -> float:
    free, total = torch.cuda.mem_get_info()
    return (total - free) / 2**30


def _versions() -> dict[str, Any]:
    versions: dict[str, Any] = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
    }
    for name in ("streamturbo", "diffusers", "transformers", "tensorrt-cu13"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _input_pixels(image: Path | None, width: int, height: int) -> torch.Tensor:
    if image is None:
        return synthetic_frame(width, height)
    from PIL import Image

    rgba = Image.open(image).convert("RGBA")
    return torch.frombuffer(bytearray(rgba.tobytes()), dtype=torch.uint8).view(rgba.height, rgba.width, 4)


def _write(out: Path, results: list[dict[str, Any]], skip: dict[str, Any] | None) -> None:
    (out / "results.json").write_text(
        json.dumps({"options": results, "similar_frame_skip": skip}, indent=2), encoding="utf-8"
    )
    lines = [
        "| Option | Throughput | Generation p50 / p95 | Peak VRAM | Power | Limit |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        if "error" in r:
            lines.append(f"| {r['option']} | failed: {r['error'].splitlines()[0]} | | | | |")
            continue
        ms = r["generation_ms"]
        lines.append(
            f"| {r['option']} | {r['throughput_fps']} fps | {ms['p50']} / {ms['p95']} ms | "
            f"{r['device_vram_used_gib']} GiB | {r['average_power_w']} W | {r['power_limit_w']} W |"
        )
    if skip:
        lines += [
            "",
            f"Similar Frame Skip on a static Source ({skip['seconds']} s each, limit {skip['power_limit_w']} W):",
            f"off {skip['off']['average_power_w']} W, on {skip['on']['average_power_w']} W "
            f"({skip['on']['frames_skipped']} frames skipped).",
        ]
    (out / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _wait_sent(runtime: Runtime, count: int) -> None:
    while runtime.status().frames_sent < count:
        if error := runtime.status().error:
            raise RuntimeError(error)
        time.sleep(0.01)


def _save_png(sink: MemorySink, path: Path) -> None:
    from PIL import Image

    from streamturbo import imageops

    frame = sink.frames[-1]
    rgb = imageops.to_rgb(
        frame.data, frame.width, frame.height, frame.width * frame.format.bytes_per_pixel, frame.format
    )
    pixels = (rgb[0] * 255).round().to(torch.uint8).permute(1, 2, 0).numpy()
    Image.fromarray(pixels).save(path)

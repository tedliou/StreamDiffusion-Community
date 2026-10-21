"""`streamturbo bench`: measures the Glass workload and writes a machine-readable report.

Benchmarks are records, not tests: results are compared per milestone and never gate CI.
"""

import importlib.metadata
import json
import platform
import time
from datetime import datetime
from pathlib import Path

import torch

from streamturbo import doctor, weights
from streamturbo.frames import PixelFormat
from streamturbo.model_spec import SD_TURBO
from streamturbo.paths import output_dir
from streamturbo.runtime import Runtime
from streamturbo.settings import Settings
from streamturbo.testframe import synthetic_frame
from streamturbo.transports.memory import MemorySink, MemorySource, input_frame

WARMUP_FRAMES = 20


def run(settings: Settings, frames: int = 120, out: Path | None = None) -> Path:
    """Run the workload and return the path of the JSON report (a PNG of the last Output Frame sits beside it)."""
    import pynvml

    from streamturbo.backends.pytorch import PyTorchBackend

    out = out or output_dir() / "bench"
    out.mkdir(parents=True, exist_ok=True)
    backend = PyTorchBackend(SD_TURBO, *weights.fetch_all(SD_TURBO))
    gen = settings.generation
    source = MemorySource(repeat_fps=240)  # a fresh Input Frame is always waiting
    source.push(input_frame(synthetic_frame(gen.width, gen.height)))
    sink = MemorySink(PixelFormat.UYVY if settings.sink.transport == "ndi" else PixelFormat.RGBA)

    pynvml.nvmlInit()
    gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
    try:
        with Runtime(settings, backend, source, sink) as runtime:
            _wait_sent(runtime, WARMUP_FRAMES)
            torch.cuda.reset_peak_memory_stats()
            energy_mj, started = pynvml.nvmlDeviceGetTotalEnergyConsumption(gpu), time.perf_counter()
            _wait_sent(runtime, WARMUP_FRAMES + frames)
            elapsed = time.perf_counter() - started
            average_w = (pynvml.nvmlDeviceGetTotalEnergyConsumption(gpu) - energy_mj) / 1000 / elapsed
            status = runtime.status()
    finally:
        pynvml.nvmlShutdown()

    machine = doctor.collect()
    card = machine.gpus[0] if machine.gpus else None
    report = {
        "workload": "glass",
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "frames": frames,
        "throughput_fps": round(frames / elapsed, 2),
        "generation_ms": {"p50": round(status.generation_ms_p50, 2), "p95": round(status.generation_ms_p95, 2)},
        "dropped_frames": status.dropped_frames,
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3),
        "average_power_w": round(average_w, 1),
        "power_limit_w": card and card.power_limit_w,
        "default_power_limit_w": card and card.default_power_limit_w,
        "gpu": card and {"name": card.name, "compute_capability": ".".join(map(str, card.compute_capability))},
        "driver": machine.driver_version,
        "backend": status.backend,
        "generation_resolution": [gen.width, gen.height],
        "output_resolution": [settings.output.width, settings.output.height],
        "output_format": sink.format.value,
        "strength": settings.strength,
        "seed": settings.seed,
        "prompt": settings.prompt,
        "versions": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            **{name: importlib.metadata.version(name) for name in ("streamturbo", "diffusers", "transformers")},
        },
    }
    stem = out / f"bench-{datetime.now():%Y%m%d-%H%M%S}"
    stem.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _save_png(sink, stem.with_suffix(".png"))
    return stem.with_suffix(".json")


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

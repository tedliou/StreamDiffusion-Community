"""`streamturbo doctor`: a quick health report of the machine the Runtime runs on."""

import importlib
import importlib.metadata
import platform
from collections.abc import Callable
from dataclasses import dataclass, field
from types import ModuleType

# MIN_DRIVER_MAJOR and DRIVER_URL are also checked by start.cmd before Python exists; keep them in step.
MIN_DRIVER_MAJOR = 580  # CUDA 13 (ADR-0001)
DRIVER_URL = "https://www.nvidia.com/Download/index.aspx"
MIN_COMPUTE_CAPABILITY = (7, 5)  # Turing
# VRAM tiers in nominal GB (ADR-0001): below LOW_VRAM_GB the Runtime runs in Low-VRAM Mode.
MIN_VRAM_GB, LOW_VRAM_GB, FULL_VRAM_GB = 4, 6, 8


def nominal_gb(vram_bytes: int) -> int:
    """VRAM as sold: a 4 GB card reports a little under 4 GiB."""
    return round(vram_bytes / 1024**3)


@dataclass(frozen=True)
class Gpu:
    name: str
    compute_capability: tuple[int, int]
    vram_bytes: int
    power_limit_w: float | None
    default_power_limit_w: float | None


@dataclass(frozen=True)
class TransportStatus:
    name: str
    available: bool
    detail: str


@dataclass
class Report:
    python: str
    driver_version: str | None = None
    gpus: list[Gpu] = field(default_factory=list)
    torch_version: str | None = None
    torch_cuda: str | None = None
    cuda_available: bool = False
    tensorrt_version: str | None = None
    engines: str = "unknown"  # which TensorRT Engines are cached for this GPU
    transports: list[TransportStatus] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def collect() -> Report:
    report = Report(python=platform.python_version())
    _collect_gpus(report)
    _collect_torch(report)
    _collect_engines(report)
    _collect_transports(report)
    return report


def _collect_gpus(report: Report) -> None:
    try:
        import pynvml

        pynvml.nvmlInit()
    except Exception as exc:
        report.problems.append(f"No NVIDIA driver found ({exc}). Install one from {DRIVER_URL}")
        return
    try:
        driver_version: str = pynvml.nvmlSystemGetDriverVersion()
        report.driver_version = driver_version
        for index in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            report.gpus.append(
                Gpu(
                    name=pynvml.nvmlDeviceGetName(handle),
                    compute_capability=pynvml.nvmlDeviceGetCudaComputeCapability(handle),
                    vram_bytes=int(pynvml.nvmlDeviceGetMemoryInfo(handle).total),
                    power_limit_w=_watts(pynvml.nvmlDeviceGetEnforcedPowerLimit, handle),
                    default_power_limit_w=_watts(pynvml.nvmlDeviceGetPowerManagementDefaultLimit, handle),
                )
            )
    finally:
        pynvml.nvmlShutdown()

    if int(driver_version.split(".")[0]) < MIN_DRIVER_MAJOR:
        report.problems.append(
            f"NVIDIA driver {driver_version} is older than {MIN_DRIVER_MAJOR}. Update it from {DRIVER_URL}"
        )
    supported = [gpu for gpu in report.gpus if gpu.compute_capability >= MIN_COMPUTE_CAPABILITY]
    if not supported:
        report.problems.append("No NVIDIA GPU of the Turing generation (RTX 20) or newer was found.")
        return
    gpu, gb = supported[0], nominal_gb(supported[0].vram_bytes)
    if gb < MIN_VRAM_GB:
        report.problems.append(f"{gpu.name} has {gb} GB of VRAM; StreamTurbo needs at least {MIN_VRAM_GB} GB.")
    elif gb < LOW_VRAM_GB:
        report.warnings.append(
            f"{gpu.name} has {gb} GB of VRAM: the Runtime runs in Low-VRAM Mode (automatic below {LOW_VRAM_GB} GB), "
            "pausing output while TensorRT Engines build."
        )
    elif gb < FULL_VRAM_GB:
        report.warnings.append(
            f"{gpu.name} has {gb} GB of VRAM: if TensorRT Engines fail to build, run with --low-vram "
            f"(automatic below {LOW_VRAM_GB} GB)."
        )


def _watts(query: Callable[[object], int], handle: object) -> float | None:
    try:
        return query(handle) / 1000
    except Exception:
        return None  # not every GPU exposes power management


def _collect_torch(report: Report) -> None:
    try:
        import torch
    except Exception as exc:
        report.problems.append(f"PyTorch cannot be imported ({exc}). Run start.cmd to repair the environment.")
        return
    report.torch_version = torch.__version__
    report.torch_cuda = torch.version.cuda
    report.cuda_available = torch.cuda.is_available()
    if not report.cuda_available:
        report.problems.append("PyTorch cannot use CUDA on this machine.")


def _collect_engines(report: Report) -> None:
    try:
        report.tensorrt_version = importlib.metadata.version("tensorrt-cu13")
    except importlib.metadata.PackageNotFoundError:
        report.warnings.append("TensorRT is not installed: the slower PyTorch Backend will be used.")
        return
    if not report.cuda_available:
        return
    try:
        from streamturbo.backends.tensorrt import COMPONENTS, missing_engines
        from streamturbo.model_spec import SD_TURBO
        from streamturbo.paths import engines_dir

        missing = missing_engines(engines_dir(), SD_TURBO)
    except Exception as exc:
        report.warnings.append(f"TensorRT cannot be loaded ({exc}): the slower PyTorch Backend will be used.")
        return
    if not missing:
        report.engines = f"all {len(COMPONENTS)} built in {engines_dir()}"
    else:
        report.engines = f"{', '.join(missing)} not built yet (built on first run, or `streamturbo build-engines`)"


def _collect_transports(report: Report) -> None:
    report.transports = [
        _probe("NDI", "cyndilib", lambda module: module.get_ndi_version()),
        _probe("Spout", "SpoutGL", lambda _: f"SpoutGL {importlib.metadata.version('SpoutGL')}"),
    ]
    missing = [transport.name for transport in report.transports if not transport.available]
    if len(missing) == len(report.transports):
        report.problems.append("Neither NDI nor Spout is available.")
    for name in missing:
        report.warnings.append(f"{name} is not available.")


def _probe(name: str, module_name: str, describe: Callable[[ModuleType], str]) -> TransportStatus:
    try:
        module = importlib.import_module(module_name)
        return TransportStatus(name, True, describe(module))
    except Exception as exc:
        return TransportStatus(name, False, str(exc))


def render(report: Report) -> str:
    lines = ["StreamTurbo doctor", "", "GPU"]
    lines.append(f"  driver            {report.driver_version or 'not found'}")
    for index, gpu in enumerate(report.gpus):
        major, minor = gpu.compute_capability
        lines += [
            f"  [{index}] {gpu.name}",
            f"      compute       {major}.{minor}",
            f"      VRAM          {gpu.vram_bytes / 1024**3:.1f} GB",
            f"      power limit   {_format_power(gpu)}",
        ]
    lines += [
        "",
        "Libraries",
        f"  python            {report.python}",
        f"  torch             {report.torch_version or 'not installed'}",
        f"  CUDA (torch)      {report.torch_cuda or '-'} ({'available' if report.cuda_available else 'unavailable'})",
        f"  TensorRT          {report.tensorrt_version or 'not installed'}",
        f"  Engines           {report.engines}",
        "",
        "Transports",
    ]
    for transport in report.transports:
        state = "available" if transport.available else "unavailable"
        lines.append(f"  {transport.name:<17} {state}: {transport.detail}")
    if report.warnings or report.problems:
        lines.append("")
    lines += [f"WARNING: {message}" for message in report.warnings]
    lines += [f"PROBLEM: {message}" for message in report.problems]
    lines += ["", "OK" if report.ok else "NOT READY"]
    return "\n".join(lines)


def _format_power(gpu: Gpu) -> str:
    if gpu.power_limit_w is None:
        return "not reported"
    text = f"{gpu.power_limit_w:.0f} W enforced"
    if gpu.default_power_limit_w:
        share = gpu.power_limit_w / gpu.default_power_limit_w
        text += f" of {gpu.default_power_limit_w:.0f} W default ({share:.0%})"
    return text

"""`streamturbo doctor` behaviour, observed through the CLI."""

import sys
from types import SimpleNamespace

import pytest

from streamturbo.cli import main


def fake_nvml(driver: str = "621.01", compute: tuple[int, int] = (8, 6), vram_gib: int = 8) -> SimpleNamespace:
    """Stand-in for the NVIDIA driver's NVML library, so GPU cases run on CPU-only CI."""
    return SimpleNamespace(
        nvmlInit=lambda: None,
        nvmlShutdown=lambda: None,
        nvmlSystemGetDriverVersion=lambda: driver,
        nvmlDeviceGetCount=lambda: 1,
        nvmlDeviceGetHandleByIndex=lambda index: index,
        nvmlDeviceGetName=lambda handle: "NVIDIA GeForce RTX 3070",
        nvmlDeviceGetCudaComputeCapability=lambda handle: compute,
        nvmlDeviceGetMemoryInfo=lambda handle: SimpleNamespace(total=vram_gib * 1024**3),
        nvmlDeviceGetEnforcedPowerLimit=lambda handle: 162_000,
        nvmlDeviceGetPowerManagementDefaultLimit=lambda handle: 270_000,
    )


def run_doctor(capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = main(["doctor"])
    return code, capsys.readouterr().out


def test_doctor_reports_every_section(capsys):
    code, out = run_doctor(capsys)

    for heading in ("GPU", "Libraries", "Transports", "torch", "CUDA (torch)", "NDI", "Spout"):
        assert heading in out
    assert out.rstrip().endswith("OK" if code == 0 else "NOT READY")


def test_doctor_reports_gpu_and_power_limits(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "pynvml", fake_nvml())

    _, out = run_doctor(capsys)

    assert "NVIDIA GeForce RTX 3070" in out
    assert "621.01" in out
    assert "8.6" in out
    assert "8.0 GB" in out
    assert "162 W enforced of 270 W default (60%)" in out


def test_doctor_fails_without_nvidia_driver(capsys, monkeypatch):
    def no_driver():
        raise OSError("nvml.dll not found")

    monkeypatch.setitem(sys.modules, "pynvml", SimpleNamespace(nvmlInit=no_driver))

    code, out = run_doctor(capsys)

    assert code == 1
    assert "PROBLEM: No NVIDIA driver found" in out
    assert "nvidia.com" in out


def test_doctor_fails_on_old_driver(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "pynvml", fake_nvml(driver="566.36"))

    code, out = run_doctor(capsys)

    assert code == 1
    assert "PROBLEM: NVIDIA driver 566.36 is older than 580" in out


def test_doctor_fails_on_pre_turing_gpu(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "pynvml", fake_nvml(compute=(6, 1)))

    code, out = run_doctor(capsys)

    assert code == 1
    assert "PROBLEM: No NVIDIA GPU of the Turing generation" in out


def test_doctor_warns_below_8_gb_vram(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "pynvml", fake_nvml(vram_gib=6))

    _, out = run_doctor(capsys)

    assert "WARNING: NVIDIA GeForce RTX 3070 has less than 8 GB of VRAM." in out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.startswith("streamturbo ")


@pytest.mark.gpu
def test_doctor_is_ready_on_a_real_gpu(capsys):
    code, out = run_doctor(capsys)

    assert code == 0, out
    assert "CUDA (torch)      13.0 (available)" in out
    assert "NDI               available" in out
    assert "Spout             available" in out

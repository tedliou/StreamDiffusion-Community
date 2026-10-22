"""Backend: executes the UNet, the tiny VAE and the text encoder for the Generation core."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

import torch

from streamturbo.settings import BackendChoice

EngineState = Literal["off", "building", "ready", "failed"]


class Backend(Protocol):
    @property
    def name(self) -> str: ...

    device: torch.device
    dtype: torch.dtype
    alphas_cumprod: torch.Tensor  # (1000,) float32 noise schedule of the model
    latent_channels: int
    latent_scale: int  # pixels per latent cell

    def encode_prompt(self, prompt: str) -> torch.Tensor: ...

    def encode(self, image: torch.Tensor) -> torch.Tensor:
        """(1, 3, H, W) in [-1, 1] -> latents."""
        ...

    def decode(self, latents: torch.Tensor) -> torch.Tensor:
        """Latents -> (1, 3, H, W) in [-1, 1]."""
        ...

    def unet(self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor) -> torch.Tensor:
        """Predicted noise (epsilon) for latents at timestep."""
        ...


Bank = object  # a Backend's own record of one Generation's self-attention features, opaque to everyone else


@runtime_checkable
class CoherentUnet(Protocol):
    """A Backend that can run the UNet with Temporal Coherence."""

    def coherent_unet(
        self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor, bank: Bank | None
    ) -> tuple[torch.Tensor, Bank]:
        """Like `unet`, with self-attention also attending to `bank`, the previous call's features (none: a plain
        Generation). Returns the predicted noise and this call's features, for the next call."""
        ...


@dataclass(frozen=True)
class EngineStatus:
    state: EngineState  # off: not wanted yet, or the PyTorch Backend is forced
    progress: float = 0.0  # 0-1 while building
    detail: str | None = None  # what is building, or why the build failed


@runtime_checkable
class Releasable(Protocol):
    def release(self) -> None:
        """Free memory not needed while another Backend generates; reloaded on the next use."""
        ...


class ProgressReport(Protocol):
    def __call__(self, progress: float, detail: str | None = None) -> None: ...


BuildFast = Callable[[ProgressReport], Backend]  # build(report) -> the fast Backend, or raise


class BestBackend:
    """The best available Backend: the fallback until the fast one has been built in the background (ADR-0005).

    `choose()` is called by the generate thread between two Generations, so a Generation never mixes Backends.
    A failed build leaves the fallback in charge and says why in `engine_status()`.
    """

    def __init__(self, fallback: Backend, build: BuildFast) -> None:
        self._fallback = fallback
        self._build = build
        self._active: Backend = fallback
        self._fast: Backend | None = None
        self._lock = threading.Lock()
        self._status = EngineStatus("off")
        self._thread: threading.Thread | None = None
        self.device, self.dtype = fallback.device, fallback.dtype
        self.alphas_cumprod = fallback.alphas_cumprod
        self.latent_channels, self.latent_scale = fallback.latent_channels, fallback.latent_scale

    @property
    def name(self) -> str:
        return self._active.name

    def choose(self, choice: BackendChoice) -> None:
        if choice == "pytorch":
            self._active = self._fallback
            return
        with self._lock:
            if self._thread is None:
                self._status = EngineStatus("building")
                self._thread = threading.Thread(target=self._run_build, name="streamturbo-engines", daemon=True)
                self._thread.start()
            fast = self._fast
        if fast is not None and self._active is not fast and isinstance(self._fallback, Releasable):
            self._fallback.release()  # e.g. the PyTorch UNet: TensorRT has its own copy
        self._active = fast or self._fallback

    def engine_status(self) -> EngineStatus:
        with self._lock:
            return self._status

    def _run_build(self) -> None:
        try:
            fast = self._build(self._report)
        except Exception as error:
            with self._lock:
                self._status = EngineStatus("failed", detail=f"{type(error).__name__}: {error}")
            return
        with self._lock:
            self._fast = fast
            self._status = EngineStatus("ready", 1.0)

    def _report(self, progress: float, detail: str | None = None) -> None:
        with self._lock:
            self._status = EngineStatus("building", progress, detail)

    def encode_prompt(self, prompt: str) -> torch.Tensor:
        return self._active.encode_prompt(prompt)

    def encode(self, image: torch.Tensor) -> torch.Tensor:
        return self._active.encode(image)

    def decode(self, latents: torch.Tensor) -> torch.Tensor:
        return self._active.decode(latents)

    def unet(self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor) -> torch.Tensor:
        return self._active.unet(latents, timestep, prompt_embeds)

    def coherent_unet(
        self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor, bank: Bank | None
    ) -> tuple[torch.Tensor, Bank]:
        """Temporal Coherence where the active Backend has it. A bank only goes back to the Backend that made it,
        so a switch costs one plain Generation."""
        active = self._active
        if not isinstance(active, CoherentUnet):
            return active.unet(latents, timestep, prompt_embeds), None
        maker, inner = bank if isinstance(bank, tuple) else (None, None)
        eps, made = active.coherent_unet(latents, timestep, prompt_embeds, inner if maker is active else None)
        return eps, (active, made)

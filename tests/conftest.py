import time

import pytest
import torch
import torch.nn.functional as F

from streamturbo.settings import Settings
from streamturbo.transports.memory import MemoryTransports


class FakeBackend:
    """A deterministic, cheap image transform standing in for sd-turbo on CPU.

    Its UNet predicts no noise, so Output Frames are the Input Frame plus the Seed's noise, scaled
    by Strength, pushed through an 8x down/up-sample. A Prompt's embedding is filled with its `shades` entry
    (0 when absent) and the UNet brightens the image by that much, so tests can see which Prompt, or which
    mix of Prompts, generated a frame. `unet_delay` simulates a slow GPU and
    `failures` makes that many UNet calls raise. A `negative` Backend inverts its Output Frames, so tests can
    tell which Backend generated a frame.
    """

    latent_channels = 4
    latent_scale = 8

    def __init__(self, unet_delay: float = 0.0, name: str = "fake", negative: bool = False) -> None:
        self.name = name
        self.negative = negative
        self.device = torch.device("cpu")
        self.dtype = torch.float32
        betas = torch.linspace(0.00085**0.5, 0.012**0.5, 1000) ** 2
        self.alphas_cumprod = torch.cumprod(1 - betas, 0)
        self.unet_delay = unet_delay
        self.failures = 0
        self.prompts: list[str] = []
        self.shades: dict[str, float] = {}

    def encode_prompt(self, prompt: str) -> torch.Tensor:
        self.prompts.append(prompt)
        return torch.full((1, 77, 8), self.shades.get(prompt, 0.0))

    def encode(self, image: torch.Tensor) -> torch.Tensor:
        pooled = F.avg_pool2d(image, self.latent_scale)
        return torch.cat((pooled, torch.zeros_like(pooled[:, :1])), dim=1)

    def decode(self, latents: torch.Tensor) -> torch.Tensor:
        image = F.interpolate(latents[:, :3], scale_factor=self.latent_scale, mode="nearest").clamp(-1, 1)
        return -image if self.negative else image

    def unet(self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor) -> torch.Tensor:
        if self.unet_delay:
            time.sleep(self.unet_delay)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("CUDA error: an illegal memory access was encountered")
        return torch.full_like(latents, -prompt_embeds.mean().item())  # predicting less noise brightens

    def coherent_unet(
        self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor, bank: object | None
    ) -> tuple[torch.Tensor, object]:
        """Temporal Coherence: with a bank (the previous noisy latents), the prediction leans halfway towards it."""
        eps = self.unet(latents, timestep, prompt_embeds)
        if isinstance(bank, torch.Tensor) and bank.shape == latents.shape:
            eps = eps + (latents - bank) / 2
        return eps, latents


@pytest.fixture
def small_settings() -> Settings:
    """Small sizes keep the fake Backend fast on CPU. Source "cam" and Sink "out" are both Spout (RGBA).

    Temporal Smoothing, Strength glide and Prompt transitions are off, so each Output Frame follows its Input
    Frame and the latest Settings at once; the tests for those features turn them on.
    """
    return Settings.model_validate(
        {
            "source": {"transport": "spout", "name": "cam"},
            "sink": {"transport": "spout", "name": "out"},
            "generation": {"width": 256, "height": 256},
            "output": {"width": 320, "height": 240},
            "temporal_smoothing": 0.0,
            "strength_glide": 0.0,
            "prompt_transition": 0.0,
        }
    )


@pytest.fixture
def net() -> MemoryTransports:
    return MemoryTransports()

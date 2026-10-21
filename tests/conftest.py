import time

import pytest
import torch
import torch.nn.functional as F

from streamturbo.settings import Settings


class FakeBackend:
    """A deterministic, cheap image transform standing in for sd-turbo on CPU.

    Its UNet predicts no noise, so Output Frames are the Input Frame plus the Seed's noise, scaled
    by Strength, pushed through an 8x down/up-sample. `unet_delay` simulates a slow GPU and
    `failures` makes that many UNet calls raise.
    """

    name = "fake"
    latent_channels = 4
    latent_scale = 8

    def __init__(self, unet_delay: float = 0.0) -> None:
        self.device = torch.device("cpu")
        self.dtype = torch.float32
        betas = torch.linspace(0.00085**0.5, 0.012**0.5, 1000) ** 2
        self.alphas_cumprod = torch.cumprod(1 - betas, 0)
        self.unet_delay = unet_delay
        self.failures = 0
        self.prompts: list[str] = []

    def encode_prompt(self, prompt: str) -> torch.Tensor:
        self.prompts.append(prompt)
        return torch.zeros(1, 77, 8)

    def encode(self, image: torch.Tensor) -> torch.Tensor:
        pooled = F.avg_pool2d(image, self.latent_scale)
        return torch.cat((pooled, torch.zeros_like(pooled[:, :1])), dim=1)

    def decode(self, latents: torch.Tensor) -> torch.Tensor:
        return F.interpolate(latents[:, :3], scale_factor=self.latent_scale, mode="nearest").clamp(-1, 1)

    def unet(self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor) -> torch.Tensor:
        if self.unet_delay:
            time.sleep(self.unet_delay)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("CUDA error: an illegal memory access was encountered")
        return torch.zeros_like(latents)


@pytest.fixture
def small_settings() -> Settings:
    """Small sizes keep the fake Backend fast on CPU."""
    return Settings.model_validate(
        {
            "source": {"transport": "none"},
            "generation": {"width": 256, "height": 256},
            "output": {"width": 320, "height": 240},
        }
    )

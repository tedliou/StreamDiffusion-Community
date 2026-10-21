"""Backend: executes the UNet, the tiny VAE and the text encoder for the Generation core."""

from typing import Protocol

import torch


class Backend(Protocol):
    name: str
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

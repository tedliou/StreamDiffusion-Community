"""Generation core: sd-turbo single-step img2img and txt2img in Strength mode (ADR-0002).

Tensor in, tensor out. It knows nothing about Transports, threads or Control Surfaces.
"""

import torch

from streamturbo.backends import Backend

MAX_TIMESTEP = 999


def timestep_for(strength: float) -> int:
    """Strength mode: one UNet step at t = round(Strength x 999), clamped to 1-999."""
    return min(MAX_TIMESTEP, max(1, round(strength * MAX_TIMESTEP)))


class GenerationCore:
    def __init__(self, backend: Backend) -> None:
        self.backend = backend
        # Coefficient table for every timestep, so a Strength change is a lookup.
        alphas = backend.alphas_cumprod.to(backend.device, torch.float32)
        self._signal = alphas.sqrt()
        self._noise = (1 - alphas).sqrt()
        self._timesteps = torch.arange(MAX_TIMESTEP + 1, device=backend.device)
        self._prompt: str | None = None
        self._prompt_embeds: torch.Tensor | None = None
        self._seed: int | None = None
        self._latent_noise: torch.Tensor | None = None

    def set_prompt(self, prompt: str) -> None:
        if prompt != self._prompt:
            self._prompt_embeds = self.backend.encode_prompt(prompt)
            self._prompt = prompt

    def set_seed(self, seed: int) -> None:
        if seed != self._seed:
            self._seed = seed
            self._latent_noise = None

    @torch.inference_mode()
    def generate(self, image: torch.Tensor | None, strength: float, width: int, height: int) -> torch.Tensor:
        """One Generation. `image` is (1, 3, H, W) in [-1, 1], or None for txt2img.

        Strength 0 passes the image through the tiny VAE only; Strength 1, or no image, is txt2img.
        """
        if self._prompt_embeds is None or self._seed is None:
            raise RuntimeError("set_prompt() and set_seed() must be called before generate()")
        backend = self.backend
        if image is not None and strength <= 0:
            return backend.decode(backend.encode(image))

        noise = self._noise_for(width, height)
        t = timestep_for(strength)
        signal, noise_level = self._signal[t], self._noise[t]
        if image is None or strength >= 1:
            noisy = noise_level * noise
        else:
            noisy = signal * backend.encode(image).float() + noise_level * noise
        eps = backend.unet(noisy, self._timesteps[t : t + 1], self._prompt_embeds).float()
        return backend.decode((noisy - noise_level * eps) / signal)

    def _noise_for(self, width: int, height: int) -> torch.Tensor:
        """Fixed noise per Seed and size: Strength changes never re-roll it."""
        backend = self.backend
        shape = (1, backend.latent_channels, height // backend.latent_scale, width // backend.latent_scale)
        if self._latent_noise is None or self._latent_noise.shape != shape:
            generator = torch.Generator(backend.device).manual_seed(self._seed or 0)
            self._latent_noise = torch.randn(shape, generator=generator, device=backend.device)
        return self._latent_noise

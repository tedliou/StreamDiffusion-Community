"""Generation core: sd-turbo single-step img2img and txt2img in Strength mode (ADR-0002).

Tensor in, tensor out. It knows nothing about Transports, threads or Control Surfaces.
"""

import time
from collections.abc import Callable, Sequence

import torch

from streamturbo.backends import Backend, Bank, CoherentUnet

MAX_TIMESTEP = 999


def timestep_for(strength: float) -> int:
    """Strength mode: one UNet step at t = round(Strength x 999), clamped to 1-999."""
    return min(MAX_TIMESTEP, max(1, round(strength * MAX_TIMESTEP)))


class Glide[T: (float, torch.Tensor)]:
    """A value that moves in a straight line to each new target over a given time instead of jumping."""

    def __init__(self, value: T, clock: Callable[[], float] = time.monotonic) -> None:
        self._start = self._target = value
        self._began, self._duration = 0.0, 0.0
        self._clock = clock

    @property
    def target(self) -> T:
        return self._target

    def settled(self) -> bool:
        return self._progress() >= 1

    def value(self) -> T:
        progress = self._progress()
        return self._target if progress >= 1 else self._start + (self._target - self._start) * progress

    def move_to(self, target: T, duration: float) -> None:
        """Head for `target` from wherever the value is now, arriving `duration` seconds from now."""
        self._start, self._target = self.value(), target
        self._began, self._duration = self._clock(), duration

    def _progress(self) -> float:
        if self._duration <= 0:
            return 1.0
        return min(1.0, (self._clock() - self._began) / self._duration)


class GenerationCore:
    def __init__(self, backend: Backend) -> None:
        self.backend = backend
        # Coefficient table for every timestep, so a Strength change is a lookup.
        alphas = backend.alphas_cumprod.to(backend.device, torch.float32)
        self._signal = alphas.sqrt()
        self._noise = (1 - alphas).sqrt()
        self._timesteps = torch.arange(MAX_TIMESTEP + 1, device=backend.device)
        self._prompts: tuple[tuple[str, float], ...] = ()
        self._embeds: dict[str, torch.Tensor] = {}  # per Prompt text, for the Prompts in the current blend
        self._blend: Glide[torch.Tensor] | None = None  # the Prompt Blend's embeddings, in float32
        self._seed: int | None = None
        self._latent_noise: torch.Tensor | None = None
        self._previous: torch.Tensor | None = None  # the last Generation's latents, for Temporal Smoothing
        self._bank: Bank | None = None  # the last Generation's self-attention features, for Temporal Coherence

    @torch.inference_mode()
    def set_prompts(self, prompts: Sequence[tuple[str, float]], transition: float = 0.0) -> None:
        """Move to a new Prompt Blend of (text, weight) pairs over `transition` seconds.

        The blend is the weighted mean of the Prompts' embeddings, so weights count relative to their total.
        """
        prompts = tuple(prompts)
        if prompts == self._prompts:
            return
        total = sum(weight for _, weight in prompts)
        if total <= 0:
            raise ValueError("at least one Prompt needs a weight above 0")
        embeds = {text: self._embeds.get(text) for text, _ in prompts}
        self._embeds = {
            text: self.backend.encode_prompt(text) if known is None else known for text, known in embeds.items()
        }
        first = next(iter(self._embeds.values()))
        target = torch.zeros_like(first, dtype=torch.float32)
        for text, weight in prompts:
            target += self._embeds[text].float() * (weight / total)
        self._prompts = prompts
        if self._blend is None:
            self._blend = Glide(target)
        else:
            self._blend.move_to(target, transition)

    def settled(self) -> bool:
        """Whether the Prompt Blend has finished its transition, so equal inputs give equal Output Frames."""
        return self._blend is None or self._blend.settled()

    def set_seed(self, seed: int) -> None:
        if seed != self._seed:
            self._seed = seed
            self._latent_noise = None

    def forget_previous(self) -> None:
        """Start Temporal Smoothing and Temporal Coherence afresh: the next Generation leans on nothing."""
        self._previous = self._bank = None

    @torch.inference_mode()
    def generate(
        self,
        image: torch.Tensor | None,
        strength: float,
        width: int,
        height: int,
        smoothing: float = 0.0,
        coherence: bool = False,
    ) -> torch.Tensor:
        """One Generation. `image` is (1, 3, H, W) in [-1, 1], or None for txt2img.

        Strength 0 passes the image through the tiny VAE only; Strength 1, or no image, is txt2img.
        Temporal Smoothing keeps `smoothing` (0-1) of the previous Generation's latents. Temporal Coherence lets
        the UNet attend to the previous Generation's features, on a Backend that has it.
        """
        if self._blend is None or self._seed is None:
            raise RuntimeError("set_prompts() and set_seed() must be called before generate()")
        if not coherence:
            self._bank = None
        embeds = self._blend.value().to(self.backend.dtype)
        latents = self._predict_latents(image, strength, width, height, embeds, coherence)
        previous, self._previous = self._previous, latents
        if smoothing > 0 and previous is not None and previous.shape == latents.shape:
            latents = self._previous = torch.lerp(latents, previous, smoothing)
        return self.backend.decode(latents)

    def _predict_latents(
        self,
        image: torch.Tensor | None,
        strength: float,
        width: int,
        height: int,
        prompt_embeds: torch.Tensor,
        coherence: bool,
    ) -> torch.Tensor:
        """The clean latents one UNet step predicts."""
        backend = self.backend
        if image is not None and strength <= 0:
            return backend.encode(image).float()
        noise = self._noise_for(width, height)
        t = timestep_for(1.0 if image is None else strength)
        signal, noise_level = self._signal[t], self._noise[t]
        if image is None or strength >= 1:
            noisy = noise_level * noise
        else:
            noisy = signal * backend.encode(image).float() + noise_level * noise
        timestep = self._timesteps[t : t + 1]
        if coherence and isinstance(backend, CoherentUnet):
            eps, self._bank = backend.coherent_unet(noisy, timestep, prompt_embeds, self._bank)
        else:
            eps = backend.unet(noisy, timestep, prompt_embeds)
        eps = eps.float()
        return (noisy - noise_level * eps) / signal

    def _noise_for(self, width: int, height: int) -> torch.Tensor:
        """Fixed noise per Seed and size: Strength changes never re-roll it."""
        backend = self.backend
        shape = (1, backend.latent_channels, height // backend.latent_scale, width // backend.latent_scale)
        if self._latent_noise is None or self._latent_noise.shape != shape:
            generator = torch.Generator(backend.device).manual_seed(self._seed or 0)
            self._latent_noise = torch.randn(shape, generator=generator, device=backend.device)
        return self._latent_noise

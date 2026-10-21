"""PyTorch Backend: eager fp16 on CUDA with SDPA attention."""

from pathlib import Path

import torch

from streamturbo.model_spec import ModelSpec


class PyTorchBackend:
    name = "pytorch"
    latent_channels = 4
    latent_scale = 8

    def __init__(self, spec: ModelSpec, model_dir: Path, tiny_vae_dir: Path, device: str = "cuda") -> None:
        from diffusers.models.autoencoders.autoencoder_tiny import AutoencoderTiny
        from diffusers.models.unets.unet_2d_condition import UNet2DConditionModel
        from diffusers.schedulers.scheduling_euler_discrete import EulerDiscreteScheduler
        from transformers import CLIPTextModel, CLIPTokenizer

        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
        self.spec = spec
        self.device = torch.device(device)
        self.dtype = torch.float16
        # The libraries' decorated `.to` and union-typed `from_pretrained` mislead pyright, hence the ignores.
        self._tokenizer = CLIPTokenizer.from_pretrained(model_dir, subfolder="tokenizer")
        self._text_encoder = (
            CLIPTextModel.from_pretrained(model_dir, subfolder="text_encoder", variant="fp16", dtype=self.dtype)
            .to(self.device)  # pyright: ignore[reportArgumentType]
            .eval()
        )
        self._unet = (
            UNet2DConditionModel.from_pretrained(model_dir, subfolder="unet", variant="fp16", torch_dtype=self.dtype)
            .to(self.device, memory_format=torch.channels_last)  # pyright: ignore[reportArgumentType]
            .eval()
        )
        self._vae = AutoencoderTiny.from_pretrained(tiny_vae_dir, torch_dtype=self.dtype)
        self._vae = self._vae.to(self.device).eval()  # pyright: ignore[reportArgumentType]
        scheduler = EulerDiscreteScheduler.from_pretrained(model_dir, subfolder="scheduler")
        self.alphas_cumprod = scheduler.alphas_cumprod.float().to(self.device)  # pyright: ignore[reportAttributeAccessIssue]

    @torch.inference_mode()
    def encode_prompt(self, prompt: str) -> torch.Tensor:
        tokens = self._tokenizer(
            prompt,
            padding="max_length",
            max_length=self._tokenizer.model_max_length,
            truncation=True,
            return_tensors="pt",
        ).input_ids.to(self.device)
        return self._text_encoder(tokens)[0]

    @torch.inference_mode()
    def encode(self, image: torch.Tensor) -> torch.Tensor:
        return self._vae.encode(image.to(self.dtype), return_dict=False)[0]

    @torch.inference_mode()
    def decode(self, latents: torch.Tensor) -> torch.Tensor:
        return self._vae.decode(latents.to(self.dtype), return_dict=False)[0]

    @torch.inference_mode()
    def unet(self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor) -> torch.Tensor:
        return self._unet(latents.to(self.dtype), timestep, encoder_hidden_states=prompt_embeds, return_dict=False)[0]

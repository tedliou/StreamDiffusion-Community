"""PyTorch Backend: eager fp16 on CUDA with SDPA attention."""

from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

KeysValues = dict[str, tuple[torch.Tensor, torch.Tensor]]  # per self-attention layer: one Generation's features
# Self-attention at the highest resolution stays plain under Temporal Coherence: it costs most there (128x96
# tokens at 1024x768) and adds little (M5 spike, #14).
HIGHEST_RESOLUTION = ("down_blocks.0.", "up_blocks.3.")


class _Recorder:
    """What the coherent self-attention layers share during one Temporal Coherence call."""

    def __init__(self) -> None:
        self.recording = False
        self.previous: KeysValues = {}
        self.current: KeysValues = {}


class _CoherentSelfAttention:
    """Self-attention that also attends to the previous Generation's keys and values (Temporal Coherence).

    Reimplemented from the StreamV2V paper's extended self-attention (arXiv 2405.15757), keeping one frame.
    Outside a Temporal Coherence call it is the layer's own processor, so exports and plain calls are unchanged.
    """

    def __init__(self, name: str, own: Any, recorder: _Recorder) -> None:
        self._name, self._own, self._recorder = name, own, recorder

    def __call__(self, attn: Any, hidden_states: torch.Tensor, *args: Any, **kwargs: Any) -> torch.Tensor:
        recorder = self._recorder
        if not recorder.recording:
            return self._own(attn, hidden_states, *args, **kwargs)
        batch = hidden_states.shape[0]
        query, key, value = attn.to_q(hidden_states), attn.to_k(hidden_states), attn.to_v(hidden_states)
        recorder.current[self._name] = (key, value)
        previous = recorder.previous.get(self._name)
        if previous is not None and previous[0].shape == key.shape:
            key, value = torch.cat((key, previous[0]), dim=1), torch.cat((value, previous[1]), dim=1)
        head_dim = query.shape[-1] // attn.heads
        query, key, value = (x.view(batch, -1, attn.heads, head_dim).transpose(1, 2) for x in (query, key, value))
        out = F.scaled_dot_product_attention(query, key, value)
        out = out.transpose(1, 2).reshape(batch, -1, attn.heads * head_dim).to(query.dtype)
        return attn.to_out[1](attn.to_out[0](out))


class PyTorchBackend:
    name = "pytorch"
    latent_channels = 4
    latent_scale = 8

    def __init__(self, model_dir: Path, tiny_vae_dir: Path, device: str = "cuda") -> None:
        from diffusers.models.autoencoders.autoencoder_tiny import AutoencoderTiny
        from diffusers.schedulers.scheduling_euler_discrete import EulerDiscreteScheduler
        from transformers import CLIPTextModel, CLIPTokenizer

        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
        self.device = torch.device(device)
        self.dtype = torch.float16
        # The libraries' decorated `.to` and union-typed `from_pretrained` mislead pyright, hence the ignores.
        self._tokenizer = CLIPTokenizer.from_pretrained(model_dir, subfolder="tokenizer")
        self._text_encoder = (
            CLIPTextModel.from_pretrained(model_dir, subfolder="text_encoder", variant="fp16", dtype=self.dtype)
            .to(self.device)  # pyright: ignore[reportArgumentType]
            .eval()
        )
        self._model_dir = model_dir
        self._recorder = _Recorder()
        self._unet: torch.nn.Module | None = self._load_unet()
        self._vae = AutoencoderTiny.from_pretrained(tiny_vae_dir, torch_dtype=self.dtype)
        self._vae = self._vae.to(self.device).eval()  # pyright: ignore[reportArgumentType]
        scheduler = EulerDiscreteScheduler.from_pretrained(model_dir, subfolder="scheduler")
        self.alphas_cumprod = scheduler.alphas_cumprod.float().to(self.device)  # pyright: ignore[reportAttributeAccessIssue]

    def _load_unet(self) -> torch.nn.Module:
        from diffusers.models.unets.unet_2d_condition import UNet2DConditionModel

        unet = UNet2DConditionModel.from_pretrained(
            self._model_dir, subfolder="unet", variant="fp16", torch_dtype=self.dtype
        )
        processors: dict[str, Any] = dict(unet.attn_processors)
        for name, own in processors.items():
            if name.endswith(".attn1.processor") and not name.startswith(HIGHEST_RESOLUTION):
                attn = unet.get_submodule(name.removesuffix(".processor"))
                # The coherent call is plain self-attention: none of the extras a processor may have to apply.
                plain = attn.group_norm is None and attn.spatial_norm is None and attn.norm_q is None
                if not plain or attn.residual_connection or attn.rescale_output_factor != 1:
                    raise RuntimeError(f"{name} is not plain self-attention; Temporal Coherence cannot extend it")
                processors[name] = _CoherentSelfAttention(name, own, self._recorder)
        unet.set_attn_processor(processors)
        return unet.to(self.device, memory_format=torch.channels_last).eval()  # pyright: ignore[reportArgumentType]

    def unet_module(self) -> torch.nn.Module:
        """The UNet, reloaded from disk (a few seconds) if `release()` dropped it."""
        if self._unet is None:
            self._unet = self._load_unet()
        return self._unet

    def release(self) -> None:
        """Free the UNet's VRAM while another Backend generates; the text encoder and tiny VAE stay loaded."""
        self._unet = None
        torch.cuda.empty_cache()

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
        unet = self.unet_module()
        return unet(latents.to(self.dtype), timestep, encoder_hidden_states=prompt_embeds, return_dict=False)[0]

    @torch.inference_mode()
    def coherent_unet(
        self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor, previous: object | None
    ) -> tuple[torch.Tensor, KeysValues]:
        state = self._recorder
        state.recording, state.previous, state.current = True, previous if isinstance(previous, dict) else {}, {}
        try:
            eps = self.unet(latents, timestep, prompt_embeds)
        finally:
            state.recording, state.previous = False, {}
        return eps, state.current

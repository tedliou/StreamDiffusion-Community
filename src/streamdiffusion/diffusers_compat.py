try:
    from diffusers.models.autoencoders.autoencoder_tiny import AutoencoderTinyOutput
except ImportError:  # pragma: no cover - exercised on older diffusers releases
    from diffusers.models.autoencoder_tiny import AutoencoderTinyOutput

try:
    from diffusers.models.unets.unet_2d_condition import UNet2DConditionOutput
except ImportError:  # pragma: no cover - exercised on older diffusers releases
    from diffusers.models.unet_2d_condition import UNet2DConditionOutput

try:
    from diffusers.models.autoencoders.vae import DecoderOutput
except ImportError:  # pragma: no cover - exercised on older diffusers releases
    from diffusers.models.vae import DecoderOutput


__all__ = [
    "AutoencoderTinyOutput",
    "DecoderOutput",
    "UNet2DConditionOutput",
]

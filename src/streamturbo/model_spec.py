"""Model Spec: which weights a model needs, at which revision, and what it supports."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Weights:
    repo_id: str
    revision: str  # a pinned commit, never a branch
    files: tuple[str, ...]  # allow-patterns: only what the Runtime loads is downloaded


@dataclass(frozen=True)
class ModelSpec:
    name: str
    model: Weights
    tiny_vae: Weights
    min_side: int = 256
    max_side: int = 1024
    side_step: int = 64


SD_TURBO = ModelSpec(
    name="sd-turbo",
    model=Weights(
        repo_id="stabilityai/sd-turbo",
        revision="b261bac6fd2cf515557d5d0707481eafa0485ec2",
        files=(
            "model_index.json",
            "scheduler/scheduler_config.json",
            "tokenizer/*",
            "text_encoder/config.json",
            "text_encoder/model.fp16.safetensors",
            "unet/config.json",
            "unet/diffusion_pytorch_model.fp16.safetensors",
        ),
    ),
    tiny_vae=Weights(
        repo_id="madebyollin/taesd",
        revision="614f76814bbe30edbe2e627ace1c2234c81a2c0e",
        files=("config.json", "diffusion_pytorch_model.safetensors"),
    ),
)

# The Glass Preset: the default Settings (spec #2).
GLASS_PROMPT = (
    "transparent translucent glass-like refraction sharp flower jellyfish scales claw petal leaf tail tree ,"
    "slime mold, Vibrant, glossy highlights, ethereal glow, masterpiece, 8k, best quality, high resolution, "
    "hdr, bloom"
)
GLASS_STRENGTH = 0.68
GLASS_SIZE = (1024, 768)

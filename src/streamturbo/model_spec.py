"""Model Spec: which weights a model needs, at which revision, and what it supports."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Weights:
    repo_id: str
    revision: str  # a pinned commit, never a branch
    files: tuple[str, ...]  # allow-patterns: only what the Runtime loads is downloaded


@dataclass(frozen=True)
class PinnedFile:
    """A single weights file outside Hugging Face, checked against its SHA-256 before use."""

    url: str
    sha256: str
    name: str


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

# The Upscaler: Real-ESRGAN realesr-animevideov3, BSD-3-Clause (spec #19).
UPSCALER = PinnedFile(
    url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth",
    sha256="b8a8376811077954d82ca3fcf476f1ac3da3e8a68a4f4d71363008000a18b75d",
    name="realesr-animevideov3.pth",
)

# The Glass Preset: the default Settings (spec #2).
GLASS_PROMPT = (
    "transparent translucent glass-like refraction sharp flower jellyfish scales claw petal leaf tail tree ,"
    "slime mold, Vibrant, glossy highlights, ethereal glow, masterpiece, 8k, best quality, high resolution, "
    "hdr, bloom"
)
GLASS_STRENGTH = 0.68
GLASS_SIZE = (1024, 768)  # Generation and Output Resolution, picked from the M3 bench matrix (ticket #7)

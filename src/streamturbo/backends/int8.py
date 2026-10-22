"""INT8 UNet, an M3 benchmark option: post-training quantisation with NVIDIA ModelOpt (the `int8` dependency group).

A strongly typed network takes no implicit INT8 calibration, so ModelOpt calibrates on Glass-like inputs and the
export carries Q/DQ nodes; TensorRT then picks INT8 kernels for the quantised layers and keeps the rest in FP16.
"""

import copy
from pathlib import Path

import torch

from streamturbo.backends.pytorch import PyTorchBackend
from streamturbo.generation import timestep_for
from streamturbo.model_spec import GLASS_PROMPT, ModelSpec
from streamturbo.testframe import synthetic_frame

CALIBRATION_PROMPTS = (
    GLASS_PROMPT,
    "a watercolor painting of a forest at dawn",
    "neon city street at night, rain, reflections",
    "macro photograph of coral and jellyfish, bioluminescent",
)
CALIBRATION_STRENGTHS = (0.4, 0.55, 0.68, 0.85)
CALIBRATION_SIZES = ((1024, 768), (768, 576))
# Layers whose quantisation costs visible quality for little speed: the first and last convolutions and the
# timestep embedding.
UNQUANTISED = ("*conv_in*", "*conv_out*", "*time_embedding*", "*time_emb_proj*")


def export_quantized_unet(backend: PyTorchBackend, spec: ModelSpec, path: Path) -> None:
    import modelopt.torch.quantization as mtq  # pyright: ignore[reportMissingImports]  # the optional int8 group

    from streamturbo.backends.tensorrt import export_onnx

    unet = copy.deepcopy(backend.unet_module())  # quantisation rewrites the module; the fallback stays FP16
    config = copy.deepcopy(mtq.INT8_DEFAULT_CFG)
    # An ordered list of rules where later ones win (ModelOpt 0.47).
    config["quant_cfg"] += [{"quantizer_name": pattern, "enable": False} for pattern in UNQUANTISED]
    alphas = backend.alphas_cumprod
    embeds = [backend.encode_prompt(prompt) for prompt in CALIBRATION_PROMPTS]
    generator = torch.Generator(backend.device).manual_seed(0)

    @torch.inference_mode()
    def calibrate(model: torch.nn.Module) -> None:
        for width, height in CALIBRATION_SIZES:
            picture = synthetic_frame(width, height)[..., :3].permute(2, 0, 1).unsqueeze(0).to(backend.device)
            clean = backend.encode(picture.float() / 127.5 - 1).float()
            for prompt_embeds in embeds:
                for strength in CALIBRATION_STRENGTHS:
                    t = timestep_for(strength)
                    noise = torch.randn(clean.shape, generator=generator, device=backend.device)
                    noisy = alphas[t].sqrt() * clean + (1 - alphas[t]).sqrt() * noise
                    timestep = torch.tensor([t], device=backend.device)
                    model(noisy.to(backend.dtype), timestep, encoder_hidden_states=prompt_embeds, return_dict=False)

    mtq.quantize(unet, config, forward_loop=calibrate)
    # Tracing ModelOpt's quantisers on a CUDA device crashes the process on Windows (ModelOpt 0.47, torch 2.14),
    # so the calibrated copy is exported on the CPU, still in FP16.
    unet.cpu()
    torch.cuda.empty_cache()
    quantised = copy.copy(backend)
    quantised.unet_module = lambda: unet
    quantised.device = torch.device("cpu")
    export_onnx(quantised, "unet", spec, path, "int8")  # the quantised copy is freed on return

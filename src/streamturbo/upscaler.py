"""The Upscaler: Real-ESRGAN's compact super-resolution network, re-implemented (spec #19).

The architecture is SRVGGNetCompact from Real-ESRGAN (https://github.com/xinntao/Real-ESRGAN, BSD-3-Clause),
with the realesr-animevideov3 configuration: 16 convolutions of 64 features, 4x pixel shuffle.
"""

from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn

FACTOR = 4
_FEATURES, _CONVOLUTIONS = 64, 16


class Upscaler(nn.Module):
    """(1, 3, H, W) in [-1, 1] -> (1, 3, 4H, 4W) in [-1, 1]; the network itself works in [0, 1]."""

    def __init__(self) -> None:
        super().__init__()
        body: list[nn.Module] = [nn.Conv2d(3, _FEATURES, 3, 1, 1), nn.PReLU(_FEATURES)]
        for _ in range(_CONVOLUTIONS):
            body += [nn.Conv2d(_FEATURES, _FEATURES, 3, 1, 1), nn.PReLU(_FEATURES)]
        body.append(nn.Conv2d(_FEATURES, 3 * FACTOR * FACTOR, 3, 1, 1))
        self.body = nn.Sequential(*body)
        self.upsampler = nn.PixelShuffle(FACTOR)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        x = (image + 1) / 2
        out = self.upsampler(self.body(x)) + F.interpolate(x, scale_factor=FACTOR, mode="nearest")
        return out * 2 - 1


def load(weights: Path, device: torch.device, dtype: torch.dtype) -> Upscaler:
    state = torch.load(weights, map_location="cpu", weights_only=True)
    state = state.get("params_ema", state.get("params", state))
    upscaler = Upscaler()
    upscaler.load_state_dict(state)  # the release names its layers body.0 ... body.33, as this Sequential does
    return upscaler.to(device, dtype).eval()

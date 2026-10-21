"""Pixel conversion, Fit Mode and scaling, all as tensor ops on the Generation device."""

import torch
import torch.nn.functional as F

from streamturbo.frames import PixelFormat
from streamturbo.settings import FitMode

# BT.709 limited range (16-235 luma, 16-240 chroma).
_Y_SCALE = 255 / 219
_C_SCALE = 255 / 224
_KR, _KB = 0.2126, 0.0722
_KG = 1 - _KR - _KB


def to_rgb(raw: torch.Tensor, width: int, height: int, row_bytes: int, fmt: PixelFormat) -> torch.Tensor:
    """Raw frame bytes on the device -> float RGB in [0, 1], shape (1, 3, H, W)."""
    rows = raw[: height * row_bytes].view(height, row_bytes)[:, : width * fmt.bytes_per_pixel]
    if fmt is PixelFormat.UYVY:
        return _uyvy_to_rgb(rows.view(height, width // 2, 4).float())
    pixels = rows.view(height, width, 4)
    channels = (2, 1, 0) if fmt in (PixelFormat.BGRA, PixelFormat.BGRX) else (0, 1, 2)
    return pixels[..., channels].permute(2, 0, 1).unsqueeze(0).float() / 255


def _uyvy_to_rgb(quads: torch.Tensor) -> torch.Tensor:
    u, y0, v, y1 = quads.unbind(-1)
    y = torch.stack((y0, y1), dim=-1).flatten(-2)
    cb = ((u - 128) * _C_SCALE / 255).repeat_interleave(2, dim=-1)
    cr = ((v - 128) * _C_SCALE / 255).repeat_interleave(2, dim=-1)
    y = (y - 16) * _Y_SCALE / 255
    r = y + 2 * (1 - _KR) * cr
    b = y + 2 * (1 - _KB) * cb
    g = (y - _KR * r - _KB * b) / _KG
    return torch.stack((r, g, b)).unsqueeze(0).clamp(0, 1)


def fit(image: torch.Tensor, width: int, height: int, mode: FitMode) -> torch.Tensor:
    """Map an image onto width x height: fill crops, fit letterboxes, stretch distorts."""
    _, _, src_h, src_w = image.shape
    if (src_w, src_h) == (width, height):
        return image
    if mode == "stretch":
        return _resize(image, width, height)
    scale = max(width / src_w, height / src_h) if mode == "fill" else min(width / src_w, height / src_h)
    scaled_w, scaled_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    scaled = _resize(image, scaled_w, scaled_h)
    if mode == "fill":
        top, left = (scaled_h - height) // 2, (scaled_w - width) // 2
        return scaled[:, :, top : top + height, left : left + width]
    canvas = image.new_zeros(1, 3, height, width)
    top, left = (height - scaled_h) // 2, (width - scaled_w) // 2
    canvas[:, :, top : top + scaled_h, left : left + scaled_w] = scaled
    return canvas


def _resize(image: torch.Tensor, width: int, height: int) -> torch.Tensor:
    downscale = width < image.shape[-1] or height < image.shape[-2]
    return F.interpolate(image, size=(height, width), mode="bicubic", antialias=downscale, align_corners=False)


def to_bytes(image: torch.Tensor, width: int, height: int, fmt: PixelFormat) -> torch.Tensor:
    """Float RGB in [0, 1], shape (1, 3, h, w) -> packed bytes of width x height in `fmt`, flattened."""
    if image.shape[-2:] != (height, width):
        image = _resize(image, width, height)
    rgb = image[0].clamp(0, 1)
    if fmt is PixelFormat.UYVY:
        return _rgb_to_uyvy(rgb).flatten()
    channels = (2, 1, 0) if fmt in (PixelFormat.BGRA, PixelFormat.BGRX) else (0, 1, 2)
    alpha = torch.ones_like(rgb[:1])
    packed = torch.cat((rgb[list(channels)], alpha)).permute(1, 2, 0)
    return (packed * 255).round().to(torch.uint8).flatten()


def _rgb_to_uyvy(rgb: torch.Tensor) -> torch.Tensor:
    r, g, b = rgb
    y = _KR * r + _KG * g + _KB * b
    cb = (b - y) / (2 * (1 - _KB))
    cr = (r - y) / (2 * (1 - _KR))
    # 4:2:2: average each horizontal pixel pair's chroma.
    cb = cb.unflatten(-1, (-1, 2)).mean(-1)
    cr = cr.unflatten(-1, (-1, 2)).mean(-1)
    y = 16 + y * 219
    u = 128 + cb * 224
    v = 128 + cr * 224
    y0, y1 = y.unflatten(-1, (-1, 2)).unbind(-1)
    quads = torch.stack((u, y0, v, y1), dim=-1)
    return quads.round().clamp(0, 255).to(torch.uint8)

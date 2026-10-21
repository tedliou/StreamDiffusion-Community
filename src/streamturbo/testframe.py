"""A deterministic synthetic Input Frame for `bench` and tests, so no image asset has to ship."""

import torch


def synthetic_frame(width: int, height: int) -> torch.Tensor:
    """(H, W, 4) uint8 RGBA: soft-edged discs over a colour gradient."""
    y, x = torch.meshgrid(torch.linspace(0, 1, height), torch.linspace(0, 1, width), indexing="ij")
    rgb = torch.stack((x, y, 1 - x * y))
    aspect = height / width
    discs = ((0.30, 0.40, 0.18, (1.0, 0.5, 0.2)), (0.70, 0.60, 0.25, (0.2, 0.8, 1.0)), (0.50, 0.20, 0.10, (1, 1, 1)))
    for cx, cy, radius, colour in discs:
        distance = ((x - cx) ** 2 + ((y - cy) * aspect) ** 2).sqrt()
        mask = ((radius - distance) / 0.01).clamp(0, 1)
        rgb = rgb * (1 - mask) + torch.tensor(colour).view(3, 1, 1) * mask
    alpha = torch.ones(1, height, width)
    return (torch.cat((rgb, alpha)) * 255).round().to(torch.uint8).permute(1, 2, 0).contiguous()

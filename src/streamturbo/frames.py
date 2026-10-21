"""Input and Output Frames as they cross the Transport boundary."""

from dataclasses import dataclass
from enum import StrEnum

import torch


class PixelFormat(StrEnum):
    UYVY = "uyvy"  # 4:2:2 BT.709 limited range, 2 bytes per pixel
    BGRA = "bgra"
    BGRX = "bgrx"
    RGBA = "rgba"
    RGBX = "rgbx"

    @property
    def bytes_per_pixel(self) -> int:
        return 2 if self is PixelFormat.UYVY else 4


@dataclass(frozen=True)
class InputFrame:
    """One picture from a Source: raw uint8 bytes, `height` rows of `stride` bytes."""

    data: torch.Tensor
    width: int
    height: int
    format: PixelFormat
    stride: int = 0  # 0: tightly packed

    @property
    def row_bytes(self) -> int:
        return self.stride or self.width * self.format.bytes_per_pixel


@dataclass(frozen=True)
class OutputFrame:
    """One picture for a Sink: tightly packed uint8 bytes in host memory."""

    data: torch.Tensor
    width: int
    height: int
    format: PixelFormat
    input_seq: int  # which Input Frame it was generated from; -1 without a Source
    settings_version: int  # which Settings snapshot generated it


def host_buffer(nbytes: int) -> torch.Tensor:
    """A host byte buffer, page-locked when CUDA is present so uploads can be asynchronous.

    Torch's caching host allocator recycles it only after pending copies finish, so each frame
    can take a fresh buffer without racing the GPU.
    """
    return torch.empty(nbytes, dtype=torch.uint8, pin_memory=torch.cuda.is_available())

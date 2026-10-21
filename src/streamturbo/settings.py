"""Settings: the one validated description of what the Runtime does (ADR-0008).

M1 reads them from a TOML file at start-up; only Prompt, Strength and Seed change while running.
"""

import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from streamturbo.model_spec import GLASS_PROMPT, GLASS_SIZE, GLASS_STRENGTH, SD_TURBO

FitMode = Literal["fill", "fit", "stretch"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Resolution(_Model):
    width: int = Field(gt=0, le=4096)
    height: int = Field(gt=0, le=4096)


class SourceSettings(_Model):
    transport: Literal["ndi", "spout", "none"] = "ndi"
    name: str = ""  # empty: the first visible sender


class SinkSettings(_Model):
    transport: Literal["ndi", "spout"] = "ndi"
    name: str = "StreamTurbo"
    fps: float = Field(default=30.0, gt=0, le=240)  # declared NDI frame rate


class Settings(_Model):
    source: SourceSettings = SourceSettings()
    sink: SinkSettings = SinkSettings()
    generation: Resolution = Resolution(width=GLASS_SIZE[0], height=GLASS_SIZE[1])
    output: Resolution = Resolution(width=GLASS_SIZE[0], height=GLASS_SIZE[1])
    fit_mode: FitMode = "fill"
    prompt: str = GLASS_PROMPT
    strength: float = Field(default=GLASS_STRENGTH, ge=0.0, le=1.0)
    seed: int = Field(default=2, ge=0, lt=2**63)

    @model_validator(mode="after")
    def _generation_fits_model(self) -> Self:
        SD_TURBO.check_resolution(self.generation.width, self.generation.height)
        return self

    @classmethod
    def load(cls, path: Path) -> Self:
        with path.open("rb") as file:
            return cls.model_validate(tomllib.load(file))


# Settings that apply to the next Output Frame without interrupting output.
LIVE_FIELDS = frozenset({"prompt", "strength", "seed"})

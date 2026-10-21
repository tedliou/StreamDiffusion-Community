"""Settings: the one validated description of what the Runtime does (ADR-0008).

Every leaf field carries its class: Live applies on the next Output Frame, Reset briefly pauses output while
buffers or Transports are rebuilt, Rebuild needs a new Engine.
"""

import tomllib
import typing
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

import annotated_types
from pydantic import BaseModel, ConfigDict, Field

from streamturbo.model_spec import GLASS_PROMPT, GLASS_SIZE, GLASS_STRENGTH, SD_TURBO

FitMode = Literal["fill", "fit", "stretch"]
SettingClass = Literal["live", "reset", "rebuild"]


def _setting(kind: SettingClass, default: Any, **constraints: Any) -> Any:
    return Field(default=default, json_schema_extra={"class": kind}, **constraints)


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GenerationResolution(_Model):
    width: int = _setting(
        "reset", GLASS_SIZE[0], ge=SD_TURBO.min_side, le=SD_TURBO.max_side, multiple_of=SD_TURBO.side_step
    )
    height: int = _setting(
        "reset", GLASS_SIZE[1], ge=SD_TURBO.min_side, le=SD_TURBO.max_side, multiple_of=SD_TURBO.side_step
    )


class OutputResolution(_Model):
    width: int = _setting("reset", GLASS_SIZE[0], ge=16, le=4096, multiple_of=2)  # UYVY packs pixel pairs
    height: int = _setting("reset", GLASS_SIZE[1], ge=16, le=4096)


class SourceSettings(_Model):
    transport: Literal["ndi", "spout", "none"] = _setting("reset", "ndi")
    name: str = _setting("reset", "")  # empty: the first visible sender


class SinkSettings(_Model):
    transport: Literal["ndi", "spout"] = _setting("reset", "ndi")
    name: str = _setting("reset", "StreamTurbo")
    fps: float = _setting("reset", 30.0, gt=0, le=240)  # declared NDI frame rate


class Settings(_Model):
    source: SourceSettings = SourceSettings()
    sink: SinkSettings = SinkSettings()
    generation: GenerationResolution = GenerationResolution()
    output: OutputResolution = OutputResolution()
    fit_mode: FitMode = _setting("reset", "fill")
    prompt: str = _setting("live", GLASS_PROMPT, max_length=2000)
    strength: float = _setting("live", GLASS_STRENGTH, ge=0.0, le=1.0)
    seed: int = _setting("live", 2, ge=0, lt=2**31)  # OSC integers are 32-bit

    @classmethod
    def load(cls, path: Path) -> Self:
        with path.open("rb") as file:
            return cls.model_validate(tomllib.load(file))

    def merged(self, changes: Mapping[str, Any]) -> Self:
        """These Settings with a partial, possibly nested, update applied and validated."""
        return self.model_validate(_deep_merge(self.model_dump(), changes))

    def leaves(self) -> dict[str, Any]:
        """Every leaf value by its dotted path, e.g. `generation.width`."""
        return _flatten(self.model_dump())


def _deep_merge(base: dict[str, Any], changes: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in changes.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)  # pyright: ignore[reportArgumentType]
        else:
            merged[key] = value
    return merged


def _flatten(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, dict):
            flat |= _flatten(value, f"{prefix}{key}.")  # pyright: ignore[reportArgumentType]
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def nested(path: str, value: Any) -> dict[str, Any]:
    """A partial update setting one dotted path, e.g. `nested("source.name", "x")`."""
    head, _, rest = path.partition(".")
    return {head: nested(rest, value) if rest else value}


def describe() -> list[dict[str, Any]]:
    """Every leaf Setting with its class, type and bounds: what a Control Surface needs to build a control."""
    return _describe(Settings, "")


def _describe(model: type[BaseModel], prefix: str) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for name, info in model.model_fields.items():
        path, annotation = f"{prefix}{name}", info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            fields += _describe(annotation, f"{path}.")
            continue
        extra = info.json_schema_extra
        assert isinstance(extra, dict), f"{path} has no Setting class"
        field: dict[str, Any] = {"path": path, "class": extra["class"], "default": info.default}
        if typing.get_origin(annotation) is Literal:
            field |= {"type": "enum", "options": list(typing.get_args(annotation))}
        else:
            field["type"] = {int: "integer", float: "number", str: "string"}[annotation]  # pyright: ignore[reportArgumentType]
        for constraint in info.metadata:
            match constraint:
                case annotated_types.Ge(ge=bound) | annotated_types.Gt(gt=bound):
                    field["minimum"] = bound
                case annotated_types.Le(le=bound) | annotated_types.Lt(lt=bound):
                    field["maximum"] = bound
                case annotated_types.MultipleOf(multiple_of=step):
                    field["step"] = step
                case annotated_types.MaxLen(max_length=length):
                    field["max_length"] = length
        fields.append(field)
    return fields

"""Settings: the one validated description of what the Runtime does (ADR-0008).

Every leaf field carries its class: Live applies on the next Output Frame, Reset briefly pauses output while
buffers or Transports are rebuilt, Rebuild needs a new Engine.
"""

import json
import tomllib
import typing
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import annotated_types
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from streamturbo.model_spec import GLASS_PROMPT, GLASS_SIZE, GLASS_STRENGTH, SD_TURBO

FitMode = Literal["fill", "fit", "stretch"]
BackendChoice = Literal["auto", "pytorch"]  # auto: TensorRT once its Engines are built, PyTorch until then
SettingClass = Literal["live", "reset", "rebuild"]


# A float a control moves in steps of 0.01; pydantic's multiple_of would reject 0.29 over rounding error.
Hundredths = Annotated[float, AfterValidator(lambda value: round(value, 2))]


def _setting(kind: SettingClass, default: Any, *, step: float | None = None, **constraints: Any) -> Any:
    """A leaf Setting. `step` is the increment a control moves in, for a Hundredths field."""
    extra: dict[str, Any] = {"class": kind} | ({"step": step} if step is not None else {})
    return Field(default=default, json_schema_extra=extra, **constraints)


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


class SimilarFrameSkip(_Model):
    # Mean absolute difference (0-1) between downsampled Input Frames below which the last Output Frame is
    # repeated instead of generating; 0 turns Similar Frame Skip off.
    threshold: float = _setting("live", 0.0, ge=0.0, le=1.0)
    max_skips: int = _setting("live", 30, ge=1, le=10000)  # then one Generation, so slow changes still appear


class WeightedPrompt(_Model):
    """One Prompt in a Prompt Blend; its weight counts relative to the total of all weights."""

    text: str = _setting("live", "", max_length=2000)
    weight: Hundredths = _setting("live", 1.0, ge=0.0, le=10.0, step=0.01)


class Settings(_Model):
    source: SourceSettings = SourceSettings()
    sink: SinkSettings = SinkSettings()
    generation: GenerationResolution = GenerationResolution()
    output: OutputResolution = OutputResolution()
    fit_mode: FitMode = _setting("reset", "fill")
    prompts: list[WeightedPrompt] = _setting("live", [WeightedPrompt(text=GLASS_PROMPT)], min_length=1)
    strength: Hundredths = _setting("live", GLASS_STRENGTH, ge=0.0, le=1.0, step=0.01)
    strength_glide: float = _setting("live", 0.25, ge=0.0, le=10.0)  # seconds to reach a new Strength; 0 jumps
    prompt_transition: float = _setting("live", 1.0, ge=0.0, le=30.0)  # seconds to blend into a new Prompt Blend
    seed: int = _setting("live", 2, ge=0, lt=2**31)  # OSC integers are 32-bit
    # How much of the previous Generation each new one keeps, 0-0.95; 0 turns Temporal Smoothing off.
    temporal_smoothing: float = _setting("live", 0.2, ge=0.0, le=0.95)  # 0.2: no visible trail behind a fast pan
    # Each Generation also attends to the previous one's features, so detail stays in place between Output Frames.
    temporal_coherence: bool = _setting("live", True)
    similar_frame_skip: SimilarFrameSkip = SimilarFrameSkip()
    backend: BackendChoice = _setting("rebuild", "auto")

    @model_validator(mode="before")
    @classmethod
    def _single_prompt(cls, values: Any) -> Any:
        """`prompt = "..."` (older Presets, `/streamturbo/prompt`) is a Prompt Blend of that Prompt alone."""
        if isinstance(values, Mapping) and "prompt" in values:
            values = dict(values)
            values["prompts"] = [{"text": values.pop("prompt"), "weight": 1.0}]
        return values

    @field_validator("prompts", mode="before")
    @classmethod
    def _prompts_from_json(cls, value: Any) -> Any:
        """A whole Prompt Blend as one JSON string, for Control Surfaces that send only scalars (OSC)."""
        return json.loads(value) if isinstance(value, str) else value

    @field_validator("prompts")
    @classmethod
    def _some_weight(cls, value: list[WeightedPrompt]) -> list[WeightedPrompt]:
        if not any(prompt.weight > 0 for prompt in value):
            raise ValueError("at least one Prompt needs a weight above 0")
        return value

    @classmethod
    def load(cls, path: Path) -> Self:
        with path.open("rb") as file:
            return cls.model_validate(tomllib.load(file))

    def merged(self, changes: Mapping[str, Any]) -> Self:
        """These Settings with a partial, possibly nested, update applied and validated."""
        return self.model_validate(_deep_merge(self.model_dump(), changes))


def _deep_merge(base: dict[str, Any], changes: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in changes.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)  # pyright: ignore[reportArgumentType]
        elif isinstance(value, Mapping) and isinstance(merged.get(key), list):
            merged[key] = _merge_items(key, merged[key], value)
        else:
            merged[key] = value
    return merged


def _merge_items(key: str, items: list[Any], changes: Mapping[Any, Any]) -> list[Any]:
    """Changes to a list by index, e.g. `{"1": {"text": "x"}}` from `prompts/1/text`; the next index appends."""
    merged = list(items)
    try:
        indexed = sorted((int(index), change) for index, change in changes.items())
    except ValueError:
        raise ValueError(f"{key}: items are changed by index, e.g. {key}/0") from None
    for index, change in indexed:
        if index == len(merged):
            merged.append({})
        elif not 0 <= index < len(merged):
            raise ValueError(f"{key}: there is no item {index}; the next new one is {len(merged)}")
        is_item = isinstance(change, Mapping) and isinstance(merged[index], dict)
        merged[index] = _deep_merge(merged[index], change) if is_item else change
    return merged


def nested(path: str, value: Any) -> dict[str, Any]:
    """A partial update setting one dotted path, e.g. `nested("source.name", "x")`."""
    head, _, rest = path.partition(".")
    return {head: nested(rest, value) if rest else value}


def describe() -> list[dict[str, Any]]:
    """Every leaf Setting with its class, type and bounds: what a Control Surface needs to build a control.

    A list Setting (the Prompt Blend) is one entry of type "list" whose `items` describe one item's fields.
    """
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
        is_list = typing.get_origin(annotation) is list
        if is_list:
            (item,) = typing.get_args(annotation)
            items = [value.model_dump() for value in info.default]
            field |= {"type": "list", "default": items, "items": _describe(item, "")}
        elif typing.get_origin(annotation) is Literal:
            field |= {"type": "enum", "options": list(typing.get_args(annotation))}
        else:
            field["type"] = {bool: "boolean", int: "integer", float: "number", str: "string"}[annotation]  # pyright: ignore[reportArgumentType]
        for constraint in info.metadata:
            match constraint:
                case annotated_types.Ge(ge=bound) | annotated_types.Gt(gt=bound):
                    field["minimum"] = bound
                case annotated_types.Le(le=bound) | annotated_types.Lt(lt=bound):
                    field["maximum"] = bound
                case annotated_types.MultipleOf(multiple_of=step):
                    field["step"] = step
                case annotated_types.MinLen(min_length=length) if is_list:
                    field["min_items"] = length
                case annotated_types.MaxLen(max_length=length):
                    field["max_items" if is_list else "max_length"] = length
        if "step" in extra:
            field["step"] = extra["step"]
        fields.append(field)
    return fields

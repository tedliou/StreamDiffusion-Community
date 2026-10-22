"""Presets: named, saved looks as readable TOML files, and the last-used Settings.

A Preset holds every Setting except the Source and Sink, which belong to the machine rather than to the look,
so recalling a Preset never disconnects TouchDesigner. Bundled Presets ship with the package and are read-only;
the user's Presets live in the project's `presets` folder.
"""

import logging
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

from streamturbo.settings import Settings

log = logging.getLogger(__name__)

BUNDLED_DIR = Path(__file__).parent / "bundled_presets"
# Not part of a look: where frames come from and go to, and which Backend this machine runs.
MACHINE_FIELDS = ("source", "sink", "backend")
_NAME = re.compile(r"^[\w][\w .-]{0,63}$")


@dataclass(frozen=True)
class PresetInfo:
    name: str
    bundled: bool


class PresetError(ValueError):
    pass


class PresetStore:
    def __init__(self, folder: Path, bundled_dir: Path = BUNDLED_DIR) -> None:
        self.folder = folder
        self._bundled_dir = bundled_dir

    def list(self) -> list[PresetInfo]:
        bundled = {path.stem: PresetInfo(path.stem, True) for path in self._bundled_dir.glob("*.toml")}
        own = {path.stem: PresetInfo(path.stem, False) for path in self.folder.glob("*.toml")}
        return sorted((bundled | own).values(), key=lambda info: info.name.casefold())

    def load(self, name: str) -> dict[str, Any]:
        """The Preset's Settings as a partial update; validated against the defaults."""
        path = self._find(name)
        try:
            with path.open("rb") as file:
                values = tomllib.load(file)
            if any(field in values for field in MACHINE_FIELDS):
                raise PresetError(f"Preset {name!r} must not contain {', '.join(MACHINE_FIELDS)}")
            Settings().merged(values)
        except (tomllib.TOMLDecodeError, ValueError) as error:
            raise PresetError(f"Preset {name!r} is invalid: {error}") from error
        return values

    def save(self, name: str, settings: Settings) -> None:
        self._check_name(name)
        if self._bundled(name) is not None:
            raise PresetError(f"{name!r} is a bundled Preset; save under another name")
        self.folder.mkdir(parents=True, exist_ok=True)
        look = settings.model_dump(exclude=set(MACHINE_FIELDS))
        (self.folder / f"{name}.toml").write_text(tomli_w.dumps(look), encoding="utf-8")

    def rename(self, name: str, new_name: str) -> None:
        self._check_name(new_name)
        path = self._own(name)
        if new_name.casefold() != name.casefold() and self._exists(new_name):
            raise PresetError(f"a Preset named {new_name!r} already exists")
        path.rename(self.folder / f"{new_name}.toml")

    def delete(self, name: str) -> None:
        self._own(name).unlink()

    def _find(self, name: str) -> Path:
        path = self._user(name) or self._bundled(name)
        if path is None:
            raise PresetError(f"no Preset named {name!r}")
        return path

    def _own(self, name: str) -> Path:
        if (path := self._user(name)) is None:
            if self._bundled(name) is not None:
                raise PresetError(f"{name!r} is a bundled Preset and cannot be changed")
            raise PresetError(f"no Preset named {name!r}")
        return path

    def _exists(self, name: str) -> bool:
        return self._user(name) is not None or self._bundled(name) is not None

    def _user(self, name: str) -> Path | None:
        return _match(self.folder, name)

    def _bundled(self, name: str) -> Path | None:
        return _match(self._bundled_dir, name)

    @staticmethod
    def _check_name(name: str) -> None:
        if not _NAME.match(name) or name.endswith((" ", ".")):
            raise PresetError("Preset names are 1-64 letters, digits, spaces, dots, dashes or underscores")


def _match(folder: Path, name: str) -> Path | None:
    """Preset names are case-insensitive, like the Windows file names they are stored in."""
    for path in folder.glob("*.toml"):
        if path.stem.casefold() == name.casefold():
            return path
    return None


def load_last(path: Path) -> Settings | None:
    """The last-used Settings, or None when there are none or they no longer validate."""
    if not path.is_file():
        return None
    try:
        return Settings.load(path)
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        log.warning("ignoring the last-used Settings in %s: %s", path, error)
        return None


def save_last(path: Path, settings: Settings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(tomli_w.dumps(settings.model_dump()), encoding="utf-8")
    temporary.replace(path)  # never leave a half-written file behind


def initial_settings(
    store: PresetStore, last_path: Path, settings_file: Path | None = None, preset: str | None = None
) -> Settings:
    """What the Runtime starts with: a Settings file, else the last-used Settings, else the defaults;
    then the chosen Preset's look on top."""
    settings = Settings.load(settings_file) if settings_file else (load_last(last_path) or Settings())
    return settings.merged(store.load(preset)) if preset else settings

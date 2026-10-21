"""Where StreamTurbo keeps its files: everything lives inside the project folder (ADR-0006)."""

import os
from pathlib import Path


def project_home() -> Path:
    """The clone StreamTurbo runs from, or `STREAMTURBO_HOME` when set."""
    if override := os.environ.get("STREAMTURBO_HOME"):
        return Path(override)
    clone = Path(__file__).resolve().parents[2]
    return clone if (clone / "pyproject.toml").is_file() else Path.cwd()


def models_dir() -> Path:
    return project_home() / "models"


def output_dir() -> Path:
    return project_home() / "output"


def presets_dir() -> Path:
    return project_home() / "presets"


def last_settings_path() -> Path:
    return project_home() / "last-settings.toml"

"""Downloads weights at their pinned revisions or hashes into the project's models folder."""

import hashlib
import urllib.request
from pathlib import Path

from streamturbo.model_spec import UPSCALER, ModelSpec, PinnedFile, Weights
from streamturbo.paths import models_dir


def fetch(weights: Weights, cache_dir: Path | None = None) -> Path:
    """Return the local snapshot folder, downloading missing files on first use."""
    from huggingface_hub import snapshot_download

    return Path(
        snapshot_download(
            repo_id=weights.repo_id,
            revision=weights.revision,
            allow_patterns=list(weights.files),
            cache_dir=cache_dir or models_dir() / "hf",
        )
    )


def fetch_file(pinned: PinnedFile, folder: Path | None = None) -> Path:
    """Return the local file, downloading it on first use; a file whose SHA-256 differs is never used."""
    path = (folder or models_dir() / "files") / pinned.name
    if path.is_file() and _sha256(path) == pinned.sha256:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".partial")
    urllib.request.urlretrieve(pinned.url, partial)
    if (actual := _sha256(partial)) != pinned.sha256:
        partial.unlink()
        raise ValueError(f"{pinned.url} has SHA-256 {actual}, expected {pinned.sha256}")
    partial.replace(path)
    return path


def _sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def fetch_all(spec: ModelSpec, cache_dir: Path | None = None) -> tuple[Path, Path, Path]:
    """Return the model and tiny VAE snapshot folders, and the Upscaler's weights file."""
    return fetch(spec.model, cache_dir), fetch(spec.tiny_vae, cache_dir), fetch_file(UPSCALER)

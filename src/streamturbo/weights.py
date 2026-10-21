"""Downloads Model Spec weights at their pinned revisions into the project's models folder."""

from pathlib import Path

from streamturbo.model_spec import ModelSpec, Weights
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


def fetch_all(spec: ModelSpec, cache_dir: Path | None = None) -> tuple[Path, Path]:
    """Return the (model, tiny VAE) snapshot folders."""
    return fetch(spec.model, cache_dir), fetch(spec.tiny_vae, cache_dir)

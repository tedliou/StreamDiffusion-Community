# StreamDiffusion

[English](./README.md) | [日本語](./README-ja.md) | [한국어](./README-ko.md)

## Overview

This repository is currently maintained as the core source workspace for the StreamDiffusion Python package.

The previous `demo/`, `examples/`, and package release automation have been removed for now so the project can stabilize around a single `uv`-managed development environment. Future refactors are expected to bring back heavier runtime pieces and broader distribution workflows in a cleaner shape.

## Current Scope

- Core Python package source under `src/streamdiffusion/`
- Root-level Docker workflow for the core workspace
- OpenSpec-driven collaboration and repository maintenance files

Not included in this phase:

- Bundled demos or examples
- PyPI/TestPyPI publishing
- A default environment that installs GPU-heavy runtime dependencies

## Requirements

- Linux or WSL2 with Ubuntu-compatible tooling
- Python 3.10+
- `uv`

If `uv` is not installed yet, Astral's installer works well on Ubuntu/WSL2:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setup

```bash
git clone https://github.com/cumulo-autumn/StreamDiffusion.git
cd StreamDiffusion
uv sync
uv run python -c "import streamdiffusion; print('streamdiffusion import OK')"
```

The baseline verification target for this repository is that `uv sync` completes and the package can be imported. This change intentionally does not promise a full inference-ready environment.

## Dependency Notes

- `torch` and `xformers` are not part of the default `uv sync` environment in this stabilization pass.
- Both packages remain required project dependencies for later refactors and must be added back to the main workflow.
- Optional extras remain defined in `pyproject.toml` for follow-up work, but they are not part of the baseline verification target here.

## Docker

The root Dockerfile follows the same lightweight setup path:

```bash
docker build -t streamdiffusion-core .
docker run --rm streamdiffusion-core
```

## Project Status

- This repository is currently developer-focused rather than end-user-focused.
- Release automation was intentionally removed from this phase.
- TensorRT and other acceleration-specific tooling still exist in the codebase, but their full setup flow is deferred until the larger runtime refactor.

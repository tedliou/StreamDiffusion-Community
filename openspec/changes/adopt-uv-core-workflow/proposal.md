## Why

The repository still mixes legacy `setup.py` and `pip` workflows with demo/example-specific dependency trees, release automation, and Docker paths that no longer match the desired project shape. We need to simplify the repository into a core source workspace that developers can initialize reliably with `uv sync` before larger refactors bring back heavier runtime dependencies and restored publishing flows.

## What Changes

- **BREAKING** Remove `demo/` and `examples/` from the repository so the project focuses on the core Python package and supporting development assets only.
- **BREAKING** Replace `setup.py`-driven packaging with a `pyproject.toml`-based project definition that `uv` can manage as the primary environment workflow.
- **BREAKING** Update repository documentation to describe the project as a core source repository, with `uv sync` as the expected setup path and with demo/example content explicitly deferred.
- **BREAKING** Remove the current GitHub release workflow and other packaging/release instructions that assume PyPI publishing is part of this change.
- Update the root Docker workflow so containerized setup uses the same `uv`-managed environment strategy as local development.
- Preserve a documented note that `torch` and `xformers` are temporarily excluded from the default synced environment but must return in a later refactor because they remain required for the project's future runtime goals.

## Capabilities

### New Capabilities
- `uv-managed-core-repository`: Define the repository as a core-only source workspace whose supported developer environment is created with `uv sync`.

### Modified Capabilities
- None.

## Impact

- Affected code and config: `pyproject.toml`, `setup.py`, root `Dockerfile`, `.github/workflows/release.yml`, root and translated READMEs, and repository layout under `demo/` and `examples/`.
- Affected workflows: local development setup, Docker-based setup, and release automation.
- Affected dependencies: package metadata moves into `pyproject.toml`; heavy GPU dependencies remain documented for later reintroduction rather than default environment sync in this change.

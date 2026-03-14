## Why

The repository still hard-pins several core and TensorRT-related dependencies to versions that are far behind the current PyPI releases, even though the `uv` lockfile already resolves other unconstrained packages to modern versions. This mismatch makes the supported environment harder to maintain, increases compatibility risk for contributors, and leaves the project with stale dependency baselines that are no longer aligned with the current Python ML ecosystem.

## What Changes

- Refresh the dependency baselines declared in `pyproject.toml` for the core package and optional TensorRT/dev extras.
- Regenerate `uv.lock` so the committed lockfile matches the updated dependency policy.
- Add targeted verification that catches stale pinned dependency baselines and keeps shared optional dependency groups aligned.
- Update repository guidance if setup or maintenance notes need to reflect the newer dependency baselines.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `uv-managed-core-repository`: update the supported `uv`-managed dependency baselines so the repository metadata and lockfile track current maintained versions for core and optional acceleration dependencies.

## Impact

- Affected files: `pyproject.toml`, `uv.lock`, dependency-focused tests, and related setup documentation if needed.
- Affected systems: `uv sync` / `uv run` workflows for core, dev, and TensorRT-oriented contributors.
- Risk areas: runtime compatibility with newer `diffusers`, `onnx`, `onnxruntime`, and `protobuf` releases; Linux and WSL2 setup expectations for optional acceleration paths.

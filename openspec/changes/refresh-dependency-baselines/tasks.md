## 1. Refresh dependency metadata

- [x] 1.1 Update the stale pinned dependency baselines in `pyproject.toml` for the core package and shared optional extras.
- [x] 1.2 Regenerate `uv.lock` so the lockfile matches the refreshed dependency policy.

## 2. Add maintenance safeguards

- [x] 2.1 Add a dependency-focused regression test that verifies the maintained pinned baselines in `pyproject.toml`.
- [x] 2.2 Add coverage that checks shared acceleration dependencies stay aligned between the `tensorrt` and `dev` extras.
- [x] 2.3 Update setup or maintenance documentation if the refreshed dependency policy changes contributor guidance.

## 3. Verify the change

- [x] 3.1 Run the targeted project verification commands for the dependency metadata and tests.
- [x] 3.2 Run `openspec validate refresh-dependency-baselines` and `openspec validate --specs`.

## 1. Reshape the repository scope

- [ ] 1.1 Remove `demo/` and `examples/` content and any root references that still treat them as supported repository components.
- [ ] 1.2 Remove the current GitHub release workflow and any publishing-oriented repository instructions that are out of scope for this stabilization change.

## 2. Migrate the Python project to uv-managed metadata

- [ ] 2.1 Move package metadata, dependency declarations, and build-system settings from `setup.py` into `pyproject.toml`.
- [ ] 2.2 Remove `setup.py` and update any remaining repository configuration that depends on legacy `pip`/`setup.py` development flows.
- [ ] 2.3 Keep the default synced environment intentionally lightweight while documenting that `torch` and `xformers` must return in a later refactor.

## 3. Align setup surfaces and verify the new baseline

- [ ] 3.1 Update the root Docker workflow to install `uv` and build the environment from the root `pyproject.toml`.
- [ ] 3.2 Rewrite the root and translated README files so they describe the repository as a core source workspace with `uv sync` as the supported setup path.
- [ ] 3.3 Verify the new baseline by running `uv sync` from the repository root and confirming the synchronized environment can import `streamdiffusion`.

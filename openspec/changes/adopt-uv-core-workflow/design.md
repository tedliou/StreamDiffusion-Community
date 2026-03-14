## Context

The repository currently combines core package code with demo applications, example scripts, release automation, and multiple `requirements.txt` files that assume a `pip`-first workflow. Package metadata still lives in `setup.py`, while `pyproject.toml` only carries linting configuration. This makes the environment story fragmented and difficult to stabilize before broader refactors.

The approved direction is to reduce the repository to a core source workspace and make `uv sync` the primary developer setup path. The change must also remove release-oriented automation for now and clearly document that heavy runtime dependencies such as `torch` and `xformers` are temporarily excluded from the default synced environment even though they remain future requirements.

## Goals / Non-Goals

**Goals:**
- Establish `pyproject.toml` as the single source of truth for project metadata and dependency management.
- Reduce the repository to core package assets by removing demo/example content and their dependency trees.
- Align local setup and Docker setup around `uv` so developers use one supported environment workflow.
- Document the temporary dependency posture clearly enough that future work can restore `torch` and `xformers` without ambiguity.
- Remove release workflow surface area that is out of scope for the current stabilization pass.

**Non-Goals:**
- Restoring or replacing the removed demo/example functionality.
- Reintroducing PyPI/TestPyPI publishing in this change.
- Making TensorRT or other GPU-specific install helpers `uv`-native.
- Guaranteeing inference execution or end-to-end runtime validation beyond successful environment synchronization.

## Decisions

### Use a single `pyproject.toml`-based project definition

The project metadata, runtime dependencies, optional dependencies, and build backend configuration will move into `pyproject.toml`, and `setup.py` will be removed. This eliminates split packaging definitions and matches `uv`'s default workflow.

Alternative considered: keep `setup.py` and add only `uv` documentation. That would reduce immediate work but preserve the same ambiguity that caused the cleanup request.

### Trim the repository to core-source scope

`demo/` and `examples/` will be removed entirely instead of being left as deprecated or unsupported directories. Their presence currently implies supported workflows, introduces extra dependency files, and creates maintenance noise that conflicts with the core-repository goal.

Alternative considered: keep the directories but stop documenting them. That would leave dead weight in the tree and make the repository boundary less obvious.

### Keep default environment sync intentionally light

The default `uv sync` environment will not pull in `torch` or `xformers` during this stabilization pass. The design favors a reproducible baseline environment over preserving full runtime capability in the initial migration. Documentation will explicitly state that both packages must return in a later refactor because they remain necessary for the project's intended future operation.

Alternative considered: keep GPU-heavy dependencies in the default environment. That would preserve more runtime behavior but would make the "clean sync" goal harder to achieve and more sensitive to platform-specific breakage.

### Remove release automation instead of partially modernizing it

The existing release workflow will be deleted rather than rewritten around `uv build`. Publishing is explicitly out of scope, and a partial modernization would add maintenance without supporting the immediate stabilization objective.

Alternative considered: modernize the workflow now and leave it dormant. That would still require package publishing decisions the user chose to defer.

### Align Docker with the same environment source

The root Docker image will install `uv` and synchronize the project from `pyproject.toml`, using the same source of truth as local development. Demo-specific Dockerfiles will be removed alongside their directories.

Alternative considered: leave Docker on `pip` while local development moves to `uv`. That would create two supported environment paths and undermine the cleanup.

## Risks / Trade-offs

- [Repository no longer includes runnable demos/examples] -> Mitigation: document the repository as a core source workspace and state that demo content is intentionally deferred until later restructuring.
- [Removing heavy dependencies from default sync may confuse future contributors] -> Mitigation: call out `torch` and `xformers` explicitly in README and project metadata comments as planned follow-up dependencies, not accidental omissions.
- [Legacy helper scripts still invoke `pip`] -> Mitigation: keep those GPU-specific helper paths out of the `uv sync` success criteria for this change and avoid broad refactors outside the approved scope.
- [Metadata migration from `setup.py` to `pyproject.toml` may miss packaging details] -> Mitigation: preserve the existing package discovery, optional dependency groupings, and Python version requirement when translating the configuration.

## Migration Plan

1. Move package metadata and dependency declarations into `pyproject.toml`.
2. Remove `setup.py`, `demo/`, `examples/`, and the release workflow.
3. Update root Docker and README files to use `uv` and describe the core-only repository scope.
4. Verify the repository can initialize with `uv sync` and that the package remains importable with the synced environment.

Rollback is straightforward because the change is confined to repository layout and configuration files; reverting the commit restores the prior structure and workflows.

## Open Questions

No blocking open questions remain for proposal scope. Future follow-up work will need to decide how `torch`, `xformers`, and removed demo assets return after the larger refactor.

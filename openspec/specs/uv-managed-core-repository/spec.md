# uv-managed-core-repository Specification

## Purpose
Define the repository as a core-only StreamDiffusion source workspace that uses `uv` for the supported development environment, while documenting the temporary exclusion of heavy runtime dependencies and the removal of publishing workflows.
## Requirements
### Requirement: Repository exposes a core-only source workspace
The repository SHALL define itself as a core source workspace and MUST exclude bundled demo and example application directories from the supported project layout for this change.

#### Scenario: Repository tree is trimmed to core assets
- **WHEN** a contributor inspects the repository after the change
- **THEN** the root project layout excludes `demo/` and `examples/`
- **AND** the remaining top-level assets focus on the core package, repository tooling, and supporting documentation

### Requirement: Developer environment sync uses uv-managed project metadata
The repository SHALL provide a `pyproject.toml` project definition that `uv sync` can use as the supported developer environment setup path.

#### Scenario: Contributor initializes the repository environment
- **WHEN** a contributor runs `uv sync` from the repository root on a supported Linux or WSL2 environment
- **THEN** dependency resolution and environment synchronization complete using project metadata defined in `pyproject.toml`
- **AND** the workflow does not depend on `setup.py develop` or README instructions centered on `pip install`

### Requirement: Deferred heavy runtime dependencies are documented explicitly
The repository SHALL document that `torch` and `xformers` are temporarily excluded from the default synced environment in this change and MUST be restored in a future refactor.

#### Scenario: Contributor reads the setup guidance
- **WHEN** a contributor follows the repository setup documentation after the migration
- **THEN** the documentation explains that the default `uv sync` environment is intentionally lighter-weight for stabilization
- **AND** the documentation explicitly states that `torch` and `xformers` remain future-required dependencies rather than removed project goals

### Requirement: Out-of-scope publishing workflows are removed
The repository SHALL remove publishing automation and instructions that imply Python package release is supported during this change.

#### Scenario: Contributor reviews repository automation and docs
- **WHEN** a contributor checks release workflows and setup documentation after the change
- **THEN** they do not find an active GitHub workflow for package publishing
- **AND** the documentation does not present PyPI/TestPyPI release as part of the current supported workflow

### Requirement: Supported dependency baselines stay current in project metadata
The repository SHALL maintain current supported dependency baselines in `pyproject.toml` for explicitly pinned core and optional acceleration dependencies instead of keeping outdated hard pins after the ecosystem has moved forward.

#### Scenario: Contributor inspects maintained pinned dependencies
- **WHEN** a contributor reviews the explicitly pinned dependency entries in `pyproject.toml`
- **THEN** the pinned core and optional acceleration packages reflect the repository's current supported baselines rather than legacy versions carried forward from earlier migrations

### Requirement: Shared optional dependency baselines remain aligned
The repository SHALL keep shared dependency baselines synchronized across optional extras that are expected to install the same acceleration-related packages.

#### Scenario: Contributor compares TensorRT and dev extras
- **WHEN** a contributor compares the overlapping acceleration-related dependency entries in the `tensorrt` and `dev` extras
- **THEN** the shared packages use the same version policy in both extras
- **AND** repository verification can detect if those shared entries drift apart


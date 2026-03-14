## ADDED Requirements

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

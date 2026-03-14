## ADDED Requirements

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

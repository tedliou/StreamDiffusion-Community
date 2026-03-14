# openspec-collaboration-flow Specification

## Purpose
Define the repository's OpenSpec collaboration flow for natural-language entry, stage ownership, user-chosen workspace strategy, and verification expectations.
## Requirements
### Requirement: Natural-language workflow requests use a staged OpenSpec entry
The repository SHALL route natural-language feature or behavior requests through the `openspec-autopilot` path when the user wants the repository to drive the full workflow. That path SHALL ask whether to use the full SDD/TDD/OpenSpec process before entering proposal work so documentation-only edits, one-off verification requests, and similar bounded tasks can stay on a lighter path.

#### Scenario: Contributor starts from a natural-language behavior request
- **WHEN** a contributor asks for a feature or behavior change in natural language
- **THEN** the repository guidance directs the agent to start with `openspec-autopilot`
- **AND** the workflow first asks whether the task should use the full SDD/TDD/OpenSpec path or a lighter path

#### Scenario: Contributor chooses a lighter path
- **WHEN** the contributor says the task is a doc-only edit, one-off verification, or another bounded task
- **THEN** the workflow guidance allows the agent to stay out of the heavier OpenSpec path
- **AND** the guidance does not force creation of OpenSpec artifacts for that task

### Requirement: Clear requests may go directly to proposal while fuzzy requests use brainstorming
The repository SHALL distinguish between idea-shaping and stage execution. Explicit `/opsx:*` commands SHALL own the requested stage, already-clear requests MAY proceed directly to proposal work, and fuzzy requests SHALL be clarified with brainstorming before proposal.

#### Scenario: Contributor gives a direct stage command
- **WHEN** a contributor invokes `/opsx:propose`, `/opsx:apply`, `/opsx:verify`, or `/opsx:archive`
- **THEN** the requested stage owns the workflow for that turn
- **AND** the guidance does not replace it with the single-entry autopilot flow

#### Scenario: Contributor has a clear change in mind
- **WHEN** a contributor provides a clear change name or a sufficiently specific request
- **THEN** the workflow guidance allows direct proposal work
- **AND** brainstorming is described as optional unless the request is still fuzzy

#### Scenario: Contributor needs help shaping the change
- **WHEN** the request still has unclear scope, trade-offs, or boundaries
- **THEN** the guidance directs the agent to use brainstorming before proposal
- **AND** the resulting handoff remains inside OpenSpec rather than creating a parallel plan

### Requirement: Worktree usage is chosen by the user after the agent explains the branch point
The repository SHALL treat worktree usage as a user decision. The agent MAY inspect OpenSpec artifact state and recommend either staying in the current workspace or using a worktree, but it SHALL NOT automatically create or require a worktree without the user's choice.

#### Scenario: Uncommitted change artifacts exist
- **WHEN** the relevant OpenSpec change files are still uncommitted
- **THEN** the workflow guidance explains that implementation can continue in the current workspace or after an explicit commit decision
- **AND** it does not automatically create a worktree

#### Scenario: Committed artifacts make isolation attractive
- **WHEN** the relevant OpenSpec change files are committed and the agent believes isolation would help
- **THEN** the workflow guidance presents a recommendation and alternatives for workspace choice
- **AND** the user decides whether to stay in place or invoke `using-git-worktrees`

### Requirement: Verification guidance covers project checks, OpenSpec validation, and tool fallbacks
The repository SHALL document that completion claims require both the relevant project verification commands and OpenSpec validation. Workflow guidance SHALL also explain the CLI fallback to use when `/opsx:*` commands are unavailable in the current tool.

#### Scenario: Contributor reaches verification
- **WHEN** a contributor prepares to verify a completed workflow-related change
- **THEN** the guidance instructs them to run the relevant project checks for the files they changed
- **AND** it also instructs them to run `openspec validate <change>` and `openspec validate --specs` when specs are affected

#### Scenario: Current tool does not support slash commands
- **WHEN** a contributor is working in a tool that does not provide `/opsx:*` commands
- **THEN** the workflow guidance gives the corresponding CLI commands to continue the same stage
- **AND** the documented fallback remains consistent with the repository's OpenSpec-first workflow

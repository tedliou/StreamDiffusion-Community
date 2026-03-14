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

#### Scenario: Contributor chooses the heavier path
- **WHEN** the contributor chooses the full SDD/TDD/OpenSpec path
- **THEN** the workflow commits the resulting OpenSpec artifacts before implementation starts
- **AND** it does not pause for a separate commit-or-not decision

### Requirement: Interactive workflow prompts match the contributor's communication style and terminal constraints
The repository SHALL format workflow questions so they work in plain-text IDE and CLI interfaces. The guidance SHALL ask questions in the contributor's preferred communication language, present mutually exclusive options as numbered choices, and use examples only when an option would otherwise be too abstract.

#### Scenario: Contributor receives a workflow decision prompt
- **WHEN** the workflow asks the contributor to choose a path, stage, commit action, or workspace action
- **THEN** the prompt uses the contributor's preferred communication language
- **AND** the options are listed with numeric labels so the contributor can answer with a short number
- **AND** the prompt remains readable in plain-text IDE and CLI views

#### Scenario: Options are already concrete
- **WHEN** every choice is specific enough to be understood without an example
- **THEN** the workflow guidance omits extra examples
- **AND** the prompt stays concise instead of adding unnecessary sample text

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

#### Scenario: Uncommitted change artifacts are detected before implementation
- **WHEN** the relevant OpenSpec change files are still uncommitted before implementation starts
- **THEN** the workflow commits those artifacts before the implementation workspace decision continues
- **AND** it does not offer a separate commit-or-not prompt

#### Scenario: Committed artifacts make isolation attractive
- **WHEN** the relevant OpenSpec change files are committed and the agent believes isolation would help
- **THEN** the workflow guidance presents a recommendation and alternatives for workspace choice
- **AND** the user decides whether to stay in place or invoke `using-git-worktrees`

### Requirement: Commit language and style prompts respect project conventions
The repository SHALL avoid unnecessary commit-format questions when project guidance already defines the expected language or style. The agent MAY inspect project instructions and recent commit history to infer the repository convention, and it SHALL only ask the contributor when the convention is missing or the contributor explicitly wants to override it.

#### Scenario: Project guidance already defines commit conventions
- **WHEN** repository instructions already specify commit message language or style
- **THEN** the workflow guidance reuses that convention automatically
- **AND** it does not interrupt the contributor with redundant commit language or style questions

#### Scenario: Repository convention is unclear
- **WHEN** project instructions are silent and recent history does not establish a clear commit convention
- **THEN** the workflow guidance asks the contributor to choose the missing commit language or style
- **AND** the prompt stays separate from unrelated commit decisions

### Requirement: Verification guidance covers project checks, OpenSpec validation, and tool fallbacks
The repository SHALL document that completion claims require both the relevant project verification commands and OpenSpec validation. Workflow guidance SHALL also explain the CLI fallback to use when `/opsx:*` commands are unavailable in the current tool.

#### Scenario: Contributor reaches verification
- **WHEN** a contributor prepares to verify a completed workflow-related change
- **THEN** the guidance instructs them to run the relevant project checks for the files they changed
- **AND** it also instructs them to run `openspec validate <change>` and `openspec validate --specs` when specs are affected

#### Scenario: SDD and TDD were completed during implementation
- **WHEN** the implementation already followed the approved SDD/TDD path
- **THEN** the workflow advances into verification automatically
- **AND** it does not stop for an extra verify-stage confirmation prompt

#### Scenario: Current tool does not support slash commands
- **WHEN** a contributor is working in a tool that does not provide `/opsx:*` commands
- **THEN** the workflow guidance gives the corresponding CLI commands to continue the same stage
- **AND** the documented fallback remains consistent with the repository's OpenSpec-first workflow

### Requirement: Archiving a worktree-backed change merges it back into the main workspace
The repository SHALL treat archive approval as the point where a completed worktree-backed change returns to the main workspace. If the contributor implemented the change in a worktree and then approves archive, the workflow SHALL merge that finished branch back into the main workspace as part of completion.

#### Scenario: Archived change was implemented in a worktree
- **WHEN** a contributor approves archive for a change that was implemented in a worktree
- **THEN** the workflow archives the OpenSpec change
- **AND** it merges the finished worktree branch back into the main workspace before cleanup

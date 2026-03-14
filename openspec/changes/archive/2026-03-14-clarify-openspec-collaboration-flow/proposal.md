## Why

The repository now points contributors toward an OpenSpec-first collaboration workflow, but the human-facing guide, `AGENTS.md`, and several repository-local skills still disagree about key decisions. In particular, natural-language entry, brainstorming expectations, worktree handling, CLI fallbacks, and verification requirements are not described consistently enough for contributors to predict what will happen when they ask for a change.

## What Changes

- Clarify the repository's OpenSpec collaboration flow for both natural-language requests and explicit `/opsx:*` stage commands.
- Define when brainstorming is required, when direct proposal work is allowed, and how lighter non-OpenSpec tasks are routed.
- Update workflow guidance so worktree usage is recommended by the agent but chosen by the user instead of being auto-invoked.
- Document the minimum verification expectations for workflow changes, including project checks and OpenSpec validation.
- Remove or replace stale OpenSpec smoke-test artifacts so the committed repository state matches the documented workflow.

## Capabilities

### New Capabilities
- `openspec-collaboration-flow`: Defines the repository's OpenSpec collaboration rules for entry points, stage ownership, worktree decisions, and verification expectations.

### Modified Capabilities

## Impact

- Affects `AGENTS.md`, `docs/openspec-workflow.md`, and repository-local workflow skills under `.agents/skills/`.
- Affects OpenSpec artifacts under `openspec/` so the documented workflow remains grounded in committed repository state.
- No runtime model, demo, or public API behavior changes are expected.

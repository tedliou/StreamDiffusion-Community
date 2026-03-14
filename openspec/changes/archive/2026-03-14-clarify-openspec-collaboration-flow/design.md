## Context

The repository recently adopted an OpenSpec-first collaboration model, but the current guidance spans `AGENTS.md`, a human-facing quick start, and multiple repository-local skills. Those sources currently drift on key questions: whether natural-language requests automatically enter OpenSpec, when brainstorming is mandatory, whether worktrees are auto-invoked or user-chosen, and what counts as sufficient verification before archive. The current workspace state also demonstrates the risk of drift because `openspec/` artifacts can disappear while the documentation still presents OpenSpec as the active workflow backbone.

## Goals / Non-Goals

**Goals:**
- Give contributors one predictable collaboration flow for natural-language requests and explicit `/opsx:*` commands.
- State that worktree usage is recommended by the agent when helpful but selected by the user.
- Align human-facing documentation and repository-local skills around the same workflow language.
- Leave the repository with a valid, committed `openspec/` state that matches the workflow being documented.

**Non-Goals:**
- Changing runtime Python package behavior, demos, or frontend code.
- Designing a fully automated worktree policy that removes user choice.
- Expanding OpenSpec into a general CI or release workflow beyond collaboration guidance.

## Decisions

### Keep OpenSpec as the formal source of truth for workflow-affecting changes

This change itself will be tracked as a spec-driven OpenSpec change so the repository's own workflow remains self-consistent. The corresponding spec introduces an `openspec-collaboration-flow` capability that documents entry routing, stage ownership, worktree choice, and verification expectations.

Alternative considered: only editing docs and skills without OpenSpec artifacts. Rejected because it would leave the repository saying "OpenSpec is the source of truth" while handling workflow changes outside OpenSpec.

### Distinguish entry routing from idea shaping

Natural-language feature or behavior requests enter through `openspec-autopilot`, which first asks whether the task should use the full SDD/TDD/OpenSpec path. Brainstorming remains available when the request is still fuzzy, but it should not be described as mandatory for every change when a clear request can proceed directly to proposal work.

Alternative considered: making brainstorming mandatory for every behavior change. Rejected because it conflicts with the documented direct `/opsx:propose` path for already-clear requests and creates unnecessary friction for bounded changes.

### Make worktree handling an explicit user choice

The workflow should inspect OpenSpec change state and explain the options, but it should not automatically create or require a worktree merely because isolation might help. The agent may recommend staying in place or using a worktree based on repo state, yet the user chooses the workspace strategy.

Alternative considered: preserving the previous "auto-decide and invoke worktree flow" language. Rejected because the user wants worktree choice retained as an explicit human decision and because hidden branch/workspace changes increase workflow surprise.

### Define verification as both repository checks and OpenSpec validation

Verification guidance should explicitly require relevant project checks plus `openspec validate <change>` and `openspec validate --specs` when specs are affected. This keeps workflow validation grounded in both implementation evidence and OpenSpec consistency.

Alternative considered: documenting only OpenSpec validation. Rejected because it under-specifies the code and documentation checks needed before claiming completion.

## Risks / Trade-offs

- [More detailed workflow text] -> Keep descriptions concise and aligned across the small set of source-of-truth files instead of duplicating bespoke guidance everywhere.
- [User-decided worktrees may reduce isolation] -> Make recommendations explicit at the decision point and keep `using-git-worktrees` available when the user wants isolation.
- [OpenSpec artifact cleanup could accidentally preserve stale guidance] -> Replace the current broken `openspec/` state with artifacts that describe the updated workflow rather than keeping stale smoke-test files by default.

## Migration Plan

1. Create and complete the OpenSpec change for workflow clarification.
2. Update `AGENTS.md`, `docs/openspec-workflow.md`, and affected skills to match the approved requirements.
3. Validate the OpenSpec artifacts and documented command paths.
4. Archive the change so the committed `openspec/specs/` state becomes the long-term workflow reference.

## Open Questions

No open questions remain for this change.

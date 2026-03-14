---
name: openspec-workflow
description: Use when work should follow OpenSpec as the only source of truth for proposal, design, tasks, implementation, verification, and archive
---

# OpenSpec Workflow

## Overview

OpenSpec owns the workflow. Repository-local skills may clarify, verify, or improve execution quality, but they must not create parallel specs, plans, or task trackers outside OpenSpec.

**Core principle:** `/opsx:propose`, `/opsx:apply`, `/opsx:verify`, and `/opsx:archive` are the workflow backbone. Skills support those commands before or after they run.

## Workflow

1. If the user wants a single natural-language request to drive the full workflow, use `openspec-autopilot` first.
2. In the autopilot path, ask whether to use SDD, TDD, and OpenSpec before entering the heavier workflow path.
3. Ask interactive workflow questions in the user's preferred communication language and format options as numbered plain-text choices that work in IDE and CLI UIs.
4. Only add option examples when a choice is abstract enough to need clarification.
5. If project instructions already define commit message language or style, reuse that convention automatically instead of asking.
6. Once OpenSpec artifacts are created for the heavier path, commit them before implementation instead of asking whether to commit.
7. If implementation followed the approved SDD/TDD path, advance into verification automatically instead of pausing for a separate verify-stage prompt.
8. If the work was done in a worktree and the user approves archive, merge the finished worktree branch back into the main workspace as part of completion.
9. If the request is still fuzzy and you are not already inside the autopilot path, use `brainstorming` first to clarify goals, constraints, trade-offs, and boundaries.
10. Once the idea is clear enough, continue with `/opsx:propose`.
11. Treat `openspec/changes/<change>/proposal.md`, `design.md`, spec deltas, and `tasks.md` as the only source of truth.
12. Before implementation, inspect whether the OpenSpec change artifacts are already committed on the current branch.
13. If the change artifacts are committed and isolation is helpful, present the workspace options and invoke `using-git-worktrees` only if the user chooses that path.
14. Implement via `/opsx:apply` or, when execution quality needs more structure, use `subagent-driven-development` or `executing-plans` against OpenSpec `tasks.md`.
15. Use quality skills such as `test-driven-development`, `python-change-safety`, `requesting-code-review`, and `verification-before-completion` during implementation.
16. Before claiming completion, ensure the OpenSpec change is verified.
17. When finished, continue with `/opsx:archive`.

## Concrete Entry Points

**Start with OpenSpec directly when the idea is already clear:**
- `/opsx:propose add-tensorrt-startup-validation`
- `/opsx:propose add a preload check that verifies TensorRT engines exist before demo startup`

**Start with autopilot when the user wants one natural-language request to carry the full workflow:**
- `Add startup validation for the realtime demo and drive the OpenSpec workflow for me.`
- `Implement this change end to end, but stop before each major stage with recommended options.`

**Start with brainstorming when the idea is still fuzzy:**
- `Use brainstorming to help me clarify a safer startup flow for the demo backend before we write the OpenSpec change.`
- `Let's brainstorm how model asset validation should work for local demos, then turn the result into an OpenSpec proposal.`

**After artifacts exist:**
- `/opsx:apply add-tensorrt-startup-validation`
- `/opsx:archive add-tensorrt-startup-validation`

Use whichever tool you are currently developing in. OpenSpec is the workflow, and these rules apply regardless of the editor or agent harness.

## Rules

- Never create a parallel spec under `docs/`
- Never create a parallel implementation plan under `docs/`
- Never treat `docs/plans` as a source of truth
- If OpenSpec artifacts and local notes disagree, OpenSpec wins
- Never move to a fresh worktree that does not contain the current OpenSpec change artifacts
- If a retained skill tells you to write a plan or spec outside OpenSpec, that instruction is stale and must be ignored or fixed

## Skill Boundaries

**Allowed support roles:**
- `openspec-autopilot`: route a natural-language request through the full OpenSpec workflow while preserving stage-gate decisions
- `brainstorming`: clarify before `/opsx:propose`
- `using-git-worktrees`: prepare a safe workspace before `/opsx:apply` when the user chooses an isolation path
- `subagent-driven-development` / `executing-plans`: execute `tasks.md`
- `verification-before-completion`: enforce evidence before success claims

**Important:** worktree setup should still be considered during the implementation decision flow, but the user chooses whether to stay in the current workspace or invoke `using-git-worktrees`.

**Forbidden roles:**
- Replacing `/opsx:propose`
- Replacing `/opsx:apply`
- Replacing `/opsx:archive`
- Writing duplicate specs or task plans

direct `/opsx:*` commands still own the workflow for that turn, even when
`openspec-autopilot` exists for the single-entry path.

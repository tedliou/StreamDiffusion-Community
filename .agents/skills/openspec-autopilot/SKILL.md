---
name: openspec-autopilot
description: Use when a single natural-language request should drive the full OpenSpec workflow automatically while still pausing for stage and branch decisions
---

# OpenSpec Autopilot

## Overview

Use this skill when the user gives a feature request or behavior-change request
in natural language and wants the repository to drive the OpenSpec workflow for
them.

OpenSpec still owns formal state. This skill is an orchestrator, not a
replacement workflow.

## Core Contract

- Start from a single natural-language request.
- Ask whether to use SDD, TDD, and OpenSpec before entering the heavier workflow path.
- Route through the repository's required workflow stages.
- Keep SDD, TDD, workspace decisions, and verification in place.
- Pause before `propose`, `apply`, `verify`, and `archive`.
- Also pause when the workflow needs a decision about worktrees or commits.
- Every decision prompt must include:
  - one recommended option
  - one or two alternatives
  - a short example for each option
- Allow the user to override with a short free-form reply.

## Direct OpenSpec Commands Still Win

If the user explicitly invokes `/opsx:propose`, `/opsx:apply`, `/opsx:verify`,
or `/opsx:archive`, direct `/opsx:*` commands still own the workflow for that
turn.

Do not replace an explicit stage request with the single-entry flow.

## Routing Logic

### 1. Detect the entry mode

- Explicit `/opsx:*` command: defer to the requested OpenSpec stage.
- Natural-language feature or behavior request: use this skill.

### 2. Ask for workflow weight first

Before entering the heavier process path, ask whether to use SDD, TDD, and OpenSpec.

Use this when the request might be:

- a documentation-only change
- a one-off verification request
- a tool or command run
- another bounded task that may not justify the full workflow

Example prompt:

- `Recommended: Use the full SDD/TDD/OpenSpec path` Example: `Behavior changes, new features, or workflow-affecting work`
- `Alternative: Use a lighter path for this task` Example: `Edit docs, run a verification command, or use a tool without opening a formal change`
- `Alternative: Decide after a short clarification pass` Example: `Clarify scope first, then choose the heavier or lighter path`

If the user chooses the lighter path, do not force the request into OpenSpec.

### 3. Decide whether to brainstorm first

- If the request is fuzzy, use `brainstorming`.
- If the request is already clear, prepare to enter proposal work directly.

Before moving forward, present the `propose` stage gate.

### 4. Stage-gate prompts

Pause before:

- `propose`
- `apply`
- `verify`
- `archive`

Each prompt should use this shape:

- `Recommended:` <option> Example: `<short example>`
- `Alternative:` <option> Example: `<short example>`
- `Alternative:` <option> Example: `<short example>`

Keep the options mutually exclusive and easy to scan.

## Conditional Branch Prompts

Ask only when the branch point is actually relevant.

### Worktree decision

Before implementation, inspect the current change state:

```bash
git status --short openspec/changes
```

- If the relevant change artifacts are uncommitted, stay in the current
  workspace or ask whether to commit first.
- If the relevant change artifacts are committed and isolation is useful, ask
  whether to stay in the current workspace or open a worktree.

Example prompt:

- `Recommended: Open a worktree` Example: `Create .worktrees/add-startup-check before apply`
- `Alternative: Stay in the current workspace` Example: `Continue apply on the current branch`
- `Alternative: Commit artifacts first, then open a worktree` Example: `Commit openspec/changes/<change>/ and branch from there`

### Commit timing

When a commit is needed or strongly recommended, ask before creating it.

Example prompt:

- `Recommended: Commit now` Example: `Commit the OpenSpec artifacts before apply`
- `Alternative: Continue without a commit` Example: `Keep proposal and tasks uncommitted in the current workspace`
- `Alternative: Commit only the workflow artifacts` Example: `Commit openspec/changes/<change>/ and nothing else`

### Commit message language

Ask separately from style.

Example prompt:

- `Recommended: English` Example: `feat: add startup validation`
- `Alternative: Traditional Chinese` Example: `feat: 新增啟動前檢查`

### Commit style

Inspect recent commit history before recommending a style:

```bash
git log --oneline --max-count=12
```

Infer the dominant pattern and present it as a recommendation, not a rule.

Example prompt:

- `Recommended: Reuse the recent commit style` Example: `feat: add startup validation`
- `Alternative: Conventional Commits` Example: `chore(openspec): add apply-ready artifacts`
- `Alternative: Short natural sentence` Example: `add startup validation flow`

## Apply Expectations

Once the user chooses to continue into implementation:

- OpenSpec `tasks.md` is the execution checklist.
- `test-driven-development` is required before changing behavior.
- `using-git-worktrees` is used when the user chooses the worktree path.
- `verification-before-completion` applies before any success claim.

## Verify Expectations

Before `verify`, ask the stage-gate question.

Then run:

- the real project verification commands for the files you changed
- `openspec validate <change>`
- `openspec validate --specs` when relevant

OpenSpec validation does not replace code tests or builds.

## Archive Expectations

Before `archive`, ask the stage-gate question.

If the work happened in a worktree, make sure the user has chosen the commit
message language and style before creating the commit that carries the finished
change.

## Smoke Flow References

The orchestrated workflow should support both of these repository-tested paths:

### In-place implementation path

1. Receive a natural-language request
2. Ask whether to use SDD, TDD, and OpenSpec
3. Pause before `propose`
4. Create OpenSpec artifacts
5. Keep uncommitted artifacts in the current workspace
6. Pause before `apply`
7. Implement with TDD in the current workspace
8. Pause before `verify`
9. Verify code and OpenSpec
10. Pause before `archive`
11. Archive the change

### Committed-artifact worktree path

1. Receive a natural-language request
2. Ask whether to use SDD, TDD, and OpenSpec
3. Pause before `propose`
4. Create OpenSpec artifacts
5. Ask whether to commit
6. Ask for commit message language
7. Detect recent commit history and recommend a commit style
8. Commit the artifacts
9. Pause before `apply`
10. Ask whether to open a worktree
11. Implement with TDD in the worktree
12. Pause before `verify`
13. Verify code and OpenSpec
14. Pause before `archive`
15. Archive the change

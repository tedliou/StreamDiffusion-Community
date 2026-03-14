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
- Pause before `propose`, `apply`, and `archive`.
- Also pause when the workflow needs a decision about worktrees.
- Ask questions in the user's preferred communication language.
- Format every decision prompt as a plain-text numbered list that displays cleanly in IDE and CLI UIs.
- Every decision prompt must include:
  - one recommended option listed first
  - one or two alternatives
  - numeric labels so the user can reply with `1`, `2`, or `3`
- Add examples only when an option is abstract enough that the choice would otherwise be unclear.
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

1. `Recommended: Use the full SDD/TDD/OpenSpec path`
   Example: `Behavior changes, new features, or workflow-affecting work`
2. `Alternative: Use a lighter path for this task`
   Example: `Edit docs, run a verification command, or use a tool without opening a formal change`
3. `Alternative: Decide after a short clarification pass`
   Example: `Clarify scope first, then choose the heavier or lighter path`

If the user chooses the lighter path, do not force the request into OpenSpec.

### 3. Decide whether to brainstorm first

- If the request is fuzzy, use `brainstorming`.
- If the request is already clear, prepare to enter proposal work directly.

Before moving forward, present the `propose` stage gate.

### 4. Stage-gate prompts

Pause before:

- `propose`
- `apply`
- `archive`

Each prompt should use this shape:

1. `Recommended:` <option>
2. `Alternative:` <option>
3. `Alternative:` <option>

Keep the options mutually exclusive and easy to scan. Add an example only when it materially clarifies an otherwise fuzzy option.

## Conditional Branch Prompts

Ask only when the branch point is actually relevant.

### Worktree decision

Before implementation, inspect the current change state:

```bash
git status --short openspec/changes
```

- If the relevant change artifacts are uncommitted, stay in the current
  workspace only until they are committed for the heavier path.
- If the relevant change artifacts are committed and isolation is useful, ask
  whether to stay in the current workspace or open a worktree.

Example prompt:

1. `Recommended: Open a worktree`
2. `Alternative: Stay in the current workspace`

### Commit timing

When OpenSpec artifacts are created for the heavier path, commit them before implementation. Do not ask whether to commit first.

### Commit message language and style

Check repository guidance before asking:

- If project instructions already specify commit language or style, follow them automatically and do not ask.
- If project instructions are silent, inspect recent commit history before inferring the dominant pattern.
- Ask only when the repository lacks a clear convention or the user explicitly wants to override it.

Inspect recent commit history before recommending a style when needed:

```bash
git log --oneline --max-count=12
```

Infer the dominant pattern and present it as a recommendation, not a rule.

Only ask for commit language or style when no project convention exists. If you do ask, keep language and style in separate numbered prompts and add examples only when the labels are too vague on their own.

## Apply Expectations

Once the user chooses to continue into implementation:

- OpenSpec `tasks.md` is the execution checklist.
- `test-driven-development` is required before changing behavior.
- `using-git-worktrees` is used when the user chooses the worktree path.
- `verification-before-completion` applies before any success claim.

## Verify Expectations

Do not pause before `verify` when implementation followed the approved SDD/TDD path. Move into verification automatically after implementation work is complete and the prior development checks have passed.

Then run:

- the real project verification commands for the files you changed
- `openspec validate <change>`
- `openspec validate --specs` when relevant

OpenSpec validation does not replace code tests or builds.

## Archive Expectations

Before `archive`, ask the stage-gate question.

If the work happened in a worktree and the user approves `archive`, merge the finished work back to the main workspace as part of the archive flow.

## Smoke Flow References

The orchestrated workflow should support both of these repository-tested paths:

### In-place implementation path

1. Receive a natural-language request
2. Ask whether to use SDD, TDD, and OpenSpec
3. Pause before `propose`
4. Create OpenSpec artifacts
5. Commit OpenSpec artifacts in the current workspace
6. Pause before `apply`
7. Implement with TDD in the current workspace
8. Automatically run `verify` after implementation when SDD/TDD expectations are satisfied
9. Verify code and OpenSpec
10. Pause before `archive`
11. Archive the change

### Committed-artifact worktree path

1. Receive a natural-language request
2. Ask whether to use SDD, TDD, and OpenSpec
3. Pause before `propose`
4. Create OpenSpec artifacts
5. Commit OpenSpec artifacts
6. Reuse project commit language and style automatically when guidance exists
7. Detect recent commit history and ask only if the repository still lacks a clear commit convention
8. Pause before `apply`
9. Ask whether to open a worktree
10. Implement with TDD in the worktree
11. Automatically run `verify` after implementation when SDD/TDD expectations are satisfied
12. Verify code and OpenSpec
13. Pause before `archive`
14. Archive the change
15. Merge the finished worktree branch back to the main workspace

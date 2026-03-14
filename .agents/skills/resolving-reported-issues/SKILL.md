---
name: resolving-reported-issues
description: Use when a user reports a bug, failure, or unexpected behavior and expects end-to-end handling rather than a one-off diagnosis
---

# Resolving Reported Issues

## Overview

Turn a raw issue report into a verified repository change without skipping the thinking needed to make that change safe.

This skill is the issue-oriented companion to `openspec-autopilot`: it borrows the one-question-at-a-time clarification style from `brainstorming`, enforces `systematic-debugging` before fix proposals, and then drives the normal OpenSpec workflow once the issue is concrete enough.

When this skill is explicitly invoked, it runs in autonomous mode: the agent should choose the best workflow option at each internal decision point and continue without waiting for human confirmation unless it is truly blocked or a decision is unusually risky or irreversible.

## Core Contract

- Keep the conversation in the user's preferred language.
- Treat the user's report as an issue intake, not as permission to guess.
- In autonomous mode, do not stop for ordinary workflow checkpoints, stage gates, or option menus.
- Choose the recommended path automatically when repository guidance already implies a default.
- In autonomous mode, create and switch to a non-main working branch before making OpenSpec artifacts, code edits, or commits.
- Never commit directly to `main` or `master`.
- Do not propose fixes before evidence supports a root-cause hypothesis or a bounded change strategy.
- Do not enter OpenSpec proposal work until the issue passes the readiness gate below.
- Direct `/opsx:*` commands still own the workflow for that turn.
- Do not create parallel specs, plans, or task trackers outside `openspec/`.
- Ask the user a follow-up only when a required fact cannot be inferred or discovered locally and proceeding would create material correctness or safety risk.

## When To Use

Use this skill when the user says things like:

- "I hit this bug. Please take it from here."
- "Something is failing. Figure out what to change and fix it."
- "Here is an issue. Reproduce it, decide the fix, and tell me the result."
- "Drive the whole OpenSpec workflow for this problem."

Do not use this skill for:

- Clearly scoped feature ideation without a reported issue: use `brainstorming`
- Explicit `/opsx:*` stage requests: follow the requested OpenSpec stage
- One-off command runs or lightweight diagnostics that the user does not want turned into a formal change

## Workflow

### 1. Ask For Workflow Weight First

Start with the same decision required by `openspec-autopilot`, but resolve it yourself in autonomous mode.

Default behavior:

- choose the full SDD/TDD/OpenSpec path when the issue is likely to require a repository change
- choose a lighter diagnosis-only path only when evidence shows the request is truly diagnostic, environmental, or does not justify a formal change
- do not ask the user to pick between these unless the trade-off cannot be judged responsibly from repository context

### 1.5. Bootstrap A Safe Working Branch

Before creating any OpenSpec change files or implementation edits, ensure the autonomous workflow is operating on a dedicated branch.

Default policy:

- if the current branch is `main`, `master`, or another protected/default branch, create and switch to a new working branch first
- if already on a dedicated non-default branch created for this issue, continue there
- if the issue later moves into a worktree path, carry the same branch intent forward there rather than returning to `main`

Automatic naming:

- derive a short slug from the issue summary or the confirmed change focus
- use the format `auto/<slug>`
- if the OpenSpec change slug becomes the clearer identifier, `auto/<change-slug>` is preferred
- if the candidate branch already exists, append a short numeric or date-based suffix rather than asking the user

Examples:

- `auto/fix-startup-validation`
- `auto/tensorrt-engine-missing`
- `auto/fix-startup-validation-2`

### 2. Run The Issue-Intake Loop

If the issue is not already concrete, switch into a brainstorming-like clarification loop:

- Explore local context first: relevant files, docs, recent commits, failing tests, logs, or commands
- Resolve missing details from the workspace yourself whenever possible
- If a question is unavoidable, ask only one at a time
- Focus on symptom, expected behavior, reproduction steps, environment, frequency, recent changes, impact, and constraints
- If the user does not know the details, gather evidence yourself by trying to reproduce locally

This loop is for narrowing the problem, not for proposing a fix yet.

### 3. Enforce Root-Cause Discipline

For any bug, test failure, performance regression, or unexpected behavior, invoke `systematic-debugging` before proposing fixes.

That means:

- reproduce consistently when possible
- read errors carefully
- inspect recent changes
- trace data flow when the failure is deep or multi-stage
- form one evidence-backed hypothesis at a time

Do not skip to implementation because a fix "seems obvious."

### 4. Apply The Readiness Gate

You may continue into OpenSpec proposal work only when at least one of these is true:

1. You have a reliable reproduction and a feasible change direction.
2. You have enough evidence to support a concrete root-cause hypothesis and a bounded fix strategy, even if reproduction is incomplete.
3. A first-class observability or guardrail change is the safest bounded next step for making the issue reproducible or constrained.

If none of these are true, stay in intake/debugging. Do not open an OpenSpec change yet.

### 5. Prepare The OpenSpec Handoff

Once the readiness gate passes, summarize the issue in OpenSpec-ready terms:

- problem statement and impact
- current evidence and reproduction status
- root-cause hypothesis or confirmed cause
- scope and non-goals
- recommended change strategy
- key risks and constraints
- testing and verification expectations

If the issue is already clear, this handoff can be short. If the issue really hides multiple independent problems, split it before proposal work.

### 6. Drive The OpenSpec Workflow

After the issue is ready, follow the normal repository workflow, but auto-select the normal stage-gate choices:

- use `openspec-autopilot` stage-gate behavior
- advance into `propose`, `apply`, and `archive` automatically once each stage's prerequisites are satisfied
- keep all OpenSpec and implementation commits on the dedicated working branch, never on `main` or `master`
- commit OpenSpec artifacts before implementation on the heavier path
- choose the workspace strategy yourself when it is actually relevant
- reuse repository commit conventions automatically when guidance already exists

Default workspace heuristic:

- stay in the current workspace when OpenSpec artifacts are still uncommitted or the change is small and isolation offers little benefit, but only after switching the current workspace onto the dedicated working branch
- open a worktree only when the artifacts are already committed and isolation materially reduces risk for a larger or longer-running implementation

If implementation work becomes large and task-separable, use `subagent-driven-development` or `executing-plans` against `openspec/changes/<change>/tasks.md`.

### 7. Implement With Quality Guards

During execution:

- use `test-driven-development` before behavior-changing code
- use `python-change-safety` when touching Python package or runtime paths
- use `using-git-worktrees` only if your autonomous workspace decision selects isolation
- use `requesting-code-review` when an implementation checkpoint would benefit from a review pass

Do not treat issue diagnosis as complete until the code change and the OpenSpec change both agree on scope.

### 8. Verify, Archive, And Report Back

Before any completion claim:

- run the real project verification commands for the files you changed
- run `openspec validate <change>`
- run `openspec validate --specs` when relevant
- apply `verification-before-completion`

After archive, report back in outcome form:

- what was actually wrong
- what changed
- how it was verified
- any residual risks, follow-ups, or limits

The user should be able to hand you an issue and receive a concrete result summary without separately managing the workflow.

## Autonomous Decision Policy

When this skill is active, prefer silent internal decisions over interactive prompts for:

- workflow weight
- branch creation and branch naming
- whether the issue is clear enough to proceed
- whether to continue from debugging into proposal work
- whether to stay in-place or use a worktree
- when to advance from propose to apply to verify to archive

Pause only for:

- missing external information that cannot be discovered locally
- decisions with unusually high irreversible impact outside normal repository work
- explicit user requests to review or approve a stage manually
- blockers that prevent a safe or correct best-effort decision

## Practical Guidance

### Good Intake Questions

Ask for the smallest missing detail that changes the plan:

- "Which command fails?"
- "What did you expect instead?"
- "Does this happen every run or only sometimes?"
- "Did this start after a specific change?"

Avoid multi-part interrogations. One question per message keeps the issue moving.

### When Reproduction Is Missing

Lack of reproduction is not automatic permission to guess.

Acceptable next moves are:

- gather logs or error output
- inspect recent diffs
- add narrowly scoped instrumentation
- propose a guardrail change that safely narrows the failure surface

Unacceptable next move:

- "I think it is probably X, so I changed Y."

### When To Split The Work

Stop and split the change when the reported "issue" is really:

- multiple unrelated failures
- one bug plus a feature request
- a fix that would require unrelated cleanup to land safely

Each resulting OpenSpec change should stay reviewable and independently shippable.

## Bottom Line

Issue report in, verified result out.

Clarify first, prove enough to act, then let OpenSpec own the formal change lifecycle.

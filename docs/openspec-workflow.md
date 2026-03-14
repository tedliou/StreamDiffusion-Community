# OpenSpec Workflow

This is the human-facing quick start for development in this repository.

## Core Rule

OpenSpec is the source of truth for:

- requirements
- design
- task breakdown
- verification state
- archive state

The normal flow is:

1. clarify the idea if needed
2. create the OpenSpec change
3. implement the change
4. verify it
5. archive it

## Single-Entry Autopilot

If you want a single natural-language request to drive the whole workflow, use
the repository's `openspec-autopilot` path.

Example requests:

- `Add startup validation for the realtime demo and drive the OpenSpec workflow for me.`
- `Implement this change end to end, but stop before each major stage with recommended options.`

The orchestrated path first asks whether to use SDD, TDD, and OpenSpec for the task at all. This keeps doc-only edits, one-off verification requests, and tool runs out of the heavier workflow when that would just waste time.

Typical preflight options should look like this:

- `Recommended: Use the full SDD/TDD/OpenSpec path` Example: `A feature or behavior change that should become a formal change`
- `Alternative: Use a lighter path for this task` Example: `A docs edit, a command run, or a small tooling task`
- `Alternative: Clarify first, then decide` Example: `Ask one short scope question before choosing the path`

If the user chooses the heavier path, the orchestrated flow keeps OpenSpec as the source of truth, uses `brainstorming` only when the request still needs shaping, and pauses before `propose`, `apply`, `verify`, and `archive`.

## When To Start With Brainstorming

Use `brainstorming` first if your idea is still fuzzy.

Good examples:

- `Use brainstorming to help me clarify a safer startup validation feature before we write the OpenSpec change.`
- `Let's brainstorm options for improving realtime demo startup safety. I want to compare approaches first.`
- `I have a rough feature idea but not a clean change boundary yet. Use brainstorming first.`

What happens next:

- the agent will ask questions
- help compare approaches
- help define a clean change boundary
- then hand off to `/opsx:propose`

If the request is already clear, you do not need a separate brainstorming pass first.

## When To Start Directly With OpenSpec

If the idea is already clear, start directly with `/opsx:propose`.

Examples:

- `/opsx:propose add-tensorrt-startup-validation`
- `/opsx:propose add a preload check that verifies TensorRT engines exist before demo startup`
- `/opsx:propose add validation for missing model assets before launching the realtime demo`

You can give:

- a clear change name
- or a short natural-language request

## Tool Support And Fallbacks

If your current tool does not support `/opsx:*`, stay on the same OpenSpec flow
with the CLI or the bundled repository skills instead of inventing a separate process.

- `propose`: use the bundled `openspec-propose` skill, or create the change with `openspec new change <name>` and author artifacts with `openspec instructions ...`
- `apply`: use the bundled `openspec-apply-change` skill, or inspect the work with `openspec instructions apply --change <name>`
- `verify`: run `openspec validate <change-name>` and `openspec validate --specs`
- `archive`: run `openspec archive <change-name> -y`

## Implementation

After the change artifacts exist, implement with:

- `/opsx:apply <change-name>`

Example:

- `/opsx:apply add-tensorrt-startup-validation`

During implementation, keep OpenSpec `tasks.md` as the execution checklist and
run the real project verification commands required by the affected code. OpenSpec
validation checks change artifacts and spec consistency; it does not replace code
tests, builds, or runtime verification.

If you entered through the single-entry path, expect a decision prompt before
moving into `apply`.

## Worktrees

You do not need to manually remember to trigger the worktree skill in normal use.

The intended behavior is:

- if the OpenSpec change files are still uncommitted, implementation stays in the current workspace or commits first
- if the OpenSpec change files are committed and isolation is useful, the agent should recommend the worktree option and let the user decide whether to use it

In short:

- worktree setup is part of the implementation workflow
- it is not meant to be a separate manual ritual in normal cases
- the user still decides whether to stay in the current workspace or open a worktree

The practical decision point is:

- uncommitted change artifacts: stay in the current workspace for `/opsx:apply`
- committed change artifacts and you want isolation: create a worktree, then run `/opsx:apply` there

When this branch point appears in the orchestrated flow, the agent should show
a recommended option, alternatives, and a short example for each choice.

Typical examples:

- `Recommended: Open a worktree` Example: `Create .worktrees/add-startup-check before apply`
- `Alternative: Stay in the current workspace` Example: `Continue apply on the current branch`
- `Alternative: Commit artifacts first, then open a worktree` Example: `Commit openspec/changes/<change>/ and branch from there`

If the workflow needs a commit decision, the agent should also ask:

- whether to commit now
- which commit message language to use
- which commit style to use after checking recent commit history

If you explicitly want isolation, you can still say so:

- `Use a worktree before applying this change.`

## Verification

If your current tool supports it, use:

- `/opsx:verify <change-name>`

If not, use the CLI directly:

- `openspec validate <change-name>`
- `openspec validate --specs`

Also run the repository's normal verification commands for the implementation
you changed before claiming completion. For this repository, that means using the
real checks that cover the files you touched instead of relying on OpenSpec
validation alone.

If you entered through the single-entry path, expect a decision prompt before
moving into `verify`.

## Archive

When the change is done, archive it with:

- `/opsx:archive <change-name>`

For non-interactive CLI use, you can also run:

- `openspec archive <change-name> -y`

If you entered through the single-entry path, expect a decision prompt before
moving into `archive`.

## Typical End-To-End Example

1. `Use brainstorming to help me clarify a safer startup validation feature before we write the OpenSpec change.`
2. `/opsx:propose add-tensorrt-startup-validation`
3. `/opsx:apply add-tensorrt-startup-validation`
4. run the relevant project tests, builds, or runtime checks for the change
5. `openspec validate add-tensorrt-startup-validation`
6. `openspec validate --specs`
7. `/opsx:archive add-tensorrt-startup-validation`

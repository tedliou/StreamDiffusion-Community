---
name: executing-plans
description: Use when you have an approved OpenSpec change with tasks to execute in a separate session with review checkpoints
---

# Executing Plans

## Overview

Load OpenSpec tasks, review critically, execute all tasks, report when complete.

**Announce at start:** "I'm using the executing-plans skill to implement this OpenSpec change."

**Note:** Tell your human partner that Superpowers works much better with access to subagents. If subagents are available, use superpowers:subagent-driven-development instead of this skill.

Autonomous caller exception: if an upstream repository skill explicitly owns workflow and workspace decisions, follow that caller's decisions without re-introducing routine confirmation prompts.

## The Process

### Step 1: Load and Review OpenSpec Change
1. Read the change's `proposal.md`, `design.md` if present, relevant spec deltas, and `tasks.md`
2. Review critically - identify any questions or concerns about the change or tasks
3. Confirm the OpenSpec change artifacts are present in the workspace you are about to use
4. If concerns: Raise them with your human partner before starting
5. If no concerns: Create TodoWrite and proceed

### Step 2: Execute Tasks

For each task:
1. Mark as in_progress
2. Follow `tasks.md` exactly
3. Run verifications as specified
4. Mark as completed

### Step 3: Complete Development

After all tasks complete and verified:
- Announce: "I'm using the finishing-a-development-branch skill to complete this work."
- **REQUIRED SUB-SKILL:** Use superpowers:finishing-a-development-branch
- Follow that skill to verify tests, present options, execute choice

## When to Stop and Ask for Help

**STOP executing immediately when:**
- Hit a blocker (missing dependency, test fails, instruction unclear)
- The OpenSpec change has critical gaps preventing starting
- The workspace does not actually contain the OpenSpec change artifacts you need
- You don't understand an instruction
- Verification fails repeatedly

**Ask for clarification rather than guessing.**

## When to Revisit Earlier Steps

**Return to Review (Step 1) when:**
- Partner updates the OpenSpec change based on your feedback
- Fundamental approach needs rethinking

**Don't force through blockers** - stop and ask.

## Remember
- Review the OpenSpec change critically first
- Follow `tasks.md` exactly
- Don't skip verifications
- Reference skills when the change or task says to
- Stop when blocked, don't guess
- Never start implementation on `main` or `master`
- If an explicit autonomous orchestrator owns workspace strategy, it must first place the work on a dedicated non-main branch before this skill proceeds

## Integration

**Required workflow skills:**
- **superpowers:openspec-workflow** - Defines the lifecycle this skill executes within
- **superpowers:using-git-worktrees** - Optional when the user or an autonomous orchestrator chooses an isolated workspace before starting
- **superpowers:finishing-a-development-branch** - Complete development after all tasks

## 1. Align workflow source-of-truth files

- [x] 1.1 Update `AGENTS.md` to describe natural-language entry, stage ownership, and user-chosen worktree handling consistently with the new flow.
- [x] 1.2 Update `docs/openspec-workflow.md` so the human-facing guide matches the staged OpenSpec entry, brainstorming boundary, CLI fallbacks, and verification expectations.

## 2. Align repository-local skills

- [x] 2.1 Update `openspec-workflow` and `openspec-autopilot` so their routing, worktree, and verification rules match the documented flow.
- [x] 2.2 Update related execution skills that mention worktrees or OpenSpec handoff so they no longer require automatic worktree creation.

## 3. Restore a coherent OpenSpec repository state

- [x] 3.1 Replace stale or contradictory `openspec/` artifacts with the current change artifacts needed to keep the repository's OpenSpec workflow valid.
- [x] 3.2 Verify the updated docs, skills, and OpenSpec artifacts with the relevant repository checks and OpenSpec validation commands.

# CLAUDE.md

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues (`tedliou/StreamTurbo`), managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Compact Instructions

When compacting, the summary must keep:

- The ticket in progress (issue number and milestone), its branch, and which acceptance criteria are done, partly done or untouched.
- Uncommitted or unpushed work: what changed and whether it passes ruff, pyright and pytest.
- Measured results not yet written to a ticket (bench numbers, power limit in force, observations).
- Open questions waiting on the user, and any decision the user gave that is not yet recorded in an ADR, ticket or memory.
- The very next action.

The spec, tickets, `GLOSSARY.md` and ADRs are the source of truth. The summary points to them by issue number or file name and does not copy their contents.

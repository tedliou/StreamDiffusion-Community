---
name: fork-pr-handoff
description: Use when preparing a pull request from this fork, organizing reviewer context, or responding to review feedback for this repository
---

# Fork PR Handoff

## Overview

Use this skill when preparing changes from the fork for review. Focus on clear
scope, explicit verification, and concise reviewer handoff.

## Purpose

- improve pull request clarity
- reduce reviewer guesswork
- keep follow-up and review response disciplined

## When to Use

- preparing a pull request from the fork
- summarizing changes for reviewers
- responding to code review comments
- documenting follow-up work or known risks

## Inputs to Gather

- branch or change summary
- files touched
- verification results
- known trade-offs, open questions, or deferred work

## Workflow

1. Summarize the change scope in reviewer-friendly language.
2. List the most important files, risks, and verification evidence.
3. Note any unresolved issues or follow-up items.
4. Use the PR and review templates to keep responses structured.
5. Update the handoff summary when review feedback changes the scope.

## Outputs

- a pull request description draft
- a review response draft
- a short maintainer handoff summary

## Repo-Specific Notes

- Keep summaries explicit because multiple agents may contribute to this repo.
- Mention docs impact if README or setup instructions changed.
- Mention workflow impact if `.github/workflows/` changed.
- Avoid overstating verification when GPU or publish checks were not run.

## Related Templates

- `pr-description-template.md`
- `review-response-template.md`

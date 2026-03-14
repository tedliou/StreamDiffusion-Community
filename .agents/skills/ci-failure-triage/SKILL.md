---
name: ci-failure-triage
description: Use when GitHub Actions, release, packaging, or publish runs fail and a structured triage process is needed in this repository
---

# CI Failure Triage

## Overview

Use this skill to debug workflow failures with a repeatable evidence-first
process. Separate confirmed facts from guesses and rank likely causes before
proposing fixes.

## Purpose

- make CI and release failures easier to explain and reproduce
- prevent premature fixes based on weak assumptions
- keep debugging records reusable for future failures

## When to Use

- a GitHub Actions job fails
- the release workflow fails
- packaging or publishing fails
- an environment or dependency change causes unstable automation

## Inputs to Gather

- failing workflow and job names
- error messages and relevant log excerpts
- commit range or recent changes
- reproduction status
- affected secrets, tokens, or publish targets

## Workflow

1. Write down the symptom, failing step, and first known failing run.
2. Gather evidence before changing code or workflow files.
3. List likely causes and rank them by evidence strength.
4. Validate one hypothesis at a time and note what gets ruled out.
5. Record the confirmed root cause, fix candidate, and follow-up verification.

## Outputs

- a filled failure triage summary
- a ranked hypothesis list
- a root-cause log with confirmed findings and next actions

## Repo-Specific Notes

- Check whether the failure touches `.github/workflows/release.yml`.
- Treat publish failures and secret-related failures as high priority.
- Prefer Linux and Bash assumptions when reasoning about workflow behavior.
- If the change touches Python packaging, review the package and documentation
  paths together.

## Related Templates

- `failure-triage-template.md`
- `root-cause-log-template.md`

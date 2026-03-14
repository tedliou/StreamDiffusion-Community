---
name: docs-consistency
description: Use when updating README files, setup steps, release notes, or multilingual documentation in this repository
---

# Docs Consistency

## Overview

Use this skill when documentation changes need to stay aligned with repository
behavior. Focus on command validity, platform wording, and sync across related
docs.

## Purpose

- keep documentation accurate and consistent
- reduce drift between docs, workflows, and code
- preserve Linux-first guidance while documenting exceptions clearly

## When to Use

- editing README files
- changing install or setup instructions
- documenting workflow or release behavior
- syncing multilingual documentation after source changes

## Inputs to Gather

- affected documentation files
- related code or workflow files
- platform assumptions
- translated or duplicated docs that may also need updates

## Workflow

1. Identify the source document and all related documents that may drift.
2. Check whether commands, paths, and prerequisites still match the repository.
3. Review platform wording for Linux, Ubuntu, WSL2, and Bash compatibility.
4. Record which translated or parallel docs need sync work.
5. Note any unverified commands or intentionally deferred doc updates.

## Outputs

- a documentation sync summary
- a list of files that should be updated together
- notes on platform-specific or translation-specific risk

## Repo-Specific Notes

- Prefer Ubuntu, WSL2, Bash, and POSIX paths in examples.
- Avoid Windows-first guidance unless end-user compatibility requires it.
- Check whether README changes should also affect `README-ja.md` and
  `README-ko.md`.
- Keep commands consistent with actual repository workflows and packaging files.

## Related Templates

- `docs-sync-checklist.md`
- `platform-compatibility-checklist.md`

---
name: ci-workflow-change
description: Use when creating or modifying GitHub Actions workflows, release jobs, permissions, caches, triggers, or publishing behavior in this repository
---

# CI Workflow Change

## Overview

Use this skill when changing workflow behavior in `.github/workflows/`. Focus on
safety, least privilege, and downstream release impact before editing YAML.

## Purpose

- keep workflow changes small, explicit, and reviewable
- catch trigger, permission, cache, and publish risks early
- preserve repository-specific expectations for Linux-first development

## When to Use

- adding a new workflow
- editing triggers, jobs, matrices, runners, or caches
- changing release or publish behavior
- updating artifact handling, permissions, or secrets

## Inputs to Gather

- target workflow files
- related release or packaging files
- current trigger conditions
- required secrets and repository permissions
- expected verification commands or checks

## Workflow

1. Read the target workflow and list the behavior that will change.
2. Check whether the change affects triggers, concurrency, caching, artifacts,
   permissions, or publishing.
3. Review repository-specific impact, especially release behavior and Linux-only
   assumptions.
4. Use the related checklists before finalizing the change.
5. Record open risks and what should be verified after the edit.

## Outputs

- a concise summary of the intended workflow change
- a completed workflow review checklist
- explicit notes for permission, secret, and release risk

## Repo-Specific Notes

- Prefer Ubuntu, Bash, and POSIX paths in workflow steps.
- Review changes against `.github/workflows/release.yml` if release behavior may
  be affected.
- Avoid hidden coupling between core package workflows, demos, and frontends.
- Treat publishing credentials and release targets as high-sensitivity inputs.

## Related Templates

- `workflow-change-checklist.md`
- `permissions-and-secrets-checklist.md`

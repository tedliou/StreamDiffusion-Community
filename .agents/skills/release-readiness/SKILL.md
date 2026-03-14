---
name: release-readiness
description: Use when preparing tags, builds, packaging, or publish steps for a release in this repository
---

# Release Readiness

## Overview

Use this skill before a release or publish action. Confirm the tag, package
inputs, publish target, and rollback posture before treating the release as
ready.

## Purpose

- reduce avoidable release mistakes
- make publish assumptions explicit
- improve confidence before tagging or publishing

## When to Use

- before creating a release tag
- before publishing artifacts
- before changing release metadata or package behavior
- before modifying publish targets or release secrets

## Inputs to Gather

- target version or tag
- release workflow files
- package build inputs
- publish destination and credentials
- verification expectations

## Workflow

1. Confirm the version, tag format, and intended publish target.
2. Review build inputs, packaging assumptions, and release workflow behavior.
3. Check secret dependencies, artifact expectations, and rollback options.
4. Use the related checklists to record open risks.
5. Produce a go, no-go, or needs-more-verification recommendation.

## Outputs

- a completed release readiness checklist
- a publish risk summary
- a short release recommendation

## Repo-Specific Notes

- The current release workflow in `.github/workflows/release.yml` publishes to
  TestPyPI.
- Review whether a change assumes `setup.py` packaging behavior.
- Confirm release instructions stay aligned with repository documentation.
- Treat token scope and publish destination mismatches as blocking issues.

## Related Templates

- `release-checklist.md`
- `publish-risk-checklist.md`

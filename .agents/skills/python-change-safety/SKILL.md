---
name: python-change-safety
description: Use when modifying Python package code, demos, examples, dependencies, or acceleration-sensitive runtime paths in this repository
---

# Python Change Safety

## Overview

Use this skill when touching Python behavior in the package, examples, or demos.
Focus on impact boundaries, runtime assumptions, and realistic verification.

## Purpose

- reduce unintended breakage in Python changes
- surface environment-sensitive risks early
- connect code edits with verification and documentation follow-through

## When to Use

- editing code under `src/`
- changing Python examples or demos
- modifying dependencies or packaging assumptions
- touching GPU, CUDA, TensorRT, ONNX, or acceleration-related paths

## Inputs to Gather

- affected files and modules
- runtime assumptions and environment constraints
- lint or test commands already used by the repository
- related documentation examples

## Workflow

1. Identify the behavior change and who depends on it.
2. Review whether the change affects runtime-sensitive or packaging-sensitive
   paths.
3. List the smallest useful verification steps for the change.
4. Check whether docs, examples, or release behavior also need updates.
5. Record caveats if verification is partial or environment-limited.

## Outputs

- a concise impact summary
- a targeted verification checklist
- explicit notes about environment-sensitive risk

## Repo-Specific Notes

- Follow the repository's Linux and WSL2 guidance for commands and examples.
- Respect boundaries between core package code, demos, and frontends.
- Review `pyproject.toml` before claiming lint or formatting expectations.
- Treat acceleration-related paths as high sensitivity even for small edits.

## Related Templates

- `change-impact-checklist.md`
- `verification-checklist.md`

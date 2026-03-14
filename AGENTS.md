# AGENTS.md

## Development Environment

- This project must be developed in Linux.
- On Windows, use WSL2 with Ubuntu as the supported development environment.
- Prefer Bash, POSIX paths, and Linux-native tooling in all commands, scripts, docs, and examples.
- Do not add Windows-only workflows, PowerShell-first instructions, or backslash-style paths unless explicitly required for end-user compatibility.

## Project Shape

- `src/streamdiffusion/`: core Python package and acceleration-related runtime code.
- `models/`: local model weight placeholders and runtime assets.
- `utils/`: small helper utilities outside the main package.
- `assets/`, `images/`: documentation media and sample inputs retained for the core repository.
- `openspec/`: the authoritative workflow state for formal change planning and execution.

## Tech Stack

- Primary runtime: Python 3.10+
- Environment and dependency management: `uv`
- ML stack: PyTorch, Diffusers, Transformers, Accelerate, xFormers
- Performance path: CUDA, TensorRT, ONNX/ONNX Runtime, stable-fast

## Special Notes

- This repository is expected to undergo major refactoring. Favor broadly applicable guidance over assumptions tied to the current layout.
- Multiple AI agents may contribute here. Keep changes small, explicit, and easy to review; avoid hidden coupling and surprising conventions.
- Preserve clear boundaries between the core library, repository tooling, and any future reintroduced demos or frontends.
- Prefer portable, reproducible Linux workflows, especially for GPU, CUDA, and TensorRT related changes.
- When documenting commands or setup steps, default to Ubuntu/WSL2-compatible instructions.

## Commit Messages

- Follow the recent repository commit style for manual commits.
- Write commit subjects in English.
- Prefer Conventional Commit prefixes such as `feat:`, `fix:`, `refactor:`, and `chore:`.
- Add a scope when it materially clarifies the area being changed, for example `chore(openspec): ...`.
- Keep the subject to a single concise line and use an imperative verb phrase such as `adopt`, `archive`, `ignore`, or `propose`.
- Prefer lowercase subjects after the prefix unless a proper noun or acronym requires capitalization.
- Avoid vague commit subjects such as `update`, `try again`, or `customize` when a more specific action can be named.
- For merge commits, keep the platform-generated message unless the workflow explicitly requires otherwise.

## Skills

- Repository-local skills live in `./.agents/skills/`.
- Agents must discover and load skills from `./.agents/skills/` before checking any home-directory, global, or tool-managed skill installation.
- Each skill is stored at `./.agents/skills/<skill-name>/SKILL.md`.
- If the same skill exists in both the repository and a global location, always use the repository copy.
- Keep skill usage self-contained to this project. Do not depend on `C:/Users/Ted/.codex/superpowers` or any other machine-local `superpowers` checkout.
- Use the repository-local `openspec-autopilot` skill when a single natural-language request should drive the full OpenSpec workflow with guided pause points.
- Use the repository-local `resolving-reported-issues` skill when a user reports a bug or failure and wants the agent to carry it from clarification through verified resolution.

## OpenSpec Workflow

- OpenSpec is the only source of truth for formal requirements, design, task breakdown, verification, and archive state.
- A single natural-language request may enter the workflow through the repository-local `openspec-autopilot` orchestration path.
- A single natural-language issue report may enter the workflow through the repository-local `resolving-reported-issues` orchestration path.
- The orchestrated path must first ask whether to use SDD, TDD, and OpenSpec at all, so doc-only edits, one-off verification requests, and tool runs can stay on a lighter path when appropriate.
- If a request is still fuzzy after that preflight, use `resolving-reported-issues` for reported bugs and unexpected behavior, or use `brainstorming` to shape feature and workflow changes before proposal work.
- For reported bugs and unexpected behavior, establish reproduction or an evidence-backed change strategy before opening the OpenSpec proposal stage.
- When `resolving-reported-issues` runs in autonomous mode, it must create and switch to an auto-named working branch before making OpenSpec artifacts, code changes, or commits.
- Autonomous issue resolution must never commit directly to `main` or `master`.
- For feature work or behavior changes, follow the OpenSpec command flow: `/opsx:propose` -> `/opsx:apply` -> `/opsx:verify` -> `/opsx:archive`.
- When a user invokes an `/opsx:*` command directly, that OpenSpec command owns the workflow. Repository-local skills must not override it with an alternate spec or planning process.
- Repository-local skills may help clarify requirements before proposal time or improve execution quality during implementation, but they must not create parallel spec or plan artifacts outside OpenSpec.
- The orchestrated path must pause before major stage transitions and key workspace or commit branch points with recommended options and short examples.
- Exception: when the user explicitly invokes `resolving-reported-issues`, the agent should auto-select the best workflow option and continue without manual stage approvals unless blocked by missing critical information or unusual safety risk.
- When `/opsx:*` commands are unavailable in the current tool, use the documented OpenSpec CLI or repository skill fallback for the same stage instead of creating a parallel process.
- `docs/plans/` and other ad-hoc planning locations are deprecated and must not be used as authoritative workflow artifacts.
- Worktree handling is a workflow decision point before implementation, but the user chooses the workspace strategy after the agent explains the state:
  - If the OpenSpec change files are still uncommitted, stay in the current workspace or commit them first.
  - If the OpenSpec change files are committed and isolation may help, present the worktree option and invoke the repository worktree workflow only if the user chooses it.
- Human-facing onboarding and command examples belong in `docs/`, not here.

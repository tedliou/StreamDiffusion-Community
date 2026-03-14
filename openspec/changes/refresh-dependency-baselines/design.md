## Context

The repository already uses `uv` as the supported environment manager, but its dependency policy is inconsistent. Unpinned packages in `pyproject.toml` resolve to current versions in `uv.lock`, while several explicitly pinned dependencies remain at much older baselines, notably `diffusers==0.24.0`, `onnx==1.15.0`, `onnxruntime==1.16.3`, and `protobuf==3.20.2`. Those pins affect both optional acceleration paths and the shared dev extra, so the mismatch is visible to contributors even when the default environment stays intentionally lightweight.

This change needs to modernize the declared baselines without accidentally widening scope into a larger runtime refactor. The repository still treats `torch` and `xformers` as opt-in extras, and acceleration-sensitive paths remain environment dependent.

## Goals / Non-Goals

**Goals:**
- Refresh obviously stale pinned dependency baselines in `pyproject.toml`.
- Regenerate `uv.lock` so the lockfile reflects the new declared policy.
- Add lightweight regression coverage for dependency metadata so future stale pins or diverging extras are caught in CI and local verification.
- Preserve the current repository shape where heavyweight runtime dependencies remain optional extras rather than default install requirements.

**Non-Goals:**
- Refactor runtime code to adopt every new upstream API pattern.
- Reintroduce demos, publishing workflows, or a broader packaging redesign.
- Guarantee full GPU or TensorRT runtime verification in environments that do not provide those stacks.

## Decisions

### Update the stale hard-pinned baselines, not every dependency declaration

The change will focus on dependencies that are explicitly pinned to older versions in `pyproject.toml` and shared extras. This keeps the scope reviewable and aligned with the reported issue. Unpinned packages such as `fire`, `numpy`, and `transformers` will continue to rely on `uv` resolution unless a compatibility issue requires further action.

Alternative considered: add upper and lower bounds across the whole dependency set. This was rejected because it would create a much larger compatibility surface and make the maintenance change harder to validate.

### Keep optional dependency groups aligned through shared assertions

The TensorRT extra and the dev extra currently duplicate the same pinned acceleration dependencies. The implementation will keep those shared baselines synchronized and add a test that asserts the duplicated entries stay aligned. This reduces the chance that one contributor path receives newer packages while another silently stays stale.

Alternative considered: introduce a custom dependency-generation script. This was rejected because the repository currently keeps dependency metadata in plain `pyproject.toml`, and a metadata regression test is the smaller, clearer safeguard.

### Verify dependency policy with metadata-focused tests

Because runtime verification for `torch`, CUDA, ONNX Runtime, and TensorRT is environment sensitive, the safest always-on regression coverage is a small test that parses `pyproject.toml` and asserts the maintained dependency baselines and shared extras layout. The lockfile regeneration itself will provide the second layer of evidence that the updated policy resolves under `uv`.

Alternative considered: rely only on `uv lock` or `uv sync` success. This was rejected because it would not flag future regressions where someone accidentally restores a stale hard pin or lets duplicated extras drift apart.

## Risks / Trade-offs

- Updated upstream packages may expose runtime API differences beyond what metadata checks catch. -> Mitigation: keep the upgrade bounded, run import-oriented verification where practical, and record any environment-limited verification gaps.
- Regenerating `uv.lock` can produce a broad diff because of transitive resolver updates. -> Mitigation: keep the declarative changes small and review only the dependency areas touched by the updated policy.
- TensorRT-related dependencies may still require narrower compatibility than their latest PyPI releases in some GPU environments. -> Mitigation: document that the change validates repository metadata and import-level behavior, not full accelerator runtime execution on every machine.

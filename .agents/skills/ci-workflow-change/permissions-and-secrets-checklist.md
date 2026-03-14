# Permissions And Secrets Checklist

- [ ] List the minimum job or workflow permissions required.
- [ ] Confirm no permission is broader than necessary.
- [ ] Identify all secrets referenced by name.
- [ ] Confirm the secret names match repository settings and documentation.
- [ ] Check whether any secret is used in logs, environment dumps, or debug output.
- [ ] Review whether `GITHUB_TOKEN` scope is sufficient before adding custom tokens.
- [ ] Confirm the publish target is correct for the intended workflow run.
- [ ] Check whether the change affects TestPyPI, PyPI, or both.
- [ ] Review artifact provenance and publish prerequisites.
- [ ] Note rollback or disable steps if the new workflow behavior misfires.

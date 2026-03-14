# Workflow Change Checklist

- [ ] Identify the exact workflow files and jobs affected.
- [ ] Confirm whether triggers are changing (`push`, `pull_request`, `workflow_dispatch`, tags).
- [ ] Confirm whether the runner choice still matches repository needs.
- [ ] Review job names and step names for clarity.
- [ ] Check whether setup steps assume Ubuntu, Bash, or POSIX paths.
- [ ] Review dependency installation steps for reproducibility.
- [ ] Check cache keys, cache scope, and cache invalidation behavior.
- [ ] Review matrix expansion for runtime cost and maintenance burden.
- [ ] Confirm whether artifact upload, download, or retention behavior changes.
- [ ] Check whether concurrency, retries, or timeouts need updates.
- [ ] Review whether the change can affect release or packaging behavior.
- [ ] List the exact verification steps to run after the workflow edit.

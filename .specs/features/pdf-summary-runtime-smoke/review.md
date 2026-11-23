# Review

**Verdict:** The CI follow-up matches the request. Pull request builds use `linux/amd64`, while pushes to `main` continue to build both `linux/amd64` and `linux/arm64`; tagged image publishing also remains multi-architecture. The final-runtime summary smoke check is still part of the Docker build and runs with network disabled.

## Findings

No findings.

## Evidence

- `.github/workflows/ci.yml` triggers on `pull_request` and pushes to `main`. The platform expression selects `linux/amd64` for pull requests; for the `push` event it selects `linux/amd64,linux/arm64`.
- `.github/workflows/publish-image.yml` still sets `platforms: linux/amd64,linux/arm64` for tagged image builds.
- `Dockerfile` copies `docker/summary-smoke.py` into the final runtime stage and runs it with `/app/.venv/bin/python` via `RUN --network=none`. The inference check is therefore still included in PR image builds, without network access.
- The smoke script calls `_abstractive_summary` with sample text and exits unsuccessfully if inference returns no text.

The expression's branches match the workflow's declared events. No application runtime behavior or supported image architecture is changed by this CI-only platform selection. No test or Docker build was run as part of this read-only review.

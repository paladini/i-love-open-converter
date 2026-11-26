# Repository Agent Instructions

## Release & Container Publishing Policy

Every new version release **must** be published to **both GitHub (GitHub Release + GHCR) and Docker Hub** (`docker.io/paladini/i-love-open-converter`), including multi-architecture (`linux/amd64` and `linux/arm64`) manifests for:
- `<version>` (e.g. `1.2.0`)
- `<major>.<minor>` (e.g. `1.2`)
- `latest`

### Required Release Checklist

1. **Version & lockfile:**
   - Bump `version` in `pyproject.toml`.
   - Run `uv lock` so `uv.lock` matches `pyproject.toml` (CI runs `uv sync --all-groups --locked`).
   - Move `## [Unreleased]` entries to `## [<version>] - YYYY-MM-DD` in `CHANGELOG.md`.
2. **Local verification:**
   - `uv sync --all-groups --locked`
   - `uv run ruff check .`
   - `uv run pytest -q -rs`
3. **GitHub Release & GHCR:**
   - Commit and push to `main`.
   - Create and push tag `v<version>` (`git tag v<version> && git push origin v<version>`).
   - Create the GitHub Release for `v<version>` (`gh release create v<version> ...`).
   - Wait for `.github/workflows/publish-image.yml` on `v<version>` to succeed and publish `ghcr.io/paladini/i-love-open-converter:<version>`, `:<minor>`, and `:latest`.
4. **Docker Hub (`paladini/i-love-open-converter`):**
   - Verify that `docker.io/paladini/i-love-open-converter` received `<version>`, `<minor>`, and `latest` multi-arch manifests.
   - Note: `.github/workflows/publish-image.yml` skips Docker Hub if `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` repository secrets are not set. If Docker Hub was skipped or not updated by CI, run `.\scripts\publish-container.ps1 -Version <version>` locally (requires `docker login` and `docker buildx`), or explicitly flag the missing Docker Hub publication to the maintainer.

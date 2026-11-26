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
3. **GitHub Release & Container Publishing (prefer local to save GitHub Actions quota):**
   - Commit and push to `main`.
   - Create and push tag `v<version>` (`git tag v<version> && git push origin v<version>`).
   - Create the GitHub Release for `v<version>` (`gh release create v<version> ...`).
   - Prefer building and publishing container images **locally** (e.g. `.\scripts\publish-container.ps1 -Version <version>` for Docker Hub, or `docker buildx` directly for GHCR + Docker Hub) to avoid unnecessary GitHub Actions minutes/limits.
4. **Docker Hub (`paladini/i-love-open-converter`) & GHCR (`ghcr.io/paladini/i-love-open-converter`):**
   - Verify that **both** `ghcr.io/paladini/i-love-open-converter` and `docker.io/paladini/i-love-open-converter` received `<version>`, `<minor>`, and `latest` multi-arch manifests.
   - Note: `.github/workflows/publish-image.yml` skips Docker Hub if `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` repository secrets are not set, so always verify Docker Hub and run `.\scripts\publish-container.ps1 -Version <version>` locally (requires `docker login` and `docker buildx`).

# State

**Last Updated:** 2026-11-26T15:22:00-03:00
**Current Work:** `ui-ilovepdf-experience` — Completed & Verified (PR #64)

---

## Recent Decisions (Last 60 days)

### AD-024: Domain-Adaptive Studio Workspace & Unified Tool Shell (2026-11-26)

- **Decision:** Introduce a 2-column Studio Workspace (`#converter-panel`) with dynamic OKLCH domain theming (`data-domain="pdf|image"`), miniature paper-sheet/thumbnail file cards with per-item batch removal, bespoke inline SVG icons for all 50 catalog cards, instant tool search (`[data-catalog-search]`), and universal `.pdf-upload` drag-and-drop (`tool-shell.js`) across all dedicated `/tools/*` routes.
- **Reason:** Aligns visual hierarchy and interaction ergonomics with iLovePDF and iLoveIMG while remaining 100% local and self-hosted.
- **Trade-off:** Kept sidebar form controls visible in the DOM prior to file upload so existing Playwright E2E tests (`tests/test_mobile_ui.py`) remain 100% compatible without weakening test assertions.
- **Impact:** Zero external CDN dependencies, zero regressions in `test_conversion_coverage.py` or `test_api.py`, and responsive 360px–1440px+ support.

---

## Active Blockers

None.

---

## Lessons Learned

### L-001: Windows File Locks When Running Concurrent `uv run` Daemons

- **Context:** Starting a second `uv run` background daemon on Windows while `uvicorn` is already running from `.venv`.
- **Problem:** `uv run` without `--no-sync` attempted to reinstall `pydantic_core`, hitting `os error 5 (Access is denied)` on `_pydantic_core.*.pyd`.
- **Solution:** Run `uv sync --all-groups --locked` once before starting daemons, then invoke `uv run --no-sync` or `.venv\Scripts\python.exe` directly for concurrent processes.
- **Prevents:** Partial package uninstallation in `.venv` on Windows.

---

## Preferences

**Model Guidance Shown:** 2026-11-26

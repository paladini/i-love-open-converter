# Testing Infrastructure

## Test Frameworks

- **Unit & Integration:** `pytest` + FastAPI `TestClient`
- **Browser E2E:** `playwright.sync_api` (Chromium headless)
- **Static Quality:** `ruff check .` + `ruff format --check`

## Test Coverage Matrix

| Code Layer | Required Test Type | Location Pattern | Run Command |
| --- | --- | --- | --- |
| Conversion engines (`*_ops.py`) | unit + integration | `tests/test_*_ops.py`, `tests/test_pdf_*.py` | `uv run pytest` |
| HTTP routes & queue (`main.py`, `worker.py`) | integration | `tests/test_api.py`, `tests/test_conversion_coverage.py` | `uv run pytest tests/test_api.py tests/test_conversion_coverage.py` |
| Templates, CSS & JS UI (`templates/`, `static/`) | integration + e2e | `tests/test_mobile_ui.py`, `tests/test_conversion_coverage.py`, `tests/test_image_editor.py` | `uv run pytest tests/test_mobile_ui.py tests/test_conversion_coverage.py` |

## Parallelism Assessment

| Test Type | Parallel-Safe? | Isolation Model | Evidence |
| --- | --- | --- | --- |
| Pytest unit/integration | Yes | Per-test `tmp_path` `Settings` fixture with isolated SQLite DB and jobs directory | `tests/conftest.py` |
| Playwright E2E | Yes | Ephemeral `127.0.0.1:0` socket per test via `_serve_app(settings)` | `tests/test_mobile_ui.py` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Template/CSS/JS contract verification | `uv run ruff check . && uv run pytest tests/test_conversion_coverage.py tests/test_mobile_ui.py` |
| Full | Feature completion | `uv run ruff check . && uv run ruff format --check tests/ src/ && uv run pytest -q -rs` |
| Build | Pre-PR / CI parity | `uv run ruff check . && uv run ruff format --check . && uv run pytest -q -rs --junitxml=pytest-results.xml` |

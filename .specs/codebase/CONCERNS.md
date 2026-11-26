# Codebase Concerns & Guardrails

## 1. Strict Template & CSS Test Contracts
- **Evidence:**
  - `tests/test_api.py:1041` asserts exact catalog card count (`response.text.count('class="tool-card"') + response.text.count('class="tool-card ') == 50`).
  - `tests/test_conversion_coverage.py:545` parses every `<input>`, `<select>`, and `<textarea>` with an `id` attribute across all `templates/*.html` and requires exact membership in `FORM_OPTION_OPERATIONS | NON_OPTION_FORM_CONTROLS`.
  - `tests/test_image_editor.py:540` asserts `".operation-options { display: flex; flex-wrap: wrap;" in css`.
- **Mitigation:** Preserve all existing form control IDs, exact `.tool-card` class prefixes on the 50 catalog items, and `.operation-options` flex-wrap rule whenever evolving the UI.

## 2. Windows File Locking with Concurrent `uv run` Daemons
- **Evidence:** Running `uv run` while another background process holds `.venv\Lib\site-packages\pydantic_core\_pydantic_core.*.pyd` open on Windows can trigger `os error 5 (Access is denied)` if `uv` attempts an environment re-sync.
- **Mitigation:** Sync `.venv` once with `uv sync --all-groups --locked`, and launch concurrent long-running local daemons (`uvicorn` + `worker`) either with `uv run --no-sync` or directly via `.venv\Scripts\python.exe`.

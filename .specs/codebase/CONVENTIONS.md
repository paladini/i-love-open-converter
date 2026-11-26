# Code Conventions

## Naming Conventions

- **Python Modules & Functions:** `snake_case` (`pdf_ops.py`, `image_ops.py`, `parse_limited_upload_form`).
- **Templates & Static JS:** `kebab-case` (`pdf-to-word.html`, `pdf-to-word.js`, `scan-to-pdf.html`).
- **Operation Identifiers:** Dot-namespaced `domain.action` strings (`image.convert`, `pdf.compress`, `html.to_pdf`).
- **CSS Classes:** Semantic `kebab-case` (`site-header`, `converter-panel`, `workspace-grid`, `tool-card`).

## Frontend & Localization Conventions

- **Zero External Assets:** Templates must never load external `https://` stylesheets, scripts, or fonts (`tests/test_api.py` enforces `"https://" not in response.text` on `/`).
- **Bilingual Attributes:** Elements use either `data-i18n="<key>"` (resolved via `messages[lang]` in `app.js`) or inline `data-pt="..." data-en="..."` attributes for static bilingual copy.
- **Form Option Inventory Contract:** Every `<input>`, `<select>`, and `<textarea>` with an `id` attribute (excluding `type="file"`) across `templates/*.html` must be registered in `FORM_OPTION_OPERATIONS` or `NON_OPTION_FORM_CONTROLS` in `tests/test_conversion_coverage.py`.

## Python Style & Formatting

- Enforced via Ruff (`uv run ruff check .` and `uv run ruff format --check` on changed `.py` files in CI).
- Line length: 100 characters (`pyproject.toml`).

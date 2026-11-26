# Tasks: Interactive Visual Crop with Handles (`#65`)

- [x] **T1:** Vendor Cropper.js v1.6.x (`cropper.min.js`, `cropper.min.css`) into `src/i_love_open_converter/static/vendor/` and update `THIRD_PARTY_NOTICES.md`.
- [x] **T2:** Add image crop stage (`#image-crop-editor`, `#image-crop-preview`), aspect ratio preset controls (`data-option="crop-aspect"`), vendor assets, and i18n strings (`pt-BR` / `en`) in `index.html` and `app.js`, with bidirectional Cropper.js sync.
- [x] **T3:** Integrate Cropper.js into `pdf-crop.html` and `pdf-crop.js` with aspect ratio presets, bidirectional percentage sync, and page-navigation preservation.
- [x] **T4:** Add responsive CSS rules in `app.css` for `.image-crop-editor`, `.crop-aspect-presets`, and Cropper.js container sizing on desktop and mobile.
- [x] **T5:** Add Playwright E2E tests in `tests/test_visual_crop.py` (desktop + mobile) verifying interactive handles, drag/resize -> input sync, input -> cropper sync, aspect ratio presets, and end-to-end job execution for both `image.crop` and `pdf.crop`.
- [x] **T6:** Run full verification (`uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q -rs`).

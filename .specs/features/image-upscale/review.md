# Review

**Verdict:** The feature runs through the existing local job flow and the full test suite, Ruff, and JavaScript syntax check pass. The browser review confirmed PT-BR and English labels, the 2x/4x selector, PNG default, one-file selection, and no horizontal overflow at the 360px viewport override (the browser reported 361 CSS px; document width was 345px). Two gaps remain against the approved plan and its problem statement.

## Findings

- **[P2] Show the predicted output dimensions before download.** The problem statement says visitors can see exact output dimensions before downloading. Selecting `Melhorar imagem` currently exposes the scale but does not calculate or show output width and height after a file is selected. The submit handler in `src/i_love_open_converter/static/js/app.js` sends the selected scale without displaying predicted dimensions; `tests/test_api.py::test_upscale_job_uses_selected_scale_and_rejects_bad_options` checks the final downloaded image dimensions only after processing. A visitor cannot see the expected dimensions before downloading.
- **[P2] Add a regression assertion for the resampling and sharpening rule.** Criterion 3 requires Lanczos followed by the fixed unsharp mask. The implementation currently calls `Image.Resampling.LANCZOS` and `_apply_unsharp_mask`, but the upscale tests assert dimensions, modes, and alpha only (`tests/test_image_ops.py::test_upscale_uses_selected_dimensions_and_preserves_alpha`, `test_upscale_converts_palette_transparency_before_lanczos_resampling`, and `test_upscale_applies_exif_orientation_before_multiplying_dimensions`). Those assertions would still pass if the resampling filter or sharpening step changed, so this named rule is not protected by a failing regression test.

## Checks

- `rtk uv run pytest -q`: passed (149 tests).
- `rtk uv run ruff check .`: passed.
- `rtk node --check src/i_love_open_converter/static/js/app.js`: passed.
- Browser at `http://127.0.0.1:8793/`, using the isolated `.specs/features/image-upscale/review-data` directory: verified the active tool in Portuguese and English at the mobile viewport override; all three controls were visible and document width stayed below viewport width. The throwaway data directory was removed after review.
- No code, commits, pushes, or changes to app data were made by the reviewer.

## Author response

- **[P2] Predicted output dimensions:** addressed in the single fix pass. The browser now reads the selected image's oriented dimensions locally, applies the chosen scale, and displays the exact output width, height, and megapixels before submission. The preview updates when scale changes, hides when the file is removed or another tool is selected, and is localized in PT-BR and English.
- **[P2] Lanczos and sharpening regression:** addressed in the single fix pass with a test that asserts the upscale path calls Pillow Lanczos resize and then the unsharp-mask helper.

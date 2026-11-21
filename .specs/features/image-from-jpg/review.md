# Independent review: Convert JPG to PNG or animated GIF

**Verdict: changes requested.** The requested JPG to PNG and animated GIF flows work in the covered cases, but the animation pixel cap is checked only after every uploaded source has been decoded and retained in memory.

## Request, sentence by sentence

1. `Converter de JPG Converta imagens JPG para PNG ou GIF.` The active catalog card offers PNG and GIF targets. One JPEG converts to a PNG or a one-frame GIF; batches convert to PNGs or one GIF.
2. `Selecione vários arquivos JPG para criar um GIF animado!` The GIF worker preserves upload order and creates a looping animation from the selected JPEGs. The animation test reads each colored frame and checks its delay and loop setting.

## Findings

### P1 - Aggregate GIF bound is enforced after decoding all images

In `src/i_love_open_converter/image_ops.py:120-128`, `create_animated_gif` opens each source and appends `ImageOps.exif_transpose(opened).convert("RGB")` to `opened_images`; only after all inputs have been converted and held in memory does it check the total canvas pixels against `MAX_GIF_ANIMATION_PIXELS`. An attacker or ordinary large batch can therefore upload as many as 10 JPEGs, each within the per-image decompression limit, and force all decoded RGB images into memory before the 25-million aggregate-frame-pixel rejection. At 50 million pixels per input, ten retained RGB frames alone can require about 1.5 GB, before canvas frames and encoder buffers. The limit prevents an oversized output, but it does not prevent the memory exhaustion it was added to bound. Check the oriented canvas and aggregate frame count before retaining decoded pixels, and add a regression that would fail if decoding occurs before the aggregate limit check.

## UI inspection

Started the app on port 8777 with throwaway data in `.specs/features/image-from-jpg/review-data`, selected `Converter de JPG`, and inspected PT-BR and English at a 360 px viewport. The active tool, JPG-only label, PNG/GIF target choices and localized title were visible; the page fit the viewport without horizontal page overflow. The actual file input `accept` value in English was `.jpg,.jpeg,image/jpeg`. No design captures are listed by the plan. Stopped the app and removed only the throwaway review data.

## Test mapping

| Plan rule | Test evidence | Would fail if rule were wrong? |
| --- | --- | --- |
| S1.1 active tool, JPG input and PNG/GIF options | `test_from_jpg_catalog_has_correct_filter_and_format_choices`; browser showed localized form and both targets in PT-BR/EN | Partly. Static test checks card/format markup/filter script; browser confirms visible localized UI. No assertion for localized queued/error status. |
| S1.2 single JPEG to PNG, dimensions | `test_single_jpeg_converts_to_png_with_source_dimensions` | Yes for output format and dimensions; it does not compare image pixels. |
| S1.3 multiple JPEGs to ordered sanitized PNG ZIP | `test_jpeg_batch_to_png_returns_ordered_sanitized_zip` | Yes for ZIP names/order, sanitization and dimensions. It does not verify each output's pixel colors. |
| S1.4 reject non-JPEG, animated, malformed or over-bound input without partial output | `test_from_jpg_rejects_non_jpeg_content_before_creating_a_job`; general image inspection tests cover invalid bytes and animated GIF | Partly. Non-JPEG is covered through the API; malformed JPEG and image pixel bounds are not tested through this operation, nor is a worker partial-download assertion for those failures. |
| S2.5 animation order, delay and infinite loop | `test_multiple_jpegs_create_ordered_animation_with_fixed_canvas` | Yes for a two-frame batch. |
| S2.6 common max-size canvas, centering and white padding | `test_multiple_jpegs_create_ordered_animation_with_fixed_canvas` | Yes for the two differing dimensions used by the test. |
| S2.7 one-frame GIF | `test_one_jpeg_with_gif_output_creates_one_frame` | Yes. |
| S2.8 25-million aggregate pixel cap with no partial output | `test_gif_animation_rejects_aggregate_pixel_limit` | Partly. It proves the helper raises and does not create the destination, but not that the cap is checked before decoding/retaining all source images. This is the P1 finding. |
| S2.9 reject >10 files or malformed options before job creation | `test_gif_output_rejects_more_than_ten_jpegs`; parametrized `test_from_jpg_rejects_unsupported_output_format` | Partly. The count is covered before job creation; unsupported target values are tested, but malformed JSON/options are not specifically exercised for this operation. |
| S2.10 localized, responsive UI and correct filter/targets | Browser inspection at 360 px, PT-BR and EN; `test_from_jpg_catalog_has_correct_filter_and_format_choices` | Browser confirmed the visible result and actual `accept` filter; the static test would not catch responsive overflow or localization regressions. |

## Verification

- `uv run pytest -q tests/test_image_from_jpg.py tests/test_image_ops.py`: 18 passed.
- `uv run pytest -q`: passed, 100%.
- Browser reviewed on port 8777 with a throwaway database and a 360 px viewport in PT-BR and English.

## Author fix pass

Reworked GIF creation into a metadata preflight and a bounded decode pass. The worker now checks JPEG format, orientation-adjusted dimensions and aggregate canvas pixels from headers and EXIF before decoding. It creates each output canvas frame one at a time and closes temporary image objects promptly. A regression replaces Pillow pixel loading with a failure, proving an over-limit animation is rejected before decode; another worker test proves the failed job has no downloadable partial output. Added malformed-options and per-image pixel-limit API regressions. No review finding remains open.

Validation after the fix: the full `uv run pytest -q` suite passed; `uv run ruff check .`, JavaScript syntax check, diff check and TLC plan validator all passed.

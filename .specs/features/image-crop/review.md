# Independent review: image crop

**Verdict: changes requested.** The numeric rectangle crop works for supported static formats, including EXIF-oriented inputs, but the user request explicitly includes GIF and this implementation rejects GIF.

## Request, sentence by sentence

1. `Recortar IMAGEM` is present as an active catalog item and selects the crop panel.
2. `Recorte uma imagem definindo um retângulo em pixels.` is implemented with left, top, width and height inputs; the worker applies EXIF orientation, checks bounds, and crops. The focused tests cover oriented pixel output, malformed options, batches and out-of-bounds failure.
3. `Recorte imagens JPG, PNG ou GIF.` JPG/JPEG and PNG are accepted; GIF is not. `image_ops.INPUT_FORMATS` is `{JPEG, PNG, WEBP, BMP, TIFF}`, and both upload inspection and worker processing reject GIF. The approved plan documents this divergence but the plan's static-codec decision does not satisfy the quoted request. This is a product-scope mismatch requiring GIF support (at least static GIF) or an explicit user decision to remove GIF from the request.

## Findings

### P1 - GIF from the request is not supported

Evidence: `src/i_love_open_converter/image_ops.py` excludes GIF from `INPUT_FORMATS`; `inspect_image` and `process_image` reject it. The upload UI likewise advertises JPG, PNG, WebP, BMP and TIFF. The plan's “Differences from the source” records the exclusion, but it cannot supersede the request's explicit GIF requirement. Add static GIF support (with animation behavior defined) or get the user's scope decision before closing this feature.

### P2 - Several acceptance rules have no regression test

`tests/test_image_crop.py` covers EXIF output/dimensions (S1.2), two-image ZIP order/content (part of S1.3), JPEG/WebP formats and JPEG quality plus PNG batch output (S1.4), invalid coordinate cases before job creation (S1.5), and all-or-nothing bounds failure (part of S1.6). However, no test checks single-image download behavior, the 10-file maximum, sanitized output names, static/animated unsupported input behavior, image-pixel bounds, WebP quality, selected catalog category or that the browser submits all four coordinates. The current HTML assertion only checks that the card and two field IDs are present. These rules could regress while the current feature test suite remains green.

## UI inspection

Started the app and worker against a throwaway database under `.specs/features/image-crop/review-data` on port 8774, then removed that data and stopped both review processes. The browser accessibility tree showed the crop controls, upload action, output format and button in Portuguese and English. No capture files are referenced by the plan. I could not independently set the subagent browser to a 360 px viewport, so the no-horizontal-overflow criterion remains unverified by this review.

## Test mapping

| Plan rule | Test evidence | Would fail if rule were wrong? |
| --- | --- | --- |
| S1.1 controls | Template assertion checks crop tool and left/height IDs; browser inspection showed full controls in PT and EN | Partly; missing top/width assertion and no UI/browser regression test |
| S1.2 EXIF and result size | `test_crop_applies_exif_orientation_before_pixel_coordinates` | Yes |
| S1.3 batch, order, ZIP | `test_crop_batch_returns_ordered_images_in_a_zip` | Yes for a two-file ZIP; not for single-file output or 10-file maximum |
| S1.4 output format and quality | `test_crop_honors_jpeg_and_webp_output_formats`, `test_crop_applies_selected_jpeg_quality`, PNG batch test | Yes for output formats; quality test only proves JPEG |
| S1.5 invalid options before job | `test_crop_rejects_malformed_coordinates_before_creating_a_job` parameter cases | Yes for its listed missing/range/fraction cases |
| S1.6 bounds/no partial output | `test_crop_fails_without_partial_download_when_any_batch_image_is_too_small` and worker bounds unit test | Yes for out-of-bounds; no test for unsupported/animated inputs or pixel ceiling |
| S1.7 localization and 360 px | No test; browser inspection confirmed PT and EN labels | Localization manually observed; mobile overflow unverified |
| S1.8 active Edit catalog and coordinate submission | Catalog card HTML exists and code routes `image.crop`; no assertion for Edit filter or browser payload | No |

Ran `uv run pytest -q tests/test_image_crop.py`: 13 tests passed.


## Author fix pass

Implemented the requested static GIF input and kept animated GIF rejection explicit. Expanded regression coverage for static and animated GIFs, single-file output, sanitized names, the 10-file cap, pixel limits, WebP quality, all four coordinate controls, GIF upload filters and the Edit category mapping. Ran the full test suite successfully and checked the page at 360 px in PT-BR; the crop controls fit and the page has no horizontal overflow. No review finding remains open.

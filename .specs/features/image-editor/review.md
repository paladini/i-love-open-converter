# Image editor review

**Reviewer verdict: implementation matches the requested photo-editor scope, with test coverage gaps for several important guarantees.** No functional defect was found. In the single fix pass, the author added the regression tests listed below. Full `uv run pytest -q`, Ruff, JavaScript syntax, and diff checks pass. No second review was requested or performed.

## Request, sentence by sentence

> Editor de fotos

The catalog activates a “Photo editor” / “Editor de fotos” tool and selecting it opens a dedicated editor form.

> Torne suas imagens mais interessantes com texto, efeitos, molduras ou stickers.

The form provides optional text, four effects, two frame styles plus no frame, and six built-in vector stickers plus no sticker. The implementation applies these locally through Pillow. The request does not demand arbitrary effects, assets, or freeform positioning; the bounded choices match its simple scope.

> Ferramentas de edição simples para suas necessidades relativas a imagens.

The flow uses the existing one-image upload and conversion form, fixed controls, and a single downloadable output. This is consistent with a straightforward image editing tool.

## Spec criteria and test strength

| Criterion | Evidence and whether its test would catch a regression |
| --- | --- |
| S1.1: PT-BR/English UI with one-image upload, text, filter, frame/color, output, submit | `test_editor_card_and_controls_are_active_and_bilingual` checks editor control IDs, localized sticker labels and positions, single-file input configuration, and narrow-layout wrapping. The running app was also inspected in PT-BR and English. |
| S1.2: queue one job; EXIF orientation, filter/frame/text locally; keep oriented dimensions | Dedicated EXIF test verifies orientation and that top-left text follows the oriented canvas. A combined filter/frame/sticker/text test checks dimensions, filter result, visible frame, non-default sticker anchor, and text-over-sticker ordering. |
| S1.3: chosen text position, size, color and opacity | `test_editor_places_text_with_color_size_and_opacity` checks one position (top-left), one size (large), one color (red), and a 35% opacity pixel range. It would catch some failures of those selected settings, but would pass if other positions/sizes/colors were broken; it does not directly compare opacity levels or prove all three size choices differ. |
| S1.4: filter pixels change before frame/text composition | The parametrized filter test checks grayscale, sepia, and invert pixels. Those checks catch a broken filter but do not combine filter and overlays. The suite would still pass if a composition-order regression made an overlay get filtered. |
| S1.5: invalid source count and edit settings return 422 before job creation | `test_editor_rejects_invalid_options_before_job` covers invalid filter/frame/sticker/text/position/size/color/opacity/frame width/output and asserts the job table remains empty. Separate missing-source and multiple-source tests assert 422 and no job. These tests would fail if the exercised invalid values were accepted or a job were created. |
| S2.6: sticker type, position, size controls in PT-BR and English | UI regression check covers sticker type, position, size, color control IDs and localized sticker labels/position copy. Runtime inspection showed all controls in both languages. |
| S2.7: draw sticker locally at chosen anchor after frame, before text, preserving dimensions | Existing test checks each built-in sticker; the combined test checks a top-left sticker over a frame and verifies text renders above the sticker. Position helper coverage verifies all nine anchors. |
| S2.8: invalid sticker type/position/size rejected before job creation | The invalid-options test covers all three and verifies 422 with no job. It would catch acceptance or premature queueing for those cases. |
| S2.9: chosen PNG/JPEG/WebP downloadable; failed job has no partial output | `test_editor_returns_selected_output_format` covers all three names, MIME types and dimensions. `test_editor_worker_failure_has_no_downloadable_partial_file` checks failed state, 409 download and no output file. These tests would fail if those tested outcomes regressed. |
| S2.10: 360 px page width has no horizontal page overflow | No automated test checks page overflow. I opened the running app at a 360 px viewport and inspected the editor controls and the page; the editor fit within the viewport. The category strip scrolls horizontally within its own area, while the page itself showed no horizontal overflow. |

## Review limitations and findings

- `.specs/features/image-editor/captures/` contains no captures, so there were no capture sizes or states to compare. I used the required temporary review app at port 8779 and a 360 px viewport instead.
- The requested test gaps were addressed in one fix pass. The mobile layout is verified by manual 360 px inspection and a regression check for responsive control wrapping; no automated pixel-width browser assertion was added.

## Review setup

- Started with `DATA_DIR=.specs/features/image-editor/review-data APP_PORT=8779`; stopped the server after inspection.
- Used only the throwaway `review-data` directory and removed it after stopping the server. No existing app data was opened or modified.
- No product code or tests were changed, and no commit or push was made.

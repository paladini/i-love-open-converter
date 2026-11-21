# Meme generator review

**Verdict: the tool works end to end in the tested cases, but this review requests one fix pass.** The main product gap is that the plan's still-present earlier criterion requires bold captions, while `ImageFont.load_default()` returns Aileron Regular and the renderer only adds a dark outline. The plan also contains a second, stale copy of its sections and acceptance criteria. Test coverage does not prove the caption layout guarantees or the invalid-format/no-job boundary.

## Request, sentence by sentence

- The request continues the free, open-source I Love Open Converter roadmap. The new operation is local and uses the existing image/job/download flow; README documentation was added in English and Portuguese.
- The request asks to continue all implementation and open PRs. This feature remains local on its branch, and the reviewer did not push.
- The slice request in `request.md` asks for one uploaded image, optional top and bottom captions, PT-BR/English, and a downloadable image. The operation and visible controls are present; the API rejects the case where both captions are blank.

## Criteria and test strength

| Criterion | Evidence and whether its test would catch a regression |
| --- | --- |
| 1. Selecting the card shows the image picker, two caption inputs, JPEG default, and action | `test_home_page_has_image_and_pdf_groups_and_local_assets` checks the card and top input in rendered HTML. I opened the app on the throwaway review instance and selected the tool: both inputs, the JPEG default, and “Criar meme” appeared. The static test would not catch selection/visibility regressions. |
| 2. One supported image produces a downloadable selected format at oriented dimensions | `test_meme_generator_creates_local_jpeg_and_rejects_invalid_requests` exercises the queue and JPEG download; `test_meme_captions_preserve_dimensions_and_alpha_or_flatten_for_jpeg` covers PNG/JPEG/WebP encoding and dimensions. These catch output-format and dimensions regressions for the tested inputs. |
| 3. Captions are centered, wrapped, scaled, outlined, bold, and truncated with an ellipsis when needed | The implementation centers text and wraps it, but the default font is Aileron **Regular**, and only a black outline is applied; it does not satisfy the still-present stale criterion requiring bold text. The long-caption test only checks that nontransparent pixels occur in both halves of a small image. It would pass if centering, wrapping, outline, scaling, or the ellipsis were removed or incorrect. |
| 4. PNG/WebP retain alpha; JPEG composites transparency onto white | The parametrized image test checks output modes and transparency, including a white pixel away from the captions in the JPEG. It would catch loss of alpha or the tested JPEG background behavior. |
| 5. EXIF orientation precedes caption placement and dimensions follow orientation | `test_meme_applies_exif_orientation_before_drawing_captions` checks 40×80 orientation 6 becomes 80×40 and all caption pixel changes remain in the top half. It would catch ignoring orientation or placing the caption in the old bottom half. |
| 6. Invalid count, blank captions, overlong text, and format return 422 before job creation | The API test covers blank captions, 301-character text, and multiple files, but does not test an unsupported output format or assert that these 422 responses leave the jobs table unchanged. The implementation validates options before creating a job, but the tests would not catch moving queue creation ahead of validation. |
| 7. Unsupported extension/content return 415/422 without a job | The API test checks `.gif` returns 415 and malformed bytes return 422. It does not assert that either response leaves no queued job. |
| 8. Worker failure marks failed and exposes no partial output | `test_meme_worker_failure_has_no_partial_download` injects an image-processing failure, then checks failed state, 409 download, and an empty output directory. It would catch a partial artifact or incorrect terminal state. |
| 9. PT-BR/English localization | I opened the selected tool in both languages. The title, top/bottom labels, placeholders, and action changed to English; the Portuguese state showed their PT-BR equivalents. The current UI tests only inspect static HTML, so they would not catch localization regressions. |
| 10. Controls remain reachable at 360 CSS pixels without horizontal page overflow | At the 360 px override, the selected form stayed visible and `document.documentElement.scrollWidth` was 345 px while the browser reported `innerWidth` 361 px; input `multiple` was false. There are no captures for this feature. This was a manual browser check, not an automated regression test. |

## Findings

1. **Bold captions are still required by the duplicated plan but are not implemented.** The earlier criterion at `.specs/features/image-meme-generator/plan.md:113` says captions use bold text. The renderer uses `ImageFont.load_default()` and a dark stroke, not a bold face or a bold rendering effect. Remove the duplicate stale section only if it was accidental; otherwise render visibly bold captions and test that styling.
2. **The plan has duplicate, conflicting sections.** After the new `## Sources` at line 86, the file repeats `## Surface`, `## Landing`, `## Criteria`, `## Out of scope`, and `## Assumptions` (starting at line 90). The old criteria conflict with the first section: the old version says “bold” and lacks the new ellipsis and selection requirements. Consolidate the plan so the reviewer and next contributor have one source of truth.
3. **Caption-layout guarantees are not locked by tests.** The long-caption test checks only alpha bounding boxes, not centered placement, line wrapping, contrast outline, or visible ellipsis. Add pixel/layout assertions that fail if each promised behavior is removed.
4. **Invalid-option tests do not prove fail-before-queue.** Add an unsupported output-format request and check the job table remains empty for each rejected meme request. Current tests check status codes but do not assert the criterion's no-job guarantee.

## Review setup and limitations

- `uv run pytest -q` passed.
- I used `APP_PORT=8791` and `.specs/features/image-meme-generator/review-data`, a fresh throwaway data directory, and removed it after the review. No existing app data was opened or changed.
- I inspected the app in PT-BR and English at 360 CSS pixels. There are no screenshots or captures under this feature, so there was no source image to compare against.
- The browser screenshot endpoint did not return an image; I verified visible labels and responsive widths through the browser accessibility tree and read-only DOM measurements instead.
- No code, tests, commits, or push were made by the reviewer.

## Author fix pass

The author addressed all four findings in one pass:

1. Removed the duplicate stale sections and retained one current criteria list, including the bold and ellipsis requirements.
2. Added a one-pixel white overdraw after the dark stroke so the bundled regular face renders visibly thicker; a pixel test compares it with the unbolded font output.
3. Added pixel/layout checks for centered alignment, dark outline, bold overdraw, wrapped text width, and ellipsis when a bounded caption cannot fit.
4. Added an unsupported output-format case and asserted all rejected meme requests leave the job table unchanged; added PT-BR/English UI copy checks.

Verification after the pass: full `uv run pytest -q`, Ruff, JavaScript syntax, diff check, and `validate_plan.py` all pass. The reviewer was not asked to perform a second review.

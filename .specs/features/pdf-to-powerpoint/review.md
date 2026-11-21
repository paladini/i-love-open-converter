# Independent review

Verdict: changes required.

## Findings

1. **P1 - Editable text is scaled roughly 72 times too small.** In `src/i_love_open_converter/powerpoint_worker.py:110-113`, `slide_factor` maps PDF points to slide inches; for the first page, whose long dimension is 360 PDF points, `transform.scale` is `13.333333 / 360` inches per PDF point. At line 62 that inches-per-point value is multiplied by the PDF font size and passed to `Pt`, which expects points. A 12 pt source font therefore becomes approximately 0.44 pt instead of 32 pt on the 13.33-inch slide. Text remains present/selectable, so the current test passes, but it is effectively illegible and fails the editable-presentation intent.

2. **P2 - Geometry and several safety limits are not guarded by regression tests.** `test_pdf_to_powerpoint_creates_editable_text_and_picture_shapes` verifies that the output has two slides, source strings and one picture, but does not assert object bounds or positions. It would pass if portrait-page content were not centered, or if image/text placement were wrong, despite AC3. The only resource-boundary test is `test_powerpoint_worker_rejects_more_than_two_hundred_pages`; there are no cases for the 16 MP page bound, the 20,000-shape bound, the 180-second timeout, or the 256 MiB output cap (AC4 and AC6). Those rules could be removed without the current feature tests failing. The production code contains checks for them, but the tests do not prove those checks work or that failures leave no download.

## Criteria and evidence

- **AC1:** `test_pdf_to_powerpoint_creates_editable_text_and_picture_shapes` checks the home link, route, one-file job acceptance, and download MIME. The page and JavaScript contain PT-BR and English labels/statuses, but tests do not exercise language switching, queued/processing/error states, or localized unavailable/error output.
- **AC2:** The same test checks two slides, editable text and one separate picture object. It would fail if those objects were absent. It does not check text ordering within a page or source-relative geometry.
- **AC3:** The test uses landscape and portrait pages but makes no assertions about slide dimensions, centering, object positions or bounds; it would pass with faulty geometry.
- **AC4:** Invalid, encrypted, multiple-file and 201-page cases are covered. Over-limit page pixels, shape count, subprocess timeout and no-artifact behavior for those limits are not tested.
- **AC5:** The PowerPoint job test checks an unavailable worker. The shared `word_isolated()` implementation is tested in `tests/test_pdf_to_word.py` for Linux attestation, loopback-only interfaces, external `eth0`, and Windows; PowerPoint calls that guard before starting its child.
- **AC6:** The output test checks presentation and slide parts, and the success test opens the PPTX with python-pptx. No test checks the output-size boundary or corrupted generated package handling.
- **AC7:** Both READMEs state python-pptx/PyMuPDF, editable text/images, exclusions, scanned-page limits, resource bounds and worker isolation.
- **AC8:** The active catalog link is asserted by the success test. I ran the repository's full pytest suite with a disposable `--basetemp` inside the feature directory: all tests passed. No screenshots/captures are cited by this feature, so there was no binding capture to compare; the route is exercised through TestClient.

The review did not modify application code or running-app data. The only temporary test files were placed in `.specs/features/pdf-to-powerpoint/reviewer-tmp/` and removed afterward.

## Fix pass

Finding 1 was fixed by converting the source font size through the PDF-points-to-slide-inches scale and then multiplying by 72 to supply PowerPoint points. The regression now asserts the expected 29.33 pt result for the sample's 11 pt text. Finding 2 was fixed with tests that verify portrait content is centered on the landscape deck, slide objects remain in bounds, and over-limit page pixels, shape count, timeout and output size fail without exposing a download or partial presentation. Existing tests continue to cover the 200-page limit and valid slide/package structure.

Verification after the fix: all ten targeted PowerPoint tests and the full 118-test suite passed. Ruff, JavaScript syntax, `git diff --check`, and plan validation passed. The rebuilt AMD64 isolated worker generated a two-slide PPTX with 29.33 pt editable text; LibreOffice opened it and exported both slides to PDF with text intact.

# Review

**Verdict:** One fix pass is needed for acceptance-criteria coverage. The local translation implementation and Docker smoke path are plausible and the visible page renders, but several specified API/job/error outcomes have no test that would fail if that integration regressed.

## Findings

### [P2] Cover the successful job and unavailable-model error paths

`tests/test_api.py::test_pdf_translation_requires_supported_direction_and_exposes_page` exercises the route and one invalid direction only. The unit tests in `tests/test_pdf_translation.py` replace `_translate_text`, so they do not reach the model loader or worker. `docker/translation-smoke.py` validates real inference and `translate_pdf` directly, but does not submit a `pdf.translate` job, run `process_one_job`, or verify the status/download artifact. There is also no test that removes or redirects the model directory and asserts `translation_unavailable` with no artifact.

Consequently, acceptance criteria 2 and 9 could be broken in API option forwarding, worker dispatch/error mapping, or job artifact handling while the existing tests still pass. Add a TestClient/worker integration test with a deterministic local translator for the success/status/download flow, and a missing-model worker test that verifies the failed state and absence of a download.

### [P2] Exercise the specified request-rejection cases

The only new API rejection assertion is for an unsupported language pair. No translation-specific test covers omitted direction, multiple files, non-PDF input, malformed PDF input, or the API's 100-page rejection. The implementation routes these through shared validation code, but acceptance criterion 5 specifically requires each request to fail before job creation. A regression in translation's inclusion in those checks would not be caught by the added test.

Add focused API assertions for those cases, including that the job table remains empty after each rejection.

## Criteria evidence

- **C1:** Opened `/tools/pdf-translate` in the isolated app at `127.0.0.1:8792`; the accessibility tree showed the single-file picker, explicit direction selector, and text-only/page-preservation instructions. No binding captures are present in `.specs/features/pdf-translation/captures/`, so there was no capture state to compare.
- **C2:** No success-path job/status test exists; see finding 1.
- **C3-C4:** `test_translation_keeps_page_order_blank_pages_and_dimensions` verifies page count, width, order, and blank-page position, but substitutes a deterministic translator. The Docker smoke script adds real offline inference and checks page count/dimensions/text presence.
- **C5:** Only unsupported direction is asserted at the API; see finding 2.
- **C6-C8:** Unit tests verify empty text, the 100,000-character bound, the 100-page bound, and page overflow without writing a partial destination. Worker code maps these exceptions and clears output, but these worker state mappings are not directly asserted.
- **C9:** Missing-model behavior has no test; see finding 1.
- **C10-C12:** `docker/translation-smoke.py` blocks `socket.create_connection` and `socket.socket.connect`, tests both directions, and verifies text-only PDF page mapping. The Docker build runs this smoke script after installing both hash-checked assets. No architecture-specific build is recorded in this review.
- **C11:** The page was inspected in the browser at its default viewport. The repository has no automated 360 CSS-pixel layout assertion; no binding capture requires comparison.

The review used a fresh app process on port 8792 for a read-only page inspection. It did not access or change persisted job data. The repository did not contain feature captures.

## Fix pass

The two findings were addressed in one pass. `tests/test_api.py::test_pdf_translation_job_returns_text_pdf_download` now runs the accepted operation through the worker, confirms succeeded status, downloads a PDF, and checks selectable translated text, page count, blank-page position, and dimensions. `test_pdf_translation_fails_without_models_and_has_no_download` points the loader at an empty temporary model directory, then asserts the worker's `translation_unavailable` error and no output/download. `test_pdf_translation_requires_supported_direction_and_exposes_page` now covers an omitted direction, unsupported pair, multiple files, non-PDF input, malformed PDF, and 101-page PDF; after each request it asserts rejection and zero jobs. The focused tests, Ruff, and the full suite passed after these additions. No runtime code or product scope changed in the fix pass.

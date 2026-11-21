# Review: HTML to PDF

**Verdict: PASS WITH ONE TEST-COVERAGE FINDING.** The local HTML conversion path is implemented and works in the production Linux image. I found no conversion or isolation defect in the reviewed code. One acceptance criterion's security and failure bounds lack regression tests.

## Request and scope

The request says to convert a page URL to PDF. This stage narrows that to one uploaded `.html` or `.htm` file and defers fetching public URLs. The plan records the unanswered scope question and this local-only choice. The page and API match that stage scope; public URL conversion remains outstanding roadmap work.

## Checks

- Read the request and plan against the implementation. The catalog, bilingual page, API validation, worker dispatch, local renderer, README support matrices, and output download are present.
- Opened `http://127.0.0.1:8799/tools/html-to-pdf`; the page loaded in English with the file picker, local-only resource explanation, and 10 MiB / 100-page bounds. The plan lists no captures, so there was no captured state to compare.
- Ran `uv run pytest -q tests/test_html_to_pdf.py`: all 10 tests passed. Ran Ruff on the changed Python files and Docker smoke script: passed.
- Ran the Docker smoke as UID 1000 with `--network none`: selectable text and a `data:` image rendered; HTTP and `file:` references were rejected.
- Reviewed each criterion's tests. Upload count, extension, size, job creation/download, blocked-resource failure, and unavailable-worker failure have direct assertions. The resource-policy helper test covers HTTPS, HTTP, FTP, `file:` and relative references, but that helper alone does not prove WeasyPrint routes each case through it.

## Finding

### R1 [P2] Add regression coverage for renderer bounds and failure paths

**Evidence:** `tests/test_html_to_pdf.py` covers normal success, upload validation, mocked external-resource failure, and an unavailable isolation gate. It does not exercise a timed-out child, a PDF exceeding the output-size or 1-100 page bounds, or an invalid generated PDF. `docker/html-to-pdf-smoke.py` checks the real renderer with a valid one-page document plus HTTP and `file:` references only. The implementation has the relevant checks in `src/i_love_open_converter/html_ops.py` and `src/i_love_open_converter/html_worker.py`, but a regression removing those guards would not fail the current suite.

**Why it matters:** Criteria 3, 4, and 6 make resource isolation and fail-closed behavior part of the contract. Without tests for these branches, later changes can silently publish oversized/invalid output or miss timeout and page-count failures.

**Suggested fix:** Add focused tests that force the child timeout and exercise output-size, page-count, and invalid-PDF rejection, then assert failed jobs expose no downloadable artifact. Where practical, exercise the real URL fetcher for HTTPS, FTP, and relative references in addition to HTTP and `file:`.

## Fix pass outcome

R1 was addressed in one pass. `tests/test_html_to_pdf.py` now forces a child timeout and invalid, oversized, and over-page-limit PDFs through the job worker, asserting each job fails with no downloadable artifact. `docker/html-to-pdf-smoke.py` now sends HTTPS, FTP, `file:`, and relative references through the real WeasyPrint fetcher in addition to the existing HTTP and `file:` cases; all are rejected in the isolated Linux container.

## Criterion notes

- **1:** Page accepts one HTML file; localized queued, processing, success, and error labels exist. No browser capture was supplied.
- **2:** API enforces one file, `.html` / `.htm`, no options, and the 10 MiB limit before job creation; tests assert the invalid cases and job count.
- **3:** The custom fetcher allows only `data:`. Live smoke covers HTTP and `file:`; the helper test covers all listed schemes and relative paths. See R1 for fetcher integration coverage.
- **4:** `office_isolated()` is required, and the child applies Landlock, 2 GiB address-space, 120-second CPU, and 256 MiB file-size limits. Compose uses `network_mode: none`; see R1 for missing regression tests.
- **5:** The parent validates PDF structure, encryption state, size, and page count; live smoke confirms selectable text and an embedded image in the generated PDF. See R1 for invalid/boundary output tests.
- **6:** Worker errors are localized in the page for unavailable isolation, blocked resources, and general conversion failures; failure handlers remove partial output. Unavailable and blocked-resource cases have job/download assertions. See R1 for untested timeout and output-validation failures.
- **7:** Both README languages and support matrices document extensions, `data:` policy, WeasyPrint, Linux/Landlock, rendering bounds, and JavaScript/CSS limitations.

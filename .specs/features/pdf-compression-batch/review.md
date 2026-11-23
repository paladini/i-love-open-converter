# Review

**Verdict:** The batch compression implementation matches the plan. One P2 test assertion is missing for the upload limit's no-job guarantee.

## Finding

- **P2 — The file-limit test does not prove that an over-limit upload creates no job.** Criterion 3 requires rejection before job creation. `test_batch_pdf_compression_rejects_more_than_configured_file_limit` checks only HTTP 422 and `too_many_files`; it would still pass if a future regression created a job before returning the error. The current API count guard is visibly before job creation, so this is a coverage gap, not an observed behavior defect. Evidence: `tests/test_pdf_compression.py`; the global file-count check in `src/i_love_open_converter/main.py` precedes the job creation path.

## Checks

- Read the request and plan criteria against the implementation. The API now lets `pdf.compress` bypass the single-file restriction, while the existing multipart parser still enforces the configured job limit and validates every uploaded PDF.
- Confirmed the form turns on `multiple` for `pdf.compress`. The browser regression checks the selector's default and PT-BR labels, selected-file order, and that both files are sent. The browser test also verifies that a batch reaches the completed-result state.
- Confirmed the PDF processor applies the same profile to each source, returns one PDF per file, and uses source stems with case-insensitive duplicate handling. The existing worker packages multiple outputs as `converted-files.zip` in returned path order.
- Read the tests against the criteria: the API integration test checks ZIP MIME/name, duplicate-safe member names, and distinct source text in upload order; the profile remains supplied on a batch; the over-limit test checks the status and error; the single-file unit test checks `compressed.pdf` and PDF MIME. The P2 finding above is the remaining unasserted part of the count rule.
- No captures were supplied. The intended UI behavior is exercised by Playwright tests, but I could not run or open the app locally because the checked-in `.venv` currently fails import collection: `pydantic` cannot import `__version__` from `pydantic_core`. No files outside this review report were changed.

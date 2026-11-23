# Review

**Verdict:** The implementation follows the option, page-limit, and worker-isolation contracts. Before merge, add coverage for the combined OCR-to-DOCX/XLSX flow and for rejecting malformed OCR options and over-limit pages before job creation.

## Findings

1. Existing OCR and Office tests cover their separate paths, but no regression proves that an OCR-produced intermediate PDF reaches the Word or Excel converter and yields a downloadable document with recognized text.
2. No test covers invalid OCR settings or the 20-page limit for either Office operation, including the requirement that these requests are rejected before a job is created.

## Author fix pass

- Added PDF-to-Word and PDF-to-Excel worker-flow coverage with a deterministic local OCR intermediate and output assertions.
- Added invalid-option cases for both operations, including a non-string language, and confirmed rejected requests do not create database jobs.
- Added 21-page OCR option rejections for both operations and assertions that no job is created.
- Delete the intermediate OCR PDF after Office conversion completes so the temporary recognized-text document does not remain in the output directory with the downloadable result.
- The first fix-pass CI run caught that error-body assertions used a nested FastAPI shape instead of the application's flat `{"error": ...}` response; updated them to match the API contract.
- CI for the first feature commit passed. CI is rerunning on the final fix-pass commit. No local tests were run.

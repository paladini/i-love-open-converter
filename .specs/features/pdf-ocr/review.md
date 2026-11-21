# PDF OCR independent review

**Verdict: needs follow-up before acceptance.** The feature is substantially implemented, but the source request's key output-fidelity requirement is not demonstrated by its tests, and the requested capture-by-capture screen review could not be performed because the capture directory is absent and no browser surface was available. No app data was changed. I did not change implementation code.

## Request, sentence by sentence

Source request: “Converta facilmente um PDF escaneado em documentos selecionáveis e pesquisáveis.”

- A single PDF can be uploaded and queued as `pdf.ocr`; the OCR page supplies the three language options and the worker routes this operation through `process_pdf` (`src/i_love_open_converter/main.py`, `src/i_love_open_converter/templates/pdf-ocr.html`, `src/i_love_open_converter/worker.py`). The page's download link appears after a succeeded job.
- `ocr_ops.py` invokes OCRmyPDF with the selected local language, verifies that the output opens as a PDF with the same page count, and rejects output with no extracted text. This supports searchable/selectable output in principle; however, the integration test replaces the OCR operation with a source-file copy, so it does not prove that an actual scanned PDF produces selectable text.
- The request does not separately demand bilingual UI, page bounds, or safety constraints; these come from the approved plan and are reviewed below.

## Findings

### P1 - Source request's searchable output and unchanged appearance lack an end-to-end test

The only API success test monkeypatches `make_searchable_pdf` to copy the uploaded PDF (`tests/test_api.py:1443-1476`), and the processor unit test fakes OCRmyPDF by copying its input (`tests/test_ocr_ops.py:23-65`). These tests would still pass if the actual OCR invocation failed to produce a selectable text layer or changed the scanned page's visible content. The implementation checks for some extracted text and page geometry (`ocr_ops.py:98-114`), but never compares rendered input and output page appearance; page count and geometry do not prove visual fidelity. Add an integration test using a generated image-only PDF and the installed OCR engine (or a faithful OCR output fixture) that checks recognized text and rendered-page equivalence, and a preservation assertion for an existing-text page.

### P2 - Screen review at capture sizes is unverified

The task named `.specs/features/pdf-ocr/captures/`, but that directory does not exist in this checkout. The CUA browser inventory also had no browser surface (`iab` unavailable), so I could not inspect the running page or compare it at capture dimensions. The plan's build-evidence paragraph claims a prior 360px check, but that is not independent review evidence. The repository has only a source-level availability/content test (`tests/test_api.py:1422-1441`), which would not catch layout, overflow, or control usability regressions. Supply the captures or an accessible browser surface and review the rendered page at the required sizes.

## Criteria and test strength

| Plan rule | Evidence and whether the test would fail if wrong |
| --- | --- |
| S1.1: catalog card, bilingual single-file page, language choices/default, processing/error/result states | `tests/test_api.py:1422-1441` asserts route/card strings, file accept, and language values. It does **not** assert default selection, visible loading/error/result states, or rendered layout. It would catch missing route/options and several copy regressions, but not a broken visual flow. |
| S1.2: local OCR, selectable text, unchanged page count and visible content | `tests/test_ocr_ops.py:23-65` asserts command flags, selected language, timeout, job bound, and unchanged text/page count using a fake copy process. `tests/test_api.py:1443-1476` also mocks OCR. These tests do **not** fail if real OCR emits no searchable layer or alters visible content. Implementation verifies page count, geometry, nonempty text, and existing text (`ocr_ops.py:98-114`), but not visual equality. |
| S1.3: preserve existing selectable text | `--skip-text` is present (`ocr_ops.py:29`) and output text is compared against source text (`ocr_ops.py:112-113`). The unit test uses a fake copy, so it would not detect OCRmyPDF behavior that changes existing text in a real run. |
| S1.4: reject invalid/encrypted PDFs, >20 pages, unsupported language, no/multiple files before job | The OCR-specific API test covers unsupported language and 21 pages plus zero DB jobs (`tests/test_api.py:1479-1503`). Single-file cardinality is enforced by shared route validation (`main.py:591-619`); this OCR-specific test does not cover zero/multiple files. No OCR-specific encrypted/invalid PDF test is present. Existing shared upload/PDF validation may cover those generic paths, but those tests are not tied to `pdf.ocr`. |
| S1.5: timeout/resource/no-text/verification failures leave no partial artifact | Timeout cleanup is tested at processor level (`tests/test_ocr_ops.py:96-138`); no-text worker failure and download rejection are tested (`tests/test_api.py:1506-1549`). Output verification is tested for no text in the processor suite. There is no OCR-specific worker test for generic subprocess failure, invalid PDF output, page-count mismatch, or output-size limit. The worker container has a 3 GiB memory limit (`compose.yaml:35-40`); OCR uses a 600 second wall timeout, Tesseract timeout/pixel caps, one job, and a 256 MiB post-run output check (`ocr_ops.py:12-13, 42-53, 79-91`). |
| S1.6: installed local `por`/`eng`, no runtime language/model downloads | Dockerfile installs `tesseract-ocr-eng` and `tesseract-ocr-por`; invocation runs local `python -m ocrmypdf` with no download step, and the worker has `network_mode: none` (`compose.yaml:35-40`). Unit test checks executable and selected language but not packaged language data; build evidence in the plan claims both language packs were installed. |
| S1.7: accuracy disclosure and usable 360px layout | Disclosure exists in both languages in `templates/pdf-ocr.html`; responsive behavior has no test. Could not visually inspect due to missing captures/browser. |

## Review method and boundaries

- Reviewed all commits after `adbc603b0acbf1d8458def91b4ff8d22ae82c730` plus the clean worktree diff/status; no uncommitted implementation changes were present.
- Read the original request and approved feature plan, inspected implementation and relevant tests, and checked the worker's Compose isolation/memory settings.
- Did not run the OCR route against the already-running app or alter its data. The browser surface was unavailable, so this is a source-and-test review rather than a live visual review.
- No Git push or commit was made.

## Author's single fix pass

1. **P1 addressed.** `make_searchable_pdf` now hashes each page's RGB rendering at a maximum 1,000 x 1,000 pixels and rejects output whose page appearance differs. A regression test proves a visually changed result is rejected and deleted. `docker/ocr-smoke.py` runs during image build against the real OCRmyPDF/Tesseract binaries; it creates a two-page PDF with a scanned Portuguese sentence and an existing selectable-text page, then asserts recognized text, exact existing text, page count, and rendered pixel equality. The rebuilt image passed with `OCR_SMOKE_OK`.
2. **P2 follow-up.** The cited binding capture is `.specs/features/project-foundation/captures/ilovepdf-home.aria.yml`; it captures the homepage catalog, not a dedicated OCR page. The reviewer prompt's `.specs/features/pdf-ocr/captures/` directory does not exist, but the cited source capture does. In the author session, I inspected the running catalog at 731x720 and confirmed the active OCR link and catalog placement, then verified the OCR page in PT-BR and English with all three language choices. At 360px the document and body widths were both 345px, with no horizontal overflow. No feature-specific page capture exists to compare pixel-for-pixel.

The full repository suite and Ruff passed after the fix; JavaScript syntax, Compose configuration, and TLC plan validation also passed. The independent review could not use the browser surface, so its UI limitation is recorded above; the live browser checks were performed by the author.

# Review

## Verdict

The implementation establishes a useful operation inventory, expands end-to-end cases, adds negative-input checks, and wires a native runtime smoke suite into CI. It does not yet meet several approved coverage guarantees: the matrix is not complete against the documented PDF paths, PDF/A has no successful available-dependency job-flow case, batch and option coverage are not fully represented, and configured limits lack accepted-at-boundary witnesses.

The original request asks how to gain confidence that all implemented tools work across file types, inputs, and processing choices, with a very robust user experience. The code addresses that direction, but the gaps below mean a future regression in some advertised capabilities could still leave the coverage matrix green.

## Findings

### [P1] The documented format matrix is not complete or forward-enforcing

`FORMAT_PAIRS` in `tests/test_conversion_coverage.py:140-171` has no pair for README row 6, which is the documented unencrypted-PDF to PDF path (`README.md:55`). In addition, `test_format_pair_matrix_has_an_operation_case_and_documentation_row` at lines 344-360 checks that each manually listed pair appears in both README tables, but never checks the reverse: every documented pair must appear in `FORMAT_PAIRS`. Adding a new documented pair without updating the matrix therefore does not fail the test. This leaves acceptance criterion S1.2 unenforced for an existing row and future additions.

### [P1] PDF/A is only mapped to the unavailable path

`OPERATION_CASES["pdf.pdfa"]` at `tests/test_conversion_coverage.py:125` points to `test_pdfa_is_unavailable_without_installed_dependencies`. That test forces `pdfa_available` to return false (`tests/test_pdf_archive.py:80-90`), and the AST guard explicitly exempts PDF/A from worker/download checks (`test_conversion_coverage.py:305-312`). The runtime smoke script calls `convert_pdfa` directly, while the API test with availability forced true deliberately makes conversion fail (`tests/test_pdf_archive.py:93-114`). There is no successful `POST /api/jobs` → worker → download case with real PDF/A dependencies enabled. This misses S1.3 and S2.5 for the conditional success path.

### [P1] The batch matrix selects single-file witnesses for batch-capable operations

The operation map selects `test_single_crop_downloads_one_sanitized_image` for `image.crop` and `test_text_watermark_is_applied_at_selected_position_and_opacity` for `image.watermark` (`tests/test_conversion_coverage.py:74-77`), although separate multi-file success tests exist for crop (`tests/test_image_crop.py:177`) and image watermark (`tests/test_image_watermark.py:86`). It also selects a single-file PDF rotation test for `pdf.rotate` (`test_conversion_coverage.py:82`), while a batch worker/download test exists at `tests/test_pdf_rotate_batch.py:28-59`. The separate tests may still catch regressions when the full suite runs, but the declared operation matrix does not establish the minimum and multi-file cases required by S2.6, so future changes to the matrix can silently drop that evidence.

### [P1] Processing-option coverage is not inventoried

The matrix maps each operation to one test (`OPERATION_CASES`, `tests/test_conversion_coverage.py:48-133`) but does not enumerate form options or map defaults, non-defaults, or their bounds to tests. Existing tests cover many individual choices, but there is no check tying options shown by tool forms to those tests. A new or changed form option can therefore bypass the coverage matrix, contrary to S1.4 and S2.8.

### [P2] Upload limit tests do not prove accepted-at-limit behavior

The configured file-size, streamed per-file, aggregate upload, and file-count tests exercise over-limit requests only (`tests/test_api.py:1792-1845`). For example, both file-size tests use `1 MiB + 1` at lines 1792-1815, without a corresponding valid `1 MiB` request. The plan requires an accepted-at-limit and rejected-over-limit case for each configured bound (S3.10), so off-by-one regressions at these boundaries could go undetected.

### [P2] The shared malformed-upload test accepts service-unavailable for every operation

`test_every_operation_rejects_malformed_upload_before_creating_a_job` allows HTTP 503 and `service_unavailable` for all parameter values (`tests/test_conversion_coverage.py:315-331`), even though only conditional PDF/A needs this unavailable behavior. A non-PDF/A operation that incorrectly becomes unavailable can still pass this negative test, weakening its proof of the existing 4xx validation contract under S3.9.

## Criteria assessment

| Criterion | Review |
| --- | --- |
| S1.1 operation/catalog map | Pass. Equality with `SUPPORTED_OPERATIONS`, catalog IDs, and routes are asserted. |
| S1.2 documented format pairs | Finding above: reverse coverage is not asserted and PDF→PDF row 6 is absent. |
| S1.3 conditional PDF/A | Finding above: only unavailable API behavior and direct converter smoke are covered. |
| S1.4 processing options | Finding above: no option-level inventory or guard exists. |
| S2.5 job flow and semantic output | Mostly pass: mapped success cases generally exercise `TestClient`, `process_one_job`, status/download, and parsers. PDF/A is the exception. |
| S2.6 batch minimum and multiple files | Finding above: selected matrix witnesses miss some batch-capable operations. |
| S2.7 semantic invariants | Existing positive tests assert many PDF/image/Office/archive properties; no single matrix inventory ensures every promised invariant stays mapped. |
| S2.8 output-changing choices | Existing tests cover several choices, but the missing option inventory means coverage is not complete or future-proof. |
| S3.9 malformed/unsupported files and no jobs | The new test checks malformed uploads for each operation and zero job directories; the broad 503 allowance weakens the assertion. Existing operation-specific tests cover additional cases. |
| S3.10 exact boundaries | Finding above. |
| S3.11 terminal failures and no partial output | Pass for the covered worker and batch failure tests, including PDF/A, crop, HEIC, and RAW. |
| S3.12 security/isolation safeguards | Existing tests remain in the suite for streamed limits, Office/decoder restrictions, PSD/SVG/URL, redaction, and passwords. |
| S3.13 fixture provenance | Pass for the added small HEIC fixture: source, license, and hash are recorded; the upstream test sample is a synthetic rainbow image. |
| S4.14 CI trigger and full tests | Pass in configuration: pytest no longer excludes PSD cases; source/test/runtime changes trigger the container build. |
| S4.15 final-image runtime engines, offline | Pass in configuration: final Python 3.14 stage runs OCR, translation, summary, HEIC, RAW, PSD, Office, PDF/A, background removal, and HTML checks under `RUN --network=none`. |
| S4.16 supported architectures | Pass in configuration: Buildx targets `linux/amd64` and `linux/arm64` on relevant PRs and pushes. A fresh two-architecture final-image build was not run during this review. |
| S4.17 unexpected matrix skips | Pass in configuration: JUnit checking requires mapped witnesses to appear and fails if they skip on Linux; platform-only skips are reported and not counted elsewhere. |

## Validation performed

- Ran `pytest` for `test_conversion_coverage.py`, `test_pdf_archive.py`, `test_pdf_rotate_batch.py`, `test_image_crop.py`, and `test_image_watermark.py`: passed.
- Reviewed the CI workflow, Dockerfile smoke wiring, fixture provenance, and the cited tests. No UI or live application data was changed.
- Did not build the full final image for both architectures; only the configured checks and source/tests were reviewed here.

## Fix pass

The single fix pass closed the six findings:

- Added the documented unencrypted PDF-to-PDF path and made the operation matrix enforce all documented format pairs in both directions in both README languages.
- Added a conditional PDF/A API submission, worker processing, download, and semantic output check. The final-image smoke performs this flow with a small ASGI harness so it does not depend on test-only `httpx2`.
- Mapped minimum and multiple-file witnesses for batch-capable operations, including image crop/watermark and PDF rotation/compression.
- Inventoried every non-file form control and linked each processing option to an operation with a positive test witness.
- Added accepted-and-processed checks at the per-file, aggregate-byte, and file-count limits.
- Restricted malformed-upload `503` acceptance to PDF/A when its runtime dependencies are actually unavailable.

Validation after the fix pass: full Windows suite completed with 691 tests, zero failures, and 16 skips; the coverage JUnit guard passed with 42 required success witnesses and correctly classified three Windows-only PSD skips; Ruff checks and formatting passed; Docker Buildx syntax check passed; the existing final runtime image passed HEIC, RAW, PSD, Office, PDF/A API job flow, background-removal model, and offline HTML smoke checks. The complete final-image two-architecture build was not run locally and remains covered by configured CI.

# SVG-to-raster review

**Verdict: changes are implemented, with a test coverage gap before the feature is fully review-ready.** I did not modify application code or app data.

## Request and scope

The request asks to continue building `i-love-open-converter` as a simple, free, open-source ILoveIMG/ILovePDF-style application, following `tlc-spec-lean` through implementation and PRs as needed. For this review, the approved feature plan supplies the concrete scope: local conversion of one static SVG to PNG/JPEG/WebP, bounded rendering and input validation, isolated processing, bilingual UI, and mobile usability. The implementation is in commit `afdaddf` on `feat/image-from-svg`; no PR or push was made during this review.

## Acceptance evidence

1. **Catalog, input, formats, limits, localization:** `templates/index.html` and `static/js/app.js` enable the SVG tool, set the file input to one `.svg`, expose PNG/JPEG/WebP, and provide PT-BR and English labels/notices. The in-browser English view showed the tool, upload, output selector, local-processing notice, and 40 MP hint.
2. **API job and worker output:** `tests/test_api.py::test_svg_conversion_job_is_queued_with_bounded_dimensions` submits each of PNG/JPEG/WebP and asserts 202 plus a queued `image.from_svg` job with dimensions. `worker.py` dispatches to `convert_svg_to_image`; Docker smoke coverage (reported in the build evidence) checks output format, dimensions, MIME, alpha for PNG/WebP, and white JPEG flattening. The API test alone would not catch a broken worker renderer; smoke coverage exercises that path.
3. **Sizing:** `tests/test_svg_ops.py` covers `viewBox`, 300×150 fallback, CSS units, and scaling oversized dimensions below 40 MP with aspect ratio. Those assertions fail if the corresponding dimension selection or bound is wrong. The conversion wrapper revalidates dimensions before rendering.
4. **Transparency:** Docker smoke assertions inspect transparent PNG/WebP pixels and white JPEG pixels. These fail if alpha is lost or JPEG transparency is not flattened as planned.
5. **Reject before job:** `tests/test_svg_ops.py` covers >10 MiB inspection. `tests/test_api.py::test_svg_conversion_rejects_invalid_request_before_queue` covers wrong extension, unsafe SVG content, invalid output format, and unapproved dimensions/options, and asserts error responses. However, no SVG-specific API test submits a missing file, multiple files, or an over-10-MiB upload and verifies that no job was created. The implementation has an explicit exact-one-file check and upload size check in `main.py`, but these tests do not fail if those API paths regress. **Finding:** add API regression cases for missing/multiple SVG parts and over-limit upload, asserting both rejection and absence of a queued job.
6. **Unsafe content and cleanup:** parameterized `test_svg_inspection_rejects_unsafe_or_non_svg_content` covers script, animation, `foreignObject`, event handler, HTTP/file references, DTD/entity, and non-SVG root. The API invalid-request test covers unsafe SVG rejection before queue. `worker.py` removes output on converter exceptions. The tests do not execute a worker failure and assert no download/partial artifact, so that specific cleanup clause is supported by implementation inspection rather than a failure-path test.
7. **No network/out-of-sandbox access:** conversion requires `office_isolated()` and uses the existing isolated HTML worker; `DataOnlyFetcher` permits only data URIs. The SVG validator rejects external resource references. `test_svg_conversion_requires_isolated_linux_worker` would fail if isolation were removed, while sanitizer tests cover representative external references. No SVG-specific test attempts a live network or host-file fetch through rendering; this criterion is supported by code-path inspection and the existing worker isolation boundary, not a direct adversarial rendering test.
8. **360 CSS-pixel usability:** opened the throwaway app at `http://127.0.0.1:8098`, set viewport to 360×780, and inspected the selected SVG tool state including its no-file error. The page content fit the viewport without horizontal overflow; controls, error, and notices were visible and usable. This was the English locale. The app/container was only read through the browser; no file was submitted and no persistent job data was changed.

## Finding

**P2 - API rejection coverage is incomplete for the single-file and size gates.** The plan explicitly requires missing/multiple files and >10 MiB to be rejected before job creation. The runtime code appears to implement these checks, but the SVG API tests do not exercise those cases or assert that no job was created. Add the three regression scenarios before treating criterion 5 as fully verified.

## Checks and limits

I read the SVG operation, API and worker paths, the relevant tests, the approved plan, and inspected the mobile UI. I did not change application code, commit, push, or alter app data. I did not independently rerun the complete test suite or Docker smoke in this review; those results are from the implementation/build evidence, while the test adequacy notes above are based on reading the tests themselves.

# Review: HTML to image

**Verdict: PASS WITH ONE TEST-COVERAGE FINDING.** The local HTML-to-image flow is implemented and the isolated Linux smoke rendered JPG and SVG output. The request's URL-based input is explicitly deferred in the plan; this review checks the local-upload stage.

## Request and scope

The request asks for HTML-to-image conversion in JPG or SVG. The plan transparently narrows this stage to one local HTML upload and defers URL fetching to a later stage to preserve the local-only worker boundary. The page, API, output formats, and README support matrix match that stage scope. Public URL conversion remains outstanding.

## Checks

- Read the request, plan, and code. The API validates the HTML file and format, dispatches `html.to_image`, and returns the generated ZIP through the existing artifact flow.
- Opened `http://127.0.0.1:8800/tools/html-to-image` in the browser at 360 x 800. PT-BR and English copy, the JPG/SVG selector, file picker, and limits were visible without horizontal overflow. The plan has no captures to compare. I did not submit a job, so the running app's data was unchanged.
- Ran `uv run pytest -q tests/test_html_to_image.py tests/test_html_to_pdf.py`: all 29 tests passed. `uv run ruff check .` passed.
- Ran the Linux Docker smoke as UID 1000 with `--network none`: local HTML rendered to PDF, JPG at 144 DPI, and SVG. HTTP, HTTPS, FTP, `file:`, and relative resources were rejected. The smoke uses a one-page document.
- Reviewed each criterion's tests. API tests cover single-file/extension/format/size validation and the ZIP job lifecycle for both formats. The archive validator tests page-count, JPG pixel, name, size, and malformed-SVG rejection. The real renderer smoke confirms the output formats and blocked-resource behavior, but it does not check multiple rendered pages or an oversized page through the child worker.

## Finding

### R1 [P2] Cover multipage image output and worker page-dimension limits

**Evidence:** `tests/test_html_to_image.py::test_html_to_image_creates_numbered_zip_download` uses a mocked one-image ZIP for both formats. `docker/html-to-pdf-smoke.py` also renders a single-page document. The archive-validator test checks an oversized JPG's dimensions after it has already been produced, but no integration test proves the HTML child rejects a page above the 40-megapixel bound (including SVG output) or emits `page-001`, `page-002` for a multipage input.

**Why it matters:** Criteria 3 and 4 require one output per page in order and enforce page-dimension bounds. A regression that dropped later pages or removed the child-side page bound would still pass the current HTML-to-image tests and smoke.

**Suggested fix:** Extend the isolated Docker smoke with a two-page HTML document and assert sequential ZIP members for both formats. Add a deliberately oversized page case and assert the job/converter fails without an artifact.

## Fix pass outcome

R1 was addressed in one pass. The isolated Linux smoke now renders two pages and asserts ordered `page-001` / `page-002` ZIP members for both JPG and SVG. It also sends a 60-inch square page through both real worker modes and requires the page-bound error plus an empty output directory. A job-level regression test confirms the bound failure results in a failed job with no downloadable artifact.

## Criterion notes

- **1:** The page accepts one `.html` / `.htm` file, explains local-only resources, and offers JPG/SVG. The live page was read in both languages at 360 px; no captures were supplied.
- **2:** Tests reject unsupported extensions, invalid/missing formats, multiple files, and uploads above 10 MiB before job creation.
- **3:** The live smoke confirms both formats and the data URI path. Resource-blocking smoke covers HTTP, HTTPS, FTP, `file:`, and relative paths using the shared renderer fetcher. Multipage output is the R1 coverage gap.
- **4:** `convert_html_to_images()` shares the `office_isolated()` gate and bounded child with HTML-to-PDF. Compose config sets `network_mode: none` and `OFFICE_NETWORK_ISOLATED=1`; Docker smoke succeeds as UID 1000 in that network mode. Code applies Landlock, 120-second timeout, 2 GiB address-space limit, 100-page limit, page-dimension limit, and output limits. The image-mode page-dimension guard lacks a real-worker regression test (R1).
- **5:** The live smoke verifies JPG encoding/DPI and valid SVG output; the parent checks ZIP names, image signatures, SVG XML, page count, and aggregate size.
- **6:** External-resource job failure tests assert no downloadable output. Worker handlers remove partial output on conversion failures; R1 recommends explicitly checking the page-bound failure path.
- **7:** The catalog and both READMEs describe local HTML, JPG/SVG, the Linux worker, page/output limits, and embedded-resource policy in PT-BR and English.

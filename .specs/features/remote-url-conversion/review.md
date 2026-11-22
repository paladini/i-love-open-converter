# Review

## Fix pass

The P2 test coverage finding was addressed. Added deterministic tests for credential rejection, redirect count, resource count, aggregate byte count, and elapsed-time enforcement; the PDF API test now asserts a query token is absent from the response, persisted job data, and captured logs. Added an explicit deadline check after the main document fetch. The per-resource read cap remains enforced during streaming in `_get`; this pass did not add a dedicated socket-streaming fixture.

Fix-pass checks passed: Ruff for the touched source/tests and the focused URL, HTML tool, and mobile browser suite (48 tests). No live URL fetch was performed.

**Verdict:** The feature implements the two requested public URL workflows and preserves the offline rendering boundary. The focused URL, HTML tool, and mobile browser tests pass (44 tests). I found one non-blocking verification gap: the safety bounds and several rejection branches in the new fetcher are not directly tested.

## Request and implementation

The original project request calls for URL input for PDF and image conversion. The request for this feature also delegates continuing the tool roadmap while excluding large application refactors. The implementation stays within the two existing HTML tools and does not touch the deferred refactor issues.

- `src/i_love_open_converter/url_snapshot.py` resolves each HTTP(S) host, rejects any non-global DNS address, pins the connection to a resolved IP, retains the HTTP Host/TLS hostname, validates redirects and subresources, and bounds resource count, bytes, redirects, and total elapsed time.
- It removes executable/active page elements, inlines CSS and supported static assets, and gives only the serialized snapshot to the existing HTML job path. The URL is not added to job options or status payloads.
- `src/i_love_open_converter/main.py` accepts URL input only for the two HTML operations, rejects mixed URL/file inputs, maps fetch failures to safe API errors, and uses the existing job and artifact paths.
- Both tool pages expose local-file and URL modes and retain localized queued, processing, success, and error states. No binding captures are supplied for the URL mode. The new browser test opens both pages at 360 CSS pixels in English and PT-BR, switches to URL mode, submits a stubbed job, checks success/download visibility, and verifies no horizontal overflow.
- README.md and README.pt-BR.md document the static renderer, public-only restriction, fetch limits, direct egress requirement, unsupported proxy settings, and network-isolated worker.

## Acceptance criteria and test evidence

1. PDF bilingual URL and file modes: page/catalog test checks labels and script operation; mobile browser test checks the URL flow in both languages. Queued/processing/error transitions are implemented in JS, but the new browser test only drives the successful transition.
2. Safe page capture and queued local snapshot: PDF API test stubs `fetch_public_html`, then checks stored HTML and `website.html`; it does not exercise the network fetcher in this API test.
3. PDF renderer and output validation: existing HTML worker and PDF validation tests cover the common conversion path; the new URL API test uses the existing worker with a stub renderer. The URL snapshot itself is local before queuing, so no URL reaches the worker.
4. Invalid scheme/private address/redirect/size/time/content rejection: tests cover loopback IP, unsupported port, mixed public/private DNS, redirect to loopback without a second connection, and non-HTML response. They do not directly test credential rejection, all redirect/resource/byte/time ceilings, or that each ceiling avoids job creation at the API boundary.
5. CSS/images and script removal: the snapshot test confirms CSS and images are embedded and `<script>` removed. It does not cover fonts or every active-resource type.
6. No URL persistence or exposure: the PDF API test includes a query token and checks the job options and job record do not contain it. It does not assert the API response or captured application logs.
7. Image bilingual URL and file modes, JPG/SVG selector, localized status and ZIP: page test checks the format selector and language content; mobile browser test submits SVG and checks successful download visibility in each language. It does not inspect the returned archive in this URL test.
8. URL-to-image format and snapshot: image API test stubs capture, checks requested format, and checks the stored snapshot artifact and successful job.
9. Per-page archive naming and output bounds: existing HTML image archive tests validate numbered pages, JPG/SVG type, page count, dimensions, and output bytes. The new URL test exercises the same worker path with a stub converter.
10. Safe errors/no partial artifact: fetch-failure API test checks no job; existing HTML failure tests check no download/artifacts. URL-specific tests do not force renderer/output failure after URL capture.
11. 360px PT-BR/English usability: the four new Playwright parameter cases cover both tools and languages, successful flow, and horizontal overflow.
12. README requirements: both language files visibly document all named limits and network/proxy constraints; no automated README assertion was added.

## Finding

**P2 — Add direct tests for URL policy bounds and sensitive-data exposure.** The implementation has code for maximum redirects, resource count, per-resource/aggregate bytes, total time, credential rejection, query-string non-persistence, and response/log privacy, but the test suite does not exercise several of those rules. Existing `tests/test_url_snapshot.py` covers loopback/port/DNS/one redirect/non-HTML and a successful CSS/image capture; existing API tests cover a query token in stored job data but not response or logs. A regression in a bound or accidental URL logging could therefore pass the current suite. Add deterministic mocked tests for the omitted bounds and assertions on API response/log records before treating the safety matrix as fully verified.

## Checks run

- `rtk uv run pytest tests/test_url_snapshot.py tests/test_html_to_pdf.py tests/test_html_to_image.py tests/test_mobile_ui.py -q` — passed, 44 tests.
- No live URL fetch was performed. The UI job API was stubbed by the browser test; capture was stubbed in the API integration tests.

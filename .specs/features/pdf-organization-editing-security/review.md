# Review — PDF organization, editing and security

## Verdict: Changes required

The stage adds the planned routes and job operations, but permanent redaction can leave the selected sensitive text recoverable in an output content stream. Other confirmed problems can corrupt or misplace user content. The Docker image containing the PDF/A dependencies was not built in this review.

## Findings

### [P1] Redacted tagged text remains recoverable in the output

`redact_pages` applies MuPDF redactions and garbage collection but retains marked-content `/ActualText` values from selected areas (`src/i_love_open_converter/pdf_ops.py:210`, `:240`). Reproduction: wrap visible text in `/Span << /ActualText (SECRET_IN_ACTUALTEXT) >> BDC ... EMC`, redact that text's entire visible area, and save with `garbage=4, deflate=True`. Normal page text extraction returns empty, yet a decompressed output stream still contains `/Span<</ActualText(SECRET_IN_ACTUALTEXT)>>BDC q Q EMC q Q`. Tagged/accessibility text is common PDF content. The existing test checks an ordinary content stream, so it passes with this leak. The result cannot safely claim permanent removal under criterion 15. Inspect and remove or safely reject affected marked content and associated structure data, including a regression that inspects the saved PDF rather than only rendered pixels and normal text extraction.

### [P1] Saving a form silently changes untouched multiline fields

The fields API omits the multiline flag, and `pdf-forms.js:13` renders every text widget as a single-line `<input>`. At submission `pdf-forms.js:20` compares the browser-normalized value with the original. I generated an existing multiline field with `line one\nline two`; the untouched browser field displayed `line oneline two`, so the code submits it as an update even when the visitor edits something else. This violates criterion 14. Existing tests use only single-line values and cannot detect it.

### [P1] Text editing silently replaces supported user characters

`edit_page` uses the built-in Base 14 fonts in `src/i_love_open_converter/pdf_ops.py:345-363` without checking glyph coverage. Reproduced in memory with the accepted text `São Paulo — café €`: `page.get_text()` returned `São Paulo ? café ?` while the operation succeeded. Criterion 8 requires the chosen text in the output; this can corrupt common punctuation and symbols. The test at `tests/test_api.py:240` checks ASCII only.

### [P1] Signature and image orientation differs from the preview on rotated pages

`edit_page` maps the rectangle through `page.derotation_matrix` but inserts the image without compensating its orientation (`pdf_ops.py:345-377`). On a page rotated 90°, an uploaded image whose left half is red and right half blue appeared red above blue in the rendered output, while the browser preview shows it left-to-right. Text insertion has the same page-rotation issue. This violates the position/style and visual-signature expectations in criteria 8 and 10. The test at `tests/test_api.py:354` counts embedded images but cannot detect orientation or placement.

### [P1] Page navigation can submit an edit against the wrong preview

`pdf-edit.js:35-37` and `pdf-crop.js:22-36` change the selected page immediately but leave the previous page image visible and the submit control enabled while the new preview request is pending. On a slow request a visitor can position an edit or signature using the old image and submit it for the new page. The redaction tool already hides its preview and disables submission while loading. No test covers this asynchronous state (criteria 6, 8 and 10).

### [P2] Unlock rejects an owner-password-protected PDF with an empty open password

`inspect_protected_pdf` rejects `not document.needs_pass` before trying the supplied password (`pdf_ops.py:402-409`). A PDF encrypted with an empty user password and a non-empty owner password has `needs_pass == 0`, but `authenticate(owner_password) == 4`; the correct current owner password is rejected with `422 invalid_file`. This is a common restriction-protected PDF, contrary to criterion 12. The current protection test creates only a PDF with a non-empty open password.

### [P2] Insertion does not offer the specified source page range or position

`pdf-organize.js:44-61` automatically appends every page from the second PDF. The visitor must remove unwanted pages and move the remaining ones individually; there is no page-range selector or insertion-position control as required by criterion 3. With a long source document, selecting a small range requires deleting potentially hundreds of rows. The API test at `tests/test_api.py:96` does not exercise this UI or distinguish identical pages from the two sources.

### [P2] Bound catalog navigation appears after the complete PDF grid

At the captured 731 × 720 viewport, `.pdf-group { order: -1 }` in `static/css/app.css:264` places the entire PDF group ahead of both the heading and category chips. In the observed DOM the PDF group began at y≈395 and category chips at y≈1519. The binding `captures/ilovepdf-home.aria.yml` places category navigation ahead of tool cards. This ordering predates this branch but remains a discrepancy in the referenced design and makes the filters hard to find. Existing catalog tests check presence and count, not visual order.

## Criterion and test audit

| Criteria | Evidence and whether tests fail if the stated rule breaks |
| --- | --- |
| 1 | The home and route tests check existence and catalog counts; they do not exercise bilingual navigation, result states, or 360–1440 px overflow. I inspected the empty organization screen at 360 px and its selected-page list at 360 and 1440 px; no horizontal overflow was observed in those states. |
| 2–3 | The API test does not exercise browser reorder/removal or source range and insertion position. Criterion 3 has the UI gap above. |
| 4–5 | `test_organize_pdf_pages_and_reject_invalid_selection` checks sequence, empty, out-of-range, duplicates and booleans. Its two inputs contain the same page text, so it cannot prove that an inserted page came from the intended input; encrypted input is not separately tested here. |
| 6–7 | Preview tests check image dimensions and invalid page numbers; crop test covers one selected rotated page and boundaries. No test drives page navigation/loading, accessible controls, or a multi-page range. |
| 8–9 | `test_pdf_edit_adds_requested_content` detects missing content types and one out-of-range rectangle. It does not assert chosen positions, dimensions, font, color, Unicode, rotated output, preview appearance, malformed colors, text lengths, or page-reference errors. The confirmed text/rotation and loading findings demonstrate the gaps. |
| 10 | `test_visual_signature_adds_an_image_to_selected_page` detects a missing image or wrong page for its sample. It cannot prove drawing, preview, orientation, position, or certificate-disclaimer behavior beyond a string assertion. |
| 11–13 | Password tests exercise valid encryption, wrong/empty/oversized passwords, absence in stored options and captured logs, and worker recovery. They do not cover owner-only restrictions, Unicode/byte boundaries, signature option classes, or error-log paths. Criterion 12 fails for owner-only encryption as described. |
| 14 | Form test checks one plain text field, checkbox, unchanged single-line field and read-only rejection. It misses multiline preservation and unsupported non-text widget behavior. |
| 15–16 | Redaction tests check one page rectangle, ordinary text streams, image pixels and an overlapping annotation; invalid rectangle and missing/read-only field are rejected. They do not check marked-content `/ActualText`, tagged structure, rotated inputs, or multiple regions. The marked-content leak above is reproducible. |
| 17 | Repair test detects failure to reconstruct a damaged cross-reference and controlled failure for an unreadable PDF. |
| 18 | Comparison test checks counts for unchanged/changed/added pages and report images, but only asserts `Removed: 0`; a broken removed-page classification would pass. UI summary was inspected in the builder's prior run but was not rerun in this review. |
| 19 | Unit tests mock both external processes, and check successful verdict, validator failures, changed text, and disabled state. They do not build the Docker image or independently validate an actual PDF/A from that image; the builder reported a separate Linux veraPDF spike. |
| 20 | No automated browser test verifies queued, processing, failed and succeeded states or downloadable artifacts for each S5 operation. The code renders these states; multiple artifacts are not emitted by these operations. |

## Checks performed

- Read the current request, stage plan, decision log, captured catalog structures, routes, processing/validation code, browser scripts and relevant tests. The request is a continuation of the larger product objective; later roadmap stages remain outside this stage plan.
- Started web and worker on localhost using a throwaway `.review-stage2` data directory; generated synthetic PDFs and an image there, then stopped the processes and removed the directory.
- Opened the catalog at 731 × 720, and the organization and forms screens using the browser. Checked the empty and populated organization views at 360 px, and the populated layout at 1440 px. Reproduced the multiline loss in the browser.
- Reproduced text corruption, rotated image orientation, owner-only password behavior and the marked-content redaction leak using in-memory synthetic PDFs. No user data was used.
- Did not build the Docker image or run the full suite again; the builder reported 71 passing tests and a Linux PDF/A spike, but those reports do not establish the built image's behavior.

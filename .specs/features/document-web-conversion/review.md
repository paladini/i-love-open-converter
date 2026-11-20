# Independent review

Verdict: changes required. The extraction fails for a valid PDF containing an image in an annotation appearance, and the status message does not follow a language change. The user's request asks to continue implementation to the end and open PRs as needed; this plan explicitly delivers only embedded-image extraction and retains the remaining conversion work for later stages, so this slice is not evidence that the overall request is complete.

## Findings

1. **P1 - A valid image in an annotation appearance makes extraction fail as an invalid PDF.** `pdf_image_order.py` walks page contents and nested forms but does not visit annotation appearance streams. `pdf_ops.py` obtains image blocks through `page.get_text("dict")`, which does include images in those appearances, and rejects the PDF when the counts differ. I reproduced this using PyMuPDF: create a page, insert a red PNG to obtain its xref, add a stamp annotation, replace its `/AP/N` Form XObject with an image drawing referencing that xref, and empty the page content stream. The annotation renders, `get_text("dict")` reports one image block, and `process_pdf("pdf.extract_images", ...)` raises `InvalidPdfError` at the length check. A PDF with normal page images and such an annotation is rejected too, rather than returning its images. No current extraction test covers annotation appearances.

2. **P2 - Changing language after completion leaves the status in the previous language.** In `static/js/pdf-extract-images.js`, `translate()` updates only `[data-pt][data-en]` elements; `#message` is populated separately from `words[lang]` and its current status key is not saved. After a success or error, the language control is enabled, and switching it changes the interface labels while leaving the success or error text in its old language. This conflicts with criterion 2. No test exercises changing language after a status appears.

## Criteria and tests

1. The link and return route exist in the templates and the application initializes PDF-to-JPG from the query parameter. No automated test asserts either navigation, so a broken link or selection would not fail the extraction tests.
2. The route, polling and PT/EN message dictionaries exist; the language-change defect above remains. No test covers the UI states, language switching or responsive layout. I opened the running local page read-only, checked the 360-pixel and 1440-pixel viewport settings, and observed no horizontal overflow in the initial state. There are no captures in this feature directory to compare. No submission was made to the running app or its existing data.
3. The API tests assert the ZIP and deduplication across pages, distinct xrefs with identical pixels, inline images, first drawing order, and a nested form. These tests would fail for those concrete regressions, but miss annotation appearances as described above.
4. The transparency test checks exact RGBA pixels and the safe `image-001.png` archive name; the drawing-order test checks colors and sequential names. They would detect loss of transparency, wrong color or changed names for those examples.
5. The no-image test checks failed state and `no_images`, but does not assert download rejection or localized UI messages. Existing generic PDF validation tests do not specifically exercise invalid and password-protected PDFs with `pdf.extract_images`.
6. Single-PDF enforcement and shared upload/retention code exist, but there is no extraction-specific test for multiple files, upload limits or retention; a regression in this operation's membership in the single-PDF set would not fail an extraction test.

The temporary PDF used for the annotation reproduction was created in a throwaway temporary directory inside the repository and removed automatically; the running application's data was not changed.

# Initial technology notes

These notes record upstream documentation relevant to the objective's named operations. They inform a future plan but do not choose its milestone or promise output quality for every input.

| Capability | Upstream evidence | Planning consequence |
| --- | --- | --- |
| PDF page editing, insertion, page reordering/deletion, text/image insertion, annotation, redaction and watermarking | PyMuPDF's official tutorial and API document PDF modification and page operations, including redaction as a two-step annotate/apply operation. <https://pymupdf.readthedocs.io/en/latest/tutorial.html> <https://pymupdf.readthedocs.io/en/latest/page.html> | Several named PDF tools can likely reuse the current PDF processing engine. Redaction needs separate correctness criteria because it must remove underlying content, not only cover it visually. |
| Image crop, resize, orientation and effects | Pillow's official ImageOps API documents crop, contain/cover/fit/pad/scale and EXIF transpose. <https://pillow.readthedocs.io/en/stable/reference/ImageOps.html> | Basic static image enhancements can extend the existing Pillow path without introducing another processing service. |
| Office to PDF | LibreOffice documents a headless mode intended for using the application without a graphical user interface. <https://help.libreoffice.org/latest/ug/text/shared/guide/start_parameters.html> | Office conversion is a system-runtime dependency, not merely a small Python package; include it only in a planned deployment image/profile and validate formats with representative documents. |
| OCR and PDF/A | Current OCRmyPDF installation documentation lists external system dependencies (including Tesseract and a PDF rasterizer), fonts and other optional encoders; its PDF/A documentation describes output modes and caveats. <https://ocrmypdf.readthedocs.io/en/latest/installation.html> <https://ocrmypdf.readthedocs.io/en/latest/advanced.html> | OCR/PDF-A support should be packaged and tested as an explicit heavyweight capability. Its external binaries and language data affect image size and offline setup. |

## Limit of this research

These sources establish documented upstream capabilities, not comparative benchmark quality, license compatibility for every possible distribution combination, support for every malformed file, or the final set of product milestones. Those require focused verification when each feature is planned.

# PDF to PowerPoint research

- The original project prompt asks for editable PowerPoint; image-only slides are insufficient. python-pptx can author individual picture and textbox shapes, and PyMuPDF's `get_text("dict")` returns text spans, bounding boxes and image blocks. Sources: python-pptx shape API, `https://python-pptx.readthedocs.io/en/latest/api/shapes.html`; PyMuPDF appendix, `https://pymupdf.readthedocs.io/en/latest/app1.html`.
- Probe: `python-pptx==1.0.2`, MIT. Pin alongside existing full `pymupdf==2.1`; create image and text shapes in the same vertical slice and confirm output opens and edits with its file-format structure.
- A real isolated AMD64 image converted a two-page PDF and loaded its output with python-pptx. LibreOffice then opened and exported the presentation to a two-page PDF with extracted editable text intact. A bridge-networked container was refused even when the operator-isolation flag was set.
- Preserve all request scope. PowerPoint is one slice; PDF-to-Excel remains required and its extraction/fidelity plan comes next.

# PDF to Markdown research

The cumulative roadmap explicitly includes PDF to Markdown. The installed `pymupdf-lite==2.1` exposes `Document.to_markdown` but raises `NotImplementedError` when called. An isolated `uv run --no-project --with pymupdf==2.1` experiment successfully converted synthetic PDF text locally. The full package requires ONNX Runtime and other dependencies; its documented layout engine and Markdown support must be tested in the project's actual image and on both supported architectures before switching the existing PDF dependency.

PyMuPDF's API can write extracted images and references; package those alongside the Markdown in a ZIP and check that paths remain relative to the archive. Disable OCR for this stage: searchable-PDF OCR is a separate roadmap capability and must not be silently claimed. Test actual text, tables and image references, network-free execution, and behavior for PDFs without extractable text.

Sources: [PyMuPDF Document API](https://pymupdf.readthedocs.io/en/latest/document.html), [layout documentation](https://pymupdf.readthedocs.io/en/latest/rag.html), [installation guidance](https://pymupdf.readthedocs.io/en/latest/installation.html).

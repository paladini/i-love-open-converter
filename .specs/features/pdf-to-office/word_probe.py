"""Probe PDF-to-DOCX compatibility with the project's PyMuPDF version."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf
from docx import Document
from pdf2docx import Converter

with TemporaryDirectory() as folder:
    root = Path(folder)
    source = root / "source.pdf"
    destination = root / "output.docx"
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "Editable document probe")
    pdf.save(source)
    pdf.close()
    converter = Converter(str(source))
    try:
        converter.convert(str(destination))
    finally:
        converter.close()
    result = Document(destination)
    assert "Editable document probe" in "\n".join(p.text for p in result.paragraphs)
    print("PDF-to-DOCX probe OK")

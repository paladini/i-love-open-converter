"""Confirm an oversized page fails without terminating the calling worker."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf

from i_love_open_converter.pdf_ops import MarkdownConversionError, process_pdf

with TemporaryDirectory() as folder:
    root = Path(folder)
    pdf = pymupdf.open()
    pdf.new_page(width=5000, height=5000).insert_text((72, 72), "Large page")
    source = root / "large.pdf"
    pdf.save(source)
    pdf.close()
    try:
        process_pdf("pdf.to_markdown", [(source, "large.pdf")], {}, root / "out")
    except MarkdownConversionError:
        print("Oversized page failed safely")
    else:
        raise AssertionError("Oversized page was accepted")

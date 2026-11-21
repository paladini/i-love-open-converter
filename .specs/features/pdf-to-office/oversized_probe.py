"""Confirm an oversized PDF page fails without terminating its caller."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf

from i_love_open_converter.pdf_ops import WordConversionError, process_pdf

with TemporaryDirectory() as folder:
    root = Path(folder)
    pdf = pymupdf.open()
    pdf.new_page(width=5000, height=5000).insert_text((72, 72), "Large page")
    source = root / "large.pdf"
    pdf.save(source)
    pdf.close()
    try:
        process_pdf("pdf.to_word", [(source, "large.pdf")], {}, root / "out")
    except WordConversionError:
        print("Oversized page failed safely")
    else:
        raise AssertionError("Oversized page was accepted")

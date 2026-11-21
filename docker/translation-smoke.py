import socket
import tempfile
from pathlib import Path

import pymupdf

from i_love_open_converter.pdf_translation import (
    _translate_text,
    translate_pdf,
)


def deny_network(*args, **kwargs):
    raise AssertionError("translation attempted network access")


socket.create_connection = deny_network
socket.socket.connect = deny_network

samples = (
    ("pb", "en", "Este é um teste de tradução."),
    ("en", "pb", "This is a translation test."),
)
for source, target, text in samples:
    translated = _translate_text(text, source, target)
    if not translated or translated.casefold() == text.casefold():
        raise SystemExit(f"Translation smoke check failed: {source} to {target}")

with tempfile.TemporaryDirectory() as directory:
    source_path = Path(directory) / "source.pdf"
    output_path = Path(directory) / "translated.pdf"
    source_document = pymupdf.open()
    source_document.new_page(width=300, height=400).insert_text((40, 60), "A short test sentence.")
    source_document.new_page(width=320, height=420)
    source_document.save(source_path)
    source_document.close()
    translate_pdf(source_path, output_path, "en", "pb")
    with pymupdf.open(source_path) as original, pymupdf.open(output_path) as translated:
        if translated.page_count != 2:
            raise SystemExit("Translation PDF smoke check changed the page count")
        if translated[0].rect != original[0].rect or translated[1].rect != original[1].rect:
            raise SystemExit("Translation PDF smoke check changed page dimensions")
        if not translated[0].get_text().strip() or translated[1].get_text().strip():
            raise SystemExit("Translation PDF smoke check did not preserve text and blank pages")

print("TRANSLATION_SMOKE_OK: both offline directions and text-only page mapping verified")

from pathlib import Path

import pymupdf
import pytest

from i_love_open_converter import pdf_translation as translation


def make_pdf(path: Path, pages: list[str]) -> None:
    document = pymupdf.open()
    for index, text in enumerate(pages):
        page = document.new_page(width=300 + index * 10, height=400 + index * 10)
        if text:
            page.insert_text((40, 60), text)
    document.save(path)
    document.close()


def test_translation_keeps_page_order_blank_pages_and_dimensions(tmp_path, monkeypatch):
    source, destination = tmp_path / "source.pdf", tmp_path / "translated.pdf"
    make_pdf(source, ["First source page.", "", "Third source page."])
    monkeypatch.setattr(
        translation,
        "_translate_text",
        lambda text, source_code, target_code: f"Translated {text}",
    )
    translation.translate_pdf(source, destination, "pb", "en")
    with pymupdf.open(source) as original, pymupdf.open(destination) as result:
        assert result.page_count == 3
        assert [page.rect.width for page in result] == [page.rect.width for page in original]
        assert [page.get_text().replace("\u00a0", " ").strip() for page in result] == [
            "Translated First source page.",
            "",
            "Translated Third source page.",
        ]


def test_translation_rejects_invalid_direction(tmp_path):
    with pytest.raises(translation.TranslationUnavailableError):
        translation.translate_pdf(tmp_path / "in.pdf", tmp_path / "out.pdf", "fr", "en")


def test_translation_rejects_scanned_pdf_without_partial_output(tmp_path):
    source, destination = tmp_path / "source.pdf", tmp_path / "translated.pdf"
    make_pdf(source, ["", ""])
    with pytest.raises(translation.NoTranslationTextError):
        translation.translate_pdf(source, destination, "pb", "en")
    assert not destination.exists()


def test_translation_rejects_too_many_pages(tmp_path):
    source, destination = tmp_path / "source.pdf", tmp_path / "translated.pdf"
    make_pdf(source, ["Page text."] * 101)
    with pytest.raises(translation.TranslationLimitError):
        translation.translate_pdf(source, destination, "pb", "en")
    assert not destination.exists()


def test_translation_rejects_excessive_extracted_text(tmp_path, monkeypatch):
    source, destination = tmp_path / "source.pdf", tmp_path / "translated.pdf"
    make_pdf(source, ["Text to extract."])
    monkeypatch.setattr(translation, "MAX_TRANSLATION_CHARACTERS", 5)
    with pytest.raises(translation.TranslationLimitError):
        translation.translate_pdf(source, destination, "pb", "en")
    assert not destination.exists()


def test_translation_rejects_page_overflow_without_partial_output(tmp_path, monkeypatch):
    source, destination = tmp_path / "source.pdf", tmp_path / "translated.pdf"
    make_pdf(source, ["Text on first page.", "Text on second page."])
    monkeypatch.setattr(translation, "_translate_text", lambda text, *args: f"translated {text}")
    original = translation._write_page

    def overflow(document, width, height, text, font_file):
        if text.endswith("second page."):
            raise translation.TranslationPageOverflowError
        original(document, width, height, text, font_file)

    monkeypatch.setattr(translation, "_write_page", overflow)
    with pytest.raises(translation.TranslationPageOverflowError):
        translation.translate_pdf(source, destination, "pb", "en")
    assert not destination.exists()


def test_sentence_chunking_never_splits_subword_tokens():
    class Tokenizer:
        def encode(self, text, out_type=str):
            return [f"{text}-{index}" for index in range(121)]

    with pytest.raises(translation.TranslationLimitError):
        translation._sentence_chunks("A long sentence.", Tokenizer())

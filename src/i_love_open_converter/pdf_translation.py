from __future__ import annotations

import functools
import os
import re
from pathlib import Path
from typing import Any

import pymupdf

MAX_TRANSLATION_PAGES = 100
MAX_TRANSLATION_CHARACTERS = 100_000
MAX_MODEL_TOKENS = 120
MIN_OUTPUT_FONT_SIZE = 6


class PdfTranslationError(Exception):
    """Base error for local PDF translation."""


class NoTranslationTextError(PdfTranslationError):
    """The PDF contains no selectable text."""


class TranslationLimitError(PdfTranslationError):
    """The PDF exceeds the local translation limits."""


class TranslationPageOverflowError(PdfTranslationError):
    """A translated page does not fit at the minimum readable font size."""


class TranslationUnavailableError(PdfTranslationError):
    """A pinned local model or runtime dependency is unavailable."""


@functools.lru_cache(maxsize=2)
def _load_direction(source_code: str, target_code: str) -> tuple[Any, Any]:
    model_root = Path(os.getenv("TRANSLATION_MODEL_DIR", "/opt/translation-models"))
    package_name = f"translate-{source_code}_{target_code}-1_9"
    package_root = model_root / package_name
    model_path = package_root / "model"
    sentencepiece_path = package_root / "sentencepiece.model"
    if not model_path.is_dir() or not sentencepiece_path.is_file():
        raise TranslationUnavailableError
    try:
        import ctranslate2
        import sentencepiece

        tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(sentencepiece_path))
        translator = ctranslate2.Translator(
            str(model_path), device="cpu", inter_threads=1, intra_threads=1
        )
    except (ImportError, OSError, RuntimeError) as exc:
        raise TranslationUnavailableError from exc
    return tokenizer, translator


def _sentence_chunks(text: str, tokenizer: Any) -> list[list[str]]:
    paragraphs = [re.sub(r"(?<!\n)\n(?!\n)", " ", part).strip() for part in text.split("\n\n")]
    chunks: list[list[str]] = []
    for paragraph in paragraphs:
        if not paragraph:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            tokens = tokenizer.encode(sentence, out_type=str)
            if not tokens:
                continue
            if len(tokens) > MAX_MODEL_TOKENS:
                fragments = re.split(r"(?<=[,;:])\s+", sentence)
                if len(fragments) == 1:
                    raise TranslationLimitError
                for fragment in fragments:
                    fragment_tokens = tokenizer.encode(fragment, out_type=str)
                    if len(fragment_tokens) > MAX_MODEL_TOKENS:
                        raise TranslationLimitError
                    if fragment_tokens:
                        chunks.append(fragment_tokens)
                continue
            chunks.append(tokens)
    return chunks


def _translate_text(text: str, source_code: str, target_code: str) -> str:
    tokenizer, translator = _load_direction(source_code, target_code)
    translated: list[str] = []
    for tokens in _sentence_chunks(text, tokenizer):
        result = translator.translate_batch(
            [tokens],
            batch_type="tokens",
            max_batch_size=1,
            beam_size=4,
            num_hypotheses=1,
            replace_unknowns=True,
            length_penalty=0.2,
        )[0]
        translated.append(tokenizer.decode(result.hypotheses[0]).strip())
    return " ".join(item for item in translated if item)


def _font_path() -> str | None:
    candidates = (
        os.getenv("TRANSLATION_FONT_FILE"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    )
    return next((font for font in candidates if font and Path(font).is_file()), None)


def _write_page(
    document: pymupdf.Document,
    width: float,
    height: float,
    text: str,
    font_file: str | None,
) -> None:
    if not text:
        document.new_page(width=width, height=height)
        return

    for font_size in (12, 10, 9, 8, 7, MIN_OUTPUT_FONT_SIZE):
        page = document.new_page(width=width, height=height)
        spare = page.insert_textbox(
            page.rect + (42, 42, -42, -42),
            text,
            fontname="translated" if font_file else "helv",
            fontfile=font_file,
            fontsize=font_size,
            lineheight=1.25,
            color=(0.12, 0.13, 0.17),
        )
        if spare >= 0:
            return
        document.delete_page(-1)
    raise TranslationPageOverflowError


def translate_pdf(
    source: Path,
    destination: Path,
    source_code: str,
    target_code: str,
) -> None:
    if (source_code, target_code) not in {("pb", "en"), ("en", "pb")}:
        raise TranslationUnavailableError
    try:
        with pymupdf.open(source) as original:
            if not original.is_pdf or original.needs_pass or original.page_count < 1:
                raise pymupdf.FileDataError
            if original.page_count > MAX_TRANSLATION_PAGES:
                raise TranslationLimitError
            pages = [page.get_text("text", sort=True) for page in original]
            normalized_pages = [
                re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n")).strip()
                for text in pages
            ]
            text_characters = sum(len(text) for text in normalized_pages)
            if text_characters > MAX_TRANSLATION_CHARACTERS:
                raise TranslationLimitError
            if not any(normalized_pages):
                raise NoTranslationTextError

            font_file = _font_path()
            with pymupdf.open() as translated_document:
                for original_page, page_text in zip(original, normalized_pages, strict=True):
                    translated_text = (
                        _translate_text(page_text, source_code, target_code) if page_text else ""
                    )
                    _write_page(
                        translated_document,
                        original_page.rect.width,
                        original_page.rect.height,
                        translated_text,
                        font_file,
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                translated_document.save(destination, garbage=3, deflate=True)
    except (
        NoTranslationTextError,
        TranslationLimitError,
        TranslationPageOverflowError,
        TranslationUnavailableError,
    ):
        raise
    except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
        raise InvalidTranslatedPdfError from exc


class InvalidTranslatedPdfError(PdfTranslationError):
    """The source PDF is malformed, encrypted, or unreadable."""

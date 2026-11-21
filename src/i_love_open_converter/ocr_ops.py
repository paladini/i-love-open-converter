from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import pymupdf

MAX_OCR_PAGES = 20
MAX_OCR_OUTPUT_BYTES = 256 * 1024 * 1024
OCR_TIMEOUT_SECONDS = 600


class OcrProcessingError(Exception):
    """The local OCR process failed or produced an invalid result."""


class NoOcrTextError(OcrProcessingError):
    """The result contains no selectable text."""


def make_searchable_pdf(source: Path, destination: Path, language: str) -> Path:
    try:
        with pymupdf.open(source) as original:
            if not original.is_pdf or original.needs_pass or original.is_repaired:
                raise OcrProcessingError
            if not 1 <= original.page_count <= MAX_OCR_PAGES:
                raise OcrProcessingError
            original_pages = [
                (page.rect, page.rotation, page.get_text("text")) for page in original
            ]

        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            "-m",
            "ocrmypdf",
            "--skip-text",
            "--output-type",
            "pdf",
            "--optimize",
            "0",
            "--jobs",
            "1",
            "--language",
            language,
            "--tesseract-timeout",
            "25",
            "--max-image-mpixels",
            "40",
            "--max-ocr-image-mpixels",
            "40",
            "--quiet",
            str(source.resolve()),
            str(destination.resolve()),
        ]
        environment = {
            **os.environ,
            "OMP_NUM_THREADS": "1",
            "OMP_THREAD_LIMIT": "1",
            "OPENBLAS_NUM_THREADS": "1",
        }
        process_options = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        with subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            **process_options,
        ) as process:
            try:
                return_code = process.wait(timeout=OCR_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired as exc:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise OcrProcessingError from exc

        if return_code != 0 or not destination.is_file():
            raise OcrProcessingError
        if destination.stat().st_size > MAX_OCR_OUTPUT_BYTES:
            raise OcrProcessingError

        with pymupdf.open(destination) as converted:
            if (
                not converted.is_pdf
                or converted.needs_pass
                or converted.is_repaired
                or converted.page_count != len(original_pages)
            ):
                raise OcrProcessingError
            converted_pages = list(converted)
            if any(
                abs(original_page[0].width - result_page.rect.width) > 0.01
                or abs(original_page[0].height - result_page.rect.height) > 0.01
                or original_page[1] != result_page.rotation
                for original_page, result_page in zip(original_pages, converted_pages, strict=True)
            ):
                raise OcrProcessingError
            searchable_text = [page.get_text("text") for page in converted_pages]
            if not any(text.strip() for text in searchable_text):
                raise NoOcrTextError
            for original_page, output_text in zip(original_pages, searchable_text, strict=True):
                if original_page[2].strip() and output_text != original_page[2]:
                    raise OcrProcessingError
        return destination
    except (OSError, RuntimeError, ValueError) as exc:
        destination.unlink(missing_ok=True)
        raise OcrProcessingError from exc
    except OcrProcessingError:
        destination.unlink(missing_ok=True)
        raise

from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import shutil
import tempfile
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pymupdf
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData, Headers, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from .config import Settings, get_settings
from .database import create_job, get_job, initialize
from .files import safe_filename
from .image_ops import INPUT_FORMATS, InvalidImageError, UnsupportedImageError, inspect_image
from .office_ops import FAMILIES
from .pdf_archive import pdfa_available
from .pdf_ops import (
    InvalidPdfError,
    inspect_pdf,
    inspect_protected_pdf,
    list_form_fields,
    validate_crop_options,
    validate_edit_options,
    validate_form_updates,
    validate_page_ranges,
    validate_redactions,
)

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
PDF_COMING_SOON = [
    ("PDF para Excel", "PDF to Excel", "convert", 6),
    ("HTML para PDF", "HTML to PDF", "convert", 16),
    ("PDF para PDF/A", "PDF to PDF/A", "convert", 20),
    ("Digitalize e transforme em PDF", "Scan to PDF", "workflows", 23),
    ("OCR PDF", "OCR PDF", "intelligence", 24),
    ("Resumir com IA", "AI summary", "intelligence", 29),
    ("Traduzir PDF", "Translate PDF", "intelligence", 30),
]
IMAGE_COMING_SOON = [
    ("Recortar IMAGEM", "Crop IMAGE", "img-edit", 3),
    ("Converter de JPG", "Convert from JPG", "img-convert", 5),
    ("Editor de fotos", "Photo editor", "img-edit", 6),
    ("Melhorar Imagem", "Upscale image", "img-create", 7),
    ("Remover fundo", "Remove background", "img-edit", 8),
    ("Marcar IMAGEM", "Watermark IMAGE", "img-edit", 9),
    ("Gerador de memes", "Meme generator", "img-create", 10),
    ("HTML para IMAGEM", "HTML to IMAGE", "img-convert", 12),
    ("Desfocar cara", "Blur faces", "img-security", 13),
]


class UploadLimitExceeded(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class LimitedMultiPartParser(MultiPartParser):
    """Enforce file size limits while multipart bytes are still streaming in."""

    def __init__(
        self,
        headers: Headers,
        stream,
        *,
        max_files: int,
        max_file_bytes: int,
        max_total_bytes: int,
    ) -> None:
        super().__init__(
            headers, stream, max_files=max_files, max_fields=3, max_part_size=1024 * 1024
        )
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes
        self._current_file_bytes = 0
        self._total_file_bytes = 0

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self._current_file_bytes = 0

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            chunk_size = end - start
            self._current_file_bytes += chunk_size
            self._total_file_bytes += chunk_size
            if self._current_file_bytes > self.max_file_bytes:
                raise UploadLimitExceeded(
                    "file_too_large", "O arquivo excede o limite configurado."
                )
            if self._total_file_bytes > self.max_total_bytes:
                raise UploadLimitExceeded("request_too_large", "O envio excede o limite total.")
        super().on_part_data(data, start, end)


async def parse_limited_upload_form(request: Request, settings: Settings):
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {"code": "invalid_options", "message": "Envie um formulário multipart."}
            },
        )
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            body_size = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Content-Length inválido.") from exc
        # Reject known oversized requests before the multipart parser creates temporary files.
        if body_size > settings.max_total_upload_bytes + 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail={
                    "error": {
                        "code": "request_too_large",
                        "message": "O envio excede o limite total.",
                    }
                },
            )

    async def bounded_stream():
        body_bytes = 0
        async for chunk in request.stream():
            body_bytes += len(chunk)
            if body_bytes > settings.max_total_upload_bytes + 1024 * 1024:
                raise UploadLimitExceeded("request_too_large", "O envio excede o limite total.")
            yield chunk

    parser = LimitedMultiPartParser(
        request.headers,
        bounded_stream(),
        max_files=settings.max_files_per_job,
        max_file_bytes=settings.max_file_size_bytes,
        max_total_bytes=settings.max_total_upload_bytes,
    )
    try:
        return await parser.parse()
    except UploadLimitExceeded as exc:
        raise HTTPException(
            status_code=413,
            detail={"error": {"code": exc.code, "message": exc.message}},
        ) from exc
    except MultiPartException as exc:
        if str(exc).startswith("Too many files"):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "too_many_files",
                        "message": "A quantidade de arquivos excede o limite.",
                    }
                },
            ) from exc
        raise HTTPException(
            status_code=400,
            detail={
                "error": {"code": "invalid_options", "message": "O formulário enviado é inválido."}
            },
        ) from exc


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings.prepare()
        initialize(settings.database_path)
        yield

    app = FastAPI(title="I Love Open Converter", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            payload = detail
        else:
            payload = {"error": {"code": "request_failed", "message": str(detail)}}
        return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        del exc
        return JSONResponse(
            status_code=422,
            content={
                "error": {"code": "invalid_options", "message": "Verifique os campos enviados."}
            },
        )

    @app.get("/", include_in_schema=False)
    async def index(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "max_file_size_mb": settings.max_file_size_mb,
                "pdf_coming_soon": [
                    item for item in PDF_COMING_SOON if item[3] != 20 or not pdfa_available()
                ],
                "pdfa_available": pdfa_available(),
                "image_coming_soon": IMAGE_COMING_SOON,
            },
        )

    @app.get("/tools/pdf-watermark", include_in_schema=False)
    async def pdf_watermark(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "pdf-tool.html",
            {
                "request": request,
                "tool": "watermark",
                "max_file_size_mb": settings.max_file_size_mb,
            },
        )

    @app.get("/tools/pdf-page-numbers", include_in_schema=False)
    async def pdf_page_numbers(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "pdf-tool.html",
            {
                "request": request,
                "tool": "page-numbers",
                "max_file_size_mb": settings.max_file_size_mb,
            },
        )

    @app.get("/tools/pdf-organize", include_in_schema=False)
    async def pdf_organize(request: Request):
        return TEMPLATES.TemplateResponse(request, "pdf-organize.html", {"request": request})

    @app.get("/tools/pdf-crop", include_in_schema=False)
    async def pdf_crop(request: Request):
        return TEMPLATES.TemplateResponse(request, "pdf-crop.html", {"request": request})

    @app.get("/tools/pdf-edit", include_in_schema=False)
    async def pdf_edit(request: Request):
        return TEMPLATES.TemplateResponse(
            request, "pdf-edit.html", {"request": request, "sign": False}
        )

    @app.get("/tools/pdf-sign", include_in_schema=False)
    async def pdf_sign(request: Request):
        return TEMPLATES.TemplateResponse(
            request, "pdf-edit.html", {"request": request, "sign": True}
        )

    @app.get("/tools/pdf-redact", include_in_schema=False)
    async def pdf_redact(request: Request):
        return TEMPLATES.TemplateResponse(request, "pdf-redact.html", {"request": request})

    @app.get("/tools/pdf-forms", include_in_schema=False)
    async def pdf_forms(request: Request):
        return TEMPLATES.TemplateResponse(request, "pdf-forms.html", {"request": request})

    @app.get("/tools/pdf-repair", include_in_schema=False)
    async def pdf_repair(request: Request):
        return TEMPLATES.TemplateResponse(request, "pdf-repair.html", {"request": request})

    @app.get("/tools/pdf-extract-images", include_in_schema=False)
    async def pdf_extract_images(request: Request):
        return TEMPLATES.TemplateResponse(request, "pdf-extract-images.html", {"request": request})

    @app.get("/tools/pdf-to-markdown", include_in_schema=False)
    async def pdf_to_markdown(request: Request):
        return TEMPLATES.TemplateResponse(request, "pdf-to-markdown.html", {"request": request})

    @app.get("/tools/pdf-to-word", include_in_schema=False)
    async def pdf_to_word(request: Request):
        return TEMPLATES.TemplateResponse(request, "pdf-to-word.html", {"request": request})

    @app.get("/tools/pdf-to-powerpoint", include_in_schema=False)
    async def pdf_to_powerpoint(request: Request):
        return TEMPLATES.TemplateResponse(
            request, "pdf-to-powerpoint.html", {"request": request}
        )

    @app.get("/tools/office-to-pdf/{family}", include_in_schema=False)
    async def office_to_pdf(request: Request, family: str):
        labels = {
            "word": ("Word", ".doc,.docx"),
            "powerpoint": ("PowerPoint", ".ppt,.pptx"),
            "excel": ("Excel", ".xls,.xlsx"),
        }
        if family not in labels:
            raise HTTPException(status_code=404)
        title, extensions = labels[family]
        return TEMPLATES.TemplateResponse(
            request, "office-to-pdf.html", {"request": request, "family": family,
                                           "title": title, "extensions": extensions}
        )

    @app.get("/tools/pdf-compare", include_in_schema=False)
    async def pdf_compare(request: Request):
        return TEMPLATES.TemplateResponse(request, "pdf-compare.html", {"request": request})

    @app.get("/tools/pdf-pdfa", include_in_schema=False)
    async def pdf_pdfa(request: Request):
        if not pdfa_available():
            raise HTTPException(
                status_code=503,
                detail={"error": {"code": "service_unavailable", "message": "PDF/A indisponível."}},
            )
        return TEMPLATES.TemplateResponse(request, "pdf-pdfa.html", {"request": request})

    @app.get("/tools/pdf-{action}", include_in_schema=False)
    async def pdf_password_tool(request: Request, action: str):
        if action not in {"protect", "unlock"}:
            raise HTTPException(status_code=404, detail="Not found")
        return TEMPLATES.TemplateResponse(
            request, "pdf-password.html", {"request": request, "action": action}
        )

    @app.post("/api/pdf/pages")
    async def pdf_pages(request: Request):
        form = await parse_limited_upload_form(request, settings)
        try:
            files = form.getlist("files")
            if len(files) != 1 or not isinstance(files[0], UploadFile):
                raise HTTPException(status_code=422, detail={"error": {"code": "invalid_file"}})
            with tempfile.TemporaryDirectory(dir=settings.data_dir) as directory:
                path = Path(directory) / "input.pdf"
                with path.open("wb") as target:
                    shutil.copyfileobj(files[0].file, target)
                try:
                    count = inspect_pdf(path)
                except InvalidPdfError as exc:
                    raise HTTPException(
                        status_code=422, detail={"error": {"code": "invalid_file"}}
                    ) from exc
            return {"page_count": count}
        finally:
            await form.close()

    @app.post("/api/pdf/preview")
    async def pdf_preview(request: Request):
        form = await parse_limited_upload_form(request, settings)
        try:
            files = form.getlist("files")
            page_value = form.get("page", "1")
            if (
                len(files) != 1
                or not isinstance(files[0], UploadFile)
                or not isinstance(page_value, str)
                or not page_value.isascii()
                or not page_value.isdecimal()
                or len(page_value) > 9
                or int(page_value) < 1
            ):
                raise HTTPException(status_code=422, detail={"error": {"code": "invalid_options"}})
            with tempfile.TemporaryDirectory(dir=settings.data_dir) as directory:
                path = Path(directory) / "input.pdf"
                with path.open("wb") as target:
                    shutil.copyfileobj(files[0].file, target)
                try:
                    count = inspect_pdf(path)
                    page_number = int(page_value)
                    if page_number > count:
                        raise HTTPException(
                            status_code=422, detail={"error": {"code": "invalid_options"}}
                        )
                    with pymupdf.open(path) as document:
                        page = document[page_number - 1]
                        scale = min(1.0, 1000 / max(page.rect.width, page.rect.height))
                        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                        image = BytesIO(pixmap.tobytes("png"))
                except InvalidPdfError as exc:
                    raise HTTPException(
                        status_code=422, detail={"error": {"code": "invalid_file"}}
                    ) from exc
                except (RuntimeError, ValueError, ZeroDivisionError) as exc:
                    raise HTTPException(
                        status_code=422, detail={"error": {"code": "invalid_file"}}
                    ) from exc
            return Response(
                content=image.getvalue(),
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
        finally:
            await form.close()

    @app.post("/api/pdf/fields")
    async def pdf_fields(request: Request):
        form = await parse_limited_upload_form(request, settings)
        try:
            files = form.getlist("files")
            if len(files) != 1 or not isinstance(files[0], UploadFile):
                raise HTTPException(status_code=422, detail={"error": {"code": "invalid_file"}})
            with tempfile.TemporaryDirectory(dir=settings.data_dir) as directory:
                path = Path(directory) / "input.pdf"
                with path.open("wb") as target:
                    shutil.copyfileobj(files[0].file, target)
                try:
                    inspect_pdf(path)
                    with pymupdf.open(path) as document:
                        fields = list_form_fields(document)
                except (InvalidPdfError, RuntimeError, ValueError) as exc:
                    raise HTTPException(
                        status_code=422, detail={"error": {"code": "invalid_file"}}
                    ) from exc
            return {"fields": fields}
        finally:
            await form.close()

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        try:
            with settings.database_path.open("ab"):
                pass
        except OSError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": {"code": "service_unavailable", "message": "Serviço indisponível."}
                },
            ) from exc
        return {"status": "ok"}

    @app.post("/api/jobs", status_code=202)
    async def submit_job(request: Request) -> dict[str, str]:
        form = await parse_limited_upload_form(request, settings)
        try:
            return await process_upload_form(request, form)
        finally:
            await form.close()

    async def process_upload_form(request: Request, form: FormData) -> dict[str, str]:
        operation = form.get("operation")
        options = form.get("options", "{}")
        raw_files = form.getlist("files")
        files = [item for item in raw_files if isinstance(item, UploadFile)]
        if (
            not isinstance(operation, str)
            or not isinstance(options, str)
            or len(files) != len(raw_files)
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_options",
                        "message": "O formulário enviado é inválido.",
                    }
                },
            )
        supported_operations = {
            *FAMILIES,
            "image.convert",
            "image.resize",
            "image.compress",
            "image.rotate",
            "image.to_pdf",
            "pdf.merge",
            "pdf.split",
            "pdf.rotate",
            "pdf.compress",
            "pdf.to_image",
            "pdf.extract_images",
            "pdf.to_markdown",
            "pdf.to_word",
            "pdf.to_powerpoint",
            "pdf.watermark",
            "pdf.page_numbers",
            "pdf.organize",
            "pdf.crop",
            "pdf.edit",
            "pdf.sign",
            "pdf.protect",
            "pdf.unlock",
            "pdf.redact",
            "pdf.forms",
            "pdf.repair",
            "pdf.compare",
            "pdf.pdfa",
        }
        if operation not in supported_operations:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {"code": "unsupported_operation", "message": "Operação indisponível."}
                },
            )
        if len(files) > settings.max_files_per_job:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "too_many_files",
                        "message": "A quantidade de arquivos excede o limite.",
                    }
                },
            )
        if not files:
            raise HTTPException(
                status_code=422,
                detail={"error": {"code": "invalid_options", "message": "Selecione um arquivo."}},
            )
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                body_size = int(content_length)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Content-Length inválido.") from exc
            # Allow a small multipart envelope beyond the actual configured file limit.
            if body_size > settings.max_total_upload_bytes + 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "error": {
                            "code": "request_too_large",
                            "message": "O envio excede o limite total.",
                        }
                    },
                )

        try:
            parsed_options: Any = json.loads(options)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {"code": "invalid_options", "message": "As opções não são válidas."}
                },
            ) from exc
        if not isinstance(parsed_options, dict):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {"code": "invalid_options", "message": "As opções não são válidas."}
                },
            )
        image_operations = {"image.convert", "image.resize", "image.compress", "image.rotate"}
        if operation == "pdf.merge" and not 2 <= len(files) <= settings.max_files_per_job:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {"code": "invalid_options", "message": "Selecione de 2 a 10 PDFs."}
                },
            )
        single_pdf_operations = {
            "pdf.split",
            "pdf.rotate",
            "pdf.compress",
            "pdf.to_image",
            "pdf.extract_images",
            "pdf.to_markdown",
            "pdf.to_word",
            "pdf.to_powerpoint",
            "pdf.page_numbers",
            "pdf.crop",
            "pdf.protect",
            "pdf.unlock",
            "pdf.redact",
            "pdf.forms",
            "pdf.repair",
            "pdf.pdfa",
        }
        if (operation in single_pdf_operations or operation in FAMILIES) and len(files) != 1:
            raise HTTPException(
                status_code=422,
                detail={"error": {"code": "invalid_options", "message": "Selecione um arquivo."}},
            )
        if operation == "image.to_pdf" and len(files) > settings.max_files_per_job:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "too_many_files",
                        "message": "A quantidade de arquivos excede o limite.",
                    }
                },
            )
        validated_options: dict[str, Any] = {}
        if operation == "pdf.pdfa" and not pdfa_available():
            raise HTTPException(
                status_code=503,
                detail={"error": {"code": "service_unavailable", "message": "PDF/A indisponível."}},
            )
        if operation == "pdf.compare":
            language = parsed_options.get("language", "pt-BR")
            if len(files) != 2 or language not in ("pt-BR", "en"):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {"code": "invalid_options", "message": "Selecione dois PDFs."}
                    },
                )
            validated_options["language"] = language
        secret = form.get("password") if operation in {"pdf.protect", "pdf.unlock"} else None
        if operation in {"pdf.protect", "pdf.unlock"} and (
            not isinstance(secret, str)
            or not secret
            or "\0" in secret
            or len(secret.encode("utf-8")) > 40
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_options" if operation == "pdf.protect" else "invalid_file",
                        "message": "Senha inválida.",
                    }
                },
            )
        watermark_kind: str | None = None
        if operation == "pdf.watermark":
            watermark_kind = parsed_options.get("kind")
            if watermark_kind not in {"text", "image"}:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "invalid_options",
                            "message": "Escolha uma marca d'água de texto ou imagem.",
                        }
                    },
                )
            expected_files = 2 if watermark_kind == "image" else 1
            if len(files) > expected_files:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "too_many_files",
                            "message": "A quantidade de arquivos excede o limite.",
                        }
                    },
                )
            if len(files) != expected_files:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "invalid_options",
                            "message": "Selecione o PDF e a imagem de marca d'água.",
                        }
                    },
                )
            if watermark_kind == "image":
                extensions = [
                    Path(safe_filename(item.filename or "arquivo")).suffix.lower() for item in files
                ]
                if (
                    extensions.count(".pdf") > 1
                    or sum(ext in {".png", ".jpg", ".jpeg", ".webp"} for ext in extensions) > 1
                ):
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": {
                                "code": "too_many_files",
                                "message": "Envie um PDF e uma imagem de marca d'água.",
                            }
                        },
                    )
                if (
                    extensions.count(".pdf") != 1
                    or sum(ext in {".png", ".jpg", ".jpeg", ".webp"} for ext in extensions) != 1
                ):
                    raise HTTPException(
                        status_code=415,
                        detail={
                            "error": {
                                "code": "unsupported_format",
                                "message": "Envie um PDF e uma imagem PNG, JPG ou WebP.",
                            }
                        },
                    )

            position = parsed_options.get("position", "center")
            valid_positions = {
                "top_left",
                "top_center",
                "top_right",
                "center_left",
                "center",
                "center_right",
                "bottom_left",
                "bottom_center",
                "bottom_right",
            }
            if position not in valid_positions:
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Posição inválida."}},
                )
            raw_opacity = parsed_options.get("opacity", 0.3)
            try:
                opacity = float(raw_opacity)
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Opacidade inválida."}},
                ) from exc
            if isinstance(raw_opacity, bool) or not 0.1 <= opacity <= 1.0:
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Opacidade inválida."}},
                )
            validated_options.update(kind=watermark_kind, position=position, opacity=opacity)
            if watermark_kind == "text":
                text = parsed_options.get("text")
                font = parsed_options.get("font", "helv")
                font_size = parsed_options.get("font_size", 24)
                color = parsed_options.get("color", "#808080")
                if not isinstance(text, str) or not text.strip() or len(text) > 500:
                    raise HTTPException(
                        status_code=422,
                        detail={"error": {"code": "invalid_options", "message": "Texto inválido."}},
                    )
                if font not in {"helv", "tiro", "cour"}:
                    raise HTTPException(
                        status_code=422,
                        detail={"error": {"code": "invalid_options", "message": "Fonte inválida."}},
                    )
                if (
                    isinstance(font_size, bool)
                    or not str(font_size).isdigit()
                    or not 8 <= int(font_size) <= 72
                ):
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": {
                                "code": "invalid_options",
                                "message": "Tamanho de fonte inválido.",
                            }
                        },
                    )
                if not isinstance(color, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", color) is None:
                    raise HTTPException(
                        status_code=422,
                        detail={"error": {"code": "invalid_options", "message": "Cor inválida."}},
                    )
                validated_options.update(
                    text=text.strip(), font=font, font_size=int(font_size), color=color
                )

        if operation == "pdf.page_numbers":
            position = parsed_options.get("position", "bottom_center")
            format_name = parsed_options.get("format", "number")
            start = parsed_options.get("start", 1)
            font = parsed_options.get("font", "helv")
            font_size = parsed_options.get("font_size", 12)
            color = parsed_options.get("color", "#000000")
            language = parsed_options.get("language", "pt-BR")
            if position not in {
                "top_left",
                "top_center",
                "top_right",
                "bottom_left",
                "bottom_center",
                "bottom_right",
            }:
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Posição inválida."}},
                )
            if format_name not in {"number", "number_total", "page_number_total"}:
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Formato inválido."}},
                )
            if isinstance(start, bool) or not str(start).isdigit() or not 1 <= int(start) <= 999999:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {"code": "invalid_options", "message": "Número inicial inválido."}
                    },
                )
            if font not in {"helv", "tiro", "cour"}:
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Fonte inválida."}},
                )
            if (
                isinstance(font_size, bool)
                or not str(font_size).isdigit()
                or not 8 <= int(font_size) <= 48
            ):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "invalid_options",
                            "message": "Tamanho de fonte inválido.",
                        }
                    },
                )
            if not isinstance(color, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", color) is None:
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Cor inválida."}},
                )
            if language not in {"pt-BR", "en"}:
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Idioma inválido."}},
                )
            validated_options.update(
                position=position,
                format=format_name,
                start=int(start),
                font=font,
                font_size=int(font_size),
                color=color,
                language=language,
            )
        output_format = "PNG"
        if operation in image_operations:
            output_format = str(parsed_options.get("format", "PNG")).upper()
            if output_format not in {"JPEG", "JPG", "PNG", "WEBP"}:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "invalid_options",
                            "message": "Formato de saída inválido.",
                        }
                    },
                )
            validated_options["format"] = "JPEG" if output_format == "JPG" else output_format
        if operation == "image.resize":
            for dimension in ("width", "height"):
                raw = parsed_options.get(dimension)
                if raw in (None, ""):
                    continue
                if isinstance(raw, bool) or not str(raw).isdigit() or not 1 <= int(raw) <= 10000:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": {"code": "invalid_options", "message": "Dimensões inválidas."}
                        },
                    )
                validated_options[dimension] = int(raw)
            if not any(key in validated_options for key in ("width", "height")):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "invalid_options",
                            "message": "Informe largura ou altura.",
                        }
                    },
                )
        if operation == "image.rotate":
            degrees = parsed_options.get("degrees")
            if isinstance(degrees, bool) or str(degrees) not in {"90", "180", "270"}:
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Ângulo inválido."}},
                )
            validated_options["degrees"] = int(degrees)
        if operation == "pdf.rotate":
            degrees = parsed_options.get("degrees")
            if isinstance(degrees, bool) or str(degrees) not in {"90", "180", "270"}:
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Ângulo inválido."}},
                )
            validated_options["degrees"] = int(degrees)
        if operation == "pdf.split":
            ranges = parsed_options.get("ranges")
            if not isinstance(ranges, str) or not ranges.strip():
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "invalid_options",
                            "message": "Informe intervalos de páginas.",
                        }
                    },
                )
            validated_options["ranges"] = ranges
        if operation == "pdf.organize":
            pages = parsed_options.get("pages")
            if (
                not isinstance(pages, list)
                or not pages
                or len(files) > 2
                or any(
                    not isinstance(item, list)
                    or len(item) != 2
                    or any(type(value) is not int or value < 1 for value in item)
                    for item in pages
                )
                or len({tuple(item) for item in pages}) != len(pages)
            ):
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Páginas inválidas."}},
                )
            validated_options["pages"] = pages
        if operation == "pdf.crop":
            validated_options = {
                "rectangle": parsed_options.get("rectangle"),
                "ranges": parsed_options.get("ranges"),
            }
        if operation == "pdf.redact":
            validated_options = {"regions": parsed_options.get("regions")}
        if operation == "pdf.forms":
            validated_options = {"updates": parsed_options.get("updates")}
        if operation in {"pdf.edit", "pdf.sign"}:
            validated_options = {
                key: parsed_options.get(key)
                for key in (
                    "kind",
                    "page",
                    "rectangle",
                    "color",
                    "text",
                    "font",
                    "font_size",
                    "shape",
                )
            }
            expected = 2 if validated_options["kind"] == "image" else 1
            if operation == "pdf.sign" and validated_options["kind"] != "image":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {"code": "invalid_options", "message": "Assinatura inválida."}
                    },
                )
            if (
                len(files) != expected
                or Path(files[0].filename or "").suffix.lower() != ".pdf"
                or (
                    expected == 2
                    and Path(files[1].filename or "").suffix.lower()
                    not in {".png", ".jpg", ".jpeg", ".webp"}
                )
            ):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "invalid_options",
                            "message": "Selecione os arquivos necessários.",
                        }
                    },
                )
        if operation == "image.compress" or (
            operation in image_operations and output_format in {"JPEG", "JPG", "WEBP"}
        ):
            quality = parsed_options.get("quality", 85)
            if (
                isinstance(quality, bool)
                or not str(quality).isdigit()
                or not 1 <= int(quality) <= 100
            ):
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Qualidade inválida."}},
                )
            validated_options["quality"] = int(quality)

        job_id = str(uuid4())
        job_dir = settings.jobs_dir / job_id
        input_dir = job_dir / "input"
        input_dir.mkdir(parents=True, exist_ok=False)
        stored: list[dict[str, Any]] = []
        pdf_page_counts: list[int] = []
        total_size = 0
        try:
            if len(files) > settings.max_files_per_job:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "too_many_files",
                            "message": "A quantidade de arquivos excede o limite.",
                        }
                    },
                )
            for index, upload in enumerate(files):
                original_name = safe_filename(upload.filename or "imagem")
                extension = Path(original_name).suffix.lower()
                accepted_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
                is_pdf_operation = operation.startswith("pdf.")
                if operation in FAMILIES and extension not in FAMILIES[operation]:
                    raise HTTPException(
                        status_code=415,
                        detail={"error": {"code": "unsupported_format",
                                          "message": "Formato de documento não suportado."}},
                    )
                is_watermark_image = (
                    (operation == "pdf.watermark" and watermark_kind == "image")
                    or (
                        operation in {"pdf.edit", "pdf.sign"}
                        and validated_options["kind"] == "image"
                        and index == 1
                    )
                ) and extension in {".png", ".jpg", ".jpeg", ".webp"}
                if is_pdf_operation and extension != ".pdf" and not is_watermark_image:
                    raise HTTPException(
                        status_code=415,
                        detail={
                            "error": {
                                "code": "unsupported_format",
                                "message": "Envie um arquivo PDF.",
                            }
                        },
                    )
                if (
                    not is_pdf_operation
                    and operation != "image.to_pdf"
                    and operation not in FAMILIES
                    and extension not in accepted_extensions
                ):
                    raise HTTPException(
                        status_code=415,
                        detail={
                            "error": {
                                "code": "unsupported_format",
                                "message": "Formato de imagem não suportado.",
                            }
                        },
                    )
                destination = input_dir / f"{index}_{original_name}"
                file_size = 0
                with destination.open("xb") as target:
                    while chunk := await upload.read(64 * 1024):
                        file_size += len(chunk)
                        total_size += len(chunk)
                        if file_size > settings.max_file_size_bytes:
                            raise HTTPException(
                                status_code=413,
                                detail={
                                    "error": {
                                        "code": "file_too_large",
                                        "message": "O arquivo excede o limite configurado.",
                                    }
                                },
                            )
                        if total_size > settings.max_total_upload_bytes:
                            raise HTTPException(
                                status_code=413,
                                detail={
                                    "error": {
                                        "code": "request_too_large",
                                        "message": "O envio excede o limite total.",
                                    }
                                },
                            )
                        target.write(chunk)
                if operation in FAMILIES:
                    content_type = "application/octet-stream"
                elif is_pdf_operation and not is_watermark_image:
                    try:
                        page_count = (
                            0
                            if operation == "pdf.repair"
                            else inspect_protected_pdf(destination, secret)
                            if operation == "pdf.unlock"
                            else inspect_pdf(destination)
                        )
                        pdf_page_counts.append(page_count)
                        content_type = "application/pdf"
                    except InvalidPdfError as exc:
                        raise HTTPException(
                            status_code=422,
                            detail={
                                "error": {
                                    "code": "invalid_file",
                                    "message": "O PDF é inválido ou protegido por senha.",
                                }
                            },
                        ) from exc
                    if operation == "pdf.split":
                        try:
                            validate_page_ranges(validated_options["ranges"], page_count)
                        except InvalidPdfError as exc:
                            raise HTTPException(
                                status_code=422,
                                detail={
                                    "error": {
                                        "code": "invalid_options",
                                        "message": "Intervalos de páginas inválidos para este PDF.",
                                    }
                                },
                            ) from exc
                    if operation == "pdf.crop":
                        try:
                            validate_crop_options(validated_options, page_count)
                        except InvalidPdfError as exc:
                            raise HTTPException(
                                status_code=422,
                                detail={
                                    "error": {
                                        "code": "invalid_options",
                                        "message": "Recorte inválido.",
                                    }
                                },
                            ) from exc
                    if operation == "pdf.redact":
                        try:
                            validate_redactions(validated_options, page_count)
                        except InvalidPdfError as exc:
                            raise HTTPException(
                                status_code=422,
                                detail={
                                    "error": {
                                        "code": "invalid_options",
                                        "message": "Áreas inválidas.",
                                    }
                                },
                            ) from exc
                    if operation == "pdf.forms":
                        try:
                            with pymupdf.open(destination) as document:
                                validate_form_updates(document, validated_options["updates"])
                        except InvalidPdfError as exc:
                            raise HTTPException(
                                status_code=422,
                                detail={
                                    "error": {
                                        "code": "invalid_options",
                                        "message": "Campos inválidos.",
                                    }
                                },
                            ) from exc
                    if operation in {"pdf.edit", "pdf.sign"}:
                        try:
                            validate_edit_options(validated_options, page_count)
                        except InvalidPdfError as exc:
                            raise HTTPException(
                                status_code=422,
                                detail={
                                    "error": {
                                        "code": "invalid_options",
                                        "message": "Edição inválida.",
                                    }
                                },
                            ) from exc
                else:
                    try:
                        image_format, content_type = inspect_image(destination)
                    except UnsupportedImageError as exc:
                        raise HTTPException(
                            status_code=415,
                            detail={
                                "error": {
                                    "code": "unsupported_format",
                                    "message": "Formato de imagem não suportado.",
                                }
                            },
                        ) from exc
                    except InvalidImageError as exc:
                        raise HTTPException(
                            status_code=422,
                            detail={
                                "error": {
                                    "code": "invalid_file",
                                    "message": "O arquivo não é uma imagem válida.",
                                }
                            },
                        ) from exc
                    if image_format not in INPUT_FORMATS or (
                        is_watermark_image and image_format not in {"PNG", "JPEG", "WEBP"}
                    ):
                        raise HTTPException(
                            status_code=415,
                            detail={
                                "error": {
                                    "code": "unsupported_format",
                                    "message": "Formato de imagem não suportado.",
                                }
                            },
                        )
                stored.append(
                    {
                        "name": original_name,
                        "relative_path": destination.relative_to(settings.data_dir).as_posix(),
                        "content_type": content_type,
                        "size_bytes": file_size,
                    }
                )
            if operation == "pdf.organize" and any(
                file_number > len(pdf_page_counts) or page > pdf_page_counts[file_number - 1]
                for file_number, page in validated_options["pages"]
            ):
                raise HTTPException(
                    status_code=422,
                    detail={"error": {"code": "invalid_options", "message": "Páginas inválidas."}},
                )
            if secret is not None:
                descriptor = os.open(
                    job_dir / "secret", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
                    secret_file.write(secret)
            create_job(
                settings.database_path,
                job_id=job_id,
                operation=operation,
                options=validated_options,
                retention_hours=settings.job_retention_hours,
                artifacts=stored,
            )
        except Exception:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise
        finally:
            for upload in files:
                await upload.close()

        return {"job_id": job_id, "state": "queued", "status_url": f"/api/jobs/{job_id}"}

    @app.get("/api/jobs/{job_id}")
    async def job_status(job_id: str) -> dict[str, Any]:
        try:
            normalized_id = str(UUID(job_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "job_not_found", "message": "Conversão não encontrada."}},
            ) from exc
        job = get_job(settings.database_path, normalized_id)
        if job is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "job_not_found", "message": "Conversão não encontrada."}},
            )
        response: dict[str, Any] = {"job_id": normalized_id, "state": job["state"]}
        if job["state"] == "failed":
            response["error"] = {"code": job["error_code"], "message": job["error_message"]}
        if job["state"] == "succeeded":
            outputs = [item for item in job["artifacts"] if item["role"] == "output"]
            inputs = [item for item in job["artifacts"] if item["role"] == "input"]
            response["download_url"] = f"/api/jobs/{normalized_id}/download"
            response["input_size_bytes"] = sum(item["size_bytes"] for item in inputs)
            response["files"] = [
                {"name": item["name"], "size_bytes": item["size_bytes"]} for item in outputs
            ]
        return response

    @app.get("/api/jobs/{job_id}/download")
    async def download(job_id: str) -> FileResponse:
        try:
            normalized_id = str(UUID(job_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "job_not_found", "message": "Conversão não encontrada."}},
            ) from exc
        job = get_job(settings.database_path, normalized_id)
        if job is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "job_not_found", "message": "Conversão não encontrada."}},
            )
        if job["state"] != "succeeded":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "job_not_ready",
                        "message": "O arquivo ainda está sendo preparado.",
                    }
                },
            )
        outputs = [item for item in job["artifacts"] if item["role"] == "output"]
        if len(outputs) != 1:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "job_not_found", "message": "Resultado não encontrado."}},
            )
        artifact = outputs[0]
        path = (settings.data_dir / artifact["relative_path"]).resolve()
        if not path.is_relative_to(settings.data_dir.resolve()) or not path.is_file():
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "job_not_found", "message": "Resultado não encontrado."}},
            )
        media_type = artifact["content_type"] or mimetypes.guess_type(artifact["name"])[0]
        return FileResponse(
            path,
            filename=artifact["name"],
            media_type=media_type or "application/octet-stream",
        )

    return app


app = create_app()

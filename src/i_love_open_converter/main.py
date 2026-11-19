from __future__ import annotations

import json
import logging
import mimetypes
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData, Headers, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from .config import Settings, get_settings
from .database import create_job, get_job, initialize
from .files import safe_filename
from .image_ops import INPUT_FORMATS, InvalidImageError, UnsupportedImageError, inspect_image
from .pdf_ops import InvalidPdfError, inspect_pdf, validate_page_ranges

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")


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
            headers, stream, max_files=max_files, max_fields=2, max_part_size=1024 * 1024
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
            {"request": request, "max_file_size_mb": settings.max_file_size_mb},
        )

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
        single_pdf_operations = {"pdf.split", "pdf.rotate", "pdf.compress", "pdf.to_image"}
        if operation in single_pdf_operations and len(files) != 1:
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
                if is_pdf_operation and extension != ".pdf":
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
                if is_pdf_operation:
                    try:
                        page_count = inspect_pdf(destination)
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
                    if image_format not in INPUT_FORMATS:
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

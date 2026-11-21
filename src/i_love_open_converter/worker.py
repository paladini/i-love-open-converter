from __future__ import annotations

import logging
import os
import shutil
import time
from zipfile import ZIP_DEFLATED, ZipFile

from .config import Settings, get_settings
from .database import (
    claim_next_job,
    delete_expired_jobs,
    find_expired_jobs,
    find_interrupted_jobs,
    initialize,
    mark_failed,
    mark_succeeded,
    requeue_interrupted_jobs,
)
from .files import safe_stem
from .image_ops import InvalidImageError, UnsupportedImageError, process_image
from .office_ops import FAMILIES, OfficeConversionError, OfficeUnavailableError, convert_office
from .pdf_ops import (
    InvalidPdfError,
    MarkdownConversionError,
    NoEmbeddedImagesError,
    WordConversionError,
    WordUnavailableError,
    process_pdf,
)

logger = logging.getLogger(__name__)


def process_one_job(settings: Settings) -> bool:
    job = claim_next_job(settings.database_path)
    if job is None:
        return False

    job_id = job["id"]
    job_dir = settings.jobs_dir / job_id
    try:
        if job["operation"] in FAMILIES:
            inputs = [item for item in job["artifacts"] if item["role"] == "input"]
            if len(inputs) != 1:
                raise OfficeConversionError
            source = (settings.data_dir / inputs[0]["relative_path"]).resolve()
            if not source.is_relative_to(settings.data_dir.resolve()):
                raise OfficeConversionError
            destination = convert_office(source, job_dir / "output")
            output_name = destination.name
            content_type = "application/pdf"
            size_bytes = destination.stat().st_size
        elif job["operation"] in {
            "image.convert",
            "image.resize",
            "image.compress",
            "image.rotate",
        }:
            input_artifacts = [item for item in job["artifacts"] if item["role"] == "input"]
            if not input_artifacts:
                raise InvalidImageError
            output_dir = job_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_format = str(job["options"].get("format", "PNG")).upper()
            extension = "jpg" if output_format in {"JPEG", "JPG"} else output_format.lower()
            generated: list[tuple[str, str, int]] = []
            for index, source_artifact in enumerate(input_artifacts, start=1):
                source = (settings.data_dir / source_artifact["relative_path"]).resolve()
                if not source.is_relative_to(settings.data_dir.resolve()):
                    raise InvalidImageError
                stem = safe_stem(source_artifact["name"])
                if any(name.rsplit(".", 1)[0] == stem for name, _, _ in generated):
                    stem = f"{stem}-{index}"
                output_name = f"{stem}.{extension}"
                destination = output_dir / output_name
                content_type, size_bytes = process_image(
                    source, destination, job["operation"], job["options"]
                )
                generated.append((output_name, content_type, size_bytes))
            if len(generated) == 1:
                output_name, content_type, size_bytes = generated[0]
            else:
                output_name = "converted-images.zip"
                destination = output_dir / output_name
                with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
                    for name, _, _ in generated:
                        archive.write(output_dir / name, arcname=name)
                        (output_dir / name).unlink()
                content_type = "application/zip"
                size_bytes = destination.stat().st_size
        elif job["operation"] in {
            "pdf.merge",
            "pdf.split",
            "pdf.rotate",
            "pdf.compress",
            "pdf.to_image",
            "pdf.extract_images",
            "pdf.to_markdown",
            "pdf.to_word",
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
            "image.to_pdf",
        }:
            input_artifacts = [item for item in job["artifacts"] if item["role"] == "input"]
            sources = []
            for artifact in input_artifacts:
                source = (settings.data_dir / artifact["relative_path"]).resolve()
                if not source.is_relative_to(settings.data_dir.resolve()):
                    raise InvalidPdfError
                sources.append((source, artifact["name"]))
            output_dir = job_dir / "output"
            secret = (
                (job_dir / "secret").read_text(encoding="utf-8")
                if job["operation"] in {"pdf.protect", "pdf.unlock"}
                else None
            )
            paths, content_type = process_pdf(
                job["operation"], sources, job["options"], output_dir, secret
            )
            if len(paths) > 1 or job["operation"] in {
                "pdf.split",
                "pdf.to_image",
                "pdf.extract_images",
                "pdf.to_markdown",
            }:
                output_name = "converted-files.zip"
                destination = output_dir / output_name
                with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
                    for path in paths:
                        archive.write(path, arcname=path.name)
                        path.unlink()
                content_type = "application/zip"
            else:
                destination = paths[0]
                output_name = destination.name
            size_bytes = destination.stat().st_size
        else:
            raise UnsupportedImageError
        mark_succeeded(
            settings.database_path,
            job_id,
            [
                {
                    "name": output_name,
                    "relative_path": destination.relative_to(settings.data_dir).as_posix(),
                    "content_type": content_type,
                    "size_bytes": size_bytes,
                }
            ],
            settings.job_retention_hours,
        )
    except OfficeUnavailableError:
        mark_failed(
            settings.database_path, job_id, "office_unavailable",
            "Conversor Office indisponível ou sem isolamento de rede e de arquivos.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except OfficeConversionError:
        mark_failed(
            settings.database_path, job_id, "office_failed",
            "Não foi possível converter o documento Office.", settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except UnsupportedImageError:
        mark_failed(
            settings.database_path,
            job_id,
            "unsupported_format",
            "Formato de imagem não suportado.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except InvalidImageError:
        mark_failed(
            settings.database_path,
            job_id,
            "invalid_file",
            "O arquivo não é uma imagem válida.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except NoEmbeddedImagesError:
        mark_failed(
            settings.database_path,
            job_id,
            "no_images",
            "O PDF não contém imagens extraíveis.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except WordUnavailableError:
        mark_failed(
            settings.database_path, job_id, "word_unavailable",
            "PDF para Word exige um worker Linux isolado da rede.", settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except WordConversionError:
        mark_failed(
            settings.database_path, job_id, "word_failed",
            "A conversão Word falhou ou excedeu os limites de processamento.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except MarkdownConversionError:
        mark_failed(
            settings.database_path, job_id, "markdown_failed",
            "A conversão Markdown falhou ou excedeu os limites de processamento.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except InvalidPdfError:
        mark_failed(
            settings.database_path,
            job_id,
            "invalid_file",
            "O arquivo PDF está inválido ou protegido por senha.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except Exception:
        if job["operation"] in {"pdf.protect", "pdf.unlock"}:
            logger.error("Unexpected processing failure for password-protected job %s", job_id)
        else:
            logger.exception("Unexpected processing failure for job %s", job_id)
        mark_failed(
            settings.database_path,
            job_id,
            "processing_failed",
            "Não foi possível processar este arquivo.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    finally:
        if job["operation"] in {"pdf.protect", "pdf.unlock"}:
            try:
                (job_dir / "secret").unlink(missing_ok=True)
            except OSError:
                logger.error("Could not remove temporary secret for job %s", job_id)
    return True


def cleanup_expired_jobs(settings: Settings) -> int:
    jobs_root = settings.jobs_dir.resolve()
    expired = find_expired_jobs(settings.database_path)
    deleted: list[str] = []
    for job_id in expired:
        job_dir = (jobs_root / job_id).resolve()
        if job_dir == jobs_root or not job_dir.is_relative_to(jobs_root):
            continue
        try:
            shutil.rmtree(job_dir, ignore_errors=False)
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("Could not remove expired job files for %s", job_id)
            continue
        deleted.append(job_id)
    return delete_expired_jobs(settings.database_path, deleted)


def recover_interrupted_jobs(settings: Settings) -> int:
    jobs_root = settings.jobs_dir.resolve()
    interrupted = find_interrupted_jobs(settings.database_path)
    requeued: list[str] = []
    for job_id in interrupted:
        job_dir = (jobs_root / job_id).resolve()
        output_dir = (job_dir / "output").resolve()
        if job_dir == jobs_root or not job_dir.is_relative_to(jobs_root):
            continue
        try:
            shutil.rmtree(output_dir, ignore_errors=False)
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("Could not clear partial output for interrupted job %s", job_id)
            continue
        requeued.append(job_id)
    return requeue_interrupted_jobs(settings.database_path, requeued, settings.job_retention_hours)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    settings = get_settings()
    settings.prepare()
    initialize(settings.database_path)
    recovered = recover_interrupted_jobs(settings)
    if recovered:
        logger.info("Requeued %s interrupted conversion jobs", recovered)
    logger.info("Worker started; waiting for conversion jobs")
    while True:
        removed = cleanup_expired_jobs(settings)
        if removed:
            logger.info("Removed %s expired conversion jobs", removed)
        if not process_one_job(settings):
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()

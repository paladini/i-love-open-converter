from __future__ import annotations

import logging
import os
import shutil
import time

from .config import Settings, get_settings
from .database import claim_next_job, delete_expired_jobs, initialize, mark_failed, mark_succeeded
from .files import safe_stem
from .image_ops import InvalidImageError, UnsupportedImageError, convert_image

logger = logging.getLogger(__name__)


def process_one_job(settings: Settings) -> bool:
    job = claim_next_job(settings.database_path)
    if job is None:
        return False

    job_id = job["id"]
    job_dir = settings.jobs_dir / job_id
    try:
        if job["operation"] != "image.convert":
            raise UnsupportedImageError
        input_artifacts = [item for item in job["artifacts"] if item["role"] == "input"]
        if len(input_artifacts) != 1:
            raise InvalidImageError
        source_artifact = input_artifacts[0]
        source = (settings.data_dir / source_artifact["relative_path"]).resolve()
        if not source.is_relative_to(settings.data_dir.resolve()):
            raise InvalidImageError
        output_dir = job_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_format = str(job["options"].get("format", "PNG")).upper()
        extension = "jpg" if output_format in {"JPEG", "JPG"} else output_format.lower()
        output_name = f"{safe_stem(source_artifact['name'])}.{extension}"
        destination = output_dir / output_name
        content_type, size_bytes = convert_image(source, destination, output_format)
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
        )
    except UnsupportedImageError:
        mark_failed(
            settings.database_path, job_id, "unsupported_format", "Formato de imagem não suportado."
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except InvalidImageError:
        mark_failed(
            settings.database_path, job_id, "invalid_file", "O arquivo não é uma imagem válida."
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except Exception:
        logger.exception("Unexpected processing failure for job %s", job_id)
        mark_failed(
            settings.database_path,
            job_id,
            "processing_failed",
            "Não foi possível processar este arquivo.",
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    return True


def cleanup_expired_jobs(settings: Settings) -> int:
    removed = 0
    jobs_root = settings.jobs_dir.resolve()
    for job_id in delete_expired_jobs(settings.database_path):
        job_dir = (jobs_root / job_id).resolve()
        if job_dir.is_relative_to(jobs_root):
            shutil.rmtree(job_dir, ignore_errors=True)
            removed += 1
    return removed


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    settings = get_settings()
    settings.prepare()
    initialize(settings.database_path)
    logger.info("Worker started; waiting for conversion jobs")
    while True:
        removed = cleanup_expired_jobs(settings)
        if removed:
            logger.info("Removed %s expired conversion jobs", removed)
        if not process_one_job(settings):
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()

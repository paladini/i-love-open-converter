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
from .heic_ops import (
    HeicConversionError,
    HeicImageTooLargeError,
    HeicUnavailableError,
    InvalidHeicError,
    convert_heic_to_image,
)
from .html_ops import HtmlConversionError, HtmlExternalResourceError, HtmlUnavailableError
from .image_ops import (
    InvalidImageError,
    InvalidImageOptionsError,
    NoFacesDetectedError,
    NoPlatesDetectedError,
    UnsupportedImageError,
    create_animated_gif,
    inspect_image,
    process_image,
)
from .ocr_ops import NoOcrTextError, OcrProcessingError
from .office_ops import FAMILIES, OfficeConversionError, OfficeUnavailableError, convert_office
from .pdf_ops import (
    ExcelConversionError,
    ExcelUnavailableError,
    InvalidPdfError,
    MarkdownConversionError,
    NoEmbeddedImagesError,
    NoSpreadsheetDataError,
    NoSummaryTextError,
    PowerPointConversionError,
    PowerPointUnavailableError,
    SummaryLimitError,
    WordConversionError,
    WordUnavailableError,
    process_pdf,
)
from .pdf_translation import (
    NoTranslationTextError,
    TranslationLimitError,
    TranslationPageOverflowError,
    TranslationUnavailableError,
)
from .psd_ops import (
    InvalidPsdError,
    PsdConversionError,
    PsdUnavailableError,
    convert_psd_to_image,
)
from .raw_ops import (
    InvalidRawError,
    RawConversionError,
    RawImageTooLargeError,
    RawUnavailableError,
    convert_raw_to_jpeg,
)
from .svg_ops import (
    InvalidSvgError,
    SvgConversionError,
    SvgUnavailableError,
    convert_svg_to_image,
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
            "image.from_jpg",
            "image.from_heic",
            "image.from_raw",
            "image.from_psd",
            "image.from_svg",
            "image.resize",
            "image.compress",
            "image.rotate",
            "image.meme",
            "image.upscale",
            "image.remove_background",
            "image.blur_faces",
            "image.blur_plates",
            "image.blur_regions",
            "image.editor",
            "image.crop",
            "image.watermark",
        }:
            input_artifacts = [item for item in job["artifacts"] if item["role"] == "input"]
            if not input_artifacts:
                raise InvalidImageError
            output_dir = job_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_format = str(job["options"].get("format", "PNG")).upper()
            extension = "jpg" if output_format in {"JPEG", "JPG"} else output_format.lower()
            generated: list[tuple[str, str, int]] = []
            if job["operation"] == "image.from_jpg" and output_format == "GIF":
                sources = []
                for artifact in input_artifacts:
                    source = (settings.data_dir / artifact["relative_path"]).resolve()
                    if not source.is_relative_to(settings.data_dir.resolve()):
                        raise InvalidImageError
                    if inspect_image(source)[0] != "JPEG":
                        raise UnsupportedImageError
                    sources.append(source)
                output_name = f"{safe_stem(input_artifacts[0]['name'])}.gif"
                destination = output_dir / output_name
                content_type, size_bytes = create_animated_gif(sources, destination)
                generated.append((output_name, content_type, size_bytes))
            else:
                source_count = int(job["options"].get("source_count", len(input_artifacts)))
                if not 1 <= source_count <= len(input_artifacts):
                    raise InvalidImageError
                source_artifacts = input_artifacts[:source_count]
                watermark_path = None
                if job["operation"] == "image.watermark" and job["options"].get("kind") == "image":
                    if source_count != len(input_artifacts) - 1:
                        raise InvalidImageError
                    watermark_path = (
                        settings.data_dir / input_artifacts[-1]["relative_path"]
                    ).resolve()
                    if not watermark_path.is_relative_to(settings.data_dir.resolve()):
                        raise InvalidImageError
                for index, source_artifact in enumerate(source_artifacts, start=1):
                    source = (settings.data_dir / source_artifact["relative_path"]).resolve()
                    if not source.is_relative_to(settings.data_dir.resolve()):
                        raise InvalidImageError
                    stem = safe_stem(source_artifact["name"])
                    if any(name.rsplit(".", 1)[0] == stem for name, _, _ in generated):
                        stem = f"{stem}-{index}"
                    output_name = f"{stem}.{extension}"
                    destination = output_dir / output_name
                    if job["operation"] == "image.from_svg":
                        content_type, size_bytes = convert_svg_to_image(
                            source,
                            destination,
                            output_format,
                            int(job["options"]["width"]),
                            int(job["options"]["height"]),
                        )
                    elif job["operation"] == "image.from_heic":
                        content_type, size_bytes = convert_heic_to_image(
                            source,
                            destination,
                            output_format,
                        )
                    elif job["operation"] == "image.from_raw":
                        content_type, size_bytes = convert_raw_to_jpeg(
                            source,
                            destination,
                            output_format,
                        )
                    elif job["operation"] == "image.from_psd":
                        content_type, size_bytes = convert_psd_to_image(
                            source,
                            destination,
                            output_format,
                            int(job["options"]["width"]),
                            int(job["options"]["height"]),
                        )
                    else:
                        content_type, size_bytes = process_image(
                            source,
                            destination,
                            job["operation"],
                            job["options"],
                            watermark_path=watermark_path,
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
            "pdf.to_powerpoint",
            "pdf.to_excel",
            "pdf.summary",
            "pdf.translate",
            "html.to_pdf",
            "html.to_image",
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
            "pdf.ocr",
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
    except HtmlUnavailableError:
        mark_failed(
            settings.database_path, job_id, "html_unavailable",
            "HTML para PDF exige um worker Linux isolado da rede e do sistema de arquivos.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except HtmlExternalResourceError:
        mark_failed(
            settings.database_path, job_id, "html_external_resource",
            "O HTML usa recursos externos. Incorpore-os como data URI e tente novamente.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except HtmlConversionError:
        mark_failed(
            settings.database_path, job_id, "html_failed",
            "Não foi possível converter o HTML. Verifique o arquivo e os limites de processamento.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except OfficeUnavailableError:
        mark_failed(
            settings.database_path,
            job_id,
            "office_unavailable",
            "Conversor Office indisponível ou sem isolamento de rede e de arquivos.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except OfficeConversionError:
        mark_failed(
            settings.database_path,
            job_id,
            "office_failed",
            "Não foi possível converter o documento Office.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except NoFacesDetectedError:
        mark_failed(
            settings.database_path,
            job_id,
            "no_faces_detected",
            "Nenhum rosto foi detectado. Revise a imagem e tente novamente.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except NoPlatesDetectedError:
        mark_failed(
            settings.database_path,
            job_id,
            "no_plates_detected",
            "Nenhuma placa foi detectada. Confira a imagem ou selecione as regiões manualmente.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except InvalidSvgError:
        mark_failed(
            settings.database_path,
            job_id,
            "invalid_file",
            "O SVG não é válido ou usa recursos não suportados.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except SvgUnavailableError:
        mark_failed(
            settings.database_path,
            job_id,
            "svg_unavailable",
            "A conversão de SVG exige um worker Linux isolado.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except SvgConversionError:
        mark_failed(
            settings.database_path,
            job_id,
            "conversion_failed",
            "Não foi possível converter este SVG dentro dos limites locais.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except HeicImageTooLargeError:
        mark_failed(
            settings.database_path,
            job_id,
            "image_too_large",
            "A imagem HEIC/HEIF excede o limite de 40 MP ou a dimensão máxima.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except InvalidHeicError:
        mark_failed(
            settings.database_path,
            job_id,
            "invalid_file",
            (
                "O HEIC/HEIF está inválido, não tem uma imagem principal compatível "
                "ou contém mais de uma imagem."
            ),
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except HeicUnavailableError:
        mark_failed(
            settings.database_path,
            job_id,
            "heic_unavailable",
            "A conversão de HEIC exige um worker Linux isolado com o decodificador local.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except HeicConversionError:
        mark_failed(
            settings.database_path,
            job_id,
            "conversion_failed",
            "Não foi possível converter este HEIC/HEIF dentro dos limites locais.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except RawImageTooLargeError:
        mark_failed(
            settings.database_path,
            job_id,
            "raw_image_too_large",
            "A imagem RAW excede o limite de 40 MP ou a dimensão máxima.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except InvalidRawError:
        mark_failed(
            settings.database_path,
            job_id,
            "invalid_file",
            "O RAW está inválido, truncado ou não é compatível.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except RawUnavailableError:
        mark_failed(
            settings.database_path,
            job_id,
            "raw_unavailable",
            "A conversão RAW exige um worker Linux isolado com o decodificador local.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except RawConversionError:
        mark_failed(
            settings.database_path,
            job_id,
            "conversion_failed",
            "Não foi possível converter este RAW dentro dos limites locais.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except InvalidPsdError:
        mark_failed(
            settings.database_path,
            job_id,
            "invalid_file",
            "O PSD é inválido ou contém recursos não suportados.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except PsdUnavailableError:
        mark_failed(
            settings.database_path,
            job_id,
            "psd_unavailable",
            "A conversão de PSD exige um worker Linux isolado.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except PsdConversionError:
        mark_failed(
            settings.database_path,
            job_id,
            "conversion_failed",
            "Não foi possível converter este PSD dentro dos limites locais.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except NoOcrTextError:
        mark_failed(
            settings.database_path,
            job_id,
            "ocr_no_text",
            "Nenhum texto foi reconhecido. Confira a qualidade do documento.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except NoSummaryTextError:
        mark_failed(
            settings.database_path,
            job_id,
            "summary_no_text",
            "O PDF não contém texto selecionável. Execute OCR antes de gerar o resumo.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except SummaryLimitError:
        mark_failed(
            settings.database_path,
            job_id,
            "summary_too_large",
            "O PDF excede os limites do resumo local.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except NoTranslationTextError:
        mark_failed(
            settings.database_path,
            job_id,
            "translation_no_text",
            "O PDF não contém texto selecionável. Execute OCR antes de traduzir.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except TranslationLimitError:
        mark_failed(
            settings.database_path,
            job_id,
            "translation_too_large",
            "O PDF excede os limites da tradução local.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except TranslationPageOverflowError:
        mark_failed(
            settings.database_path,
            job_id,
            "translation_page_overflow",
            "O texto traduzido não cabe na página com tamanho legível.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except TranslationUnavailableError:
        mark_failed(
            settings.database_path,
            job_id,
            "translation_unavailable",
            "Os modelos locais de tradução não estão disponíveis.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except OcrProcessingError:
        mark_failed(
            settings.database_path,
            job_id,
            "ocr_failed",
            "Não foi possível reconhecer o PDF dentro dos limites de processamento.",
            settings.job_retention_hours,
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
    except InvalidImageOptionsError:
        mark_failed(
            settings.database_path,
            job_id,
            "crop_out_of_bounds",
            "O recorte precisa caber dentro de cada imagem.",
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
            settings.database_path,
            job_id,
            "word_unavailable",
            "PDF para Word exige um worker Linux isolado da rede.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except PowerPointUnavailableError:
        mark_failed(
            settings.database_path,
            job_id,
            "powerpoint_unavailable",
            "PDF para PowerPoint exige um worker Linux isolado da rede.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except PowerPointConversionError:
        mark_failed(
            settings.database_path,
            job_id,
            "powerpoint_failed",
            "A conversão para PowerPoint falhou ou excedeu os limites de processamento.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except ExcelUnavailableError:
        mark_failed(
            settings.database_path,
            job_id,
            "excel_unavailable",
            "PDF para Excel exige um worker Linux isolado da rede.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except NoSpreadsheetDataError:
        mark_failed(
            settings.database_path,
            job_id,
            "no_extractable_data",
            "O PDF não contém tabelas detectadas nem texto selecionável.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except ExcelConversionError:
        mark_failed(
            settings.database_path,
            job_id,
            "excel_failed",
            "A extração para Excel falhou ou excedeu os limites de processamento.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except WordConversionError:
        mark_failed(
            settings.database_path,
            job_id,
            "word_failed",
            "A conversão Word falhou ou excedeu os limites de processamento.",
            settings.job_retention_hours,
        )
        shutil.rmtree(job_dir / "output", ignore_errors=True)
    except MarkdownConversionError:
        mark_failed(
            settings.database_path,
            job_id,
            "markdown_failed",
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

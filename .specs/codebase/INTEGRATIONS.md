# External Integrations

## Core Principle: Zero Third-Party Cloud Dependencies

By architectural decision (`AD-001`, `AD-006`), **I Love Open Converter** integrates with **no external SaaS APIs, analytics, telemetry, authentication providers, or cloud storage** at runtime.

## Local Runtime Integrations

### 1. Local SQLite Job Queue
- **Location:** `src/i_love_open_converter/database.py`
- **Purpose:** Coordinates asynchronous conversion jobs between the FastAPI web server and the background worker process over a shared local volume.

### 2. Optional Public URL Snapshotter (`html.to_pdf`, `html.to_image`)
- **Location:** `src/i_love_open_converter/url_snapshot.py`
- **Purpose:** Only when a user explicitly submits a public `http(s)://` URL, fetches bounded HTML/CSS/images while pinning DNS and blocking private/loopback/link-local SSRF ranges (`AD-023`), before handing an offline snapshot to the network-isolated WeasyPrint worker.

### 3. Local Native Binaries & Offline Models
- **LibreOffice (`soffice`)**: Office-to-PDF conversion in isolated Linux worker (`office_sandbox.py`).
- **Ghostscript + veraPDF**: PDF/A-2b conversion and validation (`pdf_archive.py`).
- **Tesseract OCR**: Local Portuguese and English OCR (`ocr_ops.py`).
- **CTranslate2 + SentencePiece**: Local offline PDF summarization and PT-BR/EN translation (`pdf_translation.py`).

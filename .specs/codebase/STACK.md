# Tech Stack

**Analyzed:** 2026-11-26

## Core

- **Framework:** FastAPI + Starlette + Jinja2 Templates
- **Language:** Python 3.14+ (`requires-python >= 3.14`)
- **Runtime:** Uvicorn ASGI server + dedicated Python SQLite polling worker
- **Package Manager:** `uv` (`uv.lock` locked dependencies)

## Frontend

- **UI Architecture:** Server-rendered Jinja2 HTML templates (`src/i_love_open_converter/templates/*.html`) + modular vanilla ES2022 scripts (`src/i_love_open_converter/static/js/*.js`)
- **Styling:** Self-hosted modern CSS (`src/i_love_open_converter/static/css/app.css`) using OKLCH color tokens, CSS Grid/Flexbox, tabular numerals, and domain-adaptive CSS custom properties (`data-domain="pdf|image"`)
- **Fonts:** Bundled offline DejaVu fonts (`/static/fonts/*.ttf`) paired with geometric system/display fallbacks; zero external CDN requests
- **Localization:** Client-side reactive dictionary (`pt-BR` and `en`) persisted in `localStorage` (`i-love-open-converter-language`)

## Backend & Conversion Pipelines

- **API Style:** REST + streaming multipart upload parser (`LimitedMultiPartParser`)
- **Database & Queue:** Local SQLite (`database.py`) storing job metadata and state transitions (`queued` → `processing` → `succeeded` / `failed`)
- **PDF Engine:** PyMuPDF (`pymupdf`), `pypdf`, Ghostscript + veraPDF (PDF/A-2b), `pdf2docx`, `python-pptx`, `openpyxl`
- **Image Engine:** Pillow, OpenCV headless, ONNX Runtime (`rembg`/background removal), `psd-tools`, `pi-heif`/isolated decoders, `rawpy`/LibRaw, WeasyPrint (HTML/SVG)
- **Local AI / NLP:** CTranslate2 + SentencePiece (offline FLAN-T5-small PDF summary & Argos PT-BR/EN translation), Tesseract OCR

## Testing & Quality

- **Unit & Integration:** `pytest` + FastAPI `TestClient`
- **End-to-End Browser:** `playwright.sync_api` (Chromium headless at 360px mobile and 1280px+ desktop viewports)
- **Linting & Formatting:** `ruff check .` and `ruff format --check`

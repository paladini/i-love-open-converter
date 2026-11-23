# I Love Open Converter

**A private, self-hosted toolkit for everyday PDF and image tasks.**

Upload a file, choose a tool, and download the result from a simple web
interface. Processing and file storage stay on your own server.

<p align="center">
  <img src="docs/screenshots/home.jpg" alt="English home page showing the PDF and image tool catalog" width="100%">
</p>
<p align="center">
  <img src="docs/screenshots/image-compress-result.jpg" alt="Image compression completed in the English interface" width="49%">
  <img src="docs/screenshots/pdf-page-numbers-result.jpg" alt="PDF page numbering completed in the English interface" width="49%">
</p>

<p align="center">
  <a href="README.pt-BR.md">Português (Brasil)</a> ·
  <a href="https://github.com/paladini/i-love-open-converter/releases">Releases</a> ·
  <a href="https://github.com/paladini/i-love-open-converter/pkgs/container/i-love-open-converter">Container image</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="SUPPORT.md">Support</a> ·
  <a href="SECURITY.md">Security</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

<p align="center">
  <a href="https://github.com/paladini/i-love-open-converter/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/paladini/i-love-open-converter?display_name=tag"></a>
  <a href="LICENSE"><img alt="AGPL-3.0 license" src="https://img.shields.io/github/license/paladini/i-love-open-converter"></a>
  <a href="https://github.com/paladini/i-love-open-converter/pkgs/container/i-love-open-converter"><img alt="Container image on GHCR" src="https://img.shields.io/badge/container-GHCR-2496ED?logo=github"></a>
</p>

I Love Open Converter is a free, self-hosted toolkit for everyday PDF and image workflows. Choose a tool, upload a file, and download the result from your own server.

## Features

- **PDF:** organize, edit, merge, split, secure, OCR, summarize, translate, compare, redact, and convert PDFs.
- **Images:** convert, compress, resize, crop, edit, watermark, remove backgrounds, blur faces or plates, and more.
- **Documents and web:** convert Office files, render HTML pages, and export PDFs to Markdown or spreadsheets.

Supported formats depend on the selected tool. Processing stays on your server; the bundled PDF summarizer runs locally.

## Quick start

Requirements: Docker Engine and Docker Compose v2.

```sh
git clone https://github.com/paladini/i-love-open-converter.git
cd i-love-open-converter
cp .env.example .env
mkdir -p data
docker compose up -d
```

Open <http://localhost:8080>. The web app and worker run as separate services, and data stays in `./data`. On Windows PowerShell, use `Copy-Item .env.example .env` and `New-Item -ItemType Directory -Force data`.

## Limits and privacy

- Defaults: 100 MB per file, 500 MB per request, 10 files per job, and 24-hour retention. Change settings in `.env`.
- URL capture supports bounded public HTTP(S) resources only; JavaScript and login pages are unsupported. The worker processes files offline.
- PDF signatures are visual. Review redactions and generated summaries before sharing.
- No accounts, third-party analytics, or telemetry are built in. Keep the app on a trusted network or behind an authenticated proxy.

## Development

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --all-groups
uv run playwright install chromium
uv run uvicorn i_love_open_converter.main:app --app-dir src --reload
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidance. Licensed under [AGPL-3.0](LICENSE).

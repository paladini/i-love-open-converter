# I Love Open Converter

A free, self-hosted toolkit for common image and PDF conversions. Upload files in a browser, run a conversion on your own server, and download the result. Files stay on your HomeLab; the application has no ads, accounts, cloud storage, or external telemetry.

The project is under active development. The initial release focuses on common static image operations and essential PDF tools.

## Quick start

Requirements: Docker Engine and Docker Compose v2.

```sh
cp .env.example .env
mkdir -p data
docker compose up -d --build
```

Open <http://localhost:8080>. If the port is already in use, change `APP_PORT` in `.env` and restart Compose.

To stop the application:

```sh
docker compose down
```

Your database and files live in `./data`. Back up that directory if you need to preserve pending jobs or downloaded results across machine changes.

## Current capabilities

- Convert, resize, compress, and rotate static JPEG, PNG, WebP, BMP, or TIFF images; process up to 10 files in one job and download batches as ZIP.
- Merge, split by page ranges, rotate, and optimize unencrypted PDFs; render PDF pages to JPG or turn images into A4 PDFs.
- Use the interface in Brazilian Portuguese or English.
- Process conversions through a local web service, SQLite queue, and worker.

Each upload is limited to 100 MB by default. Batch jobs support up to 10 files. Animated images and advanced document conversion (Office, OCR, PDF/A, and AI) are outside the initial release. Supported inputs are validated from their content before processing.

## Configuration

Copy `.env.example` to `.env`. Compose reads these settings when the containers start:

| Setting | Default | Purpose |
| --- | --- | --- |
| `APP_PORT` | `8080` | Host port for the web interface and API |
| `MAX_FILE_SIZE_MB` | `100` | Maximum size of one uploaded file |
| `MAX_TOTAL_UPLOAD_MB` | `500` | Maximum total uploaded bytes in one request |
| `MAX_FILES_PER_JOB` | `10` | Maximum files accepted in one conversion job |
| `JOB_RETENTION_HOURS` | `24` | Time before a job and its local files are removed |
| `WORKER_POLL_SECONDS` | `1` | How often the worker checks the local queue |
| `PUID`, `PGID` | `1000` | User and group IDs that own data created in the bind mount |

The worker and web process need read/write access to `./data`. On Linux, set `PUID` and `PGID` to the account that owns that directory.

## Privacy

All processing and file storage run on the machine where you deploy the application. The UI uses local static files; it does not load analytics, fonts, or scripts from third-party hosts. Anyone who can reach the web service can use it. Job links use unpredictable IDs, but they are not user accounts or access-control boundaries. Deploy the service only on a network you control.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, tests, formatting, and contribution guidelines.

## License

This project is licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).

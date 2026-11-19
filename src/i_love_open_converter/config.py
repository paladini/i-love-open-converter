from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", "./data"))
    max_file_size_mb: int = _positive_int("MAX_FILE_SIZE_MB", 100)
    max_total_upload_mb: int = _positive_int("MAX_TOTAL_UPLOAD_MB", 500)
    max_files_per_job: int = _positive_int("MAX_FILES_PER_JOB", 10)
    job_retention_hours: int = _positive_int("JOB_RETENTION_HOURS", 24)
    app_port: int = _positive_int("APP_PORT", 8080)
    worker_poll_seconds: float = float(os.getenv("WORKER_POLL_SECONDS", "1"))

    @property
    def database_path(self) -> Path:
        return self.data_dir / "i-love-open-converter.sqlite3"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def max_total_upload_bytes(self) -> int:
        return self.max_total_upload_mb * 1024 * 1024

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()

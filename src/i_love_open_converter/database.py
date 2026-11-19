from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=30, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def initialize(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(database_path)) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversion_jobs (
                id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                state TEXT NOT NULL CHECK (
                    state IN ('queued', 'processing', 'succeeded', 'failed')
                ),
                options_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                error_code TEXT,
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS ix_conversion_jobs_queue
                ON conversion_jobs(state, created_at);
            CREATE INDEX IF NOT EXISTS ix_conversion_jobs_expiration
                ON conversion_jobs(expires_at);

            CREATE TABLE IF NOT EXISTS job_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES conversion_jobs(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK (role IN ('input', 'output')),
                name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0)
            );
            CREATE INDEX IF NOT EXISTS ix_job_artifacts_job ON job_artifacts(job_id, role);
            """
        )


def create_job(
    database_path: Path,
    *,
    job_id: str,
    operation: str,
    options: dict[str, Any],
    retention_hours: int,
    artifacts: list[dict[str, Any]],
) -> None:
    now = utc_now()
    created = _timestamp(now)
    expires = _timestamp(now + timedelta(hours=retention_hours))
    with closing(connect(database_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """INSERT INTO conversion_jobs
                   (id, operation, state, options_json, created_at, updated_at, expires_at)
                   VALUES (?, ?, 'queued', ?, ?, ?, ?)""",
                (job_id, operation, json.dumps(options), created, created, expires),
            )
            connection.executemany(
                """INSERT INTO job_artifacts
                   (job_id, role, name, relative_path, content_type, size_bytes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        job_id,
                        "input",
                        item["name"],
                        item["relative_path"],
                        item["content_type"],
                        item["size_bytes"],
                    )
                    for item in artifacts
                ],
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def get_job(database_path: Path, job_id: str) -> dict[str, Any] | None:
    with closing(connect(database_path)) as connection:
        job = connection.execute("SELECT * FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            return None
        result = dict(job)
        result["options"] = json.loads(result.pop("options_json"))
        result["artifacts"] = [
            dict(item)
            for item in connection.execute(
                "SELECT * FROM job_artifacts WHERE job_id = ? ORDER BY id", (job_id,)
            ).fetchall()
        ]
        return result


def claim_next_job(database_path: Path) -> dict[str, Any] | None:
    with closing(connect(database_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = connection.execute(
            "SELECT id FROM conversion_jobs WHERE state = 'queued' ORDER BY created_at, id LIMIT 1"
        ).fetchone()
        if job is None:
            connection.commit()
            return None
        now = _timestamp(utc_now())
        cursor = connection.execute(
            "UPDATE conversion_jobs SET state = 'processing', updated_at = ? "
            "WHERE id = ? AND state = 'queued'",
            (now, job["id"]),
        )
        connection.commit()
        if cursor.rowcount != 1:
            return None
    return get_job(database_path, job["id"])


def mark_succeeded(
    database_path: Path,
    job_id: str,
    artifacts: list[dict[str, Any]],
    retention_hours: int,
) -> None:
    now = _timestamp(utc_now())
    expires = _timestamp(utc_now() + timedelta(hours=retention_hours))
    with closing(connect(database_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.executemany(
                """INSERT INTO job_artifacts
                   (job_id, role, name, relative_path, content_type, size_bytes)
                   VALUES (?, 'output', ?, ?, ?, ?)""",
                [
                    (
                        job_id,
                        item["name"],
                        item["relative_path"],
                        item["content_type"],
                        item["size_bytes"],
                    )
                    for item in artifacts
                ],
            )
            connection.execute(
                "UPDATE conversion_jobs SET state = 'succeeded', updated_at = ?, expires_at = ? "
                "WHERE id = ?",
                (now, expires, job_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def mark_failed(
    database_path: Path,
    job_id: str,
    code: str,
    message: str,
    retention_hours: int,
) -> None:
    updated_at = utc_now()
    now = _timestamp(updated_at)
    expires = _timestamp(updated_at + timedelta(hours=retention_hours))
    with closing(connect(database_path)) as connection:
        connection.execute(
            """UPDATE conversion_jobs
               SET state = 'failed', error_code = ?, error_message = ?, updated_at = ?,
                   expires_at = ?
               WHERE id = ?""",
            (code, message, now, expires, job_id),
        )


def find_expired_jobs(database_path: Path) -> list[str]:
    """Return expired jobs that are not actively being processed."""
    now = _timestamp(utc_now())
    with closing(connect(database_path)) as connection:
        return [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM conversion_jobs WHERE expires_at <= ? "
                "AND state IN ('queued', 'succeeded', 'failed')",
                (now,),
            ).fetchall()
        ]


def delete_expired_jobs(database_path: Path, job_ids: list[str]) -> int:
    """Delete rows only after the worker has removed their local files."""
    now = _timestamp(utc_now())
    with closing(connect(database_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.executemany(
            "DELETE FROM conversion_jobs WHERE id = ? AND expires_at <= ? "
            "AND state IN ('queued', 'succeeded', 'failed')",
            [(job_id, now) for job_id in job_ids],
        )
        connection.commit()
    return cursor.rowcount

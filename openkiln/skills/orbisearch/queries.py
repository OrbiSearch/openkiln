"""Database queries for the OrbiSearch skill."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from openkiln import config


def _connection() -> sqlite3.Connection:
    """Opens a connection to orbisearch.db."""
    db_path = config.get().skill_db_path("orbisearch")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def upsert_verification_result(
    record_id: int,
    result: dict[str, Any],
    *,
    verified_via: str = "single",
    bulk_job_id: str | None = None,
) -> None:
    """Insert or update a verification result."""
    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO verification_results (
                record_id, email, status, substatus, explanation,
                email_provider, is_disposable, is_role_account, is_free,
                verified_via, bulk_job_id, raw_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                result["email"],
                result["status"],
                result.get("substatus"),
                result["explanation"],
                result["email_provider"],
                _bool_to_int(result.get("is_disposable")),
                _bool_to_int(result.get("is_role_account")),
                _bool_to_int(result.get("is_free")),
                verified_via,
                bulk_job_id,
                json.dumps(result),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_bulk_job(job: dict[str, Any]) -> None:
    """Insert or update a bulk job record."""
    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO bulk_jobs (
                job_id, job_status, total_emails, emails_processed,
                estimated_cost, submitted_at, completed_at, retry_status
            ) VALUES (?, ?, ?, ?, ?,
                      COALESCE(?, datetime('now')),
                      ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                job_status = excluded.job_status,
                emails_processed = excluded.emails_processed,
                completed_at = excluded.completed_at,
                retry_status = excluded.retry_status
            """,
            (
                job["job_id"],
                job.get("status", "pending"),
                _int(job.get("total_emails", 0)),
                _int(job.get("emails_processed", 0)),
                job.get("estimated_cost"),
                job.get("submitted_at"),
                job.get("completed_at"),
                job.get("retry_status", "none"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_bulk_job(job_id: str) -> dict | None:
    """Fetch a bulk job by its job_id."""
    conn = _connection()
    try:
        row = conn.execute("SELECT * FROM bulk_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_bulk_jobs(*, limit: int = 20) -> list[dict]:
    """List recent bulk jobs."""
    conn = _connection()
    try:
        rows = conn.execute(
            "SELECT * FROM bulk_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_verification_result(email: str) -> dict | None:
    """Fetch the latest verification result for an email."""
    conn = _connection()
    try:
        row = conn.execute(
            "SELECT * FROM verification_results WHERE email = ? ORDER BY verified_at DESC LIMIT 1",
            (email,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _bool_to_int(val: Any) -> int | None:
    if val is None:
        return None
    return 1 if val else 0


def _int(val: object) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0

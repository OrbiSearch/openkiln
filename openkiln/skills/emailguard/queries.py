"""
EmailGuard skill database queries.

All functions open their own connection to emailguard.db.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from openkiln import config


def _connection() -> sqlite3.Connection:
    """Opens a connection to emailguard.db."""
    db_path = config.get().skill_db_path("emailguard")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ── Placement Tests ──────────────────────────────────────────


def upsert_test(test: dict[str, Any]) -> None:
    """Insert or update a placement test from API data."""
    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO placement_tests (
                test_uuid, name, status, overall_score, filter_phrase,
                gmail_seed_count, msft_seed_count,
                completed_at, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(test_uuid) DO UPDATE SET
                status = excluded.status,
                overall_score = excluded.overall_score,
                completed_at = excluded.completed_at,
                synced_at = datetime('now')
            """,
            (
                test.get("uuid"),
                test.get("name", ""),
                test.get("status", "created"),
                test.get("overall_score"),
                test.get("filter_phrase", ""),
                test.get("google_workspace_emails_count", 0),
                test.get("microsoft_professional_emails_count", 0),
                test.get("completed_at"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_seed_results(test_uuid: str, seeds: list[dict]) -> None:
    """Insert or update seed results from API data."""
    conn = _connection()
    try:
        for seed in seeds:
            conn.execute(
                """
                INSERT INTO seed_results (
                    test_uuid, seed_email, provider,
                    sender_email, status, folder, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(test_uuid, seed_email) DO UPDATE SET
                    sender_email = excluded.sender_email,
                    status = excluded.status,
                    folder = excluded.folder,
                    synced_at = datetime('now')
                """,
                (
                    test_uuid,
                    seed.get("email", ""),
                    seed.get("provider", ""),
                    seed.get("sender_email_account_address"),
                    seed.get("status", "waiting_for_email"),
                    seed.get("folder"),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def upsert_account_score(
    test_uuid: str,
    account_email: str,
    stats: dict[str, int],
) -> None:
    """Insert or update an account's score from a test."""
    domain = account_email.split("@")[-1] if "@" in account_email else ""
    total = stats.get("inbox", 0) + stats.get("spam", 0)
    inbox_rate = stats["inbox"] / total if total > 0 else None

    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO account_scores (
                test_uuid, account_email, domain,
                total_seeds, inbox_count, spam_count, inbox_rate,
                gmail_inbox, gmail_spam, msft_inbox, msft_spam,
                tested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(test_uuid, account_email) DO UPDATE SET
                total_seeds = excluded.total_seeds,
                inbox_count = excluded.inbox_count,
                spam_count = excluded.spam_count,
                inbox_rate = excluded.inbox_rate,
                gmail_inbox = excluded.gmail_inbox,
                gmail_spam = excluded.gmail_spam,
                msft_inbox = excluded.msft_inbox,
                msft_spam = excluded.msft_spam,
                tested_at = datetime('now')
            """,
            (
                test_uuid,
                account_email,
                domain,
                total,
                stats.get("inbox", 0),
                stats.get("spam", 0),
                inbox_rate,
                stats.get("gmail_inbox", 0),
                stats.get("gmail_spam", 0),
                stats.get("msft_inbox", 0),
                stats.get("msft_spam", 0),
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ── Reads ────────────────────────────────────────────────────


def get_test(test_uuid: str) -> sqlite3.Row | None:
    """Get a placement test by UUID."""
    conn = _connection()
    try:
        return conn.execute(
            "SELECT * FROM placement_tests WHERE test_uuid = ?",
            (test_uuid,),
        ).fetchone()
    finally:
        conn.close()


def list_tests(limit: int = 20) -> list[sqlite3.Row]:
    """List placement tests, most recent first."""
    conn = _connection()
    try:
        return conn.execute(
            "SELECT * FROM placement_tests ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()


def get_seed_results(test_uuid: str) -> list[sqlite3.Row]:
    """Get all seed results for a test."""
    conn = _connection()
    try:
        return conn.execute(
            "SELECT * FROM seed_results WHERE test_uuid = ? ORDER BY provider, seed_email",
            (test_uuid,),
        ).fetchall()
    finally:
        conn.close()


def get_account_scores(test_uuid: str) -> list[sqlite3.Row]:
    """Get account scores for a test."""
    conn = _connection()
    try:
        return conn.execute(
            "SELECT * FROM account_scores WHERE test_uuid = ? ORDER BY account_email",
            (test_uuid,),
        ).fetchall()
    finally:
        conn.close()


def get_account_history(account_email: str, limit: int = 10) -> list[sqlite3.Row]:
    """Get historical scores for an account across tests."""
    conn = _connection()
    try:
        return conn.execute(
            "SELECT * FROM account_scores WHERE account_email = ? ORDER BY tested_at DESC LIMIT ?",
            (account_email, limit),
        ).fetchall()
    finally:
        conn.close()

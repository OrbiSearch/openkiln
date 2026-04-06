"""
Cleanco database queries.

Caches cleaned company names to avoid redundant API calls.
"""

from __future__ import annotations

import sqlite3

from openkiln import config


def _connection() -> sqlite3.Connection:
    """Opens a connection to cleanco.db."""
    db_path = config.get().skill_db_path("cleanco")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_cached(names: list[str]) -> dict[str, str]:
    """Look up cached cleaned names. Returns {original: cleaned}."""
    if not names:
        return {}
    conn = _connection()
    try:
        placeholders = ",".join("?" for _ in names)
        rows = conn.execute(
            f"SELECT original, cleaned FROM cleaned_names WHERE original IN ({placeholders})",
            names,
        ).fetchall()
        return {row["original"]: row["cleaned"] for row in rows}
    finally:
        conn.close()


def cache_results(mappings: dict[str, str]) -> None:
    """Store cleaned name mappings in the cache."""
    if not mappings:
        return
    conn = _connection()
    try:
        conn.executemany(
            """
            INSERT INTO cleaned_names (original, cleaned)
            VALUES (?, ?)
            ON CONFLICT(original) DO UPDATE SET
                cleaned = excluded.cleaned,
                cleaned_at = datetime('now')
            """,
            list(mappings.items()),
        )
        conn.commit()
    finally:
        conn.close()

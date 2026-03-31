from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from openkiln import config


# ── Constants ─────────────────────────────────────────────────

BATCH_SIZE = 1000  # rows per batch for all read/write operations


# ── Schema paths ──────────────────────────────────────────────

PACKAGE_DIR  = Path(__file__).parent
CORE_SCHEMA  = PACKAGE_DIR / "schema" / "core" / "001_initial.sql"
SKILLS_DIR   = PACKAGE_DIR / "skills"


# ── Core connection ───────────────────────────────────────────

def core_db_path() -> Path:
    """Returns the path to core.db from config."""
    return config.get().core_db


def get_connection(attach_skills: list[str] | None = None) -> sqlite3.Connection:
    """
    Opens and returns a connection to core.db.
    Optionally attaches skill databases by name.

    Caller is responsible for closing the connection.
    For managed connections use the connection() context manager.

    attach_skills: list of installed skill names to attach.
    Each skill is attached as its skill_name alias.
    e.g. attach_skills=["orbisearch"] attaches orbisearch.db as "orbisearch"
    """
    conn = sqlite3.connect(core_db_path())
    conn.row_factory = sqlite3.Row  # rows accessible by column name
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON")

    if attach_skills:
        cfg = config.get()
        for skill_name in attach_skills:
            db_path = cfg.skill_db_path(skill_name)
            if not db_path.exists():
                raise RuntimeError(
                    f"Skill database not found: {db_path}\n"
                    f"Is '{skill_name}' installed? "
                    f"Run: openkiln skill install {skill_name}"
                )
            conn.execute(
                f"ATTACH DATABASE ? AS {skill_name}",
                (str(db_path),)
            )

    return conn


@contextmanager
def connection(
    attach_skills: list[str] | None = None
) -> Iterator[sqlite3.Connection]:
    """
    Context manager for a core.db connection.
    Closes connection on exit. Does not manage transactions.
    Use transaction() for transactional operations.

    Usage:
        with db.connection() as conn:
            rows = conn.execute("SELECT * FROM records").fetchall()

        with db.connection(attach_skills=["orbisearch"]) as conn:
            rows = conn.execute(
                "SELECT * FROM orbisearch.verification_results"
            ).fetchall()
    """
    conn = get_connection(attach_skills=attach_skills)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(
    attach_skills: list[str] | None = None
) -> Iterator[sqlite3.Connection]:
    """
    Context manager for a transactional connection to core.db.
    Commits on clean exit. Rolls back on any exception.
    All-or-nothing — no partial writes.

    Use this for all workflow run operations.

    Usage:
        with db.transaction() as conn:
            conn.execute("UPDATE records SET record_status = 'archived' ...")
            conn.executemany("INSERT INTO workflow_runs ...", rows)
        # commits here

        with db.transaction(attach_skills=["orbisearch"]) as conn:
            conn.executemany(
                "INSERT INTO orbisearch.verification_results ...", rows
            )
        # commits here — rolls back entire workflow on any error
    """
    conn = get_connection(attach_skills=attach_skills)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema initialisation ─────────────────────────────────────

def init_core() -> None:
    """
    Creates core.db and applies the core schema.
    Creates ~/.openkiln/ and ~/.openkiln/skills/ if they do not exist.
    Safe to call multiple times — CREATE TABLE IF NOT EXISTS guards apply.
    Called by openkiln init.
    """
    db_path = core_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    config.get().skills_dir.mkdir(parents=True, exist_ok=True)

    sql = CORE_SCHEMA.read_text()
    with connection() as conn:
        conn.executescript(sql)


def init_skill(skill_name: str) -> None:
    """
    Creates a skill database and applies its schema.
    Schema SQL file must exist at:
      openkiln/skills/<skill_name>/schema/001_initial.sql
    Safe to call multiple times — CREATE TABLE IF NOT EXISTS guards apply.
    Called by openkiln skill install.
    """
    schema_path = SKILLS_DIR / skill_name / "schema" / "001_initial.sql"
    if not schema_path.exists():
        raise RuntimeError(
            f"Schema not found for skill '{skill_name}': {schema_path}"
        )

    db_path = config.get().skill_db_path(skill_name)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    sql = schema_path.read_text()
    skill_conn = sqlite3.connect(db_path)
    try:
        skill_conn.executescript(sql)
        skill_conn.commit()
    finally:
        skill_conn.close()


# ── Health check ──────────────────────────────────────────────

def check_connection() -> bool:
    """
    Returns True if core.db exists and is reachable.
    Returns False otherwise — never raises.
    Used by openkiln status and CLI startup check.
    """
    if not core_db_path().exists():
        return False
    try:
        with connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


# ── Batch helpers ─────────────────────────────────────────────

def batch_read(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple = (),
) -> Iterator[list[sqlite3.Row]]:
    """
    Executes a SELECT query and yields results in batches of BATCH_SIZE.
    Never loads all rows into memory at once.
    Used by Source implementations.

    Usage:
        with db.connection(attach_skills=["crm"]) as conn:
            for batch in db.batch_read(conn, "SELECT * FROM crm.contacts"):
                process(batch)
    """
    cursor = conn.execute(sql, params)
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        yield rows


def batch_write(
    conn: sqlite3.Connection,
    sql: str,
    rows: list[tuple],
) -> int:
    """
    Executes a parameterised INSERT or UPDATE for a list of rows.
    Uses executemany for efficiency — one round trip per batch.
    Returns number of rows affected.
    Used by Sink implementations.

    Usage:
        with db.transaction(attach_skills=["orbisearch"]) as conn:
            db.batch_write(
                conn,
                "INSERT INTO orbisearch.verification_results
                 (record_id, email, status) VALUES (?, ?, ?)",
                [(1, "a@b.com", "safe"), (2, "c@d.com", "invalid")]
            )
    """
    cursor = conn.executemany(sql, rows)
    return cursor.rowcount

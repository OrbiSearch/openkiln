from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from openkiln import config

# ── Constants ─────────────────────────────────────────────────

BATCH_SIZE = 1000  # rows per batch for all read/write operations


# ── Schema paths ──────────────────────────────────────────────

PACKAGE_DIR = Path(__file__).parent
CORE_SCHEMA = PACKAGE_DIR / "schema" / "core" / "001_initial.sql"
SKILLS_DIR = PACKAGE_DIR / "skills"


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
            conn.execute(f"ATTACH DATABASE ? AS {skill_name}", (str(db_path),))

    return conn


@contextmanager
def connection(attach_skills: list[str] | None = None) -> Iterator[sqlite3.Connection]:
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
def transaction(attach_skills: list[str] | None = None) -> Iterator[sqlite3.Connection]:
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


def init_skill(skill_name: str) -> list[str]:
    """
    Creates a skill database and applies any unapplied schema migrations.
    Tracks applied migrations in a schema_migrations table per skill db.
    Safe to call multiple times — only unapplied migrations are run.

    Handles legacy installations (pre-migration-tracking) by checking
    if a migration's effects are already present before running it.
    Returns list of newly applied migration filenames.

    Called by openkiln skill install and openkiln skill update.
    """
    schema_dir = SKILLS_DIR / skill_name / "schema"
    if not schema_dir.exists():
        raise RuntimeError(f"Schema directory not found for skill '{skill_name}': {schema_dir}")

    migration_files = sorted(schema_dir.glob("*.sql"))
    if not migration_files:
        raise RuntimeError(f"No schema migrations found for skill '{skill_name}': {schema_dir}")

    db_path = config.get().skill_db_path(skill_name)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    skill_conn = sqlite3.connect(db_path)
    try:
        # ensure migrations tracking table exists
        skill_conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename   TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        skill_conn.commit()

        # find which migrations have already been applied
        applied = {
            row[0] for row in skill_conn.execute("SELECT filename FROM schema_migrations").fetchall()
        }

        # legacy install detection: schema_migrations exists but is empty
        # and the db already has tables — migrations ran before tracking.
        # mark all migrations as applied without re-running them.
        if not applied:
            existing_tables = {
                row[0]
                for row in skill_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name != 'schema_migrations'"
                ).fetchall()
            }
            if existing_tables:
                # db already has schema — mark all migrations as applied
                for migration_file in migration_files:
                    skill_conn.execute(
                        "INSERT OR IGNORE INTO schema_migrations (filename) VALUES (?)",
                        (migration_file.name,),
                    )
                skill_conn.commit()
                return []  # nothing newly applied

        # apply only unapplied migrations in order
        newly_applied = []
        for migration_file in migration_files:
            filename = migration_file.name
            if filename in applied:
                continue

            sql = migration_file.read_text()
            try:
                skill_conn.executescript(sql)
            except sqlite3.OperationalError as e:
                err = str(e).lower()
                if "duplicate column name" in err:
                    # column already exists — migration effectively applied
                    # mark as applied and continue
                    skill_conn.execute(
                        "INSERT OR IGNORE INTO schema_migrations (filename) VALUES (?)", (filename,)
                    )
                    skill_conn.commit()
                    continue
                raise RuntimeError(f"Migration failed: {filename}\n{e}") from e

            skill_conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (filename) VALUES (?)", (filename,)
            )
            skill_conn.commit()
            newly_applied.append(filename)

        return newly_applied

    finally:
        skill_conn.close()


def migrate_installed_skills() -> None:
    """
    Runs pending schema migrations for all installed skills.
    Called automatically on CLI startup.
    Silent on success. Warns if a migration fails.
    """
    if not check_connection():
        return  # db not initialised yet — skip

    try:
        with connection() as conn:
            skills = conn.execute("SELECT skill_name FROM installed_skills").fetchall()

        for row in skills:
            skill_name = row["skill_name"]
            try:
                init_skill(skill_name)
                # silent on success — only log if migrations were applied
            except Exception:
                pass  # never crash startup due to migration failure
    except Exception:
        pass  # never crash startup


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

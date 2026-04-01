"""
Tests for the OrbiSearch skill.

Covers: skill install, schema, constants, API client, CLI registration, queries.
"""
from __future__ import annotations

import json
import os
import sqlite3

from typer.testing import CliRunner

from openkiln.cli import app
from openkiln import db

runner = CliRunner()


# ── Skill Install ────────────────────────────────────────────


def test_skill_install_orbisearch(openkiln_home):
    """skill install orbisearch creates db and registers skill."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "install", "orbisearch"])
    assert result.exit_code == 0
    assert (openkiln_home / "skills" / "orbisearch.db").exists()

    with db.connection() as conn:
        row = conn.execute(
            "SELECT skill_name FROM installed_skills "
            "WHERE skill_name = 'orbisearch'"
        ).fetchone()
    assert row is not None


def test_skill_install_creates_config_section(openkiln_home):
    """skill install orbisearch appends config section."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "orbisearch"])
    config_text = (openkiln_home / "config.toml").read_text()
    assert "[skills.orbisearch]" in config_text
    assert "api_key" in config_text


def test_skill_info_orbisearch(openkiln_home):
    """skill info orbisearch prints SKILL.md content."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "info", "orbisearch"])
    assert result.exit_code == 0
    assert "OrbiSearch Skill" in result.output
    assert "orbisearch.validate" in result.output


# ── Schema ───────────────────────────────────────────────────


def test_schema_creates_all_tables(openkiln_home):
    """orbisearch.db has all expected tables after install."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "orbisearch"])

    db_path = openkiln_home / "skills" / "orbisearch.db"
    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()

    assert "verification_results" in tables
    assert "bulk_jobs" in tables


def test_bulk_jobs_unique_constraint(openkiln_home):
    """bulk_jobs enforces UNIQUE(job_id)."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "orbisearch"])

    db_path = openkiln_home / "skills" / "orbisearch.db"
    conn = sqlite3.connect(db_path)

    conn.execute(
        "INSERT INTO bulk_jobs (job_id, total_emails) VALUES ('job-1', 10)"
    )
    conn.commit()

    try:
        conn.execute(
            "INSERT INTO bulk_jobs (job_id, total_emails) VALUES ('job-1', 20)"
        )
        conn.commit()
        assert False, "Expected UNIQUE constraint violation"
    except sqlite3.IntegrityError:
        pass

    conn.close()


# ── __init__.py ──────────────────────────────────────────────


def test_init_exports():
    """__init__.py exports __version__."""
    from openkiln.skills.orbisearch import __version__
    assert __version__ == "0.1.0"


# ── API Client ───────────────────────────────────────────────


def test_api_client_construction():
    """OrbiSearchClient can be instantiated with an API key."""
    from openkiln.skills.orbisearch.api import OrbiSearchClient

    client = OrbiSearchClient("test-key-123")
    assert client._api_key == "test-key-123"


def test_api_client_no_key_error():
    """get_client raises OrbiSearchError when no key is configured."""
    from openkiln.skills.orbisearch.api import get_client, OrbiSearchError

    old = os.environ.pop("ORBISEARCH_API_KEY", None)
    try:
        try:
            get_client()
            assert False, "Expected OrbiSearchError"
        except OrbiSearchError as e:
            assert "API key" in str(e)
    finally:
        if old:
            os.environ["ORBISEARCH_API_KEY"] = old


def test_api_client_auth_header():
    """Client uses X-API-Key header."""
    from openkiln.skills.orbisearch.api import OrbiSearchClient

    client = OrbiSearchClient("my-key")
    headers = client._headers()
    assert headers["X-API-Key"] == "my-key"


# ── CLI ──────────────────────────────────────────────────────


def test_cli_app_mountable():
    """CLI app is a Typer instance and can be mounted."""
    import importlib
    mod = importlib.import_module("openkiln.skills.orbisearch.cli")
    skill_app = getattr(mod, "app", None)
    assert skill_app is not None
    assert skill_app.info.name == "orbisearch"


def test_cli_commands_registered():
    """All expected commands are registered."""
    from openkiln.skills.orbisearch.cli import app as orbisearch_app

    cmds = [c.name or c.callback.__name__ for c in orbisearch_app.registered_commands]
    assert "verify" in cmds
    assert "credits" in cmds
    assert "bulk-submit" in cmds or "bulk_submit" in cmds
    assert "bulk-status" in cmds or "bulk_status" in cmds
    assert "bulk-results" in cmds or "bulk_results" in cmds


# ── Queries ──────────────────────────────────────────────────


def test_queries_upsert_bulk_job(openkiln_home):
    """upsert_bulk_job inserts and updates correctly."""
    from openkiln.skills.orbisearch import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "orbisearch"])

    # insert
    queries.upsert_bulk_job({
        "job_id": "test-job-1",
        "status": "pending",
        "total_emails": 100,
        "emails_processed": 0,
    })

    job = queries.get_bulk_job("test-job-1")
    assert job is not None
    assert job["job_status"] == "pending"
    assert job["total_emails"] == 100

    # update
    queries.upsert_bulk_job({
        "job_id": "test-job-1",
        "status": "complete",
        "total_emails": 100,
        "emails_processed": 100,
        "completed_at": "2026-01-01T00:00:00Z",
    })

    job = queries.get_bulk_job("test-job-1")
    assert job["job_status"] == "complete"
    assert job["emails_processed"] == 100


def test_queries_verification_result(openkiln_home):
    """upsert_verification_result stores and retrieves correctly."""
    from openkiln.skills.orbisearch import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "orbisearch"])

    result = {
        "email": "test@example.com",
        "status": "safe",
        "substatus": None,
        "explanation": "Email is deliverable",
        "email_provider": "Google Workspace",
        "is_disposable": False,
        "is_role_account": False,
        "is_free": False,
    }

    queries.upsert_verification_result(record_id=1, result=result)

    stored = queries.get_verification_result("test@example.com")
    assert stored is not None
    assert stored["status"] == "safe"
    assert stored["email_provider"] == "Google Workspace"
    assert stored["is_disposable"] == 0  # stored as int


def test_queries_list_bulk_jobs(openkiln_home):
    """list_bulk_jobs returns jobs in order."""
    from openkiln.skills.orbisearch import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "orbisearch"])

    queries.upsert_bulk_job({
        "job_id": "job-a",
        "status": "complete",
        "total_emails": 50,
    })
    queries.upsert_bulk_job({
        "job_id": "job-b",
        "status": "pending",
        "total_emails": 100,
    })

    jobs = queries.list_bulk_jobs()
    assert len(jobs) == 2

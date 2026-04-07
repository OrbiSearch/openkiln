"""
Tests for the EmailGuard skill.

Covers: skill install, schema, API client, queries, CLI registration.
"""

from __future__ import annotations

import os
import sqlite3

from typer.testing import CliRunner

from openkiln import db
from openkiln.cli import app

runner = CliRunner()


# ── Skill Install ────────────────────────────────────────────


def test_skill_install_emailguard(openkiln_home):
    """skill install emailguard creates db and registers skill."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "install", "emailguard"])
    assert result.exit_code == 0
    assert (openkiln_home / "skills" / "emailguard.db").exists()

    with db.connection() as conn:
        row = conn.execute(
            "SELECT skill_name FROM installed_skills WHERE skill_name = 'emailguard'"
        ).fetchone()
    assert row is not None


def test_skill_install_creates_config_section(openkiln_home):
    """skill install emailguard appends config section."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "emailguard"])
    config_text = (openkiln_home / "config.toml").read_text()
    assert "[skills.emailguard]" in config_text
    assert "api_key" in config_text


def test_skill_info_emailguard(openkiln_home):
    """skill info emailguard prints SKILL.md content."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "info", "emailguard"])
    assert result.exit_code == 0
    assert "EmailGuard" in result.output
    assert "placement" in result.output.lower()


# ── Schema ───────────────────────────────────────────────────


def test_schema_creates_all_tables(openkiln_home):
    """emailguard.db has all expected tables after install."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "emailguard"])

    db_path = openkiln_home / "skills" / "emailguard.db"
    conn = sqlite3.connect(db_path)
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn.close()

    assert "placement_tests" in tables
    assert "seed_results" in tables
    assert "account_scores" in tables


# ── API Client ───────────────────────────────────────────────


def test_api_client_construction():
    """EmailGuardClient can be instantiated with an API key."""
    from openkiln.skills.emailguard.api import EmailGuardClient

    client = EmailGuardClient("test-token-123")
    assert client._api_key == "test-token-123"


def test_api_client_auth_header():
    """Client uses Bearer token auth."""
    from openkiln.skills.emailguard.api import EmailGuardClient

    client = EmailGuardClient("my-token")
    headers = client._headers()
    assert headers["Authorization"] == "Bearer my-token"


def test_api_client_no_key_error():
    """get_client raises EmailGuardError when no key is configured."""
    from openkiln.skills.emailguard.api import EmailGuardError, get_client

    old = os.environ.pop("EMAILGUARD_API_KEY", None)
    try:
        try:
            get_client()
            assert False, "Expected EmailGuardError"
        except EmailGuardError as e:
            assert "API key" in str(e)
    finally:
        if old:
            os.environ["EMAILGUARD_API_KEY"] = old


# ── Queries ──────────────────────────────────────────────────


def test_queries_upsert_test(openkiln_home):
    """upsert_test inserts and updates correctly."""
    from openkiln.skills.emailguard import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "emailguard"])

    queries.upsert_test(
        {
            "uuid": "test-abc",
            "name": "My Test",
            "filter_phrase": "fp_xyz",
            "google_workspace_emails_count": 4,
            "microsoft_professional_emails_count": 4,
        }
    )

    test = queries.get_test("test-abc")
    assert test is not None
    assert test["name"] == "My Test"
    assert test["filter_phrase"] == "fp_xyz"

    # update
    queries.upsert_test(
        {
            "uuid": "test-abc",
            "name": "My Test",
            "status": "completed",
            "overall_score": 85.0,
            "filter_phrase": "fp_xyz",
        }
    )

    test = queries.get_test("test-abc")
    assert test["status"] == "completed"
    assert test["overall_score"] == 85.0


def test_queries_seed_results(openkiln_home):
    """upsert_seed_results stores and retrieves correctly."""
    from openkiln.skills.emailguard import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "emailguard"])

    queries.upsert_seed_results(
        "test-abc",
        [
            {"email": "s1@gmail.com", "provider": "Google", "status": "completed", "folder": "Inbox"},
            {
                "email": "s2@outlook.com",
                "provider": "Microsoft",
                "status": "completed",
                "folder": "Spam",
            },
        ],
    )

    seeds = queries.get_seed_results("test-abc")
    assert len(seeds) == 2
    assert seeds[0]["folder"] == "Inbox"
    assert seeds[1]["folder"] == "Spam"


def test_queries_account_scores(openkiln_home):
    """upsert_account_score stores and retrieves correctly."""
    from openkiln.skills.emailguard import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "emailguard"])

    queries.upsert_account_score(
        "test-abc",
        "me@example.com",
        {"inbox": 6, "spam": 2, "gmail_inbox": 3, "gmail_spam": 1, "msft_inbox": 3, "msft_spam": 1},
    )

    scores = queries.get_account_scores("test-abc")
    assert len(scores) == 1
    assert scores[0]["inbox_rate"] == 0.75
    assert scores[0]["domain"] == "example.com"


def test_queries_list_tests(openkiln_home):
    """list_tests returns tests in order."""
    from openkiln.skills.emailguard import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "emailguard"])

    queries.upsert_test({"uuid": "t1", "name": "Test 1", "filter_phrase": "fp1"})
    queries.upsert_test({"uuid": "t2", "name": "Test 2", "filter_phrase": "fp2"})

    tests = queries.list_tests()
    assert len(tests) == 2


# ── CLI ──────────────────────────────────────────────────────


def test_cli_app_mountable():
    """CLI app is a Typer instance and can be mounted."""
    import importlib

    mod = importlib.import_module("openkiln.skills.emailguard.cli")
    skill_app = getattr(mod, "app", None)
    assert skill_app is not None
    assert skill_app.info.name == "emailguard"


def test_cli_commands_registered():
    """All expected commands are registered."""
    from openkiln.skills.emailguard.cli import app as eg_app

    cmds = [c.name or c.callback.__name__ for c in eg_app.registered_commands]
    assert "create" in cmds
    assert "check" in cmds
    assert "report" in cmds
    assert "list" in cmds


# ── __init__.py ──────────────────────────────────────────────


def test_init_exports():
    """__init__.py exports __version__."""
    from openkiln.skills.emailguard import __version__

    assert __version__ == "0.1.0"

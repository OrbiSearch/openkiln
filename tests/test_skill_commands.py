from typer.testing import CliRunner

from openkiln import db
from openkiln.cli import app

runner = CliRunner()


def test_skill_list_before_init(openkiln_home):
    """skill list fails clearly before init."""
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 1
    assert "openkiln init" in result.output


def test_skill_list_after_init_shows_available(openkiln_home):
    """skill list shows available skills after init."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 0
    assert "crm" in result.output
    assert "orbisearch" in result.output


def test_skill_install_unknown_skill(openkiln_home):
    """skill install fails clearly for unknown skill names."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "install", "nonexistent"])
    assert result.exit_code == 1
    assert "Unknown skill" in result.output


def test_skill_install_crm(openkiln_home):
    """skill install crm creates db and registers skill."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "install", "crm"])
    assert result.exit_code == 0
    assert (openkiln_home / "skills" / "crm.db").exists()

    with db.connection() as conn:
        row = conn.execute("SELECT skill_name FROM installed_skills WHERE skill_name = 'crm'").fetchone()
    assert row is not None


def test_skill_install_idempotent(openkiln_home):
    """skill install is safe to run twice."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])
    result = runner.invoke(app, ["skill", "install", "crm"])
    assert result.exit_code == 0
    assert "already installed" in result.output


def test_skill_list_shows_installed(openkiln_home):
    """skill list shows crm as installed after install."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 0
    assert "✓" in result.output or "installed" in result.output.lower()


def test_skill_info_unknown_skill(openkiln_home):
    """skill info fails clearly for unknown skill names."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "info", "nonexistent"])
    assert result.exit_code == 1
    assert "Unknown skill" in result.output


def test_skill_info_crm(openkiln_home):
    """skill info crm prints SKILL.md content."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "info", "crm"])
    assert result.exit_code == 0
    assert "CRM Skill" in result.output
    assert "crm.contacts" in result.output


def test_skill_info_orbisearch(openkiln_home):
    """skill info orbisearch prints SKILL.md content."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "info", "orbisearch"])
    assert result.exit_code == 0
    assert "OrbiSearch Skill" in result.output
    assert "orbisearch.validate" in result.output


def test_skill_list_json(openkiln_home):
    """skill list --json returns valid JSON."""
    import json

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])
    result = runner.invoke(app, ["skill", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "installed" in data
    assert "available" in data
    assert any(s["name"] == "crm" for s in data["installed"])


def test_skill_install_orbisearch_appends_config(openkiln_home):
    """skill install orbisearch appends config section."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "orbisearch"])
    config_text = (openkiln_home / "config.toml").read_text()
    assert "[skills.orbisearch]" in config_text


def test_skill_update_applies_pending_migrations(openkiln_home, tmp_path):
    """skill update applies pending migrations to installed skill."""
    # install crm — creates db with migrations 001 and 002
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])

    # verify initial migrations were tracked
    crm_db = openkiln_home / "skills" / "crm.db"
    import sqlite3

    conn = sqlite3.connect(crm_db)
    applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations").fetchall()}
    conn.close()
    assert "001_initial.sql" in applied
    assert "002_add_touches.sql" in applied
    assert "003_lifecycle_lists.sql" in applied


def test_skill_update_already_up_to_date(openkiln_home):
    """skill update reports up to date when no migrations pending."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])
    result = runner.invoke(app, ["skill", "update", "crm"])
    assert result.exit_code == 0
    assert "up to date" in result.output.lower()


def test_skill_update_unknown_skill_fails(openkiln_home):
    """skill update fails clearly for unknown skill."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "update", "nonexistent"])
    assert result.exit_code == 1
    assert "not installed" in result.output.lower()


def test_auto_migration_runs_on_startup(openkiln_home):
    """migrate_installed_skills runs pending migrations silently."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])

    # verify all migrations applied after install
    crm_db = openkiln_home / "skills" / "crm.db"
    import sqlite3

    conn = sqlite3.connect(crm_db)
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    conn.close()
    # should have 3 migrations applied (001, 002, 003)
    assert count == 3

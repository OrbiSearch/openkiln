from typer.testing import CliRunner
from openkiln.cli import app
from openkiln import db

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
        row = conn.execute(
            "SELECT skill_name FROM installed_skills "
            "WHERE skill_name = 'crm'"
        ).fetchone()
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

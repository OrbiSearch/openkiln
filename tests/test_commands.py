from typer.testing import CliRunner
from openkiln.cli import app

runner = CliRunner()


def test_help_shows_commands():
    """openkiln --help lists all expected command groups."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.output
    assert "status" in result.output
    assert "workflow" in result.output
    assert "skill" in result.output
    assert "record" in result.output


def test_init_creates_expected_files(openkiln_home):
    """openkiln init creates config.toml and core.db."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (openkiln_home / "config.toml").exists()
    assert (openkiln_home / "core.db").exists()
    assert (openkiln_home / "skills").exists()


def test_init_is_idempotent(openkiln_home):
    """openkiln init can be run twice without error."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "already exists" in result.output


def test_status_fails_before_init(openkiln_home):
    """openkiln status exits with code 1 when db does not exist."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 1


def test_status_succeeds_after_init(openkiln_home):
    """openkiln status exits with code 0 after init."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_status_json_is_valid(openkiln_home):
    """openkiln status --json returns valid JSON."""
    import json
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["connected"] is True
    assert "records" in data
    assert "skills" in data


def test_status_json_before_init_returns_error(openkiln_home):
    """openkiln status --json returns connected: false before init."""
    import json
    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["connected"] is False


def test_update_command_is_registered(openkiln_home):
    """update command is registered and shows help."""
    result = runner.invoke(app, ["update", "--help"])
    assert result.exit_code == 0
    assert "Update" in result.output or "update" in result.output.lower()

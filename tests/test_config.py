from pathlib import Path

from openkiln import config


def test_default_paths_point_to_home():
    """Core paths resolve under the home directory."""
    assert config.OPENKILN_DIR == Path.home() / ".openkiln"
    assert config.CONFIG_PATH == Path.home() / ".openkiln" / "config.toml"


def test_write_default_creates_config_file(openkiln_home):
    """write_default creates config.toml in the openkiln dir."""
    config.write_default(
        core_db=openkiln_home / "core.db",
        skills_dir=openkiln_home / "skills",
    )
    config_file = openkiln_home / "config.toml"
    assert config_file.exists()


def test_write_default_does_not_overwrite(openkiln_home):
    """write_default does not overwrite an existing config file."""
    config_file = openkiln_home / "config.toml"
    config_file.write_text("original content")

    config.write_default(
        core_db=openkiln_home / "core.db",
        skills_dir=openkiln_home / "skills",
    )
    assert config_file.read_text() == "original content"


def test_config_reads_defaults_when_no_file(openkiln_home):
    """Config returns defaults when config.toml does not exist."""
    cfg = config.get()
    assert cfg.core_db == openkiln_home / "core.db"
    assert cfg.skills_dir == openkiln_home / "skills"


def test_config_reads_from_file(openkiln_home):
    """Config reads values from config.toml when it exists."""
    config_file = openkiln_home / "config.toml"
    config_file.write_text(
        f'[database]\ncore_db = "{openkiln_home}/mycore.db"\nskills_dir = "{openkiln_home}/myskills"\n'
    )
    cfg = config.get()
    assert cfg.core_db == openkiln_home / "mycore.db"
    assert cfg.skills_dir == openkiln_home / "myskills"


def test_env_var_overrides_config_file(openkiln_home, monkeypatch):
    """Environment variables take precedence over config file."""
    custom_db = openkiln_home / "custom.db"
    monkeypatch.setenv("OPENKILN_CORE_DB", str(custom_db))
    cfg = config.get()
    assert cfg.core_db == custom_db


def test_skill_db_path(openkiln_home):
    """skill_db_path returns expected path for a skill name."""
    cfg = config.get()
    assert cfg.skill_db_path("orbisearch") == (openkiln_home / "skills" / "orbisearch.db")


def test_skill_config_returns_empty_dict_when_missing(openkiln_home):
    """skill_config returns empty dict for unregistered skills."""
    cfg = config.get()
    assert cfg.skill_config("nonexistent") == {}


def test_skill_config_reads_skill_section(openkiln_home):
    """skill_config returns the correct section for an installed skill."""
    config_file = openkiln_home / "config.toml"
    config_file.write_text(
        "[database]\n"
        f'core_db = "{openkiln_home}/core.db"\n'
        f'skills_dir = "{openkiln_home}/skills"\n'
        "\n"
        "[skills.orbisearch]\n"
        'api_key = "test-key-123"\n'
    )
    cfg = config.get()
    assert cfg.skill_config("orbisearch") == {"api_key": "test-key-123"}

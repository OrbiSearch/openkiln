from __future__ import annotations

import pytest
from openkiln import config


@pytest.fixture
def openkiln_home(tmp_path, monkeypatch):
    """
    Redirects all OpenKiln paths to a pytest-managed temp directory.
    Prevents tests from touching the real ~/.openkiln/ directory.
    Safe to use in any test that touches the filesystem.

    Yields the temp directory path so tests can make assertions
    against specific files within it.

    Usage:
        def test_something(openkiln_home):
            # openkiln_home is a Path to a clean temp directory
            # all config/db operations go there, not ~/.openkiln/
            ...
    """
    # redirect all core paths
    monkeypatch.setattr("openkiln.config.OPENKILN_DIR", tmp_path)
    monkeypatch.setattr(
        "openkiln.config.CONFIG_PATH",
        tmp_path / "config.toml"
    )
    monkeypatch.setattr(
        "openkiln.config.DEFAULT_CORE_DB",
        tmp_path / "core.db"
    )
    monkeypatch.setattr(
        "openkiln.config.DEFAULT_SKILLS_DIR",
        tmp_path / "skills"
    )

    # reset singleton so it re-reads config fresh for each test
    config.reset()

    # reset mounted skills so skill CLIs are re-discovered per test
    import openkiln.cli as cli_mod
    cli_mod._mounted_skills.clear()

    yield tmp_path

    # cleanup — reset singleton and mounted skills after test
    config.reset()
    cli_mod._mounted_skills.clear()

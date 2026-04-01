from __future__ import annotations

import os
import tomllib  # built-in Python 3.11+
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────

OPENKILN_DIR = Path.home() / ".openkiln"
CONFIG_PATH = OPENKILN_DIR / "config.toml"

DEFAULT_CORE_DB = OPENKILN_DIR / "core.db"
DEFAULT_SKILLS_DIR = OPENKILN_DIR / "skills"


# ── Default config template ──────────────────────────────────
# Written to ~/.openkiln/config.toml by openkiln init.
# Skill sections are appended here when skills are installed.

DEFAULT_CONFIG_TOML = """\
[database]
core_db    = "{core_db}"
skills_dir = "{skills_dir}"

# Skill configuration sections are added here when skills
# are installed via: openkiln skill install <name>
#
# Example:
# [skills.orbisearch]
# api_key = ""
"""


# ── Config class ─────────────────────────────────────────────


class Config:
    """
    Single source of truth for all runtime configuration.

    Reads from ~/.openkiln/config.toml then applies env var overrides.
    Core config contains only database paths — nothing skill-specific.
    Skills read their own sections via skill_config().

    Do not instantiate directly. Use the module-level get() function.
    """

    def __init__(self) -> None:
        raw = _load_file()
        db = raw.get("database", {})

        # database paths — only thing core config owns
        self.core_db: Path = Path(
            os.environ.get("OPENKILN_CORE_DB") or db.get("core_db", str(DEFAULT_CORE_DB))
        ).expanduser()

        self.skills_dir: Path = Path(
            os.environ.get("OPENKILN_SKILLS_DIR") or db.get("skills_dir", str(DEFAULT_SKILLS_DIR))
        ).expanduser()

        # full raw config available for skill_config() lookups
        # core never reads from this directly
        self._raw = raw

    def skill_db_path(self, skill_name: str) -> Path:
        """
        Returns the database path for a given skill.
        ~/.openkiln/skills/<skill_name>.db
        """
        return self.skills_dir / f"{skill_name}.db"

    def skill_config(self, skill_name: str) -> dict:
        """
        Returns the config section for a named skill.
        Skills call this themselves — core never calls this.
        Returns empty dict if no section exists for this skill.

        Usage (inside a skill module):
            cfg = config.get().skill_config("orbisearch")
            api_key = os.environ.get("ORBISEARCH_API_KEY") or cfg.get("api_key", "")
        """
        return self._raw.get("skills", {}).get(skill_name, {})


# ── File loader ──────────────────────────────────────────────


def _load_file() -> dict:
    """
    Reads ~/.openkiln/config.toml if it exists.
    Returns empty dict if missing — defaults handle the rest.
    Raises RuntimeError with clear instructions if file is malformed.
    """
    if not CONFIG_PATH.exists():
        return {}

    try:
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise RuntimeError(
            f"Config file is malformed: {CONFIG_PATH}\n"
            f"{e}\n"
            f"Fix the file or delete it and run: openkiln init"
        ) from e


# ── Singleton ────────────────────────────────────────────────

_config: Config | None = None


def get() -> Config:
    """
    Returns the global Config instance.
    Reads config file once on first call, cached for process lifetime.

    Usage:
        from openkiln import config
        cfg = config.get()
        print(cfg.core_db)
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset() -> None:
    """
    Resets the cached config instance.
    Used in tests only — forces a fresh read on next get() call.
    Do not call in production code.
    """
    global _config
    _config = None


def write_default(
    core_db: Path = DEFAULT_CORE_DB,
    skills_dir: Path = DEFAULT_SKILLS_DIR,
) -> None:
    """
    Writes the default config file to ~/.openkiln/config.toml.
    Called by openkiln init. Does not overwrite an existing file.
    Creates ~/.openkiln/ directory if it does not exist.
    """
    if CONFIG_PATH.exists():
        return

    OPENKILN_DIR.mkdir(parents=True, exist_ok=True)

    CONFIG_PATH.write_text(
        DEFAULT_CONFIG_TOML.format(
            core_db=core_db,
            skills_dir=skills_dir,
        )
    )

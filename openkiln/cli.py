from __future__ import annotations

import importlib

import typer

from openkiln.commands import init, status, workflow, skill, record
from openkiln import db

app = typer.Typer(
    name="openkiln",
    help="Open source agentic data workflow CLI. Built by OrbiSearch.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

# core command groups
app.add_typer(workflow.app, name="workflow")
app.add_typer(skill.app,    name="skill")
app.add_typer(record.app,   name="record")

# single commands
app.command("init")(init.run)
app.command("status")(status.run)

# dynamically mount installed skill CLIs
# runs once at startup — core never needs changing for new skills
_skill_clis_mounted = False

def _mount_skill_clis() -> None:
    """
    Discovers installed skills that ship a cli.py and mounts
    their Typer apps as subcommands on the main app.
    Called once at startup. Core never needs changing for new skills.
    A skill exposes CLI commands by providing:
      openkiln/skills/<name>/cli.py with a Typer app named 'app'
    """
    global _skill_clis_mounted
    if _skill_clis_mounted:
        return
    _skill_clis_mounted = True

    if not db.check_connection():
        return  # db not initialised yet — skip silently

    try:
        with db.connection() as conn:
            skills = conn.execute(
                "SELECT skill_name FROM installed_skills"
            ).fetchall()

        for row in skills:
            skill_name = row["skill_name"]
            try:
                mod = importlib.import_module(
                    f"openkiln.skills.{skill_name}.cli"
                )
                skill_app = getattr(mod, "app", None)
                if skill_app:
                    app.add_typer(skill_app, name=skill_name)
            except ModuleNotFoundError:
                pass  # skill has no cli.py — fine, not required
            except Exception:
                pass  # never crash startup due to skill discovery
    except Exception:
        pass  # never crash startup due to skill discovery

_mount_skill_clis()

if __name__ == "__main__":
    app()

from __future__ import annotations

import json
from pathlib import Path

import httpx
import typer
from rich import print as rprint
from rich.console import Console

from openkiln import config, db

app = typer.Typer(
    name="skill",
    help="Skill operations — install, uninstall, list, info, update.",
    no_args_is_help=True,
)

console = Console()

# skills available to install locally (from this package)
# hub skills added in a later version
PACKAGE_DIR = Path(__file__).parent.parent
SKILLS_DIR = PACKAGE_DIR / "skills"
KNOWN_SKILLS = [d.name for d in SKILLS_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]


@app.command("install")
def install(
    skill_name: str = typer.Argument(..., help="Skill name to install."),
) -> None:
    """
    Install a skill. Creates skill database and registers with OpenKiln.
    """
    # check db is initialised
    if not db.check_connection():
        rprint("[red]✗ Database not found.[/red]\nRun [bold]openkiln init[/bold] first.")
        raise typer.Exit(code=1)

    # check skill is known
    if skill_name not in KNOWN_SKILLS:
        rprint(
            f"[red]✗ Unknown skill: {skill_name}[/red]\n"
            f"Available skills: {', '.join(sorted(KNOWN_SKILLS))}"
        )
        raise typer.Exit(code=1)

    cfg = config.get()

    # check not already installed
    with db.connection() as conn:
        existing = conn.execute(
            "SELECT skill_name FROM installed_skills WHERE skill_name = ?", (skill_name,)
        ).fetchone()

    if existing:
        rprint(
            f"[yellow]Skill '{skill_name}' is already installed.[/yellow]\n"
            f"Run [bold]openkiln skill info {skill_name}[/bold] for details."
        )
        raise typer.Exit()

    # initialise skill database
    console.print(f"Installing skill: {skill_name}...")
    db.init_skill(skill_name)
    console.print(f"[green]✓[/green] Database created: {cfg.skill_db_path(skill_name)}")

    # register in installed_skills
    with db.transaction() as conn:
        skill_version = _read_skill_version(skill_name)
        conn.execute(
            """
            INSERT INTO installed_skills
              (skill_name, skill_version, db_path)
            VALUES (?, ?, ?)
            """,
            (skill_name, skill_version, str(cfg.skill_db_path(skill_name))),
        )
    console.print(f"[green]✓[/green] Registered: {skill_name} v{skill_version}")

    # append config section if skill needs it
    _append_config_section(skill_name)

    console.print(
        f"\n[bold green]Skill '{skill_name}' installed.[/bold green]\n"
        f"Run [bold]openkiln skill info {skill_name}[/bold] to get started."
    )


@app.command("list")
def list_skills(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON for agent consumption."),
) -> None:
    """
    List installed skills and available skills.
    """
    if not db.check_connection():
        rprint("[red]✗ Database not found.[/red]\nRun [bold]openkiln init[/bold] first.")
        raise typer.Exit(code=1)

    with db.connection() as conn:
        installed = conn.execute(
            "SELECT skill_name, skill_version FROM installed_skills ORDER BY skill_name"
        ).fetchall()

    installed_names = {row["skill_name"] for row in installed}
    available = sorted(set(KNOWN_SKILLS) - installed_names)

    if output_json:
        typer.echo(
            json.dumps(
                {
                    "installed": [
                        {"name": row["skill_name"], "version": row["skill_version"]} for row in installed
                    ],
                    "available": available,
                }
            )
        )
        return

    if installed:
        console.print("\n[bold]Installed[/bold]")
        for row in installed:
            console.print(f"  [green]✓[/green]  {row['skill_name']:<20} v{row['skill_version']}")
    else:
        console.print("\n[dim]No skills installed.[/dim]")

    if available:
        console.print("\n[bold]Available[/bold]")
        for name in available:
            console.print(f"  [dim]○[/dim]  {name:<20} [dim]run: openkiln skill install {name}[/dim]")

    console.print(
        "\n[dim]Don't see what you need? Build a skill:[/dim] "
        "[dim]https://github.com/OrbiSearch/openkiln-skill-maker[/dim]"
    )
    console.print()


@app.command("info")
def info(
    skill_name: str = typer.Argument(..., help="Skill name."),
    credits: bool = typer.Option(
        False, "--credits", help="Show current API credit balance (OrbiSearch only)."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON for agent consumption."),
) -> None:
    """
    Show detailed information about a skill.
    Reads the skill's SKILL.md — the authoritative self-description.
    """
    # find SKILL.md
    skill_md_path = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_md_path.exists():
        rprint(
            f"[red]✗ Unknown skill: {skill_name}[/red]\n"
            f"Available skills: {', '.join(sorted(KNOWN_SKILLS))}"
        )
        raise typer.Exit(code=1)

    skill_md = skill_md_path.read_text()

    # check if installed
    is_installed = False
    if db.check_connection():
        with db.connection() as conn:
            row = conn.execute(
                "SELECT skill_version FROM installed_skills WHERE skill_name = ?", (skill_name,)
            ).fetchone()
            is_installed = row is not None

    # handle --credits flag
    credits_balance = None
    if credits:
        credits_balance = _fetch_credits(skill_name)

    if output_json:
        data: dict = {
            "skill_name": skill_name,
            "installed": is_installed,
            "skill_md": skill_md,
        }
        if credits_balance is not None:
            data["credits"] = credits_balance
        typer.echo(json.dumps(data))
        return

    # human output
    status_str = (
        "[green]installed[/green]"
        if is_installed
        else f"[yellow]not installed[/yellow] — run: openkiln skill install {skill_name}"
    )
    console.print(f"\nStatus: {status_str}\n")
    console.print(skill_md)

    if credits_balance is not None:
        console.print(f"\n[bold]Credits:[/bold] {credits_balance:,.1f} available")

    console.print()


@app.command("update")
def update(
    skill_name: str = typer.Argument(..., help="Skill name to update."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """
    Apply pending schema migrations for an installed skill.
    Run after upgrading OpenKiln to pick up new skill schema changes.
    """
    if not db.check_connection():
        rprint("[red]✗ Database not found.[/red]\nRun [bold]openkiln init[/bold] first.")
        raise typer.Exit(code=1)

    # check skill is installed
    with db.connection() as conn:
        row = conn.execute(
            "SELECT skill_name, skill_version FROM installed_skills WHERE skill_name = ?", (skill_name,)
        ).fetchone()

    if not row:
        rprint(
            f"[red]✗ Skill '{skill_name}' is not installed.[/red]\n"
            f"Run: openkiln skill install {skill_name}"
        )
        raise typer.Exit(code=1)

    # run pending migrations
    try:
        newly_applied = db.init_skill(skill_name)
    except RuntimeError as e:
        rprint(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=1)

    # update version in installed_skills
    new_version = _read_skill_version(skill_name)
    with db.transaction() as conn:
        conn.execute(
            "UPDATE installed_skills SET skill_version = ?, "
            "updated_at = datetime('now') WHERE skill_name = ?",
            (new_version, skill_name),
        )

    if output_json:
        typer.echo(
            json.dumps(
                {
                    "skill_name": skill_name,
                    "version": new_version,
                    "migrations_applied": newly_applied,
                }
            )
        )
        return

    if newly_applied:
        console.print(f"\n[green]✓[/green] Skill '{skill_name}' updated to v{new_version}")
        for m in newly_applied:
            console.print(f"  Applied: {m}")
    else:
        console.print(f"\n[green]✓[/green] Skill '{skill_name}' is already up to date (v{new_version})")
    console.print()


# ── Internal helpers ──────────────────────────────────────────


def _read_skill_version(skill_name: str) -> str:
    """
    Reads the skill version from its __init__.py __version__ attribute.
    Falls back to "0.1.0" if not defined.
    """
    try:
        import importlib

        mod = importlib.import_module(f"openkiln.skills.{skill_name}")
        return getattr(mod, "__version__", "0.1.0")
    except Exception:
        return "0.1.0"


def _append_config_section(skill_name: str) -> None:
    """
    Appends a config section for the skill to ~/.openkiln/config.toml
    if no section exists for it yet.
    Skills that need no config (e.g. crm) get no section appended.
    """
    # skills that require config sections
    config_templates: dict[str, str] = {
        "orbisearch": ('\n[skills.orbisearch]\napi_key = ""  # get your free key at orbisearch.com\n'),
        "smartlead": ('\n[skills.smartlead]\napi_key = ""\n'),
        "emailguard": ('\n[skills.emailguard]\napi_key = ""  # Bearer token from app.emailguard.io\n'),
    }

    template = config_templates.get(skill_name)
    if not template:
        return  # skill needs no config section

    cfg_path = config.CONFIG_PATH
    if not cfg_path.exists():
        return

    existing = cfg_path.read_text()
    if f"[skills.{skill_name}]" in existing:
        return  # section already exists

    cfg_path.write_text(existing + template)
    console.print(f"[green]✓[/green] Config section added: [skills.{skill_name}]")


def _fetch_credits(skill_name: str) -> float | None:
    """
    Fetches the API credit balance for skills that support it.
    Currently only orbisearch. Returns None for other skills.
    """
    if skill_name != "orbisearch":
        rprint(f"[yellow]--credits is not supported for skill '{skill_name}'[/yellow]")
        return None

    cfg = config.get()
    api_key = __import__("os").environ.get("ORBISEARCH_API_KEY") or cfg.skill_config("orbisearch").get(
        "api_key", ""
    )

    if not api_key:
        rprint(
            "[red]✗ No OrbiSearch API key configured.[/red]\n"
            "Set ORBISEARCH_API_KEY or add it to "
            "~/.openkiln/config.toml"
        )
        return None

    try:
        response = httpx.get(
            "https://api.orbisearch.com/v1/credits",
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["credits"]
    except Exception as e:
        rprint(f"[red]✗ Failed to fetch credits: {e}[/red]")
        return None

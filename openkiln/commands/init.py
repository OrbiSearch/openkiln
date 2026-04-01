from __future__ import annotations

import typer
from rich import print as rprint
from rich.console import Console

from openkiln import config, db

console = Console()


def run() -> None:
    """
    Initialise OpenKiln. Run once on first use.

    Creates:
      ~/.openkiln/config.toml
      ~/.openkiln/core.db
      ~/.openkiln/skills/

    Safe to re-run — nothing is overwritten.
    """
    cfg = config.get()

    # check if already initialised
    if cfg.core_db.exists():
        rprint(
            "[yellow]~/.openkiln/ already exists. Nothing to do.[/yellow]\n"
            "Run [bold]openkiln status[/bold] to verify your installation."
        )
        raise typer.Exit()

    console.print("Initialising OpenKiln...\n")

    # write default config
    config.write_default(
        core_db=config.DEFAULT_CORE_DB,
        skills_dir=config.DEFAULT_SKILLS_DIR,
    )
    console.print(f"[green]✓[/green] Config created: {config.CONFIG_PATH}")

    # create core database and apply schema
    db.init_core()
    console.print(f"[green]✓[/green] Database created: {cfg.core_db}")
    console.print(f"[green]✓[/green] Skills directory: {cfg.skills_dir}")

    console.print(
        "\n[bold green]OpenKiln is ready.[/bold green]\n"
        "Run [bold]openkiln status[/bold] to verify.\n"
        "Run [bold]openkiln skill install crm[/bold] to install your first skill."
    )

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich import print as rprint

console = Console()


def run() -> None:
    """
    Update OpenKiln to the latest version.

    Pulls the latest code from git and reinstalls dependencies.
    Safe to run at any time — no data is affected.
    """
    # resolve repo root from this file's location
    # works for editable installs (pip install -e .)
    repo_root = Path(__file__).parent.parent.parent.resolve()

    # verify this looks like the right directory
    if not (repo_root / ".git").exists():
        rprint(
            "[red]✗ Cannot find git repo.[/red]\n"
            "OpenKiln must be installed in editable mode "
            "from the source repo.\n"
            "Clone the repo and run: pip install -e ."
        )
        raise typer.Exit(code=1)

    console.print(f"\nRepo: {repo_root}\n")

    # git pull
    console.print("[bold]Pulling latest...[/bold]")
    result = subprocess.run(
        ["git", "pull", "origin", "main"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        rprint(
            f"[red]✗ git pull failed:[/red]\n{result.stderr}"
        )
        raise typer.Exit(code=1)

    console.print(result.stdout.strip())

    # pip install -e . to pick up any new dependencies
    console.print("\n[bold]Reinstalling dependencies...[/bold]")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        rprint(
            f"[red]✗ pip install failed:[/red]\n{result.stderr}"
        )
        raise typer.Exit(code=1)

    console.print("[green]✓[/green] Dependencies up to date")
    console.print("\n[bold green]OpenKiln updated.[/bold green]\n")

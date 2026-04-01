from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console

console = Console()


def run() -> None:
    """
    Update OpenKiln to the latest version.

    Detects install method and updates accordingly:
    - pipx install: runs pipx upgrade
    - git clone (dev): runs git pull + pip install
    """
    # check if installed via pipx
    if _try_pipx_upgrade():
        return

    # fall back to git-based update for dev installs
    _try_git_upgrade()


def _try_pipx_upgrade() -> bool:
    """Attempt pipx upgrade. Returns True if successful."""
    # check if pipx is available
    try:
        result = subprocess.run(
            ["pipx", "upgrade", "openkiln"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print(f"\n[green]\u2713[/green] {result.stdout.strip()}")
            console.print("\n[bold green]OpenKiln updated.[/bold green]\n")
            return True

        # pipx exists but openkiln wasn't installed via pipx
        if "is not installed" in result.stderr:
            return False

        # pipx exists, openkiln is installed, but upgrade failed
        rprint(f"[red]\u2717 pipx upgrade failed:[/red]\n{result.stderr}")
        raise typer.Exit(code=1)

    except FileNotFoundError:
        # pipx not installed
        return False


def _try_git_upgrade() -> None:
    """Fall back to git-based update for dev installs."""
    repo_root = Path(__file__).parent.parent.parent.resolve()

    if not (repo_root / ".git").exists():
        rprint(
            "[yellow]Could not detect install method.[/yellow]\n\n"
            "If you installed via pipx:\n"
            "  pipx upgrade openkiln\n\n"
            "If you installed from source:\n"
            "  cd /path/to/openkiln && git pull && pip install -e .\n"
        )
        raise typer.Exit(code=1)

    console.print(f"\nDev install detected: {repo_root}\n")

    # git pull
    console.print("[bold]Pulling latest...[/bold]")
    result = subprocess.run(
        ["git", "pull", "origin", "main"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        rprint(f"[red]\u2717 git pull failed:[/red]\n{result.stderr}")
        raise typer.Exit(code=1)

    console.print(result.stdout.strip())

    # pip install
    console.print("\n[bold]Reinstalling dependencies...[/bold]")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        rprint(f"[red]\u2717 pip install failed:[/red]\n{result.stderr}")
        raise typer.Exit(code=1)

    console.print("[green]\u2713[/green] Dependencies up to date")
    console.print("\n[bold green]OpenKiln updated.[/bold green]\n")

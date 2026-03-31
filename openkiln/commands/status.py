from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from openkiln import config, db

console = Console()


def run(
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON for agent consumption."
    ),
) -> None:
    """
    Show a summary of the current OpenKiln installation.

    Checks database connection, record counts, installed skills,
    and last workflow run. Run at the start of every agent session.
    """
    cfg = config.get()

    # check connection
    connected = db.check_connection()

    if not connected:
        if output_json:
            typer.echo(json.dumps({
                "connected": False,
                "error": "Database not found. Run: openkiln init"
            }))
        else:
            rprint(
                "[red]✗ Database not found.[/red]\n"
                "Run [bold]openkiln init[/bold] to set up OpenKiln."
            )
        raise typer.Exit(code=1)

    # gather data
    with db.connection() as conn:
        # record counts by type
        record_rows = conn.execute("""
            SELECT type, COUNT(*) as count
            FROM records
            WHERE record_status = 'active'
            GROUP BY type
            ORDER BY type
        """).fetchall()

        # installed skills
        skill_rows = conn.execute("""
            SELECT skill_name, skill_version, installed_at
            FROM installed_skills
            ORDER BY skill_name
        """).fetchall()

        # last workflow run
        last_run = conn.execute("""
            SELECT workflow_name, status, records_in,
                   records_out, started_at
            FROM workflow_runs
            ORDER BY started_at DESC
            LIMIT 1
        """).fetchone()

    # json output for agents
    if output_json:
        typer.echo(json.dumps({
            "connected": True,
            "core_db": str(cfg.core_db),
            "records": {row["type"]: row["count"] for row in record_rows},
            "skills": [
                {
                    "name": row["skill_name"],
                    "version": row["skill_version"],
                    "installed_at": row["installed_at"],
                }
                for row in skill_rows
            ],
            "last_workflow_run": dict(last_run) if last_run else None,
        }))
        return

    # human-readable output
    from importlib.metadata import version
    try:
        ver = version("openkiln")
    except Exception:
        ver = "dev"

    console.print(f"\n[bold]OpenKiln v{ver}[/bold]")
    console.print("─" * 40)

    # database
    console.print(
        f"[green]✓[/green] Database   {cfg.core_db}"
    )
    console.print()

    # records
    if record_rows:
        console.print("[bold]Records[/bold]")
        for row in record_rows:
            console.print(f"  {row['type']:<20} {row['count']:>8,}")
    else:
        console.print("[dim]Records      none imported yet[/dim]")
    console.print()

    # skills
    if skill_rows:
        console.print("[bold]Skills[/bold]")
        for row in skill_rows:
            console.print(
                f"  [green]✓[/green] {row['skill_name']:<18} "
                f"v{row['skill_version']}"
            )
    else:
        console.print("[dim]Skills       none installed[/dim]")
        console.print(
            "  Run: [bold]openkiln skill install crm[/bold]"
        )
    console.print()

    # last workflow run
    if last_run:
        status_colour = "green" if last_run["status"] == "complete" else "red"
        console.print("[bold]Last workflow[/bold]")
        console.print(
            f"  {last_run['workflow_name']}   "
            f"[{status_colour}]{last_run['status']}[/{status_colour}]   "
            f"{last_run['records_in']:,} in   "
            f"{last_run['records_out']:,} out   "
            f"{last_run['started_at']}"
        )
    else:
        console.print("[dim]Workflows    no runs yet[/dim]")

    console.print()

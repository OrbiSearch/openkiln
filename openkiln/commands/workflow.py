from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from openkiln import db
from openkiln.core.workflow import (
    parse_workflow,
    validate_workflow,
    run_workflow,
)

app = typer.Typer(
    name="workflow",
    help="Workflow operations — run, validate, history.",
    no_args_is_help=True,
)

console = Console()


@app.command("run")
def run(
    file: Path = typer.Argument(
        ..., help="Path to workflow YAML file.",
        exists=True, readable=True,
    ),
    apply: bool = typer.Option(
        False, "--apply", help="Actually execute sinks. Default is dry run."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Run a workflow pipeline.

    Default is dry run — reads source, applies transforms and filters,
    reports what would be written to sinks. Use --apply to execute.
    """
    try:
        wf = parse_workflow(file)
    except Exception as e:
        rprint(f"[red]\u2717 Failed to parse workflow: {e}[/red]")
        raise typer.Exit(code=1)

    # validate first
    errors = validate_workflow(wf)
    if errors:
        rprint(f"[red]\u2717 Workflow validation failed:[/red]")
        for err in errors:
            rprint(f"  - {err}")
        raise typer.Exit(code=1)

    dry_run = not apply
    mode = "Dry run" if dry_run else "Executing"
    if not output_json:
        console.print(f"\n[bold]{mode}: {wf.name}[/bold]")
        console.print(f"  Source: {wf.source.get('skill')}.{wf.source.get('type')}")
        if wf.transforms:
            console.print(f"  Transforms: {', '.join(wf.transforms)}")
        if wf.filter:
            console.print(f"  Filter: {wf.filter}")
        console.print(f"  Sinks: {len(wf.sinks)}")
        console.print()

    result = run_workflow(wf, dry_run=dry_run)

    if output_json:
        typer.echo(json.dumps({
            "workflow": wf.name,
            "status": result.status,
            "records_in": result.records_in,
            "records_out": result.records_out,
            "dry_run": dry_run,
            "sinks": result.sink_results,
            "error": result.error,
        }, indent=2))
        return

    if result.status == "failed":
        rprint(f"[red]\u2717 Workflow failed: {result.error}[/red]")
        raise typer.Exit(code=1)

    # success output
    table = Table(title="Pipeline Results")
    table.add_column("Stage", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("Records read", str(result.records_in))
    if wf.transforms:
        table.add_row("After transforms", str(result.records_out))
    if wf.filter:
        table.add_row("After filter", str(result.records_out))

    console.print(table)

    if result.sink_results:
        console.print()
        sink_table = Table(title="Sinks")
        sink_table.add_column("Skill")
        sink_table.add_column("Action")
        sink_table.add_column("Result", justify="right")

        for sr in result.sink_results:
            if dry_run:
                sink_table.add_row(
                    sr.get("skill", ""),
                    sr.get("action", ""),
                    f"would write {sr.get('would_write', 0)}",
                )
            else:
                sink_table.add_row(
                    sr.get("skill", ""),
                    sr.get("action", ""),
                    f"wrote {sr.get('written', 0)}",
                )

        console.print(sink_table)

    if dry_run:
        console.print(
            f"\n[yellow]Dry run complete. "
            f"Use --apply to execute sinks.[/yellow]\n"
        )
    else:
        console.print(
            f"\n[bold green]\u2713 Workflow '{wf.name}' completed.[/bold green]\n"
        )


@app.command("validate")
def validate(
    file: Path = typer.Argument(
        ..., help="Path to workflow YAML file.",
        exists=True, readable=True,
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Validate a workflow YAML file without running it."""
    try:
        wf = parse_workflow(file)
    except Exception as e:
        if output_json:
            typer.echo(json.dumps({"valid": False, "errors": [str(e)]}))
        else:
            rprint(f"[red]\u2717 Parse error: {e}[/red]")
        raise typer.Exit(code=1)

    errors = validate_workflow(wf)

    if output_json:
        typer.echo(json.dumps({
            "valid": len(errors) == 0,
            "workflow": wf.name,
            "errors": errors,
        }, indent=2))
        if errors:
            raise typer.Exit(code=1)
        return

    if errors:
        rprint(f"[red]\u2717 Validation failed for '{wf.name}':[/red]")
        for err in errors:
            rprint(f"  - {err}")
        raise typer.Exit(code=1)

    console.print(f"\n[green]\u2713[/green] Workflow '{wf.name}' is valid.")
    console.print(f"  Source: {wf.source.get('skill')}.{wf.source.get('type')}")
    if wf.transforms:
        console.print(f"  Transforms: {', '.join(wf.transforms)}")
    console.print(f"  Sinks: {len(wf.sinks)}")
    console.print()


@app.command("history")
def history(
    name: Optional[str] = typer.Argument(
        None, help="Filter by workflow name."
    ),
    limit: int = typer.Option(
        20, "--limit", help="Max runs to show."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Show past workflow runs."""
    if not db.check_connection():
        rprint(
            "[red]\u2717 Database not found.[/red]\n"
            "Run [bold]openkiln init[/bold] first."
        )
        raise typer.Exit(code=1)

    with db.connection() as conn:
        if name:
            runs = conn.execute(
                "SELECT * FROM workflow_runs WHERE workflow_name = ? "
                "ORDER BY started_at DESC LIMIT ?",
                (name, limit),
            ).fetchall()
        else:
            runs = conn.execute(
                "SELECT * FROM workflow_runs "
                "ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

    if output_json:
        typer.echo(json.dumps(
            [dict(r) for r in runs], indent=2
        ))
        return

    if not runs:
        console.print("\n[dim]No workflow runs found.[/dim]\n")
        return

    table = Table(title="Workflow Runs")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("In", justify="right")
    table.add_column("Out", justify="right")
    table.add_column("Started")
    table.add_column("Error")

    for r in runs:
        status = r["status"]
        style = {
            "complete": "green",
            "failed": "red",
            "running": "yellow",
        }.get(status, "")

        table.add_row(
            str(r["id"]),
            r["workflow_name"],
            f"[{style}]{status}[/{style}]" if style else status,
            str(r["records_in"] or ""),
            str(r["records_out"] or ""),
            str(r["started_at"] or "")[:19],
            (r["error"] or "")[:50],
        )

    console.print()
    console.print(table)
    console.print()

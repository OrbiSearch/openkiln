"""OrbiSearch CLI commands for OpenKiln."""
from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from openkiln.skills.orbisearch.api import get_client, OrbiSearchError

app = typer.Typer(
    name="orbisearch",
    help="OrbiSearch — email verification.",
    no_args_is_help=True,
)

console = Console()


def _int(val: object) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _handle_api_error(err: OrbiSearchError) -> None:
    console.print(f"[red]OrbiSearch API error:[/red] {err}")
    raise typer.Exit(code=1)


# ── Read-only commands ──────────────────────────────────────


@app.command("verify")
def verify_email(
    email: str = typer.Argument(..., help="Email address to verify"),
    timeout: int = typer.Option(70, help="Timeout in seconds (3-90)"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Verify a single email address."""
    try:
        client = get_client()
        result = client.verify_email(email, timeout=timeout)
    except OrbiSearchError as err:
        _handle_api_error(err)
        return

    if as_json:
        typer.echo(json.dumps(result, indent=2))
        return

    table = Table(title=f"Verification: {email}")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Status", result.get("status", ""))
    table.add_row("Substatus", result.get("substatus") or "—")
    table.add_row("Explanation", result.get("explanation", ""))
    table.add_row("Provider", result.get("email_provider", ""))
    table.add_row("Disposable", str(result.get("is_disposable", "—")))
    table.add_row("Role Account", str(result.get("is_role_account", "—")))
    table.add_row("Free Provider", str(result.get("is_free", "—")))
    console.print(table)


@app.command("credits")
def credits(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show current OrbiSearch credit balance."""
    try:
        client = get_client()
        data = client.get_credits()
    except OrbiSearchError as err:
        _handle_api_error(err)
        return

    if as_json:
        typer.echo(json.dumps(data, indent=2))
        return

    console.print(f"Credits: [green]{data.get('credits', 0)}[/green]")


@app.command("bulk-submit")
def bulk_submit(
    emails: list[str] = typer.Argument(..., help="Email addresses to verify"),
    apply: bool = typer.Option(False, "--apply", help="Actually submit the job"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Submit a bulk email verification job."""
    if not apply:
        console.print(
            f"[yellow]Dry run:[/yellow] would submit {len(emails)} email(s) "
            "for bulk verification. Pass --apply to execute."
        )
        return

    try:
        client = get_client()
        data = client.submit_bulk(emails)
    except OrbiSearchError as err:
        _handle_api_error(err)
        return

    # persist job locally
    from openkiln.skills.orbisearch import queries

    queries.upsert_bulk_job(data)

    if as_json:
        typer.echo(json.dumps(data, indent=2))
        return

    console.print(f"Job submitted: [green]{data.get('job_id')}[/green]")
    console.print(f"  Emails: {_int(data.get('total_emails'))}")
    console.print(f"  Estimated cost: {data.get('estimated_cost', 0)} credits")


@app.command("bulk-status")
def bulk_status(
    job_id: str = typer.Argument(..., help="Bulk job ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Check the status of a bulk verification job."""
    try:
        client = get_client()
        data = client.get_bulk_status(job_id)
    except OrbiSearchError as err:
        _handle_api_error(err)
        return

    # update local record
    from openkiln.skills.orbisearch import queries

    queries.upsert_bulk_job(data)

    if as_json:
        typer.echo(json.dumps(data, indent=2))
        return

    table = Table(title=f"Bulk Job: {job_id}")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Status", data.get("status", ""))
    table.add_row("Progress", f"{_int(data.get('emails_processed'))}/{_int(data.get('total_emails'))}")
    table.add_row("Retry Status", data.get("retry_status", "none"))
    table.add_row("Submitted", data.get("submitted_at", "—"))
    table.add_row("Completed", data.get("completed_at") or "—")
    console.print(table)


@app.command("bulk-results")
def bulk_results(
    job_id: str = typer.Argument(..., help="Bulk job ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Retrieve results of a completed bulk verification job."""
    try:
        client = get_client()
        data = client.get_bulk_results(job_id)
    except OrbiSearchError as err:
        _handle_api_error(err)
        return

    if as_json:
        typer.echo(json.dumps(data, indent=2))
        return

    results = data.get("results", [])
    if not results:
        console.print("[yellow]No results yet.[/yellow]")
        return

    table = Table(title=f"Results for job {job_id} ({len(results)} emails)")
    table.add_column("Email")
    table.add_column("Status")
    table.add_column("Substatus")
    table.add_column("Provider")
    for r in results:
        table.add_row(
            r.get("email", ""),
            r.get("status", ""),
            r.get("substatus") or "—",
            r.get("email_provider", ""),
        )
    console.print(table)

    pending = data.get("pending_retries", [])
    if pending:
        console.print(f"\n[yellow]{len(pending)} email(s) still retrying.[/yellow]")

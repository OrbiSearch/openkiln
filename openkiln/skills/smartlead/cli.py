from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from openkiln.skills.smartlead.api import get_client, SmartleadError
from openkiln.skills.smartlead import queries

app = typer.Typer(
    name="smartlead",
    help="Smartlead skill — campaigns, leads, analytics.",
    no_args_is_help=True,
)

accounts_app = typer.Typer(
    help="Email account operations.",
    no_args_is_help=True,
)
app.add_typer(accounts_app, name="accounts")

console = Console()


def _handle_api_error(e: SmartleadError) -> None:
    """Print a SmartleadError and exit."""
    rprint(f"[red]\u2717 {e}[/red]")
    raise typer.Exit(code=1)


# ── Campaigns ────────────────────────────────────────────────


@app.command("campaigns")
def campaigns(
    campaign_id: Optional[int] = typer.Argument(
        None, help="Campaign ID to show details for. Omit to list all."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """List campaigns or show details for a specific campaign."""
    try:
        client = get_client()
    except SmartleadError as e:
        _handle_api_error(e)

    if campaign_id is not None:
        # show single campaign + sequences
        try:
            campaign = client.get_campaign(campaign_id)
            sequences = client.get_sequences(campaign_id)
        except SmartleadError as e:
            _handle_api_error(e)

        if output_json:
            campaign["sequences"] = sequences
            typer.echo(json.dumps(campaign, indent=2))
            return

        console.print(f"\n[bold]{campaign.get('name', 'Unnamed')}[/bold]")
        console.print(f"  ID:     {campaign.get('id')}")
        console.print(f"  Status: {campaign.get('status', 'unknown')}")

        if campaign.get("timezone"):
            console.print(f"  TZ:     {campaign['timezone']}")

        # show sequences
        if sequences:
            console.print(f"\n  [bold]Sequences ({len(sequences)})[/bold]")
            for seq in sequences:
                seq_num = seq.get("seq_number", "?")
                delay = seq.get("seq_delay_details", {})
                delay_days = delay.get("delay_in_days", 0) if isinstance(delay, dict) else 0
                variants = seq.get("variants", [])
                variant_count = len(variants)
                subject = ""
                if variants:
                    subject = variants[0].get("subject", "")
                    if len(subject) > 60:
                        subject = subject[:57] + "..."
                console.print(
                    f"    Step {seq_num} "
                    f"(+{delay_days}d, {variant_count} variant{'s' if variant_count != 1 else ''})"
                    f": {subject}"
                )
        else:
            console.print("\n  [dim]No sequences configured.[/dim]")

        console.print()
        return

    # list all campaigns
    try:
        data = client.list_campaigns()
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps(data, indent=2))
        return

    if not data:
        console.print("\n[dim]No campaigns found.[/dim]\n")
        return

    table = Table(title="Campaigns")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Created")

    for c in data:
        status = c.get("status", "")
        style = {
            "ACTIVE": "green",
            "PAUSED": "yellow",
            "STOPPED": "red",
            "DRAFTED": "dim",
        }.get(status, "")
        table.add_row(
            str(c.get("id", "")),
            c.get("name", ""),
            f"[{style}]{status}[/{style}]" if style else status,
            str(c.get("created_at", ""))[:10],
        )

    console.print()
    console.print(table)
    console.print()


# ── Stats ────────────────────────────────────────────────────


@app.command("stats")
def stats(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Show campaign analytics."""
    try:
        client = get_client()
        analytics = client.get_campaign_analytics(campaign_id)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps(analytics, indent=2))
        return

    campaign_name = analytics.get("name", f"Campaign {campaign_id}")
    console.print(f"\n[bold]{campaign_name}[/bold]")

    # engagement metrics
    sent = analytics.get("unique_sent_count", 0) or 0
    opened = analytics.get("unique_open_count", 0) or 0
    clicked = analytics.get("unique_click_count", 0) or 0
    replied = analytics.get("reply_count", 0) or 0

    def _rate(n: int, total: int) -> str:
        if not total:
            return "0.0%"
        return f"{n / total * 100:.1f}%"

    table = Table(title="Engagement")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Rate", justify="right")

    table.add_row("Sent", str(sent), "-")
    table.add_row("Opened", str(opened), _rate(opened, sent))
    table.add_row("Clicked", str(clicked), _rate(clicked, sent))
    table.add_row("Replied", str(replied), _rate(replied, sent))

    console.print()
    console.print(table)

    # lead status breakdown
    lead_stats = analytics.get("campaign_lead_stats", {})
    if lead_stats:
        console.print()
        status_table = Table(title="Lead Status")
        status_table.add_column("Status", style="bold")
        status_table.add_column("Count", justify="right")

        for key in [
            "total", "notStarted", "inprogress", "completed",
            "interested", "blocked", "paused",
        ]:
            val = lead_stats.get(key)
            if val is not None and val > 0:
                label = {
                    "notStarted": "Not Started",
                    "inprogress": "In Progress",
                }.get(key, key.capitalize())
                status_table.add_row(label, str(val))

        console.print(status_table)

    console.print()


# ── Email Accounts ───────────────────────────────────────────


@accounts_app.command("list")
def accounts_list(
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """List all email accounts."""
    try:
        client = get_client()
        data = client.list_email_accounts()
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps(data, indent=2))
        return

    if not data:
        console.print("\n[dim]No email accounts found.[/dim]\n")
        return

    table = Table(title="Email Accounts")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Email")
    table.add_column("Name")
    table.add_column("Daily Limit", justify="right")
    table.add_column("Warmup")

    for acct in data:
        warmup = acct.get("warmup_enabled", False)
        warmup_str = "[green]on[/green]" if warmup else "[dim]off[/dim]"
        table.add_row(
            str(acct.get("id", "")),
            acct.get("from_email", ""),
            acct.get("from_name", ""),
            str(acct.get("max_email_per_day", "")),
            warmup_str,
        )

    console.print()
    console.print(table)
    console.print()


# ── Sync ─────────────────────────────────────────────────────


@app.command("sync")
def sync(
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Sync campaigns, sequences, and stats from Smartlead to local DB."""
    try:
        client = get_client()
    except SmartleadError as e:
        _handle_api_error(e)

    console.print("Syncing campaigns from Smartlead...")

    try:
        campaigns_data = client.list_campaigns()
    except SmartleadError as e:
        _handle_api_error(e)

    synced = []
    for campaign in campaigns_data:
        cid = campaign.get("id")
        if cid is None:
            continue

        # sync campaign metadata
        queries.upsert_campaign(campaign)

        # sync sequences
        try:
            seqs = client.get_sequences(cid)
            queries.upsert_sequences(cid, seqs)
        except SmartleadError:
            seqs = []

        # sync analytics snapshot
        try:
            analytics = client.get_campaign_analytics(cid)
            queries.insert_campaign_stats(cid, analytics)
        except SmartleadError:
            analytics = {}

        synced.append({
            "id": cid,
            "name": campaign.get("name"),
            "status": campaign.get("status"),
            "sequences": len(seqs),
        })

        if not output_json:
            console.print(
                f"  [green]\u2713[/green] {campaign.get('name', cid)} "
                f"({campaign.get('status', '?')}, "
                f"{len(seqs)} sequences)"
            )

    if output_json:
        typer.echo(json.dumps({"synced": synced}, indent=2))
    else:
        console.print(
            f"\n[bold green]Synced {len(synced)} campaigns.[/bold green]\n"
        )

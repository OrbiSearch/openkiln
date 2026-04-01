from __future__ import annotations

import json
from pathlib import Path
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


# ── Campaign Creation ────────────────────────────────────────


@app.command("create")
def create(
    name: str = typer.Argument(..., help="Campaign name."),
    client_id: Optional[int] = typer.Option(
        None, "--client-id", help="Associate with a client (sub-account)."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Create a new campaign (DRAFTED status)."""
    try:
        client = get_client()
        result = client.create_campaign(name, client_id=client_id)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps(result, indent=2))
        return

    campaign_id = result.get("id", "?")
    console.print(
        f"\n[green]\u2713[/green] Campaign created: "
        f"[bold]{name}[/bold] (ID: {campaign_id}, status: DRAFTED)"
    )
    console.print(
        f"\nNext steps:\n"
        f"  openkiln smartlead sequence {campaign_id} --file sequences.yml\n"
        f"  openkiln smartlead schedule {campaign_id} --timezone US/Eastern\n"
        f"  openkiln smartlead accounts add {campaign_id} --account-id <id>\n"
    )


@app.command("duplicate")
def duplicate(
    campaign_id: int = typer.Argument(..., help="Campaign ID to duplicate."),
    name: Optional[str] = typer.Option(
        None, "--name", help="Name for the new campaign. Default: '<original> (copy)'."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Duplicate a campaign — copies sequences and settings to a new drafted campaign."""
    try:
        client = get_client()

        # read source campaign
        source = client.get_campaign(campaign_id)
        source_sequences = client.get_sequences(campaign_id)
    except SmartleadError as e:
        _handle_api_error(e)

    new_name = name or f"{source.get('name', 'Campaign')} (copy)"

    try:
        # create new campaign
        result = client.create_campaign(new_name)
        new_id = result.get("id")

        # copy sequences
        if source_sequences:
            client.save_sequences(new_id, source_sequences)

        # copy email accounts
        try:
            source_accounts = client.get_campaign_email_accounts(campaign_id)
            if source_accounts:
                account_ids = [a["id"] for a in source_accounts if "id" in a]
                if account_ids:
                    client.add_email_accounts_to_campaign(new_id, account_ids)
        except SmartleadError:
            pass  # non-critical — accounts can be added manually

    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps({
            "source_id": campaign_id,
            "new_id": new_id,
            "name": new_name,
            "sequences_copied": len(source_sequences),
        }, indent=2))
        return

    console.print(
        f"\n[green]\u2713[/green] Duplicated campaign {campaign_id} "
        f"\u2192 [bold]{new_name}[/bold] (ID: {new_id})"
    )
    console.print(
        f"  Sequences copied: {len(source_sequences)}"
    )
    console.print(
        f"\nEdit sequences, then start:\n"
        f"  openkiln smartlead campaigns {new_id}\n"
        f"  openkiln smartlead start {new_id}\n"
    )


@app.command("sequence")
def sequence(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    file: Path = typer.Option(
        ..., "--file", "-f", help="JSON or YAML file with sequence steps.",
        exists=True, readable=True,
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Set email sequences for a campaign from a file.

    File format (JSON array):
    [
      {
        "seq_number": 1,
        "seq_delay_details": {"delay_in_days": 0},
        "variants": [
          {"subject": "...", "email_body": "...", "variant_label": "A"}
        ]
      }
    ]
    """
    content = file.read_text()

    # try JSON first, then YAML
    try:
        sequences = json.loads(content)
    except json.JSONDecodeError:
        try:
            import yaml  # noqa: F811
            sequences = yaml.safe_load(content)
        except Exception:
            rprint("[red]\u2717 Could not parse file as JSON or YAML.[/red]")
            raise typer.Exit(code=1)

    if not isinstance(sequences, list):
        rprint("[red]\u2717 File must contain a JSON/YAML array of sequence steps.[/red]")
        raise typer.Exit(code=1)

    try:
        client = get_client()
        result = client.save_sequences(campaign_id, sequences)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps({
            "campaign_id": campaign_id,
            "sequences_saved": len(sequences),
        }, indent=2))
        return

    console.print(
        f"\n[green]\u2713[/green] Saved {len(sequences)} sequence steps "
        f"to campaign {campaign_id}.\n"
    )


@app.command("schedule")
def schedule(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    timezone: str = typer.Option(
        ..., "--timezone", "-tz", help="IANA timezone (e.g. US/Eastern)."
    ),
    days: str = typer.Option(
        "1,2,3,4,5", "--days",
        help="Comma-separated days (0=Sun, 1=Mon, ..., 6=Sat)."
    ),
    start_hour: str = typer.Option(
        "09:00", "--start-hour", help="Send window start (24h, e.g. 09:00)."
    ),
    end_hour: str = typer.Option(
        "17:00", "--end-hour", help="Send window end (24h, e.g. 17:00)."
    ),
    max_leads_per_day: Optional[int] = typer.Option(
        None, "--max-leads-per-day", help="Max new leads contacted per day."
    ),
    min_time_btw_emails: int = typer.Option(
        2, "--min-gap", help="Min minutes between emails."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Set the sending schedule for a campaign."""
    days_list = [int(d.strip()) for d in days.split(",")]

    try:
        client = get_client()
        client.update_campaign_schedule(
            campaign_id,
            timezone=timezone,
            days_of_the_week=days_list,
            start_hour=start_hour,
            end_hour=end_hour,
            min_time_btw_emails=min_time_btw_emails,
            max_leads_per_day=max_leads_per_day,
        )
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps({
            "campaign_id": campaign_id,
            "timezone": timezone,
            "days": days_list,
            "start_hour": start_hour,
            "end_hour": end_hour,
        }, indent=2))
        return

    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    day_str = ", ".join(day_names[d] for d in days_list if 0 <= d <= 6)
    console.print(
        f"\n[green]\u2713[/green] Schedule set for campaign {campaign_id}:\n"
        f"  {day_str}, {start_hour}\u2013{end_hour} ({timezone})"
    )
    if max_leads_per_day:
        console.print(f"  Max leads/day: {max_leads_per_day}")
    console.print()


@accounts_app.command("add")
def accounts_add(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    account_id: list[int] = typer.Option(
        ..., "--account-id", help="Email account ID(s) to add. Repeatable."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Add email accounts to a campaign."""
    try:
        client = get_client()
        client.add_email_accounts_to_campaign(campaign_id, account_id)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps({
            "campaign_id": campaign_id,
            "added": account_id,
        }, indent=2))
        return

    console.print(
        f"\n[green]\u2713[/green] Added {len(account_id)} email account(s) "
        f"to campaign {campaign_id}.\n"
    )

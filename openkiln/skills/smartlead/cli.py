from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from openkiln import db
from openkiln.skills.smartlead import CONTACT_TO_SMARTLEAD, INTERNAL_FIELDS, queries
from openkiln.skills.smartlead.api import SmartleadError, get_client

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
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
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
    start_date: Optional[str] = typer.Option(
        None, "--start-date", help="Start date (YYYY-MM-DD) for date-range analytics."
    ),
    end_date: Optional[str] = typer.Option(
        None, "--end-date", help="End date (YYYY-MM-DD) for date-range analytics."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show campaign analytics. Use --start-date/--end-date for date-range breakdown."""
    try:
        client = get_client()
        if start_date and end_date:
            analytics = client.get_campaign_analytics_by_date(
                campaign_id, start_date=start_date, end_date=end_date
            )
        else:
            analytics = client.get_campaign_analytics(campaign_id)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps(analytics, indent=2))
        return

    campaign_name = analytics.get("name", f"Campaign {campaign_id}")
    console.print(f"\n[bold]{campaign_name}[/bold]")

    # engagement metrics — API may return strings or ints
    def _int(val: object) -> int:
        try:
            return int(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0

    sent = _int(analytics.get("unique_sent_count", 0))
    opened = _int(analytics.get("unique_open_count", 0))
    clicked = _int(analytics.get("unique_click_count", 0))
    replied = _int(analytics.get("reply_count", 0))

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
            "total",
            "notStarted",
            "inprogress",
            "completed",
            "interested",
            "blocked",
            "paused",
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
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
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
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
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
        except SmartleadError as e:
            seqs = []
            if not output_json:
                console.print(
                    f"  [yellow]\u26a0 Failed to sync sequences for "
                    f"{campaign.get('name', cid)}: {e}[/yellow]"
                )

        # sync analytics snapshot
        try:
            analytics = client.get_campaign_analytics(cid)
            queries.insert_campaign_stats(cid, analytics)
        except SmartleadError as e:
            analytics = {}
            if not output_json:
                console.print(
                    f"  [yellow]\u26a0 Failed to sync analytics for "
                    f"{campaign.get('name', cid)}: {e}[/yellow]"
                )

        synced.append(
            {
                "id": cid,
                "name": campaign.get("name"),
                "status": campaign.get("status"),
                "sequences": len(seqs),
            }
        )

        if not output_json:
            console.print(
                f"  [green]\u2713[/green] {campaign.get('name', cid)} "
                f"({campaign.get('status', '?')}, "
                f"{len(seqs)} sequences)"
            )

    if output_json:
        typer.echo(json.dumps({"synced": synced}, indent=2))
    else:
        console.print(f"\n[bold green]Synced {len(synced)} campaigns.[/bold green]\n")


# ── Campaign Creation ────────────────────────────────────────


@app.command("create")
def create(
    name: str = typer.Argument(..., help="Campaign name."),
    client_id: Optional[int] = typer.Option(
        None, "--client-id", help="Associate with a client (sub-account)."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
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
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
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

        # copy sequences — normalize format for the save endpoint
        if source_sequences:
            normalized = []
            for seq in source_sequences:
                delay = seq.get("seq_delay_details", {})
                # API returns delayInDays but expects delay_in_days
                delay_days = delay.get("delay_in_days") or delay.get("delayInDays") or 0
                entry: dict = {
                    "seq_number": seq.get("seq_number"),
                    "seq_delay_details": {"delay_in_days": delay_days},
                }
                # copy subject/body from top-level or first variant
                variants = seq.get("sequence_variants", [])
                if variants:
                    entry["subject"] = variants[0].get("subject", "")
                    entry["email_body"] = variants[0].get("email_body", "")
                elif seq.get("subject"):
                    entry["subject"] = seq.get("subject", "")
                    entry["email_body"] = seq.get("email_body", "")
                normalized.append(entry)
            client.save_sequences(new_id, normalized)

        # copy email accounts
        try:
            source_accounts = client.get_campaign_email_accounts(campaign_id)
            if source_accounts:
                account_ids = [a["id"] for a in source_accounts if "id" in a]
                if account_ids:
                    client.add_email_accounts_to_campaign(new_id, account_ids)
        except SmartleadError as e:
            if not output_json:
                console.print(
                    f"  [yellow]\u26a0 Could not copy email accounts: {e}[/yellow]\n"
                    f"  Add them manually: openkiln smartlead accounts add {new_id} --account-id <id>"
                )

    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(
            json.dumps(
                {
                    "source_id": campaign_id,
                    "new_id": new_id,
                    "name": new_name,
                    "sequences_copied": len(source_sequences),
                },
                indent=2,
            )
        )
        return

    console.print(
        f"\n[green]\u2713[/green] Duplicated campaign {campaign_id} "
        f"\u2192 [bold]{new_name}[/bold] (ID: {new_id})"
    )
    console.print(f"  Sequences copied: {len(source_sequences)}")
    console.print(
        f"\nEdit sequences, then start:\n"
        f"  openkiln smartlead campaigns {new_id}\n"
        f"  openkiln smartlead start {new_id}\n"
    )


@app.command("sequence")
def sequence(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    file: Path = typer.Option(
        ...,
        "--file",
        "-f",
        help="JSON file with sequence steps.",
        exists=True,
        readable=True,
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Set email sequences for a campaign from a JSON file.

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

    try:
        sequences = json.loads(content)
    except json.JSONDecodeError:
        rprint("[red]\u2717 Could not parse file as JSON.[/red]")
        raise typer.Exit(code=1)

    if not isinstance(sequences, list):
        rprint("[red]\u2717 File must contain a JSON array of sequence steps.[/red]")
        raise typer.Exit(code=1)

    try:
        client = get_client()
        client.save_sequences(campaign_id, sequences)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(
            json.dumps(
                {
                    "campaign_id": campaign_id,
                    "sequences_saved": len(sequences),
                },
                indent=2,
            )
        )
        return

    console.print(
        f"\n[green]\u2713[/green] Saved {len(sequences)} sequence steps to campaign {campaign_id}.\n"
    )


@app.command("schedule")
def schedule(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    timezone: str = typer.Option(..., "--timezone", "-tz", help="IANA timezone (e.g. US/Eastern)."),
    days: str = typer.Option(
        "1,2,3,4,5", "--days", help="Comma-separated days (0=Sun, 1=Mon, ..., 6=Sat)."
    ),
    start_hour: str = typer.Option("09:00", "--start-hour", help="Send window start (24h, e.g. 09:00)."),
    end_hour: str = typer.Option("17:00", "--end-hour", help="Send window end (24h, e.g. 17:00)."),
    max_leads_per_day: Optional[int] = typer.Option(
        None, "--max-leads-per-day", help="Max new leads contacted per day."
    ),
    min_time_btw_emails: int = typer.Option(
        3, "--min-gap", help="Min minutes between emails (minimum 3)."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Set the sending schedule for a campaign."""
    import re

    try:
        days_list = [int(d.strip()) for d in days.split(",")]
    except ValueError:
        rprint("[red]\u2717 --days must be comma-separated numbers (0=Sun through 6=Sat).[/red]")
        raise typer.Exit(code=1)

    for d in days_list:
        if d < 0 or d > 6:
            rprint(f"[red]\u2717 Invalid day: {d}. Use 0=Sun through 6=Sat.[/red]")
            raise typer.Exit(code=1)

    hour_pattern = re.compile(r"^\d{1,2}:\d{2}$")
    if not hour_pattern.match(start_hour):
        rprint(f"[red]\u2717 Invalid --start-hour: {start_hour}. Use HH:MM format.[/red]")
        raise typer.Exit(code=1)
    if not hour_pattern.match(end_hour):
        rprint(f"[red]\u2717 Invalid --end-hour: {end_hour}. Use HH:MM format.[/red]")
        raise typer.Exit(code=1)

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
        typer.echo(
            json.dumps(
                {
                    "campaign_id": campaign_id,
                    "timezone": timezone,
                    "days": days_list,
                    "start_hour": start_hour,
                    "end_hour": end_hour,
                },
                indent=2,
            )
        )
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
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Add email accounts to a campaign."""
    try:
        client = get_client()
        client.add_email_accounts_to_campaign(campaign_id, account_id)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(
            json.dumps(
                {
                    "campaign_id": campaign_id,
                    "added": account_id,
                },
                indent=2,
            )
        )
        return

    console.print(
        f"\n[green]\u2713[/green] Added {len(account_id)} email account(s) to campaign {campaign_id}.\n"
    )


# ── Lead Push ────────────────────────────────────────────────

PUSH_BATCH_SIZE = 400  # Smartlead API limit


def _map_contact_to_lead(contact: dict) -> dict:
    """Map a contact row to a Smartlead lead dict.

    Known fields map via CONTACT_TO_SMARTLEAD.
    Remaining non-internal fields go into custom_fields
    so they're available as template variables in sequences.
    """
    lead: dict = {}
    mapped_crm_fields = set(CONTACT_TO_SMARTLEAD.keys())

    for crm_field, sl_field in CONTACT_TO_SMARTLEAD.items():
        val = contact.get(crm_field)
        if val is not None and val != "":
            lead[sl_field] = val

    # add unmapped fields as custom_fields
    custom: dict = {}
    for key, val in contact.items():
        if key in mapped_crm_fields or key in INTERNAL_FIELDS:
            continue
        if val is not None and val != "":
            custom[key] = str(val)

    if custom:
        lead["custom_fields"] = custom

    return lead


def _load_contacts(
    skill: str,
    segment: str | None,
    tag: str | None,
    list_name: str | None,
    lifecycle: str | None,
    status: str | None,
) -> list[dict]:
    """Load contacts from a skill's DB via the attach layer.

    Queries the skill's contacts table directly through
    db.connection(attach_skills=[skill]). No Python imports
    from the skill — only SQL via attached databases.
    """
    where: list[str] = []
    params: list = []

    if list_name:
        # query via list_members join
        sql = (
            f"SELECT c.* FROM {skill}.contacts c "
            f"JOIN {skill}.list_members lm ON lm.record_id = c.record_id "
            f"JOIN {skill}.lists l ON l.id = lm.list_id "
            f"WHERE l.name = ? "
            f"ORDER BY lm.added_at DESC"
        )
        params.append(list_name)
        with db.connection(attach_skills=[skill]) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    if segment:
        where.append("segment = ?")
        params.append(segment)

    if tag:
        where.append("(tags LIKE ? OR tags LIKE ? OR tags LIKE ? OR tags = ?)")
        params.extend([f"{tag},%", f"%,{tag},%", f"%,{tag}", tag])

    if lifecycle:
        where.append("lifecycle_stage = ?")
        params.append(lifecycle)

    if status:
        where.append("lead_status = ?")
        params.append(status)

    sql = f"SELECT * FROM {skill}.contacts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC"

    with db.connection(attach_skills=[skill]) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@app.command("push")
def push(
    campaign_id: int = typer.Argument(..., help="Smartlead campaign ID."),
    skill: str = typer.Option("crm", "--skill", help="Skill to read contacts from."),
    segment: Optional[str] = typer.Option(None, "--segment", help="Filter contacts by segment."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter contacts by tag."),
    list_name: Optional[str] = typer.Option(None, "--list", help="Push contacts from a named list."),
    lifecycle: Optional[str] = typer.Option(None, "--lifecycle", help="Filter by lifecycle stage."),
    lead_status: Optional[str] = typer.Option(None, "--status", help="Filter by lead status."),
    force: bool = typer.Option(False, "--force", help="Bypass dedup — push even if already pushed."),
    apply: bool = typer.Option(False, "--apply", help="Actually push. Default is dry run."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Push contacts to a Smartlead campaign.

    Default is dry run — shows what would be pushed. Use --apply to push.
    Contacts already pushed to this campaign are skipped (dedup by email).
    Use --force to bypass dedup and re-push all contacts.
    Reads contacts from the skill specified by --skill (default: crm).
    """
    # load contacts via db attach layer
    try:
        contacts = _load_contacts(skill, segment, tag, list_name, lifecycle, lead_status)
    except RuntimeError as e:
        rprint(f"[red]\u2717 {e}[/red]")
        raise typer.Exit(code=1)

    if not contacts:
        rprint("[yellow]No contacts match the given filters.[/yellow]")
        raise typer.Exit()

    # filter out contacts without email
    contacts_with_email = [c for c in contacts if c["email"]]
    skipped_no_email = len(contacts) - len(contacts_with_email)

    # dedup against already-pushed contacts (unless --force)
    if force:
        to_push = contacts_with_email
        skipped_dedup = 0
    else:
        already_pushed = queries.get_pushed_emails(campaign_id)
        already_pushed_lower = {e.lower() for e in already_pushed}
        to_push = [c for c in contacts_with_email if c["email"].lower() not in already_pushed_lower]
        skipped_dedup = len(contacts_with_email) - len(to_push)

    # summary
    summary = {
        "campaign_id": campaign_id,
        "total_contacts": len(contacts),
        "skipped_no_email": skipped_no_email,
        "skipped_already_pushed": skipped_dedup,
        "to_push": len(to_push),
        "dry_run": not apply,
    }

    if not apply:
        # dry run
        if output_json:
            typer.echo(json.dumps(summary, indent=2))
            return

        console.print(f"\n[bold]Dry run — push to campaign {campaign_id}[/bold]")
        console.print(f"  Total contacts matching filters: {len(contacts)}")
        if skipped_no_email:
            console.print(f"  Skipped (no email): {skipped_no_email}")
        if skipped_dedup:
            console.print(f"  Skipped (already pushed): {skipped_dedup}")
        console.print(f"  [bold]Would push: {len(to_push)}[/bold]")
        if to_push:
            console.print("\nRun with [bold]--apply[/bold] to push.")
        console.print()
        return

    if not to_push:
        rprint("[yellow]Nothing to push — all contacts already pushed or have no email.[/yellow]")
        raise typer.Exit()

    # push in batches
    try:
        client = get_client()
    except SmartleadError as e:
        _handle_api_error(e)

    pushed_count = 0
    batch_count = 0

    for i in range(0, len(to_push), PUSH_BATCH_SIZE):
        batch = to_push[i : i + PUSH_BATCH_SIZE]
        lead_list = [_map_contact_to_lead(dict(c)) for c in batch]

        try:
            client.add_leads_to_campaign(campaign_id, lead_list)
        except SmartleadError as e:
            rprint(
                f"[red]\u2717 Batch {batch_count + 1} failed: {e}[/red]\n"
                f"  Pushed {pushed_count} of {len(to_push)} before failure."
            )
            raise typer.Exit(code=1)

        # record each push locally
        for contact in batch:
            queries.record_push(
                record_id=contact["record_id"],
                campaign_id=campaign_id,
                email=contact["email"],
            )

        pushed_count += len(batch)
        batch_count += 1

        if not output_json:
            console.print(
                f"  Batch {batch_count}: pushed {len(batch)} leads ({pushed_count}/{len(to_push)})"
            )

    summary["pushed"] = pushed_count
    summary["batches"] = batch_count
    summary["dry_run"] = False

    if output_json:
        typer.echo(json.dumps(summary, indent=2))
        return

    console.print(
        f"\n[bold green]\u2713 Pushed {pushed_count} contacts to "
        f"campaign {campaign_id}[/bold green] "
        f"({batch_count} batch{'es' if batch_count != 1 else ''}).\n"
    )


# ── Campaign Control ─────────────────────────────────────────


@app.command("start")
def start(
    campaign_id: int = typer.Argument(..., help="Campaign ID to start."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Start a campaign (set status to ACTIVE)."""
    if not yes:
        confirm = typer.confirm(f"Start campaign {campaign_id}? This will begin sending emails.")
        if not confirm:
            raise typer.Abort()

    try:
        client = get_client()
        client.update_campaign_status(campaign_id, "START")
    except SmartleadError as e:
        _handle_api_error(e)

    console.print(f"\n[bold green]\u2713 Campaign {campaign_id} started.[/bold green]\n")


@app.command("pause")
def pause(
    campaign_id: int = typer.Argument(..., help="Campaign ID to pause."),
) -> None:
    """Pause a campaign."""
    try:
        client = get_client()
        client.update_campaign_status(campaign_id, "PAUSED")
    except SmartleadError as e:
        _handle_api_error(e)

    console.print(f"\n[yellow]\u23f8 Campaign {campaign_id} paused.[/yellow]\n")


@app.command("stop")
def stop(
    campaign_id: int = typer.Argument(..., help="Campaign ID to stop."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Stop a campaign. Stopped campaigns cannot be restarted."""
    if not yes:
        confirm = typer.confirm(f"Stop campaign {campaign_id}? Stopped campaigns cannot be restarted.")
        if not confirm:
            raise typer.Abort()

    try:
        client = get_client()
        client.update_campaign_status(campaign_id, "STOPPED")
    except SmartleadError as e:
        _handle_api_error(e)

    console.print(f"\n[red]\u23f9 Campaign {campaign_id} stopped.[/red]\n")


@app.command("monitor")
def monitor(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    limit: int = typer.Option(100, "--limit", help="Max leads to show."),
    offset: int = typer.Option(0, "--offset", help="Skip this many leads."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show lead-level engagement data for a campaign."""
    try:
        client = get_client()
        leads = client.get_campaign_leads(campaign_id, limit=limit, offset=offset)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps(leads, indent=2))
        return

    # API returns {"total_leads": N, "data": [...]} or a list
    total_leads = None
    if isinstance(leads, dict):
        total_leads = leads.get("total_leads")
        lead_entries = leads.get("data", [])
    elif isinstance(leads, list):
        lead_entries = leads
    else:
        lead_entries = []

    if not lead_entries:
        console.print(f"\n[dim]No leads in campaign {campaign_id}.[/dim]\n")
        return

    table = Table(title=f"Campaign {campaign_id} — Lead Activity")
    table.add_column("Email")
    table.add_column("Status")
    table.add_column("Sent", justify="right")
    table.add_column("Opened", justify="right")
    table.add_column("Clicked", justify="right")
    table.add_column("Replied", justify="right")

    for entry in lead_entries:
        # leads may be nested under "lead" key or flat
        lead = entry.get("lead", entry) if isinstance(entry, dict) else entry
        if not isinstance(lead, dict):
            continue

        email = lead.get("email", "")
        status = entry.get("status", lead.get("lead_status", ""))
        sent = lead.get("sent_count", lead.get("email_sent_count", 0)) or 0
        opened = lead.get("open_count", lead.get("email_open_count", 0)) or 0
        clicked = lead.get("click_count", lead.get("email_click_count", 0)) or 0
        replied = lead.get("reply_count", lead.get("email_reply_count", 0)) or 0

        table.add_row(
            email,
            str(status),
            str(sent),
            str(opened),
            str(clicked),
            str(replied),
        )

    console.print()
    console.print(table)
    shown = len(lead_entries)
    if total_leads:
        console.print(f"\n  Showing {shown} of {total_leads} leads.\n")
    elif shown == limit:
        console.print(
            f"\n  Showing {shown} leads (offset {offset}). Use --offset {offset + limit} to see more.\n"
        )
    else:
        console.print(f"\n  Showing {shown} leads.\n")


# ── Engagement Sync ──────────────────────────────────────────


@app.command("sync-touches")
def sync_touches(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    skill: str = typer.Option("crm", "--skill", help="Skill to write touches to."),
    apply: bool = typer.Option(False, "--apply", help="Actually create touches. Default is dry run."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Sync Smartlead engagement back as touches.

    Pulls lead-level stats from Smartlead for contacts that were pushed.
    Creates touch records for replied events via the db attach layer.
    No Python imports from other skills — writes directly via SQL.
    """
    # get local push records for this campaign
    pushes = queries.get_pushes_for_campaign(campaign_id)
    if not pushes:
        rprint(f"[yellow]No contacts pushed to campaign {campaign_id}.[/yellow]")
        raise typer.Exit()

    # fetch lead data from Smartlead
    try:
        client = get_client()
    except SmartleadError as e:
        _handle_api_error(e)

    # build email -> push mapping
    push_by_email = {p["email"].lower(): p for p in pushes}

    # fetch all leads from the campaign (paginated)
    all_leads: list[dict] = []
    offset = 0
    while True:
        try:
            batch = client.get_campaign_leads(campaign_id, offset=offset, limit=100)
        except SmartleadError as e:
            _handle_api_error(e)
        if not batch:
            break
        all_leads.extend(batch)
        if len(batch) < 100:
            break
        offset += 100

    # match leads to pushed contacts and find new touches
    touches_to_create: list[dict] = []
    updated_pushes: list[dict] = []

    for lead in all_leads:
        email = (lead.get("email") or "").lower()
        push = push_by_email.get(email)
        if not push:
            continue

        record_id = push["record_id"]
        reply_count = lead.get("reply_count", lead.get("email_reply_count", 0)) or 0
        old_reply_count = push["reply_count"] or 0

        # track engagement updates
        update = {
            "record_id": record_id,
            "campaign_id": campaign_id,
            "email": email,
            "sent_count": lead.get("sent_count", lead.get("email_sent_count", 0)) or 0,
            "open_count": lead.get("open_count", lead.get("email_open_count", 0)) or 0,
            "click_count": lead.get("click_count", lead.get("email_click_count", 0)) or 0,
            "reply_count": reply_count,
        }
        updated_pushes.append(update)

        # create touches for new replies
        if reply_count > old_reply_count:
            new_replies = reply_count - old_reply_count
            for _ in range(new_replies):
                touches_to_create.append(
                    {
                        "record_id": record_id,
                        "channel": "email",
                        "direction": "inbound",
                        "note": f"Reply via Smartlead campaign {campaign_id}",
                        "campaign_id": str(campaign_id),
                    }
                )

    summary = {
        "campaign_id": campaign_id,
        "leads_matched": len(updated_pushes),
        "new_touches": len(touches_to_create),
        "dry_run": not apply,
    }

    if not apply:
        if output_json:
            typer.echo(json.dumps(summary, indent=2))
            return

        console.print(f"\n[bold]Dry run — sync touches for campaign {campaign_id}[/bold]")
        console.print(f"  Leads matched: {len(updated_pushes)}")
        console.print(f"  New reply touches to create: {len(touches_to_create)}")
        if touches_to_create:
            console.print("\nRun with [bold]--apply[/bold] to create touches.")
        console.print()
        return

    # apply: update push records in smartlead.db
    conn = queries._connection()
    try:
        for update in updated_pushes:
            conn.execute(
                """
                UPDATE lead_pushes SET
                    sent_count = ?, open_count = ?, click_count = ?,
                    reply_count = ?, last_synced_at = datetime('now')
                WHERE record_id = ? AND campaign_id = ?
                """,
                (
                    update["sent_count"],
                    update["open_count"],
                    update["click_count"],
                    update["reply_count"],
                    update["record_id"],
                    update["campaign_id"],
                ),
            )
        conn.commit()
    finally:
        conn.close()

    # create touches via db attach layer — no skill Python imports
    with db.transaction(attach_skills=[skill]) as conn:
        for touch in touches_to_create:
            conn.execute(
                f"""
                INSERT INTO {skill}.touches
                    (record_id, channel, direction, note, campaign_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    touch["record_id"],
                    touch["channel"],
                    touch["direction"],
                    touch["note"],
                    touch["campaign_id"],
                ),
            )
            # update last_contacted_at on the contact
            conn.execute(
                f"""
                UPDATE {skill}.contacts
                SET last_contacted_at = datetime('now')
                WHERE record_id = ?
                """,
                (touch["record_id"],),
            )

    summary["dry_run"] = False

    if output_json:
        typer.echo(json.dumps(summary, indent=2))
        return

    console.print(f"\n[bold green]\u2713 Synced engagement for campaign {campaign_id}[/bold green]")
    console.print(f"  Updated {len(updated_pushes)} lead push records")
    console.print(f"  Created {len(touches_to_create)} touches in {skill}")
    console.print()


# ── Campaign Delete ──────────────────────────────────────────


@app.command("delete")
def delete(
    campaign_id: int = typer.Argument(..., help="Campaign ID to delete."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete a campaign from Smartlead."""
    if not yes:
        confirm = typer.confirm(f"Delete campaign {campaign_id}? This cannot be undone.")
        if not confirm:
            raise typer.Abort()

    try:
        client = get_client()
        client.delete_campaign(campaign_id)
    except SmartleadError as e:
        _handle_api_error(e)

    console.print(f"\n[green]\u2713[/green] Campaign {campaign_id} deleted.\n")


# ── Accounts Remove ─────────────────────────────────────────


@accounts_app.command("remove")
def accounts_remove(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    account_id: int = typer.Option(..., "--account-id", help="Email account ID to remove."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Remove an email account from a campaign."""
    try:
        client = get_client()
        client.remove_email_account_from_campaign(campaign_id, account_id)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(
            json.dumps(
                {
                    "campaign_id": campaign_id,
                    "removed": account_id,
                },
                indent=2,
            )
        )
        return

    console.print(
        f"\n[green]\u2713[/green] Removed email account {account_id} from campaign {campaign_id}.\n"
    )


# ── Lead Lookup ──────────────────────────────────────────────

lead_app = typer.Typer(
    help="Lead operations.",
    no_args_is_help=True,
)
app.add_typer(lead_app, name="lead")


@lead_app.command("find")
def lead_find(
    email: str = typer.Argument(..., help="Email address to search for."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Look up a lead by email address."""
    try:
        client = get_client()
        data = client.get_lead_by_email(email)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps(data, indent=2))
        return

    if not data:
        console.print(f"\n[dim]No lead found for {email}.[/dim]\n")
        return

    console.print(f"\n[bold]Lead: {email}[/bold]")
    if isinstance(data, dict):
        for key in ["id", "first_name", "last_name", "company_name", "status"]:
            val = data.get(key)
            if val is not None:
                console.print(f"  {key}: {val}")
    elif isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                lead_id = entry.get("id", "?")
                campaign = entry.get("campaign_name", entry.get("campaign_id", "?"))
                status = entry.get("lead_status", entry.get("status", "?"))
                console.print(f"  ID: {lead_id}, Campaign: {campaign}, Status: {status}")
    console.print()


@lead_app.command("thread")
def lead_thread(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    lead_id: int = typer.Argument(..., help="Lead ID."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """View email thread history for a lead in a campaign."""
    try:
        client = get_client()
        data = client.get_lead_message_history(campaign_id, lead_id)
    except SmartleadError as e:
        _handle_api_error(e)

    if output_json:
        typer.echo(json.dumps(data, indent=2))
        return

    if not data:
        console.print("\n[dim]No messages found.[/dim]\n")
        return

    messages = data if isinstance(data, list) else [data]
    console.print(f"\n[bold]Thread: campaign {campaign_id}, lead {lead_id}[/bold]\n")
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        direction = msg.get("type", msg.get("direction", "?"))
        subject = msg.get("subject", "")
        time_str = msg.get("time", msg.get("sent_at", msg.get("created_at", "")))
        console.print(f"  [{direction}] {time_str}")
        if subject:
            console.print(f"    Subject: {subject}")
        body = msg.get("email_body", msg.get("body", ""))
        if body:
            # show first 200 chars of body
            preview = body[:200].replace("\n", " ")
            if len(body) > 200:
                preview += "..."
            console.print(f"    {preview}")
        console.print()


@lead_app.command("pause")
def lead_pause(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    lead_id: int = typer.Argument(..., help="Lead ID."),
) -> None:
    """Pause a lead in a campaign."""
    try:
        client = get_client()
        client.update_lead_status(campaign_id, lead_id, "pause")
    except SmartleadError as e:
        _handle_api_error(e)

    console.print(f"\n[yellow]\u23f8 Lead {lead_id} paused in campaign {campaign_id}.[/yellow]\n")


@lead_app.command("resume")
def lead_resume(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    lead_id: int = typer.Argument(..., help="Lead ID."),
) -> None:
    """Resume a paused lead in a campaign."""
    try:
        client = get_client()
        client.update_lead_status(campaign_id, lead_id, "resume")
    except SmartleadError as e:
        _handle_api_error(e)

    console.print(f"\n[green]\u2713[/green] Lead {lead_id} resumed in campaign {campaign_id}.\n")


@lead_app.command("unsubscribe")
def lead_unsubscribe(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    lead_id: int = typer.Argument(..., help="Lead ID."),
) -> None:
    """Unsubscribe a lead from a campaign."""
    try:
        client = get_client()
        client.update_lead_status(campaign_id, lead_id, "unsubscribe")
    except SmartleadError as e:
        _handle_api_error(e)

    console.print(f"\n[green]\u2713[/green] Lead {lead_id} unsubscribed from campaign {campaign_id}.\n")


# ── Export ───────────────────────────────────────────────────


@app.command("export")
def export(
    campaign_id: int = typer.Argument(..., help="Campaign ID."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Export all leads from a campaign as CSV."""
    try:
        client = get_client()
        csv_text = client.export_campaign_leads(campaign_id)
    except SmartleadError as e:
        _handle_api_error(e)

    typer.echo(csv_text)


# ── Date-Range Stats ─────────────────────────────────────────
# Extend the existing stats command with --start-date / --end-date

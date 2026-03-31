from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from openkiln.skills.crm import queries

app = typer.Typer(
    name="crm",
    help="CRM skill — list, tag, stats, and touch logging.",
    no_args_is_help=True,
)

list_app = typer.Typer(
    help="List contacts or companies.",
    no_args_is_help=True,
)
app.add_typer(list_app, name="list")

touch_app = typer.Typer(
    help="Touch logging.",
    no_args_is_help=True,
)
app.add_typer(touch_app, name="touch")

console = Console()


# ── list contacts ─────────────────────────────────────────────

@list_app.command("contacts")
def list_contacts(
    segment: Optional[str] = typer.Option(
        None, "--segment", help="Filter by segment."
    ),
    tag: Optional[str] = typer.Option(
        None, "--tag", help="Filter by tag."
    ),
    not_contacted_since: Optional[int] = typer.Option(
        None, "--not-contacted-since",
        help="Only contacts not touched in this many days."
    ),
    limit: int = typer.Option(50, "--limit", help="Max rows to show."),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """List contacts with optional filters."""
    rows = queries.list_contacts(
        segment=segment,
        tag=tag,
        not_contacted_since=not_contacted_since,
        limit=limit,
    )
    total = queries.count_contacts(
        segment=segment,
        tag=tag,
        not_contacted_since=not_contacted_since,
    )

    if output_json:
        typer.echo(json.dumps({
            "total": total,
            "showing": len(rows),
            "contacts": [dict(r) for r in rows],
        }))
        return

    # build filter description
    filters = []
    if segment:
        filters.append(f"segment={segment}")
    if tag:
        filters.append(f"tag={tag}")
    if not_contacted_since:
        filters.append(f"not contacted in {not_contacted_since}d")

    filter_str = "  Filters: " + ", ".join(filters) if filters else ""

    console.print(
        f"\n[bold]Contacts[/bold] — "
        f"{total:,} total (showing {len(rows)})"
        f"{filter_str}\n"
    )

    if not rows:
        console.print("[dim]No contacts match your filters.[/dim]\n")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID",         width=6)
    table.add_column("Name",       width=22)
    table.add_column("Email",      width=28)
    table.add_column("Segment",    width=22)
    table.add_column("Tags",       width=20)
    table.add_column("Last contact", width=14)

    for row in rows:
        table.add_row(
            str(row["record_id"]),
            row["full_name"] or f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "—",
            row["email"] or "—",
            row["segment"] or "—",
            row["tags"] or "—",
            (row["last_contacted_at"] or "never")[:10],
        )

    console.print(table)
    if total > limit:
        console.print(
            f"\n[dim]Showing {limit} of {total:,}. "
            f"Use --limit to see more.[/dim]"
        )
    console.print()


# ── list companies ────────────────────────────────────────────

@list_app.command("companies")
def list_companies(
    segment: Optional[str] = typer.Option(
        None, "--segment", help="Filter by segment."
    ),
    tag: Optional[str] = typer.Option(
        None, "--tag", help="Filter by tag."
    ),
    limit: int = typer.Option(50, "--limit", help="Max rows to show."),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """List companies with optional filters."""
    rows = queries.list_companies(
        segment=segment,
        tag=tag,
        limit=limit,
    )

    if output_json:
        typer.echo(json.dumps({
            "showing": len(rows),
            "companies": [dict(r) for r in rows],
        }))
        return

    console.print(f"\n[bold]Companies[/bold] — showing {len(rows)}\n")

    if not rows:
        console.print("[dim]No companies match your filters.[/dim]\n")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID",       width=6)
    table.add_column("Name",     width=25)
    table.add_column("Domain",   width=25)
    table.add_column("Segment",  width=20)
    table.add_column("Tags",     width=20)

    for row in rows:
        table.add_row(
            str(row["record_id"]),
            row["name"] or "—",
            row["domain"] or "—",
            row["segment"] or "—",
            row["tags"] or "—",
        )

    console.print(table)
    console.print()


# ── tag ───────────────────────────────────────────────────────

@app.command("tag")
def tag(
    entity: str = typer.Argument(
        ..., help="Entity type to tag: contacts or companies."
    ),
    set_segment: Optional[str] = typer.Option(
        None, "--set-segment", help="Set segment on matching records."
    ),
    add_tag: Optional[str] = typer.Option(
        None, "--add-tag", help="Add a tag to matching records."
    ),
    remove_tag: Optional[str] = typer.Option(
        None, "--remove-tag", help="Remove a tag from matching records."
    ),
    filter_segment: Optional[str] = typer.Option(
        None, "--segment", help="Only update records with this segment."
    ),
    filter_tag: Optional[str] = typer.Option(
        None, "--tag", help="Only update records with this tag."
    ),
    ids: Optional[str] = typer.Option(
        None, "--ids",
        help="Comma-separated record IDs to update e.g. 1,2,3."
    ),
    email: Optional[str] = typer.Option(
        None, "--email", help="Update record with this email."
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply",
        help="Preview without writing (default)."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Apply segment or tag updates to contacts or companies."""
    if entity not in ("contacts", "companies"):
        rprint(
            f"[red]✗ Unknown entity '{entity}'. "
            f"Use: contacts or companies[/red]"
        )
        raise typer.Exit(code=1)

    if not any([set_segment, add_tag, remove_tag]):
        rprint(
            "[red]✗ No update action specified.[/red]\n\n"
            "  To update contacts, specify what to change:\n"
            "    --set-segment 'value'   set the segment field\n"
            "    --add-tag 'value'       add a tag\n"
            "    --remove-tag 'value'    remove a tag\n\n"
            "  Note: --segment and --tag are filter flags — they select\n"
            "  which contacts to update, not what to update them to.\n\n"
            "  Example:\n"
            "    openkiln crm tag contacts \\\n"
            "      --set-segment 'cold-email-agencies' --apply\n\n"
            "    openkiln crm tag contacts \\\n"
            "      --segment 'old-segment' \\\n"
            "      --set-segment 'new-segment' --apply"
        )
        raise typer.Exit(code=1)

    record_id_list = None
    if ids:
        try:
            record_id_list = [int(i.strip()) for i in ids.split(",")]
        except ValueError:
            rprint("[red]✗ --ids must be comma-separated integers[/red]")
            raise typer.Exit(code=1)

    if dry_run:
        # count what would be affected
        count = queries.count_contacts(
            segment=filter_segment,
            tag=filter_tag,
        ) if entity == "contacts" else 0

        if output_json:
            typer.echo(json.dumps({
                "dry_run": True,
                "entity": entity,
                "would_affect": count,
                "set_segment": set_segment,
                "add_tag": add_tag,
                "remove_tag": remove_tag,
            }))
            return

        console.print(
            f"\n[yellow]DRY RUN[/yellow] — "
            f"would update {count:,} {entity}\n"
            f"Run with [bold]--apply[/bold] to write.\n"
        )
        return

    affected = queries.tag_contacts(
        set_segment=set_segment,
        add_tag=add_tag,
        remove_tag=remove_tag,
        filter_segment=filter_segment,
        filter_tag=filter_tag,
        record_ids=record_id_list,
        email=email,
    )

    if output_json:
        typer.echo(json.dumps({
            "dry_run": False,
            "entity": entity,
            "updated": affected,
            "set_segment": set_segment,
            "add_tag": add_tag,
            "remove_tag": remove_tag,
        }))
        return

    console.print(f"\n[green]✓[/green] Updated {affected:,} {entity}\n")


# ── stats ─────────────────────────────────────────────────────

@app.command("stats")
def stats(
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Show CRM summary statistics."""
    data = queries.get_stats()

    if output_json:
        typer.echo(json.dumps(data))
        return

    console.print("\n[bold]CRM Stats[/bold]")
    console.print("─" * 40)

    # contacts
    console.print(
        f"\n[bold]Contacts[/bold]   {data['contacts']['total']:,}"
    )
    for row in data["contacts"]["by_segment"]:
        console.print(
            f"  {row['segment']:<30} {row['count']:>6,}"
        )

    # companies
    console.print(
        f"\n[bold]Companies[/bold]  {data['companies']['total']:,}"
    )
    for row in data["companies"]["by_segment"]:
        console.print(
            f"  {row['segment']:<30} {row['count']:>6,}"
        )

    # touches
    console.print(
        f"\n[bold]Touches[/bold]    {data['touches']['total']:,}"
    )

    console.print()


# ── touch log ─────────────────────────────────────────────────

@touch_app.command("log")
def touch_log(
    record_id: int = typer.Option(
        ..., "--record-id", help="Record ID to log touch against."
    ),
    channel: str = typer.Option(
        "email", "--channel",
        help="Channel: email, linkedin, phone, in_person, other."
    ),
    direction: str = typer.Option(
        "outbound", "--direction",
        help="Direction: outbound or inbound."
    ),
    note: Optional[str] = typer.Option(
        None, "--note", help="Optional note about the interaction."
    ),
    campaign_id: Optional[str] = typer.Option(
        None, "--campaign-id", help="Campaign ID if applicable."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON."
    ),
) -> None:
    """Log a touch (interaction) against a contact or company."""
    touch_id = queries.log_touch(
        record_id=record_id,
        channel=channel,
        direction=direction,
        note=note,
        campaign_id=campaign_id,
    )

    if output_json:
        typer.echo(json.dumps({
            "touch_id": touch_id,
            "record_id": record_id,
            "channel": channel,
            "direction": direction,
        }))
        return

    console.print(
        f"\n[green]✓[/green] Touch logged "
        f"(id={touch_id}, record={record_id}, "
        f"channel={channel})\n"
    )

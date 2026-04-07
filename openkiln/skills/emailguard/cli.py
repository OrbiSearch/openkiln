from __future__ import annotations

import json

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from openkiln.skills.emailguard import queries
from openkiln.skills.emailguard.api import EmailGuardError, get_client

app = typer.Typer(
    name="emailguard",
    help="EmailGuard — inbox placement testing.",
    no_args_is_help=True,
)

console = Console()


def _handle_api_error(e: EmailGuardError) -> None:
    rprint(f"[red]\u2717 {e}[/red]")
    raise typer.Exit(code=1)


# ── Create ───────────────────────────────────────────────────


@app.command("create")
def create(
    name: str = typer.Option(..., "--name", help="Test name."),
    gmail_seeds: int = typer.Option(4, "--gmail-seeds", help="Number of Gmail seed addresses."),
    msft_seeds: int = typer.Option(4, "--msft-seeds", help="Number of Microsoft seed addresses."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Create a new inbox placement test."""
    try:
        client = get_client()
        test = client.create_test(name, gmail_seeds=gmail_seeds, msft_seeds=msft_seeds)
    except EmailGuardError as e:
        _handle_api_error(e)

    # store locally
    queries.upsert_test(test)
    seeds = test.get("inbox_placement_test_emails", [])
    queries.upsert_seed_results(test["uuid"], seeds)

    if output_json:
        typer.echo(
            json.dumps(
                {
                    "test_id": test["uuid"],
                    "name": test.get("name"),
                    "filter_phrase": test.get("filter_phrase"),
                    "seeds": [{"email": s["email"], "provider": s["provider"]} for s in seeds],
                },
                indent=2,
            )
        )
        return

    console.print(f"\n[green]\u2713[/green] Placement test created: [bold]{name}[/bold]")
    console.print(f"  Test ID:        {test['uuid']}")
    console.print(f"  Filter phrase:  [cyan]{test.get('filter_phrase')}[/cyan]")
    console.print(f"\n  [bold]Seeds ({len(seeds)}):[/bold]")

    for seed in seeds:
        provider = seed.get("provider", "?")
        tag = "[blue]G[/blue]" if provider == "Google" else "[cyan]M[/cyan]"
        console.print(f"    {tag}  {seed['email']}")

    console.print(
        "\n  [dim]Append the filter phrase to your email body, then send "
        "to all seed addresses via your outreach skill.[/dim]\n"
    )


# ── Check ────────────────────────────────────────────────────


@app.command("check")
def check(
    test_id: str = typer.Argument(..., help="Test UUID."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Check results of a placement test."""
    try:
        client = get_client()
        test = client.get_test(test_id)
    except EmailGuardError as e:
        _handle_api_error(e)

    # store results locally
    queries.upsert_test(test)
    seeds = test.get("inbox_placement_test_emails", [])
    queries.upsert_seed_results(test_id, seeds)

    # aggregate per sender
    by_sender: dict[str, dict] = {}
    for seed in seeds:
        sender = seed.get("sender_email_account_address") or "unknown"
        if sender not in by_sender:
            by_sender[sender] = {
                "inbox": 0,
                "spam": 0,
                "waiting": 0,
                "gmail_inbox": 0,
                "gmail_spam": 0,
                "msft_inbox": 0,
                "msft_spam": 0,
            }
        s = by_sender[sender]
        folder = seed.get("folder")
        provider = seed.get("provider", "")
        if seed.get("status") == "waiting_for_email":
            s["waiting"] += 1
        elif folder == "Inbox":
            s["inbox"] += 1
            if provider == "Google":
                s["gmail_inbox"] += 1
            else:
                s["msft_inbox"] += 1
        elif folder in ("Spam", "Junk"):
            s["spam"] += 1
            if provider == "Google":
                s["gmail_spam"] += 1
            else:
                s["msft_spam"] += 1

    # store account scores
    for account_email, stats in by_sender.items():
        if account_email != "unknown":
            queries.upsert_account_score(test_id, account_email, stats)

    if output_json:
        typer.echo(
            json.dumps(
                {
                    "test_id": test_id,
                    "status": test.get("status"),
                    "overall_score": test.get("overall_score"),
                    "by_sender": by_sender,
                },
                indent=2,
            )
        )
        return

    status = test.get("status", "unknown")
    score = test.get("overall_score")
    status_style = "green" if status == "completed" else "yellow"

    console.print(f"\n  Test: [bold]{test.get('name', test_id)}[/bold]")
    console.print(f"  Status: [{status_style}]{status}[/{status_style}]")
    if score is not None:
        console.print(f"  Overall score: [bold]{score}[/bold]")

    # per-seed table
    table = Table(title="Seed Results")
    table.add_column("Seed")
    table.add_column("Provider")
    table.add_column("Sender")
    table.add_column("Folder")

    for seed in seeds:
        folder = seed.get("folder") or seed.get("status", "waiting")
        if folder == "Inbox":
            folder_style = "green"
        elif folder in ("Spam", "Junk"):
            folder_style = "red"
        else:
            folder_style = "yellow"
        table.add_row(
            seed.get("email", ""),
            seed.get("provider", ""),
            seed.get("sender_email_account_address") or "—",
            f"[{folder_style}]{folder}[/{folder_style}]",
        )

    console.print()
    console.print(table)
    console.print()


# ── Report ───────────────────────────────────────────────────


@app.command("report")
def report(
    test_id: str = typer.Argument(..., help="Test UUID."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Generate a formatted placement test report."""
    test = queries.get_test(test_id)
    if not test:
        rprint(f"[red]\u2717 Test not found locally: {test_id}[/red]")
        rprint("[dim]Run: openkiln emailguard check <test_id>[/dim]")
        raise typer.Exit(code=1)

    seeds = queries.get_seed_results(test_id)
    scores = queries.get_account_scores(test_id)

    if output_json:
        typer.echo(
            json.dumps(
                {
                    "test_id": test_id,
                    "name": test["name"],
                    "status": test["status"],
                    "overall_score": test["overall_score"],
                    "seeds": [dict(s) for s in seeds],
                    "account_scores": [dict(s) for s in scores],
                },
                indent=2,
            )
        )
        return

    console.print("\n[bold]Placement Test Report[/bold]")
    console.print(f"  Name:    {test['name']}")
    console.print(f"  Status:  {test['status']}")
    if test["overall_score"] is not None:
        console.print(f"  Score:   [bold]{test['overall_score']}[/bold]")
    console.print(f"  Created: {test['created_at']}")

    # provider breakdown
    by_provider: dict[str, dict] = {}
    for seed in seeds:
        p = seed["provider"]
        if p not in by_provider:
            by_provider[p] = {"inbox": 0, "spam": 0, "waiting": 0}
        if seed["status"] == "waiting_for_email":
            by_provider[p]["waiting"] += 1
        elif seed["folder"] == "Inbox":
            by_provider[p]["inbox"] += 1
        elif seed["folder"] in ("Spam", "Junk"):
            by_provider[p]["spam"] += 1

    if by_provider:
        console.print("\n[bold]  By Provider:[/bold]")
        for provider, counts in sorted(by_provider.items()):
            total = counts["inbox"] + counts["spam"]
            rate = f"{counts['inbox'] / total * 100:.0f}%" if total > 0 else "—"
            console.print(
                f"    {provider:<12} Inbox: {counts['inbox']}  Spam: {counts['spam']}  ({rate})"
            )

    # account breakdown
    if scores:
        console.print("\n[bold]  By Account:[/bold]")
        for score in scores:
            rate = f"{score['inbox_rate'] * 100:.0f}%" if score["inbox_rate"] is not None else "—"
            console.print(
                f"    {score['account_email']:<35} "
                f"Inbox: {score['inbox_count']}  "
                f"Spam: {score['spam_count']}  "
                f"({rate})"
            )

    console.print()


# ── List ─────────────────────────────────────────────────────


@app.command("list")
def list_tests(
    limit: int = typer.Option(20, "--limit", help="Max tests to show."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List past placement tests."""
    tests = queries.list_tests(limit=limit)

    if output_json:
        typer.echo(json.dumps([dict(t) for t in tests], indent=2))
        return

    if not tests:
        console.print("\n[dim]No placement tests found.[/dim]")
        console.print('[dim]Run: openkiln emailguard create --name "My Test"[/dim]\n')
        return

    table = Table(title="Placement Tests")
    table.add_column("UUID", style="cyan", max_width=20)
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Score", justify="right")
    table.add_column("Created")

    for t in tests:
        status = t["status"]
        style = "green" if status == "completed" else "yellow"
        score = str(t["overall_score"]) if t["overall_score"] is not None else "—"
        table.add_row(
            t["test_uuid"][:20] + "...",
            t["name"],
            f"[{style}]{status}[/{style}]",
            score,
            str(t["created_at"])[:19],
        )

    console.print()
    console.print(table)
    console.print()

from __future__ import annotations

import csv
import json
from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console

from openkiln.skills.cleanco import queries
from openkiln.skills.cleanco.api import CleancoError, get_client

app = typer.Typer(
    name="cleanco",
    help="Cleanco -- clean company names for outreach.",
    no_args_is_help=True,
)

console = Console()

BATCH_SIZE = 50


def _handle_api_error(e: CleancoError) -> None:
    """Print an API error and exit."""
    rprint(f"[red]\u2717 {e}[/red]")
    raise typer.Exit(code=1)


@app.command("clean")
def clean(
    file: Path = typer.Argument(
        ...,
        help="CSV file to clean.",
        exists=True,
        readable=True,
    ),
    column: str = typer.Option(
        "company_name",
        "--column",
        "-c",
        help="Column name containing company names.",
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path. Defaults to <input>-cleaned.csv.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Actually write the output file. Default is dry run.",
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Clean company names in a CSV file.

    Reads the CSV, cleans the specified column using OpenAI,
    and writes the result. Uses a local cache to avoid re-cleaning
    names already processed.
    """
    with open(file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if column not in (reader.fieldnames or []):
            rprint(f"[red]\u2717 Column '{column}' not found in {file}[/red]")
            rprint(f"  Available columns: {', '.join(reader.fieldnames or [])}")
            raise typer.Exit(code=1)
        rows = list(reader)
        fieldnames = reader.fieldnames

    # Collect unique names
    all_names = list(dict.fromkeys(r[column].strip() for r in rows if r.get(column, "").strip()))

    # Check cache
    cached = queries.get_cached(all_names)
    uncached = [n for n in all_names if n not in cached]

    console.print(f"  Total rows:     {len(rows):>6}")
    console.print(f"  Unique names:   {len(all_names):>6}")
    console.print(f"  Cached:         {len(cached):>6}")
    console.print(f"  To clean:       {len(uncached):>6}")

    if not apply:
        console.print("\n  [yellow]Dry run.[/yellow] Use --apply to clean and write output.")
        if output_json:
            typer.echo(
                json.dumps(
                    {
                        "rows": len(rows),
                        "unique_names": len(all_names),
                        "cached": len(cached),
                        "to_clean": len(uncached),
                    },
                    indent=2,
                )
            )
        return

    # Clean uncached names via API
    new_mappings: dict[str, str] = {}
    if uncached:
        try:
            client = get_client()
        except CleancoError as e:
            _handle_api_error(e)

        for i in range(0, len(uncached), BATCH_SIZE):
            batch = uncached[i : i + BATCH_SIZE]
            try:
                cleaned = client.clean_batch(batch)
            except CleancoError as e:
                _handle_api_error(e)
            for orig, clean in zip(batch, cleaned):
                new_mappings[orig] = clean
            console.print(f"  Cleaned {min(i + BATCH_SIZE, len(uncached))}/{len(uncached)}...")

        queries.cache_results(new_mappings)

    # Merge all mappings
    all_mappings = {**cached, **new_mappings}

    # Apply to rows
    changed = 0
    for row in rows:
        name = row.get(column, "").strip()
        if name and name in all_mappings and all_mappings[name] != name:
            row[column] = all_mappings[name]
            changed += 1

    # Write output
    out_path = output or file.with_stem(f"{file.stem}-cleaned")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    console.print(f"\n  [green]\u2713[/green] Cleaned {changed} names")
    console.print(f"  Output: {out_path}")

    if output_json:
        typer.echo(
            json.dumps(
                {
                    "rows": len(rows),
                    "cleaned": changed,
                    "unchanged": len(rows) - changed,
                    "output": str(out_path),
                },
                indent=2,
            )
        )


@app.command("cache")
def cache_stats(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show cache statistics."""
    import sqlite3

    from openkiln import config

    db_path = config.get().skill_db_path("cleanco")
    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM cleaned_names").fetchone()[0]
        changed = conn.execute(
            "SELECT COUNT(*) FROM cleaned_names WHERE original != cleaned"
        ).fetchone()[0]
    finally:
        conn.close()

    if output_json:
        typer.echo(json.dumps({"cached": count, "changed": changed}, indent=2))
        return

    console.print(f"  Cached names:   {count}")
    console.print(f"  Were changed:   {changed}")
    console.print(f"  Unchanged:      {count - changed}")


@app.command("show")
def show_changes(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of entries."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show cached name changes (where original differs from cleaned)."""
    import sqlite3

    from openkiln import config

    db_path = config.get().skill_db_path("cleanco")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT original, cleaned FROM cleaned_names "
            "WHERE original != cleaned ORDER BY cleaned_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    if output_json:
        typer.echo(
            json.dumps(
                [{"original": r["original"], "cleaned": r["cleaned"]} for r in rows],
                indent=2,
            )
        )
        return

    if not rows:
        console.print("  No changes recorded.")
        return

    for row in rows:
        console.print(f'  "{row["original"]}" [dim]\u2192[/dim] "{row["cleaned"]}"')

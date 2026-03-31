from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from openkiln import config, db

app = typer.Typer(
    name="record",
    help="Record operations — inspect, import, list, clean.",
    no_args_is_help=True,
)

console = Console()

# number of rows to sample for type inference in inspect
INSPECT_SAMPLE_ROWS = 3


@app.command("inspect")
def inspect(
    file: Path = typer.Argument(
        ..., help="Path to CSV file.", exists=True
    ),
    skill: str = typer.Option(
        None, "--skill", help="Show column mapping for this skill."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON for agent consumption."
    ),
) -> None:
    """
    Preview a CSV file before importing.
    Shows columns, row count, and sample values.
    Use --skill to see which columns match the skill schema.
    """
    # read csv
    with open(file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        csv_columns = reader.fieldnames or []
        rows = []
        for row in reader:
            rows.append(row)

    total_rows = len(rows)
    sample = rows[:INSPECT_SAMPLE_ROWS]

    # infer simple types from sample values
    def infer_type(col: str) -> str:
        values = [r.get(col, "") for r in sample if r.get(col)]
        for v in values:
            try:
                float(v)
                return "number"
            except (ValueError, TypeError):
                pass
        return "text"

    columns_info = [
        {
            "name": col,
            "type": infer_type(col),
            "example": next(
                (r[col] for r in sample if r.get(col)), ""
            ),
        }
        for col in csv_columns
    ]

    # skill mapping if requested
    skill_mapping = None
    if skill:
        skill_columns = _get_skill_columns(skill)
        if skill_columns is None:
            rprint(f"[red]✗ Unknown skill: {skill}[/red]")
            raise typer.Exit(code=1)

        csv_col_set = {c.lower() for c in csv_columns}
        skill_col_set = {c.lower() for c in skill_columns}

        matched = [
            c for c in csv_columns
            if c.lower() in skill_col_set
        ]
        skipped = [
            c for c in csv_columns
            if c.lower() not in skill_col_set
        ]
        skill_mapping = {
            "skill": skill,
            "matched": matched,
            "skipped": skipped,
        }

    if output_json:
        typer.echo(json.dumps({
            "file": str(file),
            "total_rows": total_rows,
            "columns": columns_info,
            "skill_mapping": skill_mapping,
        }))
        return

    # human output
    console.print(f"\n[bold]File:[/bold] {file}")
    console.print(f"[bold]Rows:[/bold] {total_rows:,}\n")

    console.print("[bold]Columns detected:[/bold]")
    for col in columns_info:
        console.print(
            f"  {col['name']:<25} {col['type']:<8} "
            f"[dim]e.g. \"{col['example']}\"[/dim]"
        )

    if skill_mapping:
        console.print(f"\n[bold]Column mapping for --skill {skill}:[/bold]")

        if skill_mapping["matched"]:
            console.print("\n  [green]Matched (will import):[/green]")
            for col in skill_mapping["matched"]:
                console.print(f"    [green]✓[/green]  {col}")

        if skill_mapping["skipped"]:
            console.print("\n  [yellow]Skipped (not in skill schema):[/yellow]")
            for col in skill_mapping["skipped"]:
                console.print(f"    [yellow]○[/yellow]  {col}")

        console.print(
            f"\n  Ready to import:\n"
            f"  [bold]openkiln record import {file} "
            f"--type contact --skill {skill}[/bold]"
        )

    elif skill is None:
        console.print(
            f"\n[dim]Run with --skill <name> to see column mapping.[/dim]"
        )

    console.print()


@app.command("import")
def import_records(
    file: Path = typer.Argument(
        ..., help="Path to CSV file.", exists=True
    ),
    type_: str = typer.Option(
        ..., "--type", help="Record type (e.g. contact, company)."
    ),
    skill: str = typer.Option(
        None, "--skill",
        help="Skill to write record data to (e.g. crm)."
    ),
    map_columns: Optional[list[str]] = typer.Option(
        None, "--map",
        help=(
            "Map a CSV column to a schema column. "
            "Format: 'CSVColumn=schema_column'. "
            "Use multiple --map flags for multiple mappings. "
            "Example: --map 'Title=job_title' --map 'linkedin_profile=linkedin_url'"
        ),
    ),
    upsert: bool = typer.Option(
        False, "--upsert",
        help=(
            "Update existing records on dedup key match instead of skipping. "
            "Without --upsert, duplicate records are skipped. "
            "With --upsert, existing records are updated with new field values."
        ),
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply",
        help="Preview import without writing data (default)."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON for agent consumption."
    ),
) -> None:
    """
    Import records from a CSV file.

    Always runs as --dry-run by default.
    Pass --apply to write data.

    Use --skill to write record data to a skill database.
    Without --skill, only bare records are created in core.db.
    """
    if not db.check_connection():
        rprint(
            "[red]✗ Database not found.[/red]\n"
            "Run [bold]openkiln init[/bold] first."
        )
        raise typer.Exit(code=1)

    # validate skill if provided
    skill_columns = None
    dedup_key = None
    if skill:
        skill_columns = _get_skill_columns(skill, type_)
        if skill_columns is None:
            rprint(
                f"[red]✗ Skill '{skill}' does not support "
                f"type '{type_}'.[/red]"
            )
            raise typer.Exit(code=1)

        dedup_key = _get_dedup_key(skill, type_)

        # check skill is installed
        with db.connection() as conn:
            row = conn.execute(
                "SELECT skill_name FROM installed_skills "
                "WHERE skill_name = ?",
                (skill,)
            ).fetchone()
        if not row:
            rprint(
                f"[red]✗ Skill '{skill}' is not installed.[/red]\n"
                f"Run: openkiln skill install {skill}"
            )
            raise typer.Exit(code=1)

    # read csv
    with open(file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        csv_columns = [c for c in (reader.fieldnames or [])]
        all_rows = list(reader)

    total_rows = len(all_rows)

    # parse --map flags into a lookup: csv_col_lower -> schema_col
    explicit_mappings: dict[str, str] = {}
    if map_columns:
        for mapping in map_columns:
            if "=" not in mapping:
                rprint(
                    f"[red]✗ Invalid --map format: '{mapping}'\n"
                    f"  Expected: --map 'CSVColumn=schema_column'[/red]"
                )
                raise typer.Exit(code=1)
            src, dst = mapping.split("=", 1)
            src = src.strip()
            dst = dst.strip()
            # validate target column exists in skill schema
            if skill_columns and dst.lower() not in {
                c.lower() for c in skill_columns
            }:
                rprint(
                    f"[red]✗ --map target '{dst}' is not a valid column "
                    f"for skill '{skill}'.\n"
                    f"  Run: openkiln skill info {skill} "
                    f"to see valid columns.[/red]"
                )
                raise typer.Exit(code=1)
            explicit_mappings[src.lower()] = dst

    # build reverse mapping: schema_col_lower -> csv_col_name
    # so we can look up the CSV column for the dedup key
    reverse_mappings: dict[str, str] = {
        dst.lower(): src for src, dst in (
            (m.split("=", 1)[0].strip(), m.split("=", 1)[1].strip())
            for m in (map_columns or [])
            if "=" in m
        )
    }

    # resolve the CSV column name for the dedup key
    # e.g. if dedup_key is "domain" and --map "website=domain",
    # we need to look up "website" in the CSV row, not "domain"
    dedup_csv_col = dedup_key
    if dedup_key and dedup_key.lower() in reverse_mappings:
        dedup_csv_col = reverse_mappings[dedup_key.lower()]
    elif dedup_key:
        # find the original CSV column name (case-insensitive match)
        for col in csv_columns:
            if col.lower() == dedup_key.lower():
                dedup_csv_col = col
                break

    # identify column mapping
    unknown_columns: list[str] = []
    matched_columns: list[str] = []

    if skill_columns:
        skill_col_lower = {c.lower(): c for c in skill_columns}
        for col in csv_columns:
            # check explicit mapping first, then exact match
            if col.lower() in explicit_mappings:
                matched_columns.append(col)
            elif col.lower() in skill_col_lower:
                matched_columns.append(col)
            else:
                unknown_columns.append(col)
    else:
        matched_columns = csv_columns

    if dry_run:
        # dry run — count what would happen, touch nothing
        imported = 0
        skipped_dupes = 0

        if dedup_key:
            # get existing dedup values from skill db
            existing = _get_existing_dedup_values(skill, type_, dedup_key)
            for row in all_rows:
                val = row.get(dedup_csv_col, "").strip().lower()
                if val and val in existing:
                    skipped_dupes += 1
                else:
                    imported += 1
        else:
            imported = total_rows

        _print_import_result(
            dry_run=True,
            file=file,
            type_=type_,
            skill=skill,
            total=total_rows,
            imported=imported,
            skipped_dupes=skipped_dupes,
            unknown_columns=unknown_columns,
            explicit_mappings=explicit_mappings,
            output_json=output_json,
            upsert=upsert,
        )
        return

    # apply — write data
    imported = 0
    skipped_dupes = 0

    existing = set()
    if dedup_key:
        existing = _get_existing_dedup_values(skill, type_, dedup_key)

    attach = [skill] if skill else None

    with db.transaction(attach_skills=attach) as conn:
        for batch_start in range(0, total_rows, db.BATCH_SIZE):
            batch = all_rows[batch_start:batch_start + db.BATCH_SIZE]

            for row in batch:
                # dedup check
                if dedup_key:
                    val = row.get(dedup_csv_col, "").strip().lower()
                    if val and val in existing:
                        if not upsert:
                            skipped_dupes += 1
                            continue
                        # upsert — update existing record
                        if skill and skill_columns:
                            skill_col_lower = {
                                c.lower(): c for c in skill_columns
                            }
                            table = _skill_table_name(skill, type_)
                            fields = {}
                            for csv_col in matched_columns:
                                schema_col = (
                                    explicit_mappings.get(csv_col.lower())
                                    or skill_col_lower.get(csv_col.lower())
                                )
                                if schema_col and schema_col != dedup_key:
                                    field_val = (
                                        row.get(csv_col, "").strip() or None
                                    )
                                    fields[schema_col] = field_val

                            if fields:
                                set_clause = ", ".join(
                                    f"{k} = ?" for k in fields.keys()
                                )
                                conn.execute(
                                    f"UPDATE {skill}.{table} "
                                    f"SET {set_clause} "
                                    f"WHERE {dedup_key} = ?",
                                    list(fields.values()) + [val],
                                )
                        imported += 1
                        continue
                    if val:
                        existing.add(val)

                # insert core record
                cursor = conn.execute(
                    "INSERT INTO records (type) VALUES (?)",
                    (type_,)
                )
                record_id = cursor.lastrowid

                # insert skill record if skill provided
                if skill and skill_columns:
                    skill_col_lower = {
                        c.lower(): c for c in skill_columns
                    }
                    table = _skill_table_name(skill, type_)
                    fields = {"record_id": record_id}

                    for csv_col in matched_columns:
                        # explicit mapping takes precedence
                        schema_col = (
                            explicit_mappings.get(csv_col.lower())
                            or skill_col_lower.get(csv_col.lower())
                        )
                        if schema_col:
                            field_val = (
                                row.get(csv_col, "").strip() or None
                            )
                            fields[schema_col] = field_val

                    cols = ", ".join(fields.keys())
                    placeholders = ", ".join(["?"] * len(fields))
                    conn.execute(
                        f"INSERT INTO {skill}.{table} "
                        f"({cols}) VALUES ({placeholders})",
                        list(fields.values()),
                    )

                imported += 1

    _print_import_result(
        dry_run=False,
        file=file,
        type_=type_,
        skill=skill,
        total=total_rows,
        imported=imported,
        skipped_dupes=skipped_dupes,
        unknown_columns=unknown_columns,
        explicit_mappings=explicit_mappings,
        output_json=output_json,
        upsert=upsert,
    )


# ── Internal helpers ──────────────────────────────────────────

def _get_skill_columns(
    skill_name: str,
    type_: str | None = None
) -> list[str] | None:
    """
    Returns the list of known columns for a skill and optional type.
    Returns None if skill is unknown or type is unsupported.
    """
    try:
        import importlib
        mod = importlib.import_module(f"openkiln.skills.{skill_name}")
    except ImportError:
        return None

    if type_ is None:
        # return all columns for inspect (no type filter)
        cols: list[str] = []
        for attr in dir(mod):
            if attr.endswith("_COLUMNS"):
                cols.extend(getattr(mod, attr, []))
        return cols or None

    # map type to column list attribute
    type_map = {
        "contact":  "CONTACT_COLUMNS",
        "company":  "COMPANY_COLUMNS",
    }
    attr = type_map.get(type_)
    if not attr:
        return None
    return getattr(mod, attr, None)


def _get_dedup_key(skill_name: str, type_: str) -> str | None:
    """Returns the dedup key for a skill and record type."""
    try:
        import importlib
        mod = importlib.import_module(f"openkiln.skills.{skill_name}")
        return getattr(mod, "DEDUP_KEYS", {}).get(type_)
    except ImportError:
        return None


def _get_existing_dedup_values(
    skill_name: str,
    type_: str,
    dedup_key: str,
) -> set[str]:
    """
    Returns a set of existing dedup key values from the skill db.
    Used to skip duplicate rows during import.
    """
    table = _skill_table_name(skill_name, type_)
    cfg = config.get()
    db_path = cfg.skill_db_path(skill_name)

    if not db_path.exists():
        return set()

    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            f"SELECT {dedup_key} FROM {table} "
            f"WHERE {dedup_key} IS NOT NULL"
        ).fetchall()
        return {row[0].strip().lower() for row in rows if row[0]}
    except Exception:
        return set()
    finally:
        conn.close()


def _skill_table_name(skill_name: str, type_: str) -> str:
    """Returns the skill db table name for a given record type."""
    table_map = {
        ("crm", "contact"):  "contacts",
        ("crm", "company"):  "companies",
    }
    return table_map.get((skill_name, type_), type_ + "s")


def _print_import_result(
    *,
    dry_run: bool,
    file: Path,
    type_: str,
    skill: str | None,
    total: int,
    imported: int,
    skipped_dupes: int,
    unknown_columns: list[str],
    explicit_mappings: dict[str, str],
    output_json: bool,
    upsert: bool = False,
) -> None:
    """Prints import results in human or JSON format."""
    if output_json:
        typer.echo(json.dumps({
            "dry_run": dry_run,
            "file": str(file),
            "type": type_,
            "skill": skill,
            "total": total,
            "imported": imported,
            "skipped_duplicates": skipped_dupes,
            "skipped_unknown_columns": unknown_columns,
            "column_mappings": explicit_mappings,
        }))
        return

    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]APPLIED[/green]"
    console.print(f"\n{mode} — {file}\n")
    console.print(f"  Total rows:      {total:>8,}")
    console.print(f"  [green]Imported:[/green]        {imported:>8,}")

    if skipped_dupes:
        label = (
            "  [yellow]Skipped (dupes):[/yellow]"
            if not upsert
            else "  [green]Updated (upsert):[/green]"
        )
        console.print(f"{label} {skipped_dupes:>8,}")

    if explicit_mappings:
        console.print(
            f"\n  [green]Column mappings applied:[/green]"
        )
        for src, dst in explicit_mappings.items():
            console.print(f"    ✓  {src} → {dst}")

    if unknown_columns:
        console.print(
            f"\n  [yellow]Skipped columns "
            f"(not in {skill} schema):[/yellow]"
        )
        for col in unknown_columns:
            console.print(f"    ○  {col}")
        console.print(
            f"\n  [dim]Tip: use --map 'ColumnName=schema_field' "
            f"to import skipped columns.[/dim]"
        )

    if dry_run:
        console.print(
            f"\n  Run with [bold]--apply[/bold] to write data."
        )

    console.print()

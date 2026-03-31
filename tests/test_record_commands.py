import csv
import json
from pathlib import Path
from typer.testing import CliRunner
from openkiln.cli import app
from openkiln import db

runner = CliRunner()


def _make_csv(tmp_path: Path, rows: list[dict]) -> Path:
    """Helper: write a CSV file to tmp_path."""
    f = tmp_path / "test.csv"
    if not rows:
        f.write_text("")
        return f
    with open(f, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return f


def _setup(runner, openkiln_home):
    """Helper: init + install crm."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])


# ── inspect tests ─────────────────────────────────────────────

def test_inspect_shows_columns(openkiln_home, tmp_path):
    """record inspect shows column names and row count."""
    f = _make_csv(tmp_path, [
        {"first_name": "John", "last_name": "Smith",
         "email": "john@acme.com"},
        {"first_name": "Jane", "last_name": "Doe",
         "email": "jane@corp.com"},
    ])
    result = runner.invoke(app, ["record", "inspect", str(f)])
    assert result.exit_code == 0
    assert "first_name" in result.output
    assert "email" in result.output
    assert "2" in result.output


def test_inspect_with_skill_shows_mapping(openkiln_home, tmp_path):
    """record inspect --skill crm shows matched and skipped columns."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com", "unknown_col": "value"},
    ])
    result = runner.invoke(
        app, ["record", "inspect", str(f), "--skill", "crm"]
    )
    assert result.exit_code == 0
    assert "email" in result.output
    assert "unknown_col" in result.output


def test_inspect_json(openkiln_home, tmp_path):
    """record inspect --json returns valid JSON."""
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com", "first_name": "John"},
    ])
    result = runner.invoke(
        app, ["record", "inspect", str(f), "--json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_rows"] == 1
    assert any(c["name"] == "email" for c in data["columns"])


# ── import tests ──────────────────────────────────────────────

def test_import_dry_run_touches_nothing(openkiln_home, tmp_path):
    """record import --dry-run does not write to database."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com", "first_name": "John"},
    ])
    runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--dry-run"],
    )
    with db.connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM records"
        ).fetchone()[0]
    assert count == 0


def test_import_apply_creates_records(openkiln_home, tmp_path):
    """record import --apply creates records in core.db."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com", "first_name": "John"},
        {"email": "jane@corp.com", "first_name": "Jane"},
    ])
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--apply"],
    )
    assert result.exit_code == 0
    with db.connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM records WHERE type = 'contact'"
        ).fetchone()[0]
    assert count == 2


def test_import_apply_creates_skill_records(openkiln_home, tmp_path):
    """record import --apply writes contact data to crm.db."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com", "first_name": "John",
         "last_name": "Smith"},
    ])
    runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--apply"],
    )
    cfg_path = openkiln_home / "skills" / "crm.db"
    import sqlite3
    conn = sqlite3.connect(cfg_path)
    row = conn.execute(
        "SELECT first_name, last_name FROM contacts WHERE email = ?",
        ("john@acme.com",)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "John"
    assert row[1] == "Smith"


def test_import_skips_duplicates(openkiln_home, tmp_path):
    """record import skips rows with duplicate dedup key."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com", "first_name": "John"},
    ])
    runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--apply"],
    )
    # import same file again
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--apply"],
    )
    assert result.exit_code == 0
    assert "dupe" in result.output.lower() or "skip" in result.output.lower()

    with db.connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM records WHERE type = 'contact'"
        ).fetchone()[0]
    assert count == 1  # still only one record


def test_import_reports_unknown_columns(openkiln_home, tmp_path):
    """record import reports columns not in skill schema."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com", "mystery_field": "value"},
    ])
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--apply"],
    )
    assert result.exit_code == 0
    assert "mystery_field" in result.output


def test_import_without_skill_creates_bare_records(
    openkiln_home, tmp_path
):
    """record import without --skill creates bare records in core only."""
    runner.invoke(app, ["init"])
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com"},
    ])
    result = runner.invoke(
        app,
        ["record", "import", str(f),
         "--type", "contact", "--apply"],
    )
    assert result.exit_code == 0
    with db.connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM records WHERE type = 'contact'"
        ).fetchone()[0]
    assert count == 1


def test_import_json_output(openkiln_home, tmp_path):
    """record import --json returns valid JSON."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com"},
    ])
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--apply", "--json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["imported"] == 1
    assert data["dry_run"] is False


def test_import_fails_if_skill_not_installed(openkiln_home, tmp_path):
    """record import fails clearly if required skill is not installed."""
    runner.invoke(app, ["init"])
    # do NOT install crm
    f = _make_csv(tmp_path, [{"email": "john@acme.com"}])
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--apply"],
    )
    assert result.exit_code == 1
    assert "not installed" in result.output.lower()


def test_import_map_remaps_columns(openkiln_home, tmp_path):
    """--map remaps non-standard CSV columns to schema columns."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"Title": "CEO", "EmailAddress": "john@acme.com",
         "FullName": "John Smith"},
    ])
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm",
         "--map", "Title=job_title",
         "--map", "EmailAddress=email",
         "--map", "FullName=full_name",
         "--apply"],
    )
    assert result.exit_code == 0

    import sqlite3
    conn = sqlite3.connect(openkiln_home / "skills" / "crm.db")
    row = conn.execute(
        "SELECT job_title, email, full_name FROM contacts LIMIT 1"
    ).fetchone()
    conn.close()
    assert row[0] == "CEO"
    assert row[1] == "john@acme.com"
    assert row[2] == "John Smith"


def test_import_map_invalid_format_fails(openkiln_home, tmp_path):
    """--map with invalid format fails with clear error."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [{"email": "a@b.com"}])
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--map", "invalid-no-equals",
         "--apply"],
    )
    assert result.exit_code == 1
    assert "Invalid --map format" in result.output


def test_import_map_invalid_target_fails(openkiln_home, tmp_path):
    """--map with unknown target column fails with clear error."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [{"email": "a@b.com"}])
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--map", "email=nonexistent_column",
         "--apply"],
    )
    assert result.exit_code == 1
    assert "not a valid column" in result.output


def test_import_map_shows_in_dry_run(openkiln_home, tmp_path):
    """--map mappings are reported in dry-run output."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [{"Title": "CEO", "email": "a@b.com"}])
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--map", "Title=job_title",
         "--dry-run"],
    )
    assert result.exit_code == 0
    assert "title" in result.output.lower()
    assert "job_title" in result.output.lower()


def test_import_dry_run_suggests_map_for_skipped_columns(
    openkiln_home, tmp_path
):
    """Dry-run output suggests --map for skipped columns."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"email": "a@b.com", "mystery_col": "value"}
    ])
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "--map" in result.output


def test_import_upsert_updates_existing_records(openkiln_home, tmp_path):
    """--upsert updates existing records instead of skipping."""
    _setup(runner, openkiln_home)

    # initial import
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com", "first_name": "John"},
    ])
    runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--apply"],
    )

    # reimport with new data using upsert
    f2 = _make_csv(tmp_path, [
        {"email": "john@acme.com", "first_name": "Jonathan",
         "job_title": "CEO"},
    ])
    tmp_path2 = tmp_path / "v2"
    tmp_path2.mkdir(exist_ok=True)
    f2 = tmp_path2 / "contacts.csv"
    import csv as csv_mod
    with open(f2, "w", newline="") as fh:
        writer = csv_mod.DictWriter(
            fh,
            fieldnames=["email", "first_name", "job_title"]
        )
        writer.writeheader()
        writer.writerow({
            "email": "john@acme.com",
            "first_name": "Jonathan",
            "job_title": "CEO",
        })

    result = runner.invoke(
        app,
        ["record", "import", str(f2), "--type", "contact",
         "--skill", "crm", "--upsert", "--apply"],
    )
    assert result.exit_code == 0

    import sqlite3
    conn = sqlite3.connect(openkiln_home / "skills" / "crm.db")
    row = conn.execute(
        "SELECT first_name, job_title FROM contacts "
        "WHERE email = 'john@acme.com'"
    ).fetchone()
    conn.close()

    assert row[0] == "Jonathan"
    assert row[1] == "CEO"

    # only one record should exist
    with db.connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM records WHERE type = 'contact'"
        ).fetchone()[0]
    assert count == 1


def test_import_without_upsert_skips_duplicates(openkiln_home, tmp_path):
    """Without --upsert duplicates are still skipped."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"email": "john@acme.com", "first_name": "John"},
    ])
    runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--apply"],
    )
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "contact",
         "--skill", "crm", "--apply"],
    )
    assert result.exit_code == 0
    assert "skip" in result.output.lower() or "dupe" in result.output.lower()


def test_import_map_dedup_uses_mapped_column(openkiln_home, tmp_path):
    """--map with dedup key uses the mapped CSV column for dedup check."""
    _setup(runner, openkiln_home)

    # first import: website column mapped to domain
    f = _make_csv(tmp_path, [
        {"website": "acme.com", "name": "Acme Corp"},
    ])
    runner.invoke(
        app,
        ["record", "import", str(f), "--type", "company",
         "--skill", "crm", "--map", "website=domain",
         "--map", "name=name", "--apply"],
    )

    # second import: same website — should be skipped as dupe
    result = runner.invoke(
        app,
        ["record", "import", str(f), "--type", "company",
         "--skill", "crm", "--map", "website=domain",
         "--map", "name=name", "--apply"],
    )
    assert result.exit_code == 0

    import sqlite3
    conn = sqlite3.connect(openkiln_home / "skills" / "crm.db")
    count = conn.execute(
        "SELECT COUNT(*) FROM companies WHERE domain = 'acme.com'"
    ).fetchone()[0]
    conn.close()
    assert count == 1  # not duplicated


def test_domain_normalised_on_import(openkiln_home, tmp_path):
    """Domain field is normalised on import."""
    _setup(runner, openkiln_home)
    f = _make_csv(tmp_path, [
        {"domain": "https://www.acme.com/about",
         "name": "Acme Corp"},
        {"domain": "http://corp.io/",
         "name": "Corp"},
        {"domain": "www.example.com",
         "name": "Example"},
        {"domain": "clean.com",
         "name": "Clean"},
    ])
    runner.invoke(
        app,
        ["record", "import", str(f), "--type", "company",
         "--skill", "crm", "--apply"],
    )

    import sqlite3
    conn = sqlite3.connect(openkiln_home / "skills" / "crm.db")
    domains = {
        row[0] for row in conn.execute(
            "SELECT domain FROM companies"
        ).fetchall()
    }
    conn.close()

    assert "acme.com" in domains
    assert "corp.io" in domains
    assert "example.com" in domains
    assert "clean.com" in domains
    # none should have protocol or www
    assert not any(d.startswith("http") for d in domains)
    assert not any(d.startswith("www.") for d in domains)


def test_normalise_domain_helper():
    """_normalise_domain handles all common cases."""
    from openkiln.commands.record import _normalise_domain
    assert _normalise_domain("https://www.acme.com/about") == "acme.com"
    assert _normalise_domain("http://acme.com") == "acme.com"
    assert _normalise_domain("www.acme.com") == "acme.com"
    assert _normalise_domain("acme.com/") == "acme.com"
    assert _normalise_domain("acme.com") == "acme.com"
    assert _normalise_domain("") == ""

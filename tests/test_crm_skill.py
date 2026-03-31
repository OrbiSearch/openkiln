from __future__ import annotations

import sqlite3
from typer.testing import CliRunner
from openkiln.cli import app
from openkiln.skills.crm import queries

runner = CliRunner()


def _setup(runner, openkiln_home):
    """Helper: init + install crm + mount skill CLI."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])
    # mount CRM CLI so crm subcommands are available
    from openkiln.cli import _mount_skill_clis
    _mount_skill_clis()


def _insert_contact(openkiln_home, **kwargs) -> int:
    """Helper: insert a contact directly into crm.db."""
    # insert bare record in core first
    from openkiln import db
    with db.transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO records (type) VALUES ('contact')"
        )
        record_id = cursor.lastrowid

    # insert contact in crm.db
    crm_db = openkiln_home / "skills" / "crm.db"
    conn = sqlite3.connect(crm_db)
    fields = {"record_id": record_id}
    fields.update(kwargs)
    cols = ", ".join(fields.keys())
    placeholders = ", ".join(["?"] * len(fields))
    conn.execute(
        f"INSERT INTO contacts ({cols}) VALUES ({placeholders})",
        list(fields.values())
    )
    conn.commit()
    conn.close()
    return record_id


# ── schema migration tests ────────────────────────────────────

def test_crm_schema_has_touches_table(openkiln_home):
    """CRM schema migration 002 creates touches table."""
    _setup(runner, openkiln_home)
    crm_db = openkiln_home / "skills" / "crm.db"
    conn = sqlite3.connect(crm_db)
    tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert "touches" in tables


def test_crm_contacts_has_last_contacted_at(openkiln_home):
    """CRM contacts table has last_contacted_at column."""
    _setup(runner, openkiln_home)
    crm_db = openkiln_home / "skills" / "crm.db"
    conn = sqlite3.connect(crm_db)
    cols = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(contacts)"
        ).fetchall()
    }
    conn.close()
    assert "last_contacted_at" in cols


# ── query tests ───────────────────────────────────────────────

def test_list_contacts_returns_all(openkiln_home):
    """list_contacts returns all contacts when no filters."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com", segment="seg1")
    _insert_contact(openkiln_home, email="b@b.com", segment="seg2")
    rows = queries.list_contacts()
    assert len(rows) == 2


def test_list_contacts_filters_by_segment(openkiln_home):
    """list_contacts filters correctly by segment."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com", segment="cold-email")
    _insert_contact(openkiln_home, email="b@b.com", segment="gtm-tools")
    rows = queries.list_contacts(segment="cold-email")
    assert len(rows) == 1
    assert rows[0]["email"] == "a@a.com"


def test_list_contacts_filters_by_tag(openkiln_home):
    """list_contacts filters correctly by tag."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com", tags="priority,hot")
    _insert_contact(openkiln_home, email="b@b.com", tags="cold")
    rows = queries.list_contacts(tag="priority")
    assert len(rows) == 1
    assert rows[0]["email"] == "a@a.com"


def test_list_contacts_not_contacted_since(openkiln_home):
    """list_contacts filters by not contacted since N days."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com",
                    last_contacted_at=None)
    _insert_contact(openkiln_home, email="b@b.com",
                    last_contacted_at="2099-01-01")
    rows = queries.list_contacts(not_contacted_since=30)
    assert len(rows) == 1
    assert rows[0]["email"] == "a@a.com"


def test_tag_contacts_set_segment(openkiln_home):
    """tag_contacts sets segment on matching records."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com", segment="old")
    affected = queries.tag_contacts(set_segment="new-seg",
                                    filter_segment="old")
    assert affected == 1
    rows = queries.list_contacts(segment="new-seg")
    assert len(rows) == 1


def test_tag_contacts_add_tag(openkiln_home):
    """tag_contacts adds a tag without removing existing tags."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com", tags="existing")
    queries.tag_contacts(add_tag="new-tag", email="a@a.com")
    rows = queries.list_contacts()
    tags = rows[0]["tags"]
    assert "existing" in tags
    assert "new-tag" in tags


def test_tag_contacts_remove_tag(openkiln_home):
    """tag_contacts removes a specific tag."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com",
                    tags="keep,remove-me")
    queries.tag_contacts(remove_tag="remove-me", email="a@a.com")
    rows = queries.list_contacts()
    assert "remove-me" not in (rows[0]["tags"] or "")
    assert "keep" in (rows[0]["tags"] or "")


def test_log_touch_creates_touch_and_updates_contacted_at(openkiln_home):
    """log_touch creates a touch row and updates last_contacted_at."""
    _setup(runner, openkiln_home)
    record_id = _insert_contact(openkiln_home, email="a@a.com")
    touch_id = queries.log_touch(record_id=record_id, channel="email")
    assert touch_id is not None

    crm_db = openkiln_home / "skills" / "crm.db"
    conn = sqlite3.connect(crm_db)
    touch = conn.execute(
        "SELECT * FROM touches WHERE id = ?", (touch_id,)
    ).fetchone()
    contact = conn.execute(
        "SELECT last_contacted_at FROM contacts WHERE record_id = ?",
        (record_id,)
    ).fetchone()
    conn.close()

    assert touch is not None
    assert contact[0] is not None


def test_get_stats_returns_correct_counts(openkiln_home):
    """get_stats returns correct contact and touch counts."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com", segment="seg1")
    _insert_contact(openkiln_home, email="b@b.com", segment="seg1")
    _insert_contact(openkiln_home, email="c@c.com", segment="seg2")
    stats = queries.get_stats()
    assert stats["contacts"]["total"] == 3
    segs = {r["segment"]: r["count"]
            for r in stats["contacts"]["by_segment"]}
    assert segs["seg1"] == 2
    assert segs["seg2"] == 1


# ── CLI command tests ─────────────────────────────────────────

def test_crm_list_contacts_command(openkiln_home):
    """openkiln crm list contacts runs without error."""
    _setup(runner, openkiln_home)
    result = runner.invoke(app, ["crm", "list", "contacts"])
    assert result.exit_code == 0


def test_crm_list_contacts_with_segment_filter(openkiln_home):
    """openkiln crm list contacts --segment filters results."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com",
                    segment="cold-email")
    result = runner.invoke(
        app, ["crm", "list", "contacts", "--segment", "cold-email"]
    )
    assert result.exit_code == 0
    assert "a@a.com" in result.output


def test_crm_stats_command(openkiln_home):
    """openkiln crm stats runs without error."""
    _setup(runner, openkiln_home)
    result = runner.invoke(app, ["crm", "stats"])
    assert result.exit_code == 0
    assert "Contacts" in result.output


def test_crm_tag_dry_run(openkiln_home):
    """openkiln crm tag contacts --dry-run does not write."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com", segment="old")
    runner.invoke(
        app,
        ["crm", "tag", "contacts",
         "--segment", "old", "--set-segment", "new", "--dry-run"]
    )
    rows = queries.list_contacts(segment="old")
    assert len(rows) == 1  # unchanged


def test_crm_tag_apply(openkiln_home):
    """openkiln crm tag contacts --apply writes changes."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com", segment="old")
    result = runner.invoke(
        app,
        ["crm", "tag", "contacts",
         "--segment", "old", "--set-segment", "new", "--apply"]
    )
    assert result.exit_code == 0
    rows = queries.list_contacts(segment="new")
    assert len(rows) == 1


def test_crm_touch_log_command(openkiln_home):
    """openkiln crm touch log creates a touch."""
    _setup(runner, openkiln_home)
    record_id = _insert_contact(openkiln_home, email="a@a.com")
    result = runner.invoke(
        app,
        ["crm", "touch", "log",
         "--record-id", str(record_id), "--channel", "email"]
    )
    assert result.exit_code == 0
    assert "Touch logged" in result.output


def test_crm_list_contacts_json(openkiln_home):
    """openkiln crm list contacts --json returns valid JSON."""
    import json
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com")
    result = runner.invoke(
        app, ["crm", "list", "contacts", "--json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "contacts" in data
    assert data["total"] == 1


def test_tag_contacts_missing_action_gives_clear_error(openkiln_home):
    """tag contacts with no action gives clear error explaining --segment vs --set-segment."""
    _setup(runner, openkiln_home)
    result = runner.invoke(
        app,
        ["crm", "tag", "contacts", "--segment", "something"]
    )
    assert result.exit_code == 1
    assert "--set-segment" in result.output
    assert "filter" in result.output.lower()


def test_crm_reset_dry_run(openkiln_home):
    """openkiln crm reset contacts --dry-run does not delete."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com")
    result = runner.invoke(
        app, ["crm", "reset", "contacts", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "dry run" in result.output.lower()
    rows = queries.list_contacts()
    assert len(rows) == 1  # not deleted


def test_crm_reset_apply_deletes_contacts(openkiln_home):
    """openkiln crm reset contacts --apply deletes all contacts."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="a@a.com")
    _insert_contact(openkiln_home, email="b@b.com")
    result = runner.invoke(
        app, ["crm", "reset", "contacts", "--apply"]
    )
    assert result.exit_code == 0
    rows = queries.list_contacts()
    assert len(rows) == 0


def test_crm_reset_unknown_entity_fails(openkiln_home):
    """openkiln crm reset with unknown entity fails clearly."""
    _setup(runner, openkiln_home)
    result = runner.invoke(
        app, ["crm", "reset", "invoices", "--apply"]
    )
    assert result.exit_code == 1
    assert "Unknown entity" in result.output


def _insert_company(openkiln_home, **kwargs) -> int:
    """Helper: insert a company directly into crm.db."""
    from openkiln import db
    with db.transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO records (type) VALUES ('company')"
        )
        record_id = cursor.lastrowid

    crm_db = openkiln_home / "skills" / "crm.db"
    conn = sqlite3.connect(crm_db)
    fields = {"record_id": record_id}
    fields.update(kwargs)
    cols = ", ".join(fields.keys())
    placeholders = ", ".join(["?"] * len(fields))
    conn.execute(
        f"INSERT INTO companies ({cols}) VALUES ({placeholders})",
        list(fields.values())
    )
    conn.commit()
    conn.close()
    return record_id


def test_link_contacts_by_email_domain(openkiln_home):
    """link_contacts_to_companies matches email domain to company domain."""
    _setup(runner, openkiln_home)
    contact_id = _insert_contact(
        openkiln_home, email="john@acme.com"
    )
    company_id = _insert_company(
        openkiln_home, name="Acme Corp", domain="acme.com"
    )

    result = queries.link_contacts_to_companies(
        contact_field="email_domain",
        company_field="domain",
        dry_run=False,
    )

    assert result["matched"] == 1
    assert result["unmatched"] == 0

    crm_db = openkiln_home / "skills" / "crm.db"
    conn = sqlite3.connect(crm_db)
    row = conn.execute(
        "SELECT company_record_id FROM contacts WHERE record_id = ?",
        (contact_id,)
    ).fetchone()
    conn.close()
    assert row[0] == company_id


def test_link_contacts_dry_run_does_not_write(openkiln_home):
    """link_contacts_to_companies dry_run does not write links."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="john@acme.com")
    _insert_company(openkiln_home, domain="acme.com")

    queries.link_contacts_to_companies(
        contact_field="email_domain",
        company_field="domain",
        dry_run=True,
    )

    crm_db = openkiln_home / "skills" / "crm.db"
    conn = sqlite3.connect(crm_db)
    row = conn.execute(
        "SELECT company_record_id FROM contacts LIMIT 1"
    ).fetchone()
    conn.close()
    assert row[0] is None  # not written


def test_link_contacts_skips_already_linked(openkiln_home):
    """link_contacts_to_companies skips contacts already linked."""
    _setup(runner, openkiln_home)
    company_id = _insert_company(
        openkiln_home, domain="acme.com"
    )
    _insert_contact(
        openkiln_home,
        email="john@acme.com",
        company_record_id=company_id
    )
    _insert_company(openkiln_home, domain="other.com")
    _insert_contact(openkiln_home, email="jane@other.com")

    result = queries.link_contacts_to_companies(
        contact_field="email_domain",
        company_field="domain",
        dry_run=False,
        overwrite=False,
    )

    assert result["skipped"] == 1
    assert result["matched"] == 1


def test_link_contacts_overwrite(openkiln_home):
    """link_contacts_to_companies overwrites existing links when requested."""
    _setup(runner, openkiln_home)
    old_company_id = _insert_company(
        openkiln_home, domain="old.com"
    )
    new_company_id = _insert_company(
        openkiln_home, domain="acme.com"
    )
    contact_id = _insert_contact(
        openkiln_home,
        email="john@acme.com",
        company_record_id=old_company_id
    )

    result = queries.link_contacts_to_companies(
        contact_field="email_domain",
        company_field="domain",
        dry_run=False,
        overwrite=True,
    )

    assert result["matched"] == 1

    crm_db = openkiln_home / "skills" / "crm.db"
    conn = sqlite3.connect(crm_db)
    row = conn.execute(
        "SELECT company_record_id FROM contacts WHERE record_id = ?",
        (contact_id,)
    ).fetchone()
    conn.close()
    assert row[0] == new_company_id


def test_link_contact_manually(openkiln_home):
    """link_contact_to_company manually links a contact to a company."""
    _setup(runner, openkiln_home)
    contact_id = _insert_contact(openkiln_home, email="a@a.com")
    company_id = _insert_company(openkiln_home, domain="a.com")

    success = queries.link_contact_to_company(
        contact_record_id=contact_id,
        company_record_id=company_id,
    )
    assert success is True

    crm_db = openkiln_home / "skills" / "crm.db"
    conn = sqlite3.connect(crm_db)
    row = conn.execute(
        "SELECT company_record_id FROM contacts WHERE record_id = ?",
        (contact_id,)
    ).fetchone()
    conn.close()
    assert row[0] == company_id


def test_crm_link_contacts_command_dry_run(openkiln_home):
    """openkiln crm link contacts --dry-run reports without writing."""
    _setup(runner, openkiln_home)
    _insert_contact(openkiln_home, email="john@acme.com")
    _insert_company(openkiln_home, domain="acme.com")

    result = runner.invoke(
        app, ["crm", "link", "contacts", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "1" in result.output


def test_crm_link_contacts_command_apply(openkiln_home):
    """openkiln crm link contacts --apply writes links."""
    _setup(runner, openkiln_home)
    contact_id = _insert_contact(openkiln_home, email="john@acme.com")
    _insert_company(openkiln_home, domain="acme.com")

    result = runner.invoke(
        app, ["crm", "link", "contacts", "--apply"]
    )
    assert result.exit_code == 0

    crm_db = openkiln_home / "skills" / "crm.db"
    conn = sqlite3.connect(crm_db)
    row = conn.execute(
        "SELECT company_record_id FROM contacts WHERE record_id = ?",
        (contact_id,)
    ).fetchone()
    conn.close()
    assert row[0] is not None


def test_crm_link_contact_manual_command(openkiln_home):
    """openkiln crm link contact --contact-id --company-id works."""
    _setup(runner, openkiln_home)
    contact_id = _insert_contact(openkiln_home, email="a@a.com")
    company_id = _insert_company(openkiln_home, domain="a.com")

    result = runner.invoke(
        app,
        ["crm", "link", "contact",
         "--contact-id", str(contact_id),
         "--company-id", str(company_id)]
    )
    assert result.exit_code == 0
    assert "linked" in result.output.lower()

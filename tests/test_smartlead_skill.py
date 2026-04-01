"""
Tests for the Smartlead skill.

Covers: skill install, schema, field mapping, batch splitting,
queries, and provider sink.
"""
from __future__ import annotations

import json
import sqlite3

from typer.testing import CliRunner

from openkiln.cli import app
from openkiln import db

runner = CliRunner()


# ── Skill Install ────────────────────────────────────────────


def test_skill_list_shows_smartlead_available(openkiln_home):
    """smartlead appears in available skills after init."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 0
    assert "smartlead" in result.output


def test_skill_install_smartlead(openkiln_home):
    """skill install smartlead creates db and registers skill."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "install", "smartlead"])
    assert result.exit_code == 0
    assert (openkiln_home / "skills" / "smartlead.db").exists()

    with db.connection() as conn:
        row = conn.execute(
            "SELECT skill_name FROM installed_skills "
            "WHERE skill_name = 'smartlead'"
        ).fetchone()
    assert row is not None


def test_skill_install_creates_config_section(openkiln_home):
    """skill install smartlead appends config section."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "smartlead"])
    config_text = (openkiln_home / "config.toml").read_text()
    assert "[skills.smartlead]" in config_text
    assert "api_key" in config_text


def test_skill_info_smartlead(openkiln_home):
    """skill info smartlead prints SKILL.md content."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["skill", "info", "smartlead"])
    assert result.exit_code == 0
    assert "Smartlead Skill" in result.output
    assert "smartlead.push" in result.output


# ── Schema ───────────────────────────────────────────────────


def test_schema_creates_all_tables(openkiln_home):
    """smartlead.db has all expected tables after install."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "smartlead"])

    db_path = openkiln_home / "skills" / "smartlead.db"
    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()

    assert "campaigns" in tables
    assert "campaign_stats" in tables
    assert "lead_pushes" in tables
    assert "sequences" in tables


def test_lead_pushes_unique_constraint(openkiln_home):
    """lead_pushes enforces UNIQUE(record_id, campaign_id)."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "smartlead"])

    db_path = openkiln_home / "skills" / "smartlead.db"
    conn = sqlite3.connect(db_path)

    conn.execute(
        "INSERT INTO lead_pushes (record_id, campaign_id, email) "
        "VALUES (1, 100, 'a@example.com')"
    )
    conn.commit()

    # second insert with same record_id + campaign_id should
    # conflict (upsert handles this in production code)
    try:
        conn.execute(
            "INSERT INTO lead_pushes (record_id, campaign_id, email) "
            "VALUES (1, 100, 'a@example.com')"
        )
        conn.commit()
        assert False, "Expected UNIQUE constraint violation"
    except sqlite3.IntegrityError:
        pass

    conn.close()


# ── Field Mapping ────────────────────────────────────────────


def test_crm_to_smartlead_mapping():
    """CRM contact fields map correctly to Smartlead lead fields."""
    from openkiln.skills.smartlead.cli import _map_contact_to_lead

    contact = {
        "email": "jane@acme.com",
        "first_name": "Jane",
        "last_name": "Smith",
        "company_name": "Acme Corp",
        "phone": "+1-555-0100",
        "linkedin_url": "https://linkedin.com/in/janesmith",
        "city": "Boston",
        "job_title": "VP Engineering",  # not in mapping
        "seniority": "vp",  # not in mapping
    }

    lead = _map_contact_to_lead(contact)

    assert lead["email"] == "jane@acme.com"
    assert lead["first_name"] == "Jane"
    assert lead["last_name"] == "Smith"
    assert lead["company_name"] == "Acme Corp"
    assert lead["phone_number"] == "+1-555-0100"
    assert lead["linkedin_profile"] == "https://linkedin.com/in/janesmith"
    assert lead["location"] == "Boston"

    # unmapped fields go to custom_fields
    assert "job_title" not in lead  # not a top-level key
    assert "seniority" not in lead  # not a top-level key
    assert lead["custom_fields"]["job_title"] == "VP Engineering"
    assert lead["custom_fields"]["seniority"] == "vp"


def test_mapping_skips_empty_values():
    """Empty and None values are not included in the lead dict."""
    from openkiln.skills.smartlead.cli import _map_contact_to_lead

    contact = {
        "email": "test@example.com",
        "first_name": None,
        "last_name": "",
        "company_name": "Test",
    }

    lead = _map_contact_to_lead(contact)

    assert "first_name" not in lead
    assert "last_name" not in lead
    assert lead["email"] == "test@example.com"
    assert lead["company_name"] == "Test"


# ── Batch Splitting ──────────────────────────────────────────


def test_push_batch_size():
    """PUSH_BATCH_SIZE is 400 (Smartlead API limit)."""
    from openkiln.skills.smartlead.cli import PUSH_BATCH_SIZE
    assert PUSH_BATCH_SIZE == 400


def test_provider_batch_size():
    """Provider BATCH_SIZE matches CLI."""
    from openkiln.providers.smartlead import BATCH_SIZE
    assert BATCH_SIZE == 400


# ── Queries ──────────────────────────────────────────────────


def test_queries_upsert_campaign(openkiln_home):
    """upsert_campaign inserts and updates correctly."""
    from openkiln.skills.smartlead import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "smartlead"])

    # insert
    queries.upsert_campaign({
        "id": 42,
        "name": "Test Campaign",
        "status": "DRAFTED",
    })

    camp = queries.get_campaign(42)
    assert camp is not None
    assert camp["name"] == "Test Campaign"
    assert camp["status"] == "DRAFTED"

    # update
    queries.upsert_campaign({
        "id": 42,
        "name": "Updated Campaign",
        "status": "ACTIVE",
    })

    camp = queries.get_campaign(42)
    assert camp["name"] == "Updated Campaign"
    assert camp["status"] == "ACTIVE"


def test_queries_push_dedup(openkiln_home):
    """get_pushed_emails returns correct set for dedup."""
    from openkiln.skills.smartlead import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "smartlead"])

    queries.record_push(1, 100, "a@example.com")
    queries.record_push(2, 100, "b@example.com")
    queries.record_push(3, 200, "a@example.com")  # different campaign

    pushed_100 = queries.get_pushed_emails(100)
    assert pushed_100 == {"a@example.com", "b@example.com"}

    pushed_200 = queries.get_pushed_emails(200)
    assert pushed_200 == {"a@example.com"}


def test_queries_sequences(openkiln_home):
    """upsert_sequences stores and retrieves correctly."""
    from openkiln.skills.smartlead import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "smartlead"])

    sequences = [
        {
            "seq_number": 1,
            "seq_delay_details": {"delay_in_days": 0},
            "variant_distribution_type": "EQUAL",
            "variants": [
                {"subject": "Hello", "email_body": "Hi there", "variant_label": "A"},
            ],
        },
        {
            "seq_number": 2,
            "seq_delay_details": {"delay_in_days": 3},
            "variant_distribution_type": "EQUAL",
            "variants": [
                {"subject": "Follow up", "email_body": "Checking in", "variant_label": "A"},
            ],
        },
    ]

    queries.upsert_sequences(42, sequences)
    stored = queries.get_sequences(42)

    assert len(stored) == 2
    assert stored[0]["seq_number"] == 1
    assert stored[1]["seq_delay_days"] == 3

    # verify variants are stored as JSON
    variants = json.loads(stored[0]["variants"])
    assert variants[0]["subject"] == "Hello"


def test_queries_campaign_stats(openkiln_home):
    """insert_campaign_stats creates snapshots."""
    from openkiln.skills.smartlead import queries

    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "smartlead"])

    queries.insert_campaign_stats(42, {
        "unique_sent_count": 100,
        "unique_open_count": 40,
        "reply_count": 5,
        "campaign_lead_stats": {"total": 100, "notStarted": 50},
    })

    stats = queries.get_latest_stats(42)
    assert stats is not None
    assert stats["sent_count"] == 100
    assert stats["unique_open_count"] == 40
    assert stats["reply_count"] == 5
    assert stats["total_leads"] == 100


# ── __init__.py Constants ────────────────────────────────────


def test_init_exports():
    """__init__.py exports expected constants."""
    from openkiln.skills.smartlead import (
        __version__,
        LEAD_COLUMNS,
        CONTACT_TO_SMARTLEAD,
        CAMPAIGN_STATUSES,
        SUPPORTED_TYPES,
        DEDUP_KEYS,
    )

    assert __version__ == "0.1.0"
    assert "email" in LEAD_COLUMNS
    assert CONTACT_TO_SMARTLEAD["email"] == "email"
    assert CONTACT_TO_SMARTLEAD["phone"] == "phone_number"
    assert "ACTIVE" in CAMPAIGN_STATUSES
    assert "contact" in SUPPORTED_TYPES
    assert DEDUP_KEYS["contact"] == "email"


# ── API Client ───────────────────────────────────────────────


def test_api_client_construction():
    """SmartleadClient can be instantiated with an API key."""
    from openkiln.skills.smartlead.api import SmartleadClient

    client = SmartleadClient("test-key-123")
    assert client._api_key == "test-key-123"


def test_api_client_no_key_error():
    """get_client raises SmartleadError when no key is configured."""
    from openkiln.skills.smartlead.api import get_client, SmartleadError
    import os

    # make sure env var is not set
    old = os.environ.pop("SMARTLEAD_API_KEY", None)
    try:
        try:
            get_client()
            assert False, "Expected SmartleadError"
        except SmartleadError as e:
            assert "API key" in str(e)
    finally:
        if old:
            os.environ["SMARTLEAD_API_KEY"] = old

"""
Smartlead skill database queries.

All functions open their own connection to smartlead.db.
"""

from __future__ import annotations

import json
import sqlite3

from openkiln import config


def _connection() -> sqlite3.Connection:
    """Opens a connection to smartlead.db."""
    db_path = config.get().skill_db_path("smartlead")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ── Campaigns ────────────────────────────────────────────────


def upsert_campaign(campaign: dict) -> None:
    """Insert or update a campaign from Smartlead API data."""
    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO campaigns (id, name, status, client_id,
                timezone, days_of_the_week, start_hour, end_hour,
                max_leads_per_day, created_at, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                status = excluded.status,
                client_id = excluded.client_id,
                timezone = excluded.timezone,
                days_of_the_week = excluded.days_of_the_week,
                start_hour = excluded.start_hour,
                end_hour = excluded.end_hour,
                max_leads_per_day = excluded.max_leads_per_day,
                created_at = excluded.created_at,
                synced_at = datetime('now')
            """,
            (
                campaign.get("id"),
                campaign.get("name"),
                campaign.get("status"),
                campaign.get("client_id"),
                campaign.get("timezone"),
                json.dumps(campaign.get("days_of_the_week"))
                if campaign.get("days_of_the_week")
                else None,
                campaign.get("start_hour"),
                campaign.get("end_hour"),
                campaign.get("max_leads_per_day"),
                campaign.get("created_at"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_sequences(campaign_id: int, sequences: list[dict]) -> None:
    """Insert or update sequences for a campaign."""
    conn = _connection()
    try:
        # clear existing sequences for this campaign
        conn.execute(
            "DELETE FROM sequences WHERE campaign_id = ?",
            (campaign_id,),
        )
        for seq in sequences:
            conn.execute(
                """
                INSERT INTO sequences
                    (campaign_id, seq_number, seq_delay_days,
                     variant_distribution, variants, synced_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    campaign_id,
                    seq.get("seq_number"),
                    seq.get("seq_delay_details", {}).get("delay_in_days")
                    if isinstance(seq.get("seq_delay_details"), dict)
                    else None,
                    seq.get("variant_distribution_type"),
                    json.dumps(seq.get("variants", [])),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def insert_campaign_stats(campaign_id: int, analytics: dict) -> None:
    """Insert a campaign stats snapshot."""
    lead_stats = analytics.get("campaign_lead_stats", {})
    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO campaign_stats (
                campaign_id,
                total_leads, leads_contacted, leads_not_started,
                leads_in_progress, leads_completed,
                sent_count, open_count, unique_open_count,
                click_count, unique_click_count,
                reply_count, bounce_count, unsubscribe_count,
                interested_count, not_interested_count,
                synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      datetime('now'))
            """,
            (
                campaign_id,
                lead_stats.get("total"),
                lead_stats.get("contacted"),
                lead_stats.get("notStarted"),
                lead_stats.get("inprogress"),
                lead_stats.get("completed"),
                analytics.get("unique_sent_count"),
                analytics.get("open_count"),
                analytics.get("unique_open_count"),
                analytics.get("click_count"),
                analytics.get("unique_click_count"),
                analytics.get("reply_count"),
                analytics.get("bounce_count"),
                analytics.get("unsubscribed_count"),
                lead_stats.get("interested"),
                lead_stats.get("not_interested"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_campaigns() -> list[sqlite3.Row]:
    """List all locally synced campaigns."""
    conn = _connection()
    try:
        return conn.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()
    finally:
        conn.close()


def get_campaign(campaign_id: int) -> sqlite3.Row | None:
    """Get a single locally synced campaign."""
    conn = _connection()
    try:
        return conn.execute(
            "SELECT * FROM campaigns WHERE id = ?",
            (campaign_id,),
        ).fetchone()
    finally:
        conn.close()


def get_latest_stats(campaign_id: int) -> sqlite3.Row | None:
    """Get the most recent stats snapshot for a campaign."""
    conn = _connection()
    try:
        return conn.execute(
            "SELECT * FROM campaign_stats WHERE campaign_id = ? ORDER BY synced_at DESC LIMIT 1",
            (campaign_id,),
        ).fetchone()
    finally:
        conn.close()


def get_sequences(campaign_id: int) -> list[sqlite3.Row]:
    """Get locally synced sequences for a campaign."""
    conn = _connection()
    try:
        return conn.execute(
            "SELECT * FROM sequences WHERE campaign_id = ? ORDER BY seq_number",
            (campaign_id,),
        ).fetchall()
    finally:
        conn.close()


# ── Lead pushes ──────────────────────────────────────────────


def record_push(
    record_id: int,
    campaign_id: int,
    email: str,
    smartlead_lead_id: int | None = None,
) -> None:
    """Record that a CRM contact was pushed to a campaign."""
    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO lead_pushes
                (record_id, campaign_id, email, smartlead_lead_id, pushed_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(record_id, campaign_id) DO UPDATE SET
                smartlead_lead_id = excluded.smartlead_lead_id,
                pushed_at = datetime('now')
            """,
            (record_id, campaign_id, email, smartlead_lead_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_pushed_emails(campaign_id: int) -> set[str]:
    """Get set of emails already pushed to a campaign."""
    conn = _connection()
    try:
        rows = conn.execute(
            "SELECT email FROM lead_pushes WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchall()
        return {row["email"] for row in rows}
    finally:
        conn.close()


def get_pushes_for_campaign(campaign_id: int) -> list[sqlite3.Row]:
    """Get all lead push records for a campaign."""
    conn = _connection()
    try:
        return conn.execute(
            "SELECT * FROM lead_pushes WHERE campaign_id = ? ORDER BY pushed_at DESC",
            (campaign_id,),
        ).fetchall()
    finally:
        conn.close()

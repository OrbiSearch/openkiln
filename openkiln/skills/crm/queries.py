from __future__ import annotations

import sqlite3
from pathlib import Path

from openkiln import config


def _crm_connection() -> sqlite3.Connection:
    """Opens a connection to crm.db."""
    db_path = config.get().skill_db_path("crm")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def list_contacts(
    segment: str | None = None,
    tag: str | None = None,
    not_contacted_since: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[sqlite3.Row]:
    """
    Returns a filtered list of contacts from crm.db.

    segment: exact match on segment field
    tag: substring match on tags field (comma-separated)
    not_contacted_since: contacts not touched in this many days
    limit: max rows to return
    offset: pagination offset
    """
    where: list[str] = []
    params: list = []

    if segment:
        where.append("segment = ?")
        params.append(segment)

    if tag:
        where.append("(tags LIKE ? OR tags LIKE ? OR tags LIKE ? OR tags = ?)")
        params.extend([
            f"{tag},%",   # tag at start
            f"%,{tag},%", # tag in middle
            f"%,{tag}",   # tag at end
            tag,          # tag is only value
        ])

    if not_contacted_since is not None:
        where.append(
            "(last_contacted_at IS NULL OR "
            "last_contacted_at < datetime('now', ?))"
        )
        params.append(f"-{not_contacted_since} days")

    sql = "SELECT * FROM contacts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = _crm_connection()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def count_contacts(
    segment: str | None = None,
    tag: str | None = None,
    not_contacted_since: int | None = None,
) -> int:
    """Returns total count matching filters — for pagination display."""
    where: list[str] = []
    params: list = []

    if segment:
        where.append("segment = ?")
        params.append(segment)

    if tag:
        where.append("(tags LIKE ? OR tags LIKE ? OR tags LIKE ? OR tags = ?)")
        params.extend([f"{tag},%", f"%,{tag},%", f"%,{tag}", tag])

    if not_contacted_since is not None:
        where.append(
            "(last_contacted_at IS NULL OR "
            "last_contacted_at < datetime('now', ?))"
        )
        params.append(f"-{not_contacted_since} days")

    sql = "SELECT COUNT(*) FROM contacts"
    if where:
        sql += " WHERE " + " AND ".join(where)

    conn = _crm_connection()
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def list_companies(
    segment: str | None = None,
    tag: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[sqlite3.Row]:
    """Returns a filtered list of companies from crm.db."""
    where: list[str] = []
    params: list = []

    if segment:
        where.append("segment = ?")
        params.append(segment)

    if tag:
        where.append("(tags LIKE ? OR tags LIKE ? OR tags LIKE ? OR tags = ?)")
        params.extend([f"{tag},%", f"%,{tag},%", f"%,{tag}", tag])

    sql = "SELECT * FROM companies"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = _crm_connection()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def tag_contacts(
    set_segment: str | None = None,
    add_tag: str | None = None,
    remove_tag: str | None = None,
    filter_segment: str | None = None,
    filter_tag: str | None = None,
    record_ids: list[int] | None = None,
    email: str | None = None,
) -> int:
    """
    Applies segment or tag updates to matching contacts.
    Returns number of rows updated.
    """
    # build WHERE clause
    where: list[str] = []
    params: list = []

    if record_ids:
        placeholders = ",".join(["?"] * len(record_ids))
        where.append(f"record_id IN ({placeholders})")
        params.extend(record_ids)

    if email:
        where.append("email = ?")
        params.append(email)

    if filter_segment:
        where.append("segment = ?")
        params.append(filter_segment)

    if filter_tag:
        where.append(
            "(tags LIKE ? OR tags LIKE ? OR tags LIKE ? OR tags = ?)"
        )
        params.extend([
            f"{filter_tag},%",
            f"%,{filter_tag},%",
            f"%,{filter_tag}",
            filter_tag,
        ])

    where_sql = " WHERE " + " AND ".join(where) if where else ""

    conn = _crm_connection()
    try:
        affected = 0

        if set_segment is not None:
            sql = f"UPDATE contacts SET segment = ? {where_sql}"
            cursor = conn.execute(sql, [set_segment] + params)
            affected = max(affected, cursor.rowcount)

        if add_tag is not None:
            # fetch current tags and append if not already present
            rows = conn.execute(
                f"SELECT record_id, tags FROM contacts{where_sql}",
                params
            ).fetchall()
            for row in rows:
                current = row["tags"] or ""
                existing = [t.strip() for t in current.split(",") if t.strip()]
                if add_tag not in existing:
                    existing.append(add_tag)
                    new_tags = ",".join(existing)
                    conn.execute(
                        "UPDATE contacts SET tags = ? WHERE record_id = ?",
                        (new_tags, row["record_id"])
                    )
                    affected += 1

        if remove_tag is not None:
            rows = conn.execute(
                f"SELECT record_id, tags FROM contacts{where_sql}",
                params
            ).fetchall()
            for row in rows:
                current = row["tags"] or ""
                existing = [t.strip() for t in current.split(",") if t.strip()]
                if remove_tag in existing:
                    existing.remove(remove_tag)
                    new_tags = ",".join(existing)
                    conn.execute(
                        "UPDATE contacts SET tags = ? WHERE record_id = ?",
                        (new_tags, row["record_id"])
                    )
                    affected += 1

        conn.commit()
        return affected
    finally:
        conn.close()


def get_stats() -> dict:
    """
    Returns summary statistics for the CRM.
    Used by openkiln crm stats.
    """
    conn = _crm_connection()
    try:
        total_contacts = conn.execute(
            "SELECT COUNT(*) FROM contacts"
        ).fetchone()[0]

        contacts_by_segment = conn.execute(
            """
            SELECT
              COALESCE(NULLIF(segment, ''), '(untagged)') as seg,
              COUNT(*) as count
            FROM contacts
            GROUP BY seg
            ORDER BY count DESC
            """
        ).fetchall()

        total_companies = conn.execute(
            "SELECT COUNT(*) FROM companies"
        ).fetchone()[0]

        companies_by_segment = conn.execute(
            """
            SELECT
              COALESCE(NULLIF(segment, ''), '(untagged)') as seg,
              COUNT(*) as count
            FROM companies
            GROUP BY seg
            ORDER BY count DESC
            """
        ).fetchall()

        total_touches = conn.execute(
            "SELECT COUNT(*) FROM touches"
        ).fetchone()[0]

        return {
            "contacts": {
                "total": total_contacts,
                "by_segment": [
                    {"segment": row["seg"], "count": row["count"]}
                    for row in contacts_by_segment
                ],
            },
            "companies": {
                "total": total_companies,
                "by_segment": [
                    {"segment": row["seg"], "count": row["count"]}
                    for row in companies_by_segment
                ],
            },
            "touches": {
                "total": total_touches,
            },
        }
    finally:
        conn.close()


def log_touch(
    record_id: int,
    channel: str = "email",
    direction: str = "outbound",
    note: str | None = None,
    campaign_id: str | None = None,
) -> int:
    """
    Logs a touch against a record and updates last_contacted_at.
    Returns the new touch id.
    """
    conn = _crm_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO touches
              (record_id, channel, direction, note, campaign_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (record_id, channel, direction, note, campaign_id)
        )
        touch_id = cursor.lastrowid

        # update last_contacted_at on the contact/company
        conn.execute(
            """
            UPDATE contacts
            SET last_contacted_at = datetime('now')
            WHERE record_id = ?
            """,
            (record_id,)
        )
        # also try companies (record may be a company)
        conn.execute(
            """
            UPDATE companies
            SET last_contacted_at = datetime('now')
            WHERE record_id = ?
            """,
            (record_id,)
        )

        conn.commit()
        return touch_id
    finally:
        conn.close()

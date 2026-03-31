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


def link_contacts_to_companies(
    contact_field: str = "email_domain",
    company_field: str = "domain",
    dry_run: bool = True,
    overwrite: bool = False,
) -> dict:
    """
    Links contacts to companies by matching fields.

    contact_field: "email_domain" extracts domain from email,
                   or any other contact column name for exact match.
    company_field: company column to match against (e.g. "domain", "name").
    dry_run: if True, counts matches without writing.
    overwrite: if True, overwrites existing company_record_id links.

    Returns dict with matched, unmatched, skipped counts.
    """
    conn = _crm_connection()
    try:
        # get all contacts
        if overwrite:
            contacts = conn.execute(
                "SELECT record_id, email, company_name, company_record_id "
                "FROM contacts"
            ).fetchall()
        else:
            contacts = conn.execute(
                "SELECT record_id, email, company_name, company_record_id "
                "FROM contacts"
            ).fetchall()

        # get all companies indexed by match field
        companies = conn.execute(
            f"SELECT record_id, {company_field} FROM companies "
            f"WHERE {company_field} IS NOT NULL"
        ).fetchall()
        company_lookup: dict[str, int] = {
            row[company_field].strip().lower(): row["record_id"]
            for row in companies
            if row[company_field]
        }

        matched = 0
        unmatched = 0
        skipped = 0

        for contact in contacts:
            # skip already linked unless overwrite
            if contact["company_record_id"] is not None and not overwrite:
                skipped += 1
                continue

            # extract match value from contact
            if contact_field == "email_domain":
                email = contact["email"] or ""
                if "@" in email:
                    match_val = email.split("@", 1)[1].strip().lower()
                else:
                    match_val = ""
            else:
                match_val = (contact[contact_field] or "").strip().lower()

            if not match_val:
                unmatched += 1
                continue

            company_id = company_lookup.get(match_val)
            if company_id is None:
                unmatched += 1
                continue

            matched += 1

            if not dry_run:
                conn.execute(
                    "UPDATE contacts SET company_record_id = ? "
                    "WHERE record_id = ?",
                    (company_id, contact["record_id"])
                )

        if not dry_run:
            conn.commit()

        return {
            "matched": matched,
            "unmatched": unmatched,
            "skipped": skipped,
        }
    finally:
        conn.close()


def link_contact_to_company(
    contact_record_id: int,
    company_record_id: int,
) -> bool:
    """
    Manually links a single contact to a company.
    Returns True on success.
    """
    conn = _crm_connection()
    try:
        conn.execute(
            "UPDATE contacts SET company_record_id = ? "
            "WHERE record_id = ?",
            (company_record_id, contact_record_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ── lists ─────────────────────────────────────────────────────

def create_list(name: str, description: str | None = None) -> int:
    """
    Creates a new named list. Returns the list id.
    Raises ValueError if a list with that name already exists.
    """
    conn = _crm_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM lists WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            raise ValueError(f"List '{name}' already exists.")
        cursor = conn.execute(
            "INSERT INTO lists (name, description) VALUES (?, ?)",
            (name, description)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_lists() -> list:
    """Returns all lists with member counts."""
    conn = _crm_connection()
    try:
        return conn.execute("""
            SELECT l.id, l.name, l.description, l.type,
                   COUNT(lm.record_id) as member_count,
                   l.created_at
            FROM lists l
            LEFT JOIN list_members lm ON lm.list_id = l.id
            GROUP BY l.id
            ORDER BY l.name
        """).fetchall()
    finally:
        conn.close()


def add_to_list(
    list_name: str,
    record_ids: list[int],
) -> dict:
    """
    Adds records to a named list.
    Skips records already in the list.
    Returns dict with added and skipped counts.
    """
    conn = _crm_connection()
    try:
        lst = conn.execute(
            "SELECT id FROM lists WHERE name = ?", (list_name,)
        ).fetchone()
        if not lst:
            raise ValueError(f"List '{list_name}' does not exist.")

        list_id = lst[0]
        existing = {
            row[0] for row in conn.execute(
                "SELECT record_id FROM list_members WHERE list_id = ?",
                (list_id,)
            ).fetchall()
        }

        to_add = [rid for rid in record_ids if rid not in existing]
        skipped = len(record_ids) - len(to_add)

        if to_add:
            conn.executemany(
                "INSERT INTO list_members (list_id, record_id) "
                "VALUES (?, ?)",
                [(list_id, rid) for rid in to_add]
            )
            conn.commit()

        return {"added": len(to_add), "skipped": skipped}
    finally:
        conn.close()


def remove_from_list(list_name: str, record_ids: list[int]) -> int:
    """
    Removes records from a named list.
    Returns number of records removed.
    """
    conn = _crm_connection()
    try:
        lst = conn.execute(
            "SELECT id FROM lists WHERE name = ?", (list_name,)
        ).fetchone()
        if not lst:
            raise ValueError(f"List '{list_name}' does not exist.")

        list_id = lst[0]
        placeholders = ",".join(["?"] * len(record_ids))
        cursor = conn.execute(
            f"DELETE FROM list_members "
            f"WHERE list_id = ? AND record_id IN ({placeholders})",
            [list_id] + record_ids
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_list_members(
    list_name: str,
    limit: int = 50,
    offset: int = 0,
) -> list:
    """Returns contacts in a named list."""
    conn = _crm_connection()
    try:
        lst = conn.execute(
            "SELECT id FROM lists WHERE name = ?", (list_name,)
        ).fetchone()
        if not lst:
            raise ValueError(f"List '{list_name}' does not exist.")

        list_id = lst[0]
        return conn.execute("""
            SELECT c.* FROM contacts c
            JOIN list_members lm ON lm.record_id = c.record_id
            WHERE lm.list_id = ?
            ORDER BY lm.added_at DESC
            LIMIT ? OFFSET ?
        """, (list_id, limit, offset)).fetchall()
    finally:
        conn.close()


def delete_list(list_name: str) -> bool:
    """
    Deletes a list and all its memberships.
    Returns True if deleted, False if not found.
    """
    conn = _crm_connection()
    try:
        lst = conn.execute(
            "SELECT id FROM lists WHERE name = ?", (list_name,)
        ).fetchone()
        if not lst:
            return False

        list_id = lst[0]
        conn.execute(
            "DELETE FROM list_members WHERE list_id = ?", (list_id,)
        )
        conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def list_contacts_by_lifecycle(
    lifecycle_stage: str | None = None,
    lead_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list:
    """Returns contacts filtered by lifecycle_stage and/or lead_status."""
    where: list[str] = []
    params: list = []

    if lifecycle_stage:
        where.append("lifecycle_stage = ?")
        params.append(lifecycle_stage)

    if lead_status:
        where.append("lead_status = ?")
        params.append(lead_status)

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

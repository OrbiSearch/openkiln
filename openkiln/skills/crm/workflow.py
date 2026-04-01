"""
CRM workflow interfaces — Source and Sink implementations.

CrmSource reads contacts or companies from crm.db.
CrmSink updates records in crm.db.
"""
from __future__ import annotations

from typing import Any, Iterator

from openkiln import db
from openkiln.core import Source, Sink

# Columns that exist in the contacts table and can be updated.
# The sink only writes these — transform-added fields are ignored.
_CONTACT_COLUMNS = {
    "first_name", "last_name", "full_name", "email", "phone",
    "linkedin_url", "company_name", "job_title", "department",
    "seniority", "city", "country", "timezone", "segment", "tags",
    "lead_score", "source", "last_contacted_at",
    "lifecycle_stage", "lead_status",
}


class CrmSource(Source):
    """
    Reads contacts or companies from crm.db.

    Workflow YAML:
        source:
          skill: crm
          type: contacts        # or companies
          filter:
            segment: gtm-agencies
            tag: priority
            lifecycle_stage: lead
            lead_status: new
            record_status: active
    """

    def read(self, **config: Any) -> Iterator[dict]:
        record_type = config.get("type", "contacts")
        table = "contacts" if record_type in ("contact", "contacts") else "companies"
        filters = config.get("filter", {})

        where: list[str] = []
        params: list = []

        if filters.get("segment"):
            where.append("segment = ?")
            params.append(filters["segment"])

        if filters.get("tag"):
            tag = filters["tag"]
            where.append(
                "(tags LIKE ? OR tags LIKE ? OR tags LIKE ? OR tags = ?)"
            )
            params.extend([f"{tag},%", f"%,{tag},%", f"%,{tag}", tag])

        if filters.get("lifecycle_stage"):
            where.append("lifecycle_stage = ?")
            params.append(filters["lifecycle_stage"])

        if filters.get("lead_status"):
            where.append("lead_status = ?")
            params.append(filters["lead_status"])

        if filters.get("record_status"):
            where.append(
                "record_id IN (SELECT id FROM records WHERE record_status = ?)"
            )
            params.append(filters["record_status"])

        sql = f"SELECT * FROM crm.{table}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC"

        with db.connection(attach_skills=["crm"]) as conn:
            cursor = conn.execute(sql, params)
            while True:
                rows = cursor.fetchmany(db.BATCH_SIZE)
                if not rows:
                    break
                for row in rows:
                    yield dict(row)


class CrmSink(Sink):
    """
    Updates records in crm.db.

    Workflow YAML:
        sinks:
          - skill: crm
            action: update
    """

    def write(self, rows: list[dict], **config: Any) -> dict:
        action = config.get("action", "update")

        if action != "update":
            raise ValueError(f"CRM sink does not support action: {action}")

        updated = 0
        with db.transaction(attach_skills=["crm"]) as conn:
            for row in rows:
                record_id = row.get("record_id")
                if record_id is None:
                    continue

                # build SET clause — only update known contact columns
                set_parts = []
                values = []
                for key, val in row.items():
                    if key not in _CONTACT_COLUMNS or val is None:
                        continue
                    set_parts.append(f"{key} = ?")
                    values.append(val)

                if not set_parts:
                    continue

                set_parts.append("updated_at = datetime('now')")
                values.append(record_id)

                conn.execute(
                    f"UPDATE crm.contacts SET {', '.join(set_parts)} "
                    f"WHERE record_id = ?",
                    values,
                )
                updated += 1

        return {"written": updated}

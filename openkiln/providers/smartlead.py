# providers/smartlead.py
#
# Smartlead provider integration.
# Implements a Sink that pushes contacts to Smartlead
# campaigns via their API.
# Requires SMARTLEAD_API_KEY in config.
#
# Workflow usage:
#   sinks:
#     - skill: smartlead
#       action: push
#       campaign_id: "12345"

from __future__ import annotations

from typing import Any

from openkiln.skills.smartlead import CRM_TO_SMARTLEAD
from openkiln.skills.smartlead.api import get_client
from openkiln.skills.smartlead import queries

BATCH_SIZE = 400  # Smartlead API limit


def push(rows: list[dict], *, campaign_id: int, **kwargs: Any) -> dict:
    """
    Sink: push rows of contact data to a Smartlead campaign.

    Each row should contain CRM contact fields (email, first_name, etc).
    Fields are mapped via CRM_TO_SMARTLEAD to Smartlead lead fields.
    Deduplicates against previously pushed contacts.
    Returns a summary dict.

    Called by the workflow engine when a sink specifies:
        skill: smartlead, action: push
    """
    client = get_client()

    # dedup against already-pushed contacts
    already_pushed = queries.get_pushed_emails(campaign_id)
    already_pushed_lower = {e.lower() for e in already_pushed}

    to_push = []
    skipped = 0
    for row in rows:
        email = row.get("email", "")
        if not email or email.lower() in already_pushed_lower:
            skipped += 1
            continue
        to_push.append(row)

    # map fields and push in batches
    pushed = 0
    for i in range(0, len(to_push), BATCH_SIZE):
        batch = to_push[i : i + BATCH_SIZE]

        lead_list = []
        for row in batch:
            lead: dict = {}
            for crm_field, sl_field in CRM_TO_SMARTLEAD.items():
                val = row.get(crm_field)
                if val is not None and val != "":
                    lead[sl_field] = val
            lead_list.append(lead)

        client.add_leads_to_campaign(campaign_id, lead_list)

        # record pushes locally
        for row in batch:
            record_id = row.get("record_id")
            if record_id is not None:
                queries.record_push(
                    record_id=record_id,
                    campaign_id=campaign_id,
                    email=row["email"],
                )

        pushed += len(batch)

    return {
        "campaign_id": campaign_id,
        "pushed": pushed,
        "skipped": skipped,
        "total_input": len(rows),
    }

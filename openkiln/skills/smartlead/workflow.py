"""
Smartlead workflow interface — Sink implementation.

SmartleadSink pushes contacts to a Smartlead campaign.
"""
from __future__ import annotations

from typing import Any

from openkiln.core import Sink
from openkiln.skills.smartlead import CONTACT_TO_SMARTLEAD, INTERNAL_FIELDS
from openkiln.skills.smartlead.api import get_client
from openkiln.skills.smartlead import queries

BATCH_SIZE = 400  # Smartlead API limit


class SmartleadSink(Sink):
    """
    Pushes contacts to a Smartlead campaign.

    Maps contact fields via CONTACT_TO_SMARTLEAD, sends unmapped
    fields as custom_fields. Deduplicates against previously pushed
    contacts. Batches in groups of 400.

    Workflow YAML:
        sinks:
          - skill: smartlead
            action: push
            campaign_id: "12345"
    """

    def write(self, rows: list[dict], **config: Any) -> dict:
        action = config.get("action", "push")
        if action != "push":
            raise ValueError(f"Smartlead sink does not support action: {action}")

        campaign_id = config.get("campaign_id")
        if not campaign_id:
            raise ValueError("Smartlead sink requires campaign_id")
        campaign_id = int(campaign_id)

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
        mapped_fields = set(CONTACT_TO_SMARTLEAD.keys())

        for i in range(0, len(to_push), BATCH_SIZE):
            batch = to_push[i : i + BATCH_SIZE]

            lead_list = []
            for row in batch:
                lead: dict = {}
                for contact_field, sl_field in CONTACT_TO_SMARTLEAD.items():
                    val = row.get(contact_field)
                    if val is not None and val != "":
                        lead[sl_field] = val

                # unmapped fields go to custom_fields
                custom: dict = {}
                for key, val in row.items():
                    if key in mapped_fields or key in INTERNAL_FIELDS:
                        continue
                    if val is not None and val != "":
                        custom[key] = str(val)
                if custom:
                    lead["custom_fields"] = custom

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

        return {"written": pushed, "skipped": skipped}

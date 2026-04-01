"""
OrbiSearch workflow interface — Transform implementation.

OrbiSearchTransform verifies email addresses via the OrbiSearch API
and adds verification fields to each row.
"""
from __future__ import annotations

from openkiln.core import Transform
from openkiln.skills.orbisearch.api import get_client, OrbiSearchError
from openkiln.skills.orbisearch import queries


class OrbiSearchTransform(Transform):
    """
    Verifies email addresses via the OrbiSearch API.

    Adds these fields to each row:
        status, substatus, explanation, email_provider,
        is_disposable, is_role_account, is_free

    Rows without an "email" field are passed through unchanged.
    API errors result in the row being passed through with
    status="unknown" so downstream filters can handle it.

    Workflow YAML:
        transforms:
          - orbisearch.validate
    """

    def __init__(self) -> None:
        self._client = get_client()

    def apply(self, row: dict) -> dict | None:
        email = row.get("email")
        if not email:
            return row

        try:
            result = self._client.verify_email(email)
        except OrbiSearchError:
            # API failure — mark as unknown, don't drop the row
            row["status"] = "unknown"
            row["substatus"] = None
            row["explanation"] = "Verification failed"
            return row

        # add verification fields to the row
        row["status"] = result.get("status", "unknown")
        row["substatus"] = result.get("substatus")
        row["explanation"] = result.get("explanation", "")
        row["email_provider"] = result.get("email_provider", "")
        row["is_disposable"] = result.get("is_disposable")
        row["is_role_account"] = result.get("is_role_account")
        row["is_free"] = result.get("is_free")

        # store result in orbisearch.db
        record_id = row.get("record_id")
        if record_id is not None:
            queries.upsert_verification_result(
                record_id=record_id,
                result={"email": email, **result},
            )

        return row

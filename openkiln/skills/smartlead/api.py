"""
Smartlead API client.

Thin wrapper around the Smartlead REST API (v1).
Auth: API key passed as query parameter.
Rate limit: 10 requests per 2 seconds.

Usage:
    from openkiln.skills.smartlead.api import get_client
    client = get_client()
    campaigns = client.list_campaigns()
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

from openkiln import config

BASE_URL = "https://server.smartlead.ai/api/v1"
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3
# Smartlead rate limit: 10 requests per 2 seconds
MIN_REQUEST_INTERVAL = 0.2  # 200ms between requests


class SmartleadError(Exception):
    """Base error for Smartlead API failures."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class SmartleadClient:
    """
    Smartlead API v1 client.

    All methods return parsed JSON (dict or list).
    Raises SmartleadError on API failures.
    """

    def __init__(self, api_key: str, base_url: str = BASE_URL) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._last_request_at: float = 0.0

    # ── HTTP layer ───────────────────────────────────────────

    def _throttle(self) -> None:
        """Enforce minimum interval between requests."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        """Make an authenticated request with retry and rate limiting."""
        url = f"{self._base_url}{path}"
        query = {"api_key": self._api_key}
        if params:
            query.update(params)

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            try:
                response = httpx.request(
                    method,
                    url,
                    params=query,
                    json=json,
                    timeout=REQUEST_TIMEOUT,
                )
                self._last_request_at = time.monotonic()

                if response.status_code == 429:
                    # rate limited — back off and retry
                    if attempt < MAX_RETRIES:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    raise SmartleadError(
                        "Rate limited by Smartlead API", 429
                    )

                if response.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    raise SmartleadError(
                        f"Server error: {response.text}", response.status_code
                    )

                if response.status_code >= 400:
                    raise SmartleadError(
                        f"API error: {response.text}", response.status_code
                    )

                # some endpoints return empty body
                if not response.text:
                    return None

                return response.json()

            except httpx.TimeoutException:
                last_error = SmartleadError("Request timed out")
                if attempt < MAX_RETRIES:
                    continue
            except httpx.RequestError as e:
                last_error = SmartleadError(f"Network error: {e}")
                if attempt < MAX_RETRIES:
                    continue

        raise last_error or SmartleadError("Request failed after retries")

    def _get(self, path: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", path, params=clean)

    def _post(self, path: str, body: Any = None, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request("POST", path, params=clean, json=body)

    def _patch(self, path: str, body: Any = None) -> Any:
        return self._request("PATCH", path, json=body)

    def _delete(self, path: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request("DELETE", path, params=clean)

    # ── Campaigns ────────────────────────────────────────────

    def list_campaigns(
        self, *, client_id: int | None = None, include_tags: bool = False
    ) -> list[dict]:
        """List all campaigns."""
        return self._get(
            "/campaigns/",
            client_id=client_id,
            include_tags=str(include_tags).lower() if include_tags else None,
        )

    def get_campaign(self, campaign_id: int) -> dict:
        """Get a single campaign by ID."""
        return self._get(f"/campaigns/{campaign_id}")

    def get_campaign_analytics(self, campaign_id: int) -> dict:
        """Get top-level analytics for a campaign."""
        return self._get(f"/campaigns/{campaign_id}/analytics")

    def get_campaign_statistics(
        self,
        campaign_id: int,
        *,
        offset: int = 0,
        limit: int = 100,
        email_sequence_number: int | None = None,
        email_status: str | None = None,
    ) -> Any:
        """Get per-lead statistics for a campaign."""
        return self._get(
            f"/campaigns/{campaign_id}/statistics",
            offset=offset,
            limit=limit,
            email_sequence_number=email_sequence_number,
            email_status=email_status,
        )

    def get_campaign_analytics_by_date(
        self,
        campaign_id: int,
        *,
        start_date: str,
        end_date: str,
    ) -> Any:
        """Get analytics broken down by date range (YYYY-MM-DD)."""
        return self._get(
            f"/campaigns/{campaign_id}/analytics-by-date",
            start_date=start_date,
            end_date=end_date,
        )

    # ── Sequences ────────────────────────────────────────────

    def get_sequences(self, campaign_id: int) -> list[dict]:
        """Get email sequences for a campaign."""
        return self._get(f"/campaigns/{campaign_id}/sequences")

    def save_sequences(
        self, campaign_id: int, sequences: list[dict]
    ) -> Any:
        """Save/replace sequences for a campaign."""
        return self._post(
            f"/campaigns/{campaign_id}/sequences", sequences
        )

    # ── Email Accounts ───────────────────────────────────────

    def list_email_accounts(
        self, *, offset: int = 0, limit: int = 100
    ) -> list[dict]:
        """List all email accounts."""
        return self._get(
            "/email-accounts/", offset=offset, limit=limit
        )

    def get_campaign_email_accounts(self, campaign_id: int) -> list[dict]:
        """List email accounts assigned to a campaign."""
        return self._get(f"/campaigns/{campaign_id}/email-accounts")

    def add_email_accounts_to_campaign(
        self, campaign_id: int, email_account_ids: list[int]
    ) -> Any:
        """Add email accounts to a campaign."""
        return self._post(
            f"/campaigns/{campaign_id}/email-accounts",
            {"email_account_ids": email_account_ids},
        )

    def remove_email_account_from_campaign(
        self, campaign_id: int, email_account_id: int
    ) -> Any:
        """Remove an email account from a campaign."""
        return self._request(
            "DELETE",
            f"/campaigns/{campaign_id}/email-accounts",
            json={"email_account_id": email_account_id},
        )

    # ── Campaign Management ──────────────────────────────────

    def create_campaign(
        self, name: str, *, client_id: int | None = None
    ) -> dict:
        """Create a new campaign (DRAFTED status)."""
        body: dict[str, Any] = {"name": name}
        if client_id is not None:
            body["client_id"] = client_id
        return self._post("/campaigns/create", body)

    def update_campaign_status(
        self, campaign_id: int, status: str
    ) -> Any:
        """Update campaign status (ACTIVE, PAUSED, STOPPED, START)."""
        return self._post(
            f"/campaigns/{campaign_id}/status", {"status": status}
        )

    def update_campaign_schedule(
        self,
        campaign_id: int,
        *,
        timezone: str,
        days_of_the_week: list[int],
        start_hour: str,
        end_hour: str,
        min_time_btw_emails: int = 2,
        max_leads_per_day: int | None = None,
    ) -> Any:
        """Set campaign sending schedule."""
        body: dict[str, Any] = {
            "timezone": timezone,
            "days_of_the_week": days_of_the_week,
            "start_hour": start_hour,
            "end_hour": end_hour,
            "min_time_btw_emails": min_time_btw_emails,
        }
        if max_leads_per_day is not None:
            body["max_new_leads_per_day"] = max_leads_per_day
        return self._post(f"/campaigns/{campaign_id}/schedule", body)

    def update_campaign_settings(
        self, campaign_id: int, settings: dict
    ) -> Any:
        """Update campaign settings (track_settings, stop_lead_settings, etc)."""
        return self._post(f"/campaigns/{campaign_id}/settings", settings)

    def delete_campaign(self, campaign_id: int) -> Any:
        """Delete a campaign."""
        return self._delete(f"/campaigns/{campaign_id}")

    # ── Leads ────────────────────────────────────────────────

    def add_leads_to_campaign(
        self,
        campaign_id: int,
        lead_list: list[dict],
        *,
        settings: dict | None = None,
    ) -> Any:
        """
        Add leads to a campaign (max 400 per request).

        lead_list items: {email, first_name, last_name, company_name,
        phone_number, website, location, linkedin_profile, company_url,
        custom_fields: {key: value}}
        """
        body: dict[str, Any] = {"lead_list": lead_list}
        if settings:
            body["settings"] = settings
        return self._post(f"/campaigns/{campaign_id}/leads", body)

    def get_campaign_leads(
        self,
        campaign_id: int,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        """List leads in a campaign."""
        return self._get(
            f"/campaigns/{campaign_id}/leads",
            offset=offset,
            limit=limit,
        )

    def get_lead_by_email(self, email: str) -> Any:
        """Find a lead by email address."""
        return self._get("/leads/", email=email)

    def get_lead_message_history(
        self, campaign_id: int, lead_id: int
    ) -> Any:
        """Get full email thread history for a lead."""
        return self._get(
            f"/campaigns/{campaign_id}/leads/{lead_id}/message-history"
        )

    def update_lead_status(
        self, campaign_id: int, lead_id: int, action: str
    ) -> Any:
        """Pause, resume, or unsubscribe a lead."""
        return self._post(
            f"/campaigns/{campaign_id}/leads/{lead_id}/{action}"
        )

    def delete_lead_from_campaign(
        self, campaign_id: int, lead_id: int
    ) -> Any:
        """Delete a lead from a campaign."""
        return self._delete(
            f"/campaigns/{campaign_id}/leads/{lead_id}"
        )

    def export_campaign_leads(self, campaign_id: int) -> Any:
        """Export all leads in a campaign (CSV data)."""
        return self._get(f"/campaigns/{campaign_id}/leads-export")

    # ── Analytics (global) ───────────────────────────────────

    def get_analytics_overview(
        self,
        *,
        client_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Any:
        """Get global cross-campaign analytics."""
        return self._get(
            "/analytics/overview",
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
        )

    # ── Webhooks ─────────────────────────────────────────────

    def list_webhooks(self, *, client_id: str | None = None) -> Any:
        """List all webhooks."""
        return self._get("/webhooks", client_id=client_id)

    def create_webhook(
        self,
        *,
        name: str,
        url: str,
        events: list[str],
        client_id: str | None = None,
    ) -> Any:
        """Create a webhook."""
        body: dict[str, Any] = {
            "name": name,
            "webhook_url": url,
            "event_types": events,
        }
        if client_id:
            body["client_id"] = client_id
        return self._post("/webhooks", body)


# ── Factory ─────────────────────────────────────────────────


def _resolve_api_key() -> str:
    """
    Resolve Smartlead API key from environment or config.
    Raises SmartleadError if not configured.
    """
    key = os.environ.get("SMARTLEAD_API_KEY")
    if key:
        return key

    cfg = config.get()
    key = cfg.skill_config("smartlead").get("api_key", "")
    if key:
        return key

    raise SmartleadError(
        "No Smartlead API key configured.\n"
        "Set SMARTLEAD_API_KEY or add it to ~/.openkiln/config.toml:\n"
        "  [skills.smartlead]\n"
        '  api_key = "your-key-here"'
    )


def get_client() -> SmartleadClient:
    """
    Returns a SmartleadClient using the configured API key.
    Raises SmartleadError if no key is set.
    """
    return SmartleadClient(_resolve_api_key())

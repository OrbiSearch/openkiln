"""
EmailGuard API client.

Inbox placement testing — create tests, fetch results.
Auth: Bearer token in Authorization header.
API: https://app.emailguard.io

Usage:
    from openkiln.skills.emailguard.api import get_client
    client = get_client()
    test = client.create_test("My Test", gmail_seeds=4, msft_seeds=4)
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from openkiln import config

BASE_URL = "https://app.emailguard.io"
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3
MIN_REQUEST_INTERVAL = 0.5


class EmailGuardError(Exception):
    """Base error for EmailGuard API failures."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


def _parse_error(body: str) -> str:
    """Extract a human-readable message from an API error response."""
    try:
        import json

        parsed = json.loads(body)
        return parsed.get("message") or parsed.get("error") or body[:200]
    except Exception:
        return body[:200]


class EmailGuardClient:
    """
    EmailGuard API client.
    All methods return parsed JSON (dict or list).
    Raises EmailGuardError on API failures.
    """

    def __init__(self, api_key: str, base_url: str = BASE_URL) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._last_request_at: float = 0.0

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            try:
                response = httpx.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json,
                    timeout=REQUEST_TIMEOUT,
                )
                self._last_request_at = time.monotonic()

                if response.status_code == 429:
                    if attempt < MAX_RETRIES:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    raise EmailGuardError("Rate limited", 429)

                if response.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    raise EmailGuardError(
                        f"Server error: {_parse_error(response.text)}",
                        response.status_code,
                    )

                if response.status_code == 401:
                    raise EmailGuardError(
                        "Invalid or missing API key",
                        401,
                    )

                if response.status_code >= 400:
                    raise EmailGuardError(
                        _parse_error(response.text),
                        response.status_code,
                    )

                if not response.text:
                    return None
                return response.json()

            except httpx.TimeoutException:
                last_error = EmailGuardError("Request timed out")
                if attempt < MAX_RETRIES:
                    continue
            except httpx.RequestError as e:
                last_error = EmailGuardError(f"Network error: {e}")
                if attempt < MAX_RETRIES:
                    continue

        raise last_error or EmailGuardError("Request failed after retries")

    # ── Placement Tests ──────────────────────────────────────

    def create_test(
        self,
        name: str,
        *,
        gmail_seeds: int = 4,
        msft_seeds: int = 4,
    ) -> dict:
        """
        Create a new inbox placement test.

        Returns test data including uuid, filter_phrase, and
        inbox_placement_test_emails (seed addresses).
        """
        result = self._request(
            "POST",
            "/api/v1/inbox-placement-tests",
            json={
                "name": name,
                "google_workspace_emails_count": gmail_seeds,
                "microsoft_professional_emails_count": msft_seeds,
            },
        )
        return result.get("data", result)

    def get_test(self, test_uuid: str) -> dict:
        """
        Get placement test status and results.

        Returns test data including status, overall_score,
        and per-seed results with folder placement.
        """
        result = self._request(
            "GET",
            f"/api/v1/inbox-placement-tests/{test_uuid}",
        )
        return result.get("data", result)

    def list_tests(self) -> list[dict]:
        """List all placement tests."""
        result = self._request(
            "GET",
            "/api/v1/inbox-placement-tests",
        )
        data = result.get("data", result)
        return data if isinstance(data, list) else [data]


# ── Factory ─────────────────────────────────────────────────


def _resolve_api_key() -> str:
    """Resolve API key from environment or config."""
    key = os.environ.get("EMAILGUARD_API_KEY")
    if key:
        return key

    cfg = config.get()
    key = cfg.skill_config("emailguard").get("api_key", "")
    if key:
        return key

    raise EmailGuardError(
        "No EmailGuard API key configured.\n"
        "Set EMAILGUARD_API_KEY or add it to ~/.openkiln/config.toml:\n"
        "  [skills.emailguard]\n"
        '  api_key = "your-bearer-token"'
    )


def get_client() -> EmailGuardClient:
    """Returns a client using the configured API key."""
    return EmailGuardClient(_resolve_api_key())

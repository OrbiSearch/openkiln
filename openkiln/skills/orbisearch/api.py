"""
OrbiSearch API client.
API docs: https://api.orbisearch.com/docs
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from openkiln import config

BASE_URL = "https://api.orbisearch.com"
REQUEST_TIMEOUT = 75.0
MAX_RETRIES = 3
MIN_REQUEST_INTERVAL = 0.06  # ~16 req/s to stay under recommended rate


class OrbiSearchError(Exception):
    """Base error for OrbiSearch API failures."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class OrbiSearchClient:
    """OrbiSearch API client. All methods return parsed JSON."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._last_request_at: float = 0.0

    # ── HTTP layer ──────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key, "Accept": "application/json"}

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        self._throttle()
        url = f"{BASE_URL}{path}"
        last_err: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._last_request_at = time.monotonic()
                resp = httpx.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=params,
                    json=json_body,
                    timeout=REQUEST_TIMEOUT,
                )

                if resp.status_code == 429:
                    wait = min(2**attempt, 30)
                    time.sleep(wait)
                    last_err = OrbiSearchError("Rate limited", status_code=429)
                    continue

                if resp.status_code >= 500:
                    wait = min(2**attempt, 30)
                    time.sleep(wait)
                    last_err = OrbiSearchError(
                        f"Server error {resp.status_code}",
                        status_code=resp.status_code,
                    )
                    continue

                if resp.status_code == 401:
                    raise OrbiSearchError("Invalid or missing API key", status_code=401)
                if resp.status_code == 403:
                    raise OrbiSearchError("Insufficient credits", status_code=403)

                resp.raise_for_status()
                return resp.json()

            except httpx.HTTPStatusError as exc:
                raise OrbiSearchError(
                    f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                last_err = OrbiSearchError(f"Request failed: {exc}")
                if attempt < MAX_RETRIES:
                    time.sleep(min(2**attempt, 30))
                    continue
                raise last_err from exc

        raise last_err or OrbiSearchError("Max retries exceeded")

    # ── Public methods (1:1 with CLI commands) ──────────────

    def verify_email(self, email: str, *, timeout: int = 70) -> dict:
        """Verify a single email address (GET /v1/verify)."""
        return self._request("GET", "/v1/verify", params={"email": email, "timeout": timeout})

    def submit_bulk(self, emails: list[str]) -> dict:
        """Submit a bulk verification job (POST /v1/bulk)."""
        return self._request("POST", "/v1/bulk", json_body=emails)

    def get_bulk_status(self, job_id: str) -> dict:
        """Get bulk job status (GET /v1/bulk/{job_id})."""
        return self._request("GET", f"/v1/bulk/{job_id}")

    def get_bulk_results(self, job_id: str) -> dict:
        """Get bulk job results (GET /v1/bulk/{job_id}/results)."""
        return self._request("GET", f"/v1/bulk/{job_id}/results")

    def get_credits(self) -> dict:
        """Get current credit balance (GET /v1/credits)."""
        return self._request("GET", "/v1/credits")


def _resolve_api_key() -> str:
    """Resolve API key from env var or config."""
    key = os.environ.get("ORBISEARCH_API_KEY")
    if key:
        return key
    cfg = config.get()
    key = cfg.skill_config("orbisearch").get("api_key", "")
    if key:
        return key
    raise OrbiSearchError(
        "No API key configured. Set ORBISEARCH_API_KEY env var or add "
        "api_key under [skills.orbisearch] in ~/.openkiln/config.toml. "
        "Get a free key at https://orbisearch.com/dashboard/api-keys"
    )


def get_client() -> OrbiSearchClient:
    """Returns a client using the configured API key."""
    return OrbiSearchClient(_resolve_api_key())

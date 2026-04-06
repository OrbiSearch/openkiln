"""
Company name cleaning via OpenAI.

Uses gpt-4o-mini to clean company names for cold email outreach.
Batches names for efficiency.
"""

from __future__ import annotations

import json
import os

import httpx

from openkiln import config

BASE_URL = "https://api.openai.com/v1"
REQUEST_TIMEOUT = 30.0
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """\
You clean company names for use in cold email outreach.

Rules:
- Remove legal suffixes: Inc, Inc., LLC, Ltd, Ltd., Limited, GmbH, Corp, \
Corp., Corporation, PLC, AG, SA, SAS, BV, NV, Pty, Co., Company, Group
- Remove parenthetical descriptions: "Tiger Data (creators of TimescaleDB)" -> "Tiger Data"
- Remove pipe-separated taglines: "Rocketship | Digital Marketing Agency" -> "Rocketship"
- Remove colon-separated taglines: "eyreACT: AI Act Compliance Platform" -> "eyreACT"
- Keep the core brand name as it would appear in casual business conversation
- Preserve capitalisation and special characters that are part of the brand
- If the entire name IS the brand (e.g. "1Password", "6sense"), return it unchanged
- If removing a suffix leaves nothing meaningful, keep the original

Return a JSON array of cleaned names in the same order as the input.
No explanations, just the JSON array.\
"""


class CleancoError(Exception):
    """Base error for cleanco failures."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class CleancoClient:
    """Cleans company names via OpenAI."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def clean_batch(self, names: list[str]) -> list[str]:
        """Clean a batch of company names. Returns cleaned names in order."""
        if not names:
            return []

        user_msg = json.dumps(names)

        response = httpx.post(
            f"{BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0,
            },
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code >= 400:
            raise CleancoError(
                f"OpenAI API error: {response.text[:200]}",
                response.status_code,
            )

        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Parse the JSON array from the response
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0].strip()

        try:
            cleaned = json.loads(content)
        except json.JSONDecodeError:
            raise CleancoError(f"Could not parse OpenAI response: {content[:200]}")

        if not isinstance(cleaned, list) or len(cleaned) != len(names):
            got = len(cleaned) if isinstance(cleaned, list) else "non-list"
            raise CleancoError(f"Expected {len(names)} names, got {got}")

        return cleaned


def _resolve_api_key() -> str:
    """Resolve API key from environment or config."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    cfg = config.get()
    key = cfg.skill_config("cleanco").get("api_key", "")
    if key:
        return key

    raise CleancoError(
        "No OpenAI API key configured.\n"
        "Set OPENAI_API_KEY or add it to ~/.openkiln/config.toml:\n"
        "  [skills.cleanco]\n"
        '  api_key = "your-key-here"'
    )


def get_client() -> CleancoClient:
    """Returns a client using the configured API key."""
    return CleancoClient(_resolve_api_key())

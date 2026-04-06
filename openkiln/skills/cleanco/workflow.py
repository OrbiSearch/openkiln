"""Cleanco workflow transform."""

from __future__ import annotations

from openkiln.core import Transform
from openkiln.skills.cleanco import queries
from openkiln.skills.cleanco.api import get_client

BATCH_SIZE = 50


class CleanCompanyName(Transform):
    """Clean company names using OpenAI. Caches results in cleanco.db."""

    def __init__(self) -> None:
        self._client = get_client()
        self._pending: list[dict] = []
        self._cache: dict[str, str] = {}

    def apply(self, row: dict) -> dict | None:
        """Buffer rows and clean in batches."""
        name = row.get("company_name", "").strip()
        if not name:
            return row

        # Check cache first
        if name in self._cache:
            row["company_name"] = self._cache[name]
            return row

        # Check DB cache
        cached = queries.get_cached([name])
        if name in cached:
            self._cache[name] = cached[name]
            row["company_name"] = cached[name]
            return row

        # Need to clean via API — do it immediately for workflow compatibility
        # (Transform.apply processes one row at a time)
        self._pending.append(row)

        if len(self._pending) >= BATCH_SIZE:
            self._flush_batch()

        # Return row — company_name will be updated when batch flushes
        # For single-row processing, flush immediately
        if len(self._pending) < BATCH_SIZE:
            self._flush_batch()

        return row

    def _flush_batch(self) -> None:
        """Clean all pending names via API and update rows."""
        if not self._pending:
            return

        names = [r.get("company_name", "") for r in self._pending]
        unique_names = list(dict.fromkeys(names))  # dedupe, preserve order

        # Check DB cache for batch
        cached = queries.get_cached(unique_names)
        uncached = [n for n in unique_names if n not in cached]

        # Clean uncached names via API
        new_mappings: dict[str, str] = {}
        if uncached:
            # Process in sub-batches of BATCH_SIZE
            for i in range(0, len(uncached), BATCH_SIZE):
                batch = uncached[i : i + BATCH_SIZE]
                cleaned = self._client.clean_batch(batch)
                for orig, clean in zip(batch, cleaned):
                    new_mappings[orig] = clean

            # Cache new results
            queries.cache_results(new_mappings)

        # Merge all mappings
        all_mappings = {**cached, **new_mappings}
        self._cache.update(all_mappings)

        # Update pending rows
        for row in self._pending:
            name = row.get("company_name", "")
            if name in all_mappings:
                row["company_name"] = all_mappings[name]

        self._pending.clear()

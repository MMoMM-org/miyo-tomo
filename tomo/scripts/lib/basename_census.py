#!/usr/bin/env python3
# version: 0.1.0
"""basename_census.py — how many vault files already carry a given file name.

Spec 039 K3 / ADR-3. Filing an attachment under a name another vault file
already holds makes Obsidian's bare embed ambiguous, so the attachment plan
(K1) needs a vault-wide count per basename. Kado `byName` is the only vault
index Tomo may use; it matches by substring over every file type, so this
module narrows each answer to exact equality on the final path segment.

Contract: `count(basename)` is a RAW vault count, or None when it could not be
established (Kado error, page budget exhausted, name carrying `*`/`?` which
Kado would read as a glob). Subtracting this run's inbox copies and adding its
targets is K1's job, not this module's. None is cached like any answer: an
unanswered census already makes K1 path-qualify the embed, and re-asking under
a rate-limit error would multiply calls against the F3-AC7 bound.

Bounds (F3-AC7): one search per distinct basename (keyed NFC + casefold, the
same normalisation as typed_name_check's inside_inbox), at most PAGE_BUDGET
pages per search. A page is fetched through `client._call_tool` because
`KadoClient.search_by_name` drains every cursor and so cannot be bounded.
"""
from __future__ import annotations

import unicodedata

PAGE_BUDGET = 2
PAGE_LIMIT = 500


def _key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


class BasenameCensus:
    def __init__(self, client):
        self._client = client
        self._cache: dict[str, int | None] = {}
        self.searches = 0
        self.pages = 0

    def count(self, basename: str) -> int | None:
        key = _key(basename)
        if key not in self._cache:
            self._cache[key] = self._search(key)
        return self._cache[key]

    def _search(self, key: str) -> int | None:
        if "*" in key or "?" in key:
            return None
        self.searches += 1
        found = 0
        cursor = None
        for _ in range(PAGE_BUDGET):
            args = {"operation": "byName", "query": key, "limit": PAGE_LIMIT}
            if cursor is not None:
                args["cursor"] = cursor
            self.pages += 1
            try:
                result = self._client._call_tool("kado-search", args)
            except Exception:  # noqa: BLE001 — any failure is "unanswered"
                return None
            items = result.get("items", [])
            found += sum(1 for item in items if _final_segment(item) == key)
            cursor = result.get("nextCursor") or result.get("cursor")
            if not cursor or not items:
                return found
        return None


def _final_segment(item: dict) -> str:
    return _key(str(item.get("path", "")).rsplit("/", 1)[-1])


def make_basename_census(client) -> BasenameCensus:
    return BasenameCensus(client)

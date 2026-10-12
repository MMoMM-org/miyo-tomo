#!/usr/bin/env python3
# version: 0.2.0
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

Kado matches `query.toLowerCase()` as a substring of `name.toLowerCase()` with
no Unicode normalisation and no casefold. So each ask sends the NFC and, when
it differs, the NFD form, each through Python `.lower()` (not casefold, which
would turn "Straße" into "strasse" and match nothing). Hits are unioned by
path, narrowed to exact final-segment equality under the local key (NFC +
casefold, the same normalisation as typed_name_check's inside_inbox; matching
more loosely than Kado is the safe, over-counting direction), and counted as
distinct paths.

Bounds (F3-AC7): one name search per distinct basename (cache keyed by the
local key), plus one more only for a name whose NFC and NFD forms differ, so at
most two per basename; ASCII names cost one. At most PAGE_BUDGET pages per
search; any variant that errors or exhausts its budget makes the whole count
None. A page is fetched through `client._call_tool` because
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
            self._cache[key] = self._search(basename, key)
        return self._cache[key]

    def _search(self, name: str, key: str) -> int | None:
        if "*" in key or "?" in key:
            return None
        paths: set[str] = set()
        for query in _query_variants(name):
            if not self._drain(query, paths):
                return None
        return sum(1 for path in paths if _final_segment(path) == key)

    def _drain(self, query: str, paths: set[str]) -> bool:
        self.searches += 1
        cursor = None
        for _ in range(PAGE_BUDGET):
            args = {"operation": "byName", "query": query, "limit": PAGE_LIMIT}
            if cursor is not None:
                args["cursor"] = cursor
            self.pages += 1
            try:
                result = self._client._call_tool("kado-search", args)
            except Exception:  # noqa: BLE001 — any failure is "unanswered"
                return False
            items = result.get("items", [])
            paths.update(str(item.get("path", "")) for item in items)
            cursor = result.get("nextCursor") or result.get("cursor")
            if not cursor or not items:
                return True
        return False


def _query_variants(name: str) -> list[str]:
    nfc = unicodedata.normalize("NFC", name).lower()
    nfd = unicodedata.normalize("NFD", name).lower()
    return [nfc] if nfc == nfd else [nfc, nfd]


def _final_segment(path: str) -> str:
    return _key(path.rsplit("/", 1)[-1])


def make_basename_census(client) -> BasenameCensus:
    return BasenameCensus(client)

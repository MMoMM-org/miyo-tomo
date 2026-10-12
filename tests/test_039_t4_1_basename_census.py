#!/usr/bin/env python3
# version: 0.1.0
"""test_039_t4_1_basename_census.py — spec 039 T4.1 (F3-AC7, SDD K3 / ADR-3).

The census asks Kado `byName` once per distinct case-folded basename, filters
the substring hits down to exact final-segment equality, and reports a raw
vault count, or None when Kado did not answer or the 2-page budget ran out.

Mechanisms falsified, one per test:
- substring leak: `photo.png` must not count `old-photo.png`
- case/Unicode blindness: `Karte.PNG` counts for `karte.png`; NFD == NFC
- unbounded lookups: repeats (any casing) cost one search
- error read as zero: an error is None and the None is cached, never 0
- unbounded paging: a third page is never requested
CON-7: a counting fake stands in for Kado; no network.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tomo" / "scripts"))

from lib.basename_census import PAGE_BUDGET, make_basename_census  # noqa: E402


class FakeKado:
    """Serves `kado-search` byName pages from a list of page item-lists."""

    def __init__(self, pages_by_query=None, error=None):
        self.pages_by_query = pages_by_query or {}
        self.error = error
        self.calls = []

    def _call_tool(self, tool_name, arguments):
        self.calls.append((tool_name, dict(arguments)))
        if self.error:
            raise self.error
        pages = self.pages_by_query.get(arguments["query"], [[]])
        idx = int(arguments.get("cursor") or 0)
        result = {"items": [{"path": p} for p in pages[idx]]}
        if idx + 1 < len(pages):
            result["nextCursor"] = str(idx + 1)
        return result


def test_substring_hits_do_not_count():
    fake = FakeKado({"photo.png": [["a/photo.png", "b/old-photo.png", "photo.png.md"]]})
    census = make_basename_census(fake)
    assert census.count("photo.png") == 1


def test_case_folded_equality():
    fake = FakeKado({"karte.png": [["x/Karte.PNG", "y/karte.png"]]})
    census = make_basename_census(fake)
    assert census.count("karte.png") == 2


def test_unicode_normalisation_nfc_both_sides():
    nfd = unicodedata.normalize("NFD", "Café.png")
    nfc = unicodedata.normalize("NFC", "Café.png")
    fake = FakeKado({nfc.casefold(): [["a/" + nfd]], nfd.casefold(): [["a/" + nfd]]})
    assert make_basename_census(fake).count(nfc) == 1


def test_only_final_segment_is_compared():
    fake = FakeKado({"a.png": [["a.png/inner.png", "dir/a.png"]]})
    assert make_basename_census(fake).count("a.png") == 1


def test_one_search_per_distinct_casefolded_basename():
    fake = FakeKado({"a.png": [["x/a.png"]]})
    census = make_basename_census(fake)
    assert [census.count(n) for n in ("a.png", "A.PNG", "a.png")] == [1, 1, 1]
    assert census.searches == 1 and census.pages == 1
    assert len(fake.calls) == 1
    assert fake.calls[0][1]["operation"] == "byName"


def test_error_is_none_and_cached_as_none_not_zero():
    fake = FakeKado(error=RuntimeError("429"))
    census = make_basename_census(fake)
    assert census.count("a.png") is None
    assert census.count("a.png") is None
    assert len(fake.calls) == 1
    assert census.searches == 1


def test_two_pages_are_read():
    fake = FakeKado({"a.png": [["x/a.png"], ["y/a.png"]]})
    census = make_basename_census(fake)
    assert census.count("a.png") == 2
    assert census.pages == 2


def test_third_page_is_never_requested_and_none_is_cached():
    assert PAGE_BUDGET == 2
    fake = FakeKado({"a.png": [["x/a.png"], ["y/a.png"], ["z/a.png"]]})
    census = make_basename_census(fake)
    assert census.count("a.png") is None
    assert census.count("a.png") is None
    assert len(fake.calls) == 2
    assert census.pages == 2 and census.searches == 1


def test_counters_accumulate_across_basenames():
    fake = FakeKado({"a.png": [["a.png"]], "b.png": [["b.png"], ["c/b.png"]]})
    census = make_basename_census(fake)
    census.count("a.png")
    census.count("b.png")
    assert (census.searches, census.pages) == (2, 3)


def test_glob_characters_are_not_sent_to_kado():
    fake = FakeKado()
    census = make_basename_census(fake)
    assert census.count("a*.png") is None
    assert fake.calls == []

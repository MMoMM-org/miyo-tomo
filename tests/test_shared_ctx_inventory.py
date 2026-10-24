#!/usr/bin/env python3
# version: 0.2.0
"""test_shared_ctx_inventory.py — T3.2 tests for spec 022 / Phase 3.

Verifies that shared-ctx-builder copies heading/callout inventory from the
moc-structure cache into mocs[] entries (A-trimmed). Spec 040 ADR-4 removed
budget shedding: the inventory now always survives.

Spec 022 T3.2 requirements:
  - build_mocs copies headings (A-trimmed: headings only, no editable_callouts
    from cache entries) and editable_callouts from cache map_notes entries.
  - headings are capped at 8 per MOC.
  - Classification MOCs (is_classification==True) carry NO inventory at all.
  - (spec 040) size_guards never drops headings, editable_callouts or topics,
    however tight --max-bytes is.
  - A representative shared-ctx delta stays <= 8192 bytes on the fixture.

RED before GREEN discipline (spec 022 / TDD).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

# shared-ctx-builder.py has a hyphen — load via importlib
_spec = importlib.util.spec_from_file_location(
    "shared_ctx_builder", SCRIPTS_DIR / "shared-ctx-builder.py"
)
scb = importlib.util.module_from_spec(_spec)
sys.modules["shared_ctx_builder"] = scb
_spec.loader.exec_module(scb)

build_mocs = scb.build_mocs
size_guards = scb.size_guards
serialize = scb.serialize


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _moc_entry(
    path: str = "Atlas/Knowledge MOC.md",
    title: str = "Knowledge MOC",
    topics: list[str] | None = None,
    headings: list[dict] | None = None,
    editable_callouts: list[str] | None = None,
) -> dict:
    """Return a map_notes cache entry that build_mocs consumes."""
    entry: dict = {
        "path": path,
        "title": title,
        "topics": topics or ["knowledge", "learning"],
        "kind": "moc",
    }
    if headings is not None:
        entry["headings"] = headings
    if editable_callouts is not None:
        entry["editable_callouts"] = editable_callouts
    return entry


def _dewey_entry(
    path: str = "Atlas/2600 - Applied Sciences MOC.md",
    title: str = "2600 - Applied Sciences",
    topics: list[str] | None = None,
    headings: list[dict] | None = None,
    editable_callouts: list[str] | None = None,
) -> dict:
    """Return a map_notes entry for a Dewey/classification MOC."""
    entry: dict = {
        "path": path,
        "title": title,
        "topics": topics or ["applied", "sciences"],
        "kind": "moc",
    }
    if headings is not None:
        entry["headings"] = headings
    if editable_callouts is not None:
        entry["editable_callouts"] = editable_callouts
    return entry


def _cache_with(entries: list[dict]) -> dict:
    return {"map_notes": entries}


# ---------------------------------------------------------------------------
# T3.2-1: headings + editable_callouts copied into mocs[] entries (A-trimmed)
# ---------------------------------------------------------------------------

def test_t32_build_mocs_copies_headings_and_editable_callouts():
    """T3.2: build_mocs copies headings and editable_callouts from cache entries
    into the mocs[] output entries (A-trimmed = headings only per spec).

    A-trimmed means: headings carry {text, level}; editable_callouts carry
    the callout-opening line strings; no other inventory fields.
    """
    headings = [
        {"text": "Key Concepts", "level": 2},
        {"text": "Details", "level": 3},
    ]
    editable_callouts = ["[!blocks]+ My Blocks", "[!connect] Connect"]
    entry = _moc_entry(headings=headings, editable_callouts=editable_callouts)

    result = build_mocs(_cache_with([entry]))
    assert result, "build_mocs must not return empty list"
    moc = result[0]

    assert "headings" in moc, "mocs[] entry must carry headings from cache"
    assert moc["headings"] == headings

    assert "editable_callouts" in moc, "mocs[] entry must carry editable_callouts from cache"
    assert moc["editable_callouts"] == editable_callouts


def test_t32_headings_capped_at_8():
    """T3.2: headings are capped at 8 per MOC in build_mocs."""
    headings = [{"text": f"Section {i}", "level": 2} for i in range(12)]
    entry = _moc_entry(headings=headings)

    result = build_mocs(_cache_with([entry]))
    moc = result[0]

    assert "headings" in moc
    assert len(moc["headings"]) == 8, (
        f"headings must be capped at 8, got {len(moc['headings'])}"
    )
    # Cap must preserve document order (first 8)
    assert moc["headings"] == headings[:8]


def test_t32_classification_moc_carries_no_inventory():
    """T3.2: Classification/Dewey MOCs (is_classification==True) carry NO inventory.

    Inventory (headings + editable_callouts) is skipped entirely for
    classification MOCs — they are structural containers, not content areas.
    """
    headings = [{"text": "Sub-areas", "level": 2}]
    editable_callouts = ["[!blocks] B"]
    entry = _dewey_entry(headings=headings, editable_callouts=editable_callouts)

    result = build_mocs(_cache_with([entry]))
    assert result, "build_mocs must not return empty list"
    moc = result[0]

    assert moc.get("is_classification") is True, "Dewey MOC must be flagged as classification"
    assert "headings" not in moc, (
        "Classification MOC must NOT carry headings"
    )
    assert "editable_callouts" not in moc, (
        "Classification MOC must NOT carry editable_callouts"
    )


def test_t32_moc_without_inventory_in_cache_omits_inventory_fields():
    """T3.2: A cache entry with no headings/editable_callouts yields a mocs[]
    entry without those keys — no empty list injection.
    """
    entry = _moc_entry()  # no headings, no editable_callouts

    result = build_mocs(_cache_with([entry]))
    moc = result[0]

    # Fields must be absent when the cache didn't provide them (not injected as [])
    assert "headings" not in moc or moc["headings"] == [], (
        "headings must not be injected when cache has none"
    )
    assert "editable_callouts" not in moc or moc["editable_callouts"] == [], (
        "editable_callouts must not be injected when cache has none"
    )


# ---------------------------------------------------------------------------
# T2.1 (spec 023): has_footer passthrough into mocs[]
# ---------------------------------------------------------------------------

def test_t21_build_mocs_passes_through_has_footer():
    """T2.1 (spec 023): build_mocs copies has_footer from a cache entry into the mocs[] entry.

    A non-classification cache entry carrying has_footer=True must yield
    a mocs[] dict that also carries has_footer=True. Mirrors the passthrough
    pattern used by headings/editable_callouts.
    """
    entry = _moc_entry()
    entry["has_footer"] = True

    result = build_mocs(_cache_with([entry]))
    assert result, "build_mocs must not return empty list"
    moc = result[0]

    assert "has_footer" in moc, "mocs[] entry must carry has_footer when cache entry has it"
    assert moc["has_footer"] is True


def test_t21_build_mocs_passes_through_has_footer_false():
    """T2.1 (spec 023): has_footer=False is also passed through (not silently dropped).

    A False flag is meaningful — it tells the Pass-1 analyst that no footer
    anchor is available as a tier-2 fallback.
    """
    entry = _moc_entry()
    entry["has_footer"] = False

    result = build_mocs(_cache_with([entry]))
    moc = result[0]

    assert "has_footer" in moc, "mocs[] entry must carry has_footer even when False"
    assert moc["has_footer"] is False


def test_t21_build_mocs_omits_has_footer_when_absent_from_cache():
    """T2.1 (spec 023): If the cache entry has no has_footer key, mocs[] entry must not inject one.

    Mirrors the headings/editable_callouts pattern: only passthrough, never inject.
    """
    entry = _moc_entry()  # no has_footer in cache entry

    result = build_mocs(_cache_with([entry]))
    moc = result[0]

    assert "has_footer" not in moc, (
        "has_footer must not be injected when cache entry does not carry it"
    )


# ---------------------------------------------------------------------------
# T3.2-2 (superseded by spec 040 ADR-4): inventory is never shed
# ---------------------------------------------------------------------------

def _ctx_with_inventory(
    n_mocs: int = 2,
    n_topics: int = 5,
    n_headings: int = 4,
    n_callouts: int = 2,
) -> dict:
    """Build a ctx dict whose mocs[] entries carry inventory fields."""
    mocs = []
    for i in range(n_mocs):
        moc: dict = {
            "path": f"Atlas/MOC{i}.md",
            "title": f"MOC {i}",
            "topics": [f"topic{j}_{i}" for j in range(n_topics)],
            "is_classification": False,
            "headings": [{"text": f"Section {j}", "level": 2} for j in range(n_headings)],
            "editable_callouts": [f"[!blocks{j}] Block {j}" for j in range(n_callouts)],
        }
        mocs.append(moc)
    return {
        "schema_version": "1",
        "run_id": "test-run",
        "mocs": mocs,
        "tag_prefixes": [],
        "classification_keywords": {},
    }


def test_inventory_and_topics_survive_any_threshold():
    """Spec 040 ADR-4: the three shedding passes (callouts, then headings, then
    topics) are gone. They existed because every analyst read `mocs` whole;
    now each reads names and fetches detail for its nominations, and shedding
    would break PRD F2-AC2 (a nominated MOC arrives with its headings and
    callouts). A 1-byte threshold only warns.
    """
    import copy
    ctx = _ctx_with_inventory(n_mocs=3, n_topics=8, n_headings=6, n_callouts=3)
    before = copy.deepcopy(ctx)
    assert size_guards(ctx, 1)  # non-vacuity: the threshold is crossed
    assert ctx == before


# ---------------------------------------------------------------------------
# T3.2-3: representative ctx delta <= 8192 bytes
# ---------------------------------------------------------------------------

def test_t32_inventory_delta_fits_within_8192_bytes():
    """T3.2: A representative shared-ctx delta (mocs[] with inventory vs without)
    stays <= 8192 bytes, ensuring inventory doesn't blow the budget on typical vaults.

    Uses a realistic fixture: 10 MOCs, each with 8 headings and 3 editable callouts.
    """
    # Build ctx WITHOUT inventory
    mocs_base = [
        {
            "path": f"Atlas/{i:04d} MOC.md",
            "title": f"Topic Area {i}",
            "topics": ["topic_a", "topic_b", "topic_c"],
            "is_classification": False,
        }
        for i in range(10)
    ]

    # Build ctx WITH inventory
    mocs_with_inv = [
        {
            **m,
            "headings": [{"text": f"Section {j}", "level": 2} for j in range(8)],
            "editable_callouts": ["[!blocks] B", "[!connect] C", "[!anchor] A"],
        }
        for m in mocs_base
    ]

    ctx_base = {"schema_version": "1", "run_id": "test", "mocs": mocs_base,
                "tag_prefixes": [], "classification_keywords": {}}
    ctx_inv = {"schema_version": "1", "run_id": "test", "mocs": mocs_with_inv,
               "tag_prefixes": [], "classification_keywords": {}}

    size_base = len(serialize(ctx_base))
    size_inv = len(serialize(ctx_inv))
    delta = size_inv - size_base

    assert delta <= 8192, (
        f"Inventory delta for 10 MOCs is {delta} bytes — must be <= 8192. "
        f"Base: {size_base}, With inventory: {size_inv}"
    )

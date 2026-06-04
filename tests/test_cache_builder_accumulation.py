#!/usr/bin/env python3
# version: 0.1.0
"""test_cache_builder_accumulation.py — Unit tests for cache-builder.py
--accumulation arg (F-34 Phase 3, T3.1).

Verifies that the new --accumulation flag lifts the
unclassified_topic_clusters dict onto the assembled cache, degrades
gracefully on malformed input, and never bumps cache_version.

Spec: docs/XDD/specs/015-msp-condition-b-accumulation/
AC:   A6 (absent → empty dict), ADR-7 (cache_version stays 1)
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# cache-builder.py has a hyphen — load via importlib
_spec = importlib.util.spec_from_file_location(
    "cache_builder", SCRIPTS_DIR / "cache-builder.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

assemble_cache = _mod.assemble_cache
CACHE_VERSION = _mod.CACHE_VERSION


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(data: object, tmp_dir: str, name: str = "accum.json") -> str:
    """Write data as JSON to a temp file and return its path."""
    path = str(Path(tmp_dir) / name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


def _assemble_with_accumulation(accumulation_data: dict | None) -> dict:
    """Call assemble_cache with only accumulation_data set; all others None."""
    return assemble_cache(
        structure_data=None,
        mocs_data=None,
        frontmatter_data=None,
        tags_data=None,
        orphans_data=None,
        accumulation_data=accumulation_data,
        start_time=None,
    )


# ---------------------------------------------------------------------------
# T3.1 — --accumulation lifts clusters onto cache
# ---------------------------------------------------------------------------


def test_accumulation_arg_lifts_clusters_onto_cache():
    """assemble_cache sets cache['unclassified_topic_clusters'] from accumulation_data."""
    clusters = {
        "games": ["alpha-beta-pruning", "minimax"],
        "search": ["alpha-beta-pruning", "minimax", "monte-carlo-tree-search"],
    }

    cache = _assemble_with_accumulation(clusters)

    assert "unclassified_topic_clusters" in cache
    assert cache["unclassified_topic_clusters"] == clusters


# ---------------------------------------------------------------------------
# A6 — absent arg yields empty dict
# ---------------------------------------------------------------------------


def test_accumulation_absent_yields_empty_dict():
    """cache['unclassified_topic_clusters'] is {} when accumulation_data is None (A6)."""
    cache = _assemble_with_accumulation(None)

    assert "unclassified_topic_clusters" in cache
    assert cache["unclassified_topic_clusters"] == {}


# ---------------------------------------------------------------------------
# ADR-7 — cache_version stays 1
# ---------------------------------------------------------------------------


def test_cache_version_unchanged():
    """cache_version remains 1 regardless of accumulation_data presence (ADR-7)."""
    cache_with = _assemble_with_accumulation({"topic": ["note-a"]})
    cache_without = _assemble_with_accumulation(None)

    assert cache_with["cache_version"] == 1
    assert cache_without["cache_version"] == 1
    assert CACHE_VERSION == 1


# ---------------------------------------------------------------------------
# Drift guard — malformed accumulation degrades to empty dict
# ---------------------------------------------------------------------------


def test_malformed_accumulation_json_degrades_to_empty():
    """Non-dict accumulation_data (e.g. a list) degrades to {} without crashing."""
    # A list is syntactically valid JSON but not the expected dict shape
    cache = _assemble_with_accumulation(["not", "a", "dict"])

    assert "unclassified_topic_clusters" in cache
    assert cache["unclassified_topic_clusters"] == {}


# ---------------------------------------------------------------------------
# Regression — existing cache fields unaffected
# ---------------------------------------------------------------------------


def test_existing_cache_fields_present_alongside_accumulation():
    """map_notes, placeholder_mocs, orphans etc. are still present when accumulation is set."""
    clusters = {"games": ["alpha-beta-pruning"]}
    cache = _assemble_with_accumulation(clusters)

    # Fields that must always be present regardless of inputs
    for field in ("cache_version", "last_scan", "map_notes", "placeholder_mocs",
                  "scan_stats", "vault_structure", "classifications",
                  "tag_patterns", "frontmatter_usage", "orphans"):
        assert field in cache, f"expected field {field!r} missing from cache"

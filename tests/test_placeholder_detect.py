#!/usr/bin/env python3
# version: 0.1.0
"""test_placeholder_detect.py — Behavioural tests for lib.placeholder_detect.

Covers T1.3 of spec 021 (MOC-propose consolidation, Phase 1 Cache Foundation).

The new module extracts anchor-stripping + per-note dedup logic from
moc-tree-builder.py's detect_placeholders, but uses the REAL in-scope vault
set as the placeholder denominator (not just the 89-MOC set). This is the
fix for the 224 false-positive inflation: [[Note#^ref]] into a real vault
note was counted as a placeholder because the old denominator only contained
MOC paths.

Expected outcomes on real data: 397 raw → ~171 actual placeholders.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.placeholder_detect import detect_placeholders  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _moc(path: str, links: list[str]) -> dict:
    return {"path": path, "linked_notes_raw": links}


def _mocs(*entries: tuple[str, list[str]]) -> dict[str, dict]:
    return {path: _moc(path, links) for path, links in entries}


# ──────────────────────────────────────────────────────────────────────────────
# Behavioral equivalents of the 10 existing test cases (anchor-strip + dedup)
# ──────────────────────────────────────────────────────────────────────────────

def test_anchored_link_to_existing_note_is_not_placeholder():
    """Core F-34 bug: block-ref into a real note must not be a placeholder."""
    mocs = _mocs(("Atlas/200 Maps/200 Maps.md", ["LYT Classification System#^9c2026"]))
    vault = {"Atlas/200 Maps/200 Maps.md", "Atlas/LYT Classification System.md"}
    known_mocs: set[str] = set()
    assert detect_placeholders(mocs, known_mocs, vault) == []


def test_same_note_anchor_is_not_placeholder():
    mocs = _mocs(("Atlas/Home.md", ["#^block123", "#Heading"]))
    vault = {"Atlas/Home.md"}
    known_mocs: set[str] = set()
    assert detect_placeholders(mocs, known_mocs, vault) == []


def test_multiple_anchors_into_one_missing_note_dedupe_to_one():
    mocs = _mocs((
        "Atlas/Home.md",
        ["Ghost Note#^a1", "Ghost Note#^b2", "Ghost Note#Heading"],
    ))
    vault = {"Atlas/Home.md"}
    known_mocs: set[str] = set()
    result = detect_placeholders(mocs, known_mocs, vault)
    assert len(result) == 1
    assert result[0]["target"] == "Ghost Note"
    assert result[0]["referenced_by"] == "Atlas/Home.md"


def test_clean_dead_link_still_detected():
    mocs = _mocs(("Atlas/Home.md", ["Totally Missing MOC"]))
    vault = {"Atlas/Home.md"}
    known_mocs: set[str] = set()
    result = detect_placeholders(mocs, known_mocs, vault)
    assert result == [{"target": "Totally Missing MOC", "referenced_by": "Atlas/Home.md"}]


def test_anchored_dead_link_reported_as_bare_note():
    """Anchor is stripped in the reported target, not just the test."""
    mocs = _mocs(("Atlas/Home.md", ["Missing#^x9"]))
    vault = {"Atlas/Home.md"}
    known_mocs: set[str] = set()
    result = detect_placeholders(mocs, known_mocs, vault)
    assert result == [{"target": "Missing", "referenced_by": "Atlas/Home.md"}]


def test_link_to_existing_moc_is_not_placeholder():
    mocs = _mocs(
        ("Atlas/Home.md", ["Sub MOC"]),
        ("Atlas/Sub MOC.md", []),
    )
    vault = {"Atlas/Home.md", "Atlas/Sub MOC.md"}
    known_mocs = {"Atlas/Sub MOC.md"}
    assert detect_placeholders(mocs, known_mocs, vault) == []


def test_empty_mocs_returns_empty():
    assert detect_placeholders({}, set(), set()) == []


def test_moc_with_no_links_returns_empty():
    mocs = _mocs(("Atlas/Home.md", []))
    vault = {"Atlas/Home.md"}
    assert detect_placeholders(mocs, set(), vault) == []


def test_dedup_across_two_mocs():
    """Same missing note linked from two different MOCs → two entries (different referenced_by)."""
    mocs = _mocs(
        ("Atlas/Home.md", ["Ghost Note"]),
        ("Atlas/Sub.md", ["Ghost Note"]),
    )
    vault = {"Atlas/Home.md", "Atlas/Sub.md"}
    known_mocs: set[str] = set()
    result = detect_placeholders(mocs, known_mocs, vault)
    assert len(result) == 2
    targets = {r["target"] for r in result}
    refs = {r["referenced_by"] for r in result}
    assert targets == {"Ghost Note"}
    assert refs == {"Atlas/Home.md", "Atlas/Sub.md"}


def test_dedup_same_moc_same_note_many_anchors():
    """Multiple anchored refs into the same missing note from one MOC → ONE placeholder."""
    mocs = _mocs(("Atlas/Home.md", ["X#^a", "X#^b", "X#^c", "X#Heading"]))
    vault = {"Atlas/Home.md"}
    known_mocs: set[str] = set()
    result = detect_placeholders(mocs, known_mocs, vault)
    assert len(result) == 1
    assert result[0]["target"] == "X"


# ──────────────────────────────────────────────────────────────────────────────
# NEW: denominator = real in-scope vault (the 224-false-positive fix)
# ──────────────────────────────────────────────────────────────────────────────

def test_anchored_link_to_existing_in_scope_note_is_not_placeholder():
    """Key T1.3 requirement: anchored wikilink into a real vault note is NOT a placeholder.

    In the old code the denominator was all_vault_paths (all discovered notes).
    In moc-tree-builder's detect_placeholders it was called with all_vault_paths which
    was the full discovered set, but in the MSP accumulation context only the 89-MOC
    set was passed. This test verifies the new module accepts in_scope_vault_paths
    as the denominator and correctly resolves the link.
    """
    mocs = _mocs(("Atlas/Home.md", ["My Journal#^abc123"]))
    # My Journal.md IS in the in-scope vault set (a real note, not a MOC)
    in_scope = {"Atlas/Home.md", "Calendar/My Journal.md"}
    known_mocs: set[str] = set()
    result = detect_placeholders(mocs, known_mocs, in_scope)
    assert result == []


def test_plain_link_to_existing_in_scope_note_is_not_placeholder():
    """Plain wikilink (no anchor) to a real in-scope note must not be a placeholder."""
    mocs = _mocs(("Atlas/Home.md", ["My Research Note"]))
    in_scope = {"Atlas/Home.md", "Research/My Research Note.md"}
    known_mocs: set[str] = set()
    result = detect_placeholders(mocs, known_mocs, in_scope)
    assert result == []


def test_link_to_genuinely_missing_note_is_placeholder():
    """A link to a note absent from in_scope_vault_paths AND not a known MOC IS a placeholder."""
    mocs = _mocs(("Atlas/Home.md", ["Nonexistent Note"]))
    # "Nonexistent Note" is not in the vault, not a MOC
    in_scope = {"Atlas/Home.md", "Other/Real Note.md"}
    known_mocs: set[str] = set()
    result = detect_placeholders(mocs, known_mocs, in_scope)
    assert result == [{"target": "Nonexistent Note", "referenced_by": "Atlas/Home.md"}]


def test_known_moc_by_name_not_path_is_not_placeholder():
    """Known MOC matched by filename (case-insensitive) is not a placeholder."""
    mocs = _mocs(("Atlas/Home.md", ["atlas maps"]))
    # "atlas maps" lowercase matches "Atlas Maps.md"
    in_scope = {"Atlas/Home.md"}
    known_mocs = {"Atlas/Atlas Maps.md"}
    result = detect_placeholders(mocs, known_mocs, in_scope)
    assert result == []

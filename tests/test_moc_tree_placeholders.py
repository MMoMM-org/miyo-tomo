#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_tree_placeholders.py — Behavioural tests for placeholder detection.

Regression guard for the F-34 over-detection bug: `detect_placeholders` counted
anchored wikilinks (`[[Note#^blockid]]`, `[[Note#Heading]]`) as placeholder MOCs
because the raw target (with the `#…` anchor) never matched the anchor-free name
in the known-vault set. On the live ~281-note vault this inflated placeholder_mocs
to 397 (mostly block-ref false positives), blowing the 15 KB shared-ctx budget and
starving the accumulation_index — so Condition B never fired.

These tests assert the anchor-stripping + per-note dedup behaviour directly:
  - anchored links into an existing note -> NOT a placeholder
  - same-note anchors ("#^id" / "#Heading") -> NOT a placeholder
  - multiple anchors into one genuinely-missing note -> ONE placeholder
  - a clean dead link -> still detected as a placeholder
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "moc-tree-builder.py"

_spec = importlib.util.spec_from_file_location("moc_tree_builder", SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

detect_placeholders = _mod.detect_placeholders
strip_link_anchor = _mod.strip_link_anchor


def _moc(path: str, links: list[str]) -> dict:
    return {"path": path, "linked_notes_raw": links}


def _mocs(*entries: tuple[str, list[str]]) -> dict[str, dict]:
    return {path: _moc(path, links) for path, links in entries}


# ──────────────────────────────────────────────────────────────────────────────
# strip_link_anchor
# ──────────────────────────────────────────────────────────────────────────────

def test_strip_block_anchor():
    assert strip_link_anchor("LYT Classification System#^9c2026") == "LYT Classification System"


def test_strip_heading_anchor():
    assert strip_link_anchor("2000 - Knowledge Management#Some Heading") == "2000 - Knowledge Management"


def test_strip_same_note_anchor_yields_empty():
    assert strip_link_anchor("#^9c2026") == ""
    assert strip_link_anchor("#Heading") == ""


def test_strip_no_anchor_is_identity():
    assert strip_link_anchor("Plain Note") == "Plain Note"


# ──────────────────────────────────────────────────────────────────────────────
# detect_placeholders — anchored links into existing notes
# ──────────────────────────────────────────────────────────────────────────────

def test_anchored_link_to_existing_note_is_not_placeholder():
    """The core F-34 bug: a block-ref into a real note must not be a placeholder."""
    mocs = _mocs(("Atlas/200 Maps/200 Maps.md", ["LYT Classification System#^9c2026"]))
    vault = {"Atlas/200 Maps/200 Maps.md", "Atlas/LYT Classification System.md"}
    assert detect_placeholders(mocs, vault) == []


def test_same_note_anchor_is_not_placeholder():
    mocs = _mocs(("Atlas/Home.md", ["#^block123", "#Heading"]))
    vault = {"Atlas/Home.md"}
    assert detect_placeholders(mocs, vault) == []


def test_multiple_anchors_into_one_missing_note_dedupe_to_one():
    mocs = _mocs((
        "Atlas/Home.md",
        ["Ghost Note#^a1", "Ghost Note#^b2", "Ghost Note#Heading"],
    ))
    vault = {"Atlas/Home.md"}
    result = detect_placeholders(mocs, vault)
    assert len(result) == 1
    assert result[0]["target"] == "Ghost Note"
    assert result[0]["referenced_by"] == "Atlas/Home.md"


def test_clean_dead_link_still_detected():
    mocs = _mocs(("Atlas/Home.md", ["Totally Missing MOC"]))
    vault = {"Atlas/Home.md"}
    result = detect_placeholders(mocs, vault)
    assert result == [{"target": "Totally Missing MOC", "referenced_by": "Atlas/Home.md"}]


def test_anchored_dead_link_reported_as_bare_note():
    """Anchor is stripped in the reported target too, not just the test."""
    mocs = _mocs(("Atlas/Home.md", ["Missing#^x9"]))
    vault = {"Atlas/Home.md"}
    result = detect_placeholders(mocs, vault)
    assert result == [{"target": "Missing", "referenced_by": "Atlas/Home.md"}]


def test_link_to_existing_moc_is_not_placeholder():
    mocs = _mocs(
        ("Atlas/Home.md", ["Sub MOC"]),
        ("Atlas/Sub MOC.md", []),
    )
    vault = {"Atlas/Home.md", "Atlas/Sub MOC.md"}
    assert detect_placeholders(mocs, vault) == []

#!/usr/bin/env python3
# version: 0.2.0
"""test_instruction_render_link_to_moc.py — link_to_moc emission for both flows.

Verifies that _build_link_to_moc_actions emits down-links correctly:
  1. Suggestion flow: supporting_items are SNN IDs → link_to_moc emitted
  2. MOC proposal flow: children baked into rendered body → NO link_to_moc emitted

Also tests the {{children}} token builder used for MOC proposal rendering.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

spec = importlib.util.spec_from_file_location("instruction_render", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

_build_link_to_moc_actions = mod._build_link_to_moc_actions
_parse_supporting_items = mod._parse_supporting_items


def _make_confirmed_suggestion(sid: str, title: str) -> dict:
    return {
        "id": sid,
        "action": "move_note",
        "title": title,
        "source_path": f"{title}.md",
        "parent_mocs": [],
    }


def _make_create_moc_suggestion(title: str, supporting: str, parent: str = "") -> dict:
    return {
        "id": "S99",
        "action": "create_moc",
        "title": title,
        "parent_moc": parent,
        "parent_mocs": [parent] if parent else [],
        "supporting_items": supporting,
    }


def _make_create_moc_proposal(title: str, children: list[str], parent: str = "") -> dict:
    return {
        "id": "MOC1",
        "action": "create_moc",
        "title": title,
        "parent_moc": parent,
        "parent_mocs": [parent] if parent else [],
        "supporting_items": children,
        "override_preserve_existing_up": False,
    }


# ── Suggestion flow tests ────────────────────────────────────────────────────

def test_suggestion_flow_emits_downlinks():
    """SNN IDs in supporting_items resolve via id_index → link_to_moc emitted."""
    confirmed = [
        _make_confirmed_suggestion("S02", "Thought Collisions"),
        _make_confirmed_suggestion("S06", "Map of Content"),
        _make_create_moc_suggestion("PKM (MOC)", "S02, S06"),
    ]
    actions = _build_link_to_moc_actions(confirmed, [0])
    downlinks = [a for a in actions if a["target_moc"] == "PKM (MOC)"]
    titles = {a["source_note_title"] for a in downlinks}
    assert "Thought Collisions" in titles
    assert "Map of Content" in titles


def test_suggestion_flow_skips_rejected():
    """SNN ID not in confirmed list → no link emitted (user rejected that item)."""
    confirmed = [
        _make_confirmed_suggestion("S02", "Thought Collisions"),
        _make_create_moc_suggestion("PKM (MOC)", "S02, S03"),
    ]
    actions = _build_link_to_moc_actions(confirmed, [0])
    downlinks = [a for a in actions if a["target_moc"] == "PKM (MOC)"]
    titles = {a["source_note_title"] for a in downlinks}
    assert "Thought Collisions" in titles
    assert len(downlinks) == 1, "S03 was rejected, should not emit"


def test_dedup_across_parent_and_supporting():
    """Same (target_moc, source_title) pair from both parent_mocs and supporting_items."""
    child = _make_confirmed_suggestion("S02", "Thought Collisions")
    child["parent_mocs"] = ["PKM (MOC)"]
    moc = _make_create_moc_suggestion("PKM (MOC)", "S02")
    confirmed = [child, moc]
    actions = _build_link_to_moc_actions(confirmed, [0])
    pkm_links = [a for a in actions if a["target_moc"] == "PKM (MOC)"
                 and a["source_note_title"] == "Thought Collisions"]
    assert len(pkm_links) == 1, "Should deduplicate"


# ── MOC proposal flow tests ─────────────────────────────────────────────────

def test_moc_proposal_no_link_to_moc():
    """MOC proposal children are baked into body → zero link_to_moc for down-links."""
    confirmed = [
        _make_create_moc_proposal(
            "Idea Emergence (MOC)",
            ["Thought Collisions", "Map of Content", "Notemaking"],
        ),
    ]
    actions = _build_link_to_moc_actions(confirmed, [0])
    downlinks = [a for a in actions if a["target_moc"] == "Idea Emergence (MOC)"]
    assert len(downlinks) == 0, "MOC proposal children should NOT emit link_to_moc"


def test_moc_proposal_parent_link_still_emitted():
    """MOC proposal's own parent_mocs still produce link_to_moc (Pass 1)."""
    confirmed = [
        _make_create_moc_proposal(
            "Idea Emergence (MOC)",
            ["Thought Collisions"],
            parent="Knowledge Structure (MOC)",
        ),
    ]
    actions = _build_link_to_moc_actions(confirmed, [0])
    parent_links = [a for a in actions if a["target_moc"] == "Knowledge Structure (MOC)"]
    assert len(parent_links) == 1
    assert parent_links[0]["source_note_title"] == "Idea Emergence (MOC)"


def test_moc_proposal_empty_children():
    """No children → no link_to_moc emitted."""
    confirmed = [
        _make_create_moc_proposal("Empty (MOC)", []),
    ]
    actions = _build_link_to_moc_actions(confirmed, [0])
    assert len(actions) == 0


# ── {{children}} token builder tests ────────────────────────────────────────

def test_children_token_from_stems():
    """_parse_supporting_items on a stem list returns stems as-is."""
    stems = _parse_supporting_items(["Thought Collisions", "Map of Content"])
    assert stems == ["Thought Collisions", "Map of Content"]


def test_children_token_value_format():
    """Children value has callout-prefixed bullets."""
    stems = ["Thought Collisions", "Map of Content"]
    value = "\n".join(f"> - [[{s}]]" for s in stems)
    assert value == "> - [[Thought Collisions]]\n> - [[Map of Content]]"


def test_children_token_empty():
    """Empty supporting_items → empty children value."""
    stems = _parse_supporting_items(None)
    assert stems == []
    value = "\n".join(f"> - [[{s}]]" for s in stems)
    assert value == ""

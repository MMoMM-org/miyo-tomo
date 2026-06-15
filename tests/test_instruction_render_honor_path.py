#!/usr/bin/env python3
# version: 0.1.0
"""test_instruction_render_honor_path.py — T5.1: _emit stamps + threads the Pass-1 anchor.

Covers:
  1. Honor path: action with a Pass-1 anchor is emitted with that anchor stamped;
     resolve_section_names does NOT re-resolve it (AC-12/AC-13).
  2. Back-compat: no Pass-1 anchor → heuristic runs as before.
  3. EC-6: user-edited heading absent from MOC → heading-typed anchor passes through
     (resolve_section_names skips non-callout anchors → Hashi creates the new H2).
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
resolve_section_names = mod.resolve_section_names


# ── Fixture helpers ──────────────────────────────────────────────────────────

def _make_atomic_item(
    sid: str,
    title: str,
    parent_mocs: list[str],
    candidate_mocs: list[dict] | None = None,
) -> dict:
    return {
        "id": sid,
        "action": "create_atomic_note",
        "title": title,
        "source_path": f"inbox/{title}.md",
        "parent_mocs": parent_mocs,
        "candidate_mocs": candidate_mocs or [],
    }


def _callout_anchor(value: str, placement: str = "inside") -> dict:
    return {"type": "callout", "value": value, "placement": placement}


def _heading_anchor(value: str, placement: str = "after") -> dict:
    return {"type": "heading", "value": value, "placement": placement}


# ── Test 1: honor path — Pass-1 anchor is stamped on the action ──────────────

def test_pass1_callout_anchor_stamped_on_action():
    """AC-12/AC-13: action carries the Pass-1 anchor (type+value+placement)."""
    anchor = _callout_anchor("blocks", "inside")
    item = _make_atomic_item(
        "S01",
        "First Principles Thinking",
        parent_mocs=["Mental Models (MOC)"],
        candidate_mocs=[
            {"path": "Mental Models (MOC).md", "score": 0.9, "pre_check": "pass", "anchor": anchor},
        ],
    )
    actions = _build_link_to_moc_actions([item], [0])
    link_actions = [a for a in actions if a["action"] == "link_to_moc"]
    assert len(link_actions) == 1
    a = link_actions[0]
    assert a["anchor"]["type"] == "callout"
    assert a["anchor"]["value"] == "blocks"
    assert a["placement"] == "inside"


# ── Test 2: honor path — resolve_section_names skips already-populated anchor ─

def test_pass1_anchor_not_re_resolved_by_heuristic():
    """AC-13: resolve_section_names skips actions whose anchor.value is truthy."""
    anchor = _callout_anchor("blocks", "inside")
    item = _make_atomic_item(
        "S01",
        "First Principles Thinking",
        parent_mocs=["Mental Models (MOC)"],
        candidate_mocs=[
            {"path": "Mental Models (MOC).md", "score": 0.9, "pre_check": "pass", "anchor": anchor},
        ],
    )
    actions = _build_link_to_moc_actions([item], [0])
    # Populate target_moc_path so resolve_section_names would normally run on this action
    for a in actions:
        if a["action"] == "link_to_moc":
            a["target_moc_path"] = "Vault/Mental Models (MOC).md"

    # A fake client that would resolve to a DIFFERENT anchor if called
    class _TrackingClient:
        def __init__(self):
            self.called = False
        def read_note(self, *args, **kwargs):
            self.called = True
            return "> [!connect] Navigation\n"

    fake_client = _TrackingClient()
    resolve_section_names(actions, fake_client, ["blocks", "connect"])

    link_actions = [a for a in actions if a["action"] == "link_to_moc"]
    assert len(link_actions) == 1
    # Anchor must remain as stamped — not overwritten by the heuristic
    assert link_actions[0]["anchor"]["value"] == "blocks"
    assert link_actions[0]["placement"] == "inside"
    # The client must NOT have been called for this action (value was already set)
    assert not fake_client.called


# ── Test 3: back-compat — no Pass-1 anchor → heuristic is invoked ────────────

def test_no_pass1_anchor_falls_to_heuristic():
    """Back-compat: item with no candidate_mocs anchor → anchor.value stays null until heuristic."""
    item = _make_atomic_item(
        "S02",
        "Zetteln Method",
        parent_mocs=["PKM (MOC)"],
        candidate_mocs=[
            # anchor absent → heuristic should run
            {"path": "PKM (MOC).md", "score": 0.8, "pre_check": "pass"},
        ],
    )
    actions = _build_link_to_moc_actions([item], [0])
    link_actions = [a for a in actions if a["action"] == "link_to_moc"]
    assert len(link_actions) == 1
    a = link_actions[0]
    # Default: callout type, null value → heuristic will populate value
    assert a["anchor"]["type"] == "callout"
    assert a["anchor"]["value"] is None
    assert a["placement"] == "after"


def test_no_candidate_mocs_at_all_falls_to_heuristic():
    """Back-compat: candidate_mocs absent entirely → default anchor emitted."""
    item = _make_atomic_item(
        "S03",
        "Zetteln Method",
        parent_mocs=["PKM (MOC)"],
        candidate_mocs=None,
    )
    actions = _build_link_to_moc_actions([item], [0])
    link_actions = [a for a in actions if a["action"] == "link_to_moc"]
    assert len(link_actions) == 1
    a = link_actions[0]
    assert a["anchor"]["type"] == "callout"
    assert a["anchor"]["value"] is None


# ── Test 4: EC-6 — user-edited heading not in MOC → heading anchor passes through

def test_ec6_user_edited_heading_absent_from_moc_passes_through():
    """EC-6: user edits placement to a heading that doesn't exist in the MOC.
    Pass-1 (or post-edit) produces a heading-typed anchor with a non-null value.
    _emit stamps it. resolve_section_names skips non-callout anchors (line:1650).
    Hashi then creates the new H2 (no re-resolution in Pass-2).
    """
    # User changed the anchor heading to "Reasoning Biases" — not present in MOC
    anchor = _heading_anchor("Reasoning Biases", "after")
    item = _make_atomic_item(
        "S04",
        "First Principles Thinking",
        parent_mocs=["Mental Models (MOC)"],
        candidate_mocs=[
            {"path": "Mental Models (MOC).md", "score": 0.9, "pre_check": "pass", "anchor": anchor},
        ],
    )
    actions = _build_link_to_moc_actions([item], [0])
    link_actions = [a for a in actions if a["action"] == "link_to_moc"]
    assert len(link_actions) == 1
    a = link_actions[0]
    # Heading anchor stamped as-is
    assert a["anchor"]["type"] == "heading"
    assert a["anchor"]["value"] == "Reasoning Biases"
    assert a["placement"] == "after"

    # resolve_section_names must NOT overwrite it (heading type is skipped at line:1650)
    class _MustNotCallClient:
        def read_note(self, *args, **kwargs):
            raise AssertionError("resolve_section_names should not call Kado for a heading anchor")

    for a in actions:
        if a["action"] == "link_to_moc":
            a["target_moc_path"] = "Vault/Mental Models (MOC).md"

    resolve_section_names(actions, _MustNotCallClient(), ["blocks", "connect"])

    a = link_actions[0]
    assert a["anchor"]["type"] == "heading"
    assert a["anchor"]["value"] == "Reasoning Biases"


# ── Test 5: supporting_items pass-2 down-links always get null anchor ─────────

def test_pass2_supporting_items_downlinks_get_null_anchor():
    """Pass-2 down-links (supporting_items) have no per-candidate anchor → null anchor."""
    child = _make_atomic_item("S10", "Deep Work", parent_mocs=[], candidate_mocs=[])
    child["id"] = "S10"
    moc_item = {
        "id": "S99",
        "action": "create_moc",
        "title": "Productivity (MOC)",
        "parent_mocs": [],
        "supporting_items": "S10",
        "candidate_mocs": [],
    }
    actions = _build_link_to_moc_actions([child, moc_item], [0])
    downlinks = [a for a in actions if a["target_moc"] == "Productivity (MOC)"]
    assert len(downlinks) == 1
    # No Pass-1 anchor for supporting_items → default callout null
    assert downlinks[0]["anchor"]["type"] == "callout"
    assert downlinks[0]["anchor"]["value"] is None

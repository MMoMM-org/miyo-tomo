#!/usr/bin/env python3
# version: 0.1.0
"""ADR-026 — proposed-MOC member_ids must reference wire suggestion ids.

Root cause (Cooking-MOC off-by-one): the reducer builds proposed_mocs `items`
in the per-SOURCE `section_id` space (S{source_idx}, via atomic_key), but the
wire keys each suggestion by the flat per-ATOMIC `suggestion_id`. The two spaces
diverge whenever a daily-only source sits between atomics (its source index is
consumed but it produces no atomic). build_wire_payload copied `items` verbatim
into `member_ids`, so a member pointed at the WRONG suggestion in the wire.

These tests build a doc with that drift (a section whose id S02 carries the
first atomic S01) and assert:
  - every member_id references an existing wire suggestion id (falsifies the bug);
  - the member is remapped from the section-space id to the flat id (S02 -> S01);
  - no drift (section_id == suggestion_id) leaves member_ids unchanged.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load():
    spec = importlib.util.spec_from_file_location("suggestions_render_ns", SCRIPTS_DIR / "suggestions-render.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load()


def _atomic(sid: str, title: str, tags: list[str]) -> dict:
    return {
        "kind": "create_atomic_note", "suggestion_id": sid,
        "rendered_md": f"**Suggested name:** {title}",
        "item": {"title": title, "template": "t_note_tomo.md",
                 "location": "Atlas/202 Notes/", "tags": tags, "audio_peer": None,
                 "worthiness": 0.8, "suppressed": False, "force_atomic": False},
        "candidate_mocs": [],
    }


def _doc_with_drift() -> dict:
    """A daily-only source consumed S01, so the single atomic lives in section
    S02 but carries flat suggestion_id S01. The Cooking MOC references the note
    by its section-space id (S02)."""
    return {
        "schema_version": "1", "generated": "g", "run_id": "r", "profile": "miyo",
        "source_items": 2, "conventions": {"moc_suffix": " (MOC)"},
        "sections": [
            {"id": "S02", "stem": "japanische-gerichte",
             "actions": [_atomic("S01", "Japanische Gerichte", ["topic/japan"])]},
        ],
        "proposed_mocs": [
            {"topic": "Cooking", "name": "Cooking (MOC)", "parent": "Root",
             "items": ["S02"], "tags": ["topic/japan"], "reason": "cluster"},
        ],
        "needs_attention": [],
    }


def test_member_ids_reference_existing_suggestions():
    wire = _MOD.build_wire_payload(_doc_with_drift())
    sugg_ids = {s["id"] for s in wire["suggestions"]}
    for pm in wire["proposed_mocs"]:
        for mid in pm["member_ids"]:
            assert mid in sugg_ids, (
                f"member_id {mid!r} references no wire suggestion (have {sorted(sugg_ids)})"
            )


def test_member_id_remapped_section_to_flat():
    wire = _MOD.build_wire_payload(_doc_with_drift())
    cooking = next(pm for pm in wire["proposed_mocs"] if pm["name"] == "Cooking (MOC)")
    # S02 (section-space) must resolve to S01 (flat) = Japanische Gerichte.
    assert cooking["member_ids"] == ["S01"], cooking["member_ids"]
    japanese = next(s for s in wire["suggestions"] if s["id"] == "S01")
    assert japanese["stem"] == "japanische-gerichte"


def test_no_drift_leaves_member_ids_unchanged():
    """When section_id == suggestion_id (no daily-only source), items are unchanged."""
    doc = _doc_with_drift()
    doc["sections"][0]["id"] = "S01"          # section id now matches the atomic
    doc["proposed_mocs"][0]["items"] = ["S01"]
    wire = _MOD.build_wire_payload(doc)
    assert wire["proposed_mocs"][0]["member_ids"] == ["S01"]


def test_multi_atomic_section_key_remaps():
    """F-41 multi-atomic: the 2nd atomic keys as S02#1 and must remap to its flat id."""
    doc = _doc_with_drift()
    doc["sections"][0]["actions"].append(_atomic("S05", "Second Atomic", ["topic/x"]))
    # A MOC referencing the 2nd atomic by its atomic_key (section_id#1).
    doc["proposed_mocs"].append(
        {"topic": "X", "name": "X (MOC)", "parent": "Root",
         "items": ["S02#1"], "tags": ["topic/x"], "reason": "c"})
    wire = _MOD.build_wire_payload(doc)
    xmoc = next(pm for pm in wire["proposed_mocs"] if pm["name"] == "X (MOC)")
    assert xmoc["member_ids"] == ["S05"], xmoc["member_ids"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))

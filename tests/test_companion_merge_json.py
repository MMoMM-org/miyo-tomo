#!/usr/bin/env python3
# version: 0.1.0
"""test_companion_merge_json.py — ADR-026 companion merge from two edited wires.

The markdown companion defers the primary's force-atomic'd items to a fan doc and
merges both. Under JSON-only (Hashi edits both wires), build_from_wire_companion
combines the two wires and runs build_from_wire once. Covers:
  - the primary's deferred (suppressed+force_atomic) items are REPLACED by the fan's
    resolved ones → no leftover pending_fan_resolutions;
  - confirmed = primary approved + fan resolved; fan ids re-namespaced (no collision);
  - same-name proposed MOCs from primary + fan merge; daily/tag-handler from primary.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("sp", SCRIPTS_DIR / "suggestion-parser.py")
_sp = importlib.util.module_from_spec(_spec)
sys.modules["sp"] = _sp
_spec.loader.exec_module(_sp)

build_from_wire_companion = _sp.build_from_wire_companion


def _sugg(sid, stem, *, decision="approve", suppressed=False, force_atomic=False, mocs=None):
    return {
        "id": sid, "stem": stem, "title": stem.title(), "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/", "tags": [], "audio_peer": None,
        "decision": decision, "keep_source": False, "delete_source": False,
        "force_atomic": force_atomic, "suppressed": suppressed, "worthiness": 0.7,
        "candidate_mocs": mocs or [],
    }


def _primary():
    return {
        "schema_version": "1", "generated": "g", "run_id": "r", "profile": "miyo",
        "source_items": 4, "emit_digest": "sha256:" + "0" * 64,
        "suggestions": [
            _sugg("S01", "alpha"),                                        # approved atomic
            _sugg("S02", "beta", decision="skip", suppressed=True, force_atomic=True),   # deferred
            _sugg("S03", "gamma", decision="skip", suppressed=True, force_atomic=True),  # deferred
        ],
        "proposed_mocs": [
            {"id": "M01", "topic": "Widgets", "name": "Widgets (MOC)", "parent": "Root",
             "member_ids": ["S01"], "decision": "approve"},
        ],
        "daily_updates": [{"date": "2026-07-08", "trackers": [], "log_entries": [], "log_links": []}],
        "tag_handler_groups": [],
    }


def _fan():
    # fan resolves the two deferred stems (un-suppressed, approve), reusing S## ids
    return {
        "schema_version": "1", "generated": "g", "run_id": "r2", "profile": "miyo",
        "source_items": 2, "emit_digest": "sha256:" + "1" * 64,
        "suggestions": [
            _sugg("S01", "beta", mocs=[]),   # NOTE: fan reuses S01 → must not collide with primary S01
            _sugg("S02", "gamma", mocs=[]),
        ],
        "proposed_mocs": [
            {"id": "M01", "topic": "Widgets", "name": "Widgets (MOC)", "parent": "Root",
             "member_ids": ["S01"], "decision": "approve"},   # same-name MOC as primary
        ],
        "daily_updates": [],
        "tag_handler_groups": [],
    }


def test_companion_merges_primary_and_fan_no_pending():
    out = build_from_wire_companion(_primary(), _fan(), "t_moc")
    ci = out["confirmed_items"]
    atomic = [c for c in ci if c.get("action") != "create_moc"]
    mocs = [c for c in ci if c.get("action") == "create_moc"]
    stems = sorted(c["source_path"] for c in atomic)
    # alpha (primary approved) + beta + gamma (fan-resolved) = 3 atomics; deferred replaced.
    assert stems == ["alpha", "beta", "gamma"], stems
    assert out["pending_fan_resolutions"] == [], "deferred items must be resolved, not stranded"
    # same-name Widgets MOC from primary + fan → merged to ONE
    assert len(mocs) == 1, [m.get("title") for m in mocs]


def test_no_id_collision_after_merge():
    out = build_from_wire_companion(_primary(), _fan(), "t_moc")
    ids = [c["id"] for c in out["confirmed_items"] if c.get("id")]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"


def test_daily_and_tag_handler_come_from_primary():
    out = build_from_wire_companion(_primary(), _fan(), "t_moc")
    assert [d["date"] for d in out["daily_updates"]] == ["2026-07-08"]

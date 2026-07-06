#!/usr/bin/env python3
# version: 0.1.0
"""ADR-026 — suggestions-wire emit + change-signal tests.

Covers build_wire_payload's projection of suggestions-doc.json onto the
vault-published wire: id-based references (S## reused, M## minted), selection
mirrored from pre_check/score, render-intermediates dropped, a stable
emit_digest, schema conformance, and the schema_version rejection.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-wire.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_render_mod():
    spec = importlib.util.spec_from_file_location(
        "suggestions_render_wire", SCRIPTS_DIR / "suggestions-render.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_render_mod()
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _doc() -> dict:
    return {
        "schema_version": "1",
        "generated": "2026-07-03T10:00:00Z",
        "run_id": "2026-07-03-1000-wire",
        "profile": "miyo",
        "source_items": 1,
        "conventions": {
            "parent_marker": "up::",
            "peer_marker": "related::",
            "moc_suffix": " MOC",
        },
        "sections": [
            {
                "id": "S01",
                "stem": "memo",
                "actions": [
                    {
                        "kind": "create_atomic_note",
                        "suggestion_id": "S01",
                        "rendered_md": "**Suggested name:** My Note",
                        "item": {
                            "title": "My Note", "template": "t_note_tomo.md",
                            "location": "Atlas/202 Notes/", "tags": ["topic/mind"],
                            "audio_peer": None, "worthiness": 0.8,
                            "suppressed": False, "force_atomic": False,
                        },
                        "candidate_mocs": [
                            {
                                "path": "Atlas/200 Maps/Topic MOC.md",
                                "pre_check": True,
                                "score": 0.8,
                                "anchor": {
                                    "type": "heading",
                                    "value": "Notes",
                                    "placement": "inside",
                                },
                            },
                            {
                                "path": "Atlas/200 Maps/Other MOC.md",
                                "pre_check": False,
                                "score": 0.2,
                                "anchor": {
                                    "type": "heading",
                                    "value": "Refs",
                                    "placement": "after",
                                },
                            },
                        ],
                    }
                ],
            }
        ],
        "proposed_mocs": [
            {
                "topic": "Widgets",
                "items": ["S01"],
                "parent": "Root MOC",
                "name": "Widgets MOC",
                "tags": ["topic/widgets"],
                "reason": "cluster",
            }
        ],
        "needs_attention": [],
    }


def test_wire_conforms_to_schema():
    jsonschema.validate(_MOD.build_wire_payload(_doc()), _SCHEMA)


def test_ids_are_reference_based():
    wire = _MOD.build_wire_payload(_doc())
    s = wire["suggestions"][0]
    assert s["id"] == "S01"
    assert s["title"] == "My Note"
    pm = wire["proposed_mocs"][0]
    assert pm["id"] == "M01"
    # note→proposed-MOC membership is by S## id, never the display string
    assert pm["member_ids"] == ["S01"]


def test_selection_mirrors_pre_check():
    wire = _MOD.build_wire_payload(_doc())
    selected = [c["selected"] for c in wire["suggestions"][0]["candidate_mocs"]]
    assert selected == [True, False]


def test_note_carries_full_mirror_fields():
    wire = _MOD.build_wire_payload(_doc())
    s = wire["suggestions"][0]
    # decision mirrors the Approve pre-check (worthiness 0.8 >= 0.5 → approve)
    assert s["decision"] == "approve"
    assert s["keep_source"] is False and s["delete_source"] is False
    assert s["template"] == "t_note_tomo.md"
    assert s["location"] == "Atlas/202 Notes/"
    assert s["tags"] == ["topic/mind"]
    assert s["suppressed"] is False
    assert s["candidate_mocs"][0]["source"] == "tomo"


def test_full_mirror_sections_present():
    wire = _MOD.build_wire_payload(_doc())
    # JSON-only Pass-2 can't fall back, so the wire always carries every section.
    assert "daily_updates" in wire and "tag_handler_groups" in wire


def test_proposed_moc_defaults_to_skip():
    # mirrors the unchecked markdown default (not created unless approved)
    wire = _MOD.build_wire_payload(_doc())
    assert wire["proposed_mocs"][0]["decision"] == "skip"


def test_no_render_intermediates_leak():
    wire = _MOD.build_wire_payload(_doc())
    assert "rendered_md" not in json.dumps(wire)


def test_emit_digest_present_stable_and_self_consistent():
    from lib.render_md import compute_payload_digest

    wire = _MOD.build_wire_payload(_doc())
    assert wire["emit_digest"].startswith("sha256:")
    # recomputation over the editable payload matches the embedded digest
    assert compute_payload_digest(wire) == wire["emit_digest"]
    # deterministic across identical inputs
    assert _MOD.build_wire_payload(_doc())["emit_digest"] == wire["emit_digest"]


def test_edit_moves_the_digest():
    from lib.render_md import compute_payload_digest

    wire = _MOD.build_wire_payload(_doc())
    wire["proposed_mocs"][0]["decision"] = "approve"
    assert compute_payload_digest(wire) != wire["emit_digest"]


def test_unknown_schema_version_rejected_by_schema():
    wire = _MOD.build_wire_payload(_doc())
    wire["schema_version"] = "9"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(wire, _SCHEMA)

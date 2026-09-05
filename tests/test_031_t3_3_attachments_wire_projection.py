#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t3_3_attachments_wire_projection.py — attachments wire projection.

Covers T3.3 (spec 031 Phase 3): `_wire_note` projects the structured item's
`attachments` list onto the suggestions-wire suggestion; an absent field
projects as `[]`, not `None`; and `emit_digest` changes when the list changes
(the digest hashes the whole payload, so this is automatic — the test
documents it).

Landed together with T3.1's wire-schema change per the plan's ordering
constraint: a half-added wire field makes a mid-flight payload read as
"edited" by emit_digest.

Spec: docs/XDD/specs/031-inbox-attachment-filing/plan/phase-3.md (T3.3)
Ref: PRD/AC-F3.3; SDD/Interface Specifications
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-wire.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_render_mod():
    spec = importlib.util.spec_from_file_location(
        "suggestions_render_t33", SCRIPTS_DIR / "suggestions-render.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_render_mod()
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

ATTACHMENT_PATH = "100 Inbox/Images/prag-karte.jpg"


def _doc(item_overrides: dict | None = None) -> dict:
    item = {
        "title": "My Note", "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/", "tags": ["topic/mind"],
        "audio_peer": None, "worthiness": 0.8,
        "suppressed": False, "force_atomic": False,
    }
    if item_overrides:
        item.update(item_overrides)
    return {
        "schema_version": "1",
        "generated": "2026-09-05T10:00:00Z",
        "run_id": "2026-09-05-1000-wire",
        "profile": "miyo",
        "source_items": 1,
        "sections": [
            {
                "id": "S01",
                "stem": "memo",
                "actions": [
                    {
                        "kind": "create_atomic_note",
                        "suggestion_id": "S01",
                        "rendered_md": "**Suggested name:** My Note",
                        "item": item,
                        "candidate_mocs": [],
                    }
                ],
            }
        ],
        "proposed_mocs": [],
        "needs_attention": [],
    }


def test_wire_note_projects_attachments():
    """_wire_note carries the item's attachments list onto the wire suggestion."""
    doc = _doc({"attachments": [ATTACHMENT_PATH]})
    note = _MOD._wire_note(doc["sections"][0], doc["sections"][0]["actions"][0])
    assert note["attachments"] == [ATTACHMENT_PATH]


def test_wire_note_absent_attachments_projects_as_empty_list():
    """An item without attachments projects as [], not None."""
    doc = _doc()
    note = _MOD._wire_note(doc["sections"][0], doc["sections"][0]["actions"][0])
    assert note["attachments"] == []
    assert note["attachments"] is not None


def test_build_wire_payload_carries_attachments_and_validates():
    """The full build_wire_payload output carries attachments and validates."""
    doc = _doc({"attachments": [ATTACHMENT_PATH]})
    payload = _MOD.build_wire_payload(doc)
    assert payload["suggestions"][0]["attachments"] == [ATTACHMENT_PATH]
    import jsonschema
    jsonschema.validate(instance=payload, schema=_SCHEMA)


def test_emit_digest_changes_when_attachments_list_changes():
    """emit_digest hashes the whole payload, so a changed attachments list
    changes the digest automatically — this test documents that guarantee."""
    doc_a = _doc({"attachments": [ATTACHMENT_PATH]})
    doc_b = _doc({"attachments": ["100 Inbox/scan.pdf"]})
    digest_a = _MOD.build_wire_payload(doc_a)["emit_digest"]
    digest_b = _MOD.build_wire_payload(doc_b)["emit_digest"]
    assert digest_a != digest_b

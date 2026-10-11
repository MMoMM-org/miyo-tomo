#!/usr/bin/env python3
# version: 0.1.0
"""test_038_t2_2_attachment_conflicts_wire_projection.py — the attachment-conflict
remedy a user would see pre-ticked in the markdown now reaches the wire too.

Spec 038 Phase 2 T2.2: `build_wire_payload` projects `d["attachment_conflicts"]`
(the structured record `detect_attachment_conflicts` produces —
`suggestions-reducer.py:582`) onto the wire's top-level `attachment_conflicts[]`
array (added by T2.1). `remedy` is not a field of that structured record; it is
computed by `render_attachment_conflicts_block` at markdown-render time
(`suggestions-reducer.py:1512-1524`) as `rename` when `proposed_name` is not
null, else `keep_in_inbox`. This test mirrors that default on the wire path so
the two paths agree for a brand-new, never-edited run.

Scope deliberately narrower than it first looks (per plan task T2.2):
- "No additional vault interaction" is satisfied by construction —
  `build_wire_payload`'s body makes no vault/client call — so no call-count
  test is written for it here.
- "One entry per attachment however many notes embed it" is already owned by
  `test_037_t1_5_one_entry_one_file.py::test_one_attachment_three_owners_still_one_entry`,
  established inside `detect_attachment_conflicts` before this projection runs.
- "The owning notes are not carried" is enforced by the wire schema's
  `additionalProperties: false` on the `attachment_conflicts[].items` node —
  a leaked `owner_source_items` would fail the `jsonschema.validate` calls
  below, so it is covered here without a dedicated test.

Spec: docs/XDD/specs/038-every-editable-decision-reaches-the-wire/plan/phase-2.md (T2.2)
Ref: PRD/F1; SDD/ADR-2; SDD/ADR-3
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-wire.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_render_mod():
    spec = importlib.util.spec_from_file_location(
        "suggestions_render_t038_t22", SCRIPTS_DIR / "suggestions-render.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_render_mod()
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

SOURCE_RENAMABLE = "100 Inbox/Scans/karte.png"
DEST_RENAMABLE = "Atlas/290 Assets/295 Attachments/karte.png"
PROPOSED_NAME = "karte (2).png"

SOURCE_STUCK = "100 Inbox/Scans/stuck.png"
DEST_STUCK = "Atlas/290 Assets/295 Attachments/stuck.png"


def _doc(attachment_conflicts: list[dict] | None = None) -> dict:
    """A minimal document build_wire_payload can fully project.

    No sections/suggestions are needed for this projection — attachment
    conflicts are top-level and independent of the suggestions array
    (SDD/ADR-2) — so sections stays empty.
    """
    doc = {
        "schema_version": "1",
        "generated": "2026-10-01T10:00:00Z",
        "run_id": "2026-10-01-1000-wire",
        "profile": "miyo",
        "source_items": 1,
        "sections": [],
        "proposed_mocs": [],
        "needs_attention": [],
    }
    if attachment_conflicts is not None:
        doc["attachment_conflicts"] = attachment_conflicts
    return doc


def test_conflict_run_wire_carries_remedy_defaulted_as_the_markdown_pre_ticks():
    """A free name found -> rename pre-ticked; none found -> keep_in_inbox
    pre-ticked (`render_attachment_conflicts_block`, suggestions-reducer.py:1512-1524).
    """
    doc = _doc([
        {
            "source": SOURCE_RENAMABLE,
            "destination": DEST_RENAMABLE,
            "same_file": False,
            "owner_source_items": ["100 Inbox/Dresden.md"],
            "proposed_name": PROPOSED_NAME,
        },
        {
            "source": SOURCE_STUCK,
            "destination": DEST_STUCK,
            "same_file": None,
            "owner_source_items": ["100 Inbox/Other.md"],
            "proposed_name": None,
        },
    ])
    payload = _MOD.build_wire_payload(doc)

    assert payload["attachment_conflicts"] == [
        {
            "source": SOURCE_RENAMABLE,
            "destination": DEST_RENAMABLE,
            "same_file": False,
            "remedy": "rename",
            "proposed_name": PROPOSED_NAME,
        },
        {
            "source": SOURCE_STUCK,
            "destination": DEST_STUCK,
            "same_file": None,
            "remedy": "keep_in_inbox",
            "proposed_name": None,
        },
    ]
    jsonschema.validate(instance=payload, schema=_SCHEMA)


def test_conflict_free_run_wire_carries_empty_array_not_absent():
    """Before this change the key is absent entirely (the reducer's doc omits
    it when empty — `suggestions-reducer.py:2884`, `if attachment_conflicts:`).
    A naive `payload["attachment_conflicts"] == []` raises KeyError rather than
    failing on an assertion when that is true, so presence and emptiness are
    asserted as two separate steps.
    """
    doc = _doc(attachment_conflicts=None)
    payload = _MOD.build_wire_payload(doc)

    _ABSENT = object()
    value = payload.get("attachment_conflicts", _ABSENT)
    assert value is not _ABSENT, (
        "attachment_conflicts must be present on every wire payload, even "
        "when the source document omits the key for a conflict-free run"
    )
    assert value == []
    jsonschema.validate(instance=payload, schema=_SCHEMA)

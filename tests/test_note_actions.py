#!/usr/bin/env python3
# version: 0.1.0
"""test_note_actions.py — Behavioural tests for lib.note_actions (spec 044 T2.5).

Covers the instruction set a /note draft delivers (SDD NoteInstructionSet):
- move_note carries exactly the seven SDD keys, all allowed by the Hashi schema
- delete_source with depends_on ["I01"] only when a source exists and is not kept
- the whole set validates with jsonschema against hashi-instructions.schema.json
- the set is built from the draft state alone (two builds are identical)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
SCHEMA_PATH = Path(__file__).parent.parent / "tomo" / "schemas" / "hashi-instructions.schema.json"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import note_actions, note_meta  # noqa: E402

STEM = "2026-11-04_173005"
MOVE_KEYS = {"id", "action", "source", "destination", "title", "rendered_file",
             "source_inbox_item"}


def _meta(**overrides):
    fields = dict(
        stem=STEM, run_id="2026-11-04T17-30-05Z-abc123",
        created="2026-11-04T17:30:05Z", generated="2026-11-04T17:30:05Z",
        template="Templates/t_meeting.md", template_stem="t_meeting",
        source_path="100 Inbox/Meeting raw.md", inbox="100 Inbox/",
        title="Design review", destination="Atlas/Meetings",
        default_destination="Atlas/202 Notes/",
    )
    keep = overrides.pop("keep_source", False)
    fields.update(overrides)
    meta = note_meta.new_meta(**fields)
    meta.keep_source = keep
    return meta


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_move_note_has_exactly_the_sdd_keys_all_allowed_by_the_schema():
    move = note_actions.build_note_actions(_meta())[0]
    allowed = set(_schema()["$defs"]["move_note"]["properties"])
    assert set(move) == MOVE_KEYS
    assert set(move) <= allowed


def test_move_note_values_come_from_the_draft_state():
    move = note_actions.build_note_actions(_meta())[0]
    assert move == {
        "id": "I01", "action": "move_note",
        "source": f"100 Inbox/{STEM}_Design review.md",
        "destination": "Atlas/Meetings/Design review.md",
        "title": "Design review",
        "rendered_file": f"{STEM}_Design review.md",
        "source_inbox_item": "100 Inbox/Meeting raw.md",
    }


def test_delete_source_depends_on_i01_when_source_is_not_kept():
    actions = note_actions.build_note_actions(_meta())
    assert actions[1] == {
        "id": "I02", "action": "delete_source",
        "source_path": "100 Inbox/Meeting raw.md",
        "reason": "Replaced by a /note note", "depends_on": ["I01"],
    }
    assert len(actions) == 2


def test_no_delete_source_when_source_is_kept():
    actions = note_actions.build_note_actions(_meta(keep_source=True))
    assert [a["action"] for a in actions] == ["move_note"]


def test_no_delete_source_and_null_inbox_item_for_text_in_call():
    actions = note_actions.build_note_actions(_meta(source_path=None))
    assert [a["action"] for a in actions] == ["move_note"]
    assert actions[0]["source_inbox_item"] is None


def test_set_top_level_fields():
    doc = note_actions.build_note_instruction_set(_meta(), profile="miyo")
    assert doc["type"] == "tomo-instructions"
    assert doc["schema_version"] == _schema()["properties"]["schema_version"]["const"]
    assert doc["generated"] == "2026-11-04T17:30:05Z"
    assert doc["profile"] == "miyo"
    assert doc["md_peer"] == f"{STEM}_instructions"


@pytest.mark.parametrize("overrides", [
    {}, {"keep_source": True}, {"source_path": None},
])
def test_set_validates_against_hashi_schema(overrides):
    doc = note_actions.build_note_instruction_set(_meta(**overrides), profile="miyo")
    jsonschema.validate(instance=doc, schema=_schema())


def test_set_with_null_profile_validates():
    doc = note_actions.build_note_instruction_set(_meta(), profile=None)
    jsonschema.validate(instance=doc, schema=_schema())


def test_delete_without_depends_on_would_be_rejected():
    """Guards the guard: the schema really rejects a delete_source missing depends_on."""
    doc = note_actions.build_note_instruction_set(_meta(), profile="miyo")
    del doc["actions"][1]["depends_on"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=_schema())


def test_two_builds_are_identical():
    meta = _meta()
    first = note_actions.build_note_instruction_set(meta, profile="miyo")
    second = note_actions.build_note_instruction_set(meta, profile="miyo")
    assert json.dumps(first) == json.dumps(second)

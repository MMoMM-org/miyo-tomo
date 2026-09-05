#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t3_1_attachments_schema.py — attachments field on the three review schemas.

Covers T3.1 (spec 031 Phase 3): item-result.schema.json, suggestions-doc.schema.json,
and suggestions-wire.schema.json each gain an optional `attachments: string[]` field.
Not in `required` on any of the three — legacy artefacts without the field must still
validate (CON-8).

Spec: docs/XDD/specs/031-inbox-attachment-filing/plan/phase-3.md (T3.1)
Ref: PRD/Feature 3; SDD/Interface Specifications; SDD/Constraints CON-8
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import ValidationError, validate  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
_ITEM_RESULT = REPO_ROOT / "tomo" / "schemas" / "item-result.schema.json"
_SUGGESTIONS_DOC = REPO_ROOT / "tomo" / "schemas" / "suggestions-doc.schema.json"
_SUGGESTIONS_WIRE = REPO_ROOT / "tomo" / "schemas" / "suggestions-wire.schema.json"


@pytest.fixture(scope="module")
def item_result_schema() -> dict:
    return json.loads(_ITEM_RESULT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def suggestions_doc_schema() -> dict:
    return json.loads(_SUGGESTIONS_DOC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def suggestions_wire_schema() -> dict:
    return json.loads(_SUGGESTIONS_WIRE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# item-result.schema.json — create_atomic_note.attachments
# ---------------------------------------------------------------------------


def _make_atomic(**overrides) -> dict:
    action = {
        "kind": "create_atomic_note",
        "source_stem": "my-inbox-note",
        "suggested_title": "Some Atomic Note",
        "template": "Atomic Note.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags_to_add": [],
    }
    action.update(overrides)
    return action


def _make_item_result(actions: list) -> dict:
    return {
        "schema_version": "1",
        "stem": "my-inbox-note",
        "path": "100 Inbox/my-inbox-note.md",
        "type": "atomic",
        "type_confidence": 0.9,
        "actions": actions,
    }


def test_item_result_with_attachments_validates(item_result_schema):
    """A create_atomic_note carrying attachments passes validation."""
    action = _make_atomic(attachments=["100 Inbox/Images/prag-karte.jpg"])
    validate(instance=_make_item_result([action]), schema=item_result_schema)


def test_item_result_without_attachments_still_validates(item_result_schema):
    """attachments is optional — a legacy result without it still validates (CON-8)."""
    validate(instance=_make_item_result([_make_atomic()]), schema=item_result_schema)


def test_item_result_attachments_must_be_a_list(item_result_schema):
    """A non-list attachments value is rejected."""
    action = _make_atomic(attachments="100 Inbox/Images/prag-karte.jpg")
    with pytest.raises(ValidationError):
        validate(instance=_make_item_result([action]), schema=item_result_schema)


def test_item_result_attachments_not_required(item_result_schema):
    """attachments must not be in the create_atomic_note required list (CON-8)."""
    required = item_result_schema["$defs"]["create_atomic_note"]["required"]
    assert "attachments" not in required


# ---------------------------------------------------------------------------
# suggestions-doc.schema.json — sections[].actions[].item.attachments
# ---------------------------------------------------------------------------


def _make_doc_item(**overrides) -> dict:
    item = {
        "title": "My Note",
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "tags": [],
        "suppressed": False,
        "force_atomic": False,
    }
    item.update(overrides)
    return item


def _make_doc(item: dict) -> dict:
    return {
        "schema_version": "1",
        "generated": "2026-09-05T10:00:00Z",
        "run_id": "2026-09-05-1000-attach",
        "profile": "miyo",
        "source_items": 1,
        "sections": [
            {
                "id": "S01",
                "stem": "my-inbox-note",
                "actions": [
                    {
                        "kind": "create_atomic_note",
                        "rendered_md": "**Suggested name:** My Note",
                        "item": item,
                    }
                ],
            }
        ],
    }


def test_suggestions_doc_item_with_attachments_validates(suggestions_doc_schema):
    """A section item carrying attachments passes validation."""
    item = _make_doc_item(attachments=["100 Inbox/Images/prag-karte.jpg"])
    validate(instance=_make_doc(item), schema=suggestions_doc_schema)


def test_suggestions_doc_item_without_attachments_still_validates(suggestions_doc_schema):
    """attachments is optional on the structured item mirror (CON-8)."""
    validate(instance=_make_doc(_make_doc_item()), schema=suggestions_doc_schema)


def test_suggestions_doc_item_attachments_must_be_a_list(suggestions_doc_schema):
    """A non-list attachments value on the item mirror is rejected."""
    item = _make_doc_item(attachments="not-a-list")
    with pytest.raises(ValidationError):
        validate(instance=_make_doc(item), schema=suggestions_doc_schema)


# ---------------------------------------------------------------------------
# suggestions-wire.schema.json — suggestions[].attachments
# ---------------------------------------------------------------------------


def _make_wire_suggestion(**overrides) -> dict:
    suggestion = {
        "id": "S01",
        "stem": "my-inbox-note",
        "title": "My Note",
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "tags": [],
        "decision": "approve",
        "keep_source": False,
        "delete_source": False,
        "force_atomic": False,
        "suppressed": False,
        "candidate_mocs": [],
    }
    suggestion.update(overrides)
    return suggestion


def _make_wire(suggestion: dict) -> dict:
    return {
        "schema_version": "1",
        "generated": "2026-09-05T10:00:00Z",
        "run_id": "2026-09-05-1000-attach",
        "profile": "miyo",
        "source_items": 1,
        "emit_digest": "sha256:" + "a" * 64,
        "suggestions": [suggestion],
        "proposed_mocs": [],
        "daily_updates": [],
        "tag_handler_groups": [],
    }


def test_wire_suggestion_with_attachments_validates(suggestions_wire_schema):
    """A wire suggestion carrying attachments passes validation."""
    suggestion = _make_wire_suggestion(attachments=["100 Inbox/Images/prag-karte.jpg"])
    validate(instance=_make_wire(suggestion), schema=suggestions_wire_schema)


def test_wire_suggestion_without_attachments_still_validates(suggestions_wire_schema):
    """attachments is optional on the wire — legacy payloads still validate (CON-8)."""
    validate(instance=_make_wire(_make_wire_suggestion()), schema=suggestions_wire_schema)


def test_wire_suggestion_attachments_must_be_a_list(suggestions_wire_schema):
    """A non-list attachments value on the wire suggestion is rejected."""
    suggestion = _make_wire_suggestion(attachments={"not": "a list"})
    with pytest.raises(ValidationError):
        validate(instance=_make_wire(suggestion), schema=suggestions_wire_schema)

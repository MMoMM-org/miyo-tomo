#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t3_1_unresolved_embeds_schema.py — unresolved_embeds on the analyst contract.

T3.1 declared `attachments` on item-result.schema.json but missed a sibling
field: suggestions-reducer.py:413 already reads `action.get("unresolved_embeds")`
(T3.2's Should-have unresolved/ambiguous reporting), and item-result.schema.json
sets `additionalProperties: false` on create_atomic_note. Today nothing
populates the field, so nothing breaks — but the moment an analyst emits it,
the whole item is rejected at validation, three phases downstream of the
actual cause. This closes that latent break.

Spec: docs/XDD/specs/031-inbox-attachment-filing/plan/phase-3.md (T3.1 fix)
Ref: PRD/Should-have: unresolved-embed reporting
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


@pytest.fixture(scope="module")
def item_result_schema() -> dict:
    return json.loads(_ITEM_RESULT.read_text(encoding="utf-8"))


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


def test_item_with_unresolved_embeds_validates(item_result_schema):
    """A create_atomic_note carrying unresolved_embeds passes validation."""
    action = _make_atomic(unresolved_embeds=[
        {"embed_target": "karte.jpg", "status": "ambiguous", "candidate_count": 2},
        {"embed_target": "missing.jpg", "status": "unresolved"},
    ])
    validate(instance=_make_item_result([action]), schema=item_result_schema)


def test_item_without_unresolved_embeds_still_validates(item_result_schema):
    """unresolved_embeds is optional — a result without it still validates."""
    validate(instance=_make_item_result([_make_atomic()]), schema=item_result_schema)


def test_unresolved_embeds_not_required(item_result_schema):
    """unresolved_embeds must not be in create_atomic_note's required list."""
    required = item_result_schema["$defs"]["create_atomic_note"]["required"]
    assert "unresolved_embeds" not in required


def test_unresolved_embeds_entry_missing_status_rejected(item_result_schema):
    """Each entry requires embed_target and status — a malformed entry is rejected."""
    action = _make_atomic(unresolved_embeds=[{"embed_target": "karte.jpg"}])
    with pytest.raises(ValidationError):
        validate(instance=_make_item_result([action]), schema=item_result_schema)


def test_unresolved_embeds_entry_invalid_status_rejected(item_result_schema):
    """status is a two-value enum — 'resolved' does not belong here (that
    goes in `attachments` instead)."""
    action = _make_atomic(unresolved_embeds=[
        {"embed_target": "karte.jpg", "status": "resolved"}
    ])
    with pytest.raises(ValidationError):
        validate(instance=_make_item_result([action]), schema=item_result_schema)


def test_unresolved_embeds_entry_extra_field_rejected(item_result_schema):
    """Each entry has additionalProperties:false."""
    action = _make_atomic(unresolved_embeds=[
        {"embed_target": "karte.jpg", "status": "unresolved", "bogus": True}
    ])
    with pytest.raises(ValidationError):
        validate(instance=_make_item_result([action]), schema=item_result_schema)


def test_unresolved_embeds_must_be_a_list(item_result_schema):
    """A non-list unresolved_embeds value is rejected."""
    action = _make_atomic(unresolved_embeds={"embed_target": "karte.jpg"})
    with pytest.raises(ValidationError):
        validate(instance=_make_item_result([action]), schema=item_result_schema)

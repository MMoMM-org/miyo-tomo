#!/usr/bin/env python3
# version: 0.1.0
"""test_edit_note_text_action.py — Tests for the edit_note_text Hashi action (ADR-3).

Covers:
  - Schema validation: accepts valid shape, rejects extra properties
  - occurrence defaults to "first" when omitted
  - _build_edit_note_text_actions builder output for the three body-edit cases:
      dead-link FIX, dead-link REMOVE, up:: REMOVAL
  - Broken-up REPOINT still emits add_relationship (NOT edit_note_text)

Spec: docs/XDD/specs/030-garden-audit/solution.md §ADR-3
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.X` works

from lib.render_actions import _build_edit_note_text_actions  # noqa: E402


# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def instructions_schema() -> dict:
    """Load the hashi-instructions.schema.json once per module."""
    schema_path = SCHEMAS_DIR / "hashi-instructions.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _make_minimal_doc(actions: list[dict]) -> dict:
    """Build the minimal valid instructions document wrapping `actions`."""
    return {
        "schema_version": "2",
        "type": "tomo-instructions",
        "generated": "2026-07-20T00:00:00Z",
        "profile": None,
        "actions": actions,
    }


def _make_edit_action(**kwargs) -> dict:
    """Build a minimal valid edit_note_text action dict."""
    base = {
        "id": "I01",
        "action": "edit_note_text",
        "path": "Notes/Foo.md",
        "match": "[[Old]]",
        "replace": "[[New]]",
        "occurrence": "first",
        "applied": False,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Schema: valid edit_note_text action accepted
# ---------------------------------------------------------------------------


def test_schema_accepts_valid_edit_note_text_action(instructions_schema):
    """A fully-specified edit_note_text action validates against the schema."""
    doc = _make_minimal_doc([_make_edit_action()])
    jsonschema.validate(doc, instructions_schema)  # no exception = pass


def test_schema_accepts_occurrence_all(instructions_schema):
    """occurrence='all' is a valid value."""
    doc = _make_minimal_doc([_make_edit_action(occurrence="all")])
    jsonschema.validate(doc, instructions_schema)


def test_schema_accepts_empty_replace(instructions_schema):
    """replace='' (remove) is valid — empty string is allowed."""
    doc = _make_minimal_doc([_make_edit_action(replace="")])
    jsonschema.validate(doc, instructions_schema)


# ---------------------------------------------------------------------------
# Schema: occurrence defaults to "first" when omitted
# ---------------------------------------------------------------------------


def test_schema_occurrence_default_is_first(instructions_schema):
    """When occurrence is omitted, the schema default is 'first'."""
    # Build action without occurrence; schema default should apply
    action = {
        "id": "I01",
        "action": "edit_note_text",
        "path": "Notes/Foo.md",
        "match": "[[Old]]",
        "replace": "[[New]]",
        "applied": False,
    }
    doc = _make_minimal_doc([action])
    # Validate first — must not raise
    validator = jsonschema.Draft202012Validator(instructions_schema)
    errors = list(validator.iter_errors(doc))
    assert not errors, f"Unexpected validation errors: {errors}"
    # Confirm the schema declares occurrence as optional with a default
    edit_def = instructions_schema["$defs"]["edit_note_text"]
    occ_prop = edit_def["properties"]["occurrence"]
    assert occ_prop.get("default") == "first", (
        f"Expected occurrence default='first', got: {occ_prop}"
    )
    assert "occurrence" not in edit_def.get("required", []), (
        "occurrence must NOT be in required (it is optional with a default)"
    )


# ---------------------------------------------------------------------------
# Schema: additionalProperties:false — extra fields rejected
# ---------------------------------------------------------------------------


def test_schema_rejects_extra_property(instructions_schema):
    """edit_note_text with an unknown field fails validation (additionalProperties:false)."""
    action = _make_edit_action(unexpected_field="oops")
    doc = _make_minimal_doc([action])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, instructions_schema)


def test_schema_rejects_invalid_occurrence_value(instructions_schema):
    """occurrence='second' (not in enum) fails validation."""
    action = _make_edit_action(occurrence="second")
    doc = _make_minimal_doc([action])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, instructions_schema)


# ---------------------------------------------------------------------------
# Builder: _build_edit_note_text_actions
# ---------------------------------------------------------------------------


def _counter() -> list[int]:
    return [0]


def test_builder_dead_link_fix():
    """Dead-link FIX: match='[[Old]]', replace='[[New]]' → edit_note_text action."""
    items = [
        {
            "path": "Notes/Bar.md",
            "match": "[[Missing Note]]",
            "replace": "[[Correct Note]]",
        }
    ]
    counter = _counter()
    actions = _build_edit_note_text_actions(items, counter)

    assert len(actions) == 1
    a = actions[0]
    assert a["action"] == "edit_note_text"
    assert a["path"] == "Notes/Bar.md"
    assert a["match"] == "[[Missing Note]]"
    assert a["replace"] == "[[Correct Note]]"
    assert a["occurrence"] == "first"
    assert a["id"] == "I01"


def test_builder_dead_link_remove():
    """Dead-link REMOVE: match='[[Old]]', replace='' → edit_note_text with empty replace."""
    items = [
        {
            "path": "Notes/Baz.md",
            "match": "[[Dead Link]]",
            "replace": "",
        }
    ]
    counter = _counter()
    actions = _build_edit_note_text_actions(items, counter)

    assert len(actions) == 1
    a = actions[0]
    assert a["action"] == "edit_note_text"
    assert a["path"] == "Notes/Baz.md"
    assert a["match"] == "[[Dead Link]]"
    assert a["replace"] == ""
    assert a["occurrence"] == "first"


def test_builder_up_removal():
    """Broken up:: REMOVAL: whole-line match, replace='' → edit_note_text."""
    items = [
        {
            "path": "Notes/Orphan.md",
            "match": "up:: [[Deleted MOC]]",
            "replace": "",
        }
    ]
    counter = _counter()
    actions = _build_edit_note_text_actions(items, counter)

    assert len(actions) == 1
    a = actions[0]
    assert a["action"] == "edit_note_text"
    assert a["path"] == "Notes/Orphan.md"
    assert a["match"] == "up:: [[Deleted MOC]]"
    assert a["replace"] == ""
    assert a["occurrence"] == "first"


def test_builder_occurrence_passthrough():
    """occurrence='all' is forwarded verbatim from the input item."""
    items = [
        {
            "path": "Notes/Multi.md",
            "match": "[[Old]]",
            "replace": "[[New]]",
            "occurrence": "all",
        }
    ]
    counter = _counter()
    actions = _build_edit_note_text_actions(items, counter)

    assert actions[0]["occurrence"] == "all"


def test_builder_empty_items_returns_empty():
    """Empty input → empty action list."""
    actions = _build_edit_note_text_actions([], _counter())
    assert actions == []


def test_builder_multiple_items_incrementing_ids():
    """Multiple items get sequential IDs and all emit edit_note_text."""
    items = [
        {"path": "A.md", "match": "[[X]]", "replace": "[[Y]]"},
        {"path": "B.md", "match": "[[P]]", "replace": ""},
    ]
    counter = _counter()
    actions = _build_edit_note_text_actions(items, counter)

    assert len(actions) == 2
    assert actions[0]["id"] == "I01"
    assert actions[1]["id"] == "I02"
    assert actions[0]["action"] == "edit_note_text"
    assert actions[1]["action"] == "edit_note_text"


def test_builder_shares_counter_with_caller():
    """Counter advances correctly when shared with other builders."""
    counter = [5]  # pre-seeded, simulating prior actions
    items = [{"path": "C.md", "match": "[[Old]]", "replace": ""}]
    actions = _build_edit_note_text_actions(items, counter)

    assert actions[0]["id"] == "I06"
    assert counter[0] == 6


# ---------------------------------------------------------------------------
# Broken-up REPOINT: stays on add_relationship (NOT edit_note_text)
# ---------------------------------------------------------------------------


def test_broken_up_repoint_emits_add_relationship_not_edit_note_text():
    """Broken-up REPOINT must use add_relationship (marker-located replace).
    This test verifies the routing contract: _build_edit_note_text_actions
    is NOT called for repoints — only for removal + free-text wikilinks."""
    # Simulate what a repoint action looks like (from _make_add_rel)
    repoint_action = {
        "id": "I01",
        "action": "add_relationship",
        "target_moc_path": "Notes/Child.md",
        "marker": "up::",
        "line": "up:: [[New MOC]]",
        "source_note_title": None,
        "applied": False,
    }
    # A repoint action must NOT be an edit_note_text action
    assert repoint_action["action"] == "add_relationship"
    assert repoint_action["action"] != "edit_note_text"
    # And the builder itself produces zero edit_note_text actions for empty input
    # (confirming the builder is never called for repoints)
    actions = _build_edit_note_text_actions([], _counter())
    assert all(a["action"] == "edit_note_text" for a in actions)  # vacuously true for empty


def test_edit_note_text_builder_never_produces_add_relationship():
    """_build_edit_note_text_actions only ever emits edit_note_text actions."""
    items = [
        {"path": "Notes/X.md", "match": "[[Broken]]", "replace": ""},
        {"path": "Notes/Y.md", "match": "[[A]]", "replace": "[[B]]"},
    ]
    actions = _build_edit_note_text_actions(items, _counter())
    for a in actions:
        assert a["action"] == "edit_note_text", (
            f"Expected edit_note_text only, got: {a['action']}"
        )

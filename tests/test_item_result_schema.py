#!/usr/bin/env python3
# version: 0.1.0
"""test_item_result_schema.py — JSON Schema validation tests for item-result.schema.json.

Covers T1.1 (XDD 016 Phase 1): source_stem provenance field on create_atomic_note,
N>=2 atomics per source allowed, and source_stem required enforcement.

Spec: docs/XDD/specs/016-multi-topic-atomic-notes/
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
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "item-result.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers — minimal valid fixture builders
# ---------------------------------------------------------------------------

def _make_atomic(source_stem: str, title: str = "Some Atomic Note") -> dict:
    """Return a minimal valid create_atomic_note action with all required fields."""
    return {
        "kind": "create_atomic_note",
        "source_stem": source_stem,
        "suggested_title": title,
        "template": "Atomic Note.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags_to_add": [],
    }


def _make_result(actions: list) -> dict:
    """Return a minimal valid item-result envelope wrapping the given actions."""
    return {
        "schema_version": "1",
        "stem": "my-inbox-note",
        "path": "100 Inbox/my-inbox-note.md",
        "type": "atomic",
        "type_confidence": 0.9,
        "actions": actions,
    }


# ---------------------------------------------------------------------------
# T1.1 — source_stem present on a single-thread result validates
# ---------------------------------------------------------------------------


def test_single_atomic_with_source_stem_validates(schema):
    """A result with one create_atomic_note carrying source_stem passes validation."""
    validate(
        instance=_make_result([_make_atomic("my-inbox-note")]),
        schema=schema,
    )


# ---------------------------------------------------------------------------
# T1.1 — N>=2 create_atomic_note from one source_stem validates (PRD/A7)
# ---------------------------------------------------------------------------


def test_two_atomics_same_source_stem_validates(schema):
    """A result with two create_atomic_note actions sharing one source_stem passes validation.

    Regression-style assertion: actions[] has no maxItems — two atomics from one
    source must be accepted (PRD/A7, ADR-2, ADR-4).
    """
    validate(
        instance=_make_result([
            _make_atomic("multi-topic-note", "First Topic"),
            _make_atomic("multi-topic-note", "Second Topic"),
        ]),
        schema=schema,
    )


def test_three_atomics_same_source_stem_validates(schema):
    """A result with three create_atomic_note actions from one source_stem passes validation."""
    validate(
        instance=_make_result([
            _make_atomic("dense-note", "Topic A"),
            _make_atomic("dense-note", "Topic B"),
            _make_atomic("dense-note", "Topic C"),
        ]),
        schema=schema,
    )


# ---------------------------------------------------------------------------
# T1.1 — source_stem is REQUIRED (ADR-4: required for ALL items)
# ---------------------------------------------------------------------------


def test_atomic_missing_source_stem_rejected(schema):
    """A create_atomic_note action missing source_stem is rejected (ADR-4: required field)."""
    action_without_source_stem = {
        "kind": "create_atomic_note",
        "suggested_title": "Some Note",
        "template": "Atomic Note.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags_to_add": [],
    }
    with pytest.raises(ValidationError):
        validate(
            instance=_make_result([action_without_source_stem]),
            schema=schema,
        )


# ---------------------------------------------------------------------------
# T1.1 — source_stem must be a non-empty string (minLength: 1)
# ---------------------------------------------------------------------------


def test_atomic_empty_source_stem_rejected(schema):
    """A create_atomic_note action with empty string source_stem is rejected."""
    action = _make_atomic("placeholder")
    action["source_stem"] = ""
    with pytest.raises(ValidationError):
        validate(
            instance=_make_result([action]),
            schema=schema,
        )


# ---------------------------------------------------------------------------
# T1.1 — additionalProperties: false still enforced
# ---------------------------------------------------------------------------


def test_atomic_extra_field_rejected(schema):
    """A create_atomic_note action with an unknown extra field is rejected."""
    action = _make_atomic("my-note")
    action["unknown_field"] = "should fail"
    with pytest.raises(ValidationError):
        validate(
            instance=_make_result([action]),
            schema=schema,
        )


# ---------------------------------------------------------------------------
# Baseline — existing required fields still enforced
# ---------------------------------------------------------------------------


def test_atomic_missing_suggested_title_rejected(schema):
    """A create_atomic_note action missing suggested_title is rejected."""
    action = {
        "kind": "create_atomic_note",
        "source_stem": "my-note",
        "template": "Atomic Note.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags_to_add": [],
    }
    with pytest.raises(ValidationError):
        validate(
            instance=_make_result([action]),
            schema=schema,
        )


def test_atomic_missing_template_rejected(schema):
    """A create_atomic_note action missing template is rejected."""
    action = {
        "kind": "create_atomic_note",
        "source_stem": "my-note",
        "suggested_title": "Some Note",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags_to_add": [],
    }
    with pytest.raises(ValidationError):
        validate(
            instance=_make_result([action]),
            schema=schema,
        )

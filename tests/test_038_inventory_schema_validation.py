#!/usr/bin/env python3
# version: 0.1.0
"""test_038_inventory_schema_validation.py — JSON Schema validation tests for T1.1:
suggestions-decision-inventory.schema.json (spec 038 Phase 1).

ADR-7 requires a two-sided join test in T1.2: every schema field marked `Editable`
in suggestions-wire.schema.json needs a row here, and every editable control the
parser recognises needs a row here. That join test is NOT this file's job — it
needs the inventory's actual row set, which is the finding T1.1 produces, not
something knowable in advance. This file only proves the shape of one row is
enforced: a conforming row validates, and a row malformed in each way the schema
claims to forbid is rejected — demonstrated by running both directions, not by
asserting them (PRD/F4).

Every declared constraint (additionalProperties, required, type, pattern,
minLength, const, minItems) gets its own rejection test, constructed to violate
exactly that constraint and nothing else — a schema missing `additionalProperties:
false`, an incomplete `required`, or a missing type/enum/pattern constraint would
let a genuinely malformed row through undetected (spec 037's nine mutations that
could not bite is the standing warning this guards against).

Spec: docs/XDD/specs/038-every-editable-decision-reaches-the-wire/
Ref: PRD/F4; SDD/ADR-7
"""
from __future__ import annotations

import copy
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
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-decision-inventory.schema.json"
INVENTORY_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-decision-inventory.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _row(**overrides) -> dict:
    row = {
        "id": "D01",
        "markdown_control": "Accept/Approve checkbox on a suggestion.",
        "wire_field": "suggestions[].decision",
        "editable": True,
    }
    row.update(overrides)
    return row


def _doc(*rows: dict) -> dict:
    return {"schema_version": 1, "decisions": list(rows) or [_row()]}


# ---------------------------------------------------------------------------
# Conforming rows validate (both a wire-backed row and a null-wire-field row,
# the F4 shape the attachment-conflict remedy needs, and a retired row).
# ---------------------------------------------------------------------------


def test_conforming_row_validates(schema):
    validate(instance=_doc(_row()), schema=schema)


def test_conforming_row_with_null_wire_field_validates(schema):
    """F4: a decision with no wire field records that absence explicitly."""
    row = _row(id="D23", markdown_control="Attachment-conflict remedy ticks.", wire_field=None)
    validate(instance=_doc(row), schema=schema)


def test_conforming_row_with_note_validates(schema):
    row = _row(note="Schema field lacks the literal 'Editable' marker (finding).")
    validate(instance=_doc(row), schema=schema)


def test_conforming_retired_row_validates(schema):
    """F4: a retired control keeps its row with editable=false."""
    row = _row(editable=False, note="Control removed from the markdown in spec NNN.")
    validate(instance=_doc(row), schema=schema)


# ---------------------------------------------------------------------------
# Row-level rejections — one per declared constraint.
# ---------------------------------------------------------------------------


def test_row_rejects_additional_property(schema):
    row = _row()
    row["unexpected"] = "nope"
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_missing_id(schema):
    row = _row()
    del row["id"]
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_missing_markdown_control(schema):
    row = _row()
    del row["markdown_control"]
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_missing_wire_field(schema):
    row = _row()
    del row["wire_field"]
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_missing_editable(schema):
    row = _row()
    del row["editable"]
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_id_wrong_type(schema):
    row = _row(id=1)
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_id_wrong_pattern(schema):
    """id must be opaque form 'D<digits>' — lowercase/hyphenated prose-derived
    ids (the exact shape ADR-7 forbids) must fail."""
    row = _row(id="accept-approve-checkbox")
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_markdown_control_wrong_type(schema):
    row = _row(markdown_control=123)
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_markdown_control_empty_string(schema):
    row = _row(markdown_control="")
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_wire_field_wrong_type(schema):
    row = _row(wire_field=42)
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_wire_field_bad_pattern(schema):
    row = _row(wire_field="not a dotted path")
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_editable_wrong_type(schema):
    row = _row(editable="true")
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_note_empty_string(schema):
    row = _row(note="")
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


# ---------------------------------------------------------------------------
# Top-level document rejections — one per declared constraint.
# ---------------------------------------------------------------------------


def test_top_level_rejects_additional_property(schema):
    doc = _doc()
    doc["unexpected"] = "nope"
    with pytest.raises(ValidationError):
        validate(instance=doc, schema=schema)


def test_top_level_rejects_missing_schema_version(schema):
    doc = _doc()
    del doc["schema_version"]
    with pytest.raises(ValidationError):
        validate(instance=doc, schema=schema)


def test_top_level_rejects_missing_decisions(schema):
    doc = _doc()
    del doc["decisions"]
    with pytest.raises(ValidationError):
        validate(instance=doc, schema=schema)


def test_top_level_rejects_wrong_schema_version(schema):
    doc = _doc()
    doc["schema_version"] = 2
    with pytest.raises(ValidationError):
        validate(instance=doc, schema=schema)


def test_top_level_rejects_empty_decisions(schema):
    doc = _doc()
    doc["decisions"] = []
    with pytest.raises(ValidationError):
        validate(instance=doc, schema=schema)


def test_top_level_rejects_decisions_wrong_type(schema):
    doc = _doc()
    doc["decisions"] = "not-a-list"
    with pytest.raises(ValidationError):
        validate(instance=doc, schema=schema)


# ---------------------------------------------------------------------------
# The committed inventory file itself (step 4: "the file validates against
# its own schema ... ids are unique"). Which rows exist is NOT asserted here
# (T1.2's job) — only that whatever rows do exist are well-formed and unique.
# ---------------------------------------------------------------------------


def test_inventory_file_exists():
    assert INVENTORY_PATH.is_file(), f"missing {INVENTORY_PATH}"


def test_inventory_file_validates_against_schema(schema):
    doc = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    validate(instance=doc, schema=schema)


def test_inventory_ids_are_unique():
    doc = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    ids = [row["id"] for row in doc["decisions"]]
    assert len(ids) == len(set(ids)), "duplicate id in suggestions-decision-inventory.json"


def test_inventory_is_untouched_by_deepcopy_round_trip(schema):
    """Sanity: the fixtures above mutate copies, never the loaded schema itself."""
    before = copy.deepcopy(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    validate(instance=_doc(_row()), schema=schema)
    assert schema == before

#!/usr/bin/env python3
# version: 0.1.0
"""test_edit_frontmatter_schema.py — spec 032-up-source-routing T4.1.

Registers `edit_frontmatter` in both instruction schemas (producer +
Hashi mirror), mirroring Hashi's shipped `$def` byte-equal (Hashi 0.22.0/0.23.0).

The existing parity tests (test_tomo_schema_parity.py,
test_instruction_render_wire_hygiene.py) compare property SETS, not schema
STRUCTURE. Hashi's `$def` carries an `allOf` with two clauses:
  1. operation == "set" -> value required
  2. oneOf: exactly one of expected / expected_absent [ref: CON-1]
A mirror that copies `properties`/`required` and drops `allOf` passes those
parity tests green and fails only at Hashi's gate in production. Every test
below validates a VIOLATING document and asserts REJECTION, against EACH of
Tomo's two schemas — proving the constraint is enforced, not just declared.

Spec: docs/XDD/specs/032-up-source-routing/plan/phase-4.md T4.1
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

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
TOMO_SCHEMA_PATH = SCHEMAS_DIR / "instructions.schema.json"
HASHI_SNAPSHOT_PATH = SCHEMAS_DIR / "hashi-instructions.schema.json"

SCHEMA_PATHS = {
    "producer (instructions.schema.json)": TOMO_SCHEMA_PATH,
    "mirror (hashi-instructions.schema.json)": HASHI_SNAPSHOT_PATH,
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _def_wrapper(schema: dict, defname: str) -> dict:
    """Build a standalone schema that validates instances of one $def directly."""
    return {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": f"#/$defs/{defname}",
    }


def _well_formed_set() -> dict:
    return {
        "id": "I01",
        "action": "edit_frontmatter",
        "path": "100 Inbox/note.md",
        "property": "up",
        "operation": "set",
        "value": "[[Some MOC]]",
        "expected_absent": True,
    }


def _well_formed_remove() -> dict:
    return {
        "id": "I02",
        "action": "edit_frontmatter",
        "path": "100 Inbox/note.md",
        "property": "up",
        "operation": "remove",
        "expected": "[[Old MOC]]",
    }


@pytest.fixture(params=SCHEMA_PATHS.items(), ids=SCHEMA_PATHS.keys())
def schema_case(request) -> tuple[str, dict]:
    label, path = request.param
    return label, _load(path)


class TestEditFrontmatterWellFormed:
    def test_set_with_expected_absent_validates(self, schema_case):
        label, schema = schema_case
        wrapper = _def_wrapper(schema, "edit_frontmatter")
        validate(instance=_well_formed_set(), schema=wrapper)

    def test_remove_with_expected_validates(self, schema_case):
        label, schema = schema_case
        wrapper = _def_wrapper(schema, "edit_frontmatter")
        validate(instance=_well_formed_remove(), schema=wrapper)


class TestEditFrontmatterRequiredFields:
    @pytest.mark.parametrize(
        "dropped", ["id", "action", "path", "property", "operation"]
    )
    def test_dropping_required_field_is_rejected(self, schema_case, dropped):
        label, schema = schema_case
        wrapper = _def_wrapper(schema, "edit_frontmatter")
        doc = _well_formed_set()
        del doc[dropped]
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=wrapper)


class TestEditFrontmatterStructuralParity:
    """Falsifies a drop-the-allOf mirror: each allOf clause must actually reject."""

    def test_expected_and_expected_absent_together_is_rejected(self, schema_case):
        """CON-1: expected + expected_absent together is a validation error,
        not a precedence rule."""
        label, schema = schema_case
        wrapper = _def_wrapper(schema, "edit_frontmatter")
        doc = _well_formed_remove()
        doc["expected_absent"] = True  # doc already carries "expected" -> both present
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=wrapper)

    def test_neither_expected_nor_expected_absent_is_rejected(self, schema_case):
        """The oneOf also forbids the ungoverned case: neither present."""
        label, schema = schema_case
        wrapper = _def_wrapper(schema, "edit_frontmatter")
        doc = _well_formed_set()
        del doc["expected_absent"]
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=wrapper)

    def test_operation_set_without_value_is_rejected(self, schema_case):
        """Second allOf clause: operation=='set' -> value required."""
        label, schema = schema_case
        wrapper = _def_wrapper(schema, "edit_frontmatter")
        doc = _well_formed_set()
        del doc["value"]
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=wrapper)

    def test_operation_remove_without_value_still_validates(self, schema_case):
        """value is required for 'set' only; 'remove' never carries it."""
        label, schema = schema_case
        wrapper = _def_wrapper(schema, "edit_frontmatter")
        validate(instance=_well_formed_remove(), schema=wrapper)


class TestEditFrontmatterAdditionalProperties:
    def test_additional_property_is_rejected(self, schema_case):
        label, schema = schema_case
        wrapper = _def_wrapper(schema, "edit_frontmatter")
        doc = _well_formed_set()
        doc["unexpected_field"] = "nope"
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=wrapper)


def test_edit_frontmatter_not_mirror_only():
    """Tomo emits edit_frontmatter (spec 032) — it must NOT be registered in
    MIRROR_ONLY_ACTIONS, which is reserved for actions with no Tomo emitter."""
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from test_tomo_schema_parity import MIRROR_ONLY_ACTIONS

    assert "edit_frontmatter" not in MIRROR_ONLY_ACTIONS


def test_edit_frontmatter_registered_in_actions_oneof():
    for label, path in SCHEMA_PATHS.items():
        schema = _load(path)
        one_of = schema["properties"]["actions"]["items"]["oneOf"]
        refs = {entry.get("$ref", "") for entry in one_of}
        assert "#/$defs/edit_frontmatter" in refs, f"missing oneOf ref in {label}"


def test_schema_version_unchanged():
    """CON-2: schema_version stays '2' — this task does not bump it."""
    for label, path in SCHEMA_PATHS.items():
        schema = _load(path)
        assert schema["properties"]["schema_version"] == {"const": "2"}, label


def test_edit_frontmatter_def_structurally_identical_across_tomo_schemas():
    """The producer and mirror copies of the $def must be the same structure
    (parsed-JSON equality, not eyeballing)."""
    producer = _load(TOMO_SCHEMA_PATH)
    mirror = _load(HASHI_SNAPSHOT_PATH)
    assert producer["$defs"]["edit_frontmatter"] == mirror["$defs"]["edit_frontmatter"]


HASHI_LOCAL_SCHEMA_PATH = (
    REPO_ROOT.parent / "Hashi" / "src" / "schema" / "instructions.schema.json"
)


@pytest.mark.skipif(
    not HASHI_LOCAL_SCHEMA_PATH.is_file(),
    reason="no co-located Hashi checkout at ../Hashi — offline/CI environment",
)
def test_edit_frontmatter_matches_local_hashi_checkout():
    """Structural (parsed-JSON) equality against a real, co-located Hashi
    checkout of instructions.schema.json — the strongest available byte-equality
    check short of the network-based upstream snapshot test in
    test_instruction_render_wire_hygiene.py."""
    hashi = _load(HASHI_LOCAL_SCHEMA_PATH)
    hashi_def = hashi["$defs"]["edit_frontmatter"]
    for label, path in SCHEMA_PATHS.items():
        tomo = _load(path)
        assert tomo["$defs"]["edit_frontmatter"] == hashi_def, label

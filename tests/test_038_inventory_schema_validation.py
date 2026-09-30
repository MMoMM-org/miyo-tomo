#!/usr/bin/env python3
# version: 0.3.3
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
minLength, const, minItems, the editable/parser_label conditional) gets its own
rejection test, constructed to violate exactly that constraint and nothing else —
a schema missing `additionalProperties: false`, an incomplete `required`, or a
missing type/enum/pattern constraint would let a genuinely malformed row through
undetected (spec 037's nine mutations that could not bite is the standing warning
this guards against).

T1.1b adds `parser_label` (required while `editable` is true, permitted absent
when false) and two consumer-facing guards that do not depend on the row set:
the wire schema's `Editable`-marked field count, and a note field's freedom from
task/phase/feature/spec identifiers.

Spec: docs/XDD/specs/038-every-editable-decision-reaches-the-wire/
Ref: PRD/F4; SDD/ADR-7
"""
from __future__ import annotations

import copy
import json
import re
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
WIRE_SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-wire.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _row(**overrides) -> dict:
    row = {
        "id": "D01",
        "markdown_control": "Accept/Approve checkbox on a suggestion.",
        "wire_field": "suggestions[].decision",
        "editable": True,
        "parser_label": ["accept", "approve"],
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


def test_row_rejects_note_wrong_type(schema):
    row = _row(note=42)
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


# ---------------------------------------------------------------------------
# parser_label — the literal(s) the parser matches on. Required while
# editable is true, permitted absent when false (T1.1b).
# ---------------------------------------------------------------------------


def test_row_rejects_parser_label_wrong_type(schema):
    row = _row(parser_label="accept")
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_parser_label_item_wrong_type(schema):
    row = _row(parser_label=[1])
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_parser_label_item_empty_string(schema):
    row = _row(parser_label=[""])
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_parser_label_empty_array(schema):
    row = _row(parser_label=[])
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_row_rejects_missing_parser_label_when_editable_true(schema):
    """The if/then conditional: editable=true requires parser_label."""
    row = _row()
    del row["parser_label"]
    with pytest.raises(ValidationError):
        validate(instance=_doc(row), schema=schema)


def test_conforming_row_with_editable_false_and_no_parser_label_validates(schema):
    """The other direction of the same conditional: a retired control
    (editable=false) has no live match site left to name, so parser_label's
    absence must be permitted — not merely tolerated by accident."""
    row = _row(editable=False, note="Retired control.")
    del row["parser_label"]
    validate(instance=_doc(row), schema=schema)


def test_conforming_row_with_editable_true_and_parser_label_validates(schema):
    validate(instance=_doc(_row(parser_label=["accept", "approve"])), schema=schema)


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


def test_top_level_rejects_non_object_instance(schema):
    """Root type: object — a JSON array at the document root must be rejected."""
    with pytest.raises(ValidationError):
        validate(instance=["not", "an", "object"], schema=schema)


def test_decisions_item_rejects_non_object(schema):
    """decisions[].type: object — a non-object item makes required/
    additionalProperties no-ops under JSON Schema semantics, so this must be
    tested independently of them."""
    doc = {"schema_version": 1, "decisions": [42]}
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


def test_validate_does_not_mutate_shared_schema_fixture(schema):
    """Sanity: the fixtures above mutate copies, never the loaded schema itself."""
    before = copy.deepcopy(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    validate(instance=_doc(_row()), schema=schema)
    assert schema == before


# ---------------------------------------------------------------------------
# The wire schema's `Editable`-marked field count (T1.1b step 4). The join
# T1.2 builds is marked-field → row; a marker DELETED from the wire schema
# makes the corresponding requirement silently disappear — no row goes
# missing, nothing fails on that side. This count is the only thing that
# catches a deleted marker; it stays even after T1.2 exists.
# ---------------------------------------------------------------------------


def _count_editable_marked_descriptions(schema_path: Path) -> int:
    doc = json.loads(schema_path.read_text(encoding="utf-8"))
    count = 0

    def walk(node) -> None:
        nonlocal count
        if isinstance(node, dict):
            description = node.get("description")
            if isinstance(description, str) and description.startswith("Editable"):
                count += 1
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(doc)
    return count


def test_wire_schema_marks_exactly_23_editable_fields():
    """candidate_mocs[].selected and .anchor gained the marker in T1.1b,
    bringing the count from 21 (T1.1) to 23. A future marker removed from
    the wire schema with no corresponding inventory-row change would
    otherwise pass every other test in this file."""
    assert _count_editable_marked_descriptions(WIRE_SCHEMA_PATH) == 23


def _editable_marked_descriptions(schema_path: Path) -> list[str]:
    doc = json.loads(schema_path.read_text(encoding="utf-8"))
    descriptions: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            description = node.get("description")
            if isinstance(description, str) and description.startswith("Editable"):
                descriptions.append(description)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(doc)
    return descriptions


def test_wire_schema_editable_markers_use_uniform_dash_form():
    """Every `Editable`-marked description must read `Editable — …` (em
    dash), not the bare `Editable.` form. The broad `startswith("Editable")`
    predicate used above and by the T1.2 join tolerates both, which is
    exactly the trap: a future guard written against the dashed form finds
    22, not 23, and fails confusingly (this is what happened once already,
    in T1.2's own measurement). This test is that guard, committed rather
    than left to be rediscovered."""
    non_uniform = [
        description
        for description in _editable_marked_descriptions(WIRE_SCHEMA_PATH)
        if not description.startswith("Editable — ")
    ]
    assert not non_uniform, (
        "Editable-marked description(s) not in the uniform 'Editable — ' "
        f"form: {non_uniform}"
    )


# ---------------------------------------------------------------------------
# note values are self-contained — no task/phase/feature/spec identifier
# (T1.1b step 4). A manual read is "a rule someone has to remember" (the
# mechanism SDD/ADR-7 names as what failed in 037); this makes the rule
# mechanical instead.
# ---------------------------------------------------------------------------

_IDENTIFIER_RE = re.compile(
    r"\bT\d+(?:\.\d+)?[a-z]?\b"      # task ids: T1, T1.1, T1.1b
    r"|\bF\d+\b"                      # feature ids: F4
    r"|\bADR-\d+\b"                   # architecture decisions: ADR-7
    r"|\bPhase\s*\d+\b"               # Phase 2
    r"|\bspec\s*0?\d{2,4}\b"          # spec 037, spec037
    r"|\b\d{3,4}\b"                   # bare id-shaped number: 037, 100, 0038
    r"|\bPRD\b",                      # PRD (always paired with an F-id in practice)
    re.IGNORECASE,
)


def test_inventory_notes_carry_no_task_phase_feature_or_spec_identifier():
    doc = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    offenders = [
        (row["id"], row["note"])
        for row in doc["decisions"]
        if row.get("note") and _IDENTIFIER_RE.search(row["note"])
    ]
    assert not offenders, f"note(s) reference an internal identifier: {offenders}"


def test_identifier_regex_bites_on_a_planted_identifier():
    """Ablation: prove the assertion above actually catches something,
    rather than vacuously passing because no note happens to match today."""
    planted = "See T5.2 for the follow-up; ref: PRD/F4, spec 037, ADR-7, Phase 2."
    assert _IDENTIFIER_RE.search(planted), "identifier regex failed to bite a planted identifier"

    # D24's actual pre-fix note (spec 038) — a bare zero-padded spec number
    # with no literal "spec" beside it. The guard exists specifically to
    # catch a reversion to this note, so it belongs in the ablation.
    bare_spec_number = "037 state: the remedy has no wire field yet."
    assert _IDENTIFIER_RE.search(bare_spec_number), (
        "identifier regex failed to bite a bare zero-padded spec number"
    )

    # The two shapes the old bare-zero-padded branch (\b0\d{2}\b) missed:
    # a 3-digit spec number with no leading zero, and a 4-digit id that
    # kills the closing \b on a 3-digit-only pattern.
    bare_unpadded_number = "100 state: the remedy has no wire field yet."
    assert _IDENTIFIER_RE.search(bare_unpadded_number), (
        "identifier regex failed to bite a bare unpadded 3-digit number"
    )
    bare_four_digit_id = "ref 0038 for detail."
    assert _IDENTIFIER_RE.search(bare_four_digit_id), (
        "identifier regex failed to bite a bare 4-digit id"
    )

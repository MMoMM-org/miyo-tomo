#!/usr/bin/env python3
# version: 0.3.0
"""test_hashi_instructions_schema.py — JSON Schema validation tests for hashi-instructions.schema.json.

Covers T4.0 (XDD 024 Phase 4): insert_under_marker action $def.
Also validates insert_under_marker against Tomo's producer schema (instructions.schema.json)
to guard against drift between the two copies.

Spec: docs/XDD/specs/024-tag-handler-framework/
Handoff contract: _outbox/for-hashi/2026-06-23_tomo-to-hashi_insert-under-marker-action.md
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
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "hashi-instructions.schema.json"
PRODUCER_SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def producer_schema() -> dict:
    return json.loads(PRODUCER_SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers — minimal valid envelope + action fixture builders
# ---------------------------------------------------------------------------

def _make_instructions(actions: list) -> dict:
    """Return a minimal valid instruction-set envelope wrapping the given actions."""
    return {
        "schema_version": "1",
        "type": "tomo-instructions",
        "generated": "2026-06-23T14:00:00Z",
        "profile": "miyo",
        "actions": actions,
    }


def _make_insert_under_marker(**overrides) -> dict:
    """Return a minimal valid insert_under_marker action with all required fields."""
    base = {
        "id": "I01",
        "action": "insert_under_marker",
        "target_path": "Efforts/400 On/Tomo Dev Log.md",
        "anchor": {"type": "heading", "value": "Captures"},
        "placement": "inside",
        "content": "### 2026-06-23\n\n- Shipped X (feature)\n- Decided Y (architecture)",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# T4.0 — insert_under_marker happy path
# ---------------------------------------------------------------------------


def test_valid_insert_under_marker_validates(schema):
    """A minimal valid insert_under_marker action passes validation."""
    validate(
        instance=_make_instructions([_make_insert_under_marker()]),
        schema=schema,
    )


def test_valid_insert_under_marker_validates_against_producer_schema(producer_schema):
    """insert_under_marker must also validate against Tomo's producer schema
    (instructions.schema.json).  This test is the RED gate for the drift fix:
    it fails when insert_under_marker is absent from the producer schema and
    passes after the $def + oneOf ref are added."""
    validate(
        instance=_make_instructions([_make_insert_under_marker()]),
        schema=producer_schema,
    )


def test_anchor_callout_type_validates(schema):
    """anchor with type:callout validates — exercises the shared anchor $def's callout branch."""
    action = _make_insert_under_marker(
        anchor={"type": "callout", "value": "[!captures]"}
    )
    validate(instance=_make_instructions([action]), schema=schema)


def test_multiline_content_ok(schema):
    """content with embedded newlines passes validation (multi-line markdown block)."""
    action = _make_insert_under_marker(
        content="### 2026-06-23\n\n- Line one\n- Line two\n\nParagraph here."
    )
    validate(instance=_make_instructions([action]), schema=schema)


# ---------------------------------------------------------------------------
# T4.0 — required field rejections
# ---------------------------------------------------------------------------


def test_missing_content_fails(schema):
    """An insert_under_marker action missing 'content' is rejected."""
    action = _make_insert_under_marker()
    del action["content"]
    with pytest.raises(ValidationError):
        validate(instance=_make_instructions([action]), schema=schema)


def test_missing_target_path_fails(schema):
    """An insert_under_marker action missing 'target_path' is rejected."""
    action = _make_insert_under_marker()
    del action["target_path"]
    with pytest.raises(ValidationError):
        validate(instance=_make_instructions([action]), schema=schema)


def test_missing_anchor_fails(schema):
    """An insert_under_marker action missing 'anchor' is rejected (required shared $def field)."""
    action = _make_insert_under_marker()
    del action["anchor"]
    with pytest.raises(ValidationError):
        validate(instance=_make_instructions([action]), schema=schema)


def test_invalid_placement_fails(schema):
    """An insert_under_marker action with an invalid placement value is rejected."""
    action = _make_insert_under_marker(placement="top")
    with pytest.raises(ValidationError):
        validate(instance=_make_instructions([action]), schema=schema)


# ---------------------------------------------------------------------------
# T4.0 — existing action shapes still validate (regression)
# ---------------------------------------------------------------------------


def test_existing_instructions_no_regression(schema):
    """Existing action types (link_to_moc, update_log_entry) still validate after the new $def."""
    validate(
        instance=_make_instructions([
            {
                "id": "I01",
                "action": "link_to_moc",
                "target_moc": "Tomo Dev Log",
                "anchor": {"type": "heading", "value": "Captures"},
                "placement": "inside",
                "line_to_add": "- [[My Note]]",
            },
            {
                "id": "I02",
                "action": "update_log_entry",
                "daily_note_path": "Calendar/2026-06-23.md",
                "date": "2026-06-23",
                "section": "Daily Log",
                "position": "after_last_line",
                "content": "Worked on tag-handler framework.",
            },
        ]),
        schema=schema,
    )


# ---------------------------------------------------------------------------
# T1.3 (spec 025 Phase 1) — block anchor + replace_section in mirror
# ADR-7: add 'block' to both wire schemas; mirror replace_section, no Tomo emitter.
# ---------------------------------------------------------------------------

TOMO_PRODUCER_SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json"


@pytest.fixture(scope="module")
def tomo_producer_schema() -> dict:
    return json.loads(TOMO_PRODUCER_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_insert_under_marker_with_block_anchor_validates_hashi(schema):
    """insert_under_marker with anchor.type='block' validates against the Hashi mirror schema (ADR-7)."""
    action = _make_insert_under_marker(
        anchor={"type": "block", "value": "| Tool | Action |\n|------|--------|"}
    )
    validate(instance=_make_instructions([action]), schema=schema)


def test_insert_under_marker_with_block_anchor_validates_tomo_producer(tomo_producer_schema):
    """insert_under_marker with anchor.type='block' validates against Tomo's producer schema (ADR-7)."""
    action = _make_insert_under_marker(
        anchor={"type": "block", "value": "| Tool | Action |\n|------|--------|"}
    )
    validate(instance=_make_instructions([action]), schema=tomo_producer_schema)


def test_replace_section_validates_in_mirror(schema):
    """replace_section action validates in the Hashi mirror schema (ADR-7, no Tomo emitter)."""
    action = {
        "id": "I01",
        "action": "replace_section",
        "target_path": "Efforts/Tomo Dev Log.md",
        "anchor": {"type": "heading", "value": "Captures"},
        "content": "| Date | Summary |\n|------|---------|",
    }
    validate(instance=_make_instructions([action]), schema=schema)


def test_replace_section_not_in_tomo_producer(tomo_producer_schema):
    """replace_section action is NOT present in Tomo's producer schema (no emitter; ADR-7).
    Validates our deliberate asymmetry: mirror has replace_section, producer does not."""
    action_refs = {
        entry.get("$ref", "").lstrip("#/$defs/")
        for entry in tomo_producer_schema["properties"]["actions"]["items"]["oneOf"]
    }
    assert "replace_section" not in action_refs, (
        "replace_section should NOT be in Tomo's producer schema actions.items.oneOf — "
        "there is no Tomo emitter (spec 025 ADR-7). If an emitter is added later, "
        "remove this test and add replace_section to instructions.schema.json."
    )


def test_anchor_block_type_in_hashi_schema(schema):
    """The 'block' type is present in the anchor $def enum in the Hashi mirror schema."""
    anchor_enum = schema["$defs"]["anchor"]["properties"]["type"]["enum"]
    assert "block" in anchor_enum, (
        "anchor.$def.type enum must include 'block' in hashi-instructions.schema.json (ADR-7)"
    )


def test_anchor_block_type_in_tomo_producer_schema(tomo_producer_schema):
    """The 'block' type is present in the anchor $def enum in Tomo's producer schema."""
    anchor_enum = tomo_producer_schema["$defs"]["anchor"]["properties"]["type"]["enum"]
    assert "block" in anchor_enum, (
        "anchor.$def.type enum must include 'block' in instructions.schema.json (ADR-7)"
    )

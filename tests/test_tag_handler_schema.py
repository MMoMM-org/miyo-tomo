#!/usr/bin/env python3
# version: 0.3.0
"""test_tag_handler_schema.py — JSON Schema validation tests for tag-handler.schema.json.

Covers T1.2 (XDD 024 Phase 1): handler config schema for the tag-handler framework.

Spec: docs/XDD/specs/024-tag-handler-framework/
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
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "tag-handler.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers — minimal valid fixture builders
# ---------------------------------------------------------------------------

def _make_handler(**overrides) -> dict:
    """Return a minimal valid tag-handler config with all required fields."""
    base = {
        "id": "tsukai",
        "match": {
            "tag_prefix": "MiYo/Tsukai/",
        },
        "action": "insert_under_marker",
        "compose": "Synthesize the batch's captures into one dated status update.",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Happy-path — full tsukai example from SDD §2
# ---------------------------------------------------------------------------


def test_valid_tsukai_handler_validates(schema):
    """The full tsukai handler example from SDD §2 passes validation."""
    handler = {
        "id": "tsukai",
        "enabled": True,
        "match": {
            "tag_prefix": "MiYo/Tsukai/",
            "capture_segments": ["repo"],
            "read_fields": ["category"],
        },
        "action": "insert_under_marker",
        "target": {
            "by": "repo",
            "map": {"Tomo": "Efforts/.../Tomo Dev Log.md"},
        },
        "marker": "## Captures",
        "placement": "inside",
        "compose": "Synthesize the batch's captures into one dated status update, grouped by category.",
    }
    validate(instance=handler, schema=schema)


# ---------------------------------------------------------------------------
# compose — oneOf: string xor array-of-strings
# ---------------------------------------------------------------------------


def test_compose_string_validates(schema):
    """compose as a plain string (LLM directive) passes validation."""
    validate(instance=_make_handler(compose="Write a status update."), schema=schema)


def test_compose_array_of_strings_validates(schema):
    """compose as an array of field name strings (mechanical template) passes validation."""
    validate(instance=_make_handler(compose=["category", "repo"]), schema=schema)


def test_compose_number_fails_oneof(schema):
    """compose as a number is rejected — must be string or array-of-strings."""
    with pytest.raises(ValidationError):
        validate(instance=_make_handler(compose=42), schema=schema)


def test_compose_object_fails_oneof(schema):
    """compose as an object is rejected — must be string or array-of-strings."""
    with pytest.raises(ValidationError):
        validate(instance=_make_handler(compose={"template": "status"}), schema=schema)


# ---------------------------------------------------------------------------
# match.tag_prefix — required
# ---------------------------------------------------------------------------


def test_missing_match_tag_prefix_fails(schema):
    """A handler missing match.tag_prefix is rejected."""
    handler = _make_handler()
    handler["match"] = {}  # tag_prefix omitted
    with pytest.raises(ValidationError):
        validate(instance=handler, schema=schema)


# ---------------------------------------------------------------------------
# action — enum enforcement
# ---------------------------------------------------------------------------


def test_unknown_action_value_fails(schema):
    """An unknown action value is rejected by the schema enum."""
    with pytest.raises(ValidationError):
        validate(instance=_make_handler(action="do_something_unknown"), schema=schema)


# ---------------------------------------------------------------------------
# enabled — default: true (documentation-only in JSON Schema draft-07)
# ---------------------------------------------------------------------------


def test_enabled_defaults_true_when_omitted(schema):
    """The schema declares default:true for enabled; validation passes when omitted."""
    # JSON Schema `default` is documentation-only — the validator does NOT inject it.
    # Assert only that the schema declares the default, not that the instance is mutated.
    handler = _make_handler()
    assert "enabled" not in handler
    validate(instance=handler, schema=schema)  # must not raise
    enabled_prop = schema.get("properties", {}).get("enabled", {})
    assert enabled_prop.get("default") is True, "Schema must declare default:true for 'enabled'"


# ---------------------------------------------------------------------------
# action — deferred actions are schema-valid (resolver enforces, not schema)
# ---------------------------------------------------------------------------


def test_deferred_action_is_schema_valid(schema):
    """Deferred action values (route_to_folder) pass the schema — the resolver rejects them."""
    validate(instance=_make_handler(action="route_to_folder"), schema=schema)


# ---------------------------------------------------------------------------
# W2 — compose empty array is rejected (minItems:1 on array branch)
# ---------------------------------------------------------------------------


def test_compose_empty_array_fails_oneof(schema):
    """compose=[] is rejected — array branch requires at least one field name."""
    with pytest.raises(ValidationError):
        validate(instance=_make_handler(compose=[]), schema=schema)


# ---------------------------------------------------------------------------
# W3 — required top-level fields: id, action, compose
# ---------------------------------------------------------------------------


def test_missing_required_id_fails(schema):
    """A handler missing 'id' is rejected."""
    handler = _make_handler()
    del handler["id"]
    with pytest.raises(ValidationError):
        validate(instance=handler, schema=schema)


def test_missing_required_action_fails(schema):
    """A handler missing 'action' is rejected."""
    handler = _make_handler()
    del handler["action"]
    with pytest.raises(ValidationError):
        validate(instance=handler, schema=schema)


def test_missing_required_compose_fails(schema):
    """A handler missing 'compose' is rejected."""
    handler = _make_handler()
    del handler["compose"]
    with pytest.raises(ValidationError):
        validate(instance=handler, schema=schema)


# ---------------------------------------------------------------------------
# W4 — additionalProperties:false at root level
# ---------------------------------------------------------------------------


def test_extra_top_level_property_fails(schema):
    """An unknown top-level property is rejected (additionalProperties:false)."""
    handler = _make_handler()
    handler["unexpected_field"] = "should fail"
    with pytest.raises(ValidationError):
        validate(instance=handler, schema=schema)


# ---------------------------------------------------------------------------
# T5.2 — shipped tsukai.json on disk validates against the schema
# ---------------------------------------------------------------------------

TSUKAI_JSON_PATH = REPO_ROOT / "tomo" / "config" / "tag-handlers" / "tsukai.json"


def test_shipped_tsukai_json_exists():
    """tomo/config/tag-handlers/tsukai.json must exist on disk (T5.2)."""
    assert TSUKAI_JSON_PATH.exists(), (
        f"Shipped handler not found at {TSUKAI_JSON_PATH}"
    )


def test_shipped_tsukai_json_validates_against_schema(schema):
    """The shipped tsukai.json passes schema validation (T5.2 / AC-2)."""
    handler = json.loads(TSUKAI_JSON_PATH.read_text(encoding="utf-8"))
    validate(instance=handler, schema=schema)


def test_shipped_tsukai_json_id_is_tsukai(schema):
    """The shipped tsukai.json has id='tsukai' (PRD §6)."""
    handler = json.loads(TSUKAI_JSON_PATH.read_text(encoding="utf-8"))
    assert handler["id"] == "tsukai"


def test_shipped_tsukai_json_enabled_true(schema):
    """The shipped tsukai.json has enabled=true (PRD §6)."""
    handler = json.loads(TSUKAI_JSON_PATH.read_text(encoding="utf-8"))
    assert handler.get("enabled") is True


def test_shipped_tsukai_json_match_fields(schema):
    """The shipped tsukai.json match block has tag_prefix, capture_segments, read_fields (PRD §6)."""
    handler = json.loads(TSUKAI_JSON_PATH.read_text(encoding="utf-8"))
    match = handler["match"]
    assert match["tag_prefix"] == "MiYo/Tsukai/"
    assert match["capture_segments"] == ["repo"]
    assert match["read_fields"] == ["category"]


def test_shipped_tsukai_json_action_and_marker(schema):
    """The shipped tsukai.json has action='insert_under_marker', marker='## Captures', placement='after' (PRD §6)."""
    handler = json.loads(TSUKAI_JSON_PATH.read_text(encoding="utf-8"))
    assert handler["action"] == "insert_under_marker"
    assert handler["marker"] == "## Captures"
    assert handler["placement"] == "after"


def test_shipped_tsukai_json_compose_is_string(schema):
    """The shipped tsukai.json compose is a string LLM directive (PRD §6)."""
    handler = json.loads(TSUKAI_JSON_PATH.read_text(encoding="utf-8"))
    assert isinstance(handler["compose"], str)
    assert len(handler["compose"]) > 0


def test_shipped_tsukai_json_target_map_stub_yields_null_for_unknown_repo(schema):
    """The shipped target.map stub does not crash for unknown repos (AC-5 / T5.2)."""
    handler = json.loads(TSUKAI_JSON_PATH.read_text(encoding="utf-8"))
    target = handler.get("target", {})
    assert target.get("by") == "repo"
    # The map is a stub (may be empty or have placeholder values).
    # An unknown repo key must not be present — so it will resolve to null.
    assert "UnknownRepo" not in target.get("map", {})


# ---------------------------------------------------------------------------
# T1.1 (spec 025 Phase 1) — output_format optional object
# FR-15: opt-in object accepted; FR-18: typed cells enforced.
# ---------------------------------------------------------------------------


def _make_handler_with_output_format(**of_overrides) -> dict:
    """Return a handler with a full valid output_format block, merged with overrides."""
    of = {
        "structure": "table_row",
        "order": "append",
        "granularity": "per_item",
        "cells": [{"field": "category"}, {"synthesize": "one-line summary"}],
    }
    of.update(of_overrides)
    return _make_handler(output_format=of)


def test_output_format_full_valid_validates(schema):
    """A handler with a fully populated output_format block passes validation (FR-15)."""
    validate(instance=_make_handler_with_output_format(), schema=schema)


def test_output_format_with_join_validates(schema):
    """output_format with optional join string passes validation."""
    validate(
        instance=_make_handler_with_output_format(join=" | "),
        schema=schema,
    )


def test_output_format_list_item_structure_validates(schema):
    """output_format structure=list_item is a valid enum value."""
    validate(
        instance=_make_handler_with_output_format(structure="list_item"),
        schema=schema,
    )


def test_output_format_absent_still_validates(schema):
    """A handler without output_format still validates (backward compat)."""
    handler = _make_handler()
    assert "output_format" not in handler
    validate(instance=handler, schema=schema)


def test_output_format_unknown_subkey_rejected(schema):
    """An output_format with an unknown sub-key is REJECTED (additionalProperties:false)."""
    handler = _make_handler_with_output_format()
    handler["output_format"]["unknown_key"] = "bad"
    with pytest.raises(ValidationError):
        validate(instance=handler, schema=schema)


def test_output_format_invalid_structure_enum_rejected(schema):
    """output_format.structure with an invalid enum value is REJECTED."""
    with pytest.raises(ValidationError):
        validate(
            instance=_make_handler_with_output_format(structure="paragraph"),
            schema=schema,
        )


def test_output_format_invalid_order_enum_rejected(schema):
    """output_format.order with an invalid enum value is REJECTED."""
    with pytest.raises(ValidationError):
        validate(
            instance=_make_handler_with_output_format(order="random"),
            schema=schema,
        )


def test_output_format_invalid_granularity_enum_rejected(schema):
    """output_format.granularity with an invalid enum value is REJECTED."""
    with pytest.raises(ValidationError):
        validate(
            instance=_make_handler_with_output_format(granularity="chunked"),
            schema=schema,
        )


def test_output_format_cells_empty_array_rejected(schema):
    """output_format.cells=[] is REJECTED (minItems:1)."""
    with pytest.raises(ValidationError):
        validate(
            instance=_make_handler_with_output_format(cells=[]),
            schema=schema,
        )


def test_output_format_cell_unknown_key_rejected(schema):
    """A cell with neither 'field' nor 'synthesize' is REJECTED (FR-18)."""
    with pytest.raises(ValidationError):
        validate(
            instance=_make_handler_with_output_format(
                cells=[{"unknown_key": "value"}]
            ),
            schema=schema,
        )


def test_output_format_cell_with_field_validates(schema):
    """A cell with only {field: ...} passes validation (FR-18)."""
    validate(
        instance=_make_handler_with_output_format(
            cells=[{"field": "category"}]
        ),
        schema=schema,
    )


def test_output_format_cell_with_synthesize_validates(schema):
    """A cell with only {synthesize: ...} passes validation (FR-18)."""
    validate(
        instance=_make_handler_with_output_format(
            cells=[{"synthesize": "one-line summary"}]
        ),
        schema=schema,
    )


def test_output_format_missing_required_structure_rejected(schema):
    """output_format missing required 'structure' is REJECTED."""
    of = {
        "order": "append",
        "granularity": "per_item",
        "cells": [{"field": "category"}],
    }
    with pytest.raises(ValidationError):
        validate(instance=_make_handler(output_format=of), schema=schema)


def test_output_format_missing_required_cells_rejected(schema):
    """output_format missing required 'cells' is REJECTED."""
    of = {
        "structure": "table_row",
        "order": "append",
        "granularity": "per_item",
    }
    with pytest.raises(ValidationError):
        validate(instance=_make_handler(output_format=of), schema=schema)

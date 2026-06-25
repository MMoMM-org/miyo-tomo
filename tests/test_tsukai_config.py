#!/usr/bin/env python3
# version: 0.1.0
"""test_tsukai_config.py — Schema validation and migration tests for tsukai.json.

Covers T7.2 (XDD 025 Phase 7): verifies the migrated tsukai handler config
includes output_format, validates against the schema, and preserves target.map.

Spec: docs/XDD/specs/025-structure-aware-tag-handler-compose/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "tag-handler.schema.json"
TSUKAI_PATH = REPO_ROOT / "tomo" / "config" / "tag-handlers" / "tsukai.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tsukai() -> dict:
    return json.loads(TSUKAI_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T7.2 — migrated tsukai.json validates against the schema
# ---------------------------------------------------------------------------


def test_tsukai_with_output_format_validates(schema, tsukai):
    """Migrated tsukai.json (with output_format) must pass schema validation (T7.2)."""
    validate(instance=tsukai, schema=schema)


def test_tsukai_has_output_format(tsukai):
    """Migrated tsukai.json must have an output_format block (T7.2)."""
    assert "output_format" in tsukai, "tsukai.json must include output_format after T7.2 migration"


def test_tsukai_output_format_structure_is_table_row(tsukai):
    """output_format.structure must be 'table_row' (T7.2 spec: emit table rows)."""
    assert tsukai["output_format"]["structure"] == "table_row"


def test_tsukai_output_format_order_is_newest_first(tsukai):
    """output_format.order must be 'newest_first' (T7.2 spec: newest entries first)."""
    assert tsukai["output_format"]["order"] == "newest_first"


def test_tsukai_output_format_granularity_is_per_item(tsukai):
    """output_format.granularity must be 'per_item' (T7.2 spec)."""
    assert tsukai["output_format"]["granularity"] == "per_item"


def test_tsukai_output_format_cells_has_created_field(tsukai):
    """output_format.cells must include a {field: created} cell (T7.2 spec)."""
    cells = tsukai["output_format"]["cells"]
    field_names = [c["field"] for c in cells if "field" in c]
    assert "created" in field_names, "cells must include {field: created}"


def test_tsukai_output_format_cells_has_category_field(tsukai):
    """output_format.cells must include a {field: category} cell (T7.2 spec)."""
    cells = tsukai["output_format"]["cells"]
    field_names = [c["field"] for c in cells if "field" in c]
    assert "category" in field_names, "cells must include {field: category}"


def test_tsukai_output_format_cells_has_synthesize_cell(tsukai):
    """output_format.cells must include a {synthesize: ...} cell (T7.2 spec)."""
    cells = tsukai["output_format"]["cells"]
    synth_cells = [c for c in cells if "synthesize" in c]
    assert len(synth_cells) >= 1, "cells must include at least one synthesize cell"


def test_tsukai_read_fields_includes_created(tsukai):
    """match.read_fields must include 'created' so the {field: created} cell has a value (T7.2)."""
    read_fields = tsukai["match"].get("read_fields", [])
    assert "created" in read_fields, (
        "match.read_fields must include 'created' after T7.2 migration "
        "— the {field: created} cell requires it"
    )


def test_tsukai_read_fields_still_includes_category(tsukai):
    """match.read_fields must still include 'category' (pre-existing field, must not be dropped)."""
    read_fields = tsukai["match"].get("read_fields", [])
    assert "category" in read_fields


# ---------------------------------------------------------------------------
# T7.2 — target.map preserved (do not overwrite user-owned map entries)
# ---------------------------------------------------------------------------


def test_tsukai_target_map_is_preserved(tsukai):
    """target.map must still exist after migration (T7.2: preserve, do not overwrite)."""
    target = tsukai.get("target", {})
    assert "map" in target, "target.map must remain present after migration"


def test_tsukai_target_map_is_empty_in_repo_source(tsukai):
    """target.map must be {} in the repo source (create-only seed — populated map lives in instance)."""
    target = tsukai.get("target", {})
    assert target["map"] == {}, (
        "Repo-source tsukai.json must have an empty target.map. "
        "The populated map lives in the user-owned instance copy — do not commit real entries here."
    )


# ---------------------------------------------------------------------------
# Pre-existing fields — must not be removed by migration
# ---------------------------------------------------------------------------


def test_tsukai_id_and_enabled_unchanged(tsukai):
    """id and enabled must be unchanged after migration."""
    assert tsukai["id"] == "tsukai"
    assert tsukai.get("enabled") is True


def test_tsukai_compose_string_preserved(tsukai):
    """compose (string directive) must still be present — it is the prose-fallback path."""
    assert isinstance(tsukai.get("compose"), str)
    assert len(tsukai["compose"]) > 0


def test_tsukai_marker_and_action_unchanged(tsukai):
    """marker and action must be unchanged after migration."""
    assert tsukai["action"] == "insert_under_marker"
    assert tsukai["marker"] == "## Captures"

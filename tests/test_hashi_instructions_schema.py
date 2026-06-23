#!/usr/bin/env python3
# version: 0.1.0
"""test_hashi_instructions_schema.py — JSON Schema validation tests for hashi-instructions.schema.json.

Covers T4.0 (XDD 024 Phase 4): insert_under_marker action $def.

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


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


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


def test_anchor_heading_reused(schema):
    """anchor with type:heading and value:'Captures' validates (reuses shared anchor $def)."""
    action = _make_insert_under_marker(
        anchor={"type": "heading", "value": "Captures"}
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

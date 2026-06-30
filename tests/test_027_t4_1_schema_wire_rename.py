#!/usr/bin/env python3
# version: 0.1.0
"""test_027_t4_1_schema_wire_rename.py — TDD coverage for T4.1 schema cutover.

ADR-3: hard rename origin_inbox_item → source_inbox_item in both
instructions.schema.json and hashi-instructions.schema.json; bump
schema_version const "1" → "2". No alias — additionalProperties:false
guarantees the old field is actively rejected.

Spec: docs/XDD/specs/027-suggestions-source-model/plan/phase-4.md (T4.1)
Ref: PRD/AC F4; SDD/ADR-3
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
_TOMO_SCHEMA = REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json"
_HASHI_SCHEMA = REPO_ROOT / "tomo" / "schemas" / "hashi-instructions.schema.json"


@pytest.fixture(scope="module")
def tomo_schema() -> dict:
    return json.loads(_TOMO_SCHEMA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def hashi_schema() -> dict:
    return json.loads(_HASHI_SCHEMA.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers — minimal valid envelope + move_note fixture builders
# ---------------------------------------------------------------------------

def _envelope(actions: list, schema_version: str = "2") -> dict:
    """Return a minimal valid instruction-set envelope wrapping the given actions."""
    return {
        "schema_version": schema_version,
        "type": "tomo-instructions",
        "generated": "2026-06-30T12:00:00Z",
        "profile": "miyo",
        "actions": actions,
    }


def _move_note(field_name: str = "source_inbox_item") -> dict:
    """Return a minimal valid move_note action using the specified inbox field name."""
    action: dict = {
        "id": "I01",
        "action": "move_note",
        "source": "100 Inbox/2026-06-30_1200_test.md",
        "destination": "Atlas/202 Notes/Test Note.md",
        "title": "Test Note",
    }
    action[field_name] = "100 Inbox/test.md"
    return action


# ---------------------------------------------------------------------------
# T4.1 — new field (source_inbox_item) + v2 validates
# ---------------------------------------------------------------------------

class TestNewFieldAndVersionV2:
    """source_inbox_item + schema_version:"2" must validate against both schemas."""

    def test_source_inbox_item_v2_validates_tomo_schema(self, tomo_schema):
        """A move_note with source_inbox_item + schema_version:'2' validates (Tomo schema)."""
        doc = _envelope([_move_note("source_inbox_item")])
        validate(instance=doc, schema=tomo_schema)  # must not raise

    def test_source_inbox_item_v2_validates_hashi_schema(self, hashi_schema):
        """A move_note with source_inbox_item + schema_version:'2' validates (Hashi schema)."""
        doc = _envelope([_move_note("source_inbox_item")])
        validate(instance=doc, schema=hashi_schema)  # must not raise

    def test_source_inbox_item_null_is_allowed_tomo(self, tomo_schema):
        """source_inbox_item may be null for non-inbox notes (Tomo schema)."""
        action = _move_note("source_inbox_item")
        action["source_inbox_item"] = None
        doc = _envelope([action])
        validate(instance=doc, schema=tomo_schema)

    def test_source_inbox_item_null_is_allowed_hashi(self, hashi_schema):
        """source_inbox_item may be null for non-inbox notes (Hashi schema)."""
        action = _move_note("source_inbox_item")
        action["source_inbox_item"] = None
        doc = _envelope([action])
        validate(instance=doc, schema=hashi_schema)


# ---------------------------------------------------------------------------
# T4.1 — old field (origin_inbox_item) is REJECTED — hard cutover, no alias
# ---------------------------------------------------------------------------

class TestOldFieldRejected:
    """origin_inbox_item must be rejected by additionalProperties:false (ADR-3 hard cutover)."""

    def test_origin_inbox_item_rejected_by_tomo_schema(self, tomo_schema):
        """move_note with origin_inbox_item is rejected by Tomo schema (additionalProperties:false)."""
        doc = _envelope([_move_note("origin_inbox_item")])
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=tomo_schema)

    def test_origin_inbox_item_rejected_by_hashi_schema(self, hashi_schema):
        """move_note with origin_inbox_item is rejected by Hashi schema (additionalProperties:false)."""
        doc = _envelope([_move_note("origin_inbox_item")])
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=hashi_schema)


# ---------------------------------------------------------------------------
# T4.1 — schema_version:"1" is REJECTED — const has been bumped to "2"
# ---------------------------------------------------------------------------

class TestSchemaVersionV1Rejected:
    """schema_version:"1" must be rejected by the bumped const (ADR-3 lockstep migration)."""

    def test_v1_rejected_by_tomo_schema(self, tomo_schema):
        """schema_version:"1" is rejected by the Tomo schema after the version bump."""
        doc = _envelope([_move_note("source_inbox_item")], schema_version="1")
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=tomo_schema)

    def test_v1_rejected_by_hashi_schema(self, hashi_schema):
        """schema_version:"1" is rejected by the Hashi schema after the version bump."""
        doc = _envelope([_move_note("source_inbox_item")], schema_version="1")
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=hashi_schema)

#!/usr/bin/env python3
# version: 0.1.0
"""test_routing_plan_schema.py — JSON Schema validation tests for routing-plan.schema.json.

Covers T1.1 (XDD 018 Phase 1): schema structure, required fields, enum values,
nested object shapes, and additionalProperties enforcement.

Spec: docs/XDD/specs/018-agent-architecture-cleanup/
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
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "routing-plan.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Minimal valid routing plan — required fields only
# ---------------------------------------------------------------------------


def test_valid_minimal_routing_plan(schema):
    """Minimal routing plan with only required fields passes validation."""
    validate(
        instance={
            "action": "suggest",
            "timestamp": "2026-05-26T10:00:00Z",
            "inbox_path": "100 Inbox",
        },
        schema=schema,
    )


# ---------------------------------------------------------------------------
# Full routing plan — all optional fields populated
# ---------------------------------------------------------------------------


def test_valid_full_routing_plan(schema):
    """Full routing plan with all fields populated passes validation."""
    validate(
        instance={
            "action": "fan-resolve",
            "timestamp": "2026-05-26T10:00:00Z",
            "inbox_path": "100 Inbox",
            "fresh_sources": [
                {"path": "100 Inbox/note.md", "modified": "2026-05-26T09:00:00Z"},
            ],
            "has_audio": False,
            "approved_suggestions": [
                {"path": "100 Inbox/sug.md", "modified": "2026-05-26T08:00:00Z", "cache_path": ".cache/sug.json"},
            ],
            "approved_fan": [
                {"path": "100 Inbox/fan.md"},
            ],
            "approved_moc_proposals": [
                {"path": "100 Inbox/moc.md", "cache_path": ".cache/moc.json"},
            ],
            "force_atomic_items": [
                {"stem": "note", "source_path": "100 Inbox/note.md", "section_id": "s1"},
            ],
            "pending_approval": [
                {"path": "100 Inbox/pending.md", "doc_type": "suggestions", "message": "awaiting user"},
            ],
            "idle_reasons": ["no new sources", "no approved docs"],
            "drift_indicators": [
                {"path": "100 Inbox/old.md", "type": "checksum_mismatch", "detail": "hash differs"},
            ],
            "skip_stems": ["already-done"],
            "metrics": {
                "total_ms": 23.6,
                "discover_ms": 12.5,
                "kado_calls": 5,
                "docs_cached": 2,
            },
        },
        schema=schema,
    )


# ---------------------------------------------------------------------------
# Missing required fields — each must be rejected
# ---------------------------------------------------------------------------


def test_missing_required_action_rejected(schema):
    """Routing plan missing 'action' is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={"timestamp": "2026-05-26T10:00:00Z", "inbox_path": "100 Inbox"},
            schema=schema,
        )


def test_missing_required_timestamp_rejected(schema):
    """Routing plan missing 'timestamp' is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={"action": "idle", "inbox_path": "100 Inbox"},
            schema=schema,
        )


def test_missing_required_inbox_path_rejected(schema):
    """Routing plan missing 'inbox_path' is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={"action": "suggest", "timestamp": "2026-05-26T10:00:00Z"},
            schema=schema,
        )


# ---------------------------------------------------------------------------
# additionalProperties: false — extra top-level fields rejected
# ---------------------------------------------------------------------------


def test_extra_top_level_field_rejected(schema):
    """Extra top-level field is rejected (additionalProperties: false)."""
    with pytest.raises(ValidationError):
        validate(
            instance={
                "action": "suggest",
                "timestamp": "2026-05-26T10:00:00Z",
                "inbox_path": "100 Inbox",
                "unknown_field": "should fail",
            },
            schema=schema,
        )


# ---------------------------------------------------------------------------
# action enum values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["suggest", "fan-resolve", "synthesize", "transcribe", "idle"])
def test_valid_action_enum_values(schema, action):
    """All valid action enum values pass validation."""
    validate(
        instance={
            "action": action,
            "timestamp": "2026-05-26T10:00:00Z",
            "inbox_path": "100 Inbox",
        },
        schema=schema,
    )


def test_invalid_action_enum_rejected(schema):
    """Invalid action enum value is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={
                "action": "unknown-action",
                "timestamp": "2026-05-26T10:00:00Z",
                "inbox_path": "100 Inbox",
            },
            schema=schema,
        )


# ---------------------------------------------------------------------------
# fresh_sources items
# ---------------------------------------------------------------------------


def test_fresh_sources_valid_shape_passes(schema):
    """fresh_sources item with valid shape (path only) passes."""
    validate(
        instance={
            "action": "suggest",
            "timestamp": "2026-05-26T10:00:00Z",
            "inbox_path": "100 Inbox",
            "fresh_sources": [{"path": "100 Inbox/note.md"}],
        },
        schema=schema,
    )


def test_fresh_sources_extra_property_rejected(schema):
    """fresh_sources item with extra property is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={
                "action": "suggest",
                "timestamp": "2026-05-26T10:00:00Z",
                "inbox_path": "100 Inbox",
                "fresh_sources": [{"path": "100 Inbox/note.md", "extra": "nope"}],
            },
            schema=schema,
        )


def test_fresh_sources_missing_path_rejected(schema):
    """fresh_sources item missing required 'path' is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={
                "action": "suggest",
                "timestamp": "2026-05-26T10:00:00Z",
                "inbox_path": "100 Inbox",
                "fresh_sources": [{"modified": "2026-05-26T09:00:00Z"}],
            },
            schema=schema,
        )


# ---------------------------------------------------------------------------
# approved_suggestions items
# ---------------------------------------------------------------------------


def test_approved_suggestions_valid_shape_passes(schema):
    """approved_suggestions item with valid shape passes."""
    validate(
        instance={
            "action": "suggest",
            "timestamp": "2026-05-26T10:00:00Z",
            "inbox_path": "100 Inbox",
            "approved_suggestions": [
                {
                    "path": "100 Inbox/sug.md",
                    "modified": "2026-05-26T08:00:00Z",
                    "cache_path": ".cache/sug.json",
                }
            ],
        },
        schema=schema,
    )


def test_approved_suggestions_path_only_passes(schema):
    """approved_suggestions item with only required 'path' passes."""
    validate(
        instance={
            "action": "suggest",
            "timestamp": "2026-05-26T10:00:00Z",
            "inbox_path": "100 Inbox",
            "approved_suggestions": [{"path": "100 Inbox/sug.md"}],
        },
        schema=schema,
    )


# ---------------------------------------------------------------------------
# force_atomic_items — requires stem + source_path
# ---------------------------------------------------------------------------


def test_force_atomic_items_valid_passes(schema):
    """force_atomic_items item with stem and source_path passes."""
    validate(
        instance={
            "action": "fan-resolve",
            "timestamp": "2026-05-26T10:00:00Z",
            "inbox_path": "100 Inbox",
            "force_atomic_items": [
                {"stem": "my-note", "source_path": "100 Inbox/my-note.md"},
            ],
        },
        schema=schema,
    )


def test_force_atomic_items_missing_stem_rejected(schema):
    """force_atomic_items item missing 'stem' is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={
                "action": "fan-resolve",
                "timestamp": "2026-05-26T10:00:00Z",
                "inbox_path": "100 Inbox",
                "force_atomic_items": [{"source_path": "100 Inbox/my-note.md"}],
            },
            schema=schema,
        )


def test_force_atomic_items_missing_source_path_rejected(schema):
    """force_atomic_items item missing 'source_path' is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={
                "action": "fan-resolve",
                "timestamp": "2026-05-26T10:00:00Z",
                "inbox_path": "100 Inbox",
                "force_atomic_items": [{"stem": "my-note"}],
            },
            schema=schema,
        )


# ---------------------------------------------------------------------------
# drift_indicators — type enum validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dtype", ["checksum_mismatch", "orphaned_state", "missing_source"])
def test_drift_indicators_valid_type_enum(schema, dtype):
    """drift_indicators with valid type enum values pass."""
    validate(
        instance={
            "action": "idle",
            "timestamp": "2026-05-26T10:00:00Z",
            "inbox_path": "100 Inbox",
            "drift_indicators": [{"path": "100 Inbox/old.md", "type": dtype}],
        },
        schema=schema,
    )


def test_drift_indicators_invalid_type_rejected(schema):
    """drift_indicators with invalid type enum value is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={
                "action": "idle",
                "timestamp": "2026-05-26T10:00:00Z",
                "inbox_path": "100 Inbox",
                "drift_indicators": [{"path": "100 Inbox/old.md", "type": "bad_type"}],
            },
            schema=schema,
        )


def test_drift_indicators_missing_required_path_rejected(schema):
    """drift_indicators item missing 'path' is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={
                "action": "idle",
                "timestamp": "2026-05-26T10:00:00Z",
                "inbox_path": "100 Inbox",
                "drift_indicators": [{"type": "checksum_mismatch"}],
            },
            schema=schema,
        )


def test_drift_indicators_extra_property_rejected(schema):
    """drift_indicators item with extra property is rejected."""
    with pytest.raises(ValidationError):
        validate(
            instance={
                "action": "idle",
                "timestamp": "2026-05-26T10:00:00Z",
                "inbox_path": "100 Inbox",
                "drift_indicators": [
                    {"path": "100 Inbox/old.md", "type": "checksum_mismatch", "extra_field": "nope"},
                ],
            },
            schema=schema,
        )


# ---------------------------------------------------------------------------
# metrics — known properties pass, extras rejected
# ---------------------------------------------------------------------------


def test_metrics_valid_properties_pass(schema):
    """metrics object with all known properties passes."""
    validate(
        instance={
            "action": "suggest",
            "timestamp": "2026-05-26T10:00:00Z",
            "inbox_path": "100 Inbox",
            "metrics": {
                "total_ms": 17.6,
                "discover_ms": 10.0,
                "kado_calls": 3,
                "docs_cached": 1,
            },
        },
        schema=schema,
    )


def test_metrics_extra_property_rejected(schema):
    """metrics object with extra property is rejected (additionalProperties: false)."""
    with pytest.raises(ValidationError):
        validate(
            instance={
                "action": "suggest",
                "timestamp": "2026-05-26T10:00:00Z",
                "inbox_path": "100 Inbox",
                "metrics": {"unknown_metric": 99},
            },
            schema=schema,
        )

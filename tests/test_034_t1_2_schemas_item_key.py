#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t1_2_schemas_item_key.py — JSON Schema validation tests for item_key on the
five item-identity schemas.

Covers T1.2 (XDD 034 Phase 1): item-result.schema.json, state-entry.schema.json,
suggestions-doc.schema.json, suggestions-wire.schema.json and routing-plan.schema.json
all gain a required `item_key` string alongside the existing `stem` field, without
altering `stem`'s own required-ness or declared meaning (ADR-1, ADR-2).

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import ValidationError, validate  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"

# A plausible item_key: a vault-relative path, verbatim, with slashes (ADR-1 — no
# pattern may forbid them).
SLASHY_ITEM_KEY = "100 Inbox/Places/Dresden.md"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def _get_nested(obj: Any, path: tuple) -> Any:
    """Walk `path` (a tuple of dict keys / list indices) into `obj`."""
    for step in path:
        obj = obj[step]
    return obj


# ---------------------------------------------------------------------------
# One case per item-identity location across the five schemas. suggestions-doc
# carries two such locations (sections[] and needs_attention[]), so six cases
# cover all five files.
# ---------------------------------------------------------------------------


def _item_result_doc() -> dict:
    return {
        "schema_version": "1",
        "stem": "my-inbox-note",
        "path": "100 Inbox/my-inbox-note.md",
        "type": "atomic",
        "type_confidence": 0.9,
        "actions": [
            {
                "kind": "create_atomic_note",
                "source_stem": "my-inbox-note",
                "suggested_title": "Some Atomic Note",
                "template": "Atomic Note.md",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": [],
                "tags_to_add": [],
            }
        ],
    }


def _state_entry_doc() -> dict:
    return {
        "run_id": "run-1",
        "stem": "my-inbox-note",
        "path": "100 Inbox/my-inbox-note.md",
        "status": "pending",
        "attempts": 0,
    }


def _suggestions_doc_sections_doc() -> dict:
    return {
        "schema_version": "1",
        "generated": "2026-09-06T00:00:00Z",
        "run_id": "run-1",
        "profile": "miyo",
        "source_items": 1,
        "sections": [
            {
                "id": "S01",
                "stem": "my-inbox-note",
                "actions": [{"kind": "create_atomic_note", "rendered_md": "..."}],
            }
        ],
    }


def _suggestions_doc_needs_attention_doc() -> dict:
    return {
        "schema_version": "1",
        "generated": "2026-09-06T00:00:00Z",
        "run_id": "run-1",
        "profile": "miyo",
        "source_items": 1,
        "sections": [],
        "needs_attention": [{"stem": "my-inbox-note", "error": "boom"}],
    }


def _suggestions_wire_doc() -> dict:
    return {
        "schema_version": "1",
        "generated": "2026-09-06T00:00:00Z",
        "run_id": "run-1",
        "profile": "miyo",
        "source_items": 1,
        "emit_digest": "sha256:" + "0" * 64,
        "suggestions": [
            {
                "id": "S01",
                "stem": "my-inbox-note",
                "title": "Some Atomic Note",
                "template": "Atomic Note.md",
                "location": "Atlas/202 Notes/",
                "tags": [],
                "decision": "approve",
                "keep_source": False,
                "delete_source": False,
                "force_atomic": False,
                "suppressed": False,
                "candidate_mocs": [],
            }
        ],
        "proposed_mocs": [],
        "daily_updates": [],
        "tag_handler_groups": [],
    }


def _routing_plan_doc() -> dict:
    return {
        "action": "fan-resolve",
        "timestamp": "2026-05-26T10:00:00Z",
        "inbox_path": "100 Inbox",
        "force_atomic_items": [
            {"stem": "my-inbox-note", "source_path": "100 Inbox/my-inbox-note.md"}
        ],
    }


# Plain tuples first (so non-pytest code can iterate them directly), then wrapped in
# pytest.param purely to attach readable ids for `-k` selection and failure reports.
RAW_CASES = [
    (
        "item-result.schema.json",
        _item_result_doc,
        (),
        ("properties", "stem"),
        None,
    ),
    (
        "state-entry.schema.json",
        _state_entry_doc,
        (),
        ("properties", "stem"),
        None,
    ),
    (
        "suggestions-doc.schema.json",
        _suggestions_doc_sections_doc,
        ("sections", 0),
        ("properties", "sections", "items", "properties", "stem"),
        None,
    ),
    (
        "suggestions-doc.schema.json",
        _suggestions_doc_needs_attention_doc,
        ("needs_attention", 0),
        ("properties", "needs_attention", "items", "properties", "stem"),
        None,
    ),
    (
        "suggestions-wire.schema.json",
        _suggestions_wire_doc,
        ("suggestions", 0),
        ("properties", "suggestions", "items", "properties", "stem"),
        "Source note stem (read-only).",
    ),
    (
        "routing-plan.schema.json",
        _routing_plan_doc,
        ("force_atomic_items", 0),
        ("properties", "force_atomic_items", "items", "properties", "stem"),
        None,
    ),
]

CASE_IDS = [
    "item-result",
    "state-entry",
    "suggestions-doc-sections",
    "suggestions-doc-needs-attention",
    "suggestions-wire",
    "routing-plan",
]

CASES = [pytest.param(*case, id=case_id) for case, case_id in zip(RAW_CASES, CASE_IDS)]


# ---------------------------------------------------------------------------
# a payload with item_key validates against each modified schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema_file, build_doc, identity_path, _stem_path, _stem_desc", CASES)
def test_item_key_present_validates(schema_file, build_doc, identity_path, _stem_path, _stem_desc):
    schema = _load_schema(schema_file)
    doc = build_doc()
    identity = _get_nested(doc, identity_path)
    identity["item_key"] = "100 Inbox/my-inbox-note.md"
    validate(instance=doc, schema=schema)


# ---------------------------------------------------------------------------
# a payload without item_key is rejected — required, not optional
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema_file, build_doc, identity_path, _stem_path, _stem_desc", CASES)
def test_item_key_absent_rejected(schema_file, build_doc, identity_path, _stem_path, _stem_desc):
    schema = _load_schema(schema_file)
    doc = build_doc()
    identity = _get_nested(doc, identity_path)
    assert "item_key" not in identity
    with pytest.raises(ValidationError):
        validate(instance=doc, schema=schema)


# ---------------------------------------------------------------------------
# stem remains required — removing it (item_key present) is still rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema_file, build_doc, identity_path, _stem_path, _stem_desc", CASES)
def test_stem_still_required(schema_file, build_doc, identity_path, _stem_path, _stem_desc):
    schema = _load_schema(schema_file)
    doc = build_doc()
    identity = _get_nested(doc, identity_path)
    identity["item_key"] = "100 Inbox/my-inbox-note.md"
    del identity["stem"]
    with pytest.raises(ValidationError):
        validate(instance=doc, schema=schema)


# ---------------------------------------------------------------------------
# stem's declared meaning (its description, or lack of one) is unchanged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema_file, build_doc, identity_path, stem_path, stem_desc", CASES)
def test_stem_description_unchanged(schema_file, build_doc, identity_path, stem_path, stem_desc):
    schema = _load_schema(schema_file)
    stem_property = _get_nested(schema, stem_path)
    assert stem_property.get("description") == stem_desc


# ---------------------------------------------------------------------------
# item_key containing slashes validates — ADR-1: no pattern forbids them
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema_file, build_doc, identity_path, _stem_path, _stem_desc", CASES)
def test_item_key_with_slashes_validates(schema_file, build_doc, identity_path, _stem_path, _stem_desc):
    schema = _load_schema(schema_file)
    doc = build_doc()
    identity = _get_nested(doc, identity_path)
    identity["item_key"] = SLASHY_ITEM_KEY
    assert "/" in identity["item_key"]
    validate(instance=doc, schema=schema)


# ---------------------------------------------------------------------------
# item_key must be a non-empty string (minLength: 1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema_file, build_doc, identity_path, _stem_path, _stem_desc", CASES)
def test_item_key_empty_string_rejected(schema_file, build_doc, identity_path, _stem_path, _stem_desc):
    schema = _load_schema(schema_file)
    doc = build_doc()
    identity = _get_nested(doc, identity_path)
    identity["item_key"] = ""
    with pytest.raises(ValidationError):
        validate(instance=doc, schema=schema)


# ---------------------------------------------------------------------------
# sanity: the un-mutated fixture docs themselves are internally consistent
# ---------------------------------------------------------------------------


def test_case_builders_return_independent_copies():
    """Guard against builder functions returning shared mutable state across cases."""
    for _, build_doc, identity_path, _stem_path, _stem_desc in RAW_CASES:
        first = build_doc()
        second = build_doc()
        _get_nested(first, identity_path)["item_key"] = "sentinel"
        assert "item_key" not in _get_nested(second, identity_path)
        assert copy.deepcopy(second) == second

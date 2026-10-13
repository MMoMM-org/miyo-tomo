#!/usr/bin/env python3
# version: 0.1.0
"""test_039_t3_1_wire_v4.py — the suggestions wire moves to v4 and every
attachment conflict on it carries `proposed_dir`, always present, null by
default.

Spec 039 Phase 3 T3.1. The live schema and its shape manifest move together;
the vendored consumer copy (`hashi-suggestions-wire.schema.json`) moved to
"4" in T6.2 once the consumer confirmed, so its const is pinned here too — a
copy left at "3" would make the consumer's real schema reject every document
we emit.

Spec: docs/XDD/specs/039-attachment-conflict-hardening/plan/phase-3.md (T3.1)
Ref: PRD/F1-AC1; SDD/External Interfaces; SDD/ADR-4
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
SCHEMA_PATH = SCHEMAS_DIR / "suggestions-wire.schema.json"
VENDORED_PATH = SCHEMAS_DIR / "hashi-suggestions-wire.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_render_mod():
    spec = importlib.util.spec_from_file_location(
        "suggestions_render_t039_t31", SCRIPTS_DIR / "suggestions-render.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_render_mod()
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

SOURCE = "100 Inbox/Scans/karte.png"
DESTINATION = "Atlas/290 Assets/295 Attachments/karte.png"


def _doc() -> dict:
    """A reducer document carrying one conflict record shaped exactly as
    `detect_attachment_conflicts` builds it after T3.2 (`proposed_dir: None`)."""
    return {
        "schema_version": "1",
        "generated": "2026-10-12T10:00:00Z",
        "run_id": "2026-10-12-1000-wire-v4",
        "profile": "miyo",
        "source_items": 1,
        "sections": [],
        "proposed_mocs": [],
        "needs_attention": [],
        "attachment_conflicts": [
            {
                "source": SOURCE,
                "destination": DESTINATION,
                "same_file": False,
                "owner_source_items": ["100 Inbox/Dresden.md"],
                "proposed_name": "karte (2).png",
                "proposed_dir": None,
            }
        ],
    }


@pytest.fixture
def wire() -> dict:
    return _MOD.build_wire_payload(_doc())


def _with_dir(wire: dict, value) -> dict:
    mutated = copy.deepcopy(wire)
    mutated["attachment_conflicts"][0]["proposed_dir"] = value
    return mutated


def test_emitted_wire_carries_proposed_dir_null_and_version_4(wire):
    assert wire["schema_version"] == "4"
    entry = wire["attachment_conflicts"][0]
    assert "proposed_dir" in entry
    assert entry["proposed_dir"] is None
    jsonschema.validate(instance=wire, schema=_SCHEMA)


def test_proposed_dir_null_validates(wire):
    jsonschema.validate(instance=_with_dir(wire, None), schema=_SCHEMA)


def test_proposed_dir_string_validates(wire):
    jsonschema.validate(instance=_with_dir(wire, "Atlas/Elsewhere"), schema=_SCHEMA)


def test_missing_proposed_dir_fails(wire):
    mutated = copy.deepcopy(wire)
    del mutated["attachment_conflicts"][0]["proposed_dir"]
    with pytest.raises(jsonschema.ValidationError, match="proposed_dir"):
        jsonschema.validate(instance=mutated, schema=_SCHEMA)


@pytest.mark.parametrize("bad", [3, [], {}, True])
def test_non_string_non_null_proposed_dir_fails(wire, bad):
    # Pinned to the `type` keyword: before proposed_dir existed, the same
    # value was rejected by `additionalProperties: false` instead, which
    # would let this test pass with no field declared at all.
    with pytest.raises(jsonschema.ValidationError) as exc:
        jsonschema.validate(instance=_with_dir(wire, bad), schema=_SCHEMA)
    assert exc.value.validator == "type"
    assert list(exc.value.path)[-1] == "proposed_dir"


def test_schema_version_const_is_4():
    assert _SCHEMA["properties"]["schema_version"] == {"const": "4"}


def test_a_version_3_wire_fails(wire):
    mutated = copy.deepcopy(wire)
    mutated["schema_version"] = "3"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=mutated, schema=_SCHEMA)


def test_proposed_dir_is_required_and_marked_editable():
    items = _SCHEMA["properties"]["attachment_conflicts"]["items"]
    assert "proposed_dir" in items["required"]
    prop = items["properties"]["proposed_dir"]
    assert prop["type"] == ["string", "null"]
    assert prop["description"].startswith("Editable — ")


def test_vendored_consumer_copy_declares_version_4():
    vendored = json.loads(VENDORED_PATH.read_text(encoding="utf-8"))
    assert vendored["properties"]["schema_version"] == {"const": "4"}

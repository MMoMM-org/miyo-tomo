#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_summary_field.py — b) content-preview (analyst 1-sentence gist).

Covers the `summary` field flowing analyst → item → reducer render → wire:
  - render_create_atomic_note renders **Summary:** under Suggested name when present,
    and omits the line when absent (back-compat).
  - render_suppressed_atomic renders **Summary:** for a sub-worthy block.
  - _wire_note carries `summary` (and None when the analyst emitted none).
  - item-result.schema.json accepts `summary` and keeps it optional.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_reducer = _load("suggestions_reducer", "suggestions-reducer.py")
_render = _load("suggestions_render", "suggestions-render.py")

render_create_atomic_note = _reducer.render_create_atomic_note
render_suppressed_atomic = _reducer.render_suppressed_atomic
_wire_note = _render._wire_note

GIST = "First-principles thinking rebuilds a solution from fundamental truths instead of analogy."


def _full_action(**over) -> dict:
    a = {
        "kind": "create_atomic_note",
        "suggested_title": "First Principles Thinking",
        "summary": GIST,
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags_to_add": [],
        "atomic_note_worthiness": 0.7,
    }
    a.update(over)
    return a


# ── render: full atomic block ────────────────────────────────────────────────


def test_full_atomic_renders_summary_under_suggested_name():
    md = render_create_atomic_note(_full_action(), "first-principles", "")
    assert f"**Summary:** {GIST}" in md
    # Placement: Summary sits directly under Suggested name.
    name_idx = md.index("**Suggested name:**")
    summ_idx = md.index("**Summary:**")
    tmpl_idx = md.index("**Template:**")
    assert name_idx < summ_idx < tmpl_idx


def test_full_atomic_omits_summary_line_when_absent():
    a = _full_action()
    del a["summary"]
    md = render_create_atomic_note(a, "first-principles", "")
    assert "**Summary:**" not in md


# ── render: suppressed (sub-worthy) block ────────────────────────────────────


def test_suppressed_block_renders_summary():
    a = _full_action(atomic_note_worthiness=0.3, suppressed=True)
    md = render_suppressed_atomic(a, "first-principles")
    assert f"**Summary:** {GIST}" in md
    assert "kept in inbox" in md


def test_suppressed_block_omits_summary_when_absent():
    a = _full_action(atomic_note_worthiness=0.3, suppressed=True)
    del a["summary"]
    md = render_suppressed_atomic(a, "first-principles")
    assert "**Summary:**" not in md


# ── wire projection ──────────────────────────────────────────────────────────


def test_wire_note_carries_summary():
    section = {"id": "S01", "stem": "first-principles"}
    action = {"item": {"title": "First Principles Thinking", "summary": GIST,
                       "worthiness": 0.7}, "candidate_mocs": []}
    w = _wire_note(section, action)
    assert w["summary"] == GIST


def test_wire_note_summary_is_none_when_absent():
    section = {"id": "S01", "stem": "first-principles"}
    action = {"item": {"title": "First Principles Thinking", "worthiness": 0.7},
              "candidate_mocs": []}
    w = _wire_note(section, action)
    assert w["summary"] is None


# ── schema: item-result accepts + keeps summary optional ─────────────────────


def _minimal_result(with_summary: bool) -> dict:
    action = {
        "kind": "create_atomic_note",
        "source_stem": "first-principles",
        "suggested_title": "First Principles Thinking",
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags_to_add": [],
    }
    if with_summary:
        action["summary"] = GIST
    return {
        "schema_version": "1",
        "stem": "first-principles",
        "path": "100 Inbox/first-principles.md",
        "type": "fleeting_note",
        "type_confidence": 0.7,
        "actions": [action],
    }


def test_item_result_schema_accepts_summary_and_is_optional():
    schema = json.loads((SCHEMAS_DIR / "item-result.schema.json").read_text())
    jsonschema.validate(_minimal_result(with_summary=True), schema)
    jsonschema.validate(_minimal_result(with_summary=False), schema)

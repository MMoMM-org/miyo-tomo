#!/usr/bin/env python3
# version: 0.1.0
"""test_instruction_render_edit_frontmatter.py — readable render for edit_frontmatter.

Spec 032 T4.4: register `edit_frontmatter` in render_md.py so the readable
instructions.md names the note, the property and the change, instead of
falling through to the "(unknown action: ...)" placeholder.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location("render_md", SCRIPTS / "lib" / "render_md.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["render_md"] = _mod
_spec.loader.exec_module(_mod)

_render_action_md = _mod._render_action_md
_md_section_for = _mod._md_section_for


def _set_action(**over) -> dict:
    action = {
        "id": "I01",
        "action": "edit_frontmatter",
        "path": "Atlas/202 Notes/foo.md",
        "property": "up",
        "operation": "set",
        "value": ["New MOC"],
        "expected_absent": True,
    }
    action.update(over)
    return action


def _remove_action(**over) -> dict:
    action = {
        "id": "I02",
        "action": "edit_frontmatter",
        "path": "Atlas/202 Notes/bar.md",
        "property": "status",
        "operation": "remove",
        "expected": "draft",
    }
    action.update(over)
    return action


def test_renders_note_property_and_change_for_set():
    md = _render_action_md(_set_action(), {})
    assert "foo" in md  # note stem, via [[foo]]
    assert "up" in md  # property name
    assert "New MOC" in md  # the change
    assert "unknown action" not in md


def test_renders_note_property_and_change_for_remove():
    md = _render_action_md(_remove_action(), {})
    assert "bar" in md
    assert "status" in md
    assert "unknown action" not in md


def test_renders_list_value_without_normalisation():
    action = _set_action(value=["A", "B"])
    md = _render_action_md(action, {})
    # The raw list repr must appear — no flattening/unwrapping/str()-ing.
    assert repr(["A", "B"]) in md


def test_renders_null_expected_without_normalisation():
    action = _remove_action(expected=None)
    md = _render_action_md(action, {})
    assert "None" in md


def test_section_routing_is_moc_links():
    assert _md_section_for(_set_action()) == "moc_links"
    assert _md_section_for(_remove_action()) == "moc_links"

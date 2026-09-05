#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t2_3_move_asset_md_rendering.py — spec 031 T2.3 readable
instruction rendering for move_asset.

Registers move_asset in both render_md.py dispatch points: _md_section_for
(which section of instructions.md it lands in) and _render_action_md (the H3
block content) — so it never falls through to the "(unknown action: ...)"
placeholder.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_md import _md_section_for, _render_action_md  # noqa: E402


def _move_asset_action(**overrides) -> dict:
    action = {
        "id": "I05",
        "action": "move_asset",
        "source": "100 Inbox/Images/karte.jpg",
        "destination": "Atlas/290 Assets/295 Attachments/karte.jpg",
    }
    action.update(overrides)
    return action


def test_move_asset_renders_with_name_source_and_destination():
    md = _render_action_md(_move_asset_action(), {})
    assert "karte.jpg" in md
    assert "100 Inbox/Images/karte.jpg" in md
    assert "Atlas/290 Assets/295 Attachments/karte.jpg" in md


def test_move_asset_never_renders_unknown_action_placeholder():
    md = _render_action_md(_move_asset_action(), {})
    assert "unknown action" not in md


def test_move_asset_routes_to_its_own_section_not_the_new_files_fallthrough():
    """Fails if the explicit move_asset branch is removed — kind would then
    fall through _md_section_for's trailing `return "new_files"` default,
    which is a different value from the dedicated "attachments" section."""
    assert _md_section_for(_move_asset_action()) == "attachments"

#!/usr/bin/env python3
# version: 0.2.2
"""test_031_t2_3_move_asset_md_rendering.py — spec 031 T2.3 readable
instruction rendering for move_asset.

Registers move_asset in both render_md.py dispatch points: _md_section_for
(which section of instructions.md it lands in) and _render_action_md (the H3
block content) — so it never falls through to the "(unknown action: ...)"
placeholder.

Also covers surfacing a skipped attachment (collision or no-basename) into
the rendered "## Skipped — un-appliable actions" section — the report a user
actually sees, not just the stderr warning _build_move_asset_actions prints
(code-quality follow-up to T2.2/T2.4: a skip visible only on stderr is
invisible to the user reviewing the suggestions document).
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_md import _md_section_for, _render_action_md, render_instructions_md  # noqa: E402


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


def test_skipped_attachment_is_surfaced_in_the_rendered_markdown():
    """A skipped attachment (collision or no-basename) must be visible in the
    human-readable document, not just on stderr — the user reviewing the
    suggestions document never sees stderr."""
    metadata = {
        "generated": "2026-09-05T12:00:00Z",
        "skipped_assets": [{
            "source": "100 Inbox/Scans/karte.jpg",
            "destination": "Atlas/290 Assets/295 Attachments/karte.jpg",
            "reason": "destination collision: also resolves to "
                      "'Atlas/290 Assets/295 Attachments/karte.jpg', "
                      "already claimed by '100 Inbox/Images/karte.jpg'",
            "kind": "collision",
        }],
    }
    md = render_instructions_md([], metadata, {})
    assert "## Skipped — un-appliable actions" in md
    assert "100 Inbox/Scans/karte.jpg" in md
    assert "collision" in md.lower()


def test_unrecognized_skip_kind_never_inherits_a_remedy():
    """A missing or unknown "kind" must not silently fall back to either the
    collision or no-basename remedy — that is exactly how a third skip reason
    added later would quietly inherit the wrong instruction. It must render a
    visibly-wrong placeholder instead, the same way an unknown action kind
    does in _render_action_md."""
    metadata = {
        "generated": "2026-09-05T12:00:00Z",
        "skipped_assets": [{
            "source": "100 Inbox/Images/mystery.jpg",
            "destination": None,
            "reason": "some future skip reason",
            "kind": "something_new",
        }],
    }
    md = render_instructions_md([], metadata, {})
    assert "rename" not in md.lower()
    assert "naming conflict" not in md.lower()
    assert "no remedy defined" in md.lower()
    assert "something_new" in md

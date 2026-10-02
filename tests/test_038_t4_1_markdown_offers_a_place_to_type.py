#!/usr/bin/env python3
# version: 0.1.0
"""test_038_t4_1_markdown_offers_a_place_to_type.py — spec 038 T4.1.

`render_attachment_conflicts_block` in `suggestions-reducer.py`'s no-free-name
branch gains empty backticks, so the owner has somewhere to type a name in
the exact case that most needs a rename (owner ruling 2026-09-29, PRD F2).
The shape is constrained by `suggestion-parser.py`'s `_walk_attachment_conflicts`
(spec 038 T4.1 brief, 2026-10-02): the checkbox label must still start with
"rename" and `RENAME_IMPOSSIBLE_MARKER` must stay in the label, so the line is
built from the shared constant rather than a literal string.

This file asserts the exact rendered line in both branches — not a
containment check — because PRD F3-AC1 lets an owner-supplied path appear
anywhere in this block, and a `code not in rendered` style assertion breaks
the moment a file is named with that substring (spec 038 lesson, two such
assertions were already removed from this spec as unsound).

Mutation this guards against: reverting the no-free-name branch to the
markerless pre-038 line (`- [ ] Rename — {RENAME_IMPOSSIBLE_MARKER}`, no
backticks at all) — the exact-string assertion on that branch fails the
moment the backticks are missing, whereas a `RENAME_IMPOSSIBLE_MARKER in
rendered` containment check would not catch it.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_module("suggestions_reducer_t038_t41", "suggestions-reducer.py")

SOURCE = "100 Inbox/Scans/karte.png"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"


def _conflict(**overrides) -> dict:
    base = {
        "source": SOURCE,
        "destination": f"{ASSET_FOLDER}karte.png",
        "same_file": None,
        "owner_source_items": ["100 Inbox/Scans/karte.md"],
        "proposed_name": "karte (2).png",
    }
    base.update(overrides)
    return base


def test_no_free_name_line_carries_empty_backticks():
    conflict = _conflict(proposed_name=None)
    rendered = REDUCER.render_attachment_conflicts_block([conflict], ASSET_FOLDER)
    marker = REDUCER.RENAME_IMPOSSIBLE_MARKER
    lines = rendered.splitlines()
    assert f"- [ ] Rename to `` — {marker}" in lines, rendered
    assert "- [x] Keep in inbox" in lines, rendered


def test_ordinary_conflict_renders_byte_identically_to_today():
    conflict = _conflict(proposed_name="karte (2).png")
    rendered = REDUCER.render_attachment_conflicts_block([conflict], ASSET_FOLDER)
    expected = "\n".join(
        [
            "## Attachment Conflicts",
            "",
            f"### `{SOURCE}`",
            "",
            f"- **Destination:** `{ASSET_FOLDER}karte.png` (already occupied)",
            "- **Embedded by:**",
            "  - [[karte]]",
            "- **File comparison:** The files could not be compared — "
            "check manually before accepting the rename.",
            "",
            "**Remedy — choose one:**",
            f"- [x] Rename to `{ASSET_FOLDER}karte (2).png`",
            "- [ ] Keep in inbox",
        ]
    )
    assert rendered.startswith(expected), rendered

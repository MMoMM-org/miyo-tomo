#!/usr/bin/env python3
"""test_038_t3_4_refusal_reported.py — spec 038 T3.4.

T3.1 built `check_typed_name` (`lib/typed_name_check.py`), closed over three
refusal classes. T3.2 wired it into `_build_move_asset_actions`'s rename
branch, which emits a `typed_name_refused` entry in `skipped_assets` carrying
a prose `reason` from `_typed_name_refusal_reason` (`render_actions.py`).
This file covers the last mile: `render_md.py`'s skipped-assets block turning
that entry into the owner-facing "Attachment not filed" bullet — the new
`elif kind == "typed_name_refused":` branch beside `no_basename`, `collision`
and `vault_collision_held` (`render_md.py:1087-1119`).

Each test asserts the EXACT rendered bullet, not its presence. Spec 037
shipped four defective sentences precisely because every assertion at the
time checked presence (`tests/test_037_t4_4_rendered_text.py`); a containment
check cannot catch a lower-case sentence opening, a doubled path, or a wrong
remedy word next to a correct one. All three refusal classes are covered
because each produces a different `reason` and all three reach this one
bullet.

Entries are built through `_build_move_asset_actions` (the real production
chain), not hand-written, for the same reason `test_037_t4_4` gives: the
`reason` text lives in the SEAM between render_actions.py and render_md.py,
and a fixture that supplies its own `reason` cannot see a regression in
either side of that seam.

Note deliberately absent: no assertion checks that a forbidden phrase, word,
or pattern is ABSENT from the rendered text. Two such assertions were tried
and removed as unsound in this spec (`e3008f9`, `5ed5b76`) — `reason` embeds
the owner's own typed name and the attachment's inbox path, so any
containment rule breaks the moment owner input happens to contain the
forbidden substring (a file named `move_asset.png`, a typed name that is
literally the word `blank`). The exact-string assertion already carries every
criterion a containment check was reaching for: if the whole line is pinned,
no forbidden phrase can be hiding in it.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import _build_move_asset_actions  # noqa: E402
from lib.render_md import render_instructions_md  # noqa: E402

INBOX = "100 Inbox/"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
BASE_METADATA = {"generated": "2026-10-02T12:00:00Z"}

# One source path and one owner-typed `proposed_name` per refusal class,
# chosen to hit exactly one branch of `check_typed_name` each (separator is
# checked before forbidden-character, blank before both).
SEPARATOR_SOURCE = "100 Inbox/Scans/foto.png"
SEPARATOR_TYPED_NAME = "sub/dir.png"

FORBIDDEN_SOURCE = "100 Inbox/Scans/bild.png"
FORBIDDEN_TYPED_NAME = "foo*bar.png"

BLANK_SOURCE = "100 Inbox/Scans/leer.png"
BLANK_TYPED_NAME = "   "

REMEDY_LINE = (
    "Type a usable name for it: before applying, correct the name in the "
    "suggestions document and run `/inbox --pass2 --force`; afterwards, the "
    "note is still in the inbox, so re-run `/inbox` and name it again"
)


def _entry(source_path, attachments) -> dict:
    return {
        "id": "S01", "action": None, "title": "Some Note",
        "source_path": source_path, "rendered_file": f"2026-01-01_0900_{source_path}",
        "destination": "Atlas/202 Notes/", "parent_moc": "", "parent_mocs": [],
        "tags": [], "attachments": attachments,
    }


def _render_refusal_bullet(source: str, typed_name: str) -> str:
    """Run one owner-typed name through the real production chain and
    return the single resulting "Attachment not filed" bullet line."""
    manifest = [_entry("note.md", [source])]
    remedies = [{
        "source": source, "remedy": "rename", "proposed_name": typed_name,
        "name_is_owner_supplied": True,
    }]
    _actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0],
        attachment_conflict_remedies=remedies,
    )
    assert [s["kind"] for s in skipped] == ["typed_name_refused"], skipped
    md = render_instructions_md([], {**BASE_METADATA, "skipped_assets": skipped}, {})
    bullets = [ln for ln in md.splitlines()
               if ln.startswith("- ⚠️ **Attachment not filed:**")]
    assert len(bullets) == 1, bullets
    return bullets[0]


def test_separator_present_renders_the_exact_bullet():
    """Mutation: delete the new `elif kind == "typed_name_refused":` branch
    in render_md.py. A refused name then falls to the `else` arm and the
    bullet's second sentence reads "(No remedy defined for skip kind
    'typed_name_refused' — check render_md.py)." instead of the remedy text
    asserted here.
    """
    ln = _render_refusal_bullet(SEPARATOR_SOURCE, SEPARATOR_TYPED_NAME)
    expected = (
        "- ⚠️ **Attachment not filed:** `100 Inbox/Scans/foto.png` — "
        "typed name refused: `sub/dir.png` contains a path separator, which "
        f"is not allowed in a filename. {REMEDY_LINE}."
    )
    assert ln == expected, ln


def test_forbidden_character_renders_the_exact_bullet():
    """Mutation: delete the new `elif kind == "typed_name_refused":` branch
    in render_md.py. Same fallback as the separator case, now for the
    forbidden-character reason — a second class on the same deleted branch.
    """
    ln = _render_refusal_bullet(FORBIDDEN_SOURCE, FORBIDDEN_TYPED_NAME)
    expected = (
        "- ⚠️ **Attachment not filed:** `100 Inbox/Scans/bild.png` — "
        "typed name refused: `foo*bar.png` contains a character Obsidian "
        f"does not allow in a filename. {REMEDY_LINE}."
    )
    assert ln == expected, ln


def test_blank_renders_the_exact_bullet():
    """Mutation: delete the new `elif kind == "typed_name_refused":` branch
    in render_md.py. Same fallback once more, now for the blank reason — the
    third and last of the three closed refusal classes this branch covers.
    """
    ln = _render_refusal_bullet(BLANK_SOURCE, BLANK_TYPED_NAME)
    expected = (
        "- ⚠️ **Attachment not filed:** `100 Inbox/Scans/leer.png` — "
        f"typed name refused: the typed name is blank. {REMEDY_LINE}."
    )
    assert ln == expected, ln

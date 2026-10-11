#!/usr/bin/env python3
"""test_038_t3_3_owning_note_held.py — spec 038 T3.3.

T3.3's production change is a non-change: `suppress_moves_for_unfiled_
attachments`'s exclusion at `lib/render_actions.py:1569` names exactly one
kind — `vault_collision_held` — and only that kind, by a single equality.
There is no exclusion list. A new kind (`typed_name_refused`, from T3.2) is
therefore never excluded by construction; it falls through to the
suppressing default with no production edit at all. This file is TEST-ONLY.

This is a DELIBERATE DUPLICATE of the assertion already made inside
`tests/test_038_t3_2_typed_name_refusal.py::
test_owner_facing_suppression_sentence_names_no_inbox_path_and_no_refusal_code`
— that test is named for the suppression *sentence*, so the data-loss
guarantee it also carries (a refused typed name holds its owning note) is
unfindable by name. A future edit narrowing that test to its sentence
concern would silently delete the guard. Do not merge this test into that
one, and do not delete either copy.

THE OTHER HALF OF THE DIVERGENCE (criterion 2, already green, not
re-asserted here): `tests/test_037_t3_1_remedy_outcomes.py::
test_vault_collision_held_owning_note_is_still_filed` proves
`vault_collision_held` does NOT hold the owning note. `vault_collision_held`
holds only the attachment, because the owner's *keep in inbox* named the
file, not the note — `typed_name_refused` is the opposite case: the owner's
retyped name was itself unusable, and the note that embeds the attachment
is not filed either. Both directions now have a named guard.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import (  # noqa: E402
    build_actions,
    suppress_moves_for_unfiled_attachments,
)

ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
INBOX = "100 Inbox/"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}

# Legal on macOS, forbidden by Obsidian (FORBIDDEN_CHARS) — same string the
# T3.2 suite uses to show the ruling matters.
UNUSABLE_TYPED_NAME = "foo*bar (2).png"


def _manifest_entry(*, source_path, rendered_file, attachments) -> dict:
    return {
        "id": "S01",
        "action": None,
        "title": "Some Note",
        "source_path": source_path,
        "rendered_file": rendered_file,
        "destination": "Atlas/202 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
        "attachments": attachments,
    }


def _remedy(source, remedy, proposed_name=None, *, name_is_owner_supplied=None) -> dict:
    entry = {"source": source, "remedy": remedy, "proposed_name": proposed_name}
    if name_is_owner_supplied is not None:
        entry["name_is_owner_supplied"] = name_is_owner_supplied
    return entry


def _confirmed_entry(**overrides) -> dict:
    entry = {
        "id": "S01",
        "action": None,
        "title": "Some Note",
        "source_path": "some-note.md",
        "parent_mocs": [],
        "tags": [],
        "candidate_mocs": [],
    }
    entry.update(overrides)
    return entry


def test_typed_name_refused_skip_holds_its_owning_note():
    """Mutation: widen the `:1569` equality from `entry.get("kind") ==
    "vault_collision_held"` to `entry.get("kind") in ("vault_collision_held",
    "typed_name_refused")` — i.e. add `typed_name_refused` to the exclusion.
    With that mutation applied, the owning note is filed to
    `Atlas/202 Notes/Some Note.md` while its attachment stays behind in the
    inbox — exactly the data loss this guard exists to catch. Verified live
    in a throwaway worktree: baseline green, mutation turns this test red
    with that note filed and no suppression recorded for it.
    """
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/other.png"],
        ),
    ]
    confirmed = [_confirmed_entry(source_path="karte.md")]
    remedies = [
        _remedy(
            "100 Inbox/Scans/other.png", "rename", UNUSABLE_TYPED_NAME,
            name_is_owner_supplied=True,
        )
    ]
    actions, skipped_assets = build_actions(
        manifest, confirmed, [], [], CFG, attachment_conflict_remedies=remedies,
    )
    assert [s["kind"] for s in skipped_assets] == ["typed_name_refused"]
    kept, suppressions = suppress_moves_for_unfiled_attachments(actions, skipped_assets)

    move_notes = [a for a in kept if a["action"] == "move_note"]
    assert move_notes == [], f"the owning note must be held, not filed: {move_notes}"
    assert len(suppressions) == 1

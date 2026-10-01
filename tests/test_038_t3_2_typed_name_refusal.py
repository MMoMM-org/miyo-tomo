#!/usr/bin/env python3
"""test_038_t3_2_typed_name_refusal.py — spec 038 T3.2.

T3.1 built `check_typed_name` (`lib/typed_name_check.py`) as a pure function
on a string. This file covers the wiring: `_build_move_asset_actions`'s
rename branch (`lib/render_actions.py`) now calls it, but ONLY when the
remedy record's `name_is_owner_supplied` is True — the flag spec 038 added to
both of `suggestion-parser.py`'s producers (covered separately, by the
updated assertions in `tests/test_037_t3_0_remedy_transport.py` and
`tests/test_037_remedy_lost_on_the_wire_path.py`) because `proposed_name`
itself carries no provenance.

THE DECISIVE PAIR (owner ruling 2026-10-01): the SAME unusable string —
`foo*bar (2).png`, legal on macOS, forbidden by Obsidian — must be REFUSED
when `name_is_owner_supplied` is True and must behave EXACTLY AS TODAY
(emits the move) when it is False or absent. A suite that only covered the
refusal side would also pass against an implementation that checks every
`rename`, which is the behaviour this ruling exists to prevent. Both sides
are covered below as one pair (`test_unusable_*`).

REGRESSION ANCHOR: `tests/test_037_t3_1_remedy_outcomes.py::
test_a_remedys_destination_still_goes_through_the_claimed_check` supplies no
flag at all and must keep passing UNCHANGED — not modified by this file, run
alongside it as part of the full suite.

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

ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
INBOX = "100 Inbox/"

# Legal on macOS, forbidden by Obsidian (FORBIDDEN_CHARS) — the exact string
# the task text uses to show the ruling matters: run the reducer's own
# `f"{stem} ({n}).{ext}"` pattern over a basename containing `*` and this is
# what comes out.
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


# ---------------------------------------------------------------------------
# The decisive pair: the SAME string, both sides of the flag.
# ---------------------------------------------------------------------------


def test_unusable_typed_name_is_refused_when_owner_supplied():
    """Mutation: drop the `name_is_owner_supplied` gate and call
    `check_typed_name` unconditionally — this alone would not distinguish
    the gated case from the ungated one, so see the paired test below for
    the mutation this half cannot catch by itself (checking every rename)."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/other.png"],
        ),
    ]
    remedies = [
        _remedy(
            "100 Inbox/Scans/other.png", "rename", UNUSABLE_TYPED_NAME,
            name_is_owner_supplied=True,
        )
    ]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert actions == [], f"a refused typed name must emit no move: {actions}"
    assert len(skipped) == 1
    assert skipped[0]["source"] == "100 Inbox/Scans/other.png"
    assert skipped[0]["kind"] == "typed_name_refused"
    assert skipped[0]["reason"] == "forbidden_character"


def test_unusable_computed_name_behaves_exactly_as_today_when_not_owner_supplied():
    """Mutation: make the check run regardless of `name_is_owner_supplied`
    (or default a missing/False flag to True) — this is the behaviour the
    owner's 2026-10-01 ruling exists to prevent: `_propose_asset_name`
    (suggestions-reducer.py) sanitises nothing and can legally produce this
    exact basename, so checking it here would refuse a name Pass 1 itself
    computed, violating F3's ninth acceptance criterion ("this feature
    constrains typed names only"). Paired with the test above: same string,
    opposite flag, opposite outcome."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/other.png"],
        ),
    ]
    remedies = [
        _remedy(
            "100 Inbox/Scans/other.png", "rename", UNUSABLE_TYPED_NAME,
            name_is_owner_supplied=False,
        )
    ]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert skipped == [], f"a computed name must never be refused: {skipped}"
    assert len(actions) == 1
    assert actions[0]["action"] == "move_asset"
    assert actions[0]["source"] == "100 Inbox/Scans/other.png"
    assert actions[0]["destination"] == (
        f"Atlas/290 Assets/295 Attachments/{UNUSABLE_TYPED_NAME}"
    )


def test_unusable_typed_name_behaves_exactly_as_today_when_flag_absent():
    """A remedy record predating this field (no `name_is_owner_supplied` key
    at all — e.g. a foreign/older caller) must behave exactly like `False`,
    not like `True`. Mutation: read the flag with a truthy default instead
    of `.get(...)`'s natural `None`/falsy result."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/other.png"],
        ),
    ]
    remedies = [_remedy("100 Inbox/Scans/other.png", "rename", UNUSABLE_TYPED_NAME)]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert skipped == [], f"a flag-absent remedy must not be checked: {skipped}"
    assert len(actions) == 1
    assert actions[0]["destination"] == (
        f"Atlas/290 Assets/295 Attachments/{UNUSABLE_TYPED_NAME}"
    )


# ---------------------------------------------------------------------------
# A usable typed name, owner-supplied, is filed normally.
# ---------------------------------------------------------------------------


def test_usable_typed_name_emits_the_move_when_owner_supplied():
    """Mutation: refuse every `name_is_owner_supplied` rename unconditionally
    — a usable name must still reach `_asset_dest_join` and emit its move."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/karte.png"],
        ),
    ]
    remedies = [
        _remedy(
            "100 Inbox/Scans/karte.png", "rename", "karte (2).png",
            name_is_owner_supplied=True,
        )
    ]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert skipped == []
    assert len(actions) == 1
    assert actions[0]["destination"] == (
        "Atlas/290 Assets/295 Attachments/karte (2).png"
    )


# ---------------------------------------------------------------------------
# A usable typed name that collides run-locally is "collision", never
# "typed_name_refused" — the one combination the pre-existing regression
# anchor cannot cover, because it needs the new field.
# ---------------------------------------------------------------------------


def test_usable_owner_supplied_name_that_collides_run_locally_is_collision_not_refused():
    """Mutation: let the typed-name check run AFTER the `claimed` check
    instead of before `_asset_dest_join`, or let it swallow the collision
    case — a USABLE name that happens to collide with another attachment
    already claimed in this run must still be reported as `kind:
    "collision"`, never `typed_name_refused`: the name itself was fine, the
    problem is a destination clash, and the two must not be told as one."""
    manifest = [
        _manifest_entry(
            source_path="one.md", rendered_file="2026-01-01_0900_one.md",
            attachments=["100 Inbox/A/orig.png"],
        ),
        _manifest_entry(
            source_path="two.md", rendered_file="2026-01-01_0901_two.md",
            attachments=["100 Inbox/B/other.png"],
        ),
    ]
    remedies = [
        _remedy(
            "100 Inbox/B/other.png", "rename", "orig.png",
            name_is_owner_supplied=True,
        )
    ]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert len(actions) == 1
    assert actions[0]["source"] == "100 Inbox/A/orig.png"
    assert len(skipped) == 1
    assert skipped[0]["source"] == "100 Inbox/B/other.png"
    assert skipped[0]["kind"] == "collision", (
        f"a usable name's run-local collision must stay 'collision': {skipped[0]}"
    )


# ---------------------------------------------------------------------------
# The degraded-rename guard (render_actions.py ~787-789) is a truthiness
# test: None degrades to keep_in_inbox, but " " does not.
# ---------------------------------------------------------------------------


def test_whitespace_only_proposed_name_reaches_the_rename_branch_and_is_refused():
    """`" "` is truthy, so the degraded-rename guard
    (`remedy == "rename" and not remedy_entry.get("proposed_name")`) does
    NOT fire for it — it reaches the rename branch, and when owner-supplied
    must be refused there as `blank` (`check_typed_name` strips before
    judging blankness). Mutation: let the degraded-rename guard swallow this
    case (e.g. test falsiness after `.strip()`) — it would silently become
    `vault_collision_held` instead of `typed_name_refused`, hiding that the
    owner actually typed something unusable."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/karte.png"],
        ),
    ]
    remedies = [
        _remedy(
            "100 Inbox/Scans/karte.png", "rename", " ",
            name_is_owner_supplied=True,
        )
    ]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert actions == []
    assert len(skipped) == 1
    assert skipped[0]["kind"] == "typed_name_refused"
    assert skipped[0]["reason"] == "blank"


def test_whitespace_only_proposed_name_without_flag_still_degrades_as_before():
    """The same `" "` string, without the flag, must still reach the rename
    branch (truthy) and fall through to `_asset_dest_join` exactly as it did
    before this task — there is no blank-string special case on the
    computed-name path."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/karte.png"],
        ),
    ]
    remedies = [_remedy("100 Inbox/Scans/karte.png", "rename", " ")]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert skipped == []
    assert len(actions) == 1
    assert actions[0]["destination"] == "Atlas/290 Assets/295 Attachments/ "


# ---------------------------------------------------------------------------
# No move_asset action is ever emitted alongside a typed_name_refused skip
# for the same source — the absence check the regression anchor's own
# docstring warns a skip-only test cannot see.
# ---------------------------------------------------------------------------


def test_refused_source_produces_no_move_asset_anywhere_in_actions():
    """Mutation: append the skip entry but omit the `continue` — a test
    inspecting only `skipped` would not notice a `move_asset` for the same
    source slipping into `actions` alongside it."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/bad.png"],
        ),
    ]
    remedies = [
        _remedy(
            "100 Inbox/Scans/bad.png", "rename", UNUSABLE_TYPED_NAME,
            name_is_owner_supplied=True,
        )
    ]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    sources_in_actions = [a["source"] for a in actions if a["action"] == "move_asset"]
    assert "100 Inbox/Scans/bad.png" not in sources_in_actions
    assert len(skipped) == 1

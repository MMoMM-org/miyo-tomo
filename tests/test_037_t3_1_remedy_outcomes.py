#!/usr/bin/env python3
# version: 0.2.0
"""test_037_t3_1_remedy_outcomes.py — spec 037 T3.1.

T3.0 built the transport: `_build_move_asset_actions` accepts
`attachment_conflict_remedies` (records of `{source, remedy, proposed_name}`,
always a list) and ignores it. This file makes it act.

Covers, per `docs/XDD/specs/037-asset-destination-collision-is-a-pass1-
decision/plan/phase-3.md` T3.1:

  1. `rename` emits a move to `_asset_dest_join(asset_folder, proposed_name)`.
  2. `keep_in_inbox` emits no move and one `skipped_assets` entry with
     `kind: vault_collision_held`.
  3. `vault_collision_held` does NOT hold the owning note in
     `suppress_moves_for_unfiled_attachments` — the standing ruling
     (`requirements.md:374-382`): *keep in inbox* names the attachment, not
     the note.
  4. `ignore` emits the move unchanged against the occupied destination and
     records nothing in `skipped_assets`.
  5. A `rename` arriving with `proposed_name: null` degrades to
     `keep_in_inbox` — a markdown/JSON desync, NOT ADR-4's 99-variants case
     (that path is closed by the renderer and T2.4's parser before Pass 2).
  6. A conflict gone by Pass 2 (no remedy record for a source) emits the
     plain move.
  7. The in-run collision path is untouched: a remedy's recomputed
     destination still goes through the `claimed` check like any other.

Anchored by running `tests/test_031_t2_4_destination_collision_guard.py` and
`tests/test_034_t6_0_case_folded_destination_keys.py` green, unmodified.

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
    _build_move_asset_actions,
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


def _manifest_entry(*, source_path, rendered_file, attachments=None, **overrides) -> dict:
    entry = {
        "id": "S01",
        "action": None,
        "title": "Some Note",
        "source_path": source_path,
        "rendered_file": rendered_file,
        "destination": "Atlas/202 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
    }
    if attachments is not None:
        entry["attachments"] = attachments
    entry.update(overrides)
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


def _remedy(source, remedy, proposed_name=None) -> dict:
    return {"source": source, "remedy": remedy, "proposed_name": proposed_name}


# ──────────────────────────────────────────────────────────────────────────
# 1. rename -> _asset_dest_join(asset_folder, proposed_name)
# ──────────────────────────────────────────────────────────────────────────

def test_rename_emits_move_to_the_proposed_basename():
    """Mutation: use `proposed_name` directly as the destination instead of
    joining it through `_asset_dest_join(asset_folder, proposed_name)` — the
    move would target `karte (2).png` at the vault ROOT, not inside the asset
    folder. This is the defect `SDD:215` was corrected for."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/karte.png"],
        ),
    ]
    remedies = [_remedy("100 Inbox/Scans/karte.png", "rename", "karte (2).png")]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert skipped == []
    assert len(actions) == 1
    assert actions[0]["action"] == "move_asset"
    assert actions[0]["source"] == "100 Inbox/Scans/karte.png"
    assert actions[0]["destination"] == (
        "Atlas/290 Assets/295 Attachments/karte (2).png"
    )


# ──────────────────────────────────────────────────────────────────────────
# 2. keep_in_inbox -> no move, one skipped_assets entry, kind vault_collision_held
# ──────────────────────────────────────────────────────────────────────────

def test_keep_in_inbox_emits_no_move_and_records_vault_collision_held():
    """Mutation: build the skip entry but omit the `continue` that withholds
    the move — a test inspecting only `skipped` cannot see the move that
    slipped out alongside it, so this asserts the move's ABSENCE in `actions`,
    not merely the skip entry's presence."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/karte.png"],
        ),
    ]
    remedies = [_remedy("100 Inbox/Scans/karte.png", "keep_in_inbox")]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert actions == [], (
        f"keep_in_inbox must emit no move at all, found: {actions}"
    )
    assert len(skipped) == 1
    assert skipped[0]["source"] == "100 Inbox/Scans/karte.png"
    assert skipped[0]["kind"] == "vault_collision_held"


# ──────────────────────────────────────────────────────────────────────────
# 3. vault_collision_held does not hold the owning note
# ──────────────────────────────────────────────────────────────────────────

def test_vault_collision_held_owning_note_is_still_filed():
    """Mutation: omit the `vault_collision_held` exclusion from
    `suppress_moves_for_unfiled_attachments`'s loop over `skipped_assets` —
    the owning note would be held in the inbox, which is the behaviour the
    owner ruled against (`requirements.md:374-382`): *keep in inbox* names
    the attachment, not the note."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/karte.png"],
        ),
    ]
    confirmed = [_confirmed_entry(source_path="karte.md")]
    remedies = [_remedy("100 Inbox/Scans/karte.png", "keep_in_inbox")]
    actions, skipped_assets = build_actions(
        manifest, confirmed, [], [], CFG, attachment_conflict_remedies=remedies,
    )
    assert [s["kind"] for s in skipped_assets] == ["vault_collision_held"]
    kept, suppressions = suppress_moves_for_unfiled_attachments(actions, skipped_assets)
    move_notes = [a for a in kept if a["action"] == "move_note"]
    assert [m["source_inbox_item"] for m in move_notes] == ["100 Inbox/karte.md"], (
        "the owning note must still be filed — only the attachment stays "
        f"behind: {move_notes}"
    )
    assert suppressions == [], (
        f"vault_collision_held must not produce a suppression at all: {suppressions}"
    )


# ──────────────────────────────────────────────────────────────────────────
# 4. ignore -> move unchanged, nothing recorded in skipped_assets
# ──────────────────────────────────────────────────────────────────────────

def test_ignore_emits_the_move_unchanged_and_skips_nothing():
    """Mutation: make `ignore` behave like `keep_in_inbox` (withhold the move
    and record a skip entry) — `ignore` must emit the move against the
    occupied destination exactly as a conflict-free attachment would, and
    `skipped_assets` must stay empty."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/karte.png"],
        ),
    ]
    remedies = [_remedy("100 Inbox/Scans/karte.png", "ignore")]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert skipped == [], f"ignore must record nothing: {skipped}"
    assert len(actions) == 1
    assert actions[0]["source"] == "100 Inbox/Scans/karte.png"
    assert actions[0]["destination"] == "Atlas/290 Assets/295 Attachments/karte.png"


# ──────────────────────────────────────────────────────────────────────────
# 5. rename with proposed_name: null degrades to keep_in_inbox
# ──────────────────────────────────────────────────────────────────────────

def test_rename_with_null_proposed_name_degrades_to_keep_in_inbox():
    """Mutation: degrade to `ignore` instead of `keep_in_inbox` — `ignore`
    would emit a move to the ORIGINAL (still-occupied) destination, a move
    certain to be refused at apply. This is the markdown/JSON desync route
    (a stale `--suggestions-doc`, a hand edit, a Pass-1 re-run between review
    and render) — NOT ADR-4's 99-variants case, which the renderer and
    T2.4's parser already resolve to `ignore` before Pass 2 ever runs."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/karte.png"],
        ),
    ]
    confirmed = [_confirmed_entry(source_path="karte.md")]
    remedies = [_remedy("100 Inbox/Scans/karte.png", "rename", proposed_name=None)]

    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert actions == [], f"a nameless rename must emit no move: {actions}"
    assert len(skipped) == 1
    assert skipped[0]["kind"] == "vault_collision_held"

    # And the owning note is still filed, exactly as any other
    # vault_collision_held entry.
    all_actions, skipped_assets = build_actions(
        manifest, confirmed, [], [], CFG, attachment_conflict_remedies=remedies,
    )
    kept, suppressions = suppress_moves_for_unfiled_attachments(all_actions, skipped_assets)
    move_notes = [a for a in kept if a["action"] == "move_note"]
    assert [m["source_inbox_item"] for m in move_notes] == ["100 Inbox/karte.md"]
    assert suppressions == []


# ──────────────────────────────────────────────────────────────────────────
# 6. a conflict gone by Pass 2 emits the plain move
# ──────────────────────────────────────────────────────────────────────────

def test_unmatched_source_emits_the_plain_move():
    """Mutation: treat a `source` with no matching remedy record as
    `keep_in_inbox` — a conflict that no longer exists by Pass 2 (re-run of
    Pass 1 cleared it, or the attachment was never conflicted at all) must
    emit the plain move like any other attachment, not withhold it."""
    manifest = [
        _manifest_entry(
            source_path="karte.md", rendered_file="2026-01-01_0900_karte.md",
            attachments=["100 Inbox/Scans/karte.png"],
        ),
    ]
    # attachment_conflict_remedies names a DIFFERENT source entirely.
    remedies = [_remedy("100 Inbox/Scans/other.png", "keep_in_inbox")]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert skipped == []
    assert len(actions) == 1
    assert actions[0]["source"] == "100 Inbox/Scans/karte.png"
    assert actions[0]["destination"] == "Atlas/290 Assets/295 Attachments/karte.png"


# ──────────────────────────────────────────────────────────────────────────
# 7. the in-run collision path is untouched by a remedy
# ──────────────────────────────────────────────────────────────────────────

def test_a_remedys_destination_still_goes_through_the_claimed_check():
    """Mutation: let a remedy short-circuit the `claimed` check (emit its
    move unconditionally once a remedy is found) — a `rename` whose
    recomputed destination happens to collide with another attachment
    already claimed IN THIS RUN must still be skipped as a `collision`, not
    emitted. The same mutation would also let a second in-run duplicate with
    no remedy at all through, which is exactly what
    `tests/test_031_t2_4_destination_collision_guard.py` and
    `tests/test_034_t6_0_case_folded_destination_keys.py` already guard —
    run unmodified alongside this file as the anchor."""
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
    # "two.md"'s attachment is renamed to a basename that collides with
    # "one.md"'s attachment's (unrelated, unremedied) destination.
    remedies = [_remedy("100 Inbox/B/other.png", "rename", "orig.png")]
    actions, skipped = _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )
    assert len(actions) == 1
    assert actions[0]["source"] == "100 Inbox/A/orig.png"
    assert actions[0]["destination"] == "Atlas/290 Assets/295 Attachments/orig.png"
    assert len(skipped) == 1, f"the renamed collision must still be caught: {skipped}"
    assert skipped[0]["source"] == "100 Inbox/B/other.png"
    assert skipped[0]["kind"] == "collision"
    assert skipped[0]["destination"] == "Atlas/290 Assets/295 Attachments/orig.png"


def test_a_degraded_rename_is_not_reported_as_the_owners_choice():
    """Mutation: collapse the two `reason` strings back into one, so the
    degraded-rename case reuses the held case's "the owner chose not to
    file" wording. Both outcomes are `vault_collision_held` and both
    withhold the move, so every other assertion in this file stays green
    under that mutation — only the reported reason distinguishes them.

    The distinction is not cosmetic. A held attachment is the owner's own
    instruction. A degraded rename is the owner asking to file it under a
    name this run could not recover, and telling them they *chose* to keep
    it in the inbox reports a decision they never made.
    """
    def _held(remedy, proposed_name):
        manifest = [
            _manifest_entry(
                source_path="karte.md",
                rendered_file="2026-01-01_0900_karte.md",
                attachments=["100 Inbox/Scans/karte.png"],
            ),
        ]
        remedies = [
            _remedy("100 Inbox/Scans/karte.png", remedy, proposed_name=proposed_name)
        ]
        _, skipped = _build_move_asset_actions(
            manifest, INBOX, ASSET_FOLDER, [0],
            attachment_conflict_remedies=remedies,
        )
        assert len(skipped) == 1
        assert skipped[0]["kind"] == "vault_collision_held"
        return skipped[0]["reason"]

    chosen = _held("keep_in_inbox", None)
    degraded = _held("rename", None)

    assert chosen != degraded, (
        "one outcome, two routes — the owner's own instruction and a rename "
        f"this run could not honour must not read alike: {chosen!r}"
    )
    assert "the owner chose" in chosen
    assert "the owner chose" not in degraded, (
        "a degraded rename must never be reported as a choice the owner made: "
        f"{degraded!r}"
    )
    # Both still name the occupied destination — that is the fact neither the
    # entry's other fields nor the rendered bullet's lead carries.
    #
    # Neither names the ATTACHMENT any more, and the earlier version of this
    # test asserted the opposite on a premise that was measurably wrong: it
    # claimed "the reason is the one place the owner learns which file stayed
    # put". It is not. `skipped_assets[].source` carries it structurally, the
    # only renderer opens its bullet with it in backticks, and Hashi does not
    # read `skipped_assets` at all (checked 2026-09-28) — so the path was
    # rendered twice on one line, in two quoting styles (spec 037 T4.4).
    for reason in (chosen, degraded):
        assert "Atlas/290 Assets/295 Attachments/karte.png" in reason
        assert "100 Inbox/Scans/karte.png" not in reason, (
            "the attachment path belongs to `source` and the bullet's lead, "
            f"not to the reason: {reason!r}"
        )

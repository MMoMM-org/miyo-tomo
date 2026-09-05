#!/usr/bin/env python3
# version: 0.2.1
"""test_031_t2_4_destination_collision_guard.py — spec 031 T2.4 destination
collision guard for _build_move_asset_actions, plus the empty-basename skip
folded in here (same skip-and-report machinery, same code-quality review).

ADR-3: on a destination collision between two DIFFERENT source files, skip
the second and report it — never silently overwrite. Renaming is explicitly
deferred (Should-have). The same file resolved twice is NOT a collision — the
global dedup from T2.2 handles it before the guard is ever consulted.

A source path with no basename (empty, or ending in "/") is a second,
distinct skip reason: _asset_dest_join raises ValueError rather than
returning a bare folder path, and _build_move_asset_actions catches it,
skips that one attachment, and reports it — the run is not aborted.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import _build_move_asset_actions, build_actions  # noqa: E402

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


def test_second_colliding_attachment_is_skipped_and_reported(capsys):
    """Two DIFFERENT files sharing a basename land on the same destination.
    The first claims it; the second is skipped, not silently overwritten —
    fails if the guard is missing and both get emitted (two actions, or the
    second one clobbers the first in some other observable way)."""
    manifest = [
        _manifest_entry(
            source_path="a.md", rendered_file="2026-01-01_0900_a.md",
            attachments=["100 Inbox/Images/karte.jpg"],
        ),
        _manifest_entry(
            source_path="b.md", rendered_file="2026-01-01_0901_b.md",
            attachments=["100 Inbox/Scans/karte.jpg"],
        ),
    ]
    actions, skipped = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0])
    assert len(actions) == 1
    assert actions[0]["source"] == "100 Inbox/Images/karte.jpg"
    err = capsys.readouterr().err
    assert "100 Inbox/Scans/karte.jpg" in err
    assert "collision" in err.lower()
    assert len(skipped) == 1
    assert skipped[0]["source"] == "100 Inbox/Scans/karte.jpg"
    assert "collision" in skipped[0]["reason"].lower()
    assert skipped[0]["kind"] == "collision"


def test_same_path_resolved_twice_is_dedup_not_collision(capsys):
    """The same file embedded by two notes is T2.2's global dedup, not a
    collision — no collision is reported, exactly one action is emitted."""
    manifest = [
        _manifest_entry(
            source_path="a.md", rendered_file="2026-01-01_0900_a.md",
            attachments=["100 Inbox/Images/karte.jpg"],
        ),
        _manifest_entry(
            source_path="b.md", rendered_file="2026-01-01_0901_b.md",
            attachments=["100 Inbox/Images/karte.jpg"],
        ),
    ]
    actions, skipped = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0])
    assert len(actions) == 1
    err = capsys.readouterr().err
    assert "collision" not in err.lower()
    assert skipped == []


def test_collision_does_not_suppress_the_notes_own_move_note():
    manifest = [
        _manifest_entry(
            source_path="a.md", rendered_file="2026-01-01_0900_a.md",
            attachments=["100 Inbox/Images/karte.jpg"],
        ),
        _manifest_entry(
            source_path="b.md", rendered_file="2026-01-01_0901_b.md",
            attachments=["100 Inbox/Scans/karte.jpg"],
        ),
    ]
    confirmed = [_confirmed_entry(source_path="a.md"), _confirmed_entry(source_path="b.md")]
    actions, _skipped_assets = build_actions(manifest, confirmed, [], [], CFG)
    move_notes = [a for a in actions if a["action"] == "move_note"]
    assert len(move_notes) == 2
    move_assets = [a for a in actions if a["action"] == "move_asset"]
    assert len(move_assets) == 1


def test_no_two_move_asset_actions_share_a_destination():
    manifest = [
        _manifest_entry(
            source_path="a.md", rendered_file="2026-01-01_0900_a.md",
            attachments=["100 Inbox/Images/karte.jpg"],
        ),
        _manifest_entry(
            source_path="b.md", rendered_file="2026-01-01_0901_b.md",
            attachments=["100 Inbox/Scans/karte.jpg", "100 Inbox/Images/other.png"],
        ),
    ]
    actions, _skipped = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0])
    destinations = [a["destination"] for a in actions]
    assert len(destinations) == len(set(destinations))


# --- empty-basename skip (folded in here: same skip-and-report path) -------

def test_attachment_with_no_basename_is_skipped_and_reported(capsys):
    """A malformed attachment path with no filename (e.g. from a Kado listDir
    entry that mistypes a folder as a file) must not raise out of
    _build_move_asset_actions and must not silently produce a directory
    destination — it is skipped and reported, and the run continues. The good
    attachment in the same batch still emits: a skip test that also swallows
    the valid case would be worse than none."""
    manifest = [
        _manifest_entry(
            source_path="a.md", rendered_file="2026-01-01_0900_a.md",
            attachments=["100 Inbox/Images/", "100 Inbox/Images/karte.jpg"],
        ),
    ]
    actions, skipped = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0])
    assert len(actions) == 1
    assert actions[0]["source"] == "100 Inbox/Images/karte.jpg"
    assert len(skipped) == 1
    assert skipped[0]["source"] == "100 Inbox/Images/"
    assert skipped[0]["destination"] is None
    assert skipped[0]["kind"] == "no_basename"
    err = capsys.readouterr().err
    assert "100 Inbox/Images/" in err

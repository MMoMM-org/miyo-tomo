#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t2_2_move_asset_emission.py — spec 031 T2.2 move_asset emission
with global de-duplication.

_build_move_asset_actions(manifest, inbox_path, asset_folder, counter) reads
`m.get("attachments")` off each manifest entry and emits one move_asset action
per unique resolved path across the WHOLE manifest — not per item, unlike the
audio_peer set at render_actions.py:922, which dedups within one origin-stem
group only.
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


def test_one_item_one_attachment_emits_one_action_with_correct_paths():
    manifest = [_manifest_entry(
        source_path="dresden.md", rendered_file="2026-01-01_0900_dresden.md",
        attachments=["100 Inbox/Images/karte.jpg"],
    )]
    actions = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0])
    assert len(actions) == 1
    assert actions[0]["source"] == "100 Inbox/Images/karte.jpg"
    assert actions[0]["destination"] == "Atlas/290 Assets/295 Attachments/karte.jpg"


def test_two_items_embedding_same_path_emit_one_action():
    """Global dedup, not per item — fails if the seen-set is reset per manifest
    entry instead of spanning the whole manifest."""
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
    actions = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0])
    assert len(actions) == 1
    assert actions[0]["source"] == "100 Inbox/Images/karte.jpg"


def test_two_items_same_basename_different_path_are_not_deduped_at_seen_level(capsys):
    """Dedup (this task) keys on the full resolved path, not the basename — two
    different files are NOT silently merged into a single "already seen" entry.
    They collide at the DESTINATION instead, a distinct, later concern (T2.4's
    collision guard): the warning it prints names the second path explicitly,
    which only happens if dedup let it through to the destination-claim step in
    the first place. Fails if the dedup key is the basename, since the second
    path would then be dropped silently with no warning at all — indistinguishable
    from the collision guard having done its job, except for that missing warning."""
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
    actions = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0])
    assert len(actions) == 1
    assert actions[0]["source"] == "100 Inbox/Images/karte.jpg"
    assert "100 Inbox/Scans/karte.jpg" in capsys.readouterr().err


def test_item_with_empty_attachment_list_emits_no_actions():
    manifest = [_manifest_entry(
        source_path="a.md", rendered_file="2026-01-01_0900_a.md", attachments=[],
    )]
    assert _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0]) == []


def test_manifest_with_no_attachments_key_emits_no_actions():
    """CON-8: an entry that never mentions attachments at all is not an error —
    m.get('attachments') is None, not []."""
    manifest = [_manifest_entry(source_path="a.md", rendered_file="2026-01-01_0900_a.md")]
    assert "attachments" not in manifest[0]
    assert _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, [0]) == []


def test_rest_of_the_action_set_is_byte_identical_without_attachments():
    """CON-8: a manifest with no attachment keys at all produces the exact same
    move_note/create_moc/etc. actions as before — the new emitter adds nothing
    when there is nothing to add."""
    manifest = [_manifest_entry(source_path="a.md", rendered_file="2026-01-01_0900_a.md")]
    confirmed = [_confirmed_entry(source_path="a.md")]
    with_emitter = build_actions(manifest, confirmed, [], [], CFG)
    move_assets = [a for a in with_emitter if a["action"] == "move_asset"]
    others = [a for a in with_emitter if a["action"] != "move_asset"]
    assert move_assets == []
    # IDs stay monotonic and untouched by an absent attachments key.
    assert [a["id"] for a in others] == [f"I{i:02d}" for i in range(1, len(others) + 1)]


def test_ids_assigned_from_shared_counter_are_monotonic():
    manifest = [_manifest_entry(
        source_path="a.md", rendered_file="2026-01-01_0900_a.md",
        attachments=["100 Inbox/Images/one.jpg", "100 Inbox/Images/two.jpg"],
    )]
    counter = [5]
    actions = _build_move_asset_actions(manifest, INBOX, ASSET_FOLDER, counter)
    assert [a["id"] for a in actions] == ["I06", "I07"]
    assert counter == [7]


def test_move_asset_occupies_planner_slot_3_between_move_note_and_link_to_moc():
    manifest = [_manifest_entry(
        source_path="a.md", rendered_file="2026-01-01_0900_a.md",
        attachments=["100 Inbox/Images/karte.jpg"],
        parent_mocs=["Japan"],
    )]
    confirmed = [_confirmed_entry(source_path="a.md", parent_mocs=["Japan"])]
    actions = build_actions(manifest, confirmed, [], [], CFG)
    kinds = [a["action"] for a in actions]
    move_note_idx = kinds.index("move_note")
    move_asset_idx = kinds.index("move_asset")
    link_to_moc_idx = kinds.index("link_to_moc")
    assert move_note_idx < move_asset_idx < link_to_moc_idx


def test_no_delete_source_action_references_an_attachment_path():
    """ADR-6: an attachment move never implies a deletion. Structural guard —
    _build_delete_source_actions only ever sees move_notes, never the manifest,
    so an attachment path has no path to a delete_source at all."""
    manifest = [_manifest_entry(
        source_path="a.md", rendered_file="2026-01-01_0900_a.md",
        attachments=["100 Inbox/Images/karte.jpg"],
    )]
    confirmed = [_confirmed_entry(source_path="a.md")]
    actions = build_actions(manifest, confirmed, [], [], CFG)
    attachment_paths = {"100 Inbox/Images/karte.jpg"}
    delete_sources = [a for a in actions if a["action"] == "delete_source"]
    assert delete_sources, "expected the origin's own delete_source to exist"
    assert not any(d["source_path"] in attachment_paths for d in delete_sources)

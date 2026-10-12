#!/usr/bin/env python3
"""test_039_t5_2_delete_waits_for_attachment_moves.py — spec 039 / T5.2 (#186).

An origin's `delete_source` (and its audio peer's) names the ids of the
`move_asset` actions for the attachments that origin embeds, after the ids of
its `move_note` actions (ADR-10, Kokoro ADR-029 section 7). Order is
deterministic: note ids in manifest order, then asset ids in the order the
move builder emitted them (first appearance of the attachment in the manifest).

Mechanism each test falsifies:
- `test_origin_and_audio_peer_delete_name_notes_then_both_assets` (F6-AC1):
  site 3 not appending the origin's move ids (delete names notes only), or
  appending them to the origin delete but not the audio peer's, or putting
  assets before notes.
- `test_shared_attachment_is_named_by_both_origins_deletes` (F6-AC3): the
  projection / site 3 reading only the FIRST owner of a shared attachment, so
  the second origin's delete is left unguarded.
- `test_withheld_attachment_id_appears_in_no_delete` (F6-AC4): a withheld move
  being given an id, or the delete naming an id absent from the action list.
- `test_keep_in_inbox_leaves_depends_on_unchanged` (F6-AC5): site 3 adding
  anything when the plan emitted no move for the attachment.
- `test_a_move_asset_withdrawn_by_a_later_guard_withdraws_the_delete`: the
  id-keyed `withdraw_unjustified_deletes` pass not treating a `move_asset` id
  like any other justification.
- `test_036_contract_still_holds_with_attachments` (036 F5-AC1..AC4): a delete
  without `depends_on`, with a dangling id, or an audio peer lacking the
  origin's ids.
- `test_instructions_schema_description_names_move_asset`: the Tomo wire
  schema's `depends_on` description not naming `move_asset` (F6-AC6, Tomo half).

CON-7: fixtures and fakes only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from attachment_plan_fakes import FakeVault, plan_from_remedies  # noqa: E402
from lib.render_actions import (  # noqa: E402
    build_actions,
    withdraw_unjustified_deletes,
)

INBOX = "100 Inbox/"
ASSET = "Atlas/290 Assets/295 Attachments/"
NOTES = "Atlas/202 Notes/"
CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSET,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}

ORIGIN = "100 Inbox/trip.md"
OTHER = "100 Inbox/other.md"
PEER = "100 Inbox/trip.m4a"
ALPHA = "100 Inbox/pics/alpha.png"
BETA = "100 Inbox/pics/beta.png"
SHARED = "100 Inbox/pics/shared.png"


def _atomic(item_key, title, idx, attachments=(), audio_peer=None):
    stem = item_key.rsplit("/", 1)[-1][:-3]
    entry = {
        "id": f"S{idx:02d}", "action": "create_atomic_note", "title": title,
        "rendered_file": f"r{idx}.md", "destination": NOTES,
        "source_path": stem, "item_key": item_key, "parent_mocs": [], "tags": [],
        "attachments": list(attachments),
    }
    if audio_peer:
        entry["audio_peer"] = audio_peer
    return entry


def _run(manifest, remedies=(), vault=None):
    plan = plan_from_remedies(manifest, list(remedies), inbox_path=INBOX,
                              asset_folder=ASSET, vault=vault)
    actions, skipped = build_actions(manifest, manifest, [], [], CFG,
                                     attachment_plan=plan)
    return actions, skipped


def _ids(actions, kind):
    return [a["id"] for a in actions if a["action"] == kind]


def _delete(actions, path):
    (found,) = [a for a in actions
                if a["action"] == "delete_source" and a["source_path"] == path]
    return found


def test_origin_and_audio_peer_delete_name_notes_then_both_assets():
    """F6-AC1 — one origin, two atomics, two attachments, an audio peer."""
    manifest = [
        _atomic(ORIGIN, "One", 1, [ALPHA, BETA], audio_peer="trip.m4a"),
        _atomic(ORIGIN, "Two", 2, [BETA], audio_peer="trip.m4a"),
    ]
    actions, _ = _run(manifest)
    notes = _ids(actions, "move_note")
    assets = _ids(actions, "move_asset")
    assert len(notes) == 2 and len(assets) == 2
    expected = notes + assets
    assert _delete(actions, ORIGIN)["depends_on"] == expected
    assert _delete(actions, PEER)["depends_on"] == expected
    assert _delete(actions, PEER)["depends_on"] == _delete(actions, ORIGIN)["depends_on"]


def test_shared_attachment_is_named_by_both_origins_deletes():
    """F6-AC3 — one attachment, two origins: BOTH deletes name its single id."""
    manifest = [
        _atomic(ORIGIN, "One", 1, [SHARED]),
        _atomic(OTHER, "Two", 2, [SHARED]),
    ]
    actions, _ = _run(manifest)
    (asset,) = _ids(actions, "move_asset")
    notes = _ids(actions, "move_note")
    assert _delete(actions, ORIGIN)["depends_on"] == [notes[0], asset]
    assert _delete(actions, OTHER)["depends_on"] == [notes[1], asset]


def test_withheld_attachment_id_appears_in_no_delete():
    """F6-AC4 — an occupied target withholds the move: no id, no dependency."""
    manifest = [_atomic(ORIGIN, "One", 1, [ALPHA, BETA])]
    vault = FakeVault([ALPHA, BETA, f"{ASSET}beta.png"], existing_folders=[ASSET])
    actions, skipped = _run(manifest, vault=vault)
    assert [s["source"] for s in skipped] == [BETA]
    (asset,) = _ids(actions, "move_asset")
    (note,) = _ids(actions, "move_note")
    assert _delete(actions, ORIGIN)["depends_on"] == [note, asset]
    all_ids = {a["id"] for a in actions}
    assert all(d in all_ids for d in _delete(actions, ORIGIN)["depends_on"])


def test_keep_in_inbox_leaves_depends_on_unchanged():
    """F6-AC5 — kept in the inbox by the owner: no move, delete as today."""
    manifest = [_atomic(ORIGIN, "One", 1, [ALPHA])]
    vault = FakeVault([ALPHA, f"{ASSET}alpha.png"], existing_folders=[ASSET])
    actions, _ = _run(
        manifest,
        [{"source": ALPHA, "remedy": "keep_in_inbox", "proposed_name": None}],
        vault=vault)
    assert _ids(actions, "move_asset") == []
    (note,) = _ids(actions, "move_note")
    assert _delete(actions, ORIGIN)["depends_on"] == [note]


def test_a_move_asset_withdrawn_by_a_later_guard_withdraws_the_delete():
    manifest = [_atomic(ORIGIN, "One", 1, [ALPHA])]
    actions, _ = _run(manifest)
    (asset,) = _ids(actions, "move_asset")
    assert asset in _delete(actions, ORIGIN)["depends_on"]
    survivors = [a for a in actions if a["id"] != asset]
    kept, withdrawn = withdraw_unjustified_deletes(survivors)
    assert [a for a in kept if a["action"] == "delete_source"] == []
    assert [w.get("source_path") for w in withdrawn] == [ORIGIN]


def test_036_contract_still_holds_with_attachments():
    """036 F5-AC1..AC4: always present, [] explicit, all partners, no dangling."""
    manifest = [
        _atomic(ORIGIN, "One", 1, [ALPHA], audio_peer="trip.m4a"),
        _atomic(OTHER, "Two", 2, []),
    ]
    actions, _ = _run(manifest)
    ids = {a["id"] for a in actions}
    deletes = [a for a in actions if a["action"] == "delete_source"]
    assert len(deletes) == 3
    for d in deletes:
        assert isinstance(d["depends_on"], list)
        assert set(d["depends_on"]) <= ids
    assert _delete(actions, OTHER)["depends_on"] == [_ids(actions, "move_note")[1]]


def test_instructions_schema_description_names_move_asset():
    """F6-AC6 (Tomo half)."""
    schema = json.loads((REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json").read_text())
    text = json.dumps(schema)
    desc = schema["$defs"]["delete_source"]["properties"]["depends_on"]["description"] \
        if "delete_source" in schema.get("$defs", {}) else text
    assert "move_asset" in desc

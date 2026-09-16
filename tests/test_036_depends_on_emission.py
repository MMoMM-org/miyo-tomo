#!/usr/bin/env python3
# version: 0.1.0
"""test_036_depends_on_emission.py — spec 036 / T1.1 depends_on declaration.

Verifies that `_build_delete_source_actions` populates `depends_on` on every
emitted `delete_source` action from site 1 (user-requested deletion) and site 3
(move_note origin plus its audio peer):

- A single-atomic origin's delete names exactly its one move id.
- A three-atomic origin's delete names all three move ids.
- An origin with an audio peer emits two deletes (origin + peer), and both
  name the same move-id set.
- A user-requested deletion (site 1, no partner action) emits `depends_on: []`.
- An item marked "Keep source files" still emits no delete at all — the
  suppression path is untouched by this change.

Tests are RED against current code (no `depends_on` key on emitted actions)
and GREEN after T1.1.

Spec: docs/XDD/specs/036-delete-outlives-its-justification/ Phase 1, T1.1.
PRD: F5-AC1 (every delete carries depends_on), F5-AC2 (user-requested is `[]`,
not absent), F5-AC3 (an N-atomic origin names N ids, not one).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load instruction-render.py via importlib (hyphen in name).
_ir_spec = importlib.util.spec_from_file_location("instruction_render_t036", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render_t036"] = ir
_ir_spec.loader.exec_module(ir)

INBOX = "100 Inbox"
ORIGIN_BASENAME = "2026-04-08-meeting-notes.md"
ORIGIN_FULL = f"{INBOX}/{ORIGIN_BASENAME}"
AUDIO_BASENAME = "2026-04-08_1430_meeting.m4a"
AUDIO_FULL = f"{INBOX}/{AUDIO_BASENAME}"


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _confirmed(source_basename: str = ORIGIN_BASENAME, keep_source: bool = False) -> dict:
    return {
        "id": f"item-{source_basename}",
        "action": "create_note",
        "source_path": source_basename,
        "keep_source": keep_source,
    }


def _move_note(
    origin_full: str = ORIGIN_FULL,
    audio_peer: str | None = None,
    note_id: str = "A01",
) -> dict:
    return {
        "id": note_id,
        "action": "move_note",
        "source_inbox_item": origin_full,
        "audio_peer": audio_peer,
        "source": f"{INBOX}/rendered-{note_id}.md",
        "destination": "200 Notes/Meeting Notes.md",
        "title": "Meeting Notes",
        "rendered_file": f"rendered-{note_id}.md",
        "parent_mocs": [],
        "tags": [],
    }


def _skipped_delete(source_basename: str = ORIGIN_BASENAME) -> dict:
    return {
        "id": f"skip-{source_basename}",
        "disposition": "delete_source",
        "source_path": source_basename,
    }


def _build(confirmed=None, move_notes=None, daily_updates=None, skipped=None):
    counter = [0]
    return ir._build_delete_source_actions(
        confirmed or [], move_notes or [], daily_updates or [], skipped or [], INBOX, counter
    )


def _deletes(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("action") == "delete_source"]


def _by_path(deletes: list[dict], source_path: str) -> dict:
    matches = [d for d in deletes if d["source_path"] == source_path]
    assert len(matches) == 1, f"expected exactly one delete for {source_path}; got {matches}"
    return matches[0]


# ── Tests: site 3 — move_note origin ────────────────────────────────────────


def test_single_atomic_origin_names_its_one_move_id():
    """A single-atomic origin's delete_source names exactly that move's id."""
    confirmed = [_confirmed()]
    move_notes = [_move_note(note_id="A01")]

    deletes = _deletes(_build(confirmed, move_notes))
    origin_delete = _by_path(deletes, ORIGIN_FULL)

    assert origin_delete["depends_on"] == ["A01"], (
        f"expected depends_on ['A01']; got {origin_delete.get('depends_on')!r}"
    )


def test_three_atomic_origin_names_all_three_move_ids():
    """A three-atomic origin's delete_source names all three move ids (PRD F5-AC3)."""
    confirmed = [_confirmed(), _confirmed(), _confirmed()]
    move_notes = [
        _move_note(note_id="A01"),
        _move_note(note_id="A02"),
        _move_note(note_id="A03"),
    ]

    deletes = _deletes(_build(confirmed, move_notes))
    origin_delete = _by_path(deletes, ORIGIN_FULL)

    assert sorted(origin_delete["depends_on"]) == ["A01", "A02", "A03"], (
        f"expected all three move ids; got {origin_delete.get('depends_on')!r}"
    )


def test_audio_peer_delete_names_same_move_id_set_as_origin_delete():
    """An origin with an audio peer emits two deletes; both name the same
    move-id set (SDD/Implementation Gotchas — separate actions hanging off the
    same move set; naming only one leaves the other unguarded).
    """
    confirmed = [_confirmed(), _confirmed()]
    move_notes = [
        _move_note(audio_peer=AUDIO_FULL, note_id="A01"),
        _move_note(audio_peer=AUDIO_FULL, note_id="A02"),
    ]

    deletes = _deletes(_build(confirmed, move_notes))
    assert len(deletes) == 2, f"expected origin + audio-peer delete; got {deletes}"

    origin_delete = _by_path(deletes, ORIGIN_FULL)
    audio_delete = _by_path(deletes, AUDIO_FULL)

    assert sorted(origin_delete["depends_on"]) == ["A01", "A02"]
    assert sorted(audio_delete["depends_on"]) == sorted(origin_delete["depends_on"]), (
        "audio-peer delete must name the same move-id set as the origin delete"
    )


def test_keep_source_still_emits_no_delete_at_all():
    """An item marked 'Keep source files' still emits no delete — the
    suppression path (keep_source_keys) is untouched by this change.
    """
    confirmed = [_confirmed(keep_source=True)]
    move_notes = [_move_note(note_id="A01")]

    deletes = _deletes(_build(confirmed, move_notes))

    assert deletes == [], f"expected no delete when keep_source=True; got {deletes}"


# ── Tests: site 1 — user-requested deletion ─────────────────────────────────


def test_user_requested_deletion_emits_empty_depends_on():
    """Site 1 (user-checked 'Delete source' on a skipped item) has no partner
    action and declares that explicitly: depends_on = [] (PRD F5-AC2 — absence
    is never valid, [] is an assertion).
    """
    skipped = [_skipped_delete()]

    deletes = _deletes(_build(skipped=skipped))
    delete = _by_path(deletes, ORIGIN_FULL)

    assert "depends_on" in delete, "depends_on must be present, not absent"
    assert delete["depends_on"] == [], (
        f"expected depends_on == []; got {delete['depends_on']!r}"
    )

#!/usr/bin/env python3
# version: 0.1.0
"""test_instruction_render_delete_source_completion_gate.py — source-deletion
completion gate (C6, F-41).

T5.2 (XDD-016): Verifies that _build_delete_source_actions emits delete_source
only after ALL expected atomic move_notes for an origin stem are present, not
after the first one (OQ6 / PRD/A9).

Tests:
  1. test_two_atomics_delete_only_after_both_move_notes_present
     2 confirmed atomics + 2 move_notes → exactly 1 delete_source (gate passes)
  2. test_two_atomics_only_one_move_note_no_delete
     2 confirmed atomics but only 1 move_note → NO delete (gate defers; OQ6)
  3. test_two_atomics_one_daily_delete_after_all_threads_present
     2 atomics + 1 daily + 2 move_notes → exactly 1 delete (combined reason)
  4. test_keep_origin_any_true_skips_delete
     keep_origin=True on first confirmed item, False on second → no delete
     (current last-wins dict would read False → emit delete = BUG)
  5. test_keep_origin_all_false_emits_delete
     keep_origin=False on all confirmed items → delete IS emitted (not suppressed)
  6. test_single_atomic_regression
     single atomic + single move_note → exactly 1 delete (CON-2)

Spec: docs/XDD/specs/016-multi-topic-atomic-notes/
SDD:  C6 (source-deletion completion gate), Complex Logic algorithm
AC:   PRD/A9, OQ6, CON-2
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load instruction-render.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("instruction_render", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render"] = ir
_spec.loader.exec_module(ir)

INBOX = "100 Inbox"


def _make_confirmed(source_basename: str, keep_origin: bool = False) -> dict:
    """Return a minimal confirmed item pointing to an inbox source file."""
    return {
        "id": f"item-{source_basename}",
        "action": "create_note",
        "source_path": source_basename,
        "keep_origin": keep_origin,
    }


def _make_move_note(origin_full_path: str, note_id: str = "A01") -> dict:
    """Return a minimal move_note action (as _build_move_note_actions emits)."""
    return {
        "id": note_id,
        "action": "move_note",
        "origin_inbox_item": origin_full_path,
        "source": f"{INBOX}/rendered-{note_id}.md",
        "destination": "200 Notes/Some Topic.md",
        "title": "Some Topic",
        "rendered_file": f"rendered-{note_id}.md",
        "parent_mocs": [],
        "tags": [],
    }


def _make_daily_entry(source_stem: str, bucket: str = "log_entries") -> dict:
    """Return a minimal daily_updates day with one accepted entry for source_stem."""
    entry = {"accepted": True, "source_stem": source_stem, "content": "note"}
    day: dict = {
        "date": "2026-06-11",
        "daily_note_path": None,
        "heading": "Journal",
        "heading_level": 2,
        "trackers": [],
        "log_entries": [],
        "log_links": [],
    }
    day[bucket] = [entry]
    return day


def _delete_sources(actions: list[dict]) -> list[dict]:
    """Filter to delete_source actions only."""
    return [a for a in actions if a.get("action") == "delete_source"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_two_atomics_delete_only_after_both_move_notes_present():
    """2 confirmed atomics + 2 move_notes → exactly 1 delete_source.

    When all expected move_notes are present, the gate passes and emits one delete.
    PRD/A9: source consumed after all threads are captured.
    """
    source_basename = "my-note.md"
    origin_full = f"{INBOX}/{source_basename}"

    confirmed = [
        _make_confirmed(source_basename),
        _make_confirmed(source_basename),
    ]
    move_notes = [
        _make_move_note(origin_full, "A01"),
        _make_move_note(origin_full, "A02"),
    ]
    counter = [0]

    deletes = _delete_sources(
        ir._build_delete_source_actions(confirmed, move_notes, [], [], INBOX, counter)
    )

    assert len(deletes) == 1, (
        f"expected 1 delete_source, got {len(deletes)}: {deletes}"
    )
    assert deletes[0]["source_path"] == origin_full


def test_two_atomics_only_one_move_note_no_delete():
    """2 confirmed atomics but only 1 move_note → NO delete_source.

    OQ6: source preserved until all threads captured. If one thread hasn't been
    rendered yet (move_note count < expected count), the delete must be deferred.
    The CURRENT implementation emits a delete after the first move_note — this
    test should FAIL until the completion gate is implemented.
    """
    source_basename = "partial-note.md"
    origin_full = f"{INBOX}/{source_basename}"

    confirmed = [
        _make_confirmed(source_basename),
        _make_confirmed(source_basename),  # 2 approved atomics
    ]
    move_notes = [
        _make_move_note(origin_full, "B01"),  # only 1 of 2 move_notes present
    ]
    counter = [0]

    deletes = _delete_sources(
        ir._build_delete_source_actions(confirmed, move_notes, [], [], INBOX, counter)
    )

    assert len(deletes) == 0, (
        f"expected NO delete_source when only 1 of 2 atomics rendered, "
        f"got {len(deletes)}: {deletes}"
    )


def test_two_atomics_one_daily_delete_after_all_threads_present():
    """2 atomics + 1 accepted daily → delete_source emitted once when both
    move_notes are present.

    SDD/Complex Logic: daily is represented when the daily_updates entry is
    accepted. With both move_notes and an accepted daily present, the gate
    passes → exactly 1 delete.
    """
    source_basename = "combined-note.md"
    origin_full = f"{INBOX}/{source_basename}"
    source_stem = "combined-note"

    confirmed = [
        _make_confirmed(source_basename),
        _make_confirmed(source_basename),
    ]
    move_notes = [
        _make_move_note(origin_full, "C01"),
        _make_move_note(origin_full, "C02"),
    ]
    daily_updates = [_make_daily_entry(source_stem, "log_entries")]
    counter = [0]

    deletes = _delete_sources(
        ir._build_delete_source_actions(
            confirmed, move_notes, daily_updates, [], INBOX, counter
        )
    )

    assert len(deletes) == 1, (
        f"expected 1 delete_source, got {len(deletes)}: {deletes}"
    )
    assert deletes[0]["source_path"] == origin_full


def test_keep_origin_any_true_skips_delete():
    """keep_origin=True on the FIRST confirmed item, False on the second.

    SDD/C6: if ANY confirmed item for the stem has keep_origin truthy, treat
    the origin as kept → no delete_source.
    The CURRENT implementation uses last-wins (overwrites), so if the second
    item has keep_origin=False it reads False and emits a delete — this test
    should FAIL until the any-keeps guard is implemented.
    """
    source_basename = "keep-first.md"
    origin_full = f"{INBOX}/{source_basename}"

    confirmed = [
        _make_confirmed(source_basename, keep_origin=True),   # first: keep
        _make_confirmed(source_basename, keep_origin=False),  # second: delete
    ]
    move_notes = [
        _make_move_note(origin_full, "D01"),
        _make_move_note(origin_full, "D02"),
    ]
    counter = [0]

    deletes = _delete_sources(
        ir._build_delete_source_actions(confirmed, move_notes, [], [], INBOX, counter)
    )

    assert len(deletes) == 0, (
        f"expected 0 delete_source when any confirmed item has keep_origin=True, "
        f"got {len(deletes)}: {deletes}"
    )


def test_keep_origin_all_false_emits_delete():
    """keep_origin=False on all confirmed items → delete IS emitted.

    Ensures that keep_origin=False (the default) still produces a delete.
    Both confirmed items opt in to deletion → gate passes → 1 delete.
    """
    source_basename = "delete-me.md"
    origin_full = f"{INBOX}/{source_basename}"

    confirmed = [
        _make_confirmed(source_basename, keep_origin=False),
        _make_confirmed(source_basename, keep_origin=False),
    ]
    move_notes = [
        _make_move_note(origin_full, "E01"),
        _make_move_note(origin_full, "E02"),
    ]
    counter = [0]

    deletes = _delete_sources(
        ir._build_delete_source_actions(confirmed, move_notes, [], [], INBOX, counter)
    )

    assert len(deletes) == 1, (
        f"expected 1 delete_source when keep_origin=False, got {len(deletes)}: {deletes}"
    )
    assert deletes[0]["source_path"] == origin_full


def test_single_atomic_regression():
    """Single atomic → exactly one delete after its move_note.

    CON-2: single-thread behavior must not change in observable output
    (beyond the reason string).
    """
    source_basename = "solo-note.md"
    origin_full = f"{INBOX}/{source_basename}"

    confirmed = [_make_confirmed(source_basename)]
    move_notes = [_make_move_note(origin_full, "F01")]
    counter = [0]

    deletes = _delete_sources(
        ir._build_delete_source_actions(confirmed, move_notes, [], [], INBOX, counter)
    )

    assert len(deletes) == 1, (
        f"expected 1 delete_source, got {len(deletes)}: {deletes}"
    )
    assert deletes[0]["source_path"] == origin_full

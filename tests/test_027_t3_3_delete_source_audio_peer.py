#!/usr/bin/env python3
# version: 0.1.0
"""test_027_t3_3_delete_source_audio_peer.py — spec 027 / T3.3 audio-peer deletion.

Verifies that _build_delete_source_actions emits paired delete_source for both
the transcript origin AND its audio peer when keep_source=False, suppresses both
when keep_source=True, emits only one when no peer, defers both when the
completion gate is unsatisfied, handles multi-atomic correctly, and never emits
an audio delete when audio_peer is absent (degraded fail-safe).

Tests are RED against current code (no audio peer delete emitted) and GREEN after T3.3.

Spec: docs/XDD/specs/027-suggestions-source-model/ ADR-1; PRD AC F3, F5.
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
_ir_spec = importlib.util.spec_from_file_location("instruction_render_t33", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render_t33"] = ir
_ir_spec.loader.exec_module(ir)

INBOX = "100 Inbox"
TRANSCRIPT_BASENAME = "2026-04-08-interview-transcript.md"
AUDIO_BASENAME = "2026-04-08_1430_interview.m4a"
TRANSCRIPT_FULL = f"{INBOX}/{TRANSCRIPT_BASENAME}"
AUDIO_FULL = f"{INBOX}/{AUDIO_BASENAME}"


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _confirmed(source_basename: str, keep_source: bool = False) -> dict:
    return {
        "id": f"item-{source_basename}",
        "action": "create_note",
        "source_path": source_basename,
        "keep_source": keep_source,
    }


def _move_note(
    origin_full: str,
    audio_peer: str | None = None,
    note_id: str = "A01",
) -> dict:
    mn: dict = {
        "id": note_id,
        "action": "move_note",
        "origin_inbox_item": origin_full,
        "audio_peer": audio_peer,
        "source": f"{INBOX}/rendered-{note_id}.md",
        "destination": "200 Notes/Interview Notes.md",
        "title": "Interview Notes",
        "rendered_file": f"rendered-{note_id}.md",
        "parent_mocs": [],
        "tags": [],
    }
    return mn


def _build(confirmed, move_notes):
    counter = [0]
    return ir._build_delete_source_actions(
        confirmed, move_notes, [], [], INBOX, counter
    )


def _deletes(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("action") == "delete_source"]


def _source_paths(deletes: list[dict]) -> list[str]:
    return [d["source_path"] for d in deletes]


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_keep_source_false_emits_both_transcript_and_audio():
    """keep_source=False → delete_source for transcript AND audio peer (PRD F3)."""
    confirmed = [_confirmed(TRANSCRIPT_BASENAME, keep_source=False)]
    move_notes = [_move_note(TRANSCRIPT_FULL, audio_peer=AUDIO_FULL)]

    deletes = _deletes(_build(confirmed, move_notes))
    paths = _source_paths(deletes)

    assert len(deletes) == 2, (
        f"Expected 2 delete_source actions (transcript + audio); got {len(deletes)}: {paths}"
    )
    assert TRANSCRIPT_FULL in paths, (
        f"Transcript delete missing; paths: {paths}"
    )
    assert AUDIO_FULL in paths, (
        f"Audio peer delete missing; paths: {paths}"
    )


def test_audio_peer_delete_reason_identifies_peer():
    """Audio peer delete_source has a descriptive reason string."""
    confirmed = [_confirmed(TRANSCRIPT_BASENAME)]
    move_notes = [_move_note(TRANSCRIPT_FULL, audio_peer=AUDIO_FULL)]

    deletes = _deletes(_build(confirmed, move_notes))
    audio_deletes = [d for d in deletes if d["source_path"] == AUDIO_FULL]

    assert len(audio_deletes) == 1
    reason = audio_deletes[0].get("reason", "")
    assert reason, "Audio peer delete must have a reason string"
    # Reason should indicate it's a peer of a consumed origin
    assert any(kw in reason.lower() for kw in ("peer", "audio", "origin")), (
        f"Reason should reference peer/audio/origin; got {reason!r}"
    )


def test_keep_source_true_suppresses_both():
    """keep_source=True → neither transcript nor audio peer is deleted (PRD F5)."""
    confirmed = [_confirmed(TRANSCRIPT_BASENAME, keep_source=True)]
    move_notes = [_move_note(TRANSCRIPT_FULL, audio_peer=AUDIO_FULL)]

    deletes = _deletes(_build(confirmed, move_notes))

    assert len(deletes) == 0, (
        f"Expected 0 delete_source when keep_source=True; got {len(deletes)}: {_source_paths(deletes)}"
    )


def test_no_audio_peer_emits_only_transcript_delete():
    """Without an audio_peer on the move_note, exactly one delete_source is emitted (unchanged)."""
    confirmed = [_confirmed(TRANSCRIPT_BASENAME)]
    move_notes = [_move_note(TRANSCRIPT_FULL, audio_peer=None)]

    deletes = _deletes(_build(confirmed, move_notes))
    paths = _source_paths(deletes)

    assert len(deletes) == 1, (
        f"Expected exactly 1 delete_source (no audio peer); got {len(deletes)}: {paths}"
    )
    assert TRANSCRIPT_FULL in paths


def test_gate_unsatisfied_defers_both():
    """2 confirmed atomics, only 1 move_note → gate not satisfied → 0 deletes (transcript+audio deferred)."""
    confirmed = [
        _confirmed(TRANSCRIPT_BASENAME),
        _confirmed(TRANSCRIPT_BASENAME),  # force expected=2
    ]
    move_notes = [
        _move_note(TRANSCRIPT_FULL, audio_peer=AUDIO_FULL, note_id="A01"),
        # A02 move_note missing → gate not yet satisfied
    ]

    deletes = _deletes(_build(confirmed, move_notes))

    assert len(deletes) == 0, (
        f"Expected 0 deletes when gate unsatisfied; got {len(deletes)}: {_source_paths(deletes)}"
    )


def test_multi_atomic_gate_both_emitted_when_gate_passes():
    """2 atomics, 2 move_notes (both with same audio_peer) → gate passes → 2 deletes."""
    confirmed = [
        _confirmed(TRANSCRIPT_BASENAME),
        _confirmed(TRANSCRIPT_BASENAME),
    ]
    move_notes = [
        _move_note(TRANSCRIPT_FULL, audio_peer=AUDIO_FULL, note_id="A01"),
        _move_note(TRANSCRIPT_FULL, audio_peer=AUDIO_FULL, note_id="A02"),
    ]

    deletes = _deletes(_build(confirmed, move_notes))
    paths = _source_paths(deletes)

    assert len(deletes) == 2, (
        f"Expected 2 deletes (transcript + audio) after gate passes; got {len(deletes)}: {paths}"
    )
    assert TRANSCRIPT_FULL in paths
    assert AUDIO_FULL in paths


def test_degraded_failsafe_no_audio_peer_on_move_note():
    """audio_peer=None on the move_note → never emits an audio delete (fail-safe)."""
    confirmed = [_confirmed(TRANSCRIPT_BASENAME)]
    # move_note has no audio_peer — degraded/unexpected state
    mn = _move_note(TRANSCRIPT_FULL, audio_peer=None)
    del mn["audio_peer"]  # completely absent, not just None
    move_notes = [mn]

    deletes = _deletes(_build(confirmed, move_notes))
    paths = _source_paths(deletes)

    assert len(deletes) == 1, (
        f"Fail-safe: expected only transcript delete when audio_peer absent; got {paths}"
    )
    assert TRANSCRIPT_FULL in paths
    audio_deletes = [d for d in deletes if ".m4a" in d["source_path"]]
    assert len(audio_deletes) == 0, (
        f"No audio delete must be emitted when audio_peer absent; got {audio_deletes}"
    )


def test_audio_peer_not_duplicated_across_two_atomics():
    """When 2 atomics share one audio peer, the audio peer delete is emitted ONCE."""
    confirmed = [
        _confirmed(TRANSCRIPT_BASENAME),
        _confirmed(TRANSCRIPT_BASENAME),
    ]
    move_notes = [
        _move_note(TRANSCRIPT_FULL, audio_peer=AUDIO_FULL, note_id="A01"),
        _move_note(TRANSCRIPT_FULL, audio_peer=AUDIO_FULL, note_id="A02"),
    ]

    deletes = _deletes(_build(confirmed, move_notes))
    audio_deletes = [d for d in deletes if d["source_path"] == AUDIO_FULL]

    assert len(audio_deletes) == 1, (
        f"Audio peer delete must be emitted exactly once; got {len(audio_deletes)}"
    )

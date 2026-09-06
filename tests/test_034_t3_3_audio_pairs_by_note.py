#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t3_3_audio_pairs_by_note.py — XDD 034 T3.3 audio pairs by note.

T3.2 made inbox discovery recursive, so a note in a subfolder (e.g.
`100 Inbox/Archive/memo.md`) is now discovered for the first time.
`check_audio` built its `md_stems` set from the bare stem only, dropping
the folder — so a namesake note anywhere in the tree could satisfy a
root-level (or any other folder's) audio file, making `has_audio` return
False and silently skipping transcription.

`[ref: PRD/AC Feature 5]` — a namesake elsewhere cannot mark an audio file
as already handled. This file pins the fix: pairing compares folder + stem,
not stem alone.

Two things the pre-T3.2 code already got right, preserved here as
regression guards:

  - `check_audio` returns a bool ("True if uncached audio files exist"),
    not a collection — every assertion here is on that bool.
  - Only the audio-side stem is sanitised via `sanitize_stem` before
    comparison; the markdown side is raw. Obsidian already forbids the
    offending characters in note filenames, while a recorder does not.
    This asymmetry was deliberately introduced after a prior regression
    (symmetrising it, or dropping it, previously caused an infinite
    transcribe loop on exactly a raw `:` vs `-` mismatch) — see
    docs/tomo/scripts/inbox-triage.md.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load_module():
    script_path = SCRIPTS_DIR / "inbox-triage.py"
    spec = importlib.util.spec_from_file_location("inbox_triage_t33", script_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_triage_t33"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _entry(path: str) -> dict:
    return {"path": path, "type": "file", "modified": 1716300000000, "size": 100}


# ---------------------------------------------------------------------------
# (a) Namesake elsewhere — genuine RED before the fix.
# ---------------------------------------------------------------------------

def test_root_audio_not_satisfied_by_namesake_in_archive():
    """`[ref: PRD/AC Feature 5]` — a root memo.m4a with no root transcript
    still needs transcription, even though an unrelated Archive/memo.md
    exists elsewhere in the tree."""
    mod = _load_module()
    audio_files = [_entry("100 Inbox/memo.m4a")]
    md_files = [_entry("100 Inbox/Archive/memo.md")]

    assert mod.check_audio(audio_files, md_files) is True


# ---------------------------------------------------------------------------
# (b) Cross-folder mis-pairing — genuine RED before the fix.
# ---------------------------------------------------------------------------

def test_voice_audio_not_satisfied_by_archive_namesake():
    """An audio file in Voice/ is not paired by a same-named note that lives
    in a different folder (Archive/), even though no Voice/ transcript
    exists at all."""
    mod = _load_module()
    audio_files = [_entry("100 Inbox/Voice/memo.m4a")]
    md_files = [_entry("100 Inbox/Archive/memo.md")]

    assert mod.check_audio(audio_files, md_files) is True


# ---------------------------------------------------------------------------
# (c) Same-folder pairing — expected already GREEN, fixed literals.
# ---------------------------------------------------------------------------

def test_same_folder_pairing_is_recognised():
    """An audio file paired with its transcript in the SAME folder is not
    flagged as needing transcription."""
    mod = _load_module()
    audio_files = [_entry("100 Inbox/Voice/memo.m4a")]
    md_files = [_entry("100 Inbox/Voice/memo.md")]

    assert mod.check_audio(audio_files, md_files) is False


def test_sanitized_stem_pairing_in_same_folder():
    """The audio side is sanitised before comparison (Obsidian forbids ':'
    in note filenames; a recorder does not). Literal fixture, not a
    before/after comparison: 'Rec 2026-01-02 14:30.m4a' pairs with
    'Rec 2026-01-02 14-30.md' when both live in the same folder."""
    mod = _load_module()
    audio_files = [_entry("100 Inbox/Rec 2026-01-02 14:30.m4a")]
    md_files = [_entry("100 Inbox/Rec 2026-01-02 14-30.md")]

    assert mod.check_audio(audio_files, md_files) is False


# ---------------------------------------------------------------------------
# (d) Flat-inbox regression — expected already GREEN.
# ---------------------------------------------------------------------------

def test_flat_inbox_paired_audio_is_not_flagged():
    mod = _load_module()
    audio_files = [_entry("100 Inbox/memo.m4a")]
    md_files = [_entry("100 Inbox/memo.md")]

    assert mod.check_audio(audio_files, md_files) is False


def test_flat_inbox_unpaired_audio_is_flagged():
    mod = _load_module()
    audio_files = [_entry("100 Inbox/memo.m4a")]
    md_files = [_entry("100 Inbox/beta.md")]

    assert mod.check_audio(audio_files, md_files) is True


def test_no_audio_files_returns_false():
    mod = _load_module()
    assert mod.check_audio([], [_entry("100 Inbox/memo.md")]) is False

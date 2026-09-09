#!/usr/bin/env python3
# version: 0.2.0
"""test_034_t5_0c_diff_daily_only_item_key.py — the coverage audit's daily-only
suppression joins on the note, not on the bare filename stem.

Covers T5.0c (XDD 034 Phase 5). T5.0b re-keyed the delete bookkeeping in
`lib/render_actions.py` onto the note's path; `instructions-diff.derive_expected`
— its paired consumer — kept the removed shape: `confirmed_stems` was a set of
bare stems and the `daily_only_seen` loop suppressed a daily-only note's expected
deletion on a stem match against it. Two namesakes collapsed, so a CORRECT
instruction set was reported as `delete_source coverage: ... [DIFF]` — a false
alarm in the artefact the user reads to judge whether Pass 2 did the right thing.

Every case pins `derive_expected` against what
`_build_delete_source_actions` actually emits for the SAME input, rather than
against a hand-written number: the two modules must agree by construction, and
a number written into a test only records what one of them did on the day it
was written.

Each case also asserts, BEFORE comparing the two sides, that the daily-only
path actually ran — the daily entries contributed a specific, non-zero number
of expected deletions, and the emitter named the specific notes by their paths.
Without that, a fixture whose daily entries never reached the branch would let
both sides agree at zero and pass against broken code.

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
SDD:  ADR-1 (the item key IS the vault-relative path), ADR-2 (`stem` stays
      display text)
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


ir = _load("instruction_render_034_t50c", "instruction-render.py")
diff = _load("instructions_diff_034_t50c", "instructions-diff.py")

INBOX = "100 Inbox"
# Two notes sharing a filename in different inbox subfolders — the collision
# recursive discovery makes reachable.
KEY_A = f"{INBOX}/Projects/Dresden.md"
KEY_B = f"{INBOX}/Travel/Dresden.md"
# A third note of that name at the inbox ROOT — what a keyless daily entry
# resolves to, and therefore the note it must be recognised as.
KEY_ROOT = f"{INBOX}/Dresden.md"
KEY_ELBE = f"{INBOX}/Places/Elbe.md"
# One note at the inbox ROOT, referenced twice from the daily block — once
# with its key, once by the bare stem a failed key recovery leaves behind.
KEY_NEUSTADT_ROOT = f"{INBOX}/Neustadt.md"
STEM_NEUSTADT = "Neustadt"
DISPLAY = "Dresden.md"
STEM = "Dresden"
DAY = "2026-06-10"
CONTENT_A = "Sprint retro moved to the Dresden office."
CONTENT_B = "Zwinger courtyard, gallery closed on Mondays."
CONTENT_ELBE = "Elbe cycle path flooded past Pillnitz."
CONTENT_N1 = "Neustadt: Kunsthofpassage funnels sing when it rains."
CONTENT_N2 = "Neustadt: Louisenstrasse closed for the Bunte Republik."


# ──────────────────────────────────────────────────────────────────────
# Fixture helpers
# ──────────────────────────────────────────────────────────────────────

def _confirmed(item_key: str, item_id: str, keep_source: bool = False) -> dict:
    """A confirmed item as both parser paths emit it: display stem in
    `source_path` (ADR-2), vault-relative path in `item_key` (ADR-1)."""
    return {
        "id": item_id,
        "action": "create_note",
        "source_path": DISPLAY,
        "item_key": item_key,
        "keep_source": keep_source,
        "title": item_id,
        "tags": [],
        "parent_moc": "",
        "parent_mocs": [],
    }


def _move_note(item_key: str, note_id: str) -> dict:
    """A move_note as `_build_move_note_actions` emits it — `source_inbox_item`
    is already the resolved vault-relative origin path."""
    return {
        "id": note_id,
        "action": "move_note",
        "source_inbox_item": item_key,
        "source": f"{INBOX}/rendered-{note_id}.md",
        "destination": f"200 Notes/{note_id}.md",
        "title": note_id,
        "rendered_file": f"rendered-{note_id}.md",
        "parent_mocs": [],
        "tags": [],
    }


def _log_entry(content: str, source_stem: str, source_item_key: str | None = None) -> dict:
    """An accepted daily log entry. `source_item_key` is omitted entirely for
    the keyless case — a document whose key could not be recovered."""
    entry = {
        "time": None,
        "position": "after_last_line",
        "content": content,
        "reason": "worthiness 0.2",
        "source_stem": source_stem,
        "accepted": True,
    }
    if source_item_key:
        entry["source_item_key"] = source_item_key
    return entry


def _day(entries: list[dict]) -> dict:
    return {
        "date": DAY,
        "daily_note_path": None,
        "trackers": [],
        "log_entries": entries,
        "log_links": [],
    }


def _parsed(confirmed: list[dict], daily: list[dict]) -> dict:
    return {
        "confirmed_items": confirmed,
        "daily_updates": daily,
        "skipped": [],
    }


def _expected_deletes(parsed: dict) -> int:
    return len(diff.derive_expected(parsed)["expected_deletions"])


def _daily_contribution(parsed: dict) -> int:
    """How many expected deletions the daily entries themselves contributed.

    Re-derives the same document with its daily block emptied and takes the
    difference, so a fixture whose daily entries never reach the branch under
    test scores 0 and fails loudly instead of agreeing with the emitter for
    the wrong reason.
    """
    without_daily = dict(parsed)
    without_daily["daily_updates"] = []
    return _expected_deletes(parsed) - _expected_deletes(without_daily)


def _emitted_deletes(confirmed: list[dict], move_notes: list[dict],
                     daily: list[dict]) -> list[dict]:
    out = ir._build_delete_source_actions(
        confirmed, move_notes, daily, [], INBOX, [0]
    )
    return [a for a in out if a.get("action") == "delete_source"]


def _delete_coverage_line(parsed: dict, actions: list[dict]) -> str:
    """The `delete_source coverage:` line `/inbox` prints for this run."""
    instrs = {"actions": actions, "action_count": len(actions)}
    buf = io.StringIO()
    with redirect_stdout(buf):
        diff.run_diff(parsed, instrs)
    matches = [
        ln.strip() for ln in buf.getvalue().splitlines()
        if "delete_source coverage:" in ln
    ]
    assert len(matches) == 1, f"expected one coverage line, got {matches}"
    return matches[0]


# ──────────────────────────────────────────────────────────────────────
# Case 1 — two daily-only namesakes
# ──────────────────────────────────────────────────────────────────────

def test_two_daily_only_namesakes_are_both_expected():
    """Two notes fully captured in the daily note, same filename, different
    inbox subfolders. The emitter deletes both (T5.0b); stem-keyed, the audit
    expects one and reports the correct run as drift.
    """
    daily = [_day([
        _log_entry(CONTENT_A, STEM, KEY_A),
        _log_entry(CONTENT_B, STEM, KEY_B),
    ])]
    parsed = _parsed([], daily)
    emitted = _emitted_deletes([], [], daily)

    # The daily-only path ran, for these two notes, identified by their paths.
    assert {a["source_path"] for a in emitted} == {KEY_A, KEY_B}, (
        f"fixture never reached the daily-only branch: {emitted}"
    )
    assert _daily_contribution(parsed) == 2, (
        "both daily-only namesakes must contribute an expected deletion; "
        f"got {_daily_contribution(parsed)}"
    )

    assert _expected_deletes(parsed) == len(emitted), (
        f"audit expects {_expected_deletes(parsed)}, emitter produces "
        f"{len(emitted)} — the coverage line would report drift on a "
        "correct instruction set"
    )
    assert "[OK]" in _delete_coverage_line(parsed, emitted)


# ──────────────────────────────────────────────────────────────────────
# Case 2 — one confirmed namesake plus one daily-only
# ──────────────────────────────────────────────────────────────────────

def test_a_confirmed_namesake_does_not_suppress_the_daily_only_one():
    """A is confirmed and moved; B, its namesake in another subfolder, is
    daily-only. The emitter deletes both origins; stem-keyed, the audit sees
    B's stem in `confirmed_stems` and suppresses B's expected deletion.
    """
    confirmed = [_confirmed(KEY_A, "S01")]
    move_notes = [_move_note(KEY_A, "A01")]
    daily = [_day([_log_entry(CONTENT_B, STEM, KEY_B)])]
    parsed = _parsed(confirmed, daily)
    emitted = _emitted_deletes(confirmed, move_notes, daily)

    assert {a["source_path"] for a in emitted} == {KEY_A, KEY_B}, (
        f"fixture never reached the daily-only branch: {emitted}"
    )
    assert _daily_contribution(parsed) == 1, (
        "the daily-only namesake must contribute its own expected deletion; "
        f"got {_daily_contribution(parsed)}"
    )

    assert _expected_deletes(parsed) == len(emitted) == 2, (
        f"audit expects {_expected_deletes(parsed)}, emitter produces "
        f"{len(emitted)}"
    )
    assert "[OK]" in _delete_coverage_line(parsed, move_notes + emitted)


# ──────────────────────────────────────────────────────────────────────
# Case 3 — mixed keyed / keyless input
# ──────────────────────────────────────────────────────────────────────

def test_a_keyless_daily_entry_still_matches_its_keyed_root_note():
    """The case a set-equality dedup breaks, and the reason this module does
    not reuse the emitter's `_origin_key`.

    A daily entry whose key could not be recovered carries only the bare stem;
    the confirmed item for the SAME note carries its full path. The emitter
    resolves the bare one against the inbox root and finds them equal, so it
    emits no daily-only delete. A set membership test splits them and expects
    one — drift on a correct run, in the opposite direction from cases 1-2.
    The second entry is genuinely daily-only, so the branch is still exercised.
    """
    confirmed = [_confirmed(KEY_ROOT, "S01", keep_source=True)]
    daily = [_day([
        _log_entry(CONTENT_A, STEM),                       # keyless — same note
        _log_entry(CONTENT_ELBE, "Elbe", KEY_ELBE),        # genuinely daily-only
    ])]
    parsed = _parsed(confirmed, daily)
    emitted = _emitted_deletes(confirmed, [], daily)

    assert {a["source_path"] for a in emitted} == {KEY_ELBE}, (
        "only the genuinely daily-only note may be deleted; the keyless entry "
        f"names a confirmed note. got {emitted}"
    )
    assert _daily_contribution(parsed) == 1, (
        "the daily-only branch must still contribute for the unmatched entry; "
        f"got {_daily_contribution(parsed)}"
    )

    assert _expected_deletes(parsed) == len(emitted) == 1, (
        f"audit expects {_expected_deletes(parsed)}, emitter produces "
        f"{len(emitted)}"
    )
    assert "[OK]" in _delete_coverage_line(parsed, emitted)


# ──────────────────────────────────────────────────────────────────────
# Case 4 — one note, two daily entries, two key shapes
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("keyed_first", [True, False], ids=["keyed-first", "keyless-first"])
def test_two_daily_entries_for_one_note_expect_one_deletion(keyed_first):
    """The dedup WITHIN the daily-only accumulation, which this task gave new
    behaviour to.

    Two accepted entries name one daily-only note: key recovery succeeded for
    the first and found the second's discriminator ambiguous, so one carries
    the full path and the other only the bare stem. The emitter resolves both
    against the inbox root, finds them equal in `seen`, and deletes the note
    ONCE. A bare `in` membership test here splits the two shapes and expects
    two deletions for one file.

    Parametrised over entry order because the tolerance is symmetric: whichever
    shape arrives first, the other must land in the same bucket.
    """
    entries = [
        _log_entry(CONTENT_N1, STEM_NEUSTADT, KEY_NEUSTADT_ROOT),
        _log_entry(CONTENT_N2, STEM_NEUSTADT),
    ]
    if not keyed_first:
        entries.reverse()
    daily = [_day(entries)]
    parsed = _parsed([], daily)
    emitted = _emitted_deletes([], [], daily)

    # The branch ran: two accepted entries went in, one delete for one note
    # came out — not zero, which is how this case would pass vacuously.
    assert len([e for e in entries if e["accepted"]]) == 2
    assert {a["source_path"] for a in emitted} == {KEY_NEUSTADT_ROOT}, (
        f"one note, one delete; got {emitted}"
    )
    assert _daily_contribution(parsed) == 1, (
        "the two entries name one note and owe one expected deletion; "
        f"got {_daily_contribution(parsed)}"
    )

    assert _expected_deletes(parsed) == len(emitted) == 1, (
        f"audit expects {_expected_deletes(parsed)}, emitter produces "
        f"{len(emitted)}"
    )
    assert "[OK]" in _delete_coverage_line(parsed, emitted)

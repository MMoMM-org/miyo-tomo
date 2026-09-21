#!/usr/bin/env python3
# version: 0.1.0
"""test_036_t4_4_withdrawn_delete_coverage.py — spec 036 T4.3 follow-up (spec
035 T-delete-reaches-user), live run 2026-09-18.

`instructions-diff.py`'s daily-only and paired-delete `expected_deletions`
are derived from the suggestions document alone (Pass 1) — independent of
whether the renderer later withdrew a delete for lacking justification
(spec 036 `withdraw_unjustified_deletes` / T4.3's `tomo.delete_withdrawals`
report). The live gap this task closes: a user ticked "Delete [[Laufrunde
Elbufer]]", `filter_missing_daily_notes` dropped its paired daily actions,
`withdraw_unjustified_deletes` correctly withdrew the delete (spec 036
working as designed) — and the coverage audit then reported
`delete_source expected=2 actual=1 [DIFF]`, halting a correct run.

Covers `_subtract_withdrawn_deletes` (tomo/scripts/instructions-diff.py):

  1. One `delete_withdrawals` entry (non-clash guard) leaves
     `expected_deletions`, count -1.
  2. Pure clash case: a delete in BOTH `destination_clashes[].
     withdrawn_deletes` AND `tomo.delete_withdrawals` is subtracted exactly
     once — `_subtract_withheld_moves` runs first (mirroring `run_diff`'s own
     wiring order) and removes it; the guard-filtered subtraction is then a
     documented no-op, never a second decrement.
  3. Mixed-cause case (the discriminator): a withdrawal whose causes name
     BOTH a `validate_destinations` cause and a `filter_missing_daily_notes`
     cause must still be skipped IN FULL — a rule that subtracts whenever
     ANY non-clash cause is present (rather than skipping whenever ANY
     clash-guard cause is present) double-subtracts here and drives the
     count negative.
  4. `causes: []` (literal empty list, no guard names at all) is treated as
     not-a-clash-guard and subtracted normally.
  5. A withdrawal whose `source_path` is absent from `expected_deletions` is
     a no-op — never a crash, never a negative count.
  6. Two distinct non-clash withdrawals subtract 2.
  7. No `delete_withdrawals` key at all leaves `expected_deletions` and the
     count byte-identical to before this task.
  8. End to end via `run_diff` (not the helper in isolation): today's live
     shape — two expected deletes, one withdrawn for a missing daily note —
     verdict OK, not DIFF. The live failure was a WIRING miss (the audit
     never read `tomo.delete_withdrawals`), not an arithmetic one; only a
     test through `run_diff` proves the wiring, not just the helper.

CON-7: fixtures and fakes only — in-memory dicts, no live vault/Kado/Docker.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "instructions_diff_t036_t44", SCRIPTS_DIR / "instructions-diff.py"
)
diff = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(diff)


def _run(parsed: dict, instrs: dict) -> tuple[int, list[str]]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc, obs = diff.run_diff(parsed, instrs)
    return rc, obs


def _withdrawal(source_path: str, causes: list[dict], id_="D1") -> dict:
    return {
        "id": id_,
        "action": "delete_source",
        "source_path": source_path,
        "reason": "Content fully captured in daily note.",
        "causes": causes,
    }


DAILY_CAUSE = [{"missing_id": "I05", "guard": "filter_missing_daily_notes"}]
CLASH_CAUSE = [{"missing_id": "M01", "guard": "validate_destinations"}]
MIXED_CAUSE = [
    {"missing_id": "M01", "guard": "validate_destinations"},
    {"missing_id": "I05", "guard": "filter_missing_daily_notes"},
]


def _expected_with_deletions(paths: list[str]) -> dict:
    """Build a minimal `expected` dict shaped like `derive_expected`'s output,
    holding only what `_subtract_withdrawn_deletes` reads/writes."""
    return {
        "counts": {"delete_source": len(paths)},
        "by_item": {},
        "expected_daily": [],
        "expected_deletions": list(paths),
        "expected_skips": [],
    }


# ── 1. one non-clash withdrawal subtracts once ──────────────────────────────


def test_one_daily_withdrawal_subtracts_one():
    expected = _expected_with_deletions(["Origin"])
    removed = diff._subtract_withdrawn_deletes(
        expected, [_withdrawal("100 Inbox/Origin.md", DAILY_CAUSE)]
    )
    assert removed == 1
    assert expected["expected_deletions"] == []
    assert expected["counts"]["delete_source"] == 0


# ── 2. pure clash case: already subtracted, never twice ────────────────────


def test_pure_clash_withdrawal_subtracted_exactly_once():
    expected = _expected_with_deletions(["Origin"])
    clash = [{
        "destination": "Atlas/202 Notes/Origin.md",
        "reason": "destination claimed twice",
        "dropped": [],
        "withdrawn_deletes": ["100 Inbox/Origin.md"],
    }]
    diff._subtract_withheld_moves(expected, clash)
    assert expected["expected_deletions"] == []  # removed by the clash pass

    removed = diff._subtract_withdrawn_deletes(
        expected, [_withdrawal("100 Inbox/Origin.md", CLASH_CAUSE)]
    )
    assert removed == 0, "already accounted for — must not decrement again"
    assert expected["expected_deletions"] == []
    assert expected["counts"]["delete_source"] == 0, "must never go negative"


# ── 3. mixed-cause discriminator ────────────────────────────────────────────


def test_mixed_cause_withdrawal_skipped_in_full_not_double_subtracted():
    """A rule that subtracts on ANY non-clash cause (ignoring that a clash
    cause is ALSO present) double-subtracts this exact case — the discriminator
    a plain path-based dedup passes test 2 but fails."""
    expected = _expected_with_deletions(["Origin"])
    clash = [{
        "destination": "Atlas/202 Notes/Origin.md",
        "reason": "destination claimed twice",
        "dropped": [],
        "withdrawn_deletes": ["100 Inbox/Origin.md"],
    }]
    diff._subtract_withheld_moves(expected, clash)
    assert expected["counts"]["delete_source"] == 0

    removed = diff._subtract_withdrawn_deletes(
        expected, [_withdrawal("100 Inbox/Origin.md", MIXED_CAUSE)]
    )
    assert removed == 0
    assert expected["counts"]["delete_source"] == 0, (
        "must not go negative — a mixed-cause entry naming a clash guard is "
        "skipped IN FULL, not partially subtracted for its other cause"
    )


# ── 4. causes: [] — not a clash guard, subtracted normally ─────────────────


def test_empty_causes_list_is_subtracted_normally():
    expected = _expected_with_deletions(["Origin"])
    removed = diff._subtract_withdrawn_deletes(
        expected, [_withdrawal("100 Inbox/Origin.md", [])]
    )
    assert removed == 1
    assert expected["expected_deletions"] == []
    assert expected["counts"]["delete_source"] == 0


# ── 5. source_path absent from expected_deletions — safe no-op ─────────────


def test_withdrawal_naming_an_unexpected_path_is_a_safe_noop():
    expected = _expected_with_deletions(["Origin"])
    removed = diff._subtract_withdrawn_deletes(
        expected, [_withdrawal("100 Inbox/Elsewhere.md", DAILY_CAUSE)]
    )
    assert removed == 0
    assert expected["expected_deletions"] == ["Origin"]
    assert expected["counts"]["delete_source"] == 1


# ── 6. two distinct non-clash withdrawals subtract two ─────────────────────


def test_two_distinct_withdrawals_subtract_two():
    expected = _expected_with_deletions(["A", "B"])
    removed = diff._subtract_withdrawn_deletes(expected, [
        _withdrawal("100 Inbox/A.md", DAILY_CAUSE, id_="D1"),
        _withdrawal("100 Inbox/B.md", [{
            "missing_id": "L1", "guard": "filter_unresolvable_moc_links",
        }], id_="D2"),
    ])
    assert removed == 2
    assert expected["expected_deletions"] == []
    assert expected["counts"]["delete_source"] == 0


# ── 7. no delete_withdrawals key — byte-identical to today ─────────────────


def test_no_delete_withdrawals_key_is_a_noop():
    expected = _expected_with_deletions(["Origin"])
    removed = diff._subtract_withdrawn_deletes(expected, [])
    assert removed == 0
    assert expected["expected_deletions"] == ["Origin"]
    assert expected["counts"]["delete_source"] == 1


# ── 8. end to end via run_diff — today's live shape ─────────────────────────


def test_live_shape_via_run_diff_reconciles_not_diff():
    """Two expected deletes (both explicit ticked `delete_source` skips), one
    withdrawn for a missing daily note, one actually rendered. Before this
    task: expected=2 actual=1 -> [DIFF], RESULT FAIL. After: expected=1
    actual=1 -> [OK]."""
    parsed = {
        "confirmed_items": [],
        "daily_updates": [],
        "skipped": [
            {"disposition": "delete_source", "source_path": "100 Inbox/Laufrunde Elbufer.md"},
            {"disposition": "delete_source", "source_path": "100 Inbox/OtherNote.md"},
        ],
    }
    instrs = {
        "action_count": 1,
        "actions": [
            {"id": "D2", "action": "delete_source", "source_path": "100 Inbox/OtherNote.md"},
        ],
        "tomo": {
            "delete_withdrawals": [{
                "id": "D1",
                "action": "delete_source",
                "source_path": "100 Inbox/Laufrunde Elbufer.md",
                "reason": "Content fully captured in daily note.",
                "causes": [{"missing_id": "I05", "guard": "filter_missing_daily_notes"}],
            }],
        },
    }
    rc, _obs = _run(parsed, instrs)
    assert rc == 0, "a withdrawn delete must reconcile, not read as a coverage gap"

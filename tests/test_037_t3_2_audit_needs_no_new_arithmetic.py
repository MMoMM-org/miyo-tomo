#!/usr/bin/env python3
# version: 0.2.0
"""test_037_t3_2_audit_needs_no_new_arithmetic.py — spec 037 T3.2.

ADR-3 claims `instructions-diff.py` (the Pass-2 coverage audit) needs no new
arithmetic to account for spec 037's remedy outcomes (`rename`, `keep_in_inbox`,
`ignore`, a degraded rename). This file demonstrates that rather than asserting
it — the paired-consumer trap that aborted Pass 2 on 2026-09-15 is closed by
evidence, not by a docstring.

Verified fact this whole file turns on (Prime step,
`docs/XDD/specs/037-asset-destination-collision-is-a-pass1-decision/plan/
phase-3.md` T3.2 bullet 1): `derive_expected`'s attachment block
(`instructions-diff.py:481-493`) keys `move_asset` on the SOURCE path via
`attachments_seen: set[str]` and counts with `len()`; `summarize_actual`
(`:520-523`) is a raw per-kind tally over `instrs["actions"]`.
`_subtract_skipped_assets` (`:922-946`) decrements the expected count once per
entry in `tomo.skipped_assets`, regardless of any `kind` field. True when this
file was written: `instruction-render.py` did not write `kind` into that JSON
block at all. **Spec 038 T3.2 changed that premise** — `kind` is now
projected there too (`typed_name_refused` and `no_basename` both carry
`destination: None`, so a JSON consumer needs the explicit value) — but
`_subtract_skipped_assets`'s own arithmetic still never reads it, which is
the fact this file actually needs and still holds. **Neither side of the
audit ever reads a `move_asset`'s `destination`.** A `rename`'s new basename,
successful or degraded, is invisible to this file end to end.

This task writes NO production code. `instructions-diff.py` needed no line
touched for spec 037's three remedies plus the degraded-rename variant to
reconcile — five tests below run the real Pass-2 pipeline
(`build_actions` -> `validate_destinations` ->
`suppress_moves_for_unfiled_attachments` -> `withdraw_unjustified_deletes`,
`instruction-render.py:607-821`'s own order) through the real, unmodified
`run_diff` and assert `RESULT: OK`. THREE of those five — `keep_in_inbox`,
the degraded `rename`, and the mixed run — carry a real `skipped_assets`
entry through the unmodified subtraction, and they are what pin
`_subtract_skipped_assets`'s loop: replacing its body with `return 0` fails
exactly those three (measured 2026-09-27). The sixth proves a different and
complementary fault — that the audit still reports drift when an expected
entry is ABSENT from the JSON, whatever the cause: it
takes the `keep_in_inbox` fixture's own `instructions.json` projection and
strips the `skipped_assets` entry that accounts for the withheld move (a
fixture-level mutation, standing in for a code mutation on a task with no
production code to mutate), and asserts the audit reports `RESULT: FAIL` with
a `move_asset` count mismatch — not merely a non-zero exit.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import (  # noqa: E402
    build_actions,
    suppress_moves_for_unfiled_attachments,
    validate_destinations,
    withdraw_unjustified_deletes,
)

INBOX = "100 Inbox/"
NOTES = "Atlas/202 Notes/"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSET_FOLDER,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}

ATTACHMENT = "100 Inbox/Scans/karte.png"
ITEM_KEY = "100 Inbox/karte.md"


# ---------------------------------------------------------------------------
# Harness — follows tests/test_034_t5_4_attachment_clash_suppression.py's
# `_diff`/`_diff_module` pattern (the established place render output and the
# audit actually meet), adapted for spec 037's remedy transport.
# ---------------------------------------------------------------------------

def _diff_module():
    spec = importlib.util.spec_from_file_location(
        "instructions_diff_t3_2", SCRIPTS_DIR / "instructions-diff.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _atomic(item_key: str, title: str, *, idx: int, attachment: str) -> tuple[dict, dict]:
    """One manifest entry + its confirmed item, item_key-joined (ADR-1)."""
    stem = item_key.rsplit("/", 1)[-1][:-3]
    manifest = {
        "action": "create_atomic_note",
        "title": title,
        "rendered_file": f"2026-09-27_10{idx:02d}_{title.lower().replace(' ', '-')}.md",
        "destination": NOTES,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": [],
        "tags": [],
        "attachments": [attachment],
    }
    confirmed = {
        "id": f"S{idx:02d}",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": [],
        # derive_expected counts move_asset from the CONFIRMED item's
        # attachments (instructions-diff.py:491-492), not the manifest's —
        # a fixture that omits it would test the audit against a shape the
        # parser never produces (see test_034_t5_4_attachment_clash_
        # suppression.py:126-130).
        "attachments": [attachment],
    }
    return manifest, confirmed


def _remedy(source: str, remedy: str, proposed_name: str | None = None) -> dict:
    return {"source": source, "remedy": remedy, "proposed_name": proposed_name}


def _run_pass2(pairs: list[tuple[dict, dict]], remedies: list[dict]):
    """Drive the real Pass-2 pipeline in instruction-render.py's own call
    order (`instruction-render.py:607-821`): build, then the two withholding
    guards, then the delete withdrawal that runs once after both.
    """
    manifest = [m for m, _ in pairs]
    confirmed = [c for _, c in pairs]
    actions, skipped_assets = build_actions(
        manifest, confirmed, [], [], CFG, kado_client=None,
        attachment_conflict_remedies=remedies,
    )
    actions, _clashes = validate_destinations(actions)
    actions, _suppressions = suppress_moves_for_unfiled_attachments(actions, skipped_assets)
    actions, _withdrawn = withdraw_unjustified_deletes(actions)
    return actions, skipped_assets, confirmed


def _instrs(actions: list[dict], skipped_assets: list[dict]) -> dict:
    """Project `skipped_assets` exactly as `instruction-render.py` writes
    them into `instructions.json`. As of spec 038 T3.2 that projection
    carries `source`/`destination`/`kind`/`reason` — `kind` included — so
    this mirrors it with `kind` present too, even though
    `_subtract_skipped_assets`'s arithmetic (this file's actual subject)
    never reads it.
    """
    return {
        "actions": actions,
        "tomo": {
            "skipped_assets": [
                {
                    "source": s.get("source"),
                    "destination": s.get("destination"),
                    "kind": s.get("kind"),
                    "reason": s.get("reason"),
                }
                for s in skipped_assets
            ],
        },
    }


def _parsed(confirmed: list[dict]) -> dict:
    return {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}


def _run_diff(pairs, remedies, capsys):
    actions, skipped_assets, confirmed = _run_pass2(pairs, remedies)
    instrs = _instrs(actions, skipped_assets)
    parsed = _parsed(confirmed)
    rc, observations = _diff_module().run_diff(parsed, instrs)
    out = capsys.readouterr().out
    return rc, observations, out


def _count_row(out: str, kind: str) -> tuple[int, int, str]:
    """(expected, actual, status) for one row of the count table."""
    line = next(ln for ln in out.splitlines() if ln.strip().startswith(kind))
    fields = line.split()
    return int(fields[1]), int(fields[2]), fields[-1]


# ---------------------------------------------------------------------------
# 1-4. Each remedy, on its own, reconciles without instructions-diff.py
#      knowing anything happened.
# ---------------------------------------------------------------------------

def test_keep_in_inbox_conflict_passes_the_audit(capsys):
    """`[ref: PRD/F3-AC5]` No mutation applies here — no line of
    `instructions-diff.py` changed for spec 037 at all. `keep_in_inbox` is the
    remedy that DOES add a `skipped_assets` entry (no rename involved), and
    the pre-existing `_subtract_skipped_assets` loop already accounts for it —
    LOWERING expected `move_asset` from 1 to 0, the same as actual, rather
    than leaving expected at 1 against an actual of 0.
    """
    pairs = [_atomic(ITEM_KEY, "Karte", idx=1, attachment=ATTACHMENT)]
    remedies = [_remedy(ATTACHMENT, "keep_in_inbox")]
    rc, _observations, out = _run_diff(pairs, remedies, capsys)
    assert rc == 0, out
    assert "RESULT: OK" in out, out
    assert _count_row(out, "move_asset") == (0, 0, "[OK]"), out


def test_ignore_conflict_passes_the_audit_move_counted_as_any_other(capsys):
    """`[ref: SDD/Interface Specifications]` `ignore` emits the move
    unchanged and records NOTHING in `skipped_assets`
    (`render_actions.py:730-731, 819-823`) — the audit never learns a
    conflict existed, and must still reconcile because the move it sees is
    indistinguishable from a conflict-free one."""
    pairs = [_atomic(ITEM_KEY, "Karte", idx=1, attachment=ATTACHMENT)]
    remedies = [_remedy(ATTACHMENT, "ignore")]
    rc, _observations, out = _run_diff(pairs, remedies, capsys)
    assert rc == 0, out
    assert _count_row(out, "move_asset") == (1, 1, "[OK]"), out


def test_successful_rename_passes_the_audit_destination_agnostic(capsys):
    """`[ref: SDD solution.md:234-235]` A successful rename lands under a
    basename (`karte (2).png`) that `derive_expected` and `summarize_actual`
    never inspect — both key `move_asset` on the SOURCE path and count with
    `len()`. Like `ignore`, it adds nothing to `skipped_assets`. The audit
    reconciles without ever reading the new name anywhere."""
    pairs = [_atomic(ITEM_KEY, "Karte", idx=1, attachment=ATTACHMENT)]
    remedies = [_remedy(ATTACHMENT, "rename", "karte (2).png")]
    rc, _observations, out = _run_diff(pairs, remedies, capsys)
    assert rc == 0, out
    assert _count_row(out, "move_asset") == (1, 1, "[OK]"), out


def test_degraded_rename_passes_the_audit_load_bearing_variant(capsys):
    """`[ref: SDD/Runtime View — A rename that lost its name]` The
    load-bearing rename variant: `proposed_name: null` degrades to
    `keep_in_inbox` (`render_actions.py:782-812`) and DOES add a
    `vault_collision_held`-shaped entry to `skipped_assets` — unlike a
    successful rename. Only `_subtract_skipped_assets` reconciling that entry
    keeps this run at `RESULT: OK` instead of `[DIFF]` — expected `move_asset`
    is lowered from 1 to 0, matching actual's 0; bullet 6 below proves that by
    removing the entry and watching the two diverge again."""
    pairs = [_atomic(ITEM_KEY, "Karte", idx=1, attachment=ATTACHMENT)]
    remedies = [_remedy(ATTACHMENT, "rename", proposed_name=None)]
    rc, _observations, out = _run_diff(pairs, remedies, capsys)
    assert rc == 0, out
    assert _count_row(out, "move_asset") == (0, 0, "[OK]"), out


# ---------------------------------------------------------------------------
# 5. All four remedies in one run
# ---------------------------------------------------------------------------

def test_mixing_every_remedy_in_one_run_passes_the_audit(capsys):
    """`[ref: PRD/F3-AC5]` The two remedies that add a `skipped_assets` entry
    (`keep_in_inbox`, degraded `rename`) and the two that add nothing
    (`ignore`, successful `rename`) reconcile together in one run, not only
    in isolation — a subtraction that only balances when driven alone would
    still fail here."""
    pairs = [
        _atomic("100 Inbox/kept.md", "Kept", idx=1,
                attachment="100 Inbox/A/kept.png"),
        _atomic("100 Inbox/ignored.md", "Ignored", idx=2,
                attachment="100 Inbox/B/ignored.png"),
        _atomic("100 Inbox/renamed.md", "Renamed", idx=3,
                attachment="100 Inbox/C/renamed.png"),
        _atomic("100 Inbox/degraded.md", "Degraded", idx=4,
                attachment="100 Inbox/D/degraded.png"),
    ]
    remedies = [
        _remedy("100 Inbox/A/kept.png", "keep_in_inbox"),
        _remedy("100 Inbox/B/ignored.png", "ignore"),
        _remedy("100 Inbox/C/renamed.png", "rename", "renamed (2).png"),
        _remedy("100 Inbox/D/degraded.png", "rename", proposed_name=None),
    ]
    rc, _observations, out = _run_diff(pairs, remedies, capsys)
    assert rc == 0, out
    assert "RESULT: OK" in out, out
    # 4 attachments confirmed; kept + degraded are withheld (2 subtracted),
    # ignored + renamed are filed — expected and actual both land on 2.
    assert _count_row(out, "move_asset") == (2, 2, "[OK]"), out


# ---------------------------------------------------------------------------
# 6. The point of this file: the reconciliation is load-bearing
# ---------------------------------------------------------------------------

def test_audit_fails_when_the_withheld_move_is_unaccounted(capsys):
    """`[ref: plan/phase-3.md T3.2 bullet 6]` This is the fixture-level
    mutation that stands in for a code mutation on a task with no production
    code. It pins a DATA-OMISSION fault: the audit still reports drift when
    an expected `skipped_assets` entry is missing from the JSON, whatever the
    cause. It does NOT pin the presence of `_subtract_skipped_assets`'s loop
    — this fixture empties that list before the audit runs, so an intact loop
    and a no-op loop both iterate nothing and this test passes either way
    (measured 2026-09-27). The loop is pinned by the three tests that carry a
    real entry through it: `keep_in_inbox`, the degraded `rename`, and the
    mixed run. Mutation: take the `keep_in_inbox` fixture's
    real `instructions.json` projection and strip its `skipped_assets` entry
    — as a hand edit or a truncated write would. `derive_expected` still
    counts one `move_asset` for Karte's attachment (from the CONFIRMED
    item's `attachments`, untouched); `summarize_actual` still counts zero
    (the move genuinely was not filed). With nothing left to subtract, the
    audit must report the mismatch instead of silently reconciling."""
    pairs = [_atomic(ITEM_KEY, "Karte", idx=1, attachment=ATTACHMENT)]
    remedies = [_remedy(ATTACHMENT, "keep_in_inbox")]
    actions, skipped_assets, confirmed = _run_pass2(pairs, remedies)
    assert len(skipped_assets) == 1, (
        f"precondition: keep_in_inbox must record exactly one entry to strip: "
        f"{skipped_assets}"
    )

    instrs = _instrs(actions, skipped_assets)
    assert instrs["tomo"]["skipped_assets"], (
        "precondition: the entry must exist in the projected JSON before the "
        "mutation removes it"
    )
    instrs["tomo"]["skipped_assets"] = []  # the mutation

    parsed = _parsed(confirmed)
    rc, observations = _diff_module().run_diff(parsed, instrs)
    out = capsys.readouterr().out

    assert rc == 1, (
        f"the audit must FAIL once the withheld move is unaccounted: {out}"
    )
    assert "RESULT: FAIL" in out, out
    exp, act, status = _count_row(out, "move_asset")
    assert (exp, act, status) == (1, 0, "[DIFF]"), (
        f"the mismatch must be a move_asset COUNT mismatch specifically "
        f"(expected 1, actual 0), not merely a non-zero exit: {out}"
    )
    assert observations == [] or all("attachment" not in o for o in observations), (
        "no observation should explain away a mismatch this fixture "
        f"deliberately introduced: {observations}"
    )

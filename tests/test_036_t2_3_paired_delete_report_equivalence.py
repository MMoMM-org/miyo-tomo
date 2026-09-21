#!/usr/bin/env python3
# version: 0.1.0
"""test_036_t2_3_paired_delete_report_equivalence.py — spec 036 / T2.3.

T2.3 retired the delete-removal half of `_drop_moves_with_paired_deletes`
(ADR-4): `validate_destinations` and `suppress_moves_for_unfiled_attachments`
still compute `withdrawn_deletes` — a **report**, keyed by path, built from
`_paired_delete_candidates` walking the same `moves` list that justified each
delete — but no longer remove the action from `kept` on that basis. Removal
now happens one step later, in `withdraw_unjustified_deletes`
(`instruction-render.py`, after every drop site), keyed by **id**: a delete
whose `depends_on` names an id that did not survive is withdrawn.

Two independent readings of one fact (site 3 emits `depends_on = move_ids`;
`_paired_delete_candidates` derives its candidate paths from that same
`moves` list) agree by construction, not by a shared join any more — which is
exactly the kind of drift `docs/tomo/scripts/lib/render_actions.md` names as
the T5.0c risk one relation earlier. This file is what turns "they agree by
construction" into something checked, end to end through the real pipeline
functions (`build_actions` -> `validate_destinations` ->
`suppress_moves_for_unfiled_attachments` -> `withdraw_unjustified_deletes`),
never against a hand-written expectation.

What each block pins:

  1. Over-report: no path named in any clash's or suppression's
     `withdrawn_deletes` survives as a `delete_source.source_path` in the
     FINAL emitted set (after the id-keyed pass).
  2. Under-report: every delete the id-keyed pass actually withdraws, whose
     justification was a move dropped by one of the two path-keyed guards,
     is named in that guard's own `withdrawn_deletes`.
  3. An audio-peer delete is withdrawn with its origin, end to end
     `[ref: PRD/F1-AC4]`.
  4. A `keep_source` item has no paired delete and must report none — the
     report and the coverage audit must not both claim a withdrawal that
     never happened.
  5. Paired-consumer coverage: `instructions-diff.py`'s audit reconciles
     (exit 0) over a rendered set containing a contested destination.

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

NOTES = "Atlas/202 Notes/"
INBOX = "100 Inbox/"
ASSETS = "Atlas/290 Assets/295 Attachments/"

DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
DRESDEN_REISE = "100 Inbox/Reise/Dresden.md"
DRESDEN_PEER = "100 Inbox/Places/Dresden.m4a"
ELBE_A = "100 Inbox/A/Elbe.md"
ELBE_B = "100 Inbox/B/Elbe.md"
UFER_A = "100 Inbox/A/Ufer.jpg"
UFER_B = "100 Inbox/B/Ufer.jpg"
KEEP_C = "100 Inbox/C/Same.md"
KEEP_D = "100 Inbox/D/Same.md"
ROOT_NOTE = "100 Inbox/Root Note.md"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSETS,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _atomic(item_key: str, title: str, *, idx: int, attachments: list[str] | None = None,
            audio_peer: str | None = None, keep_source: bool = False,
            location: str = NOTES) -> tuple[dict, dict]:
    """One manifest entry + its confirmed item, as instruction-render pairs them."""
    stem = item_key.rsplit("/", 1)[-1][:-3]
    manifest = {
        "action": "create_atomic_note",
        "title": title,
        "rendered_file": f"2026-09-07_10{idx:02d}_{title.lower().replace(' ', '-')}.md",
        "destination": location,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": [],
        "tags": [],
        "attachments": list(attachments or []),
    }
    if audio_peer:
        manifest["audio_peer"] = audio_peer
    confirmed = {
        "id": f"S{idx:02d}",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": [],
        "attachments": list(attachments or []),
    }
    if audio_peer:
        confirmed["audio_peer"] = audio_peer
    if keep_source:
        confirmed["keep_source"] = True
    return manifest, confirmed


def _build(pairs: list[tuple[dict, dict]], **kw) -> tuple[list[dict], list[dict]]:
    return build_actions(
        [m for m, _ in pairs], [c for _, c in pairs],
        kw.pop("daily_updates", []), kw.pop("skipped", []),
        CFG, kado_client=None,
    )


def _deletes(actions: list[dict]) -> list[str]:
    return [a["source_path"] for a in actions if a.get("action") == "delete_source"]


def _run_pipeline(
    pairs: list[tuple[dict, dict]],
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """build_actions -> validate_destinations -> suppress_moves_for_unfiled_attachments
    -> withdraw_unjustified_deletes, in the real pipeline's order
    (instruction-render.py, T2.3).

    Returns (final_actions, clashes, suppressions, id_keyed_withdrawn, skipped_assets).
    """
    actions, skipped_assets = _build(pairs)
    kept, clashes = validate_destinations(actions)
    kept, suppressions = suppress_moves_for_unfiled_attachments(kept, skipped_assets)
    kept, withdrawn = withdraw_unjustified_deletes(kept)
    return kept, clashes, suppressions, withdrawn, skipped_assets


# A single fixture exercising both path-keyed guards at once, plus a
# keep_source clash and an unrelated survivor — so tests 1 and 2 check the
# equivalence across BOTH withholding mechanisms, not just one.
MIXED_FIXTURE = [
    # Destination clash, one claimant carries an audio peer.
    _atomic(DRESDEN_PLACES, "Dresden", idx=1, audio_peer=DRESDEN_PEER),
    _atomic(DRESDEN_REISE, "Dresden", idx=2),
    # Attachment clash: two files sharing a basename in the flat asset folder.
    _atomic(ELBE_A, "Elbe A", idx=3, attachments=[UFER_A]),
    _atomic(ELBE_B, "Elbe B", idx=4, attachments=[UFER_B]),
    # Destination clash between two keep_source items — no delete was ever
    # built for either, so nothing should be reported withdrawn for them.
    _atomic(KEEP_C, "Same", idx=5, keep_source=True),
    _atomic(KEEP_D, "Same", idx=6, keep_source=True),
    # Untouched survivor — must keep its own delete throughout.
    _atomic(ROOT_NOTE, "Root note takeaway", idx=7),
]


# ---------------------------------------------------------------------------
# 1. Over-report: nothing named withdrawn survives the final emitted set
# ---------------------------------------------------------------------------

def test_report_names_no_delete_that_survives():
    kept, clashes, suppressions, _withdrawn, _skipped_assets = _run_pipeline(MIXED_FIXTURE)
    final_paths = set(_deletes(kept))

    reported_withdrawn: set[str] = set()
    for clash in clashes:
        reported_withdrawn.update(clash.get("withdrawn_deletes") or [])
    for suppression in suppressions:
        reported_withdrawn.update(suppression.get("withdrawn_deletes") or [])

    assert reported_withdrawn, "fixture must actually exercise a withdrawal to test anything"
    survivors = reported_withdrawn & final_paths
    assert survivors == set(), (
        "a path the report claims was withdrawn still has a delete_source "
        f"in the final emitted set: {survivors}"
    )


# ---------------------------------------------------------------------------
# 2. Under-report: every id-keyed withdrawal whose cause was a path-keyed
#    guard is named in that guard's own withdrawn_deletes
# ---------------------------------------------------------------------------

def test_every_clash_withdrawn_delete_is_actually_gone():
    _kept, clashes, suppressions, withdrawn, _skipped_assets = _run_pipeline(MIXED_FIXTURE)

    reported_withdrawn: set[str] = set()
    for clash in clashes:
        reported_withdrawn.update(clash.get("withdrawn_deletes") or [])
    for suppression in suppressions:
        reported_withdrawn.update(suppression.get("withdrawn_deletes") or [])

    id_keyed_withdrawn_paths = {w["source_path"] for w in withdrawn}
    assert id_keyed_withdrawn_paths, "fixture must actually withdraw a delete to test anything"

    # Every delete the id-keyed pass withdrew for a dangling-id reason (not
    # the fail-closed missing-key reason, which no site in this fixture
    # produces) must have been named by one of the two path-keyed reports —
    # otherwise a guard silently dropped a move whose paired delete the
    # report never mentioned, which is exactly the under-report T5.0c-shaped
    # drift this test exists to catch.
    missing_from_reports = id_keyed_withdrawn_paths - reported_withdrawn
    assert missing_from_reports == set(), (
        "the id-keyed pass withdrew a delete that neither guard's report "
        f"named: {missing_from_reports}"
    )


# ---------------------------------------------------------------------------
# 3. Audio-peer delete withdrawn with its origin, end to end
# ---------------------------------------------------------------------------

def test_audio_peer_delete_still_withdrawn_with_its_origin():
    """[ref: PRD/F1-AC4] A contested move that carried an audio peer must
    withdraw both paired deletes — through the full pipeline, not just the
    path-keyed guard."""
    actions, _skipped = _build(MIXED_FIXTURE)
    assert DRESDEN_PEER in _deletes(actions), "fixture no longer emits the peer delete"

    kept, clashes, _suppressions, _withdrawn, _skipped_assets = _run_pipeline(MIXED_FIXTURE)
    final_paths = _deletes(kept)
    assert DRESDEN_PEER not in final_paths, (
        "the audio peer of an unfiled origin must stay in the inbox with it"
    )
    assert DRESDEN_PLACES not in final_paths
    assert DRESDEN_REISE not in final_paths

    dresden_clash = next(c for c in clashes if c["destination"] == f"{NOTES}Dresden.md")
    assert DRESDEN_PEER in dresden_clash["withdrawn_deletes"]


# ---------------------------------------------------------------------------
# 4. keep_source reports no phantom withdrawal
# ---------------------------------------------------------------------------

def test_keep_source_item_still_reports_no_phantom_withdrawal():
    """An item marked "Keep source files" has no paired delete — naming its
    origin would make the report and the audit both claim a withdrawal that
    never happened."""
    kept, clashes, _suppressions, withdrawn, _skipped_assets = _run_pipeline(MIXED_FIXTURE)

    assert KEEP_C not in _deletes(kept) and KEEP_D not in _deletes(kept), (
        "keep_source means no delete was ever built for these origins"
    )

    same_clash = next(c for c in clashes if c["destination"] == f"{NOTES}Same.md")
    assert same_clash["withdrawn_deletes"] == [], (
        "neither keep_source claimant had a delete to withdraw: "
        f"{same_clash['withdrawn_deletes']}"
    )
    assert not any(
        w["source_path"] in (KEEP_C, KEEP_D) for w in withdrawn
    ), "the id-keyed pass must not invent a withdrawal for a delete that never existed"

    # The untouched survivor keeps its own delete throughout.
    assert ROOT_NOTE in _deletes(kept)


# ---------------------------------------------------------------------------
# 5. Paired-consumer coverage — instructions-diff.py reconciles
# ---------------------------------------------------------------------------

def test_paired_consumer_coverage_reconciles(capsys):
    """Run the real audit over the emitter's own output for the same input —
    pinned against instructions-diff.py, never against a hand-written count."""
    confirmed = [c for _, c in MIXED_FIXTURE]
    kept, clashes, suppressions, _withdrawn, skipped_assets = _run_pipeline(MIXED_FIXTURE)
    instrs = {
        "actions": kept,
        "action_count": len(kept),
        "tomo": {
            "destination_clashes": clashes,
            "attachment_suppressions": suppressions,
            # Projected exactly as instruction-render.py writes it (mirrors
            # test_034_t5_4's _diff()) — the audit reads this block, so a
            # fixture that omits it would test the audit against a document
            # Tomo never produces.
            "skipped_assets": [
                {
                    "source": s.get("source"),
                    "destination": s.get("destination"),
                    "reason": s.get("reason"),
                }
                for s in skipped_assets
            ],
        },
    }
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    rc, observations = _load("instructions_diff_t2_3", "instructions-diff.py").run_diff(
        parsed, instrs
    )
    capsys.readouterr()
    assert rc == 0, (
        "a deliberate withdrawal must not stop the conductor and blame Tomo "
        f"for its own guard: {observations}"
    )

#!/usr/bin/env python3
# version: 0.2.0
"""test_036_t2_4_phase_validation.py — spec 036 / T2.4 Phase 2 validation.

Phase 2 ("Collect — the withdrawal pass") claims this is where P1 and Bug A
actually stop happening. This file proves that claim end to end, through the
real pipeline functions (`build_actions`, then the real guards in their real
order, exactly as `instruction-render.py` runs them), not through a
hand-built action list.

P1 — the contested destination (`docs/XDD/specs/036-delete-outlives-its-
justification/solution.md`, "Traced walkthrough"): a `create_moc` and a
`move_note` claim one destination; `validate_destinations` drops both
claimants (ADR-3), but the moved note's `delete_source` used to survive that
drop and ship anyway — deleting an inbox note Tomo had just refused to file.

Bug A (same doc, next table): a daily-only origin's `delete_source` depends
on the daily action that captured its content. `filter_missing_daily_notes`
drops that daily action when the target daily note does not exist, but the
delete used to ship regardless — removing the note while writing its content
nowhere. Tomo-only: no executor check catches this one.

Each test asserts the delete is present immediately after the guard that
would, pre-Phase-2, have let it ship (proving "P1/Bug A used to happen"),
then asserts `withdraw_unjustified_deletes` removes it (proving "and now it
doesn't") — a within-test before/after, not git archaeology.

A third property, checked over both scenarios' FINAL emitted actions: no
`delete_source` names an id (in `depends_on`) absent from that same final
set. This is the dangling-id invariant Phase 4's `assert_no_dangling_
dependencies` will enforce for real; here it is a per-scenario assertion,
not that audit.

A fourth test (F2-AC2, added T4.6 traceability) closes a composition gap:
neither the Bug A scenario above (one daily action, one target note) nor
`test_036_depends_on_emission.py` (proves the naming, not the withdrawal)
nor `test_036_withdraw_unjustified_deletes.py` (proves the AND semantics on
synthetic actions, not through the real daily-note guard) drives a real
multi-bucket, multi-day daily-only origin through `filter_missing_daily_
notes` with only ONE of its target daily notes absent, then through
`withdraw_unjustified_deletes`. That composition is what F2-AC2 actually
promises; the new test proves it end to end, the same way P1 and Bug A are
proven above.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

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
from lib.render_resolve import (  # noqa: E402
    filter_missing_daily_notes,
    filter_unappliable_relationships,
    filter_unresolvable_moc_links,
)

NOTES = "Atlas/202 Notes/"
INBOX = "100 Inbox/"
DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}


# ---------------------------------------------------------------------------
# Fixture builders (house pattern — see tests/test_034_t5_3_destination_
# validation.py and tests/test_036_t2_3_paired_delete_report_equivalence.py)
# ---------------------------------------------------------------------------

def _atomic(item_key: str, title: str, *, idx: int, location: str = NOTES) -> tuple[dict, dict]:
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
        "attachments": [],
    }
    confirmed = {
        "id": f"S{idx:02d}",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": [],
    }
    return manifest, confirmed


def _moc(title: str, *, idx: int, location: str = NOTES) -> tuple[dict, dict]:
    """A `create_moc` manifest entry, as a (manifest, confirmed) pair.

    `create_moc` has no confirmed-item counterpart; the builders that read
    `confirmed` tolerate a dict with no `id`.
    """
    manifest = {
        "action": "create_moc",
        "title": title,
        "rendered_file": f"2026-09-07_20{idx:02d}_{title.lower().replace(' ', '-')}.md",
        "destination": location,
        "parent_moc": None,
        "template": None,
        "tags": [],
        "supporting_items": None,
    }
    return manifest, {}


def _log_entry(source_item_key: str, source_stem: str) -> dict:
    return {
        "content": "did something", "accepted": True,
        "source_item_key": source_item_key, "source_stem": source_stem,
    }


def _tracker_entry(source_item_key: str, source_stem: str) -> dict:
    return {
        "field": "Sleep", "value": "23:00", "accepted": True,
        "source_item_key": source_item_key, "source_stem": source_stem,
    }


def _log_link_entry(source_item_key: str, source_stem: str) -> dict:
    return {
        "target_stem": "SomeTarget", "accepted": True,
        "source_item_key": source_item_key, "source_stem": source_stem,
    }


def _day(
    date: str, daily_note_path: str, log_entries: list[dict],
    *, trackers: list[dict] | None = None, log_links: list[dict] | None = None,
) -> dict:
    return {
        "date": date,
        "daily_note_path": daily_note_path,
        "trackers": trackers or [],
        "log_entries": log_entries,
        "log_links": log_links or [],
    }


class FakeKadoMissingDaily:
    """`note_exists` only — the one call `filter_missing_daily_notes` makes.
    Every path is reported missing, modelling the historical-day case the SDD
    walkthrough describes (a daily note the user never opened)."""

    def __init__(self):
        self.calls: list[str] = []

    def note_exists(self, path: str) -> bool:
        self.calls.append(path)
        return False


class FakeKadoOneMissingDaily:
    """`note_exists` reports False for exactly one configured path and True
    for every other — models a daily-only origin whose entries land in more
    than one bucket and more than one day, where only ONE target daily note
    is absent (PRD F2-AC2). Distinct from `FakeKadoMissingDaily` (every path
    missing, the all-missing case): this fake is what makes the withheld
    note a partial-withholding test."""

    def __init__(self, missing_path: str):
        self.missing_path = missing_path
        self.calls: list[str] = []

    def note_exists(self, path: str) -> bool:
        self.calls.append(path)
        return path != self.missing_path


def _deletes(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("action") == "delete_source"]


def _assert_no_dangling_deletes(actions: list[dict]) -> None:
    """The third T2.4 check: no `delete_source` in a final emitted set names
    a `depends_on` id absent from that same set."""
    surviving_ids = {a["id"] for a in actions if a.get("id")}
    for d in _deletes(actions):
        for dep in d.get("depends_on") or []:
            assert dep in surviving_ids, (
                f"dangling dependency: {d.get('id')} delete_source "
                f"({d.get('source_path')}) names {dep!r}, absent from the "
                f"final emitted set"
            )


# ---------------------------------------------------------------------------
# P1 — the contested destination
# ---------------------------------------------------------------------------

def test_p1_contested_destination_emits_no_orphaned_delete():
    """A `create_moc` and a `move_note` both claim `Atlas/202 Notes/
    Dresden.md`. `validate_destinations` drops both claimants (ADR-3) but —
    pre-Phase-2 — the moved note's paired `delete_source` survived that drop
    and shipped, deleting an inbox note Tomo had just refused to file.
    `[ref: solution.md "Traced walkthrough" — I01 create_moc, I02 move_note,
    I03 delete_source]`.
    """
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1),
        _moc("Dresden", idx=2),
    ]
    manifest = [m for m, _ in pairs]
    confirmed = [c for _, c in pairs]

    # 1. BUILD (real builder): both claimants present, the delete already
    #    declares its dependency on the move.
    actions, _skipped_assets = build_actions(
        manifest, confirmed, [], [], CFG, kado_client=None,
    )
    mocs = [a for a in actions if a.get("action") == "create_moc"]
    moves = [a for a in actions if a.get("action") == "move_note"]
    deletes = _deletes(actions)
    assert len(mocs) == 1 and len(moves) == 1 and len(deletes) == 1, actions
    move_id = moves[0]["id"]
    assert deletes[0]["depends_on"] == [move_id], (
        f"expected the delete to depend on the move's id; got {deletes[0]}"
    )

    # 2. GUARD (real guard): validate_destinations drops BOTH claimants —
    #    "before this phase" state. The delete's justification (the move) is
    #    already gone, yet the delete itself is still here: this is P1,
    #    reproduced. Without Phase 2 this is exactly what would reach the
    #    wire.
    kept, clashes = validate_destinations(actions)
    assert [a for a in kept if a.get("action") == "create_moc"] == [], (
        "the create_moc must not survive the contest"
    )
    assert [a for a in kept if a.get("action") == "move_note"] == [], (
        "the move must not survive the contest"
    )
    assert len(clashes) == 1 and clashes[0]["kind"] == "run_collision"
    deletes_before_withdrawal = _deletes(kept)
    assert len(deletes_before_withdrawal) == 1, (
        "P1 precondition: the delete must still be present right after the "
        f"contest that dropped its justification; got {kept}"
    )
    assert deletes_before_withdrawal[0]["depends_on"] == [move_id]

    # 3. WITHDRAW (the pass under test): the delete's dependency (the move)
    #    is no longer in `kept`, so it is withdrawn — "after this phase".
    final_kept, withdrawn = withdraw_unjustified_deletes(kept)
    assert _deletes(final_kept) == [], (
        f"P1 must not reproduce: delete_source is absent from the emitted "
        f"set; got {final_kept}"
    )
    assert len(withdrawn) == 1
    assert withdrawn[0]["missing_dependencies"] == [move_id]

    _assert_no_dangling_deletes(final_kept)


# ---------------------------------------------------------------------------
# Bug A — the missing daily note
# ---------------------------------------------------------------------------

def test_bug_a_missing_daily_note_leaves_no_delete_behind():
    """A daily-only origin's `delete_source` depends on the `update_log_
    entry` action that captured its content. `filter_missing_daily_notes`
    drops that action when the target daily note does not exist — pre-
    Phase-2 the delete shipped regardless, removing the inbox note while its
    content went nowhere. `[ref: solution.md "Bug A, same pass, different
    guard" — I01 update_log_entry, I02 delete_source]`.
    """
    origin_key = f"{INBOX}meeting-notes.md"
    daily_note_path = "Calendar/301 Daily/2026-04-08.md"
    daily_updates = [_day(
        "2026-04-08", daily_note_path, [_log_entry(origin_key, "meeting-notes")],
    )]

    # 1. BUILD (real builder): the log-entry action and its dependent delete
    #    both present.
    actions, _skipped_assets = build_actions(
        [], [], daily_updates, [], CFG, kado_client=None,
    )
    log_entries = [a for a in actions if a.get("action") == "update_log_entry"]
    deletes = _deletes(actions)
    assert len(log_entries) == 1 and len(deletes) == 1, actions
    log_entry_id = log_entries[0]["id"]
    assert deletes[0]["depends_on"] == [log_entry_id], (
        f"expected the delete to depend on the log-entry action's id; got {deletes[0]}"
    )

    # 2. GUARD (real guard, needs a Kado client — the note-existence probe):
    #    filter_missing_daily_notes drops the daily action because the
    #    target daily note does not exist. "Before this phase" state: the
    #    delete is still here even though its sole dependency just left.
    client = FakeKadoMissingDaily()
    after_daily_filter, skipped_daily = filter_missing_daily_notes(actions, client)
    assert [a for a in after_daily_filter if a.get("action") == "update_log_entry"] == [], (
        "the daily action must be dropped — its target daily note is absent"
    )
    assert len(skipped_daily) == 1
    deletes_before_withdrawal = _deletes(after_daily_filter)
    assert len(deletes_before_withdrawal) == 1, (
        "Bug A precondition: the delete must still be present right after "
        f"the daily-note filter that dropped its justification; got {after_daily_filter}"
    )
    assert deletes_before_withdrawal[0]["depends_on"] == [log_entry_id]

    # filter_unappliable_relationships is the remaining drop site between
    # filter_missing_daily_notes and the withdrawal pass in instruction-
    # render.py's real order; it is a pure no-op here (no add_relationship
    # actions in this fixture) but is run for pipeline fidelity.
    after_rel_filter, skipped_rel = filter_unappliable_relationships(after_daily_filter)
    assert skipped_rel == []

    # 3. WITHDRAW (the pass under test): the log-entry action is gone, so
    #    the delete's declared justification does not survive — withdrawn.
    final_kept, withdrawn = withdraw_unjustified_deletes(after_rel_filter)
    assert _deletes(final_kept) == [], (
        f"Bug A must not reproduce: delete_source is absent from the "
        f"emitted set; got {final_kept}"
    )
    assert len(withdrawn) == 1
    assert withdrawn[0]["missing_dependencies"] == [log_entry_id]

    _assert_no_dangling_deletes(final_kept)


# ---------------------------------------------------------------------------
# F2-AC2 — one withheld daily note of several must still withdraw the delete
# ---------------------------------------------------------------------------

def test_bug_a_one_of_several_daily_notes_missing_still_withdraws_the_delete():
    """PRD F2-AC2: a daily-only origin whose content produced entries across
    SEVERAL buckets AND several days — if ANY ONE of those target daily
    notes is absent, the delete is still withdrawn (AND semantics on
    `depends_on`), even though the daily actions for the OTHER, present days
    survive `filter_missing_daily_notes` untouched.

    `test_bug_a_missing_daily_note_leaves_no_delete_behind` cannot prove
    this: it has exactly one daily action, so "some missing" and "all
    missing" coincide there. This fixture has three (a tracker and a log
    entry on 2026-04-08, a log link on 2026-04-09) with only the 04-09 daily
    note absent — 1-of-3 missing, not 3-of-3.

    THE MUTATION THIS TEST KILLS: `withdraw_unjustified_deletes`'s AND
    check —
        missing = [d for d in action["depends_on"] if d not in surviving]
        if missing:
            withdrawn.append(...)
    — changed to OR semantics, e.g.
        if len(missing) == len(action["depends_on"]):
            withdrawn.append(...)
    Under that mutant, 1-of-3 missing no longer satisfies "all missing", so
    the delete is kept instead of withdrawn — this test's final assertion
    (`_deletes(final_kept) == []`) fails while
    `test_bug_a_missing_daily_note_leaves_no_delete_behind` (1-of-1 missing)
    still passes, which is exactly the gap this test closes. Verified by a
    local production mutation (git worktree, discarded after): red then,
    green on the unmodified pass.
    `[ref: solution.md "Bug A, same pass, different guard"; PRD F2-AC2]`.
    """
    origin_key = f"{INBOX}meeting-notes.md"
    day1_path = "Calendar/301 Daily/2026-04-08.md"
    day2_path = "Calendar/301 Daily/2026-04-09.md"
    daily_updates = [
        _day(
            "2026-04-08", day1_path, [_log_entry(origin_key, "meeting-notes")],
            trackers=[_tracker_entry(origin_key, "meeting-notes")],
        ),
        _day(
            "2026-04-09", day2_path, [],
            log_links=[_log_link_entry(origin_key, "meeting-notes")],
        ),
    ]

    # 1. BUILD (real builder): three daily actions (tracker, log entry, log
    #    link — three buckets, two days) and one delete naming all three.
    actions, _skipped_assets = build_actions(
        [], [], daily_updates, [], CFG, kado_client=None,
    )
    trackers = [a for a in actions if a.get("action") == "update_tracker"]
    log_entries = [a for a in actions if a.get("action") == "update_log_entry"]
    log_links = [a for a in actions if a.get("action") == "update_log_link"]
    deletes = _deletes(actions)
    assert len(trackers) == 1 and len(log_entries) == 1 and len(log_links) == 1, actions
    assert len(deletes) == 1, actions
    tracker_id, log_entry_id, log_link_id = (
        trackers[0]["id"], log_entries[0]["id"], log_links[0]["id"]
    )
    assert sorted(deletes[0]["depends_on"]) == sorted([tracker_id, log_entry_id, log_link_id]), (
        f"expected the delete to name all three daily action ids; got {deletes[0]}"
    )

    # 2. GUARD (real guard): only the 04-09 daily note (the log link's
    #    target) is reported absent — the 04-08 note (tracker + log entry's
    #    target) is present. "Before this phase" state: the delete is still
    #    here, and — this is the partial-withholding property — the OTHER
    #    two daily actions are untouched.
    client = FakeKadoOneMissingDaily(missing_path=day2_path)
    after_daily_filter, skipped_daily = filter_missing_daily_notes(actions, client)
    surviving_daily_ids = {
        a["id"] for a in after_daily_filter
        if a.get("action") in {"update_tracker", "update_log_entry", "update_log_link"}
    }
    assert surviving_daily_ids == {tracker_id, log_entry_id}, (
        "the 04-08 tracker and log-entry actions must survive untouched — "
        f"only the 04-09 log link's target note is absent; got {surviving_daily_ids}"
    )
    assert [s["id"] for s in skipped_daily] == [log_link_id]
    deletes_before_withdrawal = _deletes(after_daily_filter)
    assert len(deletes_before_withdrawal) == 1, (
        "F2-AC2 precondition: the delete must still be present right after "
        f"the daily-note filter that dropped one of its three justifications; "
        f"got {after_daily_filter}"
    )
    assert sorted(deletes_before_withdrawal[0]["depends_on"]) == sorted(
        [tracker_id, log_entry_id, log_link_id]
    ), "the delete's depends_on is untouched by the daily-note filter itself"

    after_rel_filter, skipped_rel = filter_unappliable_relationships(after_daily_filter)
    assert skipped_rel == []

    # 3. WITHDRAW (the pass under test): one of the delete's three named ids
    #    (the log link's) is gone — AND semantics withdraws the delete, and
    #    the withdrawal record names exactly that one missing id, not all
    #    three.
    final_kept, withdrawn = withdraw_unjustified_deletes(after_rel_filter)
    assert _deletes(final_kept) == [], (
        f"F2-AC2 must hold: delete_source is absent from the emitted set "
        f"even though only 1 of its 3 dependencies is missing; got {final_kept}"
    )
    final_daily_ids = {
        a["id"] for a in final_kept
        if a.get("action") in {"update_tracker", "update_log_entry", "update_log_link"}
    }
    assert final_daily_ids == {tracker_id, log_entry_id}, (
        "the surviving 04-08 daily actions must still be present after the "
        f"withdrawal pass — it governs delete_source only; got {final_daily_ids}"
    )
    assert len(withdrawn) == 1
    assert withdrawn[0]["missing_dependencies"] == [log_link_id]

    _assert_no_dangling_deletes(final_kept)


# ---------------------------------------------------------------------------
# Full suite sanity: the two path-keyed guards P1 also passes through
# (validate_destinations, suppress_moves_for_unfiled_attachments,
# filter_unresolvable_moc_links) are genuine no-ops on the Bug A fixture and
# vice versa — confirms neither scenario's proof depends on a guard silently
# mutating unrelated actions.
# ---------------------------------------------------------------------------

def test_p1_fixture_passes_unrelated_guards_as_no_ops():
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1),
        _moc("Dresden", idx=2),
    ]
    actions, skipped_assets = build_actions(
        [m for m, _ in pairs], [c for _, c in pairs], [], [], CFG, kado_client=None,
    )
    kept, _clashes = validate_destinations(actions)
    kept, suppressions = suppress_moves_for_unfiled_attachments(kept, skipped_assets)
    assert suppressions == []
    kept, unresolvable = filter_unresolvable_moc_links(kept)
    assert unresolvable == []

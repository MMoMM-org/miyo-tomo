# version: 0.1.0
"""instructions_diff_reconcile.py — subtract deliberate withholdings from expected.

Extracted from instructions-diff.py (#216). The renderer withholds some actions
on purpose (missing daily note, guard-dropped move, unfiled attachment,
withdrawn delete, unconfirmed MOC link) and records each in instructions.tomo.
Each `_subtract_*` here removes one such kind from `derive_expected`'s output so
a correct instruction set is not reported as a coverage gap;
`_unresolvable_link_notes` words the matching observations.
"""
from __future__ import annotations

from lib.instructions_diff_keys import _keys_match, _moc_stem, _stem
from lib.render_helpers import WITHDRAWAL_GUARDS

# Guards whose withdrawal is already accounted for via destination_clashes[]/
# attachment_suppressions[]'s own `withdrawn_deletes` list — see
# _subtract_withdrawn_deletes. A PROPER SUBSET of WITHDRAWAL_GUARDS
# (render_helpers.py, the documented SSoT for the five guard names), asserted
# the same way render_md.py validates its own inline-guard subset — a sixth
# guard added to WITHDRAWAL_GUARDS without a decision here is caught rather
# than silently falling through the subtraction it needs.
_CLASH_WITHDRAWAL_GUARDS = frozenset({
    "validate_destinations",
    "suppress_moves_for_unfiled_attachments",
})
assert _CLASH_WITHDRAWAL_GUARDS <= set(WITHDRAWAL_GUARDS), (
    "_CLASH_WITHDRAWAL_GUARDS names a guard absent from render_helpers."
    "WITHDRAWAL_GUARDS — keep the two lists in sync"
)


def _subtract_skipped_daily(expected: dict, skipped_daily: list[dict]) -> int:
    """Remove renderer-dropped daily-note actions from the expected tallies.

    The renderer skips update_tracker/update_log_entry/update_log_link actions
    whose target daily note does not exist (Hashi cannot create daily notes) and
    records them in instructions.tomo.skipped_daily. Those are legitimate drops,
    not coverage gaps — subtract them from expected["counts"] and prune one
    matching entry per kind from expected["expected_daily"] so BOTH the count
    table and the daily-coverage section reconcile. Returns the number removed.
    """
    daily_kinds = {"update_tracker", "update_log_entry", "update_log_link"}
    removed = 0
    for entry in skipped_daily or []:
        kind = entry.get("action")
        if kind not in daily_kinds or expected["counts"].get(kind, 0) <= 0:
            continue
        # Prune one expected_daily entry of this kind; only then decrement the
        # count, so counts and expected_daily stay consistent and never go
        # negative if skipped_daily lists more than were expected.
        for i, e in enumerate(expected["expected_daily"]):
            if e.get("kind") == kind:
                expected["expected_daily"].pop(i)
                expected["counts"][kind] -= 1
                removed += 1
                break
    return removed


def _subtract_withheld_moves(expected: dict, withholdings: list[dict]) -> int:
    """Remove guard-withheld moves and their paired deletes from expected.

    Two Pass-2 post-passes withhold a move deliberately, and both report it in
    this shape — a `dropped` list of moves and a `withdrawn_deletes` list of
    paths:

    - `render_actions.validate_destinations` (spec 034 T5.3) drops **both**
      claimants when two approved items name one destination.
    - `render_actions.suppress_moves_for_unfiled_attachments` (spec 034 T5.4,
      ADR-6) drops the note whose attachment could not be filed, so the note
      stays in the inbox with the file it embeds.

    Either way the paired `delete_source` is withdrawn with the move — emitting
    the delete without the move would remove an inbox note the run refused to
    file. Those are deliberate withholdings, not coverage gaps, so they are
    subtracted here the way `_subtract_skipped_daily` subtracts a missing daily
    note. Without this the audit reports `RESULT: FAIL — count or coverage
    mismatch` on a **correct** instruction set, and the conductor's STRICT stop
    halts the run with a message that misdiagnoses the guard as drift — the
    exact failure T5.0c was scheduled to fix one module over.

    One function over both lists, not one per cause: the two passes share the
    withdrawal mechanism in the emitter, and a second copy here is the drift
    that produced T5.0c.

    A withheld move also takes its `link_to_moc` bullets with it — a bullet
    naming a note the run refused to file is an instruction to create a dead
    link. Its expected links are therefore subtracted here, from the withheld
    item's own `expected_links`, not from the emitter's report: the audit's
    whole job is to derive what should have been emitted from the suggestions
    document rather than to accept the emitter's account of itself.

    That derivation also lands on the right count when a bullet is *shared*.
    `_build_link_to_moc_actions` dedups by (target MOC, title) while
    `derive_expected` counts one per item, so two same-titled items under one
    MOC expect 2 and emit 1. Dropping one of them subtracts 1 and the emitted
    bullet survives (the other item still authors it); dropping both subtracts
    2 and the bullet is withdrawn. Either way both sides agree.

    The move join is `_keys_match`, not set membership: a clash entry's
    `source_inbox_item` is the inbox-joined path a rendered action carries,
    while `by_item`'s key comes straight from `confirmed_items` and is never
    inbox-prefixed. Deletions are matched by the raw path first (an audio peer
    is expected under its full path) and by the bare stem second (an origin is
    expected under its stem), mirroring how `derive_expected` appends each.

    Returns the number of expected entries removed.
    """
    removed = 0
    for clash in withholdings or []:
        for dropped in clash.get("dropped") or []:
            origin = dropped.get("source_inbox_item") or ""
            if not origin:
                continue
            for item_id, info in list(expected["by_item"].items()):
                if info.get("kind") != "move_note":
                    continue
                if _keys_match(info.get("item_key") or "", origin):
                    del expected["by_item"][item_id]
                    expected["counts"]["move_note"] -= 1
                    expected["counts"]["link_to_moc"] -= len(
                        info.get("expected_links") or []
                    )
                    removed += 1
                    break
        for path in clash.get("withdrawn_deletes") or []:
            for candidate in (path, _stem(path)):
                if candidate in expected["expected_deletions"]:
                    expected["expected_deletions"].remove(candidate)
                    expected["counts"]["delete_source"] -= 1
                    removed += 1
                    break
    return removed


def _subtract_withdrawn_deletes(expected: dict, delete_withdrawals: list[dict]) -> int:
    """Remove T4.3-reported delete withdrawals from expected["expected_deletions"].

    `tomo.delete_withdrawals` (spec 036 T4.3) is the full record of every
    withdrawn `delete_source`, independent of *why* it was withdrawn — unlike
    `destination_clashes[]`/`attachment_suppressions[]`'s own `withdrawn_
    deletes`, which only lists the ones THEY caused. T2.3 kept both reports
    (retired only the path-keyed *removal*), so a clash- or suppression-
    caused withdrawal is ALREADY subtracted by `_subtract_withheld_moves`
    before this runs, and the SAME delete also appears here.

    Subtracting both double-counts and drives `expected` below `actual` — the
    same halt `_subtract_withheld_moves` exists to prevent, with the opposite
    sign and a harder cause to find. So this filters by GUARD, not by path: an
    entry is skipped in full when ANY of its `causes` names
    `validate_destinations` or `suppress_moves_for_unfiled_attachments`
    (`_CLASH_WITHDRAWAL_GUARDS`) — already accounted for — and subtracted
    otherwise. `causes` is not guaranteed single-guard (a delete can depend on
    both a move id and a daily id), so every cause is checked, not just the
    first; a path-based dedup collapses exactly this mixed case, which is why
    it is not used here.

    Matches `source_path` first, then its bare stem — mirroring
    `_subtract_withheld_moves` and `derive_expected`'s own append convention
    (`expected_deletions` holds bare stems). A `source_path` absent from
    `expected_deletions` (already removed, or naming something this
    derivation never expected) is a no-op — never a negative count.

    Returns the number of expected entries removed.
    """
    removed = 0
    for withdrawal in delete_withdrawals or []:
        causes = withdrawal.get("causes") or []
        if any(c.get("guard") in _CLASH_WITHDRAWAL_GUARDS for c in causes):
            continue
        path = withdrawal.get("source_path") or ""
        if not path:
            continue
        for candidate in (path, _stem(path)):
            if candidate in expected["expected_deletions"]:
                expected["expected_deletions"].remove(candidate)
                expected["counts"]["delete_source"] -= 1
                removed += 1
                break
    return removed


def _subtract_skipped_assets(expected: dict, skipped_assets: list[dict]) -> int:
    """Remove attachments the renderer could not file from expected move_asset.

    `derive_expected` counts one `move_asset` per distinct attachment path on
    the confirmed items. Whatever K1 (`attachment_plan._decide`) withholds, the
    move builder emits no `move_asset` for and records the path in
    `tomo.skipped_assets` instead; the kind set belongs to K1 and is not
    enumerated here. Each such entry is one path the renderer deliberately did
    not file — the same subtraction
    `_subtract_skipped_daily` makes for a missing daily note.

    Present since spec 031 and only reachable once discovery became recursive
    (a flat inbox cannot hold two files with one basename), so this closes a
    pre-existing FAIL rather than one T5.4 introduced — but T5.4 is the task
    that makes the clash a normal outcome, and a guard whose own audit halts
    the run is not shippable.

    Returns the number of expected entries removed.
    """
    removed = 0
    for _entry in skipped_assets or []:
        if expected["counts"]["move_asset"] <= 0:
            break
        expected["counts"]["move_asset"] -= 1
        removed += 1
    return removed


def _subtract_unresolvable_links(expected: dict, records: list[dict]) -> int:
    """Remove MOC links the renderer withheld from the expected link tallies.

    `filter_unresolvable_moc_links` withholds a `link_to_moc` whose target MOC
    the run could not confirm exists (spec 034 T6.0d) and records it in
    `instructions.tomo.unresolvable_moc_links`. `derive_expected` counts one
    link per `parent_mocs` entry regardless of resolution, so without this the
    audit reports `RESULT: FAIL` on a correct instruction set and the
    conductor's STRICT stop halts the run misdiagnosing the guard as drift —
    the same failure `_subtract_withheld_moves` exists to prevent.

    Subtracted for ALL THREE causes. Not because the three are equivalent —
    they are not, and the observation notes keep them apart — but because the
    count table only answers "did the renderer emit what the document
    promised", and the renderer withheld the link under every cause. Leaving
    two of them unsubtracted turns a deliberate withholding into a hard fail,
    which is the wrong answer for all of them.

    One withheld action can cover several expected entries: the emitter dedups
    by (target MOC, source title) while `derive_expected` counts one per item,
    so two same-titled items under one MOC expect 2 and emit 1. Every matching
    expectation is therefore subtracted, not just the first — the same
    shared-bullet arithmetic `_subtract_withheld_moves` documents.

    Returns the number of expected entries removed.
    """
    removed = 0
    for record in records or []:
        title = record.get("source_note_title") or ""
        moc = _moc_stem(record.get("target_moc") or "")
        if not title or not moc:
            continue
        for info in expected["by_item"].values():
            if info.get("title") != title:
                continue
            links = info.get("expected_links") or []
            if moc in links:
                links.remove(moc)
                expected["counts"]["link_to_moc"] -= 1
                removed += 1
    return removed


def _unresolvable_link_notes(records: list[dict]) -> list[str]:
    """One aggregated note per cause — never one per link.

    `client is None` is a single condition set once for the whole run, so every
    tier-2 miss in that run shares it: a run with Kado down would otherwise
    emit a dozen near-identical lines and bury the one fact that matters. Every
    other withholding note in the audit aggregates a count plus a pointer to
    the itemised detail in instructions.md; these follow that template.

    The two "nothing was checked" causes keep their own notes. Merging them
    with the confirmed-absent one would make an offline run indistinguishable
    from one where Kado confirmed the MOC missing — the CON-2 conflation this
    whole guard removes from the renderer, reintroduced one layer down.
    """
    by_cause: dict[str, int] = {}
    for record in records or []:
        by_cause[record.get("cause") or "unknown"] = (
            by_cause.get(record.get("cause") or "unknown", 0) + 1
        )
    detail = 'see "MOC link not offered" in instructions.md'
    wording = {
        "absent": (
            "target MOC confirmed absent by Kado; excluded from expected "
            f"coverage — {detail}, create the MOC and re-run Pass 2"
        ),
        "unchecked": (
            "target MOC could not be checked — Kado was not available for this "
            f"run, so nothing was asked about it; {detail}, re-run with Kado "
            "running"
        ),
        "probe-failed": (
            "target MOC could not be checked — the Kado lookup failed; this is "
            f"not evidence the MOC is missing; {detail}, re-run once Kado "
            "answers"
        ),
    }
    notes: list[str] = []
    # Fixed order so a run's observations read the same way every time; any
    # unrecognised cause is reported rather than silently dropped, because a
    # withholding nobody can explain is worse than one nobody expected.
    ordered = [c for c in ("absent", "unchecked", "probe-failed") if c in by_cause]
    ordered += [c for c in by_cause if c not in wording]
    for cause in ordered:
        count = by_cause[cause]
        why = wording.get(
            cause, f"withheld for unrecognised cause {cause!r}; {detail}"
        )
        notes.append(f"{count} MOC link(s) withheld — {why}")
    return notes

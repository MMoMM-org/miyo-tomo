# version: 0.1.0
"""render_attachment_withhold.py — hold a note whose attachment could not be filed.

Split out of render_actions.py (#216, Constitution L2 file size). The sibling
of the destination guard: keeps every owning note (and its paired deletes and
MOC bullets) in the inbox when an attachment was withheld, then drops the
staging notes no surviving action claims. Shares the withdrawal machinery in
render_withhold so both guards withdraw by one mechanism.
"""
from __future__ import annotations

from lib.refusal_sentences import withheld_attachment_remedy
from lib.render_withhold import (
    _drop_moves_with_paired_deletes,
    _links_for,
    _paired_delete_candidates,
)


def _attachment_suppression_reason(entry: dict, note_count: int) -> str:
    """The sentence the user reads for one attachment that could not be filed.

    The head names the attachment and why it was withheld; the remedy is
    `lib.refusal_sentences.withheld_attachment_remedy` for the entry's kind —
    the same remedy the "Attachments still in the inbox" bullet and the shell
    relay carry, so one item never reads two different fixes (owner ruling
    2026-10-12). A destination clash (`collision`) names the claimed
    destination; every other kind's head is the entry's own `reason`, phrased
    by `lib.refusal_sentences` (or the plan, for `no_basename`).
    `vault_collision_held` never reaches this function at all (excluded in
    `suppress_moves_for_unfiled_attachments`, below).
    """
    source = entry.get("source") or "?"
    kind = entry.get("kind")
    if kind == "collision":
        head = (
            f"`{source}` cannot be filed — another file of that name already "
            f"claims `{entry.get('destination')}`"
        )
    else:
        head = f"`{source}` cannot be filed — {entry.get('reason') or 'no filename'}"
    remedy = withheld_attachment_remedy(kind, entry.get("destination"))
    tail = (
        "the note that embeds it is not filed either"
        if note_count == 1
        else f"the {note_count} notes that embed it are not filed either"
    )
    return f"{head} — {tail}. {remedy}."


def suppress_moves_for_unfiled_attachments(
    actions: list[dict], skipped_assets: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Keep a note in the inbox when its attachment could not be filed.

    Returns ``(kept_actions, suppressions)``. Runs after ``build_actions`` as a
    sibling of ``validate_destinations``, over the whole assembled list, for a
    reason the ordering inside ``build_actions`` forces: the paired
    ``delete_source`` actions do not exist yet while ``_build_move_asset_actions``
    is running, so an inline suppression would have nothing to withdraw and the
    note's source would be deleted while the note stayed in the inbox — losing
    it outright, which is worse than filing it incompletely.

    This **reverses spec 031** (`plan/phase-2.md:85`), which let the note move
    without its attachment. That was right while a flat inbox made a basename
    clash unreachable; recursive discovery made it reachable, and moving a note
    never carries its attachments, so the file would stay in the inbox
    indefinitely `[ref: PRD/Feature 8, SDD/ADR-6]`.

    Only the *owning* notes are suppressed, joined on the resolved source path
    (ADR-1) that `_build_move_asset_actions` recorded on each skipped entry —
    never on the stem, which two notes in different inbox folders share.

    `kind: vault_collision_held` (spec 037) is excluded from this pass: the
    owner chose *keep in inbox* for the attachment, not for the note, and
    holding the note anyway would silently widen that choice. See
    docs/tomo/scripts/lib/render_actions.md for why this needed an explicit
    exclusion rather than following from the shape above.

    Composes with ``validate_destinations`` in either order: a move that pass
    already dropped is absent here, so no note is reported as withheld twice
    and no delete or MOC link is counted as withdrawn twice. Only suppressions that
    actually withheld a move are returned — the attachment itself is already
    reported through ``skipped_assets``.

    The pass holds no state across calls: renaming one file and re-running
    Pass 2 files everything, with no memo of the earlier clash.
    """
    if not skipped_assets:
        return actions, []

    moves_by_source: dict[str, list[dict]] = {}
    for action in actions:
        if action.get("action") != "move_note":
            continue
        source = action.get("source_inbox_item")
        if source:
            moves_by_source.setdefault(source, []).append(action)

    pending: list[tuple[dict, list[str]]] = []
    dropped_ids: set[str] = set()
    withdrawn_paths: set[str] = set()
    for entry in skipped_assets:
        if entry.get("kind") == "vault_collision_held":
            # The owner's remedy — spec 037 T3.1. Only the file stays behind.
            continue
        dropped: list[dict] = []
        candidates: list[str] = []
        for owner in entry.get("owner_source_items") or []:
            for move in moves_by_source.get(owner) or []:
                if move.get("id") in dropped_ids:
                    continue
                dropped_ids.add(move.get("id"))
                dropped.append({
                    "id": move.get("id"),
                    "title": move.get("title"),
                    "destination": move.get("destination"),
                    "source_inbox_item": move.get("source_inbox_item"),
                })
                candidates.extend(
                    _paired_delete_candidates(move, withdrawn_paths)
                )
        if not dropped:
            continue
        pending.append((
            {
                "kind": entry.get("kind"),
                "attachment": entry.get("source"),
                "attachment_destination": entry.get("destination"),
                "reason": _attachment_suppression_reason(entry, len(dropped)),
                "dropped": dropped,
                # Filled in below, once it is known which of `candidates`
                # actually had a delete_source to withdraw.
                "withdrawn_deletes": [],
                "withdrawn_moc_links": [],
            },
            candidates,
        ))

    if not pending:
        return actions, []

    kept, removed_deletes, removed_moc_links = _drop_moves_with_paired_deletes(
        actions, dropped_ids, withdrawn_paths
    )
    claimed_links: set[int] = set()
    for suppression, candidates in pending:
        suppression["withdrawn_deletes"] = [
            c for c in candidates if c in removed_deletes
        ]
        suppression["withdrawn_moc_links"] = _links_for(
            suppression, removed_moc_links, claimed_links
        )
    return kept, [suppression for suppression, _candidates in pending]


def claimed_rendered_files(actions: list[dict]) -> set[str]:
    """The staging notes an action list claims, by ``rendered_file``.

    Taken once over ``build_actions``' output and once over the guards'
    output; the difference is what a guard withheld. See
    ``manifest_without_withheld_staging``.
    """
    return {a.get("rendered_file") for a in actions if a.get("rendered_file")}


def manifest_without_withheld_staging(
    manifest: list[dict], actions: list[dict], claimed_before: set[str]
) -> tuple[list[dict], list[str]]:
    """Drop the manifest entries whose claim a guard withheld.

    Returns ``(kept_entries, withheld_filenames)``. Each manifest entry is a
    staging note that a later upload step writes into the inbox, and each is
    claimed by exactly one ``move_note`` or ``create_moc``. When a guard
    withholds that action the staging note has nothing left to move it, so the
    upload must not write it.

    Keyed on ``rendered_file``, which both action builders copy from the
    manifest entry — an action ``id`` is a fresh counter value and does not
    join back to the entry it came from.

    ``claimed_before`` is that key set as ``build_actions`` left it, and is
    what makes the pass precise rather than merely plausible: an entry no
    action ever claimed is **kept**, because nothing withheld it. Without that
    half, a run whose action building produced nothing would silently drop
    every staging note — indistinguishable here from a run where every move
    was withheld.

    Written against the surviving actions rather than against a withholding
    report, so both guards are covered by one pass and a third one would need
    no change here. An entry with no ``rendered_file`` is kept: nothing was
    rendered for it to leave behind.
    """
    surviving = claimed_rendered_files(actions)
    kept: list[dict] = []
    withheld: list[str] = []
    for entry in manifest:
        rendered = entry.get("rendered_file")
        if rendered and rendered in claimed_before and rendered not in surviving:
            withheld.append(rendered)
            continue
        kept.append(entry)
    return kept, withheld

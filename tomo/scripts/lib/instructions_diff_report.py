# version: 0.1.0
"""instructions_diff_report.py — the suggestions-mode coverage report.

Extracted from instructions-diff.py (#216). `run_diff` derives both sides,
applies every reconciliation, prints the count table, per-item, extension,
daily, delete and skip coverage plus observations, and returns the exit code
the CLI hands back. Its printed text is the conductor's audit contract.
"""
from __future__ import annotations

from lib.instructions_diff_expected import derive_expected, summarize_actual
from lib.instructions_diff_extensions import _reconcile_extensions
from lib.instructions_diff_garden import _is_garden_parsed, run_diff_garden
from lib.instructions_diff_keys import _keys_match, _moc_stem, _parse_supporting_items
from lib.instructions_diff_reconcile import (
    _subtract_skipped_assets,
    _subtract_skipped_daily,
    _subtract_unresolvable_links,
    _subtract_withdrawn_deletes,
    _subtract_withheld_moves,
    _unresolvable_link_notes,
)

# ──────────────────────────────────────────────────────────────────────────────
# Reporting
# ──────────────────────────────────────────────────────────────────────────────

ACTION_ORDER = [
    "move_note", "move_asset", "create_moc", "link_to_moc",
    "update_tracker", "update_log_entry", "update_log_link",
    "delete_source", "skip", "edit_frontmatter",
]


def run_diff(
    parsed: dict, instrs: dict, tag_handler_groups: list[dict] | None = None
) -> tuple[int, list[str]]:
    """Compare parsed suggestions with instructions.json.

    Returns (exit_code, observations). exit_code=0 means counts reconcile.
    """
    # Garden-audit docs carry garden_action items — a different shape with its
    # own count math. Route them to the dedicated garden mode.
    if _is_garden_parsed(parsed):
        return run_diff_garden(parsed, instrs)

    expected = derive_expected(parsed, tag_handler_groups)
    actual = summarize_actual(instrs)

    # Reconcile daily-note actions the renderer legitimately dropped (missing
    # target daily note) before comparing — see _subtract_skipped_daily.
    skipped_daily = (instrs.get("tomo") or {}).get("skipped_daily") or []
    n_daily_skipped = _subtract_skipped_daily(expected, skipped_daily)

    # Reconcile the moves and paired deletes the two Pass-2 guards withheld,
    # and the attachments the renderer could not file — see
    # _subtract_withheld_moves and _subtract_skipped_assets.
    tomo_block = instrs.get("tomo") or {}
    destination_clashes = tomo_block.get("destination_clashes") or []
    attachment_suppressions = tomo_block.get("attachment_suppressions") or []
    skipped_assets = tomo_block.get("skipped_assets") or []
    _subtract_withheld_moves(expected, destination_clashes)
    _subtract_withheld_moves(expected, attachment_suppressions)
    n_assets_skipped = _subtract_skipped_assets(expected, skipped_assets)

    # Reconcile deletes withdrawn for a reason the clash/suppression reports
    # above do not already cover (missing daily note, unresolvable MOC link,
    # unappliable relationship, or an undeclared dependency) — see
    # _subtract_withdrawn_deletes for why this must filter by guard.
    delete_withdrawals = tomo_block.get("delete_withdrawals") or []
    _subtract_withdrawn_deletes(expected, delete_withdrawals)

    # Reconcile the MOC links withheld because their target could not be
    # confirmed — see _subtract_unresolvable_links.
    unresolvable_links = tomo_block.get("unresolvable_moc_links") or []
    _subtract_unresolvable_links(expected, unresolvable_links)

    # Extensions are checked per member against the renderer's record.
    ext_lines, ext_notes, ext_fail = _reconcile_extensions(
        expected, instrs, unresolvable_links
    )

    lines: list[str] = []
    observations: list[str] = list(ext_notes)
    hard_fail = ext_fail

    # Header
    total_conf = len(parsed.get("confirmed_items") or [])
    total_daily_dates = len(parsed.get("daily_updates") or [])
    total_skipped = len(parsed.get("skipped") or [])
    action_count = instrs.get("action_count", len(instrs.get("actions") or []))
    lines.append("=" * 72)
    lines.append("instructions-diff — suggestions vs instructions coverage")
    lines.append("=" * 72)
    lines.append(
        f"  suggestions: confirmed={total_conf} "
        f"daily_dates={total_daily_dates} skipped={total_skipped}"
    )
    lines.append(f"  instructions: action_count={action_count}")

    # Count table
    lines.append("")
    lines.append(f"  {'kind':<20s} {'expected':>9s} {'actual':>9s}  status")
    lines.append(f"  {'-'*20} {'-'*9} {'-'*9}  {'-'*7}")
    total_expected = 0
    total_actual = 0
    for kind in ACTION_ORDER:
        exp = expected["counts"].get(kind, 0)
        act = actual["counts"].get(kind, 0)
        total_expected += exp
        total_actual += act
        status = "[OK]" if exp == act else "[DIFF]"
        if exp != act:
            hard_fail = True
        lines.append(f"  {kind:<20s} {exp:>9d} {act:>9d}  {status}")
    lines.append(f"  {'-'*20} {'-'*9} {'-'*9}  {'-'*7}")
    total_status = "[OK]" if total_expected == total_actual else "[DIFF]"
    if total_expected != total_actual:
        hard_fail = True
    lines.append(f"  {'TOTAL':<20s} {total_expected:>9d} {total_actual:>9d}  {total_status}")

    # Per-item coverage
    lines.append("")
    lines.append("  per-item coverage (file-action + parent_mocs):")
    for item_id, info in expected["by_item"].items():
        if info["kind"] == "create_moc":
            found = any(a.get("title") == info["title"] for a in actual["create_mocs"])
        else:
            expected_key = info.get("item_key") or ""
            found = bool(expected_key) and any(
                _keys_match(expected_key, actual_key)
                for actual_key in actual["move_by_key"]
            )
        file_mark = "[OK]" if found else "[MISSING]"
        if not found:
            hard_fail = True

        # Links: expected parent stems vs actual links from this item's source
        # For create_moc: links carry source_note_title == new MOC title.
        # For move_note: links carry source_note_title == item title.
        source_key = info["title"]
        actual_links = actual["links_by_source"].get(source_key, [])
        expected_links = info["expected_links"]
        if sorted(actual_links) == sorted(expected_links):
            link_mark = "[OK]"
        else:
            hard_fail = True
            link_mark = f"[DIFF want={expected_links} got={actual_links}]"
        title_short = info["title"][:50]
        lines.append(
            f"    {item_id:<6s} {info['kind']:<11s} {title_short:<52s} "
            f"file={file_mark} links={link_mark}"
        )

    if ext_lines:
        lines.append("")
        lines.append("  extension coverage (add_relationship + link_to_moc per member):")
        lines.extend(ext_lines)

    # Daily coverage
    if expected["expected_daily"] or any(actual["daily_by_kind"].values()):
        lines.append("")
        lines.append("  daily-update coverage:")
        for kind in ("update_tracker", "update_log_entry", "update_log_link"):
            exp_items = [e for e in expected["expected_daily"] if e["kind"] == kind]
            act_items = actual["daily_by_kind"].get(kind, [])
            mark = "[OK]" if len(exp_items) == len(act_items) else "[DIFF]"
            if len(exp_items) != len(act_items):
                hard_fail = True
            lines.append(
                f"    {kind:<20s} expected={len(exp_items)} actual={len(act_items)} {mark}"
            )

    if destination_clashes:
        withheld = sum(len(c.get("dropped") or []) for c in destination_clashes)
        # Count the withdrawn deletes rather than implying one per move: an
        # item the user marked "Keep source files" has no paired delete to
        # withdraw, and the note must not claim one was.
        withdrawn = sum(
            len(c.get("withdrawn_deletes") or []) for c in destination_clashes
        )
        note = (
            f"{withheld} move(s) and {withdrawn} paired delete(s) withheld — "
            f"{len(destination_clashes)} destination(s) claimed twice; see "
            "\"Not filed\" in instructions.md, rename one and re-run Pass 2"
        )
        lines.append("")
        lines.append(f"  note: {note}")
        observations.append(note)

    if attachment_suppressions:
        withheld = sum(len(s.get("dropped") or []) for s in attachment_suppressions)
        withdrawn = sum(
            len(s.get("withdrawn_deletes") or []) for s in attachment_suppressions
        )
        note = (
            f"{withheld} move(s) and {withdrawn} paired delete(s) withheld — "
            f"{len(attachment_suppressions)} attachment(s) could not be filed; "
            "see \"an attachment could not be filed\" in instructions.md, "
            "rename the file and re-run Pass 2"
        )
        lines.append("")
        lines.append(f"  note: {note}")
        observations.append(note)

    if n_assets_skipped:
        note = (
            f"{n_assets_skipped} attachment(s) not filed — no basename, or a "
            "destination already claimed by a different file; excluded from "
            "expected coverage"
        )
        lines.append("")
        lines.append(f"  note: {note}")
        observations.append(note)

    if n_daily_skipped:
        note = (
            f"{n_daily_skipped} daily-note update(s) skipped — target daily note "
            "missing (Hashi cannot create it); excluded from expected coverage"
        )
        lines.append("")
        lines.append(f"  note: {note}")
        observations.append(note)

    for note in _unresolvable_link_notes(unresolvable_links):
        lines.append("")
        lines.append(f"  note: {note}")
        observations.append(note)

    # Delete / skip coverage
    lines.append("")
    exp_del = len(expected["expected_deletions"])
    act_del = len(actual["deletes"])
    lines.append(
        f"  delete_source coverage: expected={exp_del} actual={act_del} "
        f"{'[OK]' if exp_del == act_del else '[DIFF]'}"
    )
    exp_sk = len(expected["expected_skips"])
    act_sk = len(actual["skips"])
    lines.append(
        f"  skip coverage:          expected={exp_sk} actual={act_sk} "
        f"{'[OK]' if exp_sk == act_sk else '[DIFF]'}"
    )

    # Soft observations — flag create_mocs that will be created empty.
    # An approved MOC is "empty" when (a) it has no supporting_items AND
    # (b) no confirmed atomic note has it in its parent_mocs.
    for item_id, info in expected["by_item"].items():
        if info["kind"] != "create_moc":
            continue
        moc_title = info["title"]
        has_supporting = bool(_parse_supporting_items(info.get("supporting_items")))
        has_parent_link = any(
            moc_title in [_moc_stem(m) for m in other.get("expected_links", [])]
            for other_id, other in expected["by_item"].items()
            if other_id != item_id
        )
        if not has_supporting and not has_parent_link:
            observations.append(
                f"Approved create_moc {moc_title!r} ({item_id}) will be created "
                f"empty — no supporting_items on the Proposed MOC block and no "
                f"confirmed atomic note lists it as parent_moc. Add supporting "
                f"items (preferred) or parent_moc links before re-running Pass 2."
            )

    # Print observations
    if observations:
        lines.append("")
        lines.append("  observations (non-blocking):")
        for obs in observations:
            lines.append(f"    [WARN] {obs}")

    # Summary
    lines.append("")
    lines.append("-" * 72)
    if hard_fail:
        lines.append("RESULT: FAIL — count or coverage mismatch above.")
    else:
        lines.append(
            f"RESULT: OK — {total_actual}/{total_expected} actions reconciled"
            + (f", {len(observations)} observation(s)" if observations else "")
            + "."
        )

    print("\n".join(lines))
    return (1 if hard_fail else 0), observations

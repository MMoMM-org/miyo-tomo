# version: 0.1.0
"""instructions_diff_garden.py — garden-audit mode of the coverage audit.

Extracted from instructions-diff.py (#216). Garden-audit envelopes carry
`garden_action` items with their own count math, so they get a separate
report path (spec 030) that `run_diff` routes to by shape.
"""
from __future__ import annotations

from lib.instructions_diff_reconcile import _unresolvable_link_notes

# ── Garden-audit mode (spec 030) ──────────────────────────────────────────────
# Garden confirmed_items are semantic fix items keyed by garden_action, not the
# suggestions manifest shape — without this mode every garden item was
# miscounted as an expected move_note and the coverage audit hard-failed on
# ANY garden-audit doc (pre-existing gap, fixed 2026-07-23).

GARDEN_ACTION_ORDER = [
    "resolve_dead_link", "remove_up_link", "link_to_moc", "add_relationship",
    "edit_frontmatter",
]

# garden_action → instruction kinds it must produce (mirrors
# render_actions.build_garden_audit_actions).
_GARDEN_EXPECTED_KINDS: dict[str, tuple[str, ...]] = {
    "resolve_dead_link": ("resolve_dead_link",),
    "remove_up_link": ("remove_up_link",),
    "add_relationship": ("add_relationship",),
    "file_note": ("link_to_moc", "add_relationship"),
    "edit_frontmatter": ("edit_frontmatter",),
}


def _is_garden_parsed(parsed: dict) -> bool:
    """True when the parsed envelope is garden-audit-shaped (garden_action items)."""
    items = parsed.get("confirmed_items") or []
    return bool(items) and all("garden_action" in i for i in items)


def _garden_item_covered(
    item: dict, actions: list[dict], withheld_link_titles: set[str] | None = None,
) -> bool:
    """True when every instruction kind this garden item owes exists with a
    matching path anchor (mirrors build_garden_audit_actions field wiring).

    `withheld_link_titles` names the source notes whose `link_to_moc` the
    renderer deliberately withheld (spec 034 T6.0d): a garden `file_note` whose
    File-under value names a MOC Kado cannot confirm reaches the same guard the
    suggestions path does, and an absent instruction there is the guard
    working, not a coverage gap.
    """
    ga = item.get("garden_action")
    path = item.get("path", "")
    stem = item.get("stem", "")
    for kind in _GARDEN_EXPECTED_KINDS.get(ga, ()):
        if kind == "link_to_moc" and stem in (withheld_link_titles or set()):
            continue
        if kind == "resolve_dead_link":
            ok = any(
                a["action"] == kind and a.get("path") == path
                and a.get("target") == item.get("target")
                for a in actions
            )
        elif kind == "remove_up_link":
            ok = any(
                a["action"] == kind and a.get("path") == path
                and a.get("link") == item.get("link")
                for a in actions
            )
        elif kind == "add_relationship":
            ok = any(
                a["action"] == kind and a.get("target_moc_path") == path
                for a in actions
            )
        elif kind == "edit_frontmatter":
            ok = any(
                a["action"] == kind and a.get("path") == path
                for a in actions
            )
        else:  # link_to_moc (file_note bullet on the MOC)
            ok = any(
                a["action"] == kind and a.get("source_note_title") == stem
                for a in actions
            )
        if not ok:
            return False
    return True


def run_diff_garden(parsed: dict, instrs: dict) -> tuple[int, list[str]]:
    """Garden-audit coverage: expected instruction counts per garden_action vs
    actual, plus per-item path-anchored coverage. Same envelope as run_diff."""
    confirmed = parsed.get("confirmed_items") or []
    actions = instrs.get("actions") or []

    # The MOC links this run withheld because their target could not be
    # confirmed. Garden `file_note` items flow through the same renderer and
    # the same guard, so the same subtraction applies — see
    # _subtract_unresolvable_links for why a raw [DIFF] is the wrong answer.
    unresolvable_links = (instrs.get("tomo") or {}).get(
        "unresolvable_moc_links") or []
    withheld_link_titles = {
        r.get("source_note_title") for r in unresolvable_links
        if r.get("source_note_title")
    }

    expected_counts: dict[str, int] = {k: 0 for k in GARDEN_ACTION_ORDER}
    for item in confirmed:
        for kind in _GARDEN_EXPECTED_KINDS.get(item.get("garden_action"), ()):
            if kind == "link_to_moc" and item.get("stem") in withheld_link_titles:
                continue
            expected_counts[kind] = expected_counts.get(kind, 0) + 1

    actual_counts: dict[str, int] = {}
    for a in actions:
        actual_counts[a["action"]] = actual_counts.get(a["action"], 0) + 1

    lines: list[str] = []
    observations: list[str] = []
    hard_fail = False

    acked = parsed.get("acked_advisories") or []
    lines.append("=" * 72)
    lines.append("instructions-diff — garden-audit fixes vs instructions coverage")
    lines.append("=" * 72)
    lines.append(
        f"  garden-audit: confirmed={len(confirmed)} acked_advisories={len(acked)}"
    )
    lines.append(
        f"  instructions: action_count="
        f"{instrs.get('action_count', len(actions))}"
    )
    lines.append("")
    lines.append(f"  {'kind':<20s} {'expected':>9s} {'actual':>9s}  status")
    lines.append(f"  {'-'*20} {'-'*9} {'-'*9}  {'-'*7}")
    total_expected = total_actual = 0
    all_kinds = GARDEN_ACTION_ORDER + [
        k for k in sorted(actual_counts) if k not in GARDEN_ACTION_ORDER
    ]
    for kind in all_kinds:
        exp = expected_counts.get(kind, 0)
        act = actual_counts.get(kind, 0)
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
    lines.append(
        f"  {'TOTAL':<20s} {total_expected:>9d} {total_actual:>9d}  {total_status}"
    )

    lines.append("")
    lines.append("  per-item coverage (garden_action → instruction kinds):")
    for item in confirmed:
        covered = _garden_item_covered(item, actions, withheld_link_titles)
        if not covered:
            hard_fail = True
        mark = "[OK]" if covered else "[MISSING]"
        lines.append(
            f"    {item.get('id', '?'):<6s} {item.get('garden_action', '?'):<17s} "
            f"{(item.get('stem') or '')[:44]:<46s} {mark}"
        )

    for note in _unresolvable_link_notes(unresolvable_links):
        lines.append("")
        lines.append(f"  note: {note}")
        observations.append(note)

    lines.append("")
    lines.append("-" * 72)
    if hard_fail:
        lines.append("RESULT: FAIL — count or coverage mismatch above.")
    else:
        lines.append(
            f"RESULT: OK — {total_actual}/{total_expected} actions reconciled."
        )
    print("\n".join(lines))
    return (1 if hard_fail else 0), observations

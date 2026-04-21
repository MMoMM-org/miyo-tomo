#!/usr/bin/env python3
# version: 0.1.0
"""instructions-diff.py — Reconcile parsed-suggestions.json with instructions.json.

Pass-2 coverage audit: every approved suggestion should produce a
well-formed instruction, and the instruction set should not contain
actions without a matching source in the suggestions doc. This script
cross-checks the two JSONs item-by-item and surfaces:

  - Count mismatches per action kind (expected from suggestions vs.
    actual in instructions.json).
  - Per-confirmed-item coverage: each atomic/create_moc item should have
    exactly one file action (move_note or create_moc) plus one
    link_to_moc per parent_moc.
  - Daily-update coverage: each accepted tracker/log_entry/log_link in
    parsed-suggestions should produce one matching action.
  - Skip / delete coverage: explicit skipped[] entries and daily-only
    delete inferences reconciled.
  - Observations (soft, non-blocking): e.g. approved `create_moc` with
    no confirmed items linking up to it.

Usage:
  python3 scripts/instructions-diff.py \\
    --suggestions tomo-tmp/parsed-suggestions.json \\
    --instructions tomo-tmp/rendered/instructions.json

  # Shorthand with default paths relative to CWD:
  python3 scripts/instructions-diff.py          # uses tomo-tmp/ defaults

Exit codes:
  0 — all expected actions accounted for (observations OK)
  1 — hard mismatch (count disagreement or missing/extra actions)
  2 — I/O or JSON parse error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _stem(path: str | None) -> str:
    if not path:
        return ""
    p = path.rsplit("/", 1)[-1]
    if p.endswith(".md"):
        p = p[:-3]
    return p


def _moc_stem(name: str | None) -> str:
    return _stem(name)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(2)


# ──────────────────────────────────────────────────────────────────────────────
# Expected-action derivation from parsed-suggestions.json
# Mirrors scripts/instruction-render.py:build_actions (without the renderer)
# so the diff has an independent source of truth for the count math.
# ──────────────────────────────────────────────────────────────────────────────

def derive_expected(parsed: dict) -> dict:
    """Derive expected action counts & per-item coverage from parsed suggestions.

    Returns:
      {
        "counts": {kind: int},
        "by_item": {item_id: {"kind": "move_note"|"create_moc",
                              "title": str,
                              "expected_links": [moc_stem, ...]}},
        "expected_daily_kinds": [{"kind", "date", "key", "source_stem"}],
        "expected_deletions": [source_path],
        "expected_skips": [source_path_or_None],
      }
    """
    confirmed = parsed.get("confirmed_items") or []
    daily_updates = parsed.get("daily_updates") or []
    skipped = parsed.get("skipped") or []

    counts: dict[str, int] = {
        "move_note": 0,
        "create_moc": 0,
        "link_to_moc": 0,
        "update_tracker": 0,
        "update_log_entry": 0,
        "update_log_link": 0,
        "delete_source": 0,
        "skip": 0,
    }

    by_item: dict[str, dict] = {}
    for item in confirmed:
        item_id = item.get("id", "?")
        parents = item.get("parent_mocs") or []
        if not parents and item.get("parent_moc"):
            parents = [item["parent_moc"]]
        parent_stems = [_moc_stem(p) for p in parents if p]
        title = item.get("title") or _stem(item.get("source_path"))
        if item.get("action") == "create_moc":
            counts["create_moc"] += 1
            by_item[item_id] = {
                "kind": "create_moc",
                "title": title,
                "expected_links": parent_stems,
                "source_path": item.get("source_path"),
            }
        else:
            counts["move_note"] += 1
            by_item[item_id] = {
                "kind": "move_note",
                "title": title,
                "expected_links": parent_stems,
                "source_path": item.get("source_path"),
            }
        counts["link_to_moc"] += len(parent_stems)

    expected_daily: list[dict] = []
    for day in daily_updates:
        date = day.get("date")
        for t in day.get("trackers") or []:
            if not t.get("accepted"):
                continue
            counts["update_tracker"] += 1
            expected_daily.append({
                "kind": "update_tracker",
                "date": date,
                "key": t.get("field"),
                "value": t.get("value"),
                "source_stem": _stem(t.get("source_stem")),
            })
        for le in day.get("log_entries") or []:
            if not le.get("accepted"):
                continue
            counts["update_log_entry"] += 1
            expected_daily.append({
                "kind": "update_log_entry",
                "date": date,
                "key": (le.get("content") or "")[:40],
                "source_stem": _stem(le.get("source_stem")),
            })
        for ll in day.get("log_links") or []:
            if not ll.get("accepted"):
                continue
            counts["update_log_link"] += 1
            expected_daily.append({
                "kind": "update_log_link",
                "date": date,
                "key": _stem(ll.get("target_stem")),
                "source_stem": _stem(ll.get("source_stem", "")),
            })

    # Delete source: explicit skipped[] + daily-only inferences
    confirmed_stems = {_stem(it.get("source_path")) for it in confirmed if it.get("source_path")}
    expected_deletions: list[str] = []
    for sk in skipped:
        if sk.get("disposition") == "delete_source":
            expected_deletions.append(_stem(sk.get("source_path")))
    # Daily-only: accepted daily items whose source_stem isn't in confirmed
    daily_only_seen: set[str] = set()
    for day in daily_updates:
        for bucket in ("trackers", "log_entries", "log_links"):
            for entry in day.get(bucket) or []:
                if not entry.get("accepted"):
                    continue
                stem = _stem(entry.get("source_stem"))
                if stem and stem not in confirmed_stems and stem not in daily_only_seen:
                    daily_only_seen.add(stem)
                    expected_deletions.append(stem)
    counts["delete_source"] = len(expected_deletions)

    expected_skips: list[str] = []
    for sk in skipped:
        if sk.get("disposition") == "skip":
            expected_skips.append(_stem(sk.get("source_path")))
    counts["skip"] = len(expected_skips)

    return {
        "counts": counts,
        "by_item": by_item,
        "expected_daily": expected_daily,
        "expected_deletions": expected_deletions,
        "expected_skips": expected_skips,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Actual-action summarization from instructions.json
# ──────────────────────────────────────────────────────────────────────────────

def summarize_actual(instrs: dict) -> dict:
    """Flatten the actual action list into the same shape used for diff."""
    actions = instrs.get("actions") or []
    counts: dict[str, int] = {}
    for a in actions:
        counts[a["action"]] = counts.get(a["action"], 0) + 1

    move_by_stem: dict[str, dict] = {}
    create_mocs: list[dict] = []
    links_by_source: dict[str, list[str]] = {}
    for a in actions:
        kind = a["action"]
        if kind == "move_note":
            stem = _stem(a.get("source_path"))
            move_by_stem[stem] = a
        elif kind == "create_moc":
            create_mocs.append(a)
        elif kind == "link_to_moc":
            src = a.get("source_note_title") or ""
            links_by_source.setdefault(src, []).append(_moc_stem(a.get("target_moc")))

    # Daily actions — bucket by kind
    daily_by_kind: dict[str, list[dict]] = {
        "update_tracker": [],
        "update_log_entry": [],
        "update_log_link": [],
    }
    for a in actions:
        if a["action"] in daily_by_kind:
            daily_by_kind[a["action"]].append(a)

    deletes = [a.get("source_path") for a in actions if a["action"] == "delete_source"]
    skips = [a.get("source_path") for a in actions if a["action"] == "skip"]

    return {
        "counts": counts,
        "move_by_stem": move_by_stem,
        "create_mocs": create_mocs,
        "links_by_source": links_by_source,
        "daily_by_kind": daily_by_kind,
        "deletes": deletes,
        "skips": skips,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Reporting
# ──────────────────────────────────────────────────────────────────────────────

ACTION_ORDER = [
    "move_note", "create_moc", "link_to_moc",
    "update_tracker", "update_log_entry", "update_log_link",
    "delete_source", "skip",
]


def run_diff(parsed: dict, instrs: dict) -> tuple[int, list[str]]:
    """Compare parsed suggestions with instructions.json.

    Returns (exit_code, observations). exit_code=0 means counts reconcile.
    """
    expected = derive_expected(parsed)
    actual = summarize_actual(instrs)

    lines: list[str] = []
    observations: list[str] = []
    hard_fail = False

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
            found = _stem(info.get("source_path")) in actual["move_by_stem"]
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

    # Soft observations
    for item_id, info in expected["by_item"].items():
        if info["kind"] != "create_moc":
            continue
        moc_title = info["title"]
        linking_items = [
            (other_id, other)
            for other_id, other in expected["by_item"].items()
            if other_id != item_id and moc_title in [_moc_stem(m) for m in other.get("expected_links", [])]
        ]
        if not linking_items:
            observations.append(
                f"Approved create_moc {moc_title!r} ({item_id}) has 0 confirmed "
                f"items linking up to it. New MOC will be created empty; "
                f"add `{moc_title}` to the Link-to-MOC checkboxes on related items "
                f"in the suggestions doc if you want them to land under it."
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
        lines.append(f"RESULT: FAIL — count or coverage mismatch above.")
    else:
        lines.append(
            f"RESULT: OK — {total_actual}/{total_expected} actions reconciled"
            + (f", {len(observations)} observation(s)" if observations else "")
            + "."
        )

    print("\n".join(lines))
    return (1 if hard_fail else 0), observations


def main() -> int:
    p = argparse.ArgumentParser(
        description="Compare parsed-suggestions.json vs instructions.json."
    )
    p.add_argument(
        "--suggestions", default="tomo-tmp/parsed-suggestions.json",
        help="Path to parsed-suggestions.json (default: tomo-tmp/parsed-suggestions.json)",
    )
    p.add_argument(
        "--instructions", default="tomo-tmp/rendered/instructions.json",
        help="Path to instructions.json (default: tomo-tmp/rendered/instructions.json)",
    )
    args = p.parse_args()

    parsed = load_json(Path(args.suggestions))
    instrs = load_json(Path(args.instructions))

    rc, _obs = run_diff(parsed, instrs)
    return rc


if __name__ == "__main__":
    sys.exit(main())

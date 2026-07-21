#!/usr/bin/env python3
# version: 0.2.0
"""garden-audit-stats.py — read-only overview mode for garden-audit (spec 030).

`/garden-audit stats` runs a fresh scan (reusing garden-audit.py, same doc.json)
then this deterministic renderer AGGREGATES the doc + reads the exclusion config
and relays a compact overview to the chat. NO vault write — an ephemeral status
view, re-runnable anytime.

Sections (markdown, compact):
  1. Open findings by area — findings grouped by AREA (first path segment;
     root-level → "(root)") × CHECK, table sorted by total DESC, top-N areas +
     an explicit "others" row (no silent truncation).
  2. Totals — per check, per tier, plus any skipped_checks (+ reason).
  3. Active exclusions — every active rule (permanent + unexpired temporary).
  4. On pushback — active TEMPORARY rules with `until` + days remaining,
     soonest-expiring first.
  5. Reappeared — expired exclusions from doc.reappeared_exclusions.

CLI (cwd-relative defaults, same style as the other garden scripts):
  python3 scripts/garden-audit-stats.py            # instance-relative defaults
Switches (--input / --exclusions) are host/test overrides only. --exclusions uses
a None sentinel: a defaulted-absent file → "none configured" section (exit 0); an
EXPLICITLY-passed missing path → error (exit 1).

Design notes: docs/tomo/scripts/garden-audit-stats.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.garden_exclusions import ALL_CHECK_NAMES, GardenExclusions  # noqa: E402

# Effective default exclusions path (instance-cwd-relative). Mirrors
# garden-audit.py's _DEFAULT_EXCL_PATH — the stats view reads the same config.
_DEFAULT_EXCL_PATH = "config/garden-audit-exclusions.yaml"
_DEFAULT_INPUT = "tomo-tmp/garden-audit-doc.json"

# Column ORDER is a display decision owned here; MEMBERSHIP is derived from the
# lib's authoritative ALL_CHECK_NAMES so a 7th check can't silently drift out of
# the table (a parity test locks _CHECKS == ALL_CHECK_NAMES as a set).
_CHECKS = ("dead_link", "orphan", "unparented", "broken_up", "duplicate_stem", "stale_moc")
assert set(_CHECKS) == set(ALL_CHECK_NAMES), (
    "stats._CHECKS drifted from garden_exclusions.ALL_CHECK_NAMES"
)
_TIER = {
    "broken_up": "integrity", "dead_link": "integrity",
    "unparented": "structure", "orphan": "structure",
    "duplicate_stem": "advisory", "stale_moc": "advisory",
}
_TIERS = ("integrity", "structure", "advisory")

_DEFAULT_TOP_N = 15

# Compact column labels for the area table (fit a chat-width table).
_COL_LABEL = {
    "dead_link": "dead_link", "orphan": "orphan", "unparented": "unparented",
    "broken_up": "broken_up", "duplicate_stem": "duplicate", "stale_moc": "stale",
}


def _area_of(path: str) -> str:
    """First path segment as the AREA; a root-level note → '(root)'.

    A note with no folder ('Loose.md'), an empty path, or a leading slash
    ('/Calendar/…' — empty first segment) all yield '(root)' so a blank area
    cell never appears; only a real folder segment becomes an area.
    """
    p = (path or "").strip()
    if "/" in p:
        seg = p.split("/", 1)[0]
        return seg if seg else "(root)"
    return "(root)"


def aggregate_by_area(findings: list[dict], *, top_n: int = _DEFAULT_TOP_N) -> dict:
    """Group findings by AREA × CHECK. Returns rows (top_n, total DESC) + an
    explicit others summary so a huge vault stays readable without silent loss.

    Return shape:
      {
        "rows": [{"area", <check>: int, ..., "total": int}, ...],  # ≤ top_n
        "others_area_count": int,   # areas beyond the cap
        "others_total": int,        # findings in those areas
      }
    """
    per_area: dict[str, dict[str, int]] = {}
    for f in findings:
        area = _area_of((f.get("target") or {}).get("path", ""))
        check = f.get("check", "")
        bucket = per_area.setdefault(area, {c: 0 for c in _CHECKS})
        if check in bucket:
            bucket[check] += 1

    rows: list[dict] = []
    for area, counts in per_area.items():
        row = {"area": area, **counts, "total": sum(counts.values())}
        rows.append(row)
    # total DESC, then area ASC for a deterministic tie-break.
    rows.sort(key=lambda r: (-r["total"], r["area"]))

    kept = rows[:top_n]
    dropped = rows[top_n:]
    return {
        "rows": kept,
        "others_area_count": len(dropped),
        "others_total": sum(r["total"] for r in dropped),
    }


def _render_area_table(agg: dict, top_n: int) -> list[str]:
    header = ["area", *(_COL_LABEL[c] for c in _CHECKS), "total"]
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * len(header)) + "|",
    ]
    for row in agg["rows"]:
        cells = [row["area"], *(str(row[c]) for c in _CHECKS), str(row["total"])]
        lines.append("| " + " | ".join(cells) + " |")
    if agg["others_area_count"]:
        lines.append(
            f"| … {agg['others_area_count']} more areas | "
            + " | ".join([""] * len(_CHECKS))
            + f" | {agg['others_total']} |"
        )
    lines.append("")
    if agg["others_area_count"]:
        # Truncation actually happened — state the cap explicitly.
        lines.append(f"Showing the top {top_n} areas by finding count.")
    else:
        lines.append(f"Showing all {len(agg['rows'])} areas.")
    return lines


def _render_totals(doc: dict) -> list[str]:
    findings = doc.get("findings") or []
    per_check = {c: 0 for c in _CHECKS}
    per_tier = {t: 0 for t in _TIERS}
    for f in findings:
        check = f.get("check", "")
        if check in per_check:
            per_check[check] += 1
        tier = f.get("tier") or _TIER.get(check)
        if tier in per_tier:
            per_tier[tier] += 1

    lines = ["## Totals", ""]
    lines.append(f"Total findings: {len(findings)}")
    lines.append("")
    lines.append("By check:")
    for c in _CHECKS:
        lines.append(f"- {c}: {per_check[c]}")
    lines.append("")
    lines.append("By tier:")
    for t in _TIERS:
        lines.append(f"- {t}: {per_tier[t]}")
    lines.append("")

    skipped = doc.get("skipped_checks") or []
    if skipped:
        reason = doc.get("skipped_checks_reason") or "external tool unavailable"
        lines.append(f"**Checks not run:** {', '.join(skipped)} — {reason}")
        lines.append("")
    return lines


def _target_str(target: dict) -> str:
    return f"{target.get('type', '?')}:{target.get('value', '')}"


def _render_active_exclusions(exclusions: GardenExclusions | None, today: date) -> list[str]:
    lines = ["## Active exclusions", ""]
    rules = exclusions.active_rules(today) if exclusions else []
    if not rules:
        lines += ["none configured", ""]
        return lines
    for r in rules:
        checks = ", ".join(r["checks"]) if r["checks"] else "all"
        lines.append(f"- `{_target_str(r['target'])}` · {checks} · {r['mode']}")
    lines.append("")
    return lines


def _render_pushback(exclusions: GardenExclusions | None, today: date) -> list[str]:
    lines = ["## On pushback (temporary)", ""]
    rules = exclusions.pushback_rules(today) if exclusions else []
    if not rules:
        lines += ["none active", ""]
        return lines

    enriched = []
    for r in rules:
        until = date.fromisoformat(r["until"]) if r["until"] else None
        days = (until - today).days if until else None
        enriched.append((days, r, until))
    # soonest-expiring first; None (no until) sorts last.
    enriched.sort(key=lambda e: (e[0] is None, e[0] if e[0] is not None else 0))

    for days, r, until in enriched:
        checks = ", ".join(r["checks"]) if r["checks"] else "all"
        until_s = until.isoformat() if until else "—"
        days_s = f"{days} days remaining" if days is not None else "no expiry"
        lines.append(f"- `{_target_str(r['target'])}` · {checks} · until {until_s} · {days_s}")
    lines.append("")
    return lines


def _render_reappeared(doc: dict) -> list[str]:
    lines = ["## Reappeared (expired)", ""]
    reappeared = doc.get("reappeared_exclusions") or []
    if not reappeared:
        lines += ["none", ""]
        return lines
    for r in reappeared:
        target = r.get("target") or {}
        checks_raw = r.get("checks")
        checks = ", ".join(checks_raw) if isinstance(checks_raw, list) else str(checks_raw)
        until = r.get("until", "?")
        lines.append(f"- `{_target_str(target)}` · {checks} · expired {until}")
    lines.append("")
    return lines


def render_stats(
    doc: dict,
    exclusions: GardenExclusions | None,
    *,
    effective_today: date,
    top_n: int = _DEFAULT_TOP_N,
) -> str:
    """Render the full read-only stats overview as a markdown string."""
    findings = doc.get("findings") or []
    parts: list[str] = []
    parts += ["## Open findings by area", ""]
    if findings:
        parts += _render_area_table(aggregate_by_area(findings, top_n=top_n), top_n)
    else:
        parts += ["No open findings.", ""]
    parts.append("")
    parts += _render_totals(doc)
    parts += _render_active_exclusions(exclusions, effective_today)
    parts += _render_pushback(exclusions, effective_today)
    parts += _render_reappeared(doc)
    return "\n".join(parts).rstrip() + "\n"


def run_stats(
    input_path: str,
    exclusions_path: str | None,
    *,
    explicit_exclusions: bool,
    effective_today: date,
    default_excl_path: str = _DEFAULT_EXCL_PATH,
    top_n: int = _DEFAULT_TOP_N,
) -> str:
    """Read doc + exclusions → the overview string. Raises FileNotFoundError when
    an EXPLICITLY-passed exclusions path is missing (a defaulted-absent path is a
    'none configured' section, not an error). Raises on an unreadable doc."""
    # An exclusions_path is only honoured when explicit_exclusions is True; a
    # caller passing a path with explicit_exclusions=False has an inconsistent
    # intent (the path would be silently ignored) — fail loudly.
    assert exclusions_path is None or explicit_exclusions, (
        "exclusions_path is set but explicit_exclusions=False — the path would be ignored"
    )
    with open(input_path, encoding="utf-8") as fh:
        doc = json.load(fh)

    excl_path = Path(exclusions_path) if explicit_exclusions else Path(default_excl_path)
    exclusions: GardenExclusions | None = None
    if not excl_path.is_file():
        if explicit_exclusions:
            raise FileNotFoundError(f"Exclusions file not found: {excl_path}")
        # defaulted-absent → render the "none configured" section (exclusions=None).
    else:
        exclusions = GardenExclusions.from_path(excl_path, today=effective_today)

    return render_stats(doc, exclusions, effective_today=effective_today, top_n=top_n)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Read-only garden-audit overview (open / excluded / pushback)."
    )
    p.add_argument(
        "--input", default=_DEFAULT_INPUT,
        help="Path to garden-audit-doc.json (the fresh scan output).",
    )
    p.add_argument(
        "--exclusions", default=None,
        help=f"Path to garden-audit-exclusions.yaml (default: {_DEFAULT_EXCL_PATH}, "
             f"'none configured' if absent).",
    )
    args = p.parse_args()

    try:
        overview = run_stats(
            args.input,
            args.exclusions,
            explicit_exclusions=args.exclusions is not None,
            effective_today=date.today(),
        )
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[error] garden-audit-stats: cannot read doc: {exc}", file=sys.stderr)
        return 1

    print(overview)
    return 0


if __name__ == "__main__":
    sys.exit(main())

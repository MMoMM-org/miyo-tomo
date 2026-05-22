#!/usr/bin/env python3
# version: 0.1.0
"""measure-inbox-phase-b-token-cost.py — per-item token report for /inbox Pass 1 Phase B fan-out.

Companion to measure-f47-token-cost.py (which covers Phase A discovery only).
Walks the subagents/ directory beside a Claude Code session JSONL, attributes
each `agent-*.jsonl` to an inbox item by matching the `stem = "..."` line in
the subagent's first user message, and tallies token usage per item.

Usage:
  # Latest session (auto-discovered)
  python3 scripts/measure-inbox-phase-b-token-cost.py --session-latest

  # Explicit session JSONL (subagents/ is found at <session>/<session-uuid>/subagents/)
  python3 scripts/measure-inbox-phase-b-token-cost.py \
    --session tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance/<uuid>.jsonl

  # Only include a specific Pass 1 run (default = the run_id of the newest subagent)
  python3 scripts/measure-inbox-phase-b-token-cost.py --session-latest --run-id 2026-05-22T14-28-40Z-df600a

  # Also tally the parent session JSONL (orchestrator overhead)
  python3 scripts/measure-inbox-phase-b-token-cost.py --session-latest --include-main

Pricing defaults to Claude Sonnet 4.6 list rates ($/M tokens):
  input 3.00, output 15.00, cache_create 3.75, cache_read 0.30
Override with --price-input/--price-output/--price-cache-write/--price-cache-read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

STEM_RE = re.compile(r'\bstem\s*=\s*"([^"]+)"')
RUN_ID_RE = re.compile(r'\brun_id\s*=\s*"([^"]+)"')

DEFAULT_PRICE = {
    "input": 3.00,
    "output": 15.00,
    "cache_create": 3.75,
    "cache_read": 0.30,
}


def iter_text_payloads(rec: dict):
    """Yield every string payload reachable from a Claude Code transcript record."""
    msg = rec.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for c in content:
            if not isinstance(c, dict):
                continue
            for k in ("text", "content", "input", "output"):
                v = c.get(k)
                if isinstance(v, str):
                    yield v


def extract_metadata(jsonl_path: Path) -> tuple[str | None, str | None, str | None]:
    """Return (stem, run_id, model) for a subagent transcript.

    stem + run_id come from the first user message (the dispatch prompt
    from the orchestrator); model is the first non-empty `message.model`
    seen on any assistant record.
    """
    stem = run_id = model = None
    with jsonl_path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") == "user" and (stem is None or run_id is None):
                for txt in iter_text_payloads(rec):
                    if stem is None:
                        m = STEM_RE.search(txt)
                        if m:
                            stem = m.group(1)
                    if run_id is None:
                        m = RUN_ID_RE.search(txt)
                        if m:
                            run_id = m.group(1)
                    if stem and run_id:
                        break
            if model is None:
                m = (rec.get("message") or {}).get("model")
                if m:
                    model = m
            if stem and run_id and model:
                break
    return stem, run_id, model


def tally_usage(jsonl_path: Path) -> dict:
    """Sum input/output/cache_create/cache_read tokens across every usage record."""
    totals = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0, "messages": 0}
    with jsonl_path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            u = (rec.get("message") or {}).get("usage") or {}
            if not u:
                continue
            totals["input"] += u.get("input_tokens", 0)
            totals["output"] += u.get("output_tokens", 0)
            totals["cache_create"] += u.get("cache_creation_input_tokens", 0)
            totals["cache_read"] += u.get("cache_read_input_tokens", 0)
            totals["messages"] += 1
    return totals


def latest_session_jsonl() -> Path | None:
    """Most recently modified host-side session JSONL for tomo-instance."""
    proj_dir = Path("tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance")
    if not proj_dir.is_dir():
        return None
    files = sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def subagents_dir_for(session_jsonl: Path) -> Path:
    return session_jsonl.parent / session_jsonl.stem / "subagents"


def estimate_cost(t: dict, price: dict) -> float:
    return (
        t["input"] * price["input"]
        + t["output"] * price["output"]
        + t["cache_create"] * price["cache_create"]
        + t["cache_read"] * price["cache_read"]
    ) / 1_000_000


def billable(t: dict) -> int:
    return t["input"] + t["output"] + t["cache_create"]


def report(
    session_jsonl: Path,
    run_id_filter: str | None,
    include_main: bool,
    price: dict,
) -> int:
    sub_dir = subagents_dir_for(session_jsonl)
    if not sub_dir.is_dir():
        print(f"No subagents/ directory found beside {session_jsonl}", file=sys.stderr)
        print(f"  expected: {sub_dir}", file=sys.stderr)
        return 1

    rows = []
    models_seen = set()
    run_ids_seen = defaultdict(int)
    for f in sorted(sub_dir.glob("agent-*.jsonl")):
        stem, rid, model = extract_metadata(f)
        if stem is None or rid is None:
            continue
        run_ids_seen[rid] += 1
        if model:
            models_seen.add(model)
        rows.append((f.name, stem, rid, model, tally_usage(f)))

    if not rows:
        print(f"No inbox-analyst subagent transcripts found in {sub_dir}", file=sys.stderr)
        print("(stem/run_id markers absent — was this session's /inbox actually run?)", file=sys.stderr)
        return 1

    if run_id_filter is None:
        # Default to the most common run_id (the latest run is usually the dominant one)
        run_id_filter = max(run_ids_seen.items(), key=lambda kv: kv[1])[0]

    filtered = [r for r in rows if r[2] == run_id_filter]
    if not filtered:
        print(f"No subagents matched run_id={run_id_filter}", file=sys.stderr)
        print(f"  available run_ids: {dict(run_ids_seen)}", file=sys.stderr)
        return 1

    # Header
    print(f"Phase B Token Report — run {run_id_filter}")
    print(f"Session: {session_jsonl.name}")
    if models_seen:
        print(f"Model(s): {', '.join(sorted(models_seen))}")
    print(f"Subagents matched: {len(filtered)}")
    if len(run_ids_seen) > 1:
        other = {k: v for k, v in run_ids_seen.items() if k != run_id_filter}
        print(f"  (other run_ids skipped: {other})")
    print()

    # Per-item table (sorted by billable desc)
    filtered.sort(key=lambda r: billable(r[4]), reverse=True)
    print(
        f"  {'#':>2}  {'stem':<48}  {'in':>5} {'out':>6} {'cache_w':>9} {'cache_r':>10} {'billable':>9}  {'$cost':>7}"
    )
    print(f"  {'-'*2}  {'-'*48}  {'-'*5} {'-'*6} {'-'*9} {'-'*10} {'-'*9}  {'-'*7}")
    sums = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}
    for idx, (_, stem, _, _, t) in enumerate(filtered, 1):
        bill = billable(t)
        cost = estimate_cost(t, price)
        for k in sums:
            sums[k] += t[k]
        stem_disp = stem if len(stem) <= 48 else stem[:45] + "..."
        print(
            f"  {idx:>2}  {stem_disp:<48}  {t['input']:>5,} {t['output']:>6,} "
            f"{t['cache_create']:>9,} {t['cache_read']:>10,} {bill:>9,}  ${cost:>6.3f}"
        )

    n = len(filtered)
    total = {**sums}
    avg = {k: v // n for k, v in sums.items()}
    print(f"  {'-'*2}  {'-'*48}  {'-'*5} {'-'*6} {'-'*9} {'-'*10} {'-'*9}  {'-'*7}")
    print(
        f"  {'':>2}  {'Average':<48}  {avg['input']:>5,} {avg['output']:>6,} "
        f"{avg['cache_create']:>9,} {avg['cache_read']:>10,} {billable(avg):>9,}  "
        f"${estimate_cost(avg, price):>6.3f}"
    )
    print(
        f"  {'':>2}  {'Total (subagents)':<48}  {total['input']:>5,} {total['output']:>6,} "
        f"{total['cache_create']:>9,} {total['cache_read']:>10,} {billable(total):>9,}  "
        f"${estimate_cost(total, price):>6.2f}"
    )

    if include_main:
        # Tally the parent session JSONL (orchestrator overhead)
        main = tally_usage(session_jsonl)
        print()
        print("Main orchestrator (parent session JSONL):")
        print(
            f"  input={main['input']:,}  output={main['output']:,}  "
            f"cache_create={main['cache_create']:,}  cache_read={main['cache_read']:,}"
        )
        print(
            f"  billable={billable(main):,}  cost=${estimate_cost(main, price):.2f}"
        )
        combined_billable = billable(total) + billable(main)
        combined_cost = estimate_cost(total, price) + estimate_cost(main, price)
        print()
        print(
            f"Grand total (main + {n} subagents): "
            f"billable={combined_billable:,}  cost=${combined_cost:.2f}"
        )

    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Per-item token report for /inbox Pass 1 Phase B fan-out."
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--session", help="Path to a Claude Code session JSONL")
    src.add_argument(
        "--session-latest",
        action="store_true",
        help="Auto-discover the most recent session JSONL for tomo-instance",
    )
    p.add_argument("--run-id", help="Filter to one Pass 1 run_id (default: most common)")
    p.add_argument(
        "--include-main",
        action="store_true",
        help="Also tally the parent session JSONL (orchestrator overhead)",
    )
    p.add_argument("--price-input", type=float, default=DEFAULT_PRICE["input"])
    p.add_argument("--price-output", type=float, default=DEFAULT_PRICE["output"])
    p.add_argument("--price-cache-write", type=float, default=DEFAULT_PRICE["cache_create"])
    p.add_argument("--price-cache-read", type=float, default=DEFAULT_PRICE["cache_read"])
    args = p.parse_args()

    if args.session:
        session_jsonl = Path(args.session)
        if not session_jsonl.is_file():
            print(f"Not a file: {session_jsonl}", file=sys.stderr)
            return 1
    else:
        session_jsonl = latest_session_jsonl()
        if not session_jsonl:
            print("No session JSONL found under tomo-home/.claude/projects/", file=sys.stderr)
            return 1
        print(f"Using latest session: {session_jsonl.name}", file=sys.stderr)

    price = {
        "input": args.price_input,
        "output": args.price_output,
        "cache_create": args.price_cache_write,
        "cache_read": args.price_cache_read,
    }
    return report(session_jsonl, args.run_id, args.include_main, price)


if __name__ == "__main__":
    sys.exit(main())

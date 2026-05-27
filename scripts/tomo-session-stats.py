#!/usr/bin/env python3
# tomo-session-stats.py — Token usage and cost report for a Tomo session.
# version: 0.1.0
"""
Reports turns, token breakdown (input/cache_read/cache_create/output),
peak single-turn context, model usage, subagent stats, and estimated cost.

Usage:
  python3 scripts/tomo-session-stats.py --session-latest
  python3 scripts/tomo-session-stats.py --session <path-to-session.jsonl>

Pricing defaults to Claude Sonnet 4.6 list rates ($/M tokens).
Override with --price-input, --price-output, --price-cache-write, --price-cache-read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_PRICE = {
    "input": 3.00,
    "output": 15.00,
    "cache_create": 3.75,
    "cache_read": 0.30,
}


def latest_session_jsonl() -> Path | None:
    proj_dir = Path("tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance")
    if not proj_dir.is_dir():
        return None
    files = sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def collect_stats(jsonl_path: Path) -> dict:
    total_in = 0
    total_out = 0
    total_cc = 0
    total_cr = 0
    turns = 0
    models: set[str] = set()
    peak = 0

    for line in jsonl_path.open():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") != "assistant":
            continue
        msg = rec.get("message", {})
        u = msg.get("usage", {})
        if not u:
            continue
        turns += 1
        inp = u.get("input_tokens", 0)
        out = u.get("output_tokens", 0)
        cc = u.get("cache_creation_input_tokens", 0)
        cr = u.get("cache_read_input_tokens", 0)
        total_in += inp
        total_out += out
        total_cc += cc
        total_cr += cr
        ctx = inp + cr
        if ctx > peak:
            peak = ctx
        m = msg.get("model", "")
        if m:
            models.add(m)

    return {
        "turns": turns,
        "models": sorted(models),
        "input": total_in,
        "cache_read": total_cr,
        "cache_create": total_cc,
        "output": total_out,
        "context": total_in + total_cr,
        "peak": peak,
    }


def estimate_cost(stats: dict, price: dict) -> float:
    return (
        stats["input"] * price["input"]
        + stats["output"] * price["output"]
        + stats["cache_create"] * price["cache_create"]
        + stats["cache_read"] * price["cache_read"]
    ) / 1_000_000


def print_stats(label: str, stats: dict, cost: float) -> None:
    print(f"  Turns:            {stats['turns']}")
    if stats["models"]:
        print(f"  Models:           {', '.join(stats['models'])}")
    print(f"  Input tokens:     {stats['input']:>12,}")
    print(f"  Cache read:       {stats['cache_read']:>12,}")
    print(f"  Cache create:     {stats['cache_create']:>12,}")
    print(f"  Output tokens:    {stats['output']:>12,}")
    print(f"  Total context:    {stats['context']:>12,}  (input + cache_read)")
    if stats["peak"] > 0:
        print(f"  Peak single turn: {stats['peak']:>12,}")
    print(f"  Est. cost:        ${cost:>10.2f}")


def main() -> int:
    p = argparse.ArgumentParser(description="Token usage and cost report for a Tomo session.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--session", help="Path to a Claude Code session JSONL")
    src.add_argument("--session-latest", action="store_true",
                     help="Auto-discover the most recent session JSONL for tomo-instance")
    p.add_argument("--price-input", type=float, default=DEFAULT_PRICE["input"])
    p.add_argument("--price-output", type=float, default=DEFAULT_PRICE["output"])
    p.add_argument("--price-cache-write", type=float, default=DEFAULT_PRICE["cache_create"])
    p.add_argument("--price-cache-read", type=float, default=DEFAULT_PRICE["cache_read"])
    args = p.parse_args()

    if args.session:
        session_path = Path(args.session)
        if not session_path.is_file():
            print(f"Not a file: {session_path}", file=sys.stderr)
            return 1
    else:
        session_path = latest_session_jsonl()
        if not session_path:
            print("No session JSONL found under tomo-home/.claude/projects/", file=sys.stderr)
            return 1
        print(f"Using: {session_path.name}", file=sys.stderr)

    price = {
        "input": args.price_input,
        "output": args.price_output,
        "cache_create": args.price_cache_write,
        "cache_read": args.price_cache_read,
    }

    main_stats = collect_stats(session_path)
    if main_stats["turns"] == 0:
        print("No LLM turns found in session.", file=sys.stderr)
        return 1

    main_cost = estimate_cost(main_stats, price)

    print("\n=== Main session ===")
    print_stats("Main", main_stats, main_cost)

    sub_dir = session_path.parent / session_path.stem / "subagents"
    grand_cost = main_cost

    if sub_dir.is_dir():
        subs = sorted(sub_dir.glob("agent-*.jsonl"))
        if subs:
            print(f"\n=== Subagents ({len(subs)}) ===")
            sub_agg = {"turns": 0, "models": set(), "input": 0, "cache_read": 0,
                       "cache_create": 0, "output": 0, "context": 0, "peak": 0}
            for sp in subs:
                s = collect_stats(sp)
                for k in ("turns", "input", "cache_read", "cache_create", "output", "context"):
                    sub_agg[k] += s[k]
                sub_agg["models"].update(s["models"])
                if s["peak"] > sub_agg["peak"]:
                    sub_agg["peak"] = s["peak"]
            sub_agg["models"] = sorted(sub_agg["models"])
            sub_cost = estimate_cost(sub_agg, price)
            print_stats("Subagents", sub_agg, sub_cost)
            grand_cost += sub_cost

    print("\n=== Total ===")
    print(f"  Grand total cost: ${grand_cost:>10.2f}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

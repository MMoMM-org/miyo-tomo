#!/usr/bin/env python3
# tomo-session-stats.py — Token usage and cost report for a Tomo session.
# version: 0.2.0
"""
Reports turns, token breakdown (input/cache_read/cache_create/output),
peak single-turn context, model usage, subagent stats, and estimated cost,
plus a per-step block: the main session and each subagent (labelled by the
``agentType`` of its ``.meta.json``) with cost, wall time (first to last
transcript timestamp) and peak context. Counts only, never message text.

One API reply is written as one transcript line per content block (thinking, text, each tool_use),
and every line repeats the reply's ``message.id`` and ``usage``. Each id is counted once; a line
without an id counts as its own reply. Summing per line overstated cost about 2× (#262).

Usage:
  python3 scripts/tomo-session-stats.py --session-latest
  python3 scripts/tomo-session-stats.py --session <path-to-session.jsonl>

Each reply is priced at its model family's rate from the PRICE table of
scripts/tomo-token-usage.py (single source). A model outside that table is
priced at the default rate (Sonnet list rates, $/M tokens) and the report says so;
override the default with --price-input, --price-output, --price-cache-write,
--price-cache-read.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path


def _load_token_usage():
    path = Path(__file__).resolve().parent / "tomo-token-usage.py"
    spec = importlib.util.spec_from_file_location("tomo_token_usage", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_TOKEN_USAGE = _load_token_usage()
PRICE = _TOKEN_USAGE.PRICE
model_family = _TOKEN_USAGE.model_family

_PRICE_KEYS = {"input": "in", "output": "out", "cache_create": "cache_w", "cache_read": "cache_r"}
DEFAULT_PRICE = {key: PRICE["sonnet"][short] for key, short in _PRICE_KEYS.items()}


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
    seen_ids: set[str] = set()
    by_model: dict[str, dict] = {}
    first_ts: datetime | None = None
    last_ts: datetime | None = None

    for line in jsonl_path.open():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _TOKEN_USAGE.parse_ts(rec.get("timestamp"))
        if ts is not None:
            first_ts = ts if first_ts is None or ts < first_ts else first_ts
            last_ts = ts if last_ts is None or ts > last_ts else last_ts
        if rec.get("type") != "assistant":
            continue
        msg = rec.get("message", {})
        u = msg.get("usage", {})
        if not u:
            continue
        msg_id = msg.get("id")
        if msg_id:
            if msg_id in seen_ids:
                continue  # another content block of a reply already counted
            seen_ids.add(msg_id)
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
        bucket = by_model.setdefault(m or "unknown", _zero_tokens())
        for key, value in (("input", inp), ("output", out), ("cache_create", cc), ("cache_read", cr)):
            bucket[key] += value

    return {
        "turns": turns,
        "models": sorted(models),
        "input": total_in,
        "cache_read": total_cr,
        "cache_create": total_cc,
        "output": total_out,
        "context": total_in + total_cr,
        "peak": peak,
        "by_model": by_model,
        "seconds": (last_ts - first_ts).total_seconds() if first_ts and last_ts else 0.0,
    }


def _zero_tokens() -> dict:
    return {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}


def _flat_cost(tokens: dict, price: dict) -> float:
    return (
        tokens["input"] * price["input"]
        + tokens["output"] * price["output"]
        + tokens["cache_create"] * price["cache_create"]
        + tokens["cache_read"] * price["cache_read"]
    ) / 1_000_000


def model_price(model: str, default: dict) -> tuple[dict, bool]:
    """Return (rates, is_default) for a model id, mapped by family onto PRICE."""
    rates = PRICE.get(model_family(model))
    if rates is None:
        return default, True
    return {key: rates[short] for key, short in _PRICE_KEYS.items()}, False


def estimate_cost(stats: dict, default: dict) -> tuple[float, list[str]]:
    """Cost at per-model rates; returns the cost and the model ids priced at the default rate."""
    cost = 0.0
    defaulted = []
    for model, tokens in stats["by_model"].items():
        price, is_default = model_price(model, default)
        if is_default and any(tokens.values()):
            defaulted.append(model)
        cost += _flat_cost(tokens, price)
    return cost, sorted(defaulted)


def step_label(transcript: Path) -> str:
    meta = transcript.with_suffix(".meta.json")
    try:
        agent_type = json.loads(meta.read_text(encoding="utf-8")).get("agentType")
    except (OSError, json.JSONDecodeError, AttributeError):
        agent_type = None
    return agent_type if isinstance(agent_type, str) and agent_type else transcript.stem


def print_step(label: str, stats: dict, cost: float, defaulted: list[str]) -> None:
    families = ",".join(sorted({model_family(m) for m in stats["by_model"]})) or "-"
    line = (f"  {label:<28} models={families} turns={stats['turns']} cost=${cost:.4f} "
            f"time={stats['seconds']:.0f}s peak={stats['peak']:,}")
    if defaulted:
        line += f"  (default price: {', '.join(defaulted)})"
    print(line)


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
    rate_help = "default $/M rate for a model outside the PRICE table (default: sonnet)"
    p.add_argument("--price-input", type=float, default=DEFAULT_PRICE["input"], help=rate_help)
    p.add_argument("--price-output", type=float, default=DEFAULT_PRICE["output"], help=rate_help)
    p.add_argument("--price-cache-write", type=float, default=DEFAULT_PRICE["cache_create"], help=rate_help)
    p.add_argument("--price-cache-read", type=float, default=DEFAULT_PRICE["cache_read"], help=rate_help)
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

    main_cost, main_defaulted = estimate_cost(main_stats, price)
    steps = [("main", main_stats, main_cost, main_defaulted)]

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
            sub_cost = 0.0
            for sp in subs:
                s = collect_stats(sp)
                for k in ("turns", "input", "cache_read", "cache_create", "output", "context"):
                    sub_agg[k] += s[k]
                sub_agg["models"].update(s["models"])
                if s["peak"] > sub_agg["peak"]:
                    sub_agg["peak"] = s["peak"]
                cost, defaulted = estimate_cost(s, price)
                sub_cost += cost
                steps.append((step_label(sp), s, cost, defaulted))
            sub_agg["models"] = sorted(sub_agg["models"])
            print_stats("Subagents", sub_agg, sub_cost)
            grand_cost += sub_cost

    print("\n=== Per step ===")
    for label, stats, cost, defaulted in steps:
        print_step(label, stats, cost, defaulted)

    print("\n=== Total ===")
    print(f"  Grand total cost: ${grand_cost:>10.2f}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

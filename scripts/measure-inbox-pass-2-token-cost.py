#!/usr/bin/env python3
# version: 0.1.0
"""measure-inbox-pass-2-token-cost.py — per-step token report for /inbox Pass 2.

Pass 2 (the instruction-builder workflow) runs mostly in the MAIN session
thread, with a single fan-out detour during Step 2.5 (FAN Resolve Subflow)
when the user ticked Force Atomic Note on daily-log-only items.

This tool reads the host-side Claude Code session JSONL, walks every
LLM turn, classifies it into one of instruction-builder's documented
steps via the tool-call pattern, and reports:

  - calls per step
  - cumulative context (input + cache_read) loaded
  - peak single-turn context
  - output tokens generated
  - cache writes (cache_create)
  - rough cost estimate at the model's list rates

Optionally also tallies fan-resolve subagents under <session>/<uuid>/subagents/.

Usage:
  # Latest session (auto-discovered)
  python3 scripts/measure-inbox-pass-2-token-cost.py --session-latest

  # Explicit session JSONL
  python3 scripts/measure-inbox-pass-2-token-cost.py \
    --session tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance/<uuid>.jsonl

  # Show turn-by-turn detail instead of (or in addition to) per-step aggregate
  python3 scripts/measure-inbox-pass-2-token-cost.py --session-latest --turns

  # Include the fan-resolve subagents' costs (when --session has a FAN subflow)
  python3 scripts/measure-inbox-pass-2-token-cost.py --session-latest --include-subagents

Pricing defaults to Claude Sonnet 4.6 list rates ($/M tokens):
  input 3.00, output 15.00, cache_create 3.75, cache_read 0.30
Override with --price-* flags.

Companion tools:
  scripts/measure-f47-token-cost.py            — Phase A discovery cost
  scripts/measure-inbox-phase-b-token-cost.py  — Phase B (Pass 1 fan-out) per-item
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_PRICE = {
    "input": 3.00,
    "output": 15.00,
    "cache_create": 3.75,
    "cache_read": 0.30,
}

# Step labels — keep in the order the instruction-builder agent runs them
# so the report reads top-to-bottom like the workflow.
STEP_ORDER = [
    "Step 0: load shared-ctx / context",
    "Step 1: load concepts.inbox / config",
    "Step 2: find suggestions doc (Kado)",
    "Step 2: ensure scratch dirs",
    "Step 2: cache primary suggestions",
    "Step 2: cache fan companion",
    "Step 2: run suggestion-parser",
    "Step 2: re-read parsed output",
    "Step 2.5: inspect parsed-suggestions",
    "Step 2.5: dispatch fan subagents",
    "Step 2.5: run suggestions-reducer (fan)",
    "Step 2.5: run suggestions-render (fan)",
    "Step 2.5: kado-write fan doc",
    "Step 3: run instruction-render",
    "Step 3: write rendered instruction notes",
    "Step 4: run instructions-diff",
    "Step 4: run instructions-dryrun",
    "Step 5: run state-promoter / state-update",
    "Step 6: kado-write instructions doc",
    "Step 7: final summary / one-line return",
    "(self-read agent / skill spec)",
    "(filesystem exploration)",
    "(tool schema lookup)",
    "(other — reasoning / unclassified)",
]

STEM_RE = re.compile(r'\bstem\s*=\s*"([^"]+)"')


def classify_step(tool: str, args_summary: str) -> str:
    """Map a single LLM turn's tool call into one of the workflow steps."""
    s = (tool + " " + args_summary).lower()

    # Script-name patterns from instruction-builder.md
    if "read-config-field" in s:                        return "Step 1: load concepts.inbox / config"
    if "shared-ctx" in s and "build" in s:              return "Step 0: load shared-ctx / context"
    if "shared-ctx" in s and ("read" in s or "cat" in s): return "Step 0: load shared-ctx / context"

    if "kado-search" in s and "suggestions" in s:       return "Step 2: find suggestions doc (Kado)"
    if "kado-search" in s and "fan" in s:               return "Step 2: find suggestions doc (Kado)"
    if "kado-search" in s:                              return "Step 2: find suggestions doc (Kado)"
    if "mkdir" in s and "tomo-tmp" in s:                return "Step 2: ensure scratch dirs"

    if "write" in s and "tomo-tmp/suggestions-fan" in s: return "Step 2: cache fan companion"
    if "write" in s and "tomo-tmp/suggestions" in s:    return "Step 2: cache primary suggestions"

    if "suggestion-parser" in s:                        return "Step 2: run suggestion-parser"
    if "read" in s and "parsed-suggestions" in s:       return "Step 2.5: inspect parsed-suggestions"
    if "read" in s and "tomo-tmp/suggestions" in s:     return "Step 2: re-read parsed output"

    # Step 2.5 fan subflow
    if "agent" in s and ("force_atomic" in s or "fan resolve" in s): return "Step 2.5: dispatch fan subagents"
    if "suggestions-reducer" in s and "fan-resolve" in s: return "Step 2.5: run suggestions-reducer (fan)"
    if "suggestions-render" in s and "fan" in s:        return "Step 2.5: run suggestions-render (fan)"
    if "kado-write" in s and "fan" in s:                return "Step 2.5: kado-write fan doc"

    # Step 3
    if "instruction-render" in s:                       return "Step 3: run instruction-render"
    if "kado-write" in s and "atomic" in s:             return "Step 3: write rendered instruction notes"

    # Step 4
    if "instructions-diff" in s:                        return "Step 4: run instructions-diff"
    if "instructions-dryrun" in s:                      return "Step 4: run instructions-dryrun"

    # Step 5
    if "state-promoter" in s or "state-update" in s:    return "Step 5: run state-promoter / state-update"

    # Step 6
    if "kado-write" in s and ("instruction" in s or "/inbox/" in s): return "Step 6: kado-write instructions doc"

    # Meta
    if "instruction-builder.md" in s or "inbox-orchestrator.md" in s or "/skills/" in s:
        return "(self-read agent / skill spec)"
    if "toolsearch" in s:                               return "(tool schema lookup)"
    if s.startswith("bash ls") or " ls " in s or "find ." in s or "find " in s:
        return "(filesystem exploration)"

    return "(other — reasoning / unclassified)"


def collect_turns(jsonl_path: Path) -> list[dict]:
    """Extract every assistant turn with a usage block from a session JSONL."""
    turns = []
    for line in jsonl_path.open():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") != "assistant":
            continue
        msg = rec.get("message") or {}
        u = msg.get("usage") or {}
        if not u:
            continue
        tool, args = "", ""
        for c in msg.get("content", []) or []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                tool = c.get("name", "")
                inp = c.get("input") or {}
                if tool == "Bash":
                    args = (inp.get("command") or "")[:120]
                elif tool in ("Read", "Write", "Edit"):
                    args = inp.get("file_path") or ""
                break
        step = classify_step(tool, args)
        turns.append({
            "ts": rec.get("timestamp", "")[11:19],
            "in": u.get("input_tokens", 0),
            "out": u.get("output_tokens", 0),
            "cc": u.get("cache_creation_input_tokens", 0),
            "cr": u.get("cache_read_input_tokens", 0),
            "tool": tool,
            "args": args[:80],
            "step": step,
            "model": msg.get("model", ""),
        })
    return turns


def latest_session_jsonl() -> Path | None:
    proj_dir = Path("tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance")
    if not proj_dir.is_dir():
        return None
    files = sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def estimate_cost(in_t: int, out_t: int, cc: int, cr: int, price: dict) -> float:
    return (
        in_t * price["input"]
        + out_t * price["output"]
        + cc * price["cache_create"]
        + cr * price["cache_read"]
    ) / 1_000_000


def aggregate_by_step(turns: list[dict]) -> dict:
    """Returns {step: {calls, ctx_total, ctx_peak, output, cache_write}}."""
    agg: dict = {}
    for t in turns:
        ctx = t["in"] + t["cr"]
        s = agg.setdefault(t["step"], {
            "calls": 0, "ctx_total": 0, "ctx_peak": 0,
            "output": 0, "cache_write": 0, "input": 0, "cache_read": 0,
        })
        s["calls"] += 1
        s["ctx_total"] += ctx
        if ctx > s["ctx_peak"]:
            s["ctx_peak"] = ctx
        s["output"] += t["out"]
        s["cache_write"] += t["cc"]
        s["input"] += t["in"]
        s["cache_read"] += t["cr"]
    return agg


def print_step_aggregate(agg: dict, price: dict) -> None:
    print(f"{'Step':<46} {'calls':>5} {'total_ctx':>11} {'peak_ctx':>10} {'output':>7} {'cache_w':>9} {'$cost':>7}")
    print("-" * 100)
    for step in STEP_ORDER:
        if step not in agg:
            continue
        s = agg[step]
        cost = estimate_cost(s["input"], s["output"], s["cache_write"], s["cache_read"], price)
        print(f"{step:<46} {s['calls']:>5} {s['ctx_total']:>11,} {s['ctx_peak']:>10,} "
              f"{s['output']:>7,} {s['cache_write']:>9,} ${cost:>6.3f}")
    # Catch any unexpected step labels (defensive — keep extractor changes from silently dropping rows)
    leftover = [k for k in agg.keys() if k not in STEP_ORDER]
    for step in leftover:
        s = agg[step]
        cost = estimate_cost(s["input"], s["output"], s["cache_write"], s["cache_read"], price)
        print(f"[unknown] {step:<37} {s['calls']:>5} {s['ctx_total']:>11,} {s['ctx_peak']:>10,} "
              f"{s['output']:>7,} {s['cache_write']:>9,} ${cost:>6.3f}")


def print_turn_detail(turns: list[dict]) -> None:
    print(f"{'#':>3} {'time':<10} {'ctx':>9} {'out':>6} {'cache_w':>9} {'step':<46} {'tool':<25}")
    print("-" * 115)
    for i, t in enumerate(turns, 1):
        ctx = t["in"] + t["cr"]
        toolshort = t["tool"]
        if t["args"]:
            toolshort = f"{t['tool']}:{t['args']}"[:25]
        print(f"{i:>3} {t['ts']:<10} {ctx:>9,} {t['out']:>6,} {t['cc']:>9,} {t['step']:<46} {toolshort:<25}")


def find_fan_subagents(session_path: Path) -> list[Path]:
    sub_dir = session_path.parent / session_path.stem / "subagents"
    if not sub_dir.is_dir():
        return []
    return sorted(sub_dir.glob("agent-*.jsonl"))


def main() -> int:
    p = argparse.ArgumentParser(
        description="Per-step token report for /inbox Pass 2 (instruction-builder)."
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--session", help="Path to a Claude Code session JSONL")
    src.add_argument("--session-latest", action="store_true",
                     help="Auto-discover the most recent session JSONL for tomo-instance")
    p.add_argument("--turns", action="store_true",
                   help="Show turn-by-turn detail instead of (or after) step aggregate")
    p.add_argument("--include-subagents", action="store_true",
                   help="Also tally Step-2.5 fan-resolve subagents")
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
        print(f"Using latest session: {session_path.name}", file=sys.stderr)

    price = {
        "input": args.price_input,
        "output": args.price_output,
        "cache_create": args.price_cache_write,
        "cache_read": args.price_cache_read,
    }

    main_turns = collect_turns(session_path)
    if not main_turns:
        print("No LLM turns found in session.", file=sys.stderr)
        return 1

    models = sorted({t["model"] for t in main_turns if t["model"]})
    if models:
        print(f"Model(s): {', '.join(models)}")
    print(f"Main-session LLM turns: {len(main_turns)}")
    print()

    if args.turns:
        print_turn_detail(main_turns)
        print()

    agg = aggregate_by_step(main_turns)
    print("=== Per-step aggregate (main session) ===")
    print_step_aggregate(agg, price)

    # Main session totals
    total_in = sum(t["in"] for t in main_turns)
    total_out = sum(t["out"] for t in main_turns)
    total_cc = sum(t["cc"] for t in main_turns)
    total_cr = sum(t["cr"] for t in main_turns)
    total_ctx = total_in + total_cr
    peak_ctx = max((t["in"] + t["cr"]) for t in main_turns)
    main_cost = estimate_cost(total_in, total_out, total_cc, total_cr, price)
    print()
    print(f"Main session totals:")
    print(f"  total context loaded:  {total_ctx:>10,}")
    print(f"  peak single-turn ctx:  {peak_ctx:>10,}")
    print(f"  total output:          {total_out:>10,}")
    print(f"  cache writes:          {total_cc:>10,}")
    print(f"  cache reads:           {total_cr:>10,}")
    print(f"  est. cost:             ${main_cost:>9.2f}")

    # Optional: include fan subagents
    if args.include_subagents:
        subs = find_fan_subagents(session_path)
        if not subs:
            print()
            print(f"(no fan-resolve subagents under {session_path.stem}/subagents/)")
        else:
            print()
            print(f"=== Fan-resolve subagents ({len(subs)}) ===")
            sub_total_in = sub_total_out = sub_total_cc = sub_total_cr = 0
            for f in subs:
                turns = collect_turns(f)
                stem = "?"
                # Try to find the stem from the dispatch prompt
                for line in f.open():
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("type") == "user":
                        msg = rec.get("message", {})
                        content = msg.get("content")
                        if isinstance(content, str):
                            m = STEM_RE.search(content)
                            if m:
                                stem = m.group(1); break
                        elif isinstance(content, list):
                            for c in content:
                                v = c.get("text") if isinstance(c, dict) else None
                                if isinstance(v, str):
                                    m = STEM_RE.search(v)
                                    if m:
                                        stem = m.group(1); break
                            if stem != "?": break
                in_t = sum(t["in"] for t in turns)
                out_t = sum(t["out"] for t in turns)
                cc = sum(t["cc"] for t in turns)
                cr = sum(t["cr"] for t in turns)
                ctx = in_t + cr
                peak = max((t["in"] + t["cr"]) for t in turns) if turns else 0
                cost = estimate_cost(in_t, out_t, cc, cr, price)
                print(f"  {f.name[:25]}  stem={stem!r:35s} turns={len(turns)} ctx={ctx:>9,} peak={peak:>9,} out={out_t:>6,} ${cost:>5.2f}")
                sub_total_in += in_t
                sub_total_out += out_t
                sub_total_cc += cc
                sub_total_cr += cr
            sub_cost = estimate_cost(sub_total_in, sub_total_out, sub_total_cc, sub_total_cr, price)
            print()
            print(f"Subagent totals:")
            print(f"  total context loaded:  {sub_total_in + sub_total_cr:>10,}")
            print(f"  total output:          {sub_total_out:>10,}")
            print(f"  est. cost:             ${sub_cost:>9.2f}")
            print()
            print(f"Grand total (main + subagents): ${main_cost + sub_cost:.2f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

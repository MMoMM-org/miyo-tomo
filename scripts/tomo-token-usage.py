#!/usr/bin/env python3
"""Aggregate Claude Code token usage for the Tomo project.

Scans both host dev sessions and Docker container sessions, sums input/output/
cache tokens per model, and reports totals (with approximate cost as scale ref).

Usage:
    python3 scripts/tomo-token-usage.py                   # all time, exclude current
    python3 scripts/tomo-token-usage.py --since 2026-04-15
    python3 scripts/tomo-token-usage.py --include-current
    python3 scripts/tomo-token-usage.py --by-session      # per-session breakdown
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HOST_DIR = Path("/Users/marcus/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo")
DOCKER_DIR = Path("/Volumes/Moon/Coding/MiYo/Tomo/tomo-home/.claude/projects")

# Approx published rates per 1M tokens (USD). Max-plan users pay flat subscription;
# these numbers are only a scale reference, not a billing truth.
PRICE = {
    "opus":   {"in": 15.00, "out": 75.00, "cache_w": 18.75, "cache_r": 1.50},
    "sonnet": {"in":  3.00, "out": 15.00, "cache_w":  3.75, "cache_r": 0.30},
    "haiku":  {"in":  0.80, "out":  4.00, "cache_w":  1.00, "cache_r": 0.08},
}


def model_family(model: str) -> str:
    m = (model or "").lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return "other"


def newest_jsonl(d: Path) -> Path | None:
    files = [p for p in d.glob("*.jsonl") if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def iter_usage(jsonl: Path):
    """Yield (timestamp, model, usage_dict) for every assistant message."""
    with jsonl.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage") or {}
            if not usage:
                continue
            model = msg.get("model") or rec.get("model") or "unknown"
            ts = rec.get("timestamp") or msg.get("created_at")
            yield ts, model, usage


def parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def sum_usage(jsonl: Path, since: datetime | None):
    totals = defaultdict(lambda: {"in": 0, "out": 0, "cache_w": 0, "cache_r": 0, "msgs": 0})
    for ts_raw, model, u in iter_usage(jsonl):
        if since is not None:
            dt = parse_ts(ts_raw)
            if dt is not None and dt < since:
                continue
        fam = model_family(model)
        totals[fam]["in"]      += u.get("input_tokens", 0) or 0
        totals[fam]["out"]     += u.get("output_tokens", 0) or 0
        totals[fam]["cache_w"] += u.get("cache_creation_input_tokens", 0) or 0
        totals[fam]["cache_r"] += u.get("cache_read_input_tokens", 0) or 0
        totals[fam]["msgs"]    += 1
    return totals


def cost_usd(fam: str, t: dict) -> float:
    p = PRICE.get(fam)
    if not p:
        return 0.0
    return (
        t["in"]      * p["in"]      / 1_000_000 +
        t["out"]     * p["out"]     / 1_000_000 +
        t["cache_w"] * p["cache_w"] / 1_000_000 +
        t["cache_r"] * p["cache_r"] / 1_000_000
    )


def fmt_int(n: int) -> str:
    return f"{n:>12,}"


def print_bucket(label: str, totals_by_fam: dict):
    if not totals_by_fam:
        print(f"  {label}: (no data)")
        return
    grand_cost = 0.0
    grand_msgs = 0
    grand_in = grand_out = grand_cw = grand_cr = 0
    print(f"  {label}:")
    print(f"    {'model':<8} {'msgs':>6} {'input':>12} {'output':>12} {'cache-w':>12} {'cache-r':>12} {'~USD':>8}")
    for fam, t in sorted(totals_by_fam.items()):
        c = cost_usd(fam, t)
        grand_cost += c
        grand_msgs += t["msgs"]
        grand_in   += t["in"]
        grand_out  += t["out"]
        grand_cw   += t["cache_w"]
        grand_cr   += t["cache_r"]
        print(f"    {fam:<8} {t['msgs']:>6,} {fmt_int(t['in'])} {fmt_int(t['out'])} {fmt_int(t['cache_w'])} {fmt_int(t['cache_r'])} {c:>8.2f}")
    print(f"    {'TOTAL':<8} {grand_msgs:>6,} {fmt_int(grand_in)} {fmt_int(grand_out)} {fmt_int(grand_cw)} {fmt_int(grand_cr)} {grand_cost:>8.2f}")


def combine(a: dict, b: dict) -> dict:
    out = defaultdict(lambda: {"in": 0, "out": 0, "cache_w": 0, "cache_r": 0, "msgs": 0})
    for src in (a, b):
        for fam, t in src.items():
            for k, v in t.items():
                out[fam][k] += v
    return out


def run_single_session(session_id: str, since):
    """Report totals for a single Docker session: its main + subagent transcripts."""
    matches = list(DOCKER_DIR.rglob(f"{session_id}.jsonl"))
    main = next((m for m in matches if "/subagents/" not in str(m)), None)
    if not main:
        print(f"No main transcript found for session {session_id}")
        return
    sub_dir = main.parent / session_id / "subagents"
    subs = sorted(sub_dir.glob("agent-*.jsonl")) if sub_dir.exists() else []

    print(f"Tomo single-session usage: {session_id}")
    print(f"  Main transcript: {main.name}  ({main.stat().st_size/1024:.0f} KB, mtime {datetime.fromtimestamp(main.stat().st_mtime):%Y-%m-%d %H:%M})")
    print(f"  Subagent runs  : {len(subs)}")
    if since:
        print(f"  Filter: since {since.isoformat()}")
    print()

    main_totals = sum_usage(main, since)
    sub_totals = defaultdict(lambda: {"in": 0, "out": 0, "cache_w": 0, "cache_r": 0, "msgs": 0})
    for f in subs:
        t = sum_usage(f, since)
        for fam, v in t.items():
            for k, vv in v.items():
                sub_totals[fam][k] += vv

    print_bucket("Main session (top-level orchestrator + your commands)", main_totals)
    print()
    print_bucket("Subagents (fan-out classifiers / executors)", sub_totals)
    print()
    print_bucket("TOTAL for this session", combine(main_totals, sub_totals))

    if subs:
        print()
        print("Per-subagent breakdown (top 15 by output tokens):")
        rows = []
        for f in subs:
            t = sum_usage(f, since)
            out = sum(v["out"] for v in t.values())
            msgs = sum(v["msgs"] for v in t.values())
            cost = sum(cost_usd(fam, v) for fam, v in t.items())
            models = ",".join(sorted(t.keys())) or "-"
            rows.append((out, msgs, cost, f.stem, models))
        rows.sort(reverse=True)
        print(f"  {'output':>8} {'msgs':>5} {'USD':>7}  {'agent-id':<25} models")
        for out, msgs, cost, sid, models in rows[:15]:
            print(f"  {out:>8,} {msgs:>5,} {cost:>7.2f}  {sid:<25} {models}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="ISO date, e.g. 2026-04-15 — only count messages after this")
    ap.add_argument("--include-current", action="store_true", help="include the current host session")
    ap.add_argument("--by-session", action="store_true", help="per-session breakdown (top 20 by cost)")
    ap.add_argument("--session", help="restrict to one Docker session-id (its main transcript + subagents)")
    ap.add_argument("--last-pass1", action="store_true", help="shortcut: most recent Docker session with subagents (typical /inbox Pass 1 run)")
    args = ap.parse_args()

    since = None
    if args.since:
        since = datetime.fromisoformat(args.since)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

    # Identify current session = most recently modified host JSONL
    current = None
    if not args.include_current:
        current = newest_jsonl(HOST_DIR)

    # Single-session mode: short-circuit the full aggregation
    session_id = args.session
    if args.last_pass1 and not session_id:
        # Pick the most recently modified main .jsonl whose subagents/ dir is non-empty.
        candidates = []
        for sub in DOCKER_DIR.iterdir() if DOCKER_DIR.exists() else []:
            if sub.is_dir():
                for jf in sub.glob("*.jsonl"):
                    subdir = sub / jf.stem / "subagents"
                    if subdir.exists() and any(subdir.glob("agent-*.jsonl")):
                        candidates.append((jf.stat().st_mtime, jf))
        if candidates:
            candidates.sort(reverse=True)
            session_id = candidates[0][1].stem
    if session_id:
        run_single_session(session_id, since)
        return

    host_files = sorted(p for p in HOST_DIR.glob("*.jsonl") if p.is_file() and p != current) if HOST_DIR.exists() else []
    # Docker: main-session .jsonl at top level + subagents/agent-*.jsonl nested
    docker_files = sorted(DOCKER_DIR.rglob("*.jsonl")) if DOCKER_DIR.exists() else []
    docker_main = [f for f in docker_files if "/subagents/" not in str(f)]
    docker_sub = [f for f in docker_files if "/subagents/" in str(f)]

    print(f"Tomo token usage — aggregated {datetime.now():%Y-%m-%d %H:%M}")
    if since:
        print(f"  Filter: since {since.isoformat()}")
    if current:
        print(f"  Excluded current session: {current.name}")
    print(f"  Host-dev transcripts : {len(host_files)}")
    print(f"  Docker main sessions : {len(docker_main)}")
    print(f"  Docker subagent runs : {len(docker_sub)}")
    print()

    host_totals = defaultdict(lambda: {"in": 0, "out": 0, "cache_w": 0, "cache_r": 0, "msgs": 0})
    per_session = []
    for f in host_files:
        t = sum_usage(f, since)
        per_session.append(("host", f.stem, t))
        for fam, v in t.items():
            for k, vv in v.items():
                host_totals[fam][k] += vv

    docker_main_totals = defaultdict(lambda: {"in": 0, "out": 0, "cache_w": 0, "cache_r": 0, "msgs": 0})
    for f in docker_main:
        t = sum_usage(f, since)
        per_session.append(("docker-main", f.stem, t))
        for fam, v in t.items():
            for k, vv in v.items():
                docker_main_totals[fam][k] += vv

    docker_sub_totals = defaultdict(lambda: {"in": 0, "out": 0, "cache_w": 0, "cache_r": 0, "msgs": 0})
    for f in docker_sub:
        t = sum_usage(f, since)
        per_session.append(("docker-sub", f.stem, t))
        for fam, v in t.items():
            for k, vv in v.items():
                docker_sub_totals[fam][k] += vv

    docker_totals = combine(docker_main_totals, docker_sub_totals)

    print_bucket("Host (dev work — coding, specs, reviews)", host_totals)
    print()
    print_bucket("Docker main sessions (top-level conversation)", docker_main_totals)
    print()
    print_bucket("Docker subagent runs (orchestrator fan-out)", docker_sub_totals)
    print()
    print_bucket("Docker total (Tomo runtime: /inbox, /explore-vault, …)", docker_totals)
    print()
    print_bucket("COMBINED", combine(host_totals, docker_totals))

    if args.by_session:
        print()
        print("Top 20 sessions by cost:")
        scored = []
        for kind, sid, t in per_session:
            c = sum(cost_usd(fam, v) for fam, v in t.items())
            msgs = sum(v["msgs"] for v in t.values())
            if msgs:
                scored.append((c, kind, sid[:8], msgs))
        scored.sort(reverse=True)
        print(f"  {'USD':>8}  {'kind':<7} {'sid':<10} {'msgs':>6}")
        for c, kind, sid, msgs in scored[:20]:
            print(f"  {c:>8.2f}  {kind:<7} {sid:<10} {msgs:>6,}")


if __name__ == "__main__":
    main()

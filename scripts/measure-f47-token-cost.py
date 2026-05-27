#!/usr/bin/env python3
# version: 0.1.0
"""measure-f47-token-cost.py — F-47 T6.3 token-cost measurement.

Parses a stderr trace (or session JSONL) for `[inbox-discovery] lifecycle.discovery`
events emitted by inbox-discovery.py (v0.3.0+) and aggregates the `token_estimate`
property against PRD §7 budgets:

  - Scenario A (steady):  ≤ 2,000 tokens
  - Scenario B (heavy):   ≤ 6,000 tokens

Usage:
  # From a captured stderr trace
  python3 scripts/measure-f47-token-cost.py --stderr /tmp/F47-P5-token-steady.log

  # From the latest session JSONL transcript (auto-discovered)
  python3 scripts/measure-f47-token-cost.py --session-latest

  # Explicitly point at a session jsonl
  python3 scripts/measure-f47-token-cost.py --session tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance/<uuid>.jsonl

  # Explicit scenario budget (defaults to auto-detect from hit count)
  python3 scripts/measure-f47-token-cost.py --stderr trace.log --scenario heavy

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/plan/phase-6.md T6.3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PRD_BUDGETS = {
    "steady": 2_000,
    "heavy": 6_000,
}

# Match the JSON payload of an inbox-discovery lifecycle event.
EVENT_RE = re.compile(r"\[inbox-discovery\]\s+(\{.*?\})\s*$")


def find_events_in_text(text: str) -> list[dict]:
    """Extract all lifecycle.discovery events from a text blob (multi-line)."""
    events = []
    for line in text.splitlines():
        m = EVENT_RE.search(line)
        if not m:
            continue
        try:
            payload = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "lifecycle.discovery":
            events.append(payload)
    return events


def find_events_in_session(jsonl_path: Path) -> list[dict]:
    """Extract lifecycle.discovery events from a Claude Code session JSONL.

    Walks every tool_result / stderr capture in the transcript and runs the
    same regex match used for raw stderr traces.
    """
    events = []
    for line in jsonl_path.open():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Walk message.content[]; tool_result entries carry stderr in their string payload
        msg = rec.get("message", {})
        content = msg.get("content")
        if isinstance(content, str):
            events.extend(find_events_in_text(content))
        elif isinstance(content, list):
            for c in content:
                if not isinstance(c, dict):
                    continue
                # tool_use input or tool_result output may carry the stderr text
                for key in ("content", "text", "input", "output"):
                    v = c.get(key)
                    if isinstance(v, str):
                        events.extend(find_events_in_text(v))
                    elif isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict):
                                for inner_key in ("text", "content"):
                                    iv = item.get(inner_key)
                                    if isinstance(iv, str):
                                        events.extend(find_events_in_text(iv))
    return events


def latest_session_jsonl() -> Path | None:
    """Return the most recently modified Claude Code session JSONL for the
    tomo-instance project (host-side path)."""
    proj_dir = Path("tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance")
    if not proj_dir.is_dir():
        return None
    files = sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def classify_scenario(event: dict) -> str:
    """Heuristic: heavy if any pending* bucket has >=1 hit OR captured >=3, else steady."""
    bc = event.get("bucket_counts", {})
    if (
        bc.get("pendingApproval", 0) >= 1
        or bc.get("pendingAccept", 0) >= 1
        or bc.get("pendingApply", 0) >= 1
        or bc.get("captured", 0) >= 3
        or event.get("byFrontmatter_hits", 0) >= 3
    ):
        return "heavy"
    return "steady"


def report(events: list[dict], scenario_override: str | None) -> int:
    if not events:
        print("No lifecycle.discovery events found.", file=sys.stderr)
        print("Make sure inbox-discovery.py is at v0.3.0+ (emits structured event)", file=sys.stderr)
        return 1

    print(f"Found {len(events)} lifecycle.discovery event(s)\n")
    any_over = False
    for idx, ev in enumerate(events, 1):
        scenario = scenario_override or classify_scenario(ev)
        budget = PRD_BUDGETS[scenario]
        token_est = ev.get("token_estimate", 0)
        bc = ev.get("bucket_counts", {})

        status = "✅ PASS" if token_est <= budget else "❌ OVER BUDGET"
        if token_est > budget:
            any_over = True

        print(f"=== Event {idx} ({scenario} scenario, budget ≤ {budget:,}) ===")
        print(f"  run_id:               {ev.get('run_id')}")
        print(f"  token_estimate:       {token_est:>6,}  {status}")
        print(f"  byFrontmatter_hits:   {ev.get('byFrontmatter_hits'):>6}")
        print(f"  listDir_hits:         {ev.get('listDir_hits'):>6}")
        print(f"  pending_body_reads:   {ev.get('pending_body_reads'):>6}")
        print(f"  phase_a_duration_ms:  {ev.get('phase_a_duration_ms'):>6}")
        print(f"  bucket_counts:        pendingApproval={bc.get('pendingApproval',0)} "
              f"pendingAccept={bc.get('pendingAccept',0)} "
              f"pendingApply={bc.get('pendingApply',0)} "
              f"captured={bc.get('captured',0)} "
              f"newSources={bc.get('newSources',0)}")
        print(f"  drift_hint_emitted:   {ev.get('drift_hint_emitted')}")
        print()

    if any_over:
        print("❌ At least one event exceeded the PRD §7 budget — investigate.", file=sys.stderr)
        return 2
    print("✅ All events within PRD §7 budget.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="F-47 T6.3 token-cost measurement against PRD §7 budgets.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--stderr", help="Path to a captured stderr trace file")
    src.add_argument("--session", help="Path to a Claude Code session JSONL")
    src.add_argument("--session-latest", action="store_true",
                     help="Auto-discover the most recent session JSONL for tomo-instance")
    p.add_argument("--scenario", choices=("steady", "heavy"),
                   help="Override the auto-detected scenario classification")
    args = p.parse_args()

    if args.stderr:
        text = Path(args.stderr).read_text()
        events = find_events_in_text(text)
    elif args.session:
        events = find_events_in_session(Path(args.session))
    else:  # session-latest
        latest = latest_session_jsonl()
        if not latest:
            print("No session JSONL found under tomo-home/.claude/projects/", file=sys.stderr)
            return 1
        print(f"Using latest session: {latest.name}", file=sys.stderr)
        events = find_events_in_session(latest)

    return report(events, args.scenario)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# tomo-session-inspect.py — Inspect a Tomo session for pipeline compliance + errors.
# version: 0.1.0
"""
Shows the full call sequence, checks which pipeline steps ran vs were
skipped, lists errors, and inspects subagent dispatch format.

Usage:
  python3 scripts/tomo-session-inspect.py --session-latest
  python3 scripts/tomo-session-inspect.py --session <path.jsonl>
  python3 scripts/tomo-session-inspect.py --session-latest --errors-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def latest_session_jsonl() -> Path | None:
    proj_dir = Path("tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance")
    if not proj_dir.is_dir():
        return None
    files = sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def load_records(jsonl_path: Path) -> list[dict]:
    records = []
    for line in jsonl_path.open():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


def print_call_sequence(records: list[dict]) -> None:
    print("=== Call Sequence ===\n")
    turn = 0
    for rec in records:
        if rec.get("type") != "assistant":
            continue
        content = rec.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        turn += 1
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text":
                t = (c.get("text") or "").strip()
                if t:
                    print(f"T{turn:02d} [text]: {t[:180]}")
            elif c.get("type") == "tool_use":
                name = c.get("name", "")
                inp = c.get("input", {})
                if name == "Agent":
                    prompt = (inp.get("prompt") or "")[:80].replace("\n", " ")
                    bg = inp.get("run_in_background", False)
                    print(f"T{turn:02d} [Agent bg={bg}]: {prompt}...")
                elif name == "Bash":
                    print(f"T{turn:02d} [Bash]: {(inp.get('command') or '')[:120]}")
                elif name == "Read":
                    print(f"T{turn:02d} [Read]: ...{(inp.get('file_path') or '')[-55:]}")
                elif name == "Write":
                    print(f"T{turn:02d} [Write]: ...{(inp.get('file_path') or '')[-55:]}")
                elif name.startswith("mcp__kado"):
                    op = inp.get("operation", "")
                    path = inp.get("path", "")
                    print(f"T{turn:02d} [{name}] op={op} path={path}")
                else:
                    print(f"T{turn:02d} [{name}]: {str(inp)[:80]}")


def check_pipeline(records: list[dict]) -> None:
    print("\n=== Pipeline Compliance ===\n")
    scripts = [
        "shared-ctx-builder", "read-config-field", "run-id",
        "suggestions-reducer", "suggestions-render",
        "mark-captured", "state-promoter", "upload-rendered",
        "instructions-diff", "instructions-dryrun",
        "suggestion-parser", "instruction-render",
        "inbox-triage", "voice-precheck",
    ]
    found = set()
    for rec in records:
        if rec.get("type") != "assistant":
            continue
        for c in rec.get("message", {}).get("content", []):
            if not isinstance(c, dict) or c.get("type") != "tool_use":
                continue
            if c.get("name") == "Bash":
                cmd = c.get("input", {}).get("command", "")
                for s in scripts:
                    if s in cmd:
                        found.add(s)

    for s in scripts:
        if s in found:
            print(f"  [x] {s}")
    print()
    skipped = [s for s in scripts if s not in found]
    if skipped:
        print(f"  Not called: {', '.join(skipped)}")


def print_errors(records: list[dict], jsonl_path: Path) -> None:
    print("\n=== Errors (main session) ===\n")
    found_any = False
    for rec in records:
        if rec.get("type") == "tool_result" and rec.get("is_error"):
            content = rec.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        content = item.get("text", "")
                        break
            if isinstance(content, str) and content.strip():
                print(f"  {content[:200]}")
                found_any = True
    if not found_any:
        print("  (none)")

    sub_dir = jsonl_path.parent / jsonl_path.stem / "subagents"
    if sub_dir.is_dir():
        subs = sorted(sub_dir.glob("agent-*.jsonl"))
        print(f"\n=== Errors (subagents: {len(subs)}) ===\n")
        found_sub = False
        for sp in subs:
            for sline in sp.open():
                try:
                    srec = json.loads(sline)
                except json.JSONDecodeError:
                    continue
                if srec.get("type") == "tool_result" and srec.get("is_error"):
                    sc = srec.get("content", "")
                    if isinstance(sc, list):
                        for item in sc:
                            if isinstance(item, dict):
                                sc = item.get("text", "")
                                break
                    if isinstance(sc, str) and sc.strip():
                        print(f"  {sp.name}: {sc[:150]}")
                        found_sub = True
        if not found_sub:
            print("  (none)")


def print_subagent_summary(jsonl_path: Path) -> None:
    sub_dir = jsonl_path.parent / jsonl_path.stem / "subagents"
    if not sub_dir.is_dir():
        return
    subs = sorted(sub_dir.glob("agent-*.jsonl"))
    if not subs:
        return
    print(f"\n=== Subagents ({len(subs)}) ===\n")
    for sp in subs:
        lines = list(sp.open())
        assistant_count = sum(1 for ln in lines if '"assistant"' in ln)
        # Find agent name from first human message
        agent_name = "?"
        for sline in lines:
            try:
                srec = json.loads(sline)
            except json.JSONDecodeError:
                continue
            if srec.get("type") == "human":
                msg_content = srec.get("message", {}).get("content", "")
                if isinstance(msg_content, str):
                    agent_name = msg_content[:60].replace("\n", " ")
                elif isinstance(msg_content, list):
                    for item in msg_content:
                        if isinstance(item, dict) and item.get("text"):
                            agent_name = item["text"][:60].replace("\n", " ")
                            break
                break
        print(f"  {sp.name}: {assistant_count} turns — {agent_name}...")


def main() -> int:
    p = argparse.ArgumentParser(description="Inspect a Tomo session for compliance and errors.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--session", help="Path to session JSONL")
    src.add_argument("--session-latest", action="store_true")
    p.add_argument("--errors-only", action="store_true",
                   help="Only show errors, skip call sequence")
    args = p.parse_args()

    if args.session:
        sp = Path(args.session)
    else:
        sp = latest_session_jsonl()
        if not sp:
            print("No session found.", file=sys.stderr)
            return 1
        print(f"Using: {sp.name}", file=sys.stderr)

    records = load_records(sp)
    assistant_count = sum(1 for r in records if r.get("type") == "assistant")
    print(f"Session: {sp.name} ({len(records)} records, {assistant_count} assistant turns)\n")

    if not args.errors_only:
        print_call_sequence(records)
        check_pipeline(records)
        print_subagent_summary(sp)

    print_errors(records, sp)
    return 0


if __name__ == "__main__":
    sys.exit(main())

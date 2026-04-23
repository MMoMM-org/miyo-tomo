#!/usr/bin/env python3
# version: 0.2.0
"""instructions-dryrun.py — Validate an instructions.json is Tomo-Hashi-ready.

Reads an instructions.json file and prints a one-line summary of each action
that a future executor (Tomo Hashi / Seigyo F-01) would run. No Kado calls,
no vault writes — a pure parse + projection.

Used for XDD 008 Phase 3 T3.2: verify every action type is parseable and
contains the fields needed for machine execution.

Exit codes:
  0 — every action parsed and has all required fields
  1 — one or more actions missing required fields or using an unknown type
  2 — file not found / JSON parse error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_FIELDS_BY_KIND = {
    "move_note": {"id", "action", "source", "destination", "title"},
    "link_to_moc": {"id", "action", "target_moc", "line_to_add"},
    "update_tracker": {"id", "action", "daily_note_path", "date", "field", "value", "syntax"},
    "update_log_entry": {"id", "action", "daily_note_path", "date", "section", "position", "content"},
    "update_log_link": {"id", "action", "daily_note_path", "date", "section", "position", "target_stem"},
    "create_moc": {"id", "action", "source", "destination", "title"},
    "delete_source": {"id", "action", "source_path", "reason"},
    "skip": {"id", "action"},
}


def describe(action: dict) -> str:
    kind = action.get("action", "?")
    aid = action.get("id", "?")
    if kind == "move_note":
        return (f"{aid} move_note: {action.get('source')} → {action.get('destination')}")
    if kind == "create_moc":
        return (f"{aid} create_moc: {action.get('source')} → {action.get('destination')} "
                f"(title={action.get('title')!r})")
    if kind == "link_to_moc":
        return (f"{aid} link_to_moc: target=[[{action.get('target_moc')}]] "
                f"line={action.get('line_to_add')!r}")
    if kind == "update_tracker":
        return (f"{aid} update_tracker: {action.get('daily_note_path')} "
                f"{action.get('field')}={action.get('value')} ({action.get('syntax')})")
    if kind == "update_log_entry":
        pos = action.get('position')
        time = f"@{action['time']} " if action.get('time') else ""
        return (f"{aid} update_log_entry: {action.get('daily_note_path')} "
                f"[{pos}] {time}content={action.get('content')!r}")
    if kind == "update_log_link":
        pos = action.get('position')
        time = f"@{action['time']} " if action.get('time') else ""
        return (f"{aid} update_log_link: {action.get('daily_note_path')} "
                f"[{pos}] {time}target=[[{action.get('target_stem')}]]")
    if kind == "delete_source":
        return f"{aid} delete_source: {action.get('source_path')} ({action.get('reason')})"
    if kind == "skip":
        return f"{aid} skip: {action.get('source_path') or '(unspecified)'}"
    return f"{aid} UNKNOWN ACTION: {kind}"


def main() -> int:
    p = argparse.ArgumentParser(description="Dry-run an instructions.json.")
    p.add_argument("path", help="Path to instructions.json")
    p.add_argument("--quiet", action="store_true", help="Only report failures.")
    args = p.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON: {exc}", file=sys.stderr)
        return 2

    actions = doc.get("actions") or []
    if not args.quiet:
        print(f"instructions-dryrun: {path}")
        print(f"  schema_version: {doc.get('schema_version')}")
        print(f"  generated:      {doc.get('generated')}")
        print(f"  profile:        {doc.get('profile')}")
        print(f"  action_count:   {doc.get('action_count')} (actual: {len(actions)})")
        print()

    failures = 0
    for action in actions:
        kind = action.get("action")
        required = REQUIRED_FIELDS_BY_KIND.get(kind)
        if required is None:
            print(f"  [FAIL] {action.get('id', '?')} unknown kind: {kind!r}", file=sys.stderr)
            failures += 1
            continue
        missing = required - set(action)
        if missing:
            print(f"  [FAIL] {action.get('id', '?')} ({kind}) missing: {sorted(missing)}", file=sys.stderr)
            failures += 1
            continue
        if not args.quiet:
            print(f"  [OK]   {describe(action)}")

    if not args.quiet:
        print()
    if failures:
        print(f"instructions-dryrun: {failures} failures", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"instructions-dryrun: all {len(actions)} actions OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

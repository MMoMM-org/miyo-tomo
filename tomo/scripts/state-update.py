#!/usr/bin/env python3
# state-update.py — Append one status transition line to the inbox state-file.
# version: 0.3.0
"""
Append-only writer for tomo-tmp/inbox-state.jsonl.

Each invocation appends exactly one JSON line matching
schemas/state-entry.schema.json. Readers take the last line per item_key
(last-write-wins) — recursive inbox discovery means two items can share a
bare stem, so `stem` alone is not a safe join key (spec 034 ADR-1/ADR-2);
`item_key` is the item's vault-relative path and stays unique across
subfolders. The original `pending` seed line from state-init is left in
place; transitions are recorded as new lines.

Inputs (CLI):
  --state        Path to inbox-state.jsonl
  --item-key     Item identity — the vault-relative path, verbatim (join key)
  --stem         Item stem (display only; not used for lookups)
  --path         Vault path of the item (required on running/done; optional on failed)
  --status       pending | running | done | failed
  --run-id       Run identifier (must match existing entries for safety)
  --attempts     Optional override for attempts counter
  --error-kind   Error classifier (e.g. "kado_read_timeout", "invalid_json")
  --error-msg    Human-readable error (truncated to 1 KB)

Outputs:
  Exactly one new line appended to --state. Exits 0 on success.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_last_entry(state_path: Path, item_key: str) -> dict | None:
    """Return the last-write-wins entry for `item_key` (spec 034 ADR-1/ADR-2).

    Joining on `stem` would let two items in different subfolders that share
    a filename mask each other's carried-forward state — the last line
    matching the shared stem wins, regardless of which item it belongs to.
    """
    if not state_path.exists():
        return None
    last = None
    with state_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("item_key") == item_key:
                last = obj
    return last


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Append a status transition line to the inbox state-file."
    )
    p.add_argument("--state", required=True)
    p.add_argument("--item-key", required=True, help="Vault-relative path; the join key")
    p.add_argument("--stem", required=True)
    p.add_argument("--path", default=None)
    p.add_argument("--status", required=True, choices=["pending", "running", "done", "failed"])
    p.add_argument("--run-id", required=True)
    p.add_argument("--attempts", type=int, default=None)
    p.add_argument("--error-kind", default=None)
    p.add_argument("--error-msg", default=None)
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    state_path = Path(args.state)

    prior = read_last_entry(state_path, args.item_key)
    now = now_iso()

    # Build the new entry, carrying forward what we can from the prior line
    entry: dict = {
        "run_id": args.run_id,
        "stem": args.stem,
        "item_key": args.item_key,
        "path": args.path or (prior.get("path") if prior else None),
        "status": args.status,
        "attempts": args.attempts if args.attempts is not None
                    else (prior.get("attempts", 0) if prior else 0),
        "started_at": prior.get("started_at") if prior else None,
        "completed_at": prior.get("completed_at") if prior else None,
        "error": None,
    }
    if entry["path"] is None:
        print(f"ERROR: no path known for item_key={args.item_key}", file=sys.stderr)
        return 1

    if args.status == "running":
        entry["started_at"] = now
        entry["attempts"] = entry["attempts"] + 1
    elif args.status in ("done", "failed"):
        if not entry["started_at"]:
            entry["started_at"] = now
        entry["completed_at"] = now

    if args.status == "failed":
        kind = args.error_kind or "unknown"
        msg = (args.error_msg or "")[:1024]
        entry["error"] = {"kind": kind, "message": msg}

    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(
        f"state-update: item_key={args.item_key} stem={args.stem} status={args.status} "
        f"attempts={entry['attempts']} run_id={args.run_id}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

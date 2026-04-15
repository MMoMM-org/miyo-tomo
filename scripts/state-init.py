#!/usr/bin/env python3
# state-init.py — Phase A: enumerate inbox, seed state-file with pending items.
# version: 0.2.0
"""
List the inbox via Kado, emit one JSONL line per item with status="pending".
Skips derived artefacts (existing suggestions/instruction docs).

Inputs (CLI):
  --inbox-path  vault-relative inbox path (e.g. "100 Inbox/")
  --run-id      unique run identifier
  --output      tomo-tmp/inbox-state.jsonl

Outputs:
  JSONL file at --output, one line per inbox item matching
  schemas/state-entry.schema.json with status="pending".
  Stdout log: items_found, items_skipped.

Exit: 0 on success, 1 on error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.kado_client import KadoClient, KadoError  # noqa: E402


# Filenames with these suffixes are Tomo-generated workflow docs, not
# source items to process.
SKIP_SUFFIXES = ("_suggestions.md", "_instructions.md", "-diff.md")


def extract_stem(path: str) -> str:
    """Return the filename without .md extension."""
    name = path.rsplit("/", 1)[-1]
    if name.endswith(".md"):
        name = name[:-3]
    return name


def is_skippable(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(suffix) for suffix in SKIP_SUFFIXES)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Seed the run state-file by listing the inbox and marking every item pending."
    )
    p.add_argument("--inbox-path", required=True, help="Vault-relative inbox path")
    p.add_argument("--run-id", default=None, help="Unique run identifier (auto if omitted)")
    p.add_argument("--output", required=True, help="Target path for inbox-state.jsonl")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    inbox_path = args.inbox_path.rstrip("/") + "/"
    out_path = Path(args.output)
    run_id = args.run_id or uuid.uuid4().hex[:12]

    try:
        client = KadoClient()
        items = client.list_dir(inbox_path, depth=1, limit=500)
    except KadoError as exc:
        print(f"ERROR: Kado list_dir failed for {inbox_path}: {exc}", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)

    found = 0
    skipped = 0
    # Deterministic order: sort by path string
    items_sorted = sorted(
        [i for i in items if isinstance(i, dict)],
        key=lambda i: i.get("path") or "",
    )
    with out_path.open("w", encoding="utf-8") as fh:
        for item in items_sorted:
            path = (item.get("path") or "").strip()
            kind = (item.get("kind") or item.get("type") or "").lower()
            if not path:
                continue
            if kind and kind != "file":
                continue  # skip subdirectories
            if not path.endswith(".md"):
                # Non-markdown assets go through the inbox-analyst as attachments
                # via their own path; still record them as pending.
                pass
            if is_skippable(path):
                skipped += 1
                continue
            stem = extract_stem(path)
            entry = {
                "run_id": run_id,
                "stem": stem,
                "path": path,
                "status": "pending",
                "attempts": 0,
                "started_at": None,
                "completed_at": None,
                "error": None,
            }
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            found += 1

    print(
        f"items_found={found} items_skipped={skipped} run_id={run_id} out={out_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

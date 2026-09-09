#!/usr/bin/env python3
# item-result-filename.py — Print the per-item result filename for an item_key.
# version: 0.1.0
"""
CLI wrapper around lib.item_key.to_filename (spec 034 ADR-5), so callers that
cannot import Python directly (e.g. the inbox-analyst agent, which invokes
scripts over Bash) can still name their per-item result file consistently
with whatever reads it back by item_key.

Inputs (CLI):
  --item-key   The item's identity (vault-relative path, verbatim)

Outputs:
  Prints the filename (no directory) to stdout. Exit 0 on success, 1 if
  --item-key is empty or otherwise invalid.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.item_key import to_filename  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Print the per-item result filename for an item_key."
    )
    p.add_argument("--item-key", required=True)
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        print(to_filename(args.item_key))
    except (ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

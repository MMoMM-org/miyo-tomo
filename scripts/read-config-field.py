#!/usr/bin/env python3
# read-config-field.py — Read a dotted field from vault-config.yaml and print it.
# version: 0.1.0
#
# Replaces ad-hoc `python3 -c "..."` and `grep/sed` in agent prompts. Keeps
# agent Bash commands flat — no quoted inline Python or compound pipelines
# that trip Claude Code's Bash validator.
#
# Usage:
#   python3 scripts/read-config-field.py --field profile
#   python3 scripts/read-config-field.py --field concepts.inbox --default "100 Inbox/"
#
# Exits 1 if the field is missing and no --default is given.

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def get_field(data: dict, dotted: str):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def main() -> int:
    p = argparse.ArgumentParser(
        description="Print a dotted field from a YAML config file."
    )
    p.add_argument("--config", default="config/vault-config.yaml")
    p.add_argument("--field", required=True, help="Dotted path, e.g. concepts.inbox")
    p.add_argument("--default", default=None, help="Fallback if missing")
    args = p.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"ERROR: config not found: {cfg_path}", file=sys.stderr)
        return 1
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    value = get_field(cfg, args.field)
    if value is None:
        if args.default is None:
            print(f"ERROR: field not found: {args.field}", file=sys.stderr)
            return 1
        value = args.default

    sys.stdout.write(str(value) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

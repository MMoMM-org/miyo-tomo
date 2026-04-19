#!/usr/bin/env python3
# read-config-field.py — Read dotted fields from vault-config.yaml.
# version: 0.2.0
#
# Replaces ad-hoc `python3 -c "..."` and `grep/sed` in agent prompts. Keeps
# agent Bash commands flat — no quoted inline Python or compound pipelines
# that trip Claude Code's Bash validator.
#
# Single field (backwards compatible):
#   python3 scripts/read-config-field.py --field profile
#   python3 scripts/read-config-field.py --field concepts.inbox --default "100 Inbox/"
#
# Multiple fields (batch — saves tool calls):
#   python3 scripts/read-config-field.py --fields concepts.inbox,profile,lifecycle.tag_prefix
#   python3 scripts/read-config-field.py --fields concepts.inbox,profile --format json
#
# Output:
#   --field (single):  plain text value on stdout
#   --fields (batch):  one key=value per line, or JSON with --format json
#
# Exits 1 if --field is used and the field is missing (no --default).
# With --fields, missing fields are omitted (no error).

from __future__ import annotations

import argparse
import json
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
        description="Print dotted field(s) from a YAML config file."
    )
    p.add_argument("--config", default="config/vault-config.yaml")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--field", help="Single dotted path, e.g. concepts.inbox")
    group.add_argument("--fields", help="Comma-separated dotted paths for batch read")
    p.add_argument("--default", default=None, help="Fallback if missing (--field only)")
    p.add_argument("--format", choices=["text", "json"], default="text",
                   help="Output format for --fields (default: text)")
    args = p.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"ERROR: config not found: {cfg_path}", file=sys.stderr)
        return 1
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # Single field mode (backwards compatible)
    if args.field:
        value = get_field(cfg, args.field)
        if value is None:
            if args.default is None:
                print(f"ERROR: field not found: {args.field}", file=sys.stderr)
                return 1
            value = args.default
        sys.stdout.write(str(value) + "\n")
        return 0

    # Batch mode
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    result = {}
    for field in fields:
        value = get_field(cfg, field)
        if value is not None:
            result[field] = value

    if args.format == "json":
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for key, value in result.items():
            sys.stdout.write(f"{key}={value}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

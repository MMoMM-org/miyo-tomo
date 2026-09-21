#!/usr/bin/env python3
# read-routing-plan.py — Read fields and source batches from routing-plan.json.
# version: 0.1.0
#
# Replaces ad-hoc `python3 -c "..."` in the suggestion conductor. The plan is
# the only input the fan-out needs, and `cat`ing it hands the model a document
# to re-derive a list from — so it wrote inline Python instead, which the
# conductor's own STRICT forbids and Claude Code's Bash validator flags on the
# `#` characters.
#
# Single field:
#   python3 scripts/read-routing-plan.py --field inbox_path
#   python3 scripts/read-routing-plan.py --field action
#
# Fresh sources, one path per line:
#   python3 scripts/read-routing-plan.py --sources
#
# One dispatch batch, one path per line (1-based batch number):
#   python3 scripts/read-routing-plan.py --sources --batch 1 --size 5
#
# Counts:
#   python3 scripts/read-routing-plan.py --count
#   python3 scripts/read-routing-plan.py --batch-count --size 5
#
# `inbox_path` is emitted without a trailing slash, so callers can join with
# "/" unconditionally. The plan carries it as "100 Inbox/", and a template
# reading "<inbox_path>/<stem>" produced "100 Inbox//<stem>" — Kado normalises
# that today, which is a dependency on someone else's tolerance.
#
# Exit: 0 on success, 1 on a missing file / malformed JSON / out-of-range batch.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_PLAN = "tomo-tmp/routing-plan.json"


def load_plan(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"read-routing-plan: no such file: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"read-routing-plan: {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"read-routing-plan: {path} must hold a JSON object")
    return data


def resolve_field(plan: dict, dotted: str):
    """Walk a dotted path. A missing segment is an error, not an empty string.

    The conductor branches on these values; silently returning "" would route
    the run down the wrong path rather than stopping it.
    """
    node = plan
    for segment in dotted.split("."):
        if not isinstance(node, dict) or segment not in node:
            raise SystemExit(f"read-routing-plan: no such field: {dotted}")
        node = node[segment]
    return node


def source_paths(plan: dict) -> list[str]:
    sources = plan.get("fresh_sources")
    if sources is None:
        return []
    if not isinstance(sources, list):
        raise SystemExit("read-routing-plan: fresh_sources must be a list")
    paths = []
    for entry in sources:
        if not isinstance(entry, dict) or "path" not in entry:
            raise SystemExit(
                "read-routing-plan: every fresh_sources entry needs a 'path'"
            )
        paths.append(entry["path"])
    return paths


def batch_count(total: int, size: int) -> int:
    if size < 1:
        raise SystemExit("read-routing-plan: --size must be 1 or greater")
    return (total + size - 1) // size


def select_batch(paths: list[str], batch: int, size: int) -> list[str]:
    total = batch_count(len(paths), size)
    if batch < 1 or batch > total:
        raise SystemExit(
            f"read-routing-plan: --batch {batch} out of range (1..{total})"
        )
    start = (batch - 1) * size
    return paths[start : start + size]


def render_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read fields and source batches from routing-plan.json."
    )
    parser.add_argument("--plan", default=DEFAULT_PLAN, help=f"default: {DEFAULT_PLAN}")
    parser.add_argument("--field", help="Dotted field, e.g. inbox_path or metrics.item_count")
    parser.add_argument("--sources", action="store_true", help="One source path per line")
    parser.add_argument("--count", action="store_true", help="Number of fresh sources")
    parser.add_argument("--batch-count", action="store_true", help="Number of batches at --size")
    parser.add_argument("--batch", type=int, help="1-based batch number; requires --sources")
    parser.add_argument("--size", type=int, default=5, help="Batch size (default 5)")
    args = parser.parse_args(argv)

    modes = [bool(args.field), args.sources, args.count, args.batch_count]
    if sum(modes) != 1:
        parser.error("choose exactly one of --field, --sources, --count, --batch-count")
    if args.batch is not None and not args.sources:
        parser.error("--batch requires --sources")

    plan = load_plan(Path(args.plan))

    if args.field:
        value = resolve_field(plan, args.field)
        if args.field == "inbox_path" and isinstance(value, str):
            value = value.rstrip("/")
        print(render_value(value))
        return 0

    paths = source_paths(plan)

    if args.count:
        print(len(paths))
        return 0

    if args.batch_count:
        print(batch_count(len(paths), args.size))
        return 0

    if args.batch is not None:
        paths = select_batch(paths, args.batch, args.size)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

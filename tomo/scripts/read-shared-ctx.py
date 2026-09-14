#!/usr/bin/env python3
# read-shared-ctx.py — Read fields from shared-ctx.json without loading it whole.
# version: 0.2.0
#
# Every Phase-B subagent loads the shared context, and `cat` is the only way
# the agent definition offers. Measured over four runs and 48 subagents: 45
# `cat`s of the whole file, 9 inline-Python reaches for a single field, 4
# whole-file Read calls. The inline Python is the right instinct with the
# forbidden tool — those calls ask for `daily_notes`, `tag_prefixes`,
# `placeholder_links`, `classification_keywords` and `asset_folder`, which
# together are under 12 KB of a 40 KB file whose `mocs` key is 72% of it.
#
# One field:
#   python3 scripts/read-shared-ctx.py --field daily_notes
#   python3 scripts/read-shared-ctx.py --field daily_notes.daily_log.cutoff_days
#
# Several at once (one tool call instead of three):
#   python3 scripts/read-shared-ctx.py --fields tag_prefixes,classification_keywords
#
# What is in there, and how big:
#   python3 scripts/read-shared-ctx.py --keys
#
# Scalars print bare so they can be captured directly; objects and arrays print
# as JSON. `--fields` always prints a JSON object keyed by the dotted path, so
# a caller never has to guess which form it got.
#
# Exit: 0 on success, 1 on a missing file / malformed JSON / unknown field.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_CTX = "tomo-tmp/shared-ctx.json"


def load_ctx(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"read-shared-ctx: no such file: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"read-shared-ctx: {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"read-shared-ctx: {path} must hold a JSON object")
    return data


def resolve(ctx: dict, dotted: str):
    """Walk a dotted path. A missing segment names itself and stops the run.

    Steps in the analyst's contract branch on these values — an absent key and
    a key holding `null` mean different things, and returning "" for both would
    collapse that distinction silently.
    """
    node = ctx
    walked: list[str] = []
    for segment in dotted.split("."):
        if not isinstance(node, dict) or segment not in node:
            where = ".".join(walked) or "(root)"
            available = sorted(node) if isinstance(node, dict) else []
            raise SystemExit(
                f"read-shared-ctx: no such field: {dotted} — {segment!r} not "
                f"present under {where}. Available there: {available}"
            )
        walked.append(segment)
        node = node[segment]
    return node


def render(value, indent: int | None = None) -> str:
    """Containers serialize compact by default.

    Pretty-printing inflates: `--field mocs` at indent=2 measures 44 KB against
    the 40 KB of simply catting the whole file, because `mocs` is 72% of it and
    indentation grows with nesting depth. The output of this script goes into a
    subagent's context window, where every byte is carried; `--indent` exists
    for the times a person is reading it.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        if indent is None:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return json.dumps(value, ensure_ascii=False, indent=indent)
    return str(value)


def render_keys(ctx: dict) -> str:
    """Top-level keys with their serialized size, largest first.

    Replaces the `print(list(d.keys()))` that opened three of the nine inline
    reaches. The sizes are the point: they are what tells a reader that `mocs`
    is 72% of the file.
    """
    rows = []
    for key, value in ctx.items():
        rows.append((len(json.dumps(value, ensure_ascii=False)), key))
    total = sum(n for n, _ in rows) or 1
    lines = []
    for size, key in sorted(rows, reverse=True):
        lines.append(f"{size:7d}  {100 * size / total:5.1f}%  {key}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read fields from shared-ctx.json without loading it whole."
    )
    parser.add_argument("--ctx", default=DEFAULT_CTX, help=f"default: {DEFAULT_CTX}")
    parser.add_argument("--field", help="One dotted field, e.g. daily_notes.daily_log.enabled")
    parser.add_argument("--fields", help="Comma-separated dotted fields; prints a JSON object")
    parser.add_argument("--keys", action="store_true", help="Top-level keys with byte sizes")
    parser.add_argument("--indent", type=int, default=None,
                        help="Pretty-print containers for human reading (default: compact)")
    args = parser.parse_args(argv)

    if sum([bool(args.field), bool(args.fields), args.keys]) != 1:
        parser.error("choose exactly one of --field, --fields, --keys")

    ctx = load_ctx(Path(args.ctx))

    if args.keys:
        print(render_keys(ctx))
        return 0

    if args.field:
        print(render(resolve(ctx, args.field), args.indent))
        return 0

    names = [f.strip() for f in args.fields.split(",") if f.strip()]
    if not names:
        parser.error("--fields needs at least one field name")
    out = {name: resolve(ctx, name) for name in names}
    print(render(out, args.indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# read-shared-ctx.py — Read fields from shared-ctx.json without loading it whole.
# version: 0.3.1
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
# The names of every eligible MOC (compact JSON array, in mocs[] order):
#   python3 scripts/read-shared-ctx.py --moc-names
#
# Full entries for the MOCs named in a file, one name per line:
#   python3 scripts/read-shared-ctx.py --mocs-from <items_dir>/<stem>.moc-names.txt
# Prints {"mocs": [...], "unresolved": [...], "omitted": [...]}. A name matches
# exactly, else by a unique NFC + casefold + whitespace-collapsed match. Unlike
# --fields, an unknown or ambiguous name does NOT fail the call: it is listed
# in `unresolved` and exit stays 0, so one mistyped name costs one candidate,
# not the item's whole MOC detail. Blank lines and duplicates are ignored; only
# the first 20 distinct names are resolved, the rest are listed in `omitted`.
# Names come from a file because MOC titles are not safe on a command line.
#
# Any mode with --run-id <id> first checks the context belongs to that run.
#
# Scalars print bare so they can be captured directly; objects and arrays print
# as JSON. `--fields` always prints a JSON object keyed by the dotted path, so
# a caller never has to guess which form it got.
#
# Exit: 0 on success; 1 with one stderr line on a missing or malformed context,
# an unknown --field/--fields name, a --run-id mismatch, a context without
# mocs[].name (built before spec 040), or a missing/unreadable names file.
# Usage errors (no mode, two modes, unknown flag) are argparse's exit 2.

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

DEFAULT_CTX = "tomo-tmp/shared-ctx.json"
MAX_NOMINATED = 20


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


def check_run_id(ctx: dict, expected: str) -> None:
    actual = ctx.get("run_id")
    if actual != expected:
        raise SystemExit(f"read-shared-ctx: shared-ctx belongs to run {actual}, expected {expected}")


def named_mocs(ctx: dict) -> list[dict]:
    mocs = ctx.get("mocs") or []
    if any("name" not in m for m in mocs):
        raise SystemExit(
            "read-shared-ctx: context predates spec 040 (mocs[] has no name); rebuild it"
        )
    return mocs


def _loose(name: str) -> str:
    return " ".join(unicodedata.normalize("NFC", name).casefold().split())


def read_names_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"read-shared-ctx: no such names file: {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"read-shared-ctx: cannot read names file {path}: {exc}") from None
    names: list[str] = []
    for line in text.splitlines():
        name = line.strip()
        if name and name not in names:
            names.append(name)
    return names


def select_mocs(mocs: list[dict], names: list[str]) -> dict:
    """Resolve nominated names to full entries; never fails on a bad name."""
    by_name = {m["name"]: m for m in mocs}
    by_loose: dict[str, list[dict]] = {}
    for m in mocs:
        by_loose.setdefault(_loose(m["name"]), []).append(m)
    picked: list[dict] = []
    unresolved: list[str] = []
    for name in names[:MAX_NOMINATED]:
        moc = by_name.get(name)
        if moc is None:
            matches = by_loose.get(_loose(name), [])
            moc = matches[0] if len(matches) == 1 else None
        if moc is None:
            unresolved.append(name)
        elif not any(p is moc for p in picked):
            picked.append(moc)
    return {"mocs": picked, "unresolved": unresolved, "omitted": names[MAX_NOMINATED:]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read fields from shared-ctx.json without loading it whole."
    )
    parser.add_argument("--ctx", default=DEFAULT_CTX, help=f"default: {DEFAULT_CTX}")
    parser.add_argument("--field", help="One dotted field, e.g. daily_notes.daily_log.cutoff_days")
    parser.add_argument("--fields", help="Comma-separated dotted fields; prints a JSON object")
    parser.add_argument("--keys", action="store_true", help="Top-level keys with byte sizes")
    parser.add_argument("--moc-names", action="store_true",
                        help="Names of all eligible MOCs, compact JSON, in mocs[] order")
    parser.add_argument("--mocs-from", metavar="FILE",
                        help="Full entries for the MOC names in FILE (one per line)")
    parser.add_argument("--run-id", help="Fail unless the context was built by this run")
    parser.add_argument("--indent", type=int, default=None,
                        help="Pretty-print containers for human reading (default: compact)")
    args = parser.parse_args(argv)

    modes = [bool(args.field), bool(args.fields), args.keys, args.moc_names, bool(args.mocs_from)]
    if sum(modes) != 1:
        parser.error("choose exactly one of --field, --fields, --keys, --moc-names, --mocs-from")

    ctx = load_ctx(Path(args.ctx))
    if args.run_id is not None:
        check_run_id(ctx, args.run_id)

    if args.moc_names:
        print(render([m["name"] for m in named_mocs(ctx)]))
        return 0

    if args.mocs_from:
        mocs = named_mocs(ctx)
        print(render(select_mocs(mocs, read_names_file(Path(args.mocs_from)))))
        return 0

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

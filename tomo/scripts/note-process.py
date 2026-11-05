#!/usr/bin/env python3
# note-process.py — read, write and decline the process files of /note.
# version: 0.1.0
"""The only writer of ``config/note-processes/<template-stem>.md``.

The /note skill reads a template's process file before asking, saves one when
the user answers "save" or runs ``/note --process``, and records "never" as a
decline marker. Parsing, the required-point check and the atomic write live in
lib/note_process.py; this script parses arguments, loads the outline and the
guidance file, and prints the result.

Usage (cwd = instance root):
    python3 scripts/note-process.py read    --template <stem> [--outline <file>]
    python3 scripts/note-process.py write   --template <stem> --outline <file>
                [--destination <folder>] [--required a,b] [--guidance-file <file>]
    python3 scripts/note-process.py decline --template <stem>

Output: one JSON object on stdout (ASCII-escaped).
    read:    exists, declined, destination, required, guidance,
             missing_required, error
    write:   written, rejected_required
    decline: written

Rules:
    --outline is a template-outline.py output file: a JSON object whose
    frontmatter, headings and tokens are lists of objects.
    --required is split on commas; entries are trimmed, empty ones dropped.
    --guidance-file is read as UTF-8; its text becomes the file body.
    A broken process file reads as exists true with error set (exit 0).
    stderr names the problem class only, never a stem or file text.

Exit codes:
    0 — output usable
    1 — write rejected: a required point is not in the outline; nothing written
    2 — bad invocation: malformed stem, outline or guidance file, write failure

Design notes: docs/tomo/scripts/note-process.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.note_process import (  # noqa: E402
    PROCESS_DIR, read_process, write_decline, write_process,
)

OUTLINE_LISTS = ("frontmatter", "headings", "tokens")


class UsageError(Exception):
    """Bad invocation; exit 2. Message names the problem class only."""


def load_outline(path: str) -> dict:
    """Return the outline object; UsageError when missing, not JSON or wrong shape."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise UsageError(f"outline unreadable ({type(exc).__name__})") from exc
    except ValueError as exc:
        raise UsageError("outline is not JSON") from exc
    if not isinstance(data, dict):
        raise UsageError("outline is not a JSON object")
    for key in OUTLINE_LISTS:
        value = data.get(key)
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            raise UsageError(f"outline {key} is not a list of objects")
    return data


def load_guidance(path: str | None) -> str:
    if path is None:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UsageError(f"guidance file unreadable ({type(exc).__name__})") from exc


def split_required(text: str | None) -> list[str]:
    return [r.strip() for r in (text or "").split(",") if r.strip()]


def run_read(args: argparse.Namespace) -> tuple[dict, int]:
    outline = load_outline(args.outline) if args.outline is not None else None
    return read_process(PROCESS_DIR, args.template, outline), 0


def run_write(args: argparse.Namespace) -> tuple[dict, int]:
    outline = load_outline(args.outline)
    guidance = load_guidance(args.guidance_file)
    result = write_process(PROCESS_DIR, args.template, outline, destination=args.destination,
                           required=split_required(args.required), guidance=guidance)
    return result, 0 if result["written"] else 1


def run_decline(args: argparse.Namespace) -> tuple[dict, int]:
    return write_decline(PROCESS_DIR, args.template), 0


COMMANDS = {"read": run_read, "write": run_write, "decline": run_decline}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read, write and decline /note process files.")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("read", help="Read a process file")
    r.add_argument("--template", required=True, help="Template stem")
    r.add_argument("--outline", help="template-outline.py output file")
    w = sub.add_parser("write", help="Write a process file, replacing a decline marker")
    w.add_argument("--template", required=True, help="Template stem")
    w.add_argument("--outline", required=True, help="template-outline.py output file")
    w.add_argument("--destination", help="Vault folder for new notes")
    w.add_argument("--required", help="Comma-separated required point names")
    w.add_argument("--guidance-file", help="File holding the guidance text")
    d = sub.add_parser("decline", help="Write the decline marker")
    d.add_argument("--template", required=True, help="Template stem")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result, code = COMMANDS[args.command](args)
    except UsageError as exc:
        print(f"note-process: {exc}", file=sys.stderr)
        return 2
    except ValueError:
        print("note-process: malformed template stem", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"note-process: process file not written ({type(exc).__name__})", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())

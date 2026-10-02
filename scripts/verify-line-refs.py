#!/usr/bin/env python3
# version: 0.1.0
"""Resolve every `<module>.py:NNN` reference in a file and show what it points at.

Prose references go stale silently. Inserting code above a cited line shifts it,
and no test notices: spec 038's T3.2 added ~106 lines above a check, and twelve
references written one task earlier ended up ~91 lines short, naming a comment in
a different branch. The suite stayed green throughout.

This reads references and reports; it never edits. Run it over a plan, a docstring,
a WHY doc, or a module, and read the line each citation actually lands on.

    scripts/verify-line-refs.py docs/XDD/specs/038-*/plan/phase-3.md
    scripts/verify-line-refs.py tomo/scripts/lib/*.py tests/test_038_*.py
    scripts/verify-line-refs.py --quiet docs/tomo/scripts/lib/render_md.md

Exit status is 0 unless `--strict` is given, which exits 1 when any reference
cannot be resolved at all (missing module, line past end of file). A reference
that resolves is never an error here — only a human can say whether the line it
landed on is the one meant.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# A module name may contain hyphens (`instruction-render.py`). Omitting them was
# itself a false positive the first time this was run by hand: `instruction-render.py`
# matched as `render.py` and was reported as a module that does not exist.
REF = re.compile(r"(?:(?P<dir>[\w./-]*?/))?(?P<mod>[\w-]+\.py):(?P<start>\d+)(?:-(?P<end>\d+))?")

SEARCH_ROOTS = [
    Path("tomo/scripts"),
    Path("tomo/scripts/lib"),
    Path("scripts"),
    Path("scripts/lib"),
    Path("tests"),
]


def resolve_module(repo: Path, mod: str, hinted_dir: str | None) -> Path | None:
    """Find the module a reference names, preferring any directory it hinted."""
    if hinted_dir:
        candidate = repo / hinted_dir.rstrip("/") / mod
        if candidate.is_file():
            return candidate
    for root in SEARCH_ROOTS:
        candidate = repo / root / mod
        if candidate.is_file():
            return candidate
    hits = sorted(repo.glob(f"**/{mod}"))
    return hits[0] if len(hits) == 1 else None


def check_file(repo: Path, path: Path, quiet: bool) -> tuple[int, int]:
    """Report every reference in `path`. Returns (checked, unresolvable)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"{path}: cannot read ({exc})", file=sys.stderr)
        return 0, 0

    rows: list[tuple[int, str, str, str]] = []
    unresolvable = 0
    for m in REF.finditer(text):
        mod = m.group("mod")
        if mod == path.name:
            continue
        cited_at = text[: m.start()].count("\n") + 1
        target = resolve_module(repo, mod, m.group("dir"))
        ref = f"{mod}:{m.group('start')}" + (f"-{m.group('end')}" if m.group("end") else "")
        if target is None:
            rows.append((cited_at, ref, "UNRESOLVED", "no such module, or ambiguous"))
            unresolvable += 1
            continue
        lines = target.read_text(encoding="utf-8").splitlines()
        start = int(m.group("start"))
        if not 1 <= start <= len(lines):
            rows.append((cited_at, ref, "OUT OF RANGE", f"{target.name} has {len(lines)} lines"))
            unresolvable += 1
            continue
        shown = lines[start - 1].strip()
        if m.group("end"):
            end = min(int(m.group("end")), len(lines))
            shown += f"   …through: {lines[end - 1].strip()}"
        rows.append((cited_at, ref, "", shown))

    if not rows or (quiet and unresolvable == 0):
        return len(rows), unresolvable

    print(f"\n{path}")
    for cited_at, ref, problem, shown in rows:
        if quiet and not problem:
            continue
        flag = f"  <-- {problem}" if problem else ""
        print(f"  :{cited_at:<5} {ref:<34}{flag}")
        print(f"         {shown[:140]}")
    return len(rows), unresolvable


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show what every `<module>.py:NNN` reference in a file points at.",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="files to scan")
    parser.add_argument(
        "--quiet", action="store_true",
        help="print only references that cannot be resolved",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 if any reference is unresolvable",
    )
    parser.add_argument(
        "--repo", type=Path, default=None,
        help="repository root (default: the directory this script's parent sits in)",
    )
    args = parser.parse_args()

    repo = args.repo or Path(__file__).resolve().parent.parent

    checked = unresolvable = 0
    for path in args.paths:
        if not path.exists():
            print(f"{path}: not found", file=sys.stderr)
            continue
        c, u = check_file(repo, path, args.quiet)
        checked += c
        unresolvable += u

    print(f"\n{checked} reference(s) checked, {unresolvable} unresolvable")
    if unresolvable and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

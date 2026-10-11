#!/usr/bin/env python3
# version: 0.2.1
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

That gap is this tool's real limitation, and it is worth stating plainly: a
reference whose line still EXISTS is not a reference that is still CORRECT. Insert
code above a cited line and the citation keeps resolving, silently, at the wrong
content. A review of spec 038's T3.5 caught eighteen such citations that this tool
had just reported clean. The one heuristic that helps is SUSPECT: a citation
landing on a bare closing bracket, a lone docstring quote, a comment marker or a
blank line is almost certainly stale, because nobody cites those deliberately. It
is advisory — shown even under `--quiet`, never failing `--strict` — and it is a
floor, not a guarantee. The only complete check is reading the cited line against
what the citing text claims it says.

One sequencing rule, learned by breaking it: **never rewrite citations and edit the
cited file in the same pass.** A sweep that verifies a landmark, rewrites every
citation to it, and then grows the file above it writes 18 stale citations in one
run — the arithmetic is right and the ordering makes it wrong. Measure after the
last code edit, rewrite citations in a pass that touches no source, and verify by
reading the cited line's CONTENT afterwards, not by this tool reporting zero
unresolvable. The same landmark in `render_actions.py` moved three times in one day
(836, 927, 939, 945) and the third move was caused by the sweep fixing the second.
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


# A citation that lands on one of these is almost certainly stale rather than
# deliberate: nobody cites a bare closing bracket or a blank line to make a point.
# This is the gap a resolve-only check leaves open — a reference whose line still
# EXISTS is not a reference that is still CORRECT, and the difference is exactly
# what shifted-by-insertion looks like. Found the hard way: a `:927` citation that
# the resolve check passed happily was pointing at a lone `}`, four lines past the
# code it named, after an unrelated docstring edit grew the function above it.
_IMPLAUSIBLE = {"}", ")", "]", "},", "),", "],", "):", '"""', "'''", "", "#"}


def implausible(line: str) -> str:
    """A one-word flag when a cited line cannot plausibly be the intended target."""
    stripped = line.strip()
    if stripped in _IMPLAUSIBLE:
        return "SUSPECT (lands on a bare delimiter or blank line)"
    return ""


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
        rows.append((cited_at, ref, implausible(lines[start - 1]), shown))

    suspects = sum(1 for _c, _r, problem, _s in rows if problem.startswith("SUSPECT"))
    if not rows or (quiet and unresolvable == 0 and suspects == 0):
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

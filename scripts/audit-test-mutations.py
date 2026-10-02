#!/usr/bin/env python3
# version: 0.1.0
"""List tests whose docstring does not name the mutation they falsify.

This repo's convention is that a test says which change to production code turns it
red. The reason is specific: spec 037 shipped nine assertions that could not bite,
and a test nobody can falsify is scaffolding wearing a guard's name. Naming the
mutation is what makes "run it" possible, and running it is what proves the guard.

The auditable unit is the test, not the assertion — a mutation falsifies a test, and
assertions travel in groups. So this reports per test function and counts the
assertions inside each, to show which ones carry weight.

    scripts/audit-test-mutations.py tests/test_038_*.py
    scripts/audit-test-mutations.py --quiet tests/
    scripts/audit-test-mutations.py --strict tests/test_038_t3_2_typed_name_refusal.py

A test flagged here is not necessarily wrong. A docstring may describe the mutation
in words this does not cue on, and some tests legitimately pin a shape rather than
falsify a mechanism. Read each one; the output is a list to work through, not a
verdict.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# Words a docstring uses when it names what would break the test. Deliberately
# broad: a false positive costs a glance, a false negative hides an unfalsifiable
# assertion.
CUES = ("mutation", "mutate", "revert", "falsif", "turns this red", "turns it red")


def cues_present(text: str) -> bool:
    lowered = text.lower()
    return any(cue in lowered for cue in CUES)


def expand(paths: list[Path]) -> list[Path]:
    """Accept files or directories; a directory contributes its test_*.py files."""
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            out.extend(sorted(p.glob("test_*.py")))
        elif p.is_file():
            out.append(p)
        else:
            print(f"{p}: not found", file=sys.stderr)
    return out


def audit(path: Path) -> tuple[list[str], list[str]]:
    """Returns (named, unnamed) labels for the test functions in `path`."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        print(f"{path}: cannot parse ({exc})", file=sys.stderr)
        return [], []

    module_doc = ast.get_docstring(tree) or ""
    module_cues = cues_present(module_doc)

    named: list[str] = []
    unnamed: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        doc = ast.get_docstring(node) or ""
        asserts = sum(1 for n in ast.walk(node) if isinstance(n, ast.Assert))
        label = f"{path.name}::{node.name}  ({asserts} assert)"
        if cues_present(doc):
            named.append(label)
        else:
            if module_cues:
                label += "   [the module docstring names one — check whether it covers this test]"
            unnamed.append(label)
    return named, unnamed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List tests whose docstring does not name the mutation they falsify.",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="test files or directories")
    parser.add_argument(
        "--quiet", action="store_true", help="list only the unnamed ones",
    )
    parser.add_argument(
        "--strict", action="store_true", help="exit 1 if any test lacks a named mutation",
    )
    args = parser.parse_args()

    all_named: list[str] = []
    all_unnamed: list[str] = []
    for path in expand(args.paths):
        named, unnamed = audit(path)
        all_named.extend(named)
        all_unnamed.extend(unnamed)

    if all_named and not args.quiet:
        print(f"NAMES A MUTATION ({len(all_named)}):")
        for label in all_named:
            print(f"  + {label}")
        print()

    print(f"NO NAMED MUTATION ({len(all_unnamed)}):")
    for label in all_unnamed:
        print(f"  - {label}")

    total = len(all_named) + len(all_unnamed)
    print(f"\n{total} test(s) examined, {len(all_unnamed)} without a named mutation")
    if all_unnamed and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

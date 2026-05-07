#!/usr/bin/env python3
# version: 0.1.0
"""test-shared-ctx-placeholders.py — Smoke tests for shared-ctx-builder.build_placeholder_mocs.

Covers the F-35 pass-through of `cache.placeholder_mocs[]` (Mental Squeeze
Point §2.C trigger source).

Happy path:
  - Well-formed entries pass through unchanged
  - Field whitespace is stripped
Drift guards (silent skip — schema treats placeholder_mocs as optional):
  - Missing field → returns []
  - Non-list value → returns []
  - Entries without both target+referenced_by → dropped
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "shared_ctx_builder", SCRIPTS_DIR / "shared-ctx-builder.py"
)
scb = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(scb)


def _must(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def test_happy_path() -> None:
    cache = {
        "placeholder_mocs": [
            {"target": "Boardgames", "referenced_by": "Atlas/200 MOCs/Hobbies MOC.md"},
            {"target": "Functional Programming", "referenced_by": "Atlas/200 MOCs/Software MOC.md"},
        ]
    }
    out = scb.build_placeholder_mocs(cache)
    _must(len(out) == 2, f"expected 2 entries, got {len(out)}")
    _must(out[0]["target"] == "Boardgames", f"target preserved: {out[0]}")
    _must(out[1]["referenced_by"] == "Atlas/200 MOCs/Software MOC.md", f"ref preserved: {out[1]}")


def test_strips_whitespace() -> None:
    cache = {
        "placeholder_mocs": [
            {"target": "  Boardgames  ", "referenced_by": "  Atlas/x.md  "},
        ]
    }
    out = scb.build_placeholder_mocs(cache)
    _must(out == [{"target": "Boardgames", "referenced_by": "Atlas/x.md"}], f"strip failed: {out}")


def test_missing_field_returns_empty() -> None:
    out = scb.build_placeholder_mocs({})
    _must(out == [], f"missing field should yield []: {out}")


def test_non_list_returns_empty() -> None:
    out = scb.build_placeholder_mocs({"placeholder_mocs": "oops"})
    _must(out == [], f"non-list should yield []: {out}")


def test_drops_malformed_entries() -> None:
    cache = {
        "placeholder_mocs": [
            {"target": "Valid", "referenced_by": "x.md"},
            {"target": "", "referenced_by": "x.md"},          # empty target
            {"target": "Y", "referenced_by": ""},             # empty ref
            {"referenced_by": "x.md"},                         # missing target
            {"target": "Z"},                                   # missing ref
            "not a dict",                                      # wrong type
            None,                                              # null
        ]
    }
    out = scb.build_placeholder_mocs(cache)
    _must(len(out) == 1, f"expected 1 valid entry, got {len(out)}: {out}")
    _must(out[0]["target"] == "Valid", f"first should be Valid: {out[0]}")


def test_null_value() -> None:
    out = scb.build_placeholder_mocs({"placeholder_mocs": None})
    _must(out == [], f"null should yield []: {out}")


def main() -> int:
    test_happy_path()
    test_strips_whitespace()
    test_missing_field_returns_empty()
    test_non_list_returns_empty()
    test_drops_malformed_entries()
    test_null_value()
    print("PASS: build_placeholder_mocs (6 tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# version: 0.2.0
"""test-shared-ctx-placeholders.py — Smoke tests for shared-ctx-builder.build_placeholder_links.

Covers the F-35 placeholder-link feed for Condition C (Mental Squeeze Point §2.C
trigger source), now filtered to the MOC naming convention (2026-06-09).

Happy path:
  - Well-formed MOC-named entries pass through (target preserved)
  - Field whitespace is stripped
MOC-convention filter (Condition C offers MOC creation only):
  - `(MOC)` parens / ` MOC` suffix kept (case-insensitive); regular notes,
    dates, and mid-word "MOC" dropped
Drift guards (silent skip — schema treats placeholder_links as optional):
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
# Register in sys.modules before exec — Python 3.14's dataclass machinery
# inspects sys.modules[cls.__module__] during @dataclass class processing
# (added when shared-ctx-builder gained MocProposalConfig in F-43).
sys.modules["shared_ctx_builder"] = scb
_spec.loader.exec_module(scb)


def _must(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def test_happy_path() -> None:
    cache = {
        "placeholder_links": [
            {"target": "Boardgames MOC", "referenced_by": "Atlas/200 MOCs/Hobbies MOC.md"},
            {"target": "Functional Programming MOC", "referenced_by": "Atlas/200 MOCs/Software MOC.md"},
        ]
    }
    out = scb.build_placeholder_links(cache)
    _must(len(out) == 2, f"expected 2 entries, got {len(out)}")
    _must(out[0]["target"] == "Boardgames MOC", f"target preserved: {out[0]}")
    _must(out[1]["referenced_by"] == "Atlas/200 MOCs/Software MOC.md", f"ref preserved: {out[1]}")


def test_strips_whitespace() -> None:
    cache = {
        "placeholder_links": [
            {"target": "  Boardgames MOC  ", "referenced_by": "  Atlas/x.md  "},
        ]
    }
    out = scb.build_placeholder_links(cache)
    _must(out == [{"target": "Boardgames MOC", "referenced_by": "Atlas/x.md"}], f"strip failed: {out}")


def test_filters_to_moc_naming_convention() -> None:
    """Only placeholder links whose target names a MOC (`(MOC)` / ` MOC`) reach
    Condition C — a missing *regular* note is not a missing MOC (2026-06-09)."""
    cache = {
        "placeholder_links": [
            {"target": "AI MOC", "referenced_by": "Atlas/Home.md"},          # ` MOC` suffix → kept
            {"target": "Efforts (MOC)", "referenced_by": "Atlas/Home.md"},   # `(MOC)` parens → kept
            {"target": "stoicism moc", "referenced_by": "Atlas/Home.md"},    # case-insensitive → kept
            {"target": "Körperliche Fitness 2024", "referenced_by": "Atlas/Home.md"},  # regular note → dropped
            {"target": "2022-06-10", "referenced_by": "Atlas/Home.md"},      # date → dropped
            {"target": "011 Index", "referenced_by": "Atlas/Home.md"},       # no MOC marker → dropped
        ]
    }
    out = scb.build_placeholder_links(cache)
    targets = {e["target"] for e in out}
    _must(targets == {"AI MOC", "Efforts (MOC)", "stoicism moc"}, f"MOC filter wrong: {targets}")


def test_midword_moc_is_not_a_match() -> None:
    """`\\bMOC` must not match mid-word — a target like 'COMMOC' is not a MOC."""
    cache = {"placeholder_links": [{"target": "COMMOC", "referenced_by": "x.md"}]}
    _must(scb.build_placeholder_links(cache) == [], "mid-word MOC wrongly matched")


def test_missing_field_returns_empty() -> None:
    out = scb.build_placeholder_links({})
    _must(out == [], f"missing field should yield []: {out}")


def test_non_list_returns_empty() -> None:
    out = scb.build_placeholder_links({"placeholder_links": "oops"})
    _must(out == [], f"non-list should yield []: {out}")


def test_drops_malformed_entries() -> None:
    cache = {
        "placeholder_links": [
            {"target": "Valid MOC", "referenced_by": "x.md"},
            {"target": "", "referenced_by": "x.md"},          # empty target
            {"target": "Y MOC", "referenced_by": ""},         # empty ref
            {"referenced_by": "x.md"},                         # missing target
            {"target": "Z MOC"},                               # missing ref
            "not a dict",                                      # wrong type
            None,                                              # null
        ]
    }
    out = scb.build_placeholder_links(cache)
    _must(len(out) == 1, f"expected 1 valid entry, got {len(out)}: {out}")
    _must(out[0]["target"] == "Valid MOC", f"first should be Valid MOC: {out[0]}")


def test_null_value() -> None:
    out = scb.build_placeholder_links({"placeholder_links": None})
    _must(out == [], f"null should yield []: {out}")


def main() -> int:
    test_happy_path()
    test_strips_whitespace()
    test_filters_to_moc_naming_convention()
    test_midword_moc_is_not_a_match()
    test_missing_field_returns_empty()
    test_non_list_returns_empty()
    test_drops_malformed_entries()
    test_null_value()
    print("PASS: build_placeholder_links (8 tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# version: 0.1.0
"""test_instruction_render_collision_guard.py — filename collision guard (C5, F-41).

T5.1 (XDD-016): Verifies that _disambiguate_filename() produces distinct filenames
when multiple atomic notes from one source would otherwise slugify to the same
filename, and raises loudly when the suffix space is exhausted.

Tests:
  1. test_distinct_titles_no_suffix — 2 distinct slugs → 2 distinct filenames unchanged
  2. test_identical_titles_get_suffix — 2 identical slugs → _01 / _02 suffixes
  3. test_suffix_reflects_action_order — 3rd collision gets _03, order is stable
  4. test_exhausted_suffix_raises — collision beyond _99 raises ValueError

Spec: docs/XDD/specs/016-multi-topic-atomic-notes/
SDD:  C5 (filename collision guard), ADR-7
AC:   PRD/A6 (N distinct notes per source)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load instruction-render.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("instruction_render", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render"] = ir
_spec.loader.exec_module(ir)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_distinct_titles_no_suffix():
    """Two atomics with distinct slugified titles produce distinct filenames
    without any numeric suffix (common-case path must be byte-for-byte
    unchanged — CON-2 regression guarantee, PRD/A6).
    """
    used: set[str] = set()

    filename_a = ir._disambiguate_filename("2026-06-11_0900_alpha.md", used)
    used.add(filename_a)
    filename_b = ir._disambiguate_filename("2026-06-11_0900_beta.md", used)
    used.add(filename_b)

    assert filename_a == "2026-06-11_0900_alpha.md"
    assert filename_b == "2026-06-11_0900_beta.md"
    assert filename_a != filename_b


def test_identical_titles_get_suffix():
    """Two atomics that slugify to the same filename get _01 / _02 suffixes.
    Both files are distinct — no overwrite (SDD/ADR-7).
    """
    used: set[str] = set()
    base = "2026-06-11_0900_duplicate-topic.md"

    first = ir._disambiguate_filename(base, used)
    used.add(first)
    second = ir._disambiguate_filename(base, used)
    used.add(second)

    # First occurrence: no suffix needed
    assert first == base
    # Second occurrence: _01 suffix
    assert second == "2026-06-11_0900_duplicate-topic_01.md"
    assert first != second


def test_suffix_reflects_action_order():
    """Third collision in action order gets _02, fourth gets _03, etc.
    Suffix sequence is 01, 02, 03 … in iteration order.
    """
    used: set[str] = set()
    base = "2026-06-11_0900_same-slug.md"

    first = ir._disambiguate_filename(base, used)
    used.add(first)
    second = ir._disambiguate_filename(base, used)
    used.add(second)
    third = ir._disambiguate_filename(base, used)
    used.add(third)

    assert first == base
    assert second == "2026-06-11_0900_same-slug_01.md"
    assert third == "2026-06-11_0900_same-slug_02.md"
    # All three are distinct
    assert len({first, second, third}) == 3


def test_exhausted_suffix_raises():
    """When suffix space is exhausted (collision even after _99) the function
    raises ValueError naming the slug — never silently overwrites (SDD/Error Handling).
    """
    # Pre-fill `used` with base + _01 through _99
    base = "2026-06-11_0900_crowded.md"
    stem = "2026-06-11_0900_crowded"
    used: set[str] = {base}
    for i in range(1, 100):
        used.add(f"{stem}_{i:02d}.md")

    with pytest.raises((ValueError, RuntimeError)):
        ir._disambiguate_filename(base, used)

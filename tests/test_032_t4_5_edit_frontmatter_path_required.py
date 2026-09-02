#!/usr/bin/env python3
# version: 0.1.0
"""test_032_t4_5_edit_frontmatter_path_required.py — edit_frontmatter is path-shape-validated (T4.5).

`_REQUIRED_PATH_FIELDS` in `lib/render_actions.py` drives `_validate_action_paths()`: a kind
absent from the map is silently skipped by the `for field in _REQUIRED_PATH_FIELDS.get(kind, ())`
loop, so a required field on that kind goes unchecked. T4.5 added
`"edit_frontmatter": ("path",)` so a `path`-less `edit_frontmatter` action is now rejected
instead of passing unvalidated.

Spec: docs/XDD/specs/032-up-source-routing/plan/phase-4.md T4.5
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.X` works

from lib.render_actions import _validate_action_paths  # noqa: E402


def test_edit_frontmatter_missing_path_is_rejected():
    """A path-less edit_frontmatter action must be caught, not silently pass.

    Regression guard for T4.5: before the fix, `edit_frontmatter` was absent
    from `_REQUIRED_PATH_FIELDS`, so this action produced zero violations.
    """
    action = {
        "id": "X12",
        "action": "edit_frontmatter",
        "property": "up",
        "operation": "remove",
    }
    violations = _validate_action_paths([action])
    assert len(violations) == 1, f"expected exactly 1 violation, got {violations}"
    assert "missing or empty" in violations[0], violations[0]


def test_edit_frontmatter_with_path_is_accepted():
    """Sanity check: a well-formed edit_frontmatter action passes clean."""
    action = {
        "id": "X13",
        "action": "edit_frontmatter",
        "path": "Atlas/Note.md",
        "property": "up",
        "operation": "remove",
    }
    assert _validate_action_paths([action]) == []

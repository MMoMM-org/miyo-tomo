#!/usr/bin/env python3
# version: 0.1.0
"""test_027_t2_1_two_box_block.py — spec 027 / Phase 2 / T2.1.

Verifies the per-item atomic decision block is the new two-box layout:

  **Decision (atomic note):**
  - [x] Approve
  - [ ] Keep source files
        (don't delete the original(s) after the note is created — you may still need them)

Requirements (ADR-4, PRD F1/F2):
  1. Block has exactly 2 checkbox lines (Approve + Keep source files).
  2. Block uses "source" wording, not "origin".
  3. Block contains NO "Skip" checkbox line.
  4. Block contains NO per-atomic "Delete source" checkbox line.
  5. High-worthiness action renders with [x] Approve; low-worthiness with [ ] Approve.

Spec: docs/XDD/specs/027-suggestions-source-model/
SDD: ADR-4 (two-box block), PRD F1 (unified source wording), F2 (single decision)
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load suggestions-reducer.py (hyphen filename → importlib).
_reducer_spec = importlib.util.spec_from_file_location(
    "suggestions_reducer_t2_1", SCRIPTS_DIR / "suggestions-reducer.py"
)
_reducer_mod = importlib.util.module_from_spec(_reducer_spec)
assert _reducer_spec.loader is not None
sys.modules["suggestions_reducer_t2_1"] = _reducer_mod
_reducer_spec.loader.exec_module(_reducer_mod)

render_create_atomic_note = _reducer_mod.render_create_atomic_note  # type: ignore[attr-defined]


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _action(worthiness: float | None = 0.8) -> dict:
    """Minimal create_atomic_note action with the given atomic_note_worthiness."""
    return {
        "suggested_title": "Sample Note",
        "atomic_note_worthiness": worthiness,
        "template": None,
        "location": None,
        "candidate_mocs": [],
        "tags_to_add": [],
        "classification": {},
        "alternatives": [],
    }


def _decision_block_lines(md: str) -> list[str]:
    """Extract lines from the **Decision (atomic note):** block.

    The block is terminal — no section follows it in the atomic render, so there
    is no closing **bold header** to rely on.  We end the block on either:
      - a new **bold header** line (defensive, in case layout changes), or
      - a blank line that appears after at least one checkbox has been seen.
    """
    in_block = False
    saw_checkbox = False
    block_lines: list[str] = []
    for line in md.splitlines():
        if line.strip() == "**Decision (atomic note):**":
            in_block = True
            continue
        if in_block:
            if line.startswith("**") and line.endswith("**"):
                break
            if line.strip() == "" and saw_checkbox:
                break
            if line.startswith("- ["):
                saw_checkbox = True
            block_lines.append(line)
    return block_lines


def _checkbox_lines(md: str) -> list[str]:
    """Return only lines matching the checkbox pattern within the decision block."""
    return [
        line for line in _decision_block_lines(md)
        if re.match(r"- \[[ x]\] ", line)
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_decision_block_has_exactly_two_checkbox_lines():
    """ADR-4: per-item atomic block must have exactly 2 checkbox lines.

    Approve + Keep source files — no Skip, no Delete source.
    """
    md = render_create_atomic_note(_action(), "my-note", " (MOC)")
    boxes = _checkbox_lines(md)
    assert len(boxes) == 2, (
        f"Expected 2 checkbox lines in the decision block, got {len(boxes)}: {boxes!r}\n"
        f"Full output:\n{md}"
    )


def test_decision_block_has_approve_line():
    """Decision block contains the Approve checkbox."""
    md = render_create_atomic_note(_action(), "my-note", " (MOC)")
    boxes = _checkbox_lines(md)
    approve_lines = [line for line in boxes if "Approve" in line]
    assert len(approve_lines) == 1, (
        f"Expected 1 Approve line, got {approve_lines!r}"
    )


def test_decision_block_has_keep_source_files_line():
    """Decision block contains 'Keep source files' — not 'Keep origin' (PRD F1)."""
    md = render_create_atomic_note(_action(), "my-note", " (MOC)")
    boxes = _checkbox_lines(md)
    keep_lines = [line for line in boxes if "Keep source files" in line]
    assert len(keep_lines) == 1, (
        f"Expected 1 'Keep source files' checkbox, got {keep_lines!r} from boxes {boxes!r}"
    )


def test_decision_block_no_origin_wording():
    """Decision block must not use 'origin' in the keep control — uses 'source' (PRD F1)."""
    md = render_create_atomic_note(_action(), "my-note", " (MOC)")
    block_lines = _decision_block_lines(md)
    origin_in_control = [
        line for line in block_lines
        if re.match(r"- \[[ x]\] ", line) and "origin" in line.lower()
    ]
    assert origin_in_control == [], (
        f"Decision block contains 'origin' in a checkbox line: {origin_in_control!r}"
    )


def test_decision_block_no_skip_checkbox():
    """Decision block must NOT have a Skip checkbox (not-approving IS skipping, ADR-4)."""
    md = render_create_atomic_note(_action(), "my-note", " (MOC)")
    boxes = _checkbox_lines(md)
    skip_lines = [line for line in boxes if re.search(r"\bSkip\b", line)]
    assert skip_lines == [], (
        f"Decision block must not contain a 'Skip' checkbox; got {skip_lines!r}"
    )


def test_decision_block_no_per_atomic_delete_source():
    """Decision block must NOT have a per-atomic Delete source checkbox (ADR-4).

    Junk delete-only flow lives in the skipped-items path, not here.
    """
    md = render_create_atomic_note(_action(), "my-note", " (MOC)")
    boxes = _checkbox_lines(md)
    delete_lines = [line for line in boxes if "Delete source" in line]
    assert delete_lines == [], (
        f"Decision block must not contain 'Delete source'; got {delete_lines!r}"
    )


def test_high_worthiness_pre_approves():
    """Worthiness >= 0.5 → Approve is pre-ticked [x]."""
    md = render_create_atomic_note(_action(worthiness=0.8), "my-note", " (MOC)")
    assert "- [x] Approve" in md, (
        "Expected '- [x] Approve' for high-worthiness action"
    )


def test_low_worthiness_leaves_approve_unticked():
    """Worthiness < 0.5 → Approve starts unchecked [ ]."""
    md = render_create_atomic_note(_action(worthiness=0.3), "my-note", " (MOC)")
    assert "- [ ] Approve" in md, (
        "Expected '- [ ] Approve' for low-worthiness action"
    )


def test_keep_source_files_continuation_text_present():
    """The parenthetical explanation for 'Keep source files' must be present."""
    md = render_create_atomic_note(_action(), "my-note", " (MOC)")
    assert "don't delete the original(s) after the note is created" in md, (
        "Expected the 'Keep source files' explanation text in the rendered block"
    )

#!/usr/bin/env python3
# version: 0.1.0
"""test_inbox_analyst_no_condition_b.py — Contract tests for T3.2 (spec 021, F-34).

Verifies that Condition B (Accumulation cluster trigger) has been removed from
inbox-analyst.md Step 4, while Condition A (Classification Guard) and Condition C
(Placeholder MOC trigger) remain intact with their required instructions.

These tests are RED against the current agent (which still has Condition B),
and GREEN after the T3.2 edit.

Since inbox-analyst.md is an LLM-loaded runtime agent spec (not a Python module),
the correct RED-able approach is contract tests on the prose file.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
AGENT_PATH = REPO_ROOT / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md"
BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "021-ac-baseline" / "ac-baseline.json"
FIXTURE_SRC = REPO_ROOT / "tests" / "fixtures" / "test-015-t4-1"
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"


def _agent_text() -> str:
    assert AGENT_PATH.exists(), f"Agent file not found: {AGENT_PATH}"
    return AGENT_PATH.read_text()


def _step4_text() -> str:
    """Extract the Step 4 section from the agent file."""
    text = _agent_text()
    step4_start = text.find("### Step 4")
    step5_start = text.find("### Step 5")
    assert step4_start != -1, "### Step 4 not found in agent file"
    assert step5_start != -1, "### Step 5 not found in agent file"
    return text[step4_start:step5_start]


# ---------------------------------------------------------------------------
# B-removal assertions (RED against current file)
# ---------------------------------------------------------------------------

def test_condition_b_accumulation_trigger_absent():
    """inbox-analyst.md Step 4 must NOT contain 'Accumulation cluster trigger' (Condition B removed)."""
    step4 = _step4_text()
    assert "Accumulation cluster trigger" not in step4, (
        "Step 4 still contains 'Accumulation cluster trigger' — Condition B must be removed (T3.2)"
    )


def test_condition_b_accumulation_index_reference_absent():
    """inbox-analyst.md Step 4 must NOT reference accumulation_index (Condition B removed)."""
    step4 = _step4_text()
    assert "accumulation_index" not in step4, (
        "Step 4 still references 'accumulation_index' — all Condition B text must be removed (T3.2)"
    )


def test_a7_vs_b_strict_block_absent():
    """The A7-vs-B STRICT block must be absent after Condition B removal."""
    step4 = _step4_text()
    # The STRICT block that guarded B was specifically labelled 'A7 (Condition C wins over Condition B)'
    assert "Condition C wins over Condition B" not in step4, (
        "The A7-vs-B STRICT block still present — it must be removed along with Condition B (T3.2)"
    )


def test_no_accumulation_index_anywhere_in_agent():
    """No accumulation_index reference remains ANYWHERE in inbox-analyst.md."""
    text = _agent_text()
    assert "accumulation_index" not in text, (
        "inbox-analyst.md still references 'accumulation_index' — must be fully cleaned (T3.2)"
    )


# ---------------------------------------------------------------------------
# Condition A (Classification Guard) regression — must remain intact
# ---------------------------------------------------------------------------

def test_condition_a_classification_guard_present():
    """Condition A (Classification Guard) instructions must remain intact after B removal."""
    step4 = _step4_text()
    assert "Classification Guard" in step4, (
        "Step 4 is missing 'Classification Guard' — Condition A must NOT be removed (T3.2 regression)"
    )


def test_condition_a_is_classification_instruction_present():
    """Condition A must still instruct never pre-checking is_classification MOCs."""
    step4 = _step4_text()
    assert "is_classification" in step4, (
        "Step 4 is missing 'is_classification' reference — Condition A guard intact check failed"
    )


def test_condition_a_needs_new_moc_instruction_present():
    """Condition A must still instruct setting needs_new_moc when all matches are classification-layer."""
    step4 = _step4_text()
    assert "needs_new_moc" in step4, (
        "Step 4 is missing 'needs_new_moc' — Condition A fallback instruction must remain"
    )


# ---------------------------------------------------------------------------
# Condition C (Placeholder MOC trigger) regression — must remain intact
# ---------------------------------------------------------------------------

def test_condition_c_placeholder_trigger_present():
    """Condition C (Placeholder MOC trigger) must remain intact after B removal."""
    step4 = _step4_text()
    assert "Placeholder MOC trigger" in step4, (
        "Step 4 is missing 'Placeholder MOC trigger' — Condition C must NOT be removed (T3.2 regression)"
    )


def test_condition_c_placeholder_mocs_reference_present():
    """Condition C must still reference placeholder_mocs."""
    step4 = _step4_text()
    assert "placeholder_mocs" in step4, (
        "Step 4 missing 'placeholder_mocs' reference — Condition C text must remain"
    )


def test_condition_c_verbatim_casing_instruction_present():
    """Condition C must still instruct verbatim casing for proposed_moc_topic (F4#2)."""
    step4 = _step4_text()
    # The F4#2 instruction: "use the placeholder name verbatim, preserving casing"
    assert "verbatim" in step4, (
        "Step 4 missing 'verbatim' casing instruction — F4#2 (Condition C casing) must be preserved"
    )
    assert "casing" in step4, (
        "Step 4 missing 'casing' instruction — F4#2 (Condition C preserving casing) must be preserved"
    )


def test_condition_c_placeholder_wins_precedence_present():
    """Condition C must still specify placeholder wins over Classification-Guard fallback (F4#4)."""
    step4 = _step4_text()
    # The F4#4 instruction: placeholder takes precedence over Classification-Guard
    assert "takes precedence" in step4, (
        "Step 4 missing 'takes precedence' — F4#4 (placeholder-wins precedence) must be preserved"
    )


def test_condition_c_silent_skip_when_absent_present():
    """Condition C must still instruct skipping silently when placeholder_mocs is absent/empty."""
    step4 = _step4_text()
    assert "absent or empty" in step4, (
        "Step 4 missing 'absent or empty' guard for placeholder_mocs — Condition C silent-skip must remain"
    )


# ---------------------------------------------------------------------------
# Version check
# ---------------------------------------------------------------------------

def test_agent_version_bumped_for_t32():
    """inbox-analyst.md version must be > 0.13.0 (bumped in T3.2)."""
    text = _agent_text()
    match = re.search(r"#\s*version:\s*(\d+)\.(\d+)\.(\d+)", text)
    assert match, "inbox-analyst.md must have a '# version: X.Y.Z' comment"
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    version_tuple = (major, minor, patch)
    assert version_tuple > (0, 13, 0), (
        f"inbox-analyst.md version {major}.{minor}.{patch} must be > 0.13.0 (T3.2 bump required)"
    )


def test_agent_version_no_parenthetical():
    """Version comment must be number-only — no parenthetical after the version number."""
    text = _agent_text()
    for line in text.splitlines():
        if "version:" in line and re.search(r"#\s*version:", line):
            assert "(" not in line, (
                f"Version comment must be number-only, no parenthetical. Found: {line!r}"
            )


# ---------------------------------------------------------------------------
# Golden-baseline guard: build_mocs + build_placeholder_mocs byte-equal to T3.0
# ---------------------------------------------------------------------------

def test_golden_baseline_mocs_and_placeholder_mocs_unchanged():
    """build_mocs + build_placeholder_mocs must produce byte-identical output for
    the 4 T3.0 baseline fixtures after Condition B removal (mocs/placeholder_mocs
    arrays only — agent text sections will legitimately change)."""
    if not BASELINE_PATH.exists():
        import pytest
        pytest.skip(f"Baseline not found: {BASELINE_PATH}")

    # Load shared-ctx-builder
    sys.path.insert(0, str(SCRIPTS_DIR))
    _spec = importlib.util.spec_from_file_location(
        "shared_ctx_builder", SCRIPTS_DIR / "shared-ctx-builder.py"
    )
    scb = importlib.util.module_from_spec(_spec)
    sys.modules["shared_ctx_builder"] = scb
    _spec.loader.exec_module(scb)

    baseline = json.loads(BASELINE_PATH.read_text())
    baseline_by_fixture = {e["fixture"]: e for e in baseline["fixtures"]}

    SCENARIOS = [
        "scenario_a_accumulation_match.json",
        "scenario_b_no_match.json",
        "scenario_c_placeholder_wins.json",
        "scenario_d_absent_index.json",
    ]

    for fname in SCENARIOS:
        path = FIXTURE_SRC / fname
        if not path.exists():
            import pytest
            pytest.skip(f"Fixture not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        ctx = data["shared_ctx"]

        cache: dict = {
            "map_notes": [
                {"path": m["path"], "title": m["title"], "topics": m["topics"]}
                for m in ctx.get("mocs", [])
            ],
        }
        if "placeholder_mocs" in ctx:
            cache["placeholder_mocs"] = ctx["placeholder_mocs"]

        built_mocs = scb.build_mocs(cache)
        built_placeholders = scb.build_placeholder_mocs(cache)

        expected = baseline_by_fixture[fname]
        assert built_mocs == expected["mocs"], (
            f"Fixture {fname}: build_mocs() output changed after T3.2\n"
            f"  expected: {expected['mocs']}\n"
            f"  got:      {built_mocs}"
        )
        assert built_placeholders == expected["placeholder_mocs"], (
            f"Fixture {fname}: build_placeholder_mocs() output changed after T3.2\n"
            f"  expected: {expected['placeholder_mocs']}\n"
            f"  got:      {built_placeholders}"
        )

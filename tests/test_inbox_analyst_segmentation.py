#!/usr/bin/env python3
# version: 0.1.0
"""test_inbox_analyst_segmentation.py — Contract tests for T2.1 (XDD 016, F-41).

Verifies that inbox-analyst.md gained a Step 7.5 topical-segmentation section and
that Step 9 stamps a shared source_stem on every emitted create_atomic_note.

inbox-analyst.md is an LLM-loaded runtime agent spec (not a Python module), so the
RED-able approach is contract assertions on the prose file plus a jsonschema
validation of a representative multi-atomic result against the item-result schema.

These tests are RED against the current 0.15.0 file (no Step 7.5, no source_stem
stamping directive) and GREEN after the T2.1 edit.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
AGENT_PATH = REPO_ROOT / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "item-result.schema.json"


def _agent_text() -> str:
    assert AGENT_PATH.exists(), f"Agent file not found: {AGENT_PATH}"
    return AGENT_PATH.read_text()


def _step75_text() -> str:
    """Extract the Step 7.5 section (between '### Step 7.5' and '### Step 8')."""
    text = _agent_text()
    start = text.find("### Step 7.5")
    end = text.find("### Step 8")
    assert start != -1, "### Step 7.5 not found in agent file"
    assert end != -1, "### Step 8 not found in agent file"
    assert start < end, "### Step 7.5 must appear before ### Step 8"
    return text[start:end]


def _step8b_eval2_text() -> str:
    """Extract the Step 8b Evaluation 2 block (between 'Evaluation 2 —' and 'Log update entry shape')."""
    text = _agent_text()
    start = text.find("**Evaluation 2 — Log eligibility:**")
    end = text.find("Log update entry shape:")
    assert start != -1, "'**Evaluation 2 — Log eligibility:**' not found in agent file"
    assert end != -1, "'Log update entry shape:' not found in agent file"
    return text[start:end]


def _step9_text() -> str:
    """Extract the Step 9 section (between '### Step 9' and '### Step 10')."""
    text = _agent_text()
    start = text.find("### Step 9")
    end = text.find("### Step 10")
    assert start != -1, "### Step 9 not found in agent file"
    assert end != -1, "### Step 10 not found in agent file"
    return text[start:end]


# ---------------------------------------------------------------------------
# Step 7.5 — Topical segmentation section (RED against current file)
# ---------------------------------------------------------------------------

def test_step_75_section_exists():
    """inbox-analyst.md must contain a '### Step 7.5' segmentation section."""
    assert "### Step 7.5" in _agent_text(), (
        "inbox-analyst.md is missing the '### Step 7.5' topical-segmentation section (T2.1)"
    )


def test_step_75_has_200_word_gate():
    """Step 7.5 must gate segmentation on a >200 word threshold (ADR-3 cost gate)."""
    step = _step75_text()
    assert "200" in step, "Step 7.5 missing the 200-word threshold number (ADR-3 cost gate)"
    assert "word" in step.lower(), "Step 7.5 missing word-count gate language"


def test_step_75_per_thread_worthiness_threshold():
    """Step 7.5 must score EACH thread with its own '≥ 0.5' worthiness gate (OQ3)."""
    step = _step75_text()
    assert "0.5" in step, "Step 7.5 missing per-thread '0.5' worthiness threshold (OQ3)"
    assert "thread" in step.lower(), "Step 7.5 must talk about threads"


def test_step_75_per_thread_own_text_scoring():
    """Step 7.5 must instruct scoring each thread against its OWN full thread text (OQ3)."""
    step = _step75_text().lower()
    assert "each thread" in step or "per-thread" in step or "per thread" in step, (
        "Step 7.5 must instruct per-thread scoring (each thread gets its own worthiness)"
    )


def test_step_75_has_worked_examples():
    """Step 7.5 must include 2-3 concrete worked examples (imperative form)."""
    step = _step75_text().lower()
    # Worked examples are introduced with 'example' — require at least two occurrences.
    occurrences = step.count("example")
    assert occurrences >= 2, (
        f"Step 7.5 must contain 2-3 worked examples; found {occurrences} 'example' mention(s)"
    )


def test_step_75_default_single_thread_path_preserved():
    """≤200-word items must fall through to a single default thread (CON-2 / A1 regression)."""
    step = _step75_text()
    # The gate number must be present.
    assert "200" in step, (
        "Step 7.5 must contain the '200' word-count gate for the short-item pass-through (CON-2/A1)"
    )
    # The pass-through anchor reuses the Step 7 score directly — pin the exact text.
    assert "The Step 7 score you already computed IS" in step, (
        "Step 7.5 must preserve the pass-through text "
        "'The Step 7 score you already computed IS' for ≤200-word items (CON-2/A1)"
    )


def test_step_75_segmentation_failure_fallback():
    """Segmentation ambiguity/failure must fall back to a single default thread (never lose item)."""
    step = _step75_text().lower()
    assert "fall back" in step or "fallback" in step or "fall-back" in step, (
        "Step 7.5 must specify a fallback to a single thread on segmentation failure/ambiguity"
    )


def test_step_75_sub_worthy_threads_one_update_daily():
    """OQ4: sub-worthy threads contribute to ONE update_daily — 'emit at most one' enforcement."""
    step = _step75_text()
    assert "update_daily" in step, (
        "Step 7.5 must route sub-worthy threads into update_daily (OQ4)"
    )
    # Pin the exact enforcement phrase — loose disjunction (only/single/one) is too weak.
    assert "emit at most one" in step, (
        "Step 7.5 must contain the exact phrase 'emit at most one' to enforce the single-update_daily "
        "rule for sub-worthy threads (OQ4)"
    )


def test_step_75_sub_worthy_routing_gated_on_step8b_daily_path():
    """C2: sub-worthy→update_daily route must be gated on Step 8b being active; when closed, fall
    back to the Step 9 default atomic so the item is never lost."""
    step = _step75_text()
    # The spec must explicitly handle the "no daily path" branch.
    assert "Step 8b daily path is NOT active" in step, (
        "Step 7.5 must explicitly handle the case where the Step 8b daily path is NOT active "
        "(no date_relevance / no daily_notes config) — C2 requires a named fallback branch"
    )
    # When the daily path is closed and no thread is atomic-worthy, fall back to default atomic.
    assert "create_atomic_note" in step, (
        "Step 7.5 must specify create_atomic_note as the fallback when Step 8b daily path is "
        "inactive and no thread is atomic-worthy (C2 — never lose the item)"
    )


# ---------------------------------------------------------------------------
# Step 8b Evaluation 2 — log_link vs log_entry must key on thread set (C1)
# ---------------------------------------------------------------------------

def test_step8b_eval2_keys_on_any_thread_not_single_scalar():
    """C1: Step 8b Evaluation 2 must gate log_link on ANY thread being atomic-worthy,
    not on a single scalar atomic_note_worthiness."""
    eval2 = _step8b_eval2_text()
    # Must reference the thread set ("ANY thread"), not a bare scalar.
    assert "ANY thread" in eval2, (
        "Step 8b Evaluation 2 must key the log_link decision on 'ANY thread' being atomic-worthy "
        "(not a single scalar atomic_note_worthiness) — C1"
    )


def test_step8b_eval2_forbids_log_entry_when_any_thread_atomic():
    """C1: Step 8b Evaluation 2 must explicitly forbid log_entry when any thread is atomic-worthy."""
    eval2 = _step8b_eval2_text()
    assert "log_entry" in eval2 and "Never emit" in eval2, (
        "Step 8b Evaluation 2 must say 'Never emit log_entry' when any thread is atomic-worthy — "
        "consistent with Step 9 coexistence table (C1)"
    )


# ---------------------------------------------------------------------------
# Step 9 — source_stem stamping on every create_atomic_note (ADR-4)
# ---------------------------------------------------------------------------

def test_step_9_stamps_source_stem_on_every_atomic():
    """Step 9 must stamp source_stem on every emitted create_atomic_note (ADR-4 uniformity)."""
    step9 = _step9_text()
    assert "source_stem" in step9, (
        "Step 9 must stamp 'source_stem' on every create_atomic_note (ADR-4)"
    )


def test_step_9_iterates_threads():
    """Step 9 atomic emission must iterate over threads (N>=1), not a single fixed note."""
    step9 = _step9_text().lower()
    assert "thread" in step9, (
        "Step 9 atomic-note emission must iterate over threads from Step 7.5 (N>=1)"
    )


def test_step_9_coexistence_rules_preserved():
    """Step 9 must keep the existing coexistence rules table (regression)."""
    step9 = _step9_text()
    assert "Coexistence rules" in step9, "Step 9 lost its coexistence rules table"
    assert "log_link" in step9 and "log_entry" in step9, (
        "Step 9 coexistence table must still reference log_link and log_entry"
    )


def test_step_9_reason_field_rule_preserved():
    """Step 9 must keep the per-update reason-field rule (regression)."""
    step9 = _step9_text()
    assert "reason" in step9, "Step 9 lost the reason-field rule"


# ---------------------------------------------------------------------------
# Version checks
# ---------------------------------------------------------------------------

def test_agent_version_bumped_for_t21():
    """inbox-analyst.md version must be > 0.15.0 (bumped in T2.1)."""
    match = re.search(r"#\s*version:\s*(\d+)\.(\d+)\.(\d+)", _agent_text())
    assert match, "inbox-analyst.md must have a '# version: X.Y.Z' comment"
    version_tuple = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    assert version_tuple > (0, 15, 0), (
        f"inbox-analyst.md version {version_tuple} must be > 0.15.0 (T2.1 bump required)"
    )


def test_agent_version_no_parenthetical():
    """Version comment must be number-only — no parenthetical after the version number."""
    for line in _agent_text().splitlines():
        if "version:" in line and re.search(r"#\s*version:", line):
            assert "(" not in line, (
                f"Version comment must be number-only, no parenthetical. Found: {line!r}"
            )


# ---------------------------------------------------------------------------
# Schema fixture — a 2x create_atomic_note result sharing one source_stem validates
# ---------------------------------------------------------------------------

def _multi_atomic_result() -> dict:
    """Representative multi-thread result: two atomics from one source_stem."""
    shared_stem = "2026-06-10 voice memo"

    def atomic(title: str) -> dict:
        return {
            "kind": "create_atomic_note",
            "source_stem": shared_stem,
            "suggested_title": title,
            "template": "Atomic Note.md",
            "location": "Atlas/202 Notes/",
            "candidate_mocs": [],
            "tags_to_add": [],
            "atomic_note_worthiness": 0.7,
        }

    return {
        "schema_version": "1",
        "stem": shared_stem,
        "path": "00 Inbox/2026-06-10 voice memo.md",
        "type": "voice-transcript",
        "type_confidence": 0.9,
        "date_relevance": None,
        "actions": [
            atomic("Dentist appointment follow-up plan"),
            atomic("PKM segmentation architecture memo"),
        ],
    }


def test_multi_atomic_shared_source_stem_validates_against_schema():
    """A 2x create_atomic_note result sharing one source_stem validates against the schema."""
    schema = json.loads(SCHEMA_PATH.read_text())
    result = _multi_atomic_result()
    jsonschema.validate(instance=result, schema=schema)

    # Both atomics must carry the SAME source_stem (provenance grouping key).
    stems = {a["source_stem"] for a in result["actions"]}
    assert stems == {"2026-06-10 voice memo"}, (
        "Both atomics from one item must share the same source_stem"
    )


def test_atomic_without_source_stem_is_rejected_by_schema():
    """An atomic missing source_stem must FAIL schema validation (ADR-4 required-on-all)."""
    schema = json.loads(SCHEMA_PATH.read_text())
    result = _multi_atomic_result()
    del result["actions"][0]["source_stem"]
    try:
        jsonschema.validate(instance=result, schema=schema)
    except jsonschema.ValidationError:
        return
    raise AssertionError(
        "Schema accepted a create_atomic_note without source_stem — ADR-4 requires it on ALL atomics"
    )

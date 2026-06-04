#!/usr/bin/env python3
# version: 0.1.0
"""test_inbox_analyst_accumulation_contract.py — Fixture-driven contract check for
inbox-analyst Step 4 Accumulation cluster trigger (spec 015, T4.1 / F-34 Condition B).

Since inbox-analyst.md is an LLM-loaded runtime agent spec (not a Python module),
there is no interpreter to invoke. These tests validate:
  1. Fixture schema integrity — each scenario fixture is valid JSON and carries the
     required contract fields.
  2. Agent-spec text contract — the accumulation trigger block in inbox-analyst.md
     contains every imperative required by PRD A3/A6/A7 and the SDD Secondary Flow.
  3. A7 precedence — the spec text explicitly conditions the Condition-B block on
     `proposed_moc_topic` not already being set (i.e., the placeholder check ran
     first and may have claimed it).
  4. A6 graceful skip — the spec text explicitly guards on `accumulation_index`
     being present before scanning.

The four fixtures (scenario_a through scenario_d) encode the expected behaviour for
the four cases called out in T4.1, serving as living documentation of the contract.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures" / "test-015-t4-1"
AGENT_PATH = REPO_ROOT / "tomo" / "dot_claude" / "agents" / "inbox-analyst.md"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    assert path.exists(), f"Fixture not found: {path}"
    data = json.loads(path.read_text())
    return data


def _agent_text() -> str:
    assert AGENT_PATH.exists(), f"Agent file not found: {AGENT_PATH}"
    return AGENT_PATH.read_text()


# ---------------------------------------------------------------------------
# Fixture integrity — all four scenario fixtures exist and have required keys
# ---------------------------------------------------------------------------

SCENARIO_FILES = [
    "scenario_a_accumulation_match.json",
    "scenario_b_no_match.json",
    "scenario_c_placeholder_wins.json",
    "scenario_d_absent_index.json",
]


def test_all_scenario_fixtures_exist():
    """All four scenario fixture files are present in the fixtures directory."""
    for fname in SCENARIO_FILES:
        path = FIXTURES_DIR / fname
        assert path.exists(), f"Missing fixture file: {path}"


def test_fixtures_have_required_keys():
    """Every scenario fixture has: shared_ctx, item, expected_result, _contract."""
    for fname in SCENARIO_FILES:
        data = _load_fixture(fname)
        for required in ("shared_ctx", "item", "expected_result", "_contract"):
            assert required in data, (
                f"Fixture {fname!r} missing required key {required!r}"
            )


def test_shared_ctx_fixtures_are_schema_valid():
    """shared_ctx in each fixture satisfies minimum required fields from shared-ctx.schema.json."""
    required_fields = {"schema_version", "run_id", "mocs", "tag_prefixes", "classification_keywords"}
    for fname in SCENARIO_FILES:
        data = _load_fixture(fname)
        ctx = data["shared_ctx"]
        missing = required_fields - set(ctx.keys())
        assert not missing, (
            f"Fixture {fname!r} shared_ctx missing required fields: {missing}"
        )


# ---------------------------------------------------------------------------
# Scenario A — accumulation match fires needs_new_moc
# ---------------------------------------------------------------------------

def test_scenario_a_contract_match_fires_trigger():
    """Scenario A: when topic matches accumulation key, contract expects needs_new_moc=true."""
    data = _load_fixture("scenario_a_accumulation_match.json")
    ctx = data["shared_ctx"]
    item = data["item"]
    expected = data["expected_result"]
    contract = data["_contract"]

    # Validate the fixture is internally consistent
    assert "accumulation_index" in ctx, "Scenario A must have accumulation_index"
    ai = ctx["accumulation_index"]
    assert isinstance(ai, dict) and len(ai) > 0, "Scenario A needs a non-empty accumulation_index"

    topic_tokens = {t.lower().strip() for t in item["dominant_topic_tokens"]}
    index_keys = {k.lower().strip() for k in ai.keys()}
    assert topic_tokens & index_keys, (
        "Scenario A fixture: no overlap between dominant_topic_tokens and accumulation_index keys — "
        "fix the fixture so a match actually exists"
    )

    assert expected["needs_new_moc"] is True, "Scenario A expects needs_new_moc=true"
    assert expected["proposed_moc_topic"] is not None, "Scenario A expects proposed_moc_topic set"
    assert expected["candidate_mocs_preserved"] is True, "Scenario A expects candidate_mocs[] preserved"
    assert contract["then_needs_new_moc"] is True


# ---------------------------------------------------------------------------
# Scenario B — no match, trigger must not fire
# ---------------------------------------------------------------------------

def test_scenario_b_contract_no_match():
    """Scenario B: when topic does not match accumulation key, trigger does not fire."""
    data = _load_fixture("scenario_b_no_match.json")
    ctx = data["shared_ctx"]
    item = data["item"]
    expected = data["expected_result"]

    assert "accumulation_index" in ctx, "Scenario B must have accumulation_index to test the no-match case"
    ai = ctx["accumulation_index"]

    topic_tokens = {t.lower().strip() for t in item["dominant_topic_tokens"]}
    index_keys = {k.lower().strip() for k in ai.keys()}
    assert not (topic_tokens & index_keys), (
        "Scenario B fixture: overlap found between dominant_topic_tokens and accumulation_index keys — "
        "fix the fixture so there is genuinely NO match"
    )

    assert expected["needs_new_moc"] is False, "Scenario B expects needs_new_moc=false"
    assert expected["proposed_moc_topic"] is None, "Scenario B expects proposed_moc_topic=null"
    assert expected["accumulation_trigger_fired"] is False


# ---------------------------------------------------------------------------
# Scenario C — A7 precedence: placeholder wins over accumulation
# ---------------------------------------------------------------------------

def test_scenario_c_contract_placeholder_wins():
    """Scenario C: when both placeholder and accumulation match, placeholder (Condition C) wins (A7)."""
    data = _load_fixture("scenario_c_placeholder_wins.json")
    ctx = data["shared_ctx"]
    item = data["item"]
    expected = data["expected_result"]
    contract = data["_contract"]

    assert "placeholder_mocs" in ctx, "Scenario C must have placeholder_mocs"
    assert "accumulation_index" in ctx, "Scenario C must have accumulation_index"

    topic_tokens = {t.lower().strip() for t in item["dominant_topic_tokens"]}

    # Both should match the item topic
    placeholder_targets = {p["target"].lower().strip() for p in ctx["placeholder_mocs"]}
    index_keys = {k.lower().strip() for k in ctx["accumulation_index"].keys()}

    assert topic_tokens & placeholder_targets, (
        "Scenario C: placeholder_mocs must match item topic"
    )
    assert topic_tokens & index_keys, (
        "Scenario C: accumulation_index must also match item topic"
    )

    # Placeholder wins — casing comes from the placeholder target
    assert expected["needs_new_moc"] is True
    # The winning proposed_moc_topic must match the placeholder target (preserving placeholder casing)
    placeholder_match = next(
        p["target"] for p in ctx["placeholder_mocs"]
        if p["target"].lower().strip() in topic_tokens
    )
    assert expected["proposed_moc_topic"] == placeholder_match, (
        f"Scenario C: proposed_moc_topic must be placeholder target {placeholder_match!r}, "
        f"got {expected['proposed_moc_topic']!r}"
    )
    assert expected["proposed_moc_topic_source"] == "placeholder_mocs"
    assert contract["then_accumulation_must_not_overwrite"] is True


# ---------------------------------------------------------------------------
# Scenario D — A6 absent index: silent skip
# ---------------------------------------------------------------------------

def test_scenario_d_contract_absent_index_silent_skip():
    """Scenario D: when accumulation_index absent, block is a no-op (A6)."""
    data = _load_fixture("scenario_d_absent_index.json")
    ctx = data["shared_ctx"]
    expected = data["expected_result"]
    contract = data["_contract"]

    assert "accumulation_index" not in ctx, (
        "Scenario D shared_ctx must NOT have accumulation_index field"
    )
    assert expected["accumulation_trigger_fired"] is False
    assert expected["needs_new_moc"] is False
    assert expected["proposed_moc_topic"] is None
    assert contract["then_accumulation_trigger"] is False


# ---------------------------------------------------------------------------
# Agent spec text contract checks
# ---------------------------------------------------------------------------

def test_agent_spec_contains_accumulation_trigger_block():
    """inbox-analyst.md Step 4 contains an 'Accumulation cluster trigger' block."""
    text = _agent_text()
    assert "Accumulation cluster trigger" in text, (
        "inbox-analyst.md must contain an 'Accumulation cluster trigger' heading/label in Step 4"
    )


def test_agent_spec_accumulation_block_after_placeholder_block():
    """The Accumulation trigger block appears AFTER the Placeholder MOC trigger in the spec."""
    text = _agent_text()
    placeholder_pos = text.find("Placeholder MOC trigger")
    accum_pos = text.find("Accumulation cluster trigger")

    assert placeholder_pos != -1, "Placeholder MOC trigger block not found"
    assert accum_pos != -1, "Accumulation cluster trigger block not found"
    assert accum_pos > placeholder_pos, (
        "Accumulation cluster trigger must appear AFTER Placeholder MOC trigger in Step 4 "
        f"(placeholder at {placeholder_pos}, accumulation at {accum_pos})"
    )


def test_agent_spec_a6_silent_skip_guarded():
    """The spec guards the Accumulation block on accumulation_index being present (A6)."""
    text = _agent_text()
    # Extract the accumulation block region
    accum_pos = text.find("Accumulation cluster trigger")
    assert accum_pos != -1, "Accumulation cluster trigger block not found"
    # Window must cover the full block including the closing A6 skip line
    # (~730 chars in). 800 chars is sufficient and stays within this block.
    block_region = text[accum_pos:accum_pos + 800]
    # Must mention explicit skip language for the absent/empty case (A6).
    # "present" alone is vacuous — the block's own guard line satisfies it.
    # Require "absent" OR "skip" so removing the A6 skip line fails this test.
    has_guard = (
        "accumulation_index" in block_region
        and ("absent" in block_region or "skip" in block_region)
    )
    assert has_guard, (
        "The Accumulation cluster trigger block must guard on accumulation_index being present "
        f"(A6: absent/empty → skip silently). Block region: {block_region!r}"
    )


def test_agent_spec_a7_no_overwrite_strict():
    """The spec contains a STRICT non-overwrite rule for A7 (Condition C wins)."""
    text = _agent_text()
    # Find the accumulation block
    accum_pos = text.find("Accumulation cluster trigger")
    assert accum_pos != -1, "Accumulation cluster trigger block not found"
    # Look for a STRICT or conditional within 800 chars after the heading
    block_region = text[accum_pos:accum_pos + 800]
    # Must have STRICT marker + proposed_moc_topic non-overwrite rule.
    # The loose "not" / "NOT" match fired on the unrelated "does not erase"
    # bullet in candidate_mocs, leaving the test green even without the STRICT
    # block. Require "STRICT" explicitly so removing the STRICT annotation
    # fails this test.
    has_a7_guard = (
        "STRICT" in block_region
        and "proposed_moc_topic" in block_region
    )
    assert has_a7_guard, (
        "The Accumulation cluster trigger block must include A7 non-overwrite guard: "
        "if proposed_moc_topic already set (by placeholder), do NOT overwrite. "
        f"Block region: {block_region!r}"
    )


def test_agent_spec_sets_needs_new_moc_on_match():
    """The spec sets needs_new_moc=true and proposed_moc_topic on accumulation key match (A3)."""
    text = _agent_text()
    accum_pos = text.find("Accumulation cluster trigger")
    assert accum_pos != -1, "Accumulation cluster trigger block not found"
    block_region = text[accum_pos:accum_pos + 800]
    assert "needs_new_moc" in block_region, (
        "The Accumulation trigger block must set needs_new_moc (A3)"
    )
    assert "proposed_moc_topic" in block_region, (
        "The Accumulation trigger block must set proposed_moc_topic (A3)"
    )


def test_agent_spec_preserves_candidate_mocs():
    """The spec preserves candidate_mocs[] on accumulation trigger (A3)."""
    text = _agent_text()
    accum_pos = text.find("Accumulation cluster trigger")
    assert accum_pos != -1, "Accumulation cluster trigger block not found"
    block_region = text[accum_pos:accum_pos + 800]
    assert "candidate_mocs" in block_region, (
        "The Accumulation trigger block must mention preserving candidate_mocs[] (A3)"
    )


def test_agent_version_bumped():
    """inbox-analyst.md version is greater than 0.12.1 (version was bumped for T4.1)."""
    text = _agent_text()
    match = re.search(r"#\s*version:\s*(\d+)\.(\d+)\.(\d+)", text)
    assert match, "inbox-analyst.md must have a '# version: X.Y.Z' comment"
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    version_tuple = (major, minor, patch)
    assert version_tuple > (0, 12, 1), (
        f"inbox-analyst.md version {major}.{minor}.{patch} must be > 0.12.1 (T4.1 bump required)"
    )


def test_agent_version_no_parenthetical():
    """Version comment must be number-only — no parenthetical after the version number."""
    text = _agent_text()
    for line in text.splitlines():
        if "version:" in line and re.search(r"#\s*version:", line):
            # Must not have a '(' after the version number
            assert "(" not in line, (
                f"Version comment must be number-only, no parenthetical. Found: {line!r}"
            )

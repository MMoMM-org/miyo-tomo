#!/usr/bin/env python3
# version: 0.1.0
"""test_doc_frontmatter.py — Tests for the doc_frontmatter helper module.

Covers T1.2 (F-47 Phase 1): build_tomo_block, parse_tomo_block,
SchemaValidationError, and the dual dev/prod validation mode (ADR-4).

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/
AC:   AC-1.5 (schema validation gates every producer write),
      AC-7.2 (every producer write schema-validated),
      AC-4.5 (source_* extensibility for future F-44/45/46 doc-types)
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.doc_frontmatter` works

import pytest  # noqa: E402

from lib.doc_frontmatter import (  # noqa: E402
    SchemaValidationError,
    build_tomo_block,
    parse_tomo_block,
)


# ---------------------------------------------------------------------------
# build_tomo_block — minimum fields
# ---------------------------------------------------------------------------


def test_build_tomo_block_minimum_fields(monkeypatch):
    """build_tomo_block returns a dict with required fields; updated_at is auto-set."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    block = build_tomo_block(
        doc_type="suggestions",
        state="pending-approval",
        run_id="2026-05-21-1430-abc123",
    )
    assert block["doc_type"] == "suggestions"
    assert block["state"] == "pending-approval"
    assert block["run_id"] == "2026-05-21-1430-abc123"
    # updated_at is auto-set as ISO-8601 UTC with Z suffix
    assert "updated_at" in block
    assert block["updated_at"].endswith("Z")
    # Wrapped in tomo key — the function returns the inner block (without tomo wrapper)
    # so callers assemble: {"tomo": build_tomo_block(...)}
    assert "doc_type" in block


def test_build_tomo_block_with_source_suggestions_ref(monkeypatch):
    """Instructions doc: source_suggestions cross-reference is preserved."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    block = build_tomo_block(
        doc_type="instructions",
        state="pending-apply",
        run_id="2026-05-21-1430-abc123",
        source_suggestions="100 Inbox/2026-05-21-1400_suggestions.md",
    )
    assert block["doc_type"] == "instructions"
    assert block["state"] == "pending-apply"
    assert block["source_suggestions"] == "100 Inbox/2026-05-21-1400_suggestions.md"


def test_build_tomo_block_with_source_moc_proposal_ref(monkeypatch):
    """Instructions doc derived from moc-proposal: source_moc_proposal is preserved."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    block = build_tomo_block(
        doc_type="instructions",
        state="pending-apply",
        run_id="2026-05-21-1500-def456",
        source_moc_proposal="100 Inbox/2026-05-21-1450_moc-proposal-lyt.md",
    )
    assert block["source_moc_proposal"] == "100 Inbox/2026-05-21-1450_moc-proposal-lyt.md"


def test_build_tomo_block_with_source_suggestions_fan_ref(monkeypatch):
    """XDD-012 fan-resolve instructions: source_suggestions_fan is preserved."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    block = build_tomo_block(
        doc_type="instructions",
        state="pending-apply",
        run_id="2026-05-21-1600-ghi789",
        source_suggestions_fan="100 Inbox/2026-05-21-1555_suggestions-fan.md",
    )
    assert block["source_suggestions_fan"] == "100 Inbox/2026-05-21-1555_suggestions-fan.md"


# ---------------------------------------------------------------------------
# Schema validation — dev mode (TOMO_SCHEMA_STRICT=1) raises
# ---------------------------------------------------------------------------


def test_invalid_state_for_doc_type_rejected_dev_mode(monkeypatch):
    """suggestions + state=applied is invalid: dev mode raises SchemaValidationError."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    with pytest.raises(SchemaValidationError):
        build_tomo_block(
            doc_type="suggestions",
            state="applied",  # 'applied' belongs to instructions, not suggestions
            run_id="test-run-id",
        )


# ---------------------------------------------------------------------------
# Schema validation — prod mode (unset) warns only
# ---------------------------------------------------------------------------


def test_invalid_state_warning_only_prod_mode(monkeypatch, capsys):
    """Same invalid input in prod mode: emits stderr warning, returns dict, no raise."""
    monkeypatch.delenv("TOMO_SCHEMA_STRICT", raising=False)
    block = build_tomo_block(
        doc_type="suggestions",
        state="applied",  # invalid for suggestions
        run_id="test-run-id",
    )
    captured = capsys.readouterr()
    assert "WARNING" in captured.err or "warning" in captured.err.lower()
    # Returns dict regardless
    assert block["doc_type"] == "suggestions"
    assert block["state"] == "applied"


# ---------------------------------------------------------------------------
# parse_tomo_block
# ---------------------------------------------------------------------------


def test_parse_tomo_block_returns_none_when_absent():
    """Frontmatter dict without 'tomo' key returns None."""
    result = parse_tomo_block({"title": "My Note", "tags": ["foo"]})
    assert result is None


def test_parse_tomo_block_returns_dict_when_present():
    """Frontmatter dict with 'tomo' key returns the inner dict."""
    tomo_data = {
        "doc_type": "source",
        "state": "captured",
        "run_id": "2026-05-21-0900-xyz",
        "updated_at": "2026-05-21T09:00:00Z",
    }
    result = parse_tomo_block({"tomo": tomo_data, "title": "My Note"})
    assert result == tomo_data


# ---------------------------------------------------------------------------
# Round-trip: build → serialize → parse
# ---------------------------------------------------------------------------


def test_round_trip_preserves_all_fields(monkeypatch):
    """build_tomo_block → wrap in frontmatter → parse_tomo_block returns equal dict."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    block = build_tomo_block(
        doc_type="moc-proposal",
        state="pending-accept",
        run_id="2026-05-21-1100-round",
    )
    # Simulate what a producer does: wrap in frontmatter dict
    frontmatter = {"tomo": block, "title": "Proposal Doc"}
    parsed = parse_tomo_block(frontmatter)
    assert parsed == block
    assert parsed["doc_type"] == "moc-proposal"
    assert parsed["state"] == "pending-accept"
    assert parsed["run_id"] == "2026-05-21-1100-round"
    assert "updated_at" in parsed


# ---------------------------------------------------------------------------
# source_* extensibility (AC-4.5)
# ---------------------------------------------------------------------------


def test_unknown_source_key_pattern_allowed(monkeypatch):
    """source_garden_audit passes schema validation — future F-44/45/46 extensibility."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    block = build_tomo_block(
        doc_type="instructions",
        state="pending-apply",
        run_id="2026-05-21-1200-ext",
        source_garden_audit="100 Inbox/2026-05-21-1150_garden-audit.md",
    )
    assert block["source_garden_audit"] == "100 Inbox/2026-05-21-1150_garden-audit.md"

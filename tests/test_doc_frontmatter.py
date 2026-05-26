#!/usr/bin/env python3
# version: 0.2.0
"""test_doc_frontmatter.py — Tests for the doc_frontmatter helper module.

Covers T1.2 (F-47 Phase 1): build_tomo_block, parse_tomo_block,
SchemaValidationError, and the dual dev/prod validation mode (ADR-4).

T1.2 (XDD-018 Phase 1): sources[] array schema extension — replaces source_* pattern.

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/
      docs/XDD/specs/018-agent-architecture-cleanup/
AC:   AC-1.5 (schema validation gates every producer write),
      AC-7.2 (every producer write schema-validated)
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
# T1.2 (XDD-018): sources[] array — new schema shape
# ---------------------------------------------------------------------------


def test_sources_array_valid_shape(monkeypatch):
    """instructions doc with sources: [{path, checksum}] validates."""
    monkeypatch.setenv("TOMO_SCHEMA_STRICT", "1")
    import json
    import jsonschema
    from pathlib import Path

    schema_path = Path(__file__).resolve().parent.parent / "tomo" / "schemas" / "doc-frontmatter.schema.json"
    schema = json.loads(schema_path.read_text())
    doc = {
        "tomo": {
            "doc_type": "instructions",
            "state": "pending-apply",
            "run_id": "2026-05-26-1430-abc",
            "updated_at": "2026-05-26T14:30:00Z",
            "sources": [
                {"path": "100 Inbox/2026-05-22_suggestions.md", "checksum": "sha256:" + "a" * 64},
                {"path": "100 Inbox/2026-05-23_suggestions-fan.md", "checksum": "sha256:" + "b" * 64},
            ],
        }
    }
    jsonschema.validate(doc, schema)  # should not raise


def test_sources_checksum_pattern_validation():
    """Invalid checksum format is rejected."""
    import json
    import jsonschema
    from pathlib import Path

    schema_path = Path(__file__).resolve().parent.parent / "tomo" / "schemas" / "doc-frontmatter.schema.json"
    schema = json.loads(schema_path.read_text())
    doc = {
        "tomo": {
            "doc_type": "instructions",
            "state": "pending-apply",
            "run_id": "r1",
            "updated_at": "2026-05-26T14:30:00Z",
            "sources": [{"path": "inbox/test.md", "checksum": "md5:invalidformat"}],
        }
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


def test_sources_rejects_old_source_star_pattern():
    """Old source_suggestions string pattern is rejected after schema migration."""
    import json
    import jsonschema
    from pathlib import Path

    schema_path = Path(__file__).resolve().parent.parent / "tomo" / "schemas" / "doc-frontmatter.schema.json"
    schema = json.loads(schema_path.read_text())
    doc = {
        "tomo": {
            "doc_type": "instructions",
            "state": "pending-apply",
            "run_id": "r1",
            "updated_at": "2026-05-26T14:30:00Z",
            "source_suggestions": "100 Inbox/old-format.md",
        }
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)


def test_existing_doctypes_validate_without_sources():
    """Non-instructions doc-types still validate without sources field."""
    import json
    import jsonschema
    from pathlib import Path

    schema_path = Path(__file__).resolve().parent.parent / "tomo" / "schemas" / "doc-frontmatter.schema.json"
    schema = json.loads(schema_path.read_text())
    for doc_type, state in [
        ("source", "captured"),
        ("suggestions", "pending-approval"),
        ("suggestions-fan", "pending-approval"),
        ("moc-proposal", "pending-accept"),
    ]:
        doc = {
            "tomo": {
                "doc_type": doc_type,
                "state": state,
                "run_id": "r1",
                "updated_at": "2026-05-26T14:30:00Z",
            }
        }
        jsonschema.validate(doc, schema)  # should not raise


def test_sources_path_only_valid():
    """sources item with path only (no checksum) validates — checksum is optional."""
    import json
    import jsonschema
    from pathlib import Path

    schema_path = Path(__file__).resolve().parent.parent / "tomo" / "schemas" / "doc-frontmatter.schema.json"
    schema = json.loads(schema_path.read_text())
    doc = {
        "tomo": {
            "doc_type": "instructions",
            "state": "pending-apply",
            "run_id": "r1",
            "updated_at": "2026-05-26T14:30:00Z",
            "sources": [{"path": "inbox/test.md"}],
        }
    }
    jsonschema.validate(doc, schema)  # should not raise

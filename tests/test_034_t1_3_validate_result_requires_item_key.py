#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t1_3_validate_result_requires_item_key.py — validate-result.py rejects a
per-item result missing `item_key`, on both the jsonschema path and the hand-rolled
`REQUIRED_TOP` fallback path used when no schema file is available.

Covers T1.3 (XDD 034 Phase 1): validate-result.py is the gate between the inbox-analyst
fan-out and the suggestions-reducer — a result missing `item_key` must not reach the
reducer unnoticed (SDD/Building Block View).

Invokes the script as a CLI subprocess (as production does: analyst -> validate-result.py
--result --schema), never by importing an internal helper — importing would risk
exercising a code path production never runs.

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPT = REPO_ROOT / "tomo" / "scripts" / "validate-result.py"
REAL_SCHEMA = REPO_ROOT / "tomo" / "schemas" / "item-result.schema.json"


def _valid_result() -> dict:
    """A minimal item-result payload that satisfies both the schema and REQUIRED_TOP."""
    return {
        "schema_version": "1",
        "stem": "my-inbox-note",
        "item_key": "100 Inbox/my-inbox-note.md",
        "path": "100 Inbox/my-inbox-note.md",
        "type": "atomic",
        "type_confidence": 0.9,
        "actions": [
            {"kind": "create_moc", "moc_title": "Test MOC", "parent_moc": "Atlas/MOC.md"}
        ],
    }


def _run(result: dict, tmp_path: Path, schema: Path) -> subprocess.CompletedProcess:
    result_path = tmp_path / "item.result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--result", str(result_path), "--schema", str(schema)],
        capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# missing item_key is rejected — hand-rolled REQUIRED_TOP fallback path.
# A nonexistent --schema path forces validate-result.py into validate_hand(),
# the branch that runs when no schema file is available. This is the RED
# case for T1.3: before item_key is added to REQUIRED_TOP, a result missing
# it passes this path unnoticed.
# ---------------------------------------------------------------------------


def test_missing_item_key_rejected_via_hand_rolled_fallback(tmp_path):
    result = _valid_result()
    del result["item_key"]
    missing_schema = tmp_path / "does-not-exist.schema.json"
    proc = _run(result, tmp_path, missing_schema)
    assert proc.returncode == 1, f"expected rejection, got exit {proc.returncode}: {proc.stderr}"
    assert "item_key" in proc.stderr, f"rejection must name item_key, got: {proc.stderr}"


# ---------------------------------------------------------------------------
# missing item_key is rejected — jsonschema path, against the real schema
# (already required there by a sibling task; confirms both gates agree).
# ---------------------------------------------------------------------------


def test_missing_item_key_rejected_via_schema_path(tmp_path):
    result = _valid_result()
    del result["item_key"]
    proc = _run(result, tmp_path, REAL_SCHEMA)
    assert proc.returncode == 1, f"expected rejection, got exit {proc.returncode}: {proc.stderr}"
    assert "item_key" in proc.stderr, f"rejection must name item_key, got: {proc.stderr}"


# ---------------------------------------------------------------------------
# a result carrying both item_key and stem passes — on both paths.
# ---------------------------------------------------------------------------


def test_result_with_item_key_and_stem_passes_schema_path(tmp_path):
    result = _valid_result()
    assert "item_key" in result and "stem" in result
    proc = _run(result, tmp_path, REAL_SCHEMA)
    assert proc.returncode == 0, f"expected success, got exit {proc.returncode}: {proc.stderr}"


def test_result_with_item_key_and_stem_passes_hand_rolled_fallback(tmp_path):
    result = _valid_result()
    assert "item_key" in result and "stem" in result
    missing_schema = tmp_path / "does-not-exist.schema.json"
    proc = _run(result, tmp_path, missing_schema)
    assert proc.returncode == 0, f"expected success, got exit {proc.returncode}: {proc.stderr}"

#!/usr/bin/env python3
# version: 0.1.0
"""test_reducer_conventions_block.py — reducer suffix + conventions block (028 T2.3).

The reducer must:
  1. Emit an additive top-level `conventions` block into suggestions-doc.json,
     carrying the active profile's resolved markers + MOC suffix.
  2. Apply the MOC-title suffix from the resolved profile (not a hardcoded
     " (MOC)") in `_ensure_moc_suffix`.
  3. Keep the existing wire otherwise unchanged and schema-valid.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import jsonschema

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "suggestions-reducer.py"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-doc.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("suggestions_reducer", SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["suggestions_reducer"] = _mod
_spec.loader.exec_module(_mod)

_ensure_moc_suffix = _mod._ensure_moc_suffix  # type: ignore[attr-defined]


# ── Unit: _ensure_moc_suffix takes the suffix as a parameter ──────────────────


def test_ensure_moc_suffix_miyo_parity() -> None:
    assert _ensure_moc_suffix("Shell", " (MOC)") == "Shell (MOC)"
    # legacy ' MOC' → suffix conversion preserved
    assert _ensure_moc_suffix("Shell MOC", " (MOC)") == "Shell (MOC)"
    # apply-once
    assert _ensure_moc_suffix("Shell (MOC)", " (MOC)") == "Shell (MOC)"
    # bare "MOC" guard
    assert _ensure_moc_suffix("MOC", " (MOC)") == "MOC"


def test_ensure_moc_suffix_empty_is_noop() -> None:
    assert _ensure_moc_suffix("Shell", "") == "Shell"
    assert _ensure_moc_suffix("Shell MOC", "") == "Shell MOC"


# ── End-to-end: conventions block written to suggestions-doc.json ─────────────


def _run(tmp_path: Path, profile: str) -> dict:
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    items = tmp_path / "items"
    items.mkdir()
    out = tmp_path / f"doc-{profile}.json"
    result = subprocess.run(
        [
            "python3", str(SCRIPT_PATH),
            "--state", str(state),
            "--items-dir", str(items),
            "--run-id", "test-run",
            "--profile", profile,
            "--output", str(out),
            "--shared-ctx", str(tmp_path / "nope.json"),
            "--no-kado",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, (
        f"reducer failed ({profile}): {result.stderr.decode()}"
    )
    return json.loads(out.read_text(encoding="utf-8"))


def test_conventions_block_miyo(tmp_path: Path) -> None:
    doc = _run(tmp_path, "miyo")
    assert doc["conventions"] == {
        "parent_marker": "up::",
        "peer_marker": "related::",
        "moc_suffix": " (MOC)",
    }


def test_conventions_block_lyt(tmp_path: Path) -> None:
    doc = _run(tmp_path, "lyt")
    assert doc["conventions"]["moc_suffix"] == ""
    assert doc["conventions"]["parent_marker"] == "up::"


def test_doc_still_schema_valid_with_conventions(tmp_path: Path) -> None:
    doc = _run(tmp_path, "miyo")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)  # must not raise


def test_existing_wire_fields_unchanged(tmp_path: Path) -> None:
    doc = _run(tmp_path, "miyo")
    # Additive-only: the pre-028 required fields remain present and untouched.
    for key in ("schema_version", "generated", "run_id", "profile", "sections"):
        assert key in doc
    assert doc["profile"] == "miyo"
    assert doc["schema_version"] == "1"

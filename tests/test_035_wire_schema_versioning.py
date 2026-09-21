#!/usr/bin/env python3
# version: 0.1.0
"""test_035_wire_schema_versioning.py — Behavioural tests for T4.3: moving
the garden-audit wire's schema_version to "2" and disclosing it to the
consumer (spec 035 Phase 4).

Tests cover:
- the garden-audit wire's schema_version const is "2", not "1"
  (PRD/F4-AC1/F4-AC3 — the version move itself)
- the schema's own description no longer claims "always '1'" — ADR-2
  excludes prose from the manifest, so a stale claim there would never be
  caught by the gate; this test is the only thing that catches it
- the committed manifest under tomo/schemas/shapes/ records "2", proving
  --regenerate was actually run and committed, not just the schema edited
- the wire-shape gate passes for the garden-audit wire after the move —
  its docstring notes the gate is ALREADY clean today (this schema has no
  other drift), so this test alone proves nothing about the version move;
  tests 1-3 above are what establish the change actually happened
- the handoff's attached schema file, when present, is byte-identical to
  the repository's tomo/schemas/garden-audit-wire.schema.json — skipped
  when _outbox/for-hashi/ or the attachment is absent, since that
  directory is gitignored and will not exist in CI

Deliberately NOT tested here (and why):
- that the emitted document carries the new version — this cannot fail
  after T3.1 (ADR-5 removed every emitter literal; garden-audit-render.py
  reads schema_version from the schema itself), and the non-vacuous
  version of this property already lives in
  tests/test_035_wire_version.py's
  test_garden_audit_render_emits_its_schemas_declared_version, which
  drives the renderer against a scratch schema declaring "99" and proves
  it is not hard-coded.
- the obligation table's prose — asserting on a handoff's wording couples
  a test to something a human must write well, not to production code.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
SHAPES_DIR = SCHEMAS_DIR / "shapes"
OUTBOX_DIR = REPO_ROOT / "_outbox" / "for-hashi"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.wire_gate import gate_one_wire, manifest_filename  # noqa: E402

GARDEN_AUDIT_SCHEMA = "garden-audit-wire.schema.json"


def _load_schema() -> dict:
    return json.loads((SCHEMAS_DIR / GARDEN_AUDIT_SCHEMA).read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────
# Test 1 — schema_version const moved to "2"
# ─────────────────────────────────────────────────────────────────────────

def test_garden_audit_schema_version_is_2():
    schema = _load_schema()
    assert schema["properties"]["schema_version"]["const"] == "2"


# ─────────────────────────────────────────────────────────────────────────
# Test 2 — the description no longer claims "always '1'"
# ─────────────────────────────────────────────────────────────────────────

def test_garden_audit_description_does_not_claim_always_1():
    schema = _load_schema()
    description = schema["properties"]["schema_version"]["description"]
    assert "always '1'" not in description
    assert "always \"1\"" not in description


# ─────────────────────────────────────────────────────────────────────────
# Test 3 — the committed manifest records the new version
# ─────────────────────────────────────────────────────────────────────────

def test_garden_audit_manifest_records_version_2():
    manifest_path = SHAPES_DIR / manifest_filename(GARDEN_AUDIT_SCHEMA)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "2"


# ─────────────────────────────────────────────────────────────────────────
# Test 4 — the gate passes for the garden-audit wire after the move
# ─────────────────────────────────────────────────────────────────────────

def test_wire_shape_check_passes_after_move():
    """This wire carries no OTHER drift today, so the gate is already
    clean against the committed manifest — passing here proves only that
    --regenerate was applied and committed, not that the version actually
    moved. Tests 1-3 above are what establish the change happened; this
    test exists to prove the move didn't leave the gate in a failing
    state, not to prove the move occurred.
    """
    schema_path = SCHEMAS_DIR / GARDEN_AUDIT_SCHEMA
    manifest_path = SHAPES_DIR / manifest_filename(GARDEN_AUDIT_SCHEMA)

    result = gate_one_wire(GARDEN_AUDIT_SCHEMA, schema_path, manifest_path)

    assert result["passed"], result


# ─────────────────────────────────────────────────────────────────────────
# Test 5 — the handoff's attached schema is byte-identical to the repo's
# ─────────────────────────────────────────────────────────────────────────

def _find_attached_garden_audit_schema() -> Path | None:
    if not OUTBOX_DIR.is_dir():
        return None
    candidates = sorted(OUTBOX_DIR.glob("*garden-audit-wire.schema.json"))
    return candidates[0] if candidates else None


def test_handoff_schema_attachment_byte_identical():
    attachment = _find_attached_garden_audit_schema()
    if attachment is None:
        pytest.skip("_outbox/for-hashi/ is gitignored and has no attachment in this checkout")

    repo_bytes = (SCHEMAS_DIR / GARDEN_AUDIT_SCHEMA).read_bytes()
    attachment_bytes = attachment.read_bytes()
    assert attachment_bytes == repo_bytes


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

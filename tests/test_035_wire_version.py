#!/usr/bin/env python3
# version: 0.1.0
"""test_035_wire_version.py — Behavioural tests for lib.wire_version (spec 035 T3.1).

ADR-5: each of the three wire renderers (suggestions-render.py,
instruction-render.py, garden-audit-render.py) must emit the `schema_version`
its OWN schema declares — never a free string literal that can drift from the
schema in either direction.

Tests cover:
- each renderer's emission path, driven against a scratch schema whose
  declared version is NOT today's literal ("99" vs "1"/"2") — proves the
  renderer reads the schema rather than hard-coding a value. Against
  today's code (a free literal) every one of these fails, still emitting the
  old literal instead of "99".
- a missing schema at runtime raises, naming the resolved path, and never
  falls back to "", None, or a stale literal.

The no-literal regression guard (static source scan, vacuous-by-design once
this task lands) lives in tests/test_035_wire_shape.py, not here — T2.4 owns
that file's existing tests and two phases editing the same assertions is how
Phase 3's independence claim would stop being true.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import wire_version  # noqa: E402
from lib.wire_version import wire_schema_version  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _scratch_schemas_dir(tmp_path: Path, filename: str, version: str) -> Path:
    """A schemas/ directory containing only `filename`, declaring `version`.

    Deliberately NOT a copy of the real schema — wire_schema_version only
    ever reads properties.schema_version.const, so a minimal synthetic
    document is enough and keeps the fixture's intent legible.
    """
    directory = tmp_path / "schemas"
    directory.mkdir()
    (directory / filename).write_text(
        json.dumps({"properties": {"schema_version": {"const": version}}}),
        encoding="utf-8",
    )
    return directory


# ─────────────────────────────────────────────────────────────────────────
# Test 1a — suggestions-render.py's build_wire_payload
# ─────────────────────────────────────────────────────────────────────────

def test_suggestions_render_emits_its_schemas_declared_version(monkeypatch, tmp_path):
    scratch = _scratch_schemas_dir(tmp_path, "suggestions-wire.schema.json", "99")
    monkeypatch.setattr(wire_version, "_default_schemas_dir", lambda: scratch)

    sr = _load("suggestions_render_wire_version", "suggestions-render.py")
    doc = {"generated": "2026-09-10T10:00:00Z", "run_id": "r1", "profile": "miyo", "source_items": 0}

    payload = sr.build_wire_payload(doc)

    assert payload["schema_version"] == "99"


# ─────────────────────────────────────────────────────────────────────────
# Test 1b — garden-audit-render.py's build_wire_payload
# ─────────────────────────────────────────────────────────────────────────

def test_garden_audit_render_emits_its_schemas_declared_version(monkeypatch, tmp_path):
    scratch = _scratch_schemas_dir(tmp_path, "garden-audit-wire.schema.json", "99")
    monkeypatch.setattr(wire_version, "_default_schemas_dir", lambda: scratch)

    gar = _load("garden_audit_render_wire_version", "garden-audit-render.py")
    doc = {
        "run_id": "r1", "generated": "2026-09-10T10:00:00Z", "profile": "miyo",
        "findings": [], "skipped_checks": [], "skipped_checks_reason": "",
        "reappeared_exclusions": [],
    }

    payload = gar.build_wire_payload(doc)

    assert payload["schema_version"] == "99"


# ─────────────────────────────────────────────────────────────────────────
# Test 1c — instruction-render.py's main(), driven end to end
# ─────────────────────────────────────────────────────────────────────────

def _drive_instruction_render(monkeypatch, tmp_path):
    """Minimal instruction-render.main() invocation that reaches the
    instructions.json emission (line ~778). Mirrors the harness in
    tests/test_034_t5_3_destination_validation.py's _drive_render — a
    placeholder confirmed item is required or main() short-circuits at its
    "nothing to do" guard before ever building instructions_doc.
    """
    ir = _load("instruction_render_wire_version", "instruction-render.py")
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps({
        "confirmed_items": [{
            "id": "S01", "action": None, "title": "placeholder",
            "source_path": "", "tags": [], "parent_mocs": [], "candidate_mocs": [],
        }],
        "daily_updates": [], "skipped": [],
    }), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(ir, "load_config", lambda _p: {
        "concepts.inbox": "100 Inbox/", "profile": "miyo", "callouts.editable": ["NOTE"],
    })
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "build_actions", lambda *_a, **_kw: ([], []))
    monkeypatch.setattr(ir, "resolve_target_moc_paths", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _a: [])

    out_dir = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "instruction-render.py", "--suggestions", str(suggestions_file),
        "--output-dir", str(out_dir), "--config", str(cfg_file),
    ])
    assert isinstance(ir.main(), int)
    return out_dir


def test_instruction_render_emits_its_schemas_declared_version(monkeypatch, tmp_path):
    scratch = _scratch_schemas_dir(tmp_path, "instructions.schema.json", "99")
    monkeypatch.setattr(wire_version, "_default_schemas_dir", lambda: scratch)

    out_dir = _drive_instruction_render(monkeypatch, tmp_path)
    doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))

    assert doc["schema_version"] == "99"


# ─────────────────────────────────────────────────────────────────────────
# Test 2 — missing schema at runtime
# ─────────────────────────────────────────────────────────────────────────

def test_missing_schema_raises_naming_the_resolved_path(monkeypatch, tmp_path):
    empty_dir = tmp_path / "schemas"
    empty_dir.mkdir()
    monkeypatch.setattr(wire_version, "_default_schemas_dir", lambda: empty_dir)

    with pytest.raises(FileNotFoundError) as excinfo:
        wire_schema_version("suggestions-wire.schema.json")

    message = str(excinfo.value)
    resolved_path = empty_dir / "suggestions-wire.schema.json"
    assert str(resolved_path) in message
    # Never a silent fallback to an empty string, None, or a stale literal —
    # the exception itself is the whole assertion; nothing was returned.


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

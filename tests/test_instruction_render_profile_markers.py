#!/usr/bin/env python3
# version: 0.1.0
"""test_instruction_render_profile_markers.py — Phase 4 T4.1 wire-in.

instruction-render.py must resolve the active profile's relationship markers
from its existing --config and thread them into build_actions (spec 028 ADR-1).

Locks:
  1. A --config selecting a profile whose markers differ → build_actions
     receives the resolved parent_marker/peer_marker.
  2. A --config selecting miyo → build_actions receives up::/related::, i.e.
     byte-identical inputs to the pre-change hardcoded defaults (CON-2).

build_actions is stubbed so no Kado connection is needed: it returns [] and all
downstream resolve/merge/filter steps no-op on the empty action list.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("instruction_render", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render"] = ir
_spec.loader.exec_module(ir)


def _run_capturing_markers(tmp_path, monkeypatch, config_text: str) -> dict:
    """Run main() with build_actions stubbed; return the captured kwargs."""
    captured: dict = {}

    def _fake_build_actions(*args, **kwargs):
        captured["parent_marker"] = kwargs.get("parent_marker")
        captured["peer_marker"] = kwargs.get("peer_marker")
        return []

    monkeypatch.setattr(ir, "build_actions", _fake_build_actions)

    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text(config_text, encoding="utf-8")

    suggestions_path = tmp_path / "suggestions.json"
    # daily_updates present so we pass the early-return guard; confirmed empty so
    # no Kado client is created and the render loop does nothing.
    suggestions_path.write_text(
        json.dumps({"confirmed_items": [], "daily_updates": [{"id": "D1"}], "skipped": []}),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "instruction-render.py",
            "--suggestions", str(suggestions_path),
            "--output-dir", str(out_dir),
            "--config", str(config_path),
        ],
    )
    rc = ir.main()
    assert rc == 0
    return captured


def test_markers_flow_from_profile(tmp_path, monkeypatch):
    """A profile with non-default markers → build_actions gets those markers."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "custom.yaml").write_text(
        "relationship_defaults:\n"
        "  parent:\n    marker: \"parent::\"\n"
        "  peer:\n    marker: \"rel::\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ir, "DEFAULT_PROFILES_DIR", profiles_dir)

    captured = _run_capturing_markers(
        tmp_path, monkeypatch, "profile: custom\n"
    )
    assert captured["parent_marker"] == "parent::"
    assert captured["peer_marker"] == "rel::"


def test_miyo_markers_are_defaults(tmp_path, monkeypatch):
    """miyo → build_actions gets up::/related:: (byte-identical to old defaults)."""
    # Use the real bundled profiles dir (miyo.yaml) — no monkeypatch of the dir.
    captured = _run_capturing_markers(
        tmp_path, monkeypatch, "profile: miyo\n"
    )
    assert captured["parent_marker"] == "up::"
    assert captured["peer_marker"] == "related::"

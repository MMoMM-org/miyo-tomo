#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_render_moc_suffix.py — F-55 (spec 028): profile-agnostic MOC suffix.

The `render_proposed_mocs` name fallback (`pm["name"] or <fallback>`) must resolve
the MOC-title suffix from the input doc's top-level `conventions.moc_suffix` block
instead of hardcoding " (MOC)". Covers:

  (a) lyt conventions (moc_suffix="")  → fallback name is the plain topic, no suffix
  (b) miyo conventions (moc_suffix=" (MOC)") → fallback name is byte-identical to the
      legacy f"{topic} (MOC)" output
  (c) absent conventions block → defaults to "" (plain topic, older-artifact safety)

Spec: docs/XDD/specs/028-profile-agnostic-markers/
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_render_mod():
    """Load suggestions-render.py as a module (not a package)."""
    spec = importlib.util.spec_from_file_location(
        "suggestions_render_moc_suffix",
        SCRIPTS_DIR / "suggestions-render.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_doc(proposed_mocs: list[dict[str, Any]], conventions: Any = "__absent__") -> dict[str, Any]:
    """Minimal suggestions-doc with proposed_mocs and an optional conventions block."""
    d: dict[str, Any] = {
        "schema_version": "1",
        "generated": "2026-07-01T10:00:00Z",
        "run_id": "2026-07-01-1000-test00",
        "profile": "miyo",
        "doc_variant": "primary",
        "source_items": 0,
        "sections": [],
        "daily_notes_updates": [],
        "proposed_mocs": proposed_mocs,
        "needs_attention": [],
    }
    if conventions != "__absent__":
        d["conventions"] = conventions
    return d


def _name_line(lines: list[str]) -> str:
    for ln in lines:
        if ln.startswith("- **Name:**"):
            return ln
    raise AssertionError(f"no Name line in rendered output: {lines!r}")


class TestMocSuffixFallback:

    def test_lyt_no_suffix_fallback_is_plain_topic(self):
        """Under lyt (moc_suffix=''), the name fallback must be the plain topic."""
        mod = _load_render_mod()
        doc = _make_doc(
            [{"topic": "Deep Work"}],  # no name → fallback triggers
            conventions={"parent_marker": "up::", "peer_marker": "related::", "moc_suffix": ""},
        )
        lines = mod.render_proposed_mocs(doc)
        name_line = _name_line(lines)
        assert "Deep Work" in name_line
        assert "(MOC)" not in name_line, f"lyt name must have no MOC suffix: {name_line!r}"

    def test_miyo_suffix_fallback_is_byte_identical(self):
        """Under miyo (moc_suffix=' (MOC)'), the fallback name must match the legacy literal."""
        mod = _load_render_mod()
        topic = "Deep Work"
        doc = _make_doc(
            [{"topic": topic}],
            conventions={"parent_marker": "up::", "peer_marker": "related::", "moc_suffix": " (MOC)"},
        )
        lines = mod.render_proposed_mocs(doc)
        name_line = _name_line(lines)
        # Byte-identical to today's hardcoded output.
        legacy = f"- **Name:** {f'{topic} (MOC)'}    ← edit this to rename the MOC before approving"
        assert name_line == legacy, f"expected {legacy!r}, got {name_line!r}"

    def test_absent_conventions_defaults_to_plain_topic(self):
        """Older artifacts without a conventions block default to '' (plain topic)."""
        mod = _load_render_mod()
        doc = _make_doc([{"topic": "Deep Work"}])  # no conventions key at all
        lines = mod.render_proposed_mocs(doc)
        name_line = _name_line(lines)
        assert "Deep Work" in name_line
        assert "(MOC)" not in name_line, f"absent conventions must not add MOC suffix: {name_line!r}"

    def test_explicit_name_wins_over_suffix(self):
        """An explicit pm['name'] is used verbatim regardless of conventions."""
        mod = _load_render_mod()
        doc = _make_doc(
            [{"topic": "Deep Work", "name": "My Custom MOC"}],
            conventions={"moc_suffix": " (MOC)"},
        )
        lines = mod.render_proposed_mocs(doc)
        name_line = _name_line(lines)
        assert "My Custom MOC" in name_line

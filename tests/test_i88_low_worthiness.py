#!/usr/bin/env python3
# version: 0.1.0
"""test_i88_low_worthiness.py — sub-0.5 atomic suppression + Force-Atomic escape.

Covers issue #88:
  - render_suppressed_atomic emits a LIGHT "kept in inbox" block (worthiness +
    Force-Atomic checkbox), with NO template/location/MOC/Approve framing.
  - parse_section reads the per-item "Force Atomic Note" checkbox onto the
    section (force_atomic), leaving Approve unchecked (it stays in the inbox
    unless force-atomic'd).
  - render → parse round-trip: ticking the box sets force_atomic.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_reducer = _load("suggestions_reducer", "suggestions-reducer.py")
_parser = _load("suggestion_parser", "suggestion-parser.py")

render_suppressed_atomic = _reducer.render_suppressed_atomic
parse_section = _parser.parse_section


def _suppressed_action() -> dict:
    return {
        "kind": "create_atomic_note",
        "suggested_title": "Some weak thought",
        "atomic_note_worthiness": 0.4,
        "stem": "202606271322_weak",
        "template": "t_note.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [{"path": "Atlas/200 Maps/X (MOC).md"}],
        "suppressed": True,
    }


# ── render: the light block ──────────────────────────────────────────────────


def test_light_block_reports_worthiness_and_force_atomic():
    md = render_suppressed_atomic(_suppressed_action(), "202606271322_weak")
    assert "**Source:** [[202606271322_weak]]" in md
    assert "40%" in md and "kept in inbox" in md
    assert "- [ ] Force Atomic Note" in md


def test_light_block_omits_atomic_pipeline_framing():
    """No template/location/MOC/Approve/Skip/Delete framing on a suppressed item."""
    md = render_suppressed_atomic(_suppressed_action(), "202606271322_weak")
    for forbidden in ("**Template:**", "**Location:**", "**Link to MOC:**",
                      "- [ ] Approve", "- [x] Approve", "Delete source", "Keep origin"):
        assert forbidden not in md, forbidden


# ── parse: per-item Force Atomic checkbox ────────────────────────────────────


def _parse(md: str) -> dict:
    return parse_section("S01", md.splitlines())


def test_parse_force_atomic_unticked_stays_in_inbox():
    """Default light block (Force Atomic unticked) → not approved, not force_atomic."""
    sec = _parse(render_suppressed_atomic(_suppressed_action(), "weak"))
    assert sec["approved"] is False
    assert sec["force_atomic"] is False


def test_parse_force_atomic_ticked_sets_flag():
    """Ticking Force Atomic Note → force_atomic True (Approve stays False)."""
    md = render_suppressed_atomic(_suppressed_action(), "weak").replace(
        "- [ ] Force Atomic Note", "- [x] Force Atomic Note"
    )
    sec = _parse(md)
    assert sec["force_atomic"] is True
    assert sec["approved"] is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

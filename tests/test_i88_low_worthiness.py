#!/usr/bin/env python3
# version: 0.2.0
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


# ── spec 031 T6.5 finding A: the unresolved-embed warning must survive ───────
#
# A suppressed item is NOT promoted, so no move_asset is ever emitted for it
# and an `**Attachments:**` line would promise an action that never happens.
# An UNRESOLVED or AMBIGUOUS embed is the opposite: it is a real defect in the
# user's vault that they must fix by hand, and it is equally true whether or
# not Tomo files the note. Live run 2 proved the warning was computed, written
# to resolved-attachments.json, and then dropped here — silently.


def _ambiguous_action() -> dict:
    action = _suppressed_action()
    action["attachments"] = []
    action["unresolved_embeds"] = [
        {"embed_target": "karte.png", "status": "ambiguous", "candidate_count": 2},
    ]
    return action


def test_light_block_reports_ambiguous_embed():
    md = render_suppressed_atomic(_ambiguous_action(), "Dresden")
    assert "**Unresolved embeds:** `karte.png` (ambiguous — 2 candidates)" in md


def test_light_block_reports_unresolved_embed():
    action = _suppressed_action()
    action["unresolved_embeds"] = [
        {"embed_target": "fehlt.png", "status": "unresolved"},
    ]
    md = render_suppressed_atomic(action, "Dresden")
    assert "**Unresolved embeds:** `fehlt.png` (unresolved)" in md


def test_light_block_omits_attachments_line():
    """A resolved attachment on a suppressed item is deliberately NOT shown.

    Nothing will be moved — the note stays in the inbox and so does its image.
    Naming the attachment here would imply a filing action that Pass 2 never
    emits, which is the same class of defect as hiding the warning above.
    """
    action = _suppressed_action()
    action["attachments"] = ["100 Inbox/Images/bautzen-turm.jpg"]
    md = render_suppressed_atomic(action, "Bautzen")
    assert "**Attachments:**" not in md
    assert "bautzen-turm.jpg" not in md


def test_light_block_silent_when_every_embed_resolved():
    """CON-8 control: no unresolved embeds → no block, byte-identical output."""
    action = _suppressed_action()
    action["attachments"] = ["100 Inbox/Images/prag-karte.png"]
    action["unresolved_embeds"] = []
    assert render_suppressed_atomic(action, "X") == render_suppressed_atomic(
        _suppressed_action(), "X"
    )

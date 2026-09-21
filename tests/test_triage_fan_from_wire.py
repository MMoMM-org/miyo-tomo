#!/usr/bin/env python3
# version: 0.3.0
"""test_triage_fan_from_wire.py — ADR-026: fan-resolve triggers from an edited wire.

Under JSON-only (Hashi edited the _suggestions.json), the markdown body is a minimal
envelope with no Force-Atomic checkboxes — the force-atomic decisions live in the JSON.
Triage must read them from the wire (when edited) so determine_action routes to
fan-resolve, exactly as the markdown flow does. Covers:
  - _load_edited_wire: edited (digest mismatch) → wire; unedited/absent/bad → None.
  - _extract_fan_items_from_wire: suppressed+force_atomic suggestions AND daily
    force_atomic_note entries, deduplicated by the note path each resolves to
    (spec 034 T4.1 — two same-stem notes in different subfolders are two items).
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


_triage = _load("inbox_triage", "inbox-triage.py")
_render_md = _load("render_md_mod", "lib/render_md.py")
compute_payload_digest = _render_md.compute_payload_digest


INBOX = "100 Inbox/"

# Sapporo is daily-only: no suggestion carries its item_key, so it resolves
# through the run's inbox listing the way an attachment target does.
INBOX_INDEX = {"Sapporo.md": [INBOX + "Sapporo.md"]}


def _wire(**over) -> dict:
    w = {
        "schema_version": "2",
        "suggestions": [
            {"id": "S01", "stem": "Asahikawa", "item_key": INBOX + "Asahikawa.md",
             "suppressed": True, "force_atomic": True},
            {"id": "S02", "stem": "note-c", "item_key": INBOX + "note-c.md",
             "suppressed": True, "force_atomic": True},
            {"id": "S03", "stem": "zettelkasten", "item_key": INBOX + "zettelkasten.md",
             "suppressed": False, "force_atomic": False},
            {"id": "S04", "stem": "quick", "item_key": INBOX + "quick.md",
             "suppressed": True, "force_atomic": False},
        ],
        "daily_updates": [
            {"date": "2026-04-17", "log_entries": [
                {"source_stem": "Asahikawa", "force_atomic_note": True},   # overlaps S01
                {"source_stem": "Sapporo", "force_atomic_note": True},     # daily-only
                {"source_stem": "Furano", "force_atomic_note": False},
            ]},
        ],
    }
    w.update(over)
    return w


def _sealed(wire: dict) -> dict:
    """Embed the correct digest → an UNEDITED wire."""
    wire = dict(wire)
    wire["emit_digest"] = compute_payload_digest(wire)
    return wire


# ── _extract_fan_items_from_wire ─────────────────────────────────────────────


def test_extracts_suppressed_force_atomic_and_daily_deduped():
    items = _triage._extract_fan_items_from_wire(
        _wire(), "100 Inbox/x_suggestions.md", inbox_index=INBOX_INDEX,
    )
    stems = [i["stem"] for i in items]
    # S01 Asahikawa, S02 note-c (suppressed+force_atomic) + Sapporo (daily). Asahikawa
    # appears in both suggestion and daily → deduped once. S03/S04/Furano excluded.
    assert stems == ["Asahikawa", "note-c", "Sapporo"], stems
    assert all(i["source_path"] == "100 Inbox/x_suggestions.md" for i in items)
    # Each item names its OWN note, never the review document it was ticked in.
    assert [i["item_key"] for i in items] == [
        INBOX + "Asahikawa.md", INBOX + "note-c.md", INBOX + "Sapporo.md",
    ]


def test_no_force_atomic_yields_empty():
    w = _wire(suggestions=[{"id": "S01", "stem": "a", "suppressed": True, "force_atomic": False}],
              daily_updates=[])
    assert _triage._extract_fan_items_from_wire(w, "p") == []


# ── _load_edited_wire ────────────────────────────────────────────────────────


def test_edited_wire_detected(tmp_path):
    sealed = _sealed(_wire())
    sealed["suggestions"][0]["force_atomic"] = False  # mutate AFTER sealing → edited
    p = tmp_path / "w.json"
    p.write_text(__import__("json").dumps(sealed), encoding="utf-8")
    assert _triage._load_edited_wire(str(p)) is not None


def test_unedited_wire_returns_none(tmp_path):
    p = tmp_path / "w.json"
    p.write_text(__import__("json").dumps(_sealed(_wire())), encoding="utf-8")
    assert _triage._load_edited_wire(str(p)) is None


def test_missing_digest_returns_none(tmp_path):
    p = tmp_path / "w.json"
    p.write_text(__import__("json").dumps(_wire()), encoding="utf-8")  # no emit_digest
    assert _triage._load_edited_wire(str(p)) is None


def test_wrong_schema_version_returns_none(tmp_path):
    w = _sealed(_wire())
    # "1" was the accepted version before spec 035 F9 moved it to "2" — now a
    # stale/wrong value, same as any other version this consumer doesn't
    # recognize (the accepted version is read from the schema, not a
    # literal here — see _load_edited_wire).
    w["schema_version"] = "1"
    p = tmp_path / "w.json"
    p.write_text(__import__("json").dumps(w), encoding="utf-8")
    assert _triage._load_edited_wire(str(p)) is None


def test_absent_or_unparseable_returns_none(tmp_path):
    assert _triage._load_edited_wire(str(tmp_path / "nope.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert _triage._load_edited_wire(str(bad)) is None

#!/usr/bin/env python3
# version: 0.2.0
"""test_garden_audit_hashi_example.py — pin the Phase-6 Hashi handoff example.

The handoff doc (_outbox/for-hashi/…garden-audit-edit-note-text.md) embeds a REAL
instruction-set generated from the actual Pass-2 pipeline and asserted valid against
hashi-instructions.schema.json. This test locks the generator (scripts/gen-garden-audit-
hashi-example.py) so the doc's example can't silently drift from the shipped code:
  - it runs the real render → build_from_report → build_garden_audit_actions path,
  - the resulting instruction-set VALIDATES against the shipped Hashi schema,
  - it covers all three garden-audit action kinds (edit_note_text, add_relationship,
    link_to_moc) with the exact edit_note_text semantics the doc describes.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "tomo" / "scripts"
SCHEMA = REPO / "tomo" / "schemas" / "hashi-instructions.schema.json"
GEN = REPO / "scripts" / "gen-garden-audit-hashi-example.py"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load("gen_gah_example", GEN)
gar = _load("garden_audit_render", SCRIPTS / "garden-audit-render.py")
gap = _load("garden_audit_parser", SCRIPTS / "garden-audit-parser.py")
from lib.render_actions import build_garden_audit_actions  # noqa: E402


def _build_instructions() -> dict:
    """Rebuild the example instruction-set exactly as the generator does."""
    doc = gen._representative_doc()
    report = "\n".join(gar.render_frontmatter(doc)) + "\n" + gar.render_report(doc)
    wire = gar.build_wire_payload(doc)
    report = gen._make_decisions(report)
    confirmed = gap.build_from_report(report, wire)["confirmed_items"]
    actions = build_garden_audit_actions(confirmed)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "schema_version": "2", "type": "tomo-instructions",
        "source_suggestions": "garden-audit-report",
        "generated": now.isoformat().replace("+00:00", "Z"),
        "profile": doc["profile"], "tomo_version": None,
        "action_count": len(actions), "md_peer": "2026-07-21_1738_garden-audit",
        "actions": actions,
        "tomo": {"doc_type": "garden-audit", "state": "pending-apply", "run_id": doc["run_id"]},
    }


def test_example_validates_against_hashi_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(instance=_build_instructions(), schema=schema)  # raises on failure


def test_example_covers_all_three_action_kinds():
    actions = _build_instructions()["actions"]
    kinds = {a["action"] for a in actions}
    assert kinds == {"edit_note_text", "add_relationship", "link_to_moc"}


def test_edit_note_text_semantics():
    actions = _build_instructions()["actions"]
    edits = {a["match"]: a for a in actions if a["action"] == "edit_note_text"}
    # dead-link FIX (repoint): match [[Old]], replace [[New]] wikilink, occurrence all.
    fix = edits["[[023 Sparks MOC]]"]
    assert fix["replace"] == "[[023 Sparks (MOC)]]"
    assert fix["occurrence"] == "all"
    # dead-link REMOVE (unlink): keep the text, drop the [[ ]] → replace is the
    # inner text, NOT "". occurrence all.
    dead_remove = edits["[[024 Thinking About MOC]]"]
    assert dead_remove["replace"] == "024 Thinking About MOC"
    assert dead_remove["occurrence"] == "all"
    # broken-up up:: REMOVAL: whole-line match, replace "" (delete the line),
    # occurrence first — UNCHANGED by the de-link semantics.
    up_remove = edits["up:: [[021 Fleeting MOC]]"]
    assert up_remove["replace"] == ""
    assert up_remove["occurrence"] == "first"


def test_repoint_is_add_relationship_not_edit():
    # The broken-up REPOINT (F01) must be add_relationship, not edit_note_text.
    actions = _build_instructions()["actions"]
    rels = [a for a in actions if a["action"] == "add_relationship"]
    lines = {a["line"] for a in rels}
    assert "up:: [[020 Active MOC]]" in lines  # F01 repoint
    assert "up:: [[000 Home MOC]]" in lines    # F10 filing up::


def test_generator_writes_validated_artifacts(tmp_path):
    # The generator itself exits 0 (it validates before writing).
    import subprocess
    rc = subprocess.run(
        [sys.executable, str(GEN), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert rc.returncode == 0, rc.stderr
    inst = json.loads((tmp_path / "garden-audit-instructions.json").read_text(encoding="utf-8"))
    jsonschema.validate(instance=inst, schema=json.loads(SCHEMA.read_text(encoding="utf-8")))

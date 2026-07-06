#!/usr/bin/env python3
# version: 0.1.0
"""ADR-026 golden test: build_from_wire(unedited wire) == markdown parse.

Proves the JSON-only Pass-2 path (build_from_wire) reproduces the markdown path's
output for an UNedited wire — i.e. the wire is a faithful full mirror and the two
authoritative paths agree on the default case. This is the safety net for the
"JSON-only when changed, markdown otherwise, never a mix" contract.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "tomo" / "scripts"
PARSER = SCRIPTS / "suggestion-parser.py"
sys.path.insert(0, str(SCRIPTS))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


reducer = _load("reducer_golden", "suggestions-reducer.py")
render = _load("render_golden", "suggestions-render.py")
parser = _load("parser_golden", "suggestion-parser.py")


def _doc() -> dict:
    action = {
        "kind": "create_atomic_note",
        "suggested_title": "First Principles Thinking",
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "audio_peer": None,
        "atomic_note_worthiness": 0.9,
        "tags_to_add": ["topic/mind/concepts"],
        "classification": {"category": "Mind", "confidence": 0.8},
        "candidate_mocs": [
            {"path": "Atlas/200 Maps/Concepts (MOC).md", "score": 0.7, "pre_check": True,
             "anchor": {"type": "heading", "value": "Frameworks", "placement": "after",
                        "new_section": None, "alt_headings": ["Content"], "fit_confidence": 0.9}},
        ],
    }
    rendered_md = reducer.render_create_atomic_note(action, "first-principles", " (MOC)")
    # `item` mirrors what suggestions-reducer persists (Phase A).
    item = {
        "title": action["suggested_title"], "template": action["template"],
        "location": action["location"], "tags": action["tags_to_add"],
        "audio_peer": None, "worthiness": 0.9, "suppressed": False, "force_atomic": False,
    }
    return {
        "schema_version": "1", "generated": "2026-07-04T10:00:00Z",
        "run_id": "2026-07-04-1000-golden", "profile": "miyo", "source_items": 1,
        "conventions": {"parent_marker": "up::", "peer_marker": "related::", "moc_suffix": " (MOC)"},
        "sections": [{"id": "S01", "stem": "first-principles",
                      "actions": [{"kind": "create_atomic_note", "suggestion_id": "S01",
                                   "rendered_md": rendered_md,
                                   "candidate_mocs": reducer.persist_candidate_anchors(action),
                                   "item": item}]}],
        "proposed_mocs": [{"topic": "Systems Thinking", "items": ["S01"], "parent": "Root (MOC)",
                           "name": "Systems Thinking (MOC)", "tags": ["topic/systems"], "reason": "cluster"}],
        "daily_notes_updates": [], "needs_attention": [],
    }


def _markdown_output(doc: dict, tmp: Path) -> dict:
    parts = []
    parts += render.render_frontmatter(doc)
    parts += render.render_header(doc)
    parts += render.render_summary(doc)
    parts += render.render_suggestions(doc)
    parts += render.render_proposed_mocs(doc)
    md_path = tmp / "2026-07-04_1000_suggestions.md"
    md_path.write_text("\n".join(parts), encoding="utf-8")
    doc_path = tmp / "suggestions-doc.json"
    doc_path.write_text(json.dumps(doc), encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(PARSER), "--file", str(md_path), "--suggestions-doc", str(doc_path)],
        capture_output=True, text=True, cwd=str(tmp), check=True,
    )
    return json.loads(out.stdout)


def test_build_from_wire_matches_markdown_parse():
    doc = _doc()
    with tempfile.TemporaryDirectory() as td:
        expected = _markdown_output(doc, Path(td))
    wire = render.build_wire_payload(doc)
    actual = parser.build_from_wire(wire, "")
    assert actual == expected, (
        "JSON-only build_from_wire diverged from the markdown parse.\n"
        f"expected={json.dumps(expected, indent=2)}\nactual={json.dumps(actual, indent=2)}"
    )


def _doc_with_sections() -> dict:
    """Doc that also carries daily-note updates + a tag-handler group, so the
    golden test exercises the full mirror (not just notes + proposed MOCs)."""
    doc = _doc()
    daily = [{
        "daily_note_stem": "2026-07-04", "exists": True,
        "trackers": [{"field": "Sport", "value": True, "reason": "ran 5k",
                      "source_stem": "first-principles", "source_section": "S01"}],
        "log_entries": [], "log_links": [],
    }]
    doc["daily_notes_updates"] = daily
    doc["rendered_daily_updates_md"] = reducer.render_daily_notes_updates_block(daily)

    groups = [{
        "schema_version": "1", "handler": "captures",
        "target_path": "Atlas/Captures.md", "marker": "captures",
        "composed_block": "- a capture", "source_paths": ["Inbox/a.md"],
        "placement": "inside", "compose_mode": "field_template",
    }]
    doc["tag_handler_updates"] = groups
    doc["rendered_tag_handler_updates_md"] = reducer.render_tag_handler_updates_block(groups)
    return doc


def _markdown_output_full(doc: dict, tmp: Path) -> dict:
    parts = []
    parts += render.render_frontmatter(doc)
    parts += render.render_header(doc)
    parts += render.render_summary(doc)
    parts += render.render_daily_updates(doc)
    parts += render.render_tag_handler_updates(doc)
    parts += render.render_suggestions(doc)
    parts += render.render_proposed_mocs(doc)
    md_path = tmp / "2026-07-04_1000_suggestions.md"
    md_path.write_text("\n".join(parts), encoding="utf-8")
    doc_path = tmp / "suggestions-doc.json"
    doc_path.write_text(json.dumps(doc), encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(PARSER), "--file", str(md_path), "--suggestions-doc", str(doc_path)],
        capture_output=True, text=True, cwd=str(tmp), check=True,
    )
    return json.loads(out.stdout)


def test_full_mirror_matches_markdown_parse_with_daily_and_tag_handler():
    doc = _doc_with_sections()
    with tempfile.TemporaryDirectory() as td:
        expected = _markdown_output_full(doc, Path(td))
    wire = render.build_wire_payload(doc)
    actual = parser.build_from_wire(wire, "")
    assert actual == expected, (
        "Full-mirror build_from_wire diverged from the markdown parse.\n"
        f"expected={json.dumps(expected, indent=2)}\nactual={json.dumps(actual, indent=2)}"
    )


# ── Edited-wire behaviour (build_from_wire is the sole authority) ───────────

def _wire(**note_overrides) -> dict:
    note = {
        "id": "S01", "stem": "memo", "title": "My Note", "template": "t_note.md",
        "location": "Notes/", "tags": [], "audio_peer": None, "decision": "approve",
        "keep_source": False, "delete_source": False, "force_atomic": False,
        "suppressed": False, "worthiness": 0.9, "candidate_mocs": [],
    }
    note.update(note_overrides)
    return {
        "schema_version": "1", "generated": "x", "run_id": "x", "profile": "miyo",
        "source_items": 1, "emit_digest": "sha256:" + "0" * 64,
        "suggestions": [note], "proposed_mocs": [], "daily_updates": [],
        "tag_handler_groups": [],
    }


def test_skip_decision_moves_note_to_skipped():
    out = parser.build_from_wire(_wire(decision="skip"), "")
    assert out["confirmed_items"] == []
    assert out["skipped"] == [{"id": "S01", "source_path": "memo", "disposition": "skip"}]


def test_skip_with_delete_source_disposition():
    out = parser.build_from_wire(_wire(decision="skip", delete_source=True), "")
    assert out["skipped"][0]["disposition"] == "delete_source"


def test_keep_source_carries_to_confirmed_item():
    out = parser.build_from_wire(_wire(keep_source=True), "")
    assert out["confirmed_items"][0]["keep_source"] is True


def test_suppressed_force_atomic_yields_fan_resolution():
    out = parser.build_from_wire(_wire(suppressed=True, force_atomic=True), "")
    assert out["confirmed_items"] == []
    assert out["pending_fan_resolutions"] == [
        {"stem": "memo", "source_path": "memo", "log_entry_summary": "My Note"}
    ]


def test_flag1_anchorless_candidate_surfaced_but_filtered():
    # Hashi flag 1: a matched-but-unchecked/unanchored MOC must appear in the
    # wire (so the editor can offer it), yet build_from_wire keeps parity by
    # only linking selected candidates.
    action = {
        "kind": "create_atomic_note", "suggested_title": "N", "template": "t.md",
        "location": "L/", "audio_peer": None, "atomic_note_worthiness": 0.9,
        "tags_to_add": [], "candidate_mocs": [
            {"path": "Atlas/200 Maps/A (MOC).md", "pre_check": True, "score": 0.8,
             "anchor": {"type": "heading", "value": "H", "placement": "after",
                        "new_section": None, "alt_headings": [], "fit_confidence": 0.8}},
            {"path": "Atlas/200 Maps/B (MOC).md", "pre_check": False, "score": 0.2},
        ],
    }
    doc = {
        "schema_version": "1", "generated": "2026-07-06T10:00:00Z",
        "run_id": "r", "profile": "miyo", "source_items": 1,
        "conventions": {"parent_marker": "up::", "peer_marker": "related::", "moc_suffix": " (MOC)"},
        "sections": [{"id": "S01", "stem": "n", "actions": [{
            "kind": "create_atomic_note", "suggestion_id": "S01",
            "rendered_md": reducer.render_create_atomic_note(action, "n", " (MOC)"),
            "candidate_mocs": reducer.persist_candidate_anchors(action),
            "item": {"title": "N", "template": "t.md", "location": "L/", "tags": [],
                     "audio_peer": None, "worthiness": 0.9, "suppressed": False, "force_atomic": False}}]}],
        "proposed_mocs": [], "daily_notes_updates": [], "needs_attention": [],
    }
    wire = render.build_wire_payload(doc)
    cands = wire["suggestions"][0]["candidate_mocs"]
    assert [c["path"] for c in cands] == ["Atlas/200 Maps/A (MOC).md", "Atlas/200 Maps/B (MOC).md"]
    assert cands[0]["selected"] is True and cands[0]["anchor"] is not None
    assert cands[1]["selected"] is False and cands[1]["anchor"] is None  # surfaced, unresolved
    out = parser.build_from_wire(wire, "")
    item = [c for c in out["confirmed_items"] if c.get("action") != "create_moc"][0]
    assert item["parent_mocs"] == ["Atlas/200 Maps/A (MOC)"]  # only the selected one links


def test_flag3_tag_handler_context_in_wire():
    wire = render.build_wire_payload(_doc_with_sections())
    g = wire["tag_handler_groups"][0]
    assert g["handler"] == "captures"
    assert g["target_path"] == "Atlas/Captures.md"
    assert g["marker"] == "captures"
    assert g["source_paths"] == ["Inbox/a.md"]
    assert "a capture" in g["preview"]


def test_tag_handler_group_approval_and_keep_source_split():
    wire = _wire()
    wire["tag_handler_groups"] = [
        {"group_id": "th-a", "approved": True, "keep_source": True},
        {"group_id": "th-b", "approved": True, "keep_source": False},
        {"group_id": "th-c", "approved": False, "keep_source": False},
    ]
    out = parser.build_from_wire(wire, "")
    assert out["approved_tag_handler_group_ids"] == ["th-a", "th-b"]
    assert out["tag_handler_keep_source_group_ids"] == ["th-a"]

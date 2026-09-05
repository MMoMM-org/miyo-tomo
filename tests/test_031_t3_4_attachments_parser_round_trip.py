#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t3_4_attachments_parser_round_trip.py — attachments parser round trip.

Covers T3.4 (spec 031 Phase 3): the four suggestion-parser.py sites that carry
a per-item field from render to confirmed_items (the wire projection at :305,
the markdown defaults dict at :586, the "attachments" dispatch branch at
:704-712, and the markdown projection at :2006-2024) must all carry
`attachments` through, matching the existing `audio_peer` precedent exactly
(verified via `rg audio_peer tomo/scripts/suggestion-parser.py` — 4 hits,
same 4 line numbers the plan names).

Follows the golden-test methodology in test_suggestions_wire_golden.py:
build_from_wire(unedited wire) must equal the markdown parse (CON-5).

Spec: docs/XDD/specs/031-inbox-attachment-filing/plan/phase-3.md (T3.4)
Ref: PRD/AC-F3.3, AC-F3.4; SDD/Constraints CON-5
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


reducer = _load("reducer_t34", "suggestions-reducer.py")
render = _load("render_t34", "suggestions-render.py")
parser = _load("parser_t34", "suggestion-parser.py")

ATTACHMENT_PATH = "100 Inbox/Images/prag-karte.jpg"
ATTACHMENTS = [ATTACHMENT_PATH, "100 Inbox/scan.pdf"]


def _doc(attachments: list | None = None) -> dict:
    action = {
        "kind": "create_atomic_note",
        "suggested_title": "Prague Trip",
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "audio_peer": None,
        "atomic_note_worthiness": 0.9,
        "tags_to_add": ["topic/travel"],
        "classification": {"category": "Travel", "confidence": 0.8},
        "candidate_mocs": [],
    }
    if attachments is not None:
        action["attachments"] = attachments
    rendered_md = reducer.render_create_atomic_note(action, "prague-trip", " (MOC)")
    item = {
        "title": action["suggested_title"], "template": action["template"],
        "location": action["location"], "tags": action["tags_to_add"],
        "audio_peer": None, "worthiness": 0.9, "suppressed": False, "force_atomic": False,
        "attachments": attachments if attachments is not None else [],
    }
    return {
        "schema_version": "1", "generated": "2026-09-05T10:00:00Z",
        "run_id": "2026-09-05-1000-t34", "profile": "miyo", "source_items": 1,
        "conventions": {"parent_marker": "up::", "peer_marker": "related::", "moc_suffix": " (MOC)"},
        "sections": [{"id": "S01", "stem": "prague-trip",
                      "actions": [{"kind": "create_atomic_note", "suggestion_id": "S01",
                                   "rendered_md": rendered_md,
                                   "candidate_mocs": [],
                                   "item": item}]}],
        "proposed_mocs": [], "daily_notes_updates": [], "needs_attention": [],
    }


def _markdown_output(doc: dict, tmp: Path) -> dict:
    parts = []
    parts += render.render_frontmatter(doc)
    parts += render.render_header(doc)
    parts += render.render_summary(doc)
    parts += render.render_suggestions(doc)
    parts += render.render_proposed_mocs(doc)
    md_path = tmp / "2026-09-05_1000_suggestions.md"
    md_path.write_text("\n".join(parts), encoding="utf-8")
    doc_path = tmp / "suggestions-doc.json"
    doc_path.write_text(json.dumps(doc), encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(PARSER), "--file", str(md_path), "--suggestions-doc", str(doc_path)],
        capture_output=True, text=True, cwd=str(tmp), check=True,
    )
    return json.loads(out.stdout)


def _confirmed(parsed: dict) -> dict:
    items = parsed["confirmed_items"]
    assert len(items) == 1, f"expected exactly one confirmed item, got {items!r}"
    return items[0]


# ---------------------------------------------------------------------------
# Markdown path
# ---------------------------------------------------------------------------


def test_markdown_attachments_line_round_trips():
    """An **Attachments:** line parses back to the identical list."""
    doc = _doc(ATTACHMENTS)
    with tempfile.TemporaryDirectory() as td:
        parsed = _markdown_output(doc, Path(td))
    assert _confirmed(parsed)["attachments"] == ATTACHMENTS


def test_markdown_no_attachment_line_yields_empty_list():
    """An item with no attachment line yields [] from the defaults dict."""
    doc = _doc(None)
    with tempfile.TemporaryDirectory() as td:
        parsed = _markdown_output(doc, Path(td))
    assert _confirmed(parsed)["attachments"] == []


def test_parse_section_defaults_dict_initializes_attachments_key():
    """parse_section's `result` dict carries `attachments` (defaulted to [])
    even before any field-line is parsed — matching the audio_peer precedent
    at the same defaults-dict site. Calls parse_section directly so this is
    load-bearing independent of downstream .get(...)-with-fallback callers."""
    lines = [
        "**Source:** [[some-note]]",
        "**Suggested name:** Some Note",
    ]
    result = parser.parse_section("S01", lines)
    assert "attachments" in result
    assert result["attachments"] == []


# ---------------------------------------------------------------------------
# Wire path
# ---------------------------------------------------------------------------


def test_wire_path_carries_attachments_through_build_from_wire():
    """build_from_wire carries the attachments list through to confirmed_items."""
    doc = _doc(ATTACHMENTS)
    wire = render.build_wire_payload(doc)
    parsed = parser.build_from_wire(wire, "")
    assert _confirmed(parsed)["attachments"] == ATTACHMENTS


def test_wire_path_no_attachments_yields_empty_list():
    doc = _doc(None)
    wire = render.build_wire_payload(doc)
    parsed = parser.build_from_wire(wire, "")
    assert _confirmed(parsed)["attachments"] == []


# ---------------------------------------------------------------------------
# CON-5 — both paths produce identical confirmed_items for the same item
# ---------------------------------------------------------------------------


def test_both_paths_produce_identical_confirmed_items():
    """Golden-test style: build_from_wire(unedited wire) == markdown parse,
    for an item that carries attachments (CON-5, asserted directly)."""
    doc = _doc(ATTACHMENTS)
    with tempfile.TemporaryDirectory() as td:
        expected = _markdown_output(doc, Path(td))
    wire = render.build_wire_payload(doc)
    actual = parser.build_from_wire(wire, "")
    assert actual == expected, (
        "JSON-only build_from_wire diverged from the markdown parse for an "
        "item carrying attachments.\n"
        f"expected={json.dumps(expected, indent=2)}\nactual={json.dumps(actual, indent=2)}"
    )
    # Anchor the guarantee to the field that matters for this spec, not just
    # overall dict equality (which could pass with both sides wrong).
    assert expected["confirmed_items"][0]["attachments"] == ATTACHMENTS
    assert actual["confirmed_items"][0]["attachments"] == ATTACHMENTS


# ---------------------------------------------------------------------------
# Stability — render -> parse -> render is stable
# ---------------------------------------------------------------------------


def test_round_trip_render_parse_render_is_stable():
    """Re-rendering the parsed attachments list reproduces the same
    **Attachments:** line — the round trip loses nothing."""
    doc = _doc(ATTACHMENTS)
    original_md = doc["sections"][0]["actions"][0]["rendered_md"]
    with tempfile.TemporaryDirectory() as td:
        parsed = _markdown_output(doc, Path(td))
    confirmed = _confirmed(parsed)

    re_action = {
        "kind": "create_atomic_note",
        "suggested_title": confirmed["title"],
        "template": confirmed["template"],
        "location": confirmed["destination"],
        "candidate_mocs": [],
        "tags_to_add": confirmed["tags"],
        "attachments": confirmed["attachments"],
    }
    re_rendered = reducer.render_create_atomic_note(re_action, "prague-trip", " (MOC)")

    original_line = next(
        ln for ln in original_md.split("\n") if ln.startswith("**Attachments:**")
    )
    re_line = next(
        ln for ln in re_rendered.split("\n") if ln.startswith("**Attachments:**")
    )
    assert original_line == re_line

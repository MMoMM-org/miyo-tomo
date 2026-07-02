#!/usr/bin/env python3
# version: 0.1.0
"""test_placement_anchor_threading.py — spec 022/023: Pass-1 placement anchor
threaded through to Pass-2 apply.

Confirmed hot-path bug: the LLM-resolved candidate_mocs[].anchor was dropped
between Pass-1 (item-result) and Pass-2 (rendered instructions), so applied
links silently fell back to the old _pick_anchor heuristic. These tests pin the
three-layer fix end-to-end:

  1. suggestions-reducer persists candidate_mocs:[{path, anchor}] into the
     suggestions-doc JSON (and the schema permits it).
  2. suggestion-parser emits candidate_mocs:[{path, anchor}] per checked MOC;
     default = the structured doc-JSON anchor, override = a hand-edited
     **Placement:** line.
  3. instruction-render honors candidate_mocs[].anchor (no re-resolution).

Fixtures are the real Pass-1 anchors from the live tomo-tmp item-results
(First Principles Thinking, Beppu Onsen) and live-rendered markdown — never
invented (per feedback_fixture_from_live_render.md).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

sys.path.insert(0, str(SCRIPTS_DIR))

from jsonschema import validate  # noqa: E402


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_reducer = _load("suggestions_reducer", "suggestions-reducer.py")
_parser = _load("suggestion_parser", "suggestion-parser.py")
_ir = _load("instruction_render", "instruction-render.py")


# ---------------------------------------------------------------------------
# Real Pass-1 anchors (verbatim from the live item-results)
# ---------------------------------------------------------------------------

# tomo-instance/tomo-tmp/items/First Principles Thinking.result.json
FPT_ANCHOR = {
    "type": "heading",
    "value": "Thinking Frameworks",
    "placement": "after",
    "new_section": None,
    "fit_confidence": 0.9,
}
FPT_MOC = "Atlas/200 Maps/Concepts (MOC).md"

# tomo-instance/tomo-tmp/items/Beppu Onsen.result.json
BEPPU_ANCHOR = {
    "type": "callout",
    "value": None,
    "placement": "before",
    "new_section": "Japanische Geographie",
    "alt_headings": ["Content"],
}
BEPPU_MOC = "Atlas/200 Maps/Japan (MOC).md"


def _fpt_action() -> dict:
    return {
        "kind": "create_atomic_note",
        "source_stem": "First Principles Thinking",
        "suggested_title": "First Principles Thinking — Reasoning from Foundational Truths",
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [
            {"path": FPT_MOC, "score": 0.33, "pre_check": True, "anchor": FPT_ANCHOR}
        ],
        "tags_to_add": ["topic/mind/concepts"],
        "atomic_note_worthiness": 0.9,
    }


def _beppu_action() -> dict:
    return {
        "kind": "create_atomic_note",
        "source_stem": "Beppu Onsen",
        "suggested_title": "Beppu — Japans berühmteste Onsen-Stadt auf Kyushu",
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [
            {"path": BEPPU_MOC, "score": 0.47, "pre_check": True, "anchor": BEPPU_ANCHOR}
        ],
        "tags_to_add": ["topic/japan/city"],
        "atomic_note_worthiness": 0.3,
    }


# ---------------------------------------------------------------------------
# Layer 1 — reducer persists candidate_mocs:[{path, anchor}] + schema allows it
# ---------------------------------------------------------------------------


class TestReducerPersistsAnchor:
    def test_persist_candidate_anchors_returns_slim_path_anchor(self):
        out = _reducer.persist_candidate_anchors(_fpt_action())
        assert out == [{"path": FPT_MOC, "anchor": FPT_ANCHOR}]

    def test_persist_skips_candidate_without_anchor(self):
        action = {
            "kind": "create_atomic_note",
            "candidate_mocs": [{"path": "Atlas/200 Maps/X (MOC).md", "score": 0.6}],
        }
        assert _reducer.persist_candidate_anchors(action) == []

    def test_persist_empty_when_no_candidates(self):
        assert _reducer.persist_candidate_anchors({"kind": "create_atomic_note"}) == []

    def test_doc_action_with_anchor_validates_against_schema(self):
        schema = json.loads(
            (SCHEMAS_DIR / "suggestions-doc.schema.json").read_text(encoding="utf-8")
        )
        doc = {
            "schema_version": "1",
            "generated": "2026-06-16T00:00:00Z",
            "run_id": "r1",
            "profile": "miyo",
            "source_items": 1,
            "sections": [
                {
                    "id": "S01",
                    "stem": "First Principles Thinking",
                    "actions": [
                        {
                            "kind": "create_atomic_note",
                            "rendered_md": "...",
                            "suggestion_id": "S01",
                            "candidate_mocs": _reducer.persist_candidate_anchors(
                                _fpt_action()
                            ),
                        }
                    ],
                }
            ],
        }
        # Raises ValidationError on regression (additionalProperties:false).
        validate(instance=doc, schema=schema)


# ---------------------------------------------------------------------------
# Layer 2 — parser emits candidate_mocs:[{path, anchor}], default = doc anchor
# ---------------------------------------------------------------------------


def _render_section_md(action: dict, stem: str) -> str:
    """Live-render the per-item markdown block (no invented fixtures)."""
    return _reducer.render_create_atomic_note(action, stem, " (MOC)")


def _doc_anchor_map_for(action: dict) -> dict[str, dict]:
    """Build the {moc_stem → anchor} default map the reducer would persist."""
    per = {}
    for c in _reducer.persist_candidate_anchors(action):
        per[_parser._moc_path_stem(c["path"])] = c["anchor"]
    return per


class TestParserDefaultAnchor:
    def test_fpt_default_anchor_from_doc_json(self):
        md = _render_section_md(_fpt_action(), "First Principles Thinking")
        # Approve must be checked so the item is confirmed.
        assert "- [x] Approve" in md
        item = _parser.parse_section(
            "S01", md.splitlines(), _doc_anchor_map_for(_fpt_action())
        )
        assert item is not None
        cands = item["candidate_mocs"]
        assert len(cands) == 1
        assert _parser._moc_path_stem(cands[0]["path"]) == "concepts (moc)"
        # Unedited Placement line round-trips to the SAME heading anchor.
        assert cands[0]["anchor"]["type"] == "heading"
        assert cands[0]["anchor"]["value"] == "Thinking Frameworks"

    def test_beppu_default_anchor_new_section_callout(self):
        md = _render_section_md(_beppu_action(), "Beppu Onsen")
        # Beppu atomic_note_worthiness=0.3 → Approve renders unchecked.
        assert "- [ ] Approve" in md
        item = _parser.parse_section(
            "S05", md.splitlines(), _doc_anchor_map_for(_beppu_action())
        )
        assert item is not None
        cands = item["candidate_mocs"]
        assert len(cands) == 1
        anchor = cands[0]["anchor"]
        # Unedited "new section ... (before the footer)" → callout/before.
        assert anchor["type"] == "callout"
        assert anchor["placement"] == "before"
        assert anchor["new_section"] == "Japanische Geographie"

    def test_unchecked_moc_yields_no_candidate(self):
        action = _beppu_action()
        action["candidate_mocs"][0]["pre_check"] = False
        action["atomic_note_worthiness"] = 0.3
        md = _render_section_md(action, "Beppu Onsen")
        assert "- [ ] [[Atlas/200 Maps/Japan (MOC)]]" in md
        item = _parser.parse_section(
            "S05", md.splitlines(), _doc_anchor_map_for(action)
        )
        assert item is not None
        assert item["candidate_mocs"] == []

    def test_no_doc_anchor_no_placement_yields_no_candidate(self):
        # A bare checked MOC with neither a doc-anchor default nor a Placement
        # line records no candidate (back-compat: render falls back).
        md = "\n".join(
            [
                "**Source:** [[Note]]",
                "**Link to MOC:**",
                "- [x] [[Atlas/200 Maps/Some (MOC)]]",
                "",
                "**Decision (atomic note):**",
                "- [x] Approve",
            ]
        )
        item = _parser.parse_section("S01", md.splitlines(), {})
        assert item is not None
        assert item["candidate_mocs"] == []
        assert item["parent_mocs"] == ["Atlas/200 Maps/Some (MOC)"]


# ---------------------------------------------------------------------------
# Layer 2b — hand-edited Placement line overrides the structured default
# ---------------------------------------------------------------------------


class TestParserPlacementOverride:
    def test_edited_heading_overrides_doc_default(self):
        md = _render_section_md(_fpt_action(), "First Principles Thinking")
        # User edits the heading: Thinking Frameworks → Mental Models.
        edited = md.replace("## Thinking Frameworks", "## Mental Models")
        assert "## Mental Models" in edited
        item = _parser.parse_section(
            "S08", edited.splitlines(), _doc_anchor_map_for(_fpt_action())
        )
        assert item is not None
        anchor = item["candidate_mocs"][0]["anchor"]
        assert anchor["type"] == "heading"
        assert anchor["value"] == "Mental Models"

    def test_last_resort_placement_falls_back_to_doc_default(self):
        # If the line is the last-resort "under the note title" form, the
        # structured default wins (override returns None).
        line = _parser.parse_placement_line(
            "**Placement:** under the note title (no matching section or callout found)"
        )
        assert line is None

    def test_reverse_parse_new_section_end_of_moc_is_line_anchor(self):
        anchor = _parser.parse_placement_line(
            "**Placement:** new section `## Places` (at the end of the MOC)    ← rename or change"
        )
        assert anchor == {
            "type": "line",
            "value": None,
            "placement": "after",
            "new_section": "Places",
        }

    def test_reverse_parse_inside_callout(self):
        anchor = _parser.parse_placement_line(
            "**Placement:** inside the `> [!blocks]` callout    ← change to a `## Heading` to place under a section"
        )
        assert anchor["type"] == "callout"
        assert anchor["placement"] == "inside"
        assert anchor["value"] == "> [!blocks]"


# ---------------------------------------------------------------------------
# Layer 3 — instruction-render honors candidate_mocs[].anchor (no re-resolve)
# ---------------------------------------------------------------------------


def _confirmed_item(stem: str, title: str, moc: str, anchor: dict) -> dict:
    return {
        "id": "S01",
        "source_path": f"100 Inbox/{stem}.md",
        "title": title,
        "action": None,
        "parent_mocs": [moc],
        "candidate_mocs": [{"path": moc, "anchor": anchor}],
    }


class TestRenderHonorsAnchor:
    def test_fpt_keeps_thinking_frameworks_heading(self):
        item = _confirmed_item(
            "First Principles Thinking",
            "First Principles Thinking — Reasoning from Foundational Truths",
            FPT_MOC,
            FPT_ANCHOR,
        )
        actions = _ir._build_link_to_moc_actions([item], [0])
        link = next(a for a in actions if a["action"] == "link_to_moc")
        assert link["anchor"]["type"] == "heading"
        assert link["anchor"]["value"] == "Thinking Frameworks"
        assert link["placement"] == "after"
        # fit_confidence must NOT leak into the Pass-2 anchor (no-leak contract).
        assert "fit_confidence" not in link["anchor"]

    def test_beppu_keeps_new_section_before_footer(self):
        item = _confirmed_item(
            "Beppu Onsen",
            "Beppu — Japans berühmteste Onsen-Stadt auf Kyushu",
            BEPPU_MOC,
            BEPPU_ANCHOR,
        )
        actions = _ir._build_link_to_moc_actions([item], [0])
        link = next(a for a in actions if a["action"] == "link_to_moc")
        assert link["anchor"]["type"] == "callout"
        assert link["placement"] == "before"
        assert link["new_section"] == "Japanische Geographie"

    def test_beppu_new_section_serializes_with_heading_and_link(self):
        item = _confirmed_item(
            "Beppu Onsen",
            "Beppu — Japans berühmteste Onsen-Stadt auf Kyushu",
            BEPPU_MOC,
            BEPPU_ANCHOR,
        )
        actions = _ir._build_link_to_moc_actions([item], [0])
        _ir._serialize_new_sections(actions)
        link = next(a for a in actions if a["action"] == "link_to_moc")
        line = link["line_to_add"]
        assert line.startswith("## Japanische Geographie")
        assert "- [[Beppu — Japans berühmteste Onsen-Stadt auf Kyushu]]" in line


# ---------------------------------------------------------------------------
# End-to-end: reducer → parser → render honors the FPT anchor (no "Core Concepts")
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_fpt_anchor_survives_reducer_to_render(self):
        action = _fpt_action()
        md = _render_section_md(action, "First Principles Thinking")
        item = _parser.parse_section(
            "S08", md.splitlines(), _doc_anchor_map_for(action)
        )
        confirmed = {
            "id": "S08",
            "source_path": "100 Inbox/First Principles Thinking.md",
            "title": action["suggested_title"],
            "action": None,
            "parent_mocs": item["parent_mocs"],
            "candidate_mocs": item["candidate_mocs"],
        }
        actions = _ir._build_link_to_moc_actions([confirmed], [0])
        link = next(a for a in actions if a["action"] == "link_to_moc")
        assert link["anchor"]["value"] == "Thinking Frameworks"

    def test_beppu_anchor_survives_reducer_to_render(self):
        """Headline bug case: new-section-before-footer must not collapse to [!blocks]."""
        action = _beppu_action()
        # pre_check=True so the MOC checkbox renders [x] and the parser picks it up.
        action["candidate_mocs"][0]["pre_check"] = True
        md = _render_section_md(action, "Beppu Onsen")
        item = _parser.parse_section(
            "S05", md.splitlines(), _doc_anchor_map_for(action)
        )
        assert item is not None, "parse_section must return an item"
        assert len(item["candidate_mocs"]) == 1, "one checked MOC must produce one candidate"
        confirmed = {
            "id": "S05",
            "source_path": "100 Inbox/Beppu Onsen.md",
            "title": action["suggested_title"],
            "action": None,
            "parent_mocs": item["parent_mocs"],
            "candidate_mocs": item["candidate_mocs"],
        }
        actions = _ir._build_link_to_moc_actions([confirmed], [0])
        link = next(a for a in actions if a["action"] == "link_to_moc")
        # Bug guard: must NOT collapse to [!blocks] Key Concepts — the old heuristic path.
        assert link["anchor"]["type"] == "callout"
        assert link["placement"] == "before"
        assert link["new_section"] == "Japanische Geographie"
        assert link["anchor"].get("value") is None  # no pre-existing callout matched


# ---------------------------------------------------------------------------
# Pending-MOC state machine — each checked MOC binds to its OWN Placement line
# ---------------------------------------------------------------------------


class TestMultiMocBinding:
    def test_two_consecutive_checked_mocs_each_get_own_anchor(self):
        """Two checked MOC checkboxes each followed by a distinct Placement line
        must bind independently — Japan→callout/new_section, Concepts→heading.

        This tests the `pending_moc` state machine: the second Placement line
        must NOT overwrite the first, and neither anchor must bleed to both MOCs.
        """
        md = "\n".join([
            "**Source:** [[Multi Topic Note]]",
            "**Link to MOC:**",
            "- [x] [[Atlas/200 Maps/Japan (MOC)]]",
            "**Placement:** new section `## Japanische Geographie` (before the footer)    ← rename or change",
            "- [x] [[Atlas/200 Maps/Concepts (MOC)]]",
            "**Placement:** under `## Thinking Frameworks`    ← edit the heading to move the link",
            "",
            "**Decision (atomic note):**",
            "- [x] Approve",
        ])
        doc_anchors = {
            "japan (moc)": BEPPU_ANCHOR,
            "concepts (moc)": FPT_ANCHOR,
        }
        item = _parser.parse_section("S01", md.splitlines(), doc_anchors)
        assert item is not None
        cands = item["candidate_mocs"]
        assert len(cands) == 2, f"expected 2 candidates, got {len(cands)}: {cands}"

        # Identify each candidate by MOC stem — order must not be assumed.
        by_stem = {_parser._moc_path_stem(c["path"]): c["anchor"] for c in cands}

        japan_anchor = by_stem.get("japan (moc)")
        assert japan_anchor is not None, "Japan (MOC) candidate missing"
        assert japan_anchor["type"] == "callout"
        assert japan_anchor["placement"] == "before"
        assert japan_anchor["new_section"] == "Japanische Geographie"

        concepts_anchor = by_stem.get("concepts (moc)")
        assert concepts_anchor is not None, "Concepts (MOC) candidate missing"
        assert concepts_anchor["type"] == "heading"
        assert concepts_anchor["value"] == "Thinking Frameworks"

        # Strict non-bleed: neither anchor should appear on the wrong MOC.
        assert by_stem["japan (moc)"] is not by_stem["concepts (moc)"]
        assert by_stem["japan (moc)"]["type"] != by_stem["concepts (moc)"]["type"]


# ---------------------------------------------------------------------------
# _default_doc_path — sibling-file branch
# ---------------------------------------------------------------------------


class TestDefaultDocPath:
    def test_sibling_file_returned_when_present(self, tmp_path):
        """When suggestions-doc.json exists next to the markdown file,
        _default_doc_path returns that sibling path rather than the canonical
        tomo-tmp/suggestions-doc.json fallback."""
        sibling = tmp_path / "suggestions-doc.json"
        sibling.write_text("{}", encoding="utf-8")
        md_path = str(tmp_path / "2026-06-17_suggestions.md")
        result = _parser._default_doc_path(md_path)
        assert result == str(sibling)

    def test_canonical_fallback_when_no_sibling(self, tmp_path):
        """When no sibling exists, _default_doc_path returns the canonical
        tomo-tmp/suggestions-doc.json (relative path, caller resolves from cwd)."""
        md_path = str(tmp_path / "2026-06-17_suggestions.md")
        # No sibling created — file does not exist.
        result = _parser._default_doc_path(md_path)
        import os
        assert result == os.path.join("tomo-tmp", "suggestions-doc.json")

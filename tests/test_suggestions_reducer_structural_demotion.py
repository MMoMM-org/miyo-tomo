#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_reducer_structural_demotion.py — #71 structural-heading backstop.

Covers demote_structural_anchors in suggestions-reducer: a tier-1 heading anchor
whose heading is a known structural/scaffolding heading (Content, Structure, ...)
is deterministically demoted to a tier-2 new-section anchor, regardless of the
LLM's self-assessed fit_confidence (spec 023 ADR-5).

Key invariant test: a demoted anchor, once rendered by _placement_line and
reverse-parsed by suggestion-parser.parse_placement_line, recovers the SAME
tier-2 anchor a genuine analyst tier-2 decision would — proving the demotion is
indistinguishable downstream (no Pass-2 change needed).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_reducer = _load("suggestions_reducer", SCRIPTS_DIR / "suggestions-reducer.py")
_parser = _load("suggestion_parser", SCRIPTS_DIR / "suggestion-parser.py")

demote_structural_anchors = _reducer.demote_structural_anchors
moc_link_line = _reducer.moc_link_line
parse_placement_line = _parser.parse_placement_line


def _action(anchor: dict | None, *, title: str = "Asakusa Senso-ji") -> dict:
    """Minimal create_atomic_note action with one candidate MOC carrying `anchor`."""
    return {
        "kind": "create_atomic_note",
        "suggested_title": title,
        "candidate_mocs": [{"path": "MOCs/Japan.md", "anchor": anchor}],
    }


# ── Core demotion ──────────────────────────────────────────────────────────

def test_demotes_structural_heading():
    action = _action({"type": "heading", "value": "Content", "fit_confidence": 0.72})
    n = demote_structural_anchors(action, "asakusa-senso-ji")
    assert n == 1
    anchor = action["candidate_mocs"][0]["anchor"]
    assert anchor == {
        "type": "callout",
        "value": None,
        "placement": "before",
        "new_section": "Asakusa Senso-ji",
        "alt_headings": ["Content"],
    }
    # fit_confidence must NOT survive onto a tier-2 anchor.
    assert "fit_confidence" not in anchor


def test_case_and_whitespace_insensitive():
    for raw in ("  content  ", "CONTENT", "Link MOC", "link moc"):
        action = _action({"type": "heading", "value": raw, "fit_confidence": 0.9})
        assert demote_structural_anchors(action, "s") == 1
        assert action["candidate_mocs"][0]["anchor"]["type"] == "callout"


def test_non_structural_heading_untouched():
    original = {"type": "heading", "value": "Cognitive Biases", "fit_confidence": 0.72}
    action = _action(dict(original))
    assert demote_structural_anchors(action, "s") == 0
    assert action["candidate_mocs"][0]["anchor"] == original


def test_preserves_and_prepends_alt_headings():
    action = _action({
        "type": "heading", "value": "Structure", "fit_confidence": 0.7,
        "alt_headings": ["Runner Up", "Structure"],  # dupe of rejected must not double
    })
    demote_structural_anchors(action, "s")
    assert action["candidate_mocs"][0]["anchor"]["alt_headings"] == ["Structure", "Runner Up"]


def test_new_section_falls_back_to_stem_without_title():
    action = _action({"type": "heading", "value": "Content"}, title="")
    demote_structural_anchors(action, "my-note-stem")
    assert action["candidate_mocs"][0]["anchor"]["new_section"] == "my-note-stem"


def test_non_heading_anchor_untouched():
    for anchor in (
        {"type": "callout", "value": "[!blocks] Key Concepts"},
        {"type": "line", "value": None, "new_section": "Topic"},
    ):
        action = _action(dict(anchor))
        assert demote_structural_anchors(action, "s") == 0
        assert action["candidate_mocs"][0]["anchor"] == anchor


def test_null_value_heading_untouched():
    # value:null heading is unresolved, not a real tier-1 structural slip.
    action = _action({"type": "heading", "value": None})
    assert demote_structural_anchors(action, "s") == 0


def test_multiple_candidate_mocs_only_structural_demoted():
    action = {
        "kind": "create_atomic_note",
        "suggested_title": "Note",
        "candidate_mocs": [
            {"path": "A.md", "anchor": {"type": "heading", "value": "Content", "fit_confidence": 0.8}},
            {"path": "B.md", "anchor": {"type": "heading", "value": "Real Topic", "fit_confidence": 0.8}},
        ],
    }
    assert demote_structural_anchors(action, "s") == 1
    assert action["candidate_mocs"][0]["anchor"]["type"] == "callout"
    assert action["candidate_mocs"][1]["anchor"]["type"] == "heading"


def test_no_candidate_mocs_is_safe():
    assert demote_structural_anchors({"kind": "create_atomic_note"}, "s") == 0


# ── Downstream-invariant: demoted anchor round-trips as a genuine tier-2 ─────

def test_demoted_anchor_roundtrips_as_tier2():
    """A demoted structural anchor, rendered then reverse-parsed by the Pass-2
    markdown parser, recovers the exact tier-2 anchor a real analyst tier-2 would."""
    action = _action({"type": "heading", "value": "Content", "fit_confidence": 0.72})
    demote_structural_anchors(action, "asakusa")
    moc = action["candidate_mocs"][0]

    rendered = moc_link_line(moc)
    # The **Placement:** line is one of the newline-joined parts.
    placement_line = next(ln for ln in rendered.split("\n") if "**Placement:**" in ln)
    assert "new section `## Asakusa Senso-ji` (before the footer)" in placement_line

    recovered = parse_placement_line(placement_line)
    assert recovered == {
        "type": "callout",
        "value": None,
        "placement": "before",
        "new_section": "Asakusa Senso-ji",
    }


# ── SSoT: analysis tool and runtime share one list ──────────────────────────

def test_structural_heading_list_is_single_source_of_truth():
    import lib.structural_headings as sh
    analyze = _load(
        "analyze_placement_confidence", REPO_ROOT / "scripts" / "analyze-placement-confidence.py"
    )
    # Same object — the analysis tool imports the runtime lib's list, never copies it.
    assert analyze.DEFAULT_STRUCTURAL_HEADINGS is sh.DEFAULT_STRUCTURAL_HEADINGS

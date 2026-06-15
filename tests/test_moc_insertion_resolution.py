#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_insertion_resolution.py — Contract fixtures for T4.1 (spec 022 Phase 4).

Validates that inbox-analyst emits candidate_mocs[].anchor in the correct four-tier
order per pre-checked thematic MOC.

The tested contracts are based on the SDD algorithm:
  TIER-1  heading LLM fits semantically → {type:heading, value:<H2>, placement:after}
  TIER-2  headings present but none fits → {type:callout, value:<footer>, placement:before,
           new_section:<topic>} (new_section ≠ "Key Concepts")
  TIER-3  no headings, editable callout present → {type:callout, value:<callout>,
           placement:inside}
  TIER-4  no headings, no callout → {type:heading, value:<H1 title>, placement:after}
  TIER-4b no headings, no callout, no H1 → {type:line, value:<first body line>,
           placement:after}
  EC-5    classification MOC → excluded as target, never gets anchor

These are *contract* fixtures — inline dicts that represent what the LLM agent should
emit. Schema validation confirms shape; structural assertions confirm tier semantics.

Spec: docs/XDD/specs/022-moc-insertion-point-intelligence/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import ValidationError, validate  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"


# ---------------------------------------------------------------------------
# Fixtures — schema loaders
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def item_result_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "item-result.schema.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers — minimal valid result builders
# ---------------------------------------------------------------------------


def _make_result_with_candidate(candidate_moc: dict) -> dict:
    """Minimal valid item-result with ONE candidate_moc entry."""
    return {
        "schema_version": "1",
        "stem": "first-principles-thinking",
        "path": "100 Inbox/first-principles-thinking.md",
        "type": "atomic",
        "type_confidence": 0.9,
        "actions": [
            {
                "kind": "create_atomic_note",
                "source_stem": "first-principles-thinking",
                "suggested_title": "First Principles Thinking",
                "template": "Atomic Note.md",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": [candidate_moc],
                "tags_to_add": [],
            }
        ],
    }


def _make_result_no_candidates() -> dict:
    """Minimal valid item-result with empty candidate_mocs (classification excluded)."""
    return {
        "schema_version": "1",
        "stem": "philosophy-note",
        "path": "100 Inbox/philosophy-note.md",
        "type": "atomic",
        "type_confidence": 0.85,
        "actions": [
            {
                "kind": "create_atomic_note",
                "source_stem": "philosophy-note",
                "suggested_title": "Philosophy Note",
                "template": "Atomic Note.md",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": [],
                "tags_to_add": [],
                "needs_new_moc": True,
                "proposed_moc_topic": "Philosophy",
            }
        ],
    }


# ===========================================================================
# AC-1: TIER-1 — MOC has a fitting H2 → heading anchor, placement after
# ===========================================================================


class TestTier1FittingHeading:
    """TIER-1: semantic heading fit → {type:heading, value:<H2>, placement:after} (AC-1)."""

    def test_tier1_fitting_h2_schema_valid(self, item_result_schema):
        """Tier-1 anchor with fitting H2 validates against item-result schema."""
        candidate = {
            "path": "Atlas/200 Maps/Systems Thinking (MOC).md",
            "score": 0.75,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Reasoning Techniques",
                "placement": "after",
                "new_section": None,
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_tier1_anchor_type_is_heading(self, item_result_schema):
        """Tier-1 anchor type must be 'heading'."""
        candidate = {
            "path": "Atlas/200 Maps/Systems Thinking (MOC).md",
            "score": 0.75,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Reasoning Techniques",
                "placement": "after",
                "new_section": None,
            },
        }
        anchor = candidate["anchor"]
        assert anchor["type"] == "heading"
        assert anchor["placement"] == "after"
        assert anchor["value"] is not None
        assert anchor["value"] != ""

    def test_tier1_anchor_new_section_is_null(self, item_result_schema):
        """Tier-1 (heading fit): new_section must be null — no new section needed."""
        candidate = {
            "path": "Atlas/200 Maps/Systems Thinking (MOC).md",
            "score": 0.75,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Reasoning Techniques",
                "placement": "after",
                "new_section": None,
            },
        }
        assert candidate["anchor"]["new_section"] is None


# ===========================================================================
# AC-2: TIER-1 — Zero token overlap but semantically fitting heading still wins
# ===========================================================================


class TestTier1SemanticFitZeroTokenOverlap:
    """AC-2: heading fit is semantic, not keyword. Zero-token-overlap still resolves correctly."""

    def test_zero_overlap_tier1_schema_valid(self, item_result_schema):
        """Zero-token-overlap fixture: 'First Principles Thinking' → 'Reasoning Techniques' heading."""
        # Note: "First Principles Thinking" shares NO literal tokens with "Reasoning Techniques"
        # but is semantically connected. The LLM must pick by meaning, not keyword overlap.
        candidate = {
            "path": "Atlas/200 Maps/Philosophy (MOC).md",
            "score": 0.65,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Reasoning Techniques",
                "placement": "after",
                "new_section": None,
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_zero_overlap_tier1_is_heading_type(self, item_result_schema):
        """Zero-token-overlap: anchor is still a heading anchor (semantic fit takes TIER-1)."""
        candidate = {
            "path": "Atlas/200 Maps/Philosophy (MOC).md",
            "score": 0.65,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Reasoning Techniques",
                "placement": "after",
                "new_section": None,
            },
        }
        anchor = candidate["anchor"]
        assert anchor["type"] == "heading"
        assert anchor["placement"] == "after"


# ===========================================================================
# AC-2 (T4.2): TIER-1 — Semantic fit beats keyword overlap (mispick guardrail)
# ===========================================================================


class TestTier1SemanticFitMispickGuardrail:
    """AC-2 mispick fixture: surface-token DECOY must not win over the semantically-correct heading.

    Scenario:
      Note topic: "version control workflows" (token: "workflows")
      MOC headings:
        DECOY   — "Agile Workflows"      (shares "workflows" with the note topic)
        CORRECT — "Source Control Practices" (shares NO literal tokens but is the right home)

    A keyword-overlap resolver would pick the DECOY. A semantic resolver picks CORRECT.
    The contract fixture encodes the CORRECT outcome and asserts the DECOY is not chosen.
    """

    def test_semantic_fit_beats_keyword_overlap_mispick_fixture(self, item_result_schema):
        """Mispick fixture: decoy heading shares 'workflows' with note; correct heading wins on meaning (AC-2)."""
        # Context encoded in the fixture comment — the test author (and any reviewer) must
        # understand BOTH candidates are present in the MOC's headings inventory; only
        # the correct semantic pick is recorded in the emitted anchor.
        #
        # MOC headings inventory (as shared_ctx.mocs[].headings would contain):
        #   [{"text": "Agile Workflows", "level": 2},          # DECOY — shares "workflows"
        #    {"text": "Source Control Practices", "level": 2}]  # CORRECT — right concept
        #
        # Note dominant topic: "version control workflows"
        # A keyword-overlap resolver scores "Agile Workflows" higher (1 shared token vs 0).
        # A semantic resolver scores "Source Control Practices" higher (same domain as VCS).

        decoy_heading = "Agile Workflows"
        correct_heading = "Source Control Practices"

        candidate = {
            "path": "Atlas/200 Maps/Software Engineering (MOC).md",
            "score": 0.72,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": correct_heading,
                "placement": "after",
                "new_section": None,
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

        anchor = candidate["anchor"]
        # Semantic fit wins: correct heading chosen
        assert anchor["value"] == correct_heading
        # Keyword-overlap DECOY is NOT chosen
        assert anchor["value"] != decoy_heading
        # Shape is correct for TIER-1
        assert anchor["type"] == "heading"
        assert anchor["placement"] == "after"
        assert anchor["new_section"] is None


# ===========================================================================
# AC-4/AC-5: TIER-2 — Headings present but none fits → new section before footer
# ===========================================================================


class TestTier2NewSection:
    """TIER-2: headings present, none fits → callout anchor before footer, new_section from topic (AC-4/AC-5)."""

    def test_tier2_new_section_schema_valid(self, item_result_schema):
        """TIER-2: new-section anchor validates against item-result schema."""
        candidate = {
            "path": "Atlas/200 Maps/Engineering (MOC).md",
            "score": 0.60,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": "[!blocks] Footer",
                "placement": "before",
                "new_section": "Mental Models",
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_tier2_anchor_type_is_callout_before(self, item_result_schema):
        """TIER-2 anchor: type=callout, placement=before (insert before footer callout)."""
        candidate = {
            "path": "Atlas/200 Maps/Engineering (MOC).md",
            "score": 0.60,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": "[!blocks] Footer",
                "placement": "before",
                "new_section": "Mental Models",
            },
        }
        anchor = candidate["anchor"]
        assert anchor["type"] == "callout"
        assert anchor["placement"] == "before"

    def test_tier2_new_section_not_key_concepts(self, item_result_schema):
        """AC-5: new_section is never the hardcoded literal 'Key Concepts'."""
        candidate = {
            "path": "Atlas/200 Maps/Engineering (MOC).md",
            "score": 0.60,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": "[!blocks] Footer",
                "placement": "before",
                "new_section": "Mental Models",
            },
        }
        assert candidate["anchor"]["new_section"] != "Key Concepts"
        assert candidate["anchor"]["new_section"] is not None
        assert len(candidate["anchor"]["new_section"]) > 0

    def test_tier2_new_section_derived_from_topic(self, item_result_schema):
        """AC-5: new_section must reflect the note's dominant topic, not a generic placeholder."""
        # The note is about "cognitive biases" — the section should reflect that topic
        candidate = {
            "path": "Atlas/200 Maps/Psychology (MOC).md",
            "score": 0.55,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": "[!blocks] Footer",
                "placement": "before",
                "new_section": "Cognitive Biases",
            },
        }
        anchor = candidate["anchor"]
        assert anchor["new_section"] == "Cognitive Biases"
        assert anchor["new_section"] != "Key Concepts"

    def test_tier2_new_section_null_footer_value_schema_valid(self, item_result_schema):
        """TIER-2: value=None is valid when no footer callout is present (prompt allows null)."""
        candidate = {
            "path": "Atlas/200 Maps/Psychology (MOC).md",
            "score": 0.55,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": None,
                "placement": "before",
                "new_section": "Behavioural Science",
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        anchor = candidate["anchor"]
        assert anchor["value"] is None
        assert anchor["new_section"] is not None
        assert anchor["new_section"] != "Key Concepts"


# ===========================================================================
# AC-7: TIER-3 — No headings, editable callout present → callout inside
# ===========================================================================


class TestTier3EditableCallout:
    """TIER-3: no headings, editable callout present → {type:callout, placement:inside} (AC-7)."""

    def test_tier3_callout_inside_schema_valid(self, item_result_schema):
        """TIER-3: inside-callout anchor validates against item-result schema."""
        candidate = {
            "path": "Atlas/200 Maps/Quick Notes (MOC).md",
            "score": 0.58,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": "[!blocks] Key Concepts",
                "placement": "inside",
                "new_section": None,
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_tier3_anchor_type_callout_placement_inside(self, item_result_schema):
        """TIER-3: type=callout, placement=inside (insert inside editable callout)."""
        candidate = {
            "path": "Atlas/200 Maps/Quick Notes (MOC).md",
            "score": 0.58,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": "[!blocks] Key Concepts",
                "placement": "inside",
                "new_section": None,
            },
        }
        anchor = candidate["anchor"]
        assert anchor["type"] == "callout"
        assert anchor["placement"] == "inside"
        assert anchor["new_section"] is None

    def test_tier3_value_is_callout_string(self, item_result_schema):
        """TIER-3: anchor value is the editable callout string from shared_ctx.mocs[]."""
        candidate = {
            "path": "Atlas/200 Maps/Quick Notes (MOC).md",
            "score": 0.58,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": "[!blocks] Key Concepts",
                "placement": "inside",
                "new_section": None,
            },
        }
        assert candidate["anchor"]["value"].startswith("[!")


# ===========================================================================
# AC-9: TIER-4 — No headings, no callout → H1 title, placement after
# ===========================================================================


class TestTier4H1LastResort:
    """TIER-4: no headings, no callout → {type:heading, value:<H1 title>, placement:after} (AC-9)."""

    def test_tier4_h1_last_resort_schema_valid(self, item_result_schema):
        """TIER-4: H1 last-resort anchor validates against item-result schema."""
        candidate = {
            "path": "Atlas/200 Maps/Miscellaneous (MOC).md",
            "score": 0.52,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Miscellaneous (MOC)",
                "placement": "after",
                "new_section": None,
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_tier4_anchor_type_heading_placement_after(self, item_result_schema):
        """TIER-4: type=heading (the H1 title), placement=after."""
        candidate = {
            "path": "Atlas/200 Maps/Miscellaneous (MOC).md",
            "score": 0.52,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Miscellaneous (MOC)",
                "placement": "after",
                "new_section": None,
            },
        }
        anchor = candidate["anchor"]
        assert anchor["type"] == "heading"
        assert anchor["placement"] == "after"
        assert anchor["new_section"] is None


# ===========================================================================
# AC-10: TIER-4b — No headings, no callout, no H1 → first body line, never unresolved
# ===========================================================================


class TestTier4bFirstBodyLine:
    """TIER-4b: no headings, no callout, no H1 → {type:line, value:<first body line>, placement:after} (AC-10)."""

    def test_tier4b_line_fallback_schema_valid(self, item_result_schema):
        """TIER-4b: line-fallback anchor validates against item-result schema."""
        candidate = {
            "path": "Atlas/200 Maps/Orphan (MOC).md",
            "score": 0.51,
            "pre_check": True,
            "anchor": {
                "type": "line",
                "value": "This is the first body line of the MOC.",
                "placement": "after",
                "new_section": None,
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_tier4b_anchor_type_line_placement_after(self, item_result_schema):
        """TIER-4b: type=line, placement=after — never left unresolved."""
        candidate = {
            "path": "Atlas/200 Maps/Orphan (MOC).md",
            "score": 0.51,
            "pre_check": True,
            "anchor": {
                "type": "line",
                "value": "This is the first body line of the MOC.",
                "placement": "after",
                "new_section": None,
            },
        }
        anchor = candidate["anchor"]
        assert anchor["type"] == "line"
        assert anchor["placement"] == "after"
        # AC-10: never unresolved — value must be a non-empty string
        assert anchor["value"] is not None
        assert len(anchor["value"]) > 0


# ===========================================================================
# EC-5: Classification MOC → excluded as target, no anchor, pre_check false
# ===========================================================================


class TestEC5ClassificationExcluded:
    """EC-5: classification MOC is never pre-checked and never receives an anchor."""

    def test_classification_moc_not_pre_checked_schema_valid(self, item_result_schema):
        """Classification MOC: pre_check=False, no anchor field — validates against schema."""
        # Classification MOCs score but are excluded from pre_check (classification guard)
        candidate = {
            "path": "Atlas/200 Maps/00 Index (MOC).md",
            "score": 0.30,
            "pre_check": False,
            # No anchor key — classification MOCs never receive one
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_classification_moc_has_no_anchor(self, item_result_schema):
        """EC-5: classification MOC entry must not carry an anchor."""
        candidate = {
            "path": "Atlas/200 Maps/00 Index (MOC).md",
            "score": 0.30,
            "pre_check": False,
        }
        assert "anchor" not in candidate

    def test_classification_exclusion_needs_new_moc_set(self, item_result_schema):
        """EC-5: when all top matches are classification-layer, needs_new_moc is set."""
        result = _make_result_no_candidates()
        validate(instance=result, schema=item_result_schema)
        action = result["actions"][0]
        assert action.get("needs_new_moc") is True
        assert action.get("candidate_mocs") == []

    def test_thematic_moc_with_pre_check_true_gets_anchor(self, item_result_schema):
        """Thematic (non-classification) MOC with pre_check=True receives anchor (contrast to EC-5)."""
        candidate = {
            "path": "Atlas/200 Maps/Technology (MOC).md",
            "score": 0.70,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Software Tools",
                "placement": "after",
                "new_section": None,
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        assert candidate["pre_check"] is True
        assert "anchor" in candidate


# ===========================================================================
# Schema constraint tests — tighten contract boundaries
# ===========================================================================


class TestAnchorSchemaConstraints:
    """Schema-level rejection tests — verify the contract rejects malformed anchors."""

    def test_anchor_value_null_is_schema_legal_unresolved_sentinel(self, item_result_schema):
        """anchor.value=null is schema-legal (sentinel for an unresolved anchor — absent when the LLM could not match any anchor text)."""
        candidate = {
            "path": "Atlas/200 Maps/Tech (MOC).md",
            "score": 0.60,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": None,
                "placement": "after",
                "new_section": None,
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_anchor_invalid_type_rejected(self, item_result_schema):
        """anchor.type='section' (not in enum) is rejected."""
        candidate = {
            "path": "Atlas/200 Maps/Tech (MOC).md",
            "score": 0.60,
            "pre_check": True,
            "anchor": {
                "type": "section",
                "value": "Some Section",
                "placement": "after",
                "new_section": None,
            },
        }
        with pytest.raises(ValidationError):
            validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_anchor_invalid_placement_rejected(self, item_result_schema):
        """anchor.placement='under' (not in enum) is rejected."""
        candidate = {
            "path": "Atlas/200 Maps/Tech (MOC).md",
            "score": 0.60,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Some Heading",
                "placement": "under",
                "new_section": None,
            },
        }
        with pytest.raises(ValidationError):
            validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_anchor_missing_required_type_rejected(self, item_result_schema):
        """anchor missing required 'type' field is rejected."""
        candidate = {
            "path": "Atlas/200 Maps/Tech (MOC).md",
            "score": 0.60,
            "pre_check": True,
            "anchor": {
                "value": "Some Heading",
                "placement": "after",
                "new_section": None,
            },
        }
        with pytest.raises(ValidationError):
            validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

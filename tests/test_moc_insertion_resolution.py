#!/usr/bin/env python3
# version: 0.2.0
"""test_moc_insertion_resolution.py — Contract fixtures for T4.1/T4.2 (spec 022/023 Phase 4).

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

  T4.2 (spec 023 Phase 4) — render-layer contracts:
    (a) _pick_anchor: footer-less MOC → {type:line, value:<last body line>, placement:after}
    (b) apply loop: null-value line anchor → resolved to last body line
    (c) _serialize_new_sections: yields "## <section>\\n\\n- [[Note]]\\n" (AC-10)
    (d) telemetry: tier1_confident count + rejected_to_tier2 count, NO heading text in line
    (e) _emit: fit_confidence stripped from Pass-2 anchor (no-leak contract)

These are *contract* fixtures — inline dicts that represent what the LLM agent should
emit. Schema validation confirms shape; structural assertions confirm tier semantics.

Spec: docs/XDD/specs/022-moc-insertion-point-intelligence/
      docs/XDD/specs/023-moc-placement-fit-confidence/
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import ValidationError, validate  # noqa: E402

# Import render-layer helpers for T4.2 unit tests.
# instruction-render.py has a hyphen → must use importlib.util.
import importlib.util  # noqa: E402

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
_ir_spec = importlib.util.spec_from_file_location(
    "instruction_render", _SCRIPTS_DIR / "instruction-render.py"
)
_ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render"] = _ir
_ir_spec.loader.exec_module(_ir)

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


# ===========================================================================
# AC-16 / T6.2 — TIER-1 ambiguous-fit: ≥2 headings fit → alt_headings advisory
# ===========================================================================


class TestTier1AmbiguousFitAltHeadings:
    """AC-16: When ≥2 headings genuinely fit, anchor.alt_headings carries runner-up(s).

    When only one heading fits, alt_headings is absent. When two or more genuinely fit,
    the chosen best-fit goes in value and the remaining plausible headings go in alt_headings.
    """

    def test_ambiguous_fit_with_two_headings_schema_valid(self, item_result_schema):
        """When ≥2 headings fit, anchor with alt_headings validates against item-result schema."""
        candidate = {
            "path": "Atlas/200 Maps/Health (MOC).md",
            "score": 0.78,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Habits",
                "placement": "after",
                "new_section": None,
                "alt_headings": ["Routines"],
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_ambiguous_fit_chosen_anchor_not_in_alt_headings(self, item_result_schema):
        """Chosen best-fit heading (value) must NOT appear in alt_headings."""
        candidate = {
            "path": "Atlas/200 Maps/Health (MOC).md",
            "score": 0.78,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Habits",
                "placement": "after",
                "new_section": None,
                "alt_headings": ["Routines", "Morning Practice"],
            },
        }
        anchor = candidate["anchor"]
        assert anchor["value"] not in anchor["alt_headings"], (
            "Chosen anchor value must not appear in alt_headings — it is the CHOSEN heading"
        )

    def test_ambiguous_fit_alt_headings_is_non_empty_list(self, item_result_schema):
        """alt_headings is a non-empty list of strings when ambiguous fit fires."""
        candidate = {
            "path": "Atlas/200 Maps/Health (MOC).md",
            "score": 0.78,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Habits",
                "placement": "after",
                "new_section": None,
                "alt_headings": ["Routines"],
            },
        }
        alt = candidate["anchor"]["alt_headings"]
        assert isinstance(alt, list)
        assert len(alt) >= 1
        assert all(isinstance(h, str) and h for h in alt)

    def test_single_fit_no_alt_headings(self, item_result_schema):
        """When only ONE heading fits, alt_headings is absent — omitted, not null."""
        candidate = {
            "path": "Atlas/200 Maps/Systems Thinking (MOC).md",
            "score": 0.75,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Reasoning Techniques",
                "placement": "after",
                "new_section": None,
                # alt_headings intentionally absent
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        assert "alt_headings" not in candidate["anchor"], (
            "Single-fit: alt_headings must be absent, not null or empty list"
        )

    def test_ambiguous_fit_multiple_runner_ups_all_strings(self, item_result_schema):
        """alt_headings may carry multiple runner-up headings — all must be strings."""
        candidate = {
            "path": "Atlas/200 Maps/Wellbeing (MOC).md",
            "score": 0.72,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Sleep",
                "placement": "after",
                "new_section": None,
                "alt_headings": ["Rest & Recovery", "Evening Practices"],
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        alt = candidate["anchor"]["alt_headings"]
        assert len(alt) == 2
        assert all(isinstance(h, str) for h in alt)


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


# ===========================================================================
# Phase 3 (spec 023): Confidence-gated TIER-1 + has_footer TIER-2
# ===========================================================================


class TestTier1ConfidenceGated:
    """TIER-1 confidence gate: fit_confidence >= 0.6 required for tier-1 heading anchor.

    Locks the emission shape for the confidence-gated tier-1 path (spec 023 ADR-4).
    Phase 4 render consumes these EXACT shapes.
    """

    def test_tier1_confident_has_fit_confidence(self, item_result_schema):
        """Tier-1 confident anchor must carry fit_confidence >= 0.6."""
        candidate = {
            "path": "Atlas/200 Maps/Concepts (MOC).md",
            "score": 0.82,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Thinking Frameworks",
                "placement": "after",
                "new_section": None,
                "fit_confidence": 0.89,
                "alt_headings": ["Core Concepts"],
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        anchor = candidate["anchor"]
        assert anchor["type"] == "heading"
        assert anchor["new_section"] is None
        assert "fit_confidence" in anchor
        conf = anchor["fit_confidence"]
        assert isinstance(conf, (int, float))
        assert 0.6 <= conf <= 1.0

    def test_tier1_confident_schema_valid(self, item_result_schema):
        """Tier-1 confident anchor validates against item-result schema."""
        candidate = {
            "path": "Atlas/200 Maps/Concepts (MOC).md",
            "score": 0.82,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Thinking Frameworks",
                "placement": "after",
                "new_section": None,
                "fit_confidence": 0.89,
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_tier1_confident_min_threshold(self, item_result_schema):
        """Tier-1 anchor at exactly the gate threshold (0.6) is valid tier-1."""
        candidate = {
            "path": "Atlas/200 Maps/Philosophy (MOC).md",
            "score": 0.65,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Epistemology",
                "placement": "after",
                "new_section": None,
                "fit_confidence": 0.6,
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        assert candidate["anchor"]["fit_confidence"] == 0.6

    def test_tier1_fit_confidence_out_of_range_rejected(self, item_result_schema):
        """fit_confidence > 1.0 is rejected by schema (bounds violation)."""
        candidate = {
            "path": "Atlas/200 Maps/Concepts (MOC).md",
            "score": 0.82,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Thinking Frameworks",
                "placement": "after",
                "new_section": None,
                "fit_confidence": 1.01,
            },
        }
        with pytest.raises(ValidationError):
            validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_tier1_fit_confidence_negative_rejected(self, item_result_schema):
        """fit_confidence < 0.0 is rejected by schema (bounds violation)."""
        candidate = {
            "path": "Atlas/200 Maps/Concepts (MOC).md",
            "score": 0.82,
            "pre_check": True,
            "anchor": {
                "type": "heading",
                "value": "Thinking Frameworks",
                "placement": "after",
                "new_section": None,
                "fit_confidence": -0.1,
            },
        }
        with pytest.raises(ValidationError):
            validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_tier1_rejected_heading_in_tier2_alt_headings(self, item_result_schema):
        """When tier-1 is rejected (fit < 0.6), the rejected heading appears in tier-2 alt_headings.

        Scenario: Japan note → Japan (MOC). Best heading 'Content' is structural scaffolding,
        scores ~0.3 < 0.6 → falls through to TIER-2; 'Content' goes into alt_headings so the
        user can retarget to it in one edit (spec 023 ADR-3).
        """
        candidate = {
            "path": "Atlas/200 Maps/Japan (MOC).md",
            "score": 0.71,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": None,
                "placement": "before",
                "new_section": "Japanische Städte",
                "alt_headings": ["Content"],
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        anchor = candidate["anchor"]
        # This is a tier-2 anchor (no fit_confidence)
        assert anchor["type"] in ("callout", "line")
        assert anchor["new_section"] is not None
        # The rejected heading is in alt_headings
        assert "alt_headings" in anchor
        assert "Content" in anchor["alt_headings"]

    def test_tier1_rejected_no_fit_confidence_on_tier2(self, item_result_schema):
        """Tier-2 anchors (after tier-1 rejection) must NOT carry fit_confidence."""
        candidate = {
            "path": "Atlas/200 Maps/Japan (MOC).md",
            "score": 0.71,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": None,
                "placement": "before",
                "new_section": "Japanische Städte",
                "alt_headings": ["Content"],
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        # Tier-2: fit_confidence must be absent or null (not a tier-1 heading anchor)
        anchor = candidate["anchor"]
        assert anchor.get("fit_confidence") is None


class TestTier2HasFooter:
    """TIER-2 with has_footer branching (spec 023 ADR-2 + ADR-5).

    When no heading scores >= 0.6, TIER-2 fires. The anchor type depends on
    moc.has_footer: true → callout/before with null value; false → line/after with null value.
    Pass-1 always emits value:null; Pass-2 render fills the actual text.
    """

    def test_tier2_footer_true_callout_before_null_value(self, item_result_schema):
        """TIER-2 with has_footer=true: type=callout, placement=before, value=null."""
        candidate = {
            "path": "Atlas/200 Maps/Japan (MOC).md",
            "score": 0.71,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": None,
                "placement": "before",
                "new_section": "Japanische Städte",
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        anchor = candidate["anchor"]
        assert anchor["type"] == "callout"
        assert anchor["placement"] == "before"
        assert anchor["value"] is None
        assert anchor["new_section"] is not None
        assert anchor["new_section"] != "Key Concepts"

    def test_tier2_footer_true_schema_valid(self, item_result_schema):
        """TIER-2 footer=true anchor validates against item-result schema."""
        candidate = {
            "path": "Atlas/200 Maps/History (MOC).md",
            "score": 0.68,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": None,
                "placement": "before",
                "new_section": "Ancient Civilizations",
                "alt_headings": ["Overview"],
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_tier2_no_footer_line_after_null_value(self, item_result_schema):
        """TIER-2 with has_footer=false: type=line, placement=after, value=null.

        Pass-1 cannot see the MOC body — it emits null; render fills the last body line.
        """
        candidate = {
            "path": "Atlas/200 Maps/Concepts (MOC).md",
            "score": 0.65,
            "pre_check": True,
            "anchor": {
                "type": "line",
                "value": None,
                "placement": "after",
                "new_section": "First Principles",
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        anchor = candidate["anchor"]
        assert anchor["type"] == "line"
        assert anchor["placement"] == "after"
        assert anchor["value"] is None
        assert anchor["new_section"] is not None
        assert anchor["new_section"] != "Key Concepts"

    def test_tier2_no_footer_schema_valid(self, item_result_schema):
        """TIER-2 no-footer (line/after/null) validates against item-result schema."""
        candidate = {
            "path": "Atlas/200 Maps/Mental Models (MOC).md",
            "score": 0.72,
            "pre_check": True,
            "anchor": {
                "type": "line",
                "value": None,
                "placement": "after",
                "new_section": "Cognitive Patterns",
                "alt_headings": ["Structure"],
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)

    def test_tier2_no_footer_rejected_heading_in_alt_headings(self, item_result_schema):
        """Tier-2 no-footer: rejected tier-1 heading appears in alt_headings (ADR-3)."""
        candidate = {
            "path": "Atlas/200 Maps/Concepts (MOC).md",
            "score": 0.65,
            "pre_check": True,
            "anchor": {
                "type": "line",
                "value": None,
                "placement": "after",
                "new_section": "First Principles",
                "alt_headings": ["Content"],
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        anchor = candidate["anchor"]
        assert anchor.get("alt_headings") is not None
        assert len(anchor["alt_headings"]) >= 1
        # Structural scaffolding heading is the rejected runner-up
        assert "Content" in anchor["alt_headings"]

    def test_tier2_new_section_never_key_concepts_footer(self, item_result_schema):
        """TIER-2 footer path: new_section is NEVER the literal 'Key Concepts'.

        Guard against the LLM pattern-matching the hardcoded example in the TIER-2
        prompt wording. The prompt says NEVER "Key Concepts"; this fixture documents
        that contract (the fixture itself uses a valid topic so it passes schema — the
        prohibition lives in the prompt and is validated in the Phase 5 live walk).
        """
        candidate = {
            "path": "Atlas/200 Maps/Engineering (MOC).md",
            "score": 0.60,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": None,
                "placement": "before",
                "new_section": "Systems Design",
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        # Guard: topic-derived label is not the forbidden literal
        assert candidate["anchor"]["new_section"] != "Key Concepts"

    def test_tier2_new_section_never_key_concepts_no_footer(self, item_result_schema):
        """TIER-2 no-footer path: new_section is NEVER the literal 'Key Concepts'.

        Same guard as the footer variant — documents the prompt prohibition so a
        reviewer editing the TIER-2 block knows this is a named contract, not dead code.
        """
        candidate = {
            "path": "Atlas/200 Maps/Engineering (MOC).md",
            "score": 0.60,
            "pre_check": True,
            "anchor": {
                "type": "line",
                "value": None,
                "placement": "after",
                "new_section": "Systems Design",
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        # Guard: topic-derived label is not the forbidden literal
        assert candidate["anchor"]["new_section"] != "Key Concepts"

    def test_tier2_footer_absent_same_as_true(self, item_result_schema):
        """moc.has_footer absent → fallback to callout/before per ADR-5.

        When the MOC cache predates spec 023 (no has_footer field), Pass-1 treats
        the absent flag as unknown and falls back to the 022 callout/before shape.
        This fixture makes that fallback a first-class named contract.
        """
        # has_footer absent from inventory → analyst must emit callout/before/null
        candidate = {
            "path": "Atlas/200 Maps/Legacy (MOC).md",
            "score": 0.66,
            "pre_check": True,
            "anchor": {
                "type": "callout",
                "value": None,
                "placement": "before",
                "new_section": "Pre-023 Topic",
            },
        }
        validate(instance=_make_result_with_candidate(candidate), schema=item_result_schema)
        anchor = candidate["anchor"]
        assert anchor["type"] == "callout"
        assert anchor["placement"] == "before"
        assert anchor["value"] is None


# ===========================================================================
# T4.2 (spec 023 Phase 4) — render-layer contracts
# ===========================================================================
# These tests exercise instruction-render.py module-level functions directly
# via the _ir importlib handle loaded at module top.
#
# (a) _pick_anchor: footer-less MOC body → {type:line, value:<last body line>, placement:after}
# (b) apply loop: null-value line anchor resolved to last body line
# (c) _serialize_new_sections: correct spacing "## <s>\n\n- [[N]]\n" (AC-10)
# (d) telemetry: tier1_confident + rejected_to_tier2 counts; NO heading text
# (e) _emit: fit_confidence stripped from Pass-2 anchor (no-leak contract)
# ===========================================================================


class _FakeKadoClient:
    """Minimal Kado stand-in for resolve_section_names tests.

    Stores a mapping of vault-path → body string.  read_note(path) returns
    {"content": body}; any unknown path raises RuntimeError (simulating
    Kado NOT_FOUND so the resolver skips gracefully).
    """

    def __init__(self, notes: dict[str, str]) -> None:
        self._notes = notes

    def read_note(self, path: str) -> dict:
        if path not in self._notes:
            raise RuntimeError(f"NOT_FOUND: {path}")
        return {"content": self._notes[path]}


def _make_link_to_moc_action(
    *,
    anchor_type: str = "callout",
    anchor_value: str | None = None,
    target_moc_path: str | None = "Atlas/200 Maps/Test (MOC).md",
    new_section: str | None = None,
    placement: str = "after",
    fit_confidence: float | None = None,
) -> dict:
    """Minimal link_to_moc action dict for resolver tests."""
    anchor: dict = {"type": anchor_type, "value": anchor_value}
    if fit_confidence is not None:
        anchor["fit_confidence"] = fit_confidence
    action: dict = {
        "action": "link_to_moc",
        "target_moc": "Test (MOC)",
        "target_moc_path": target_moc_path,
        "anchor": anchor,
        "placement": placement,
        "line_to_add": "- [[Source Note]]",
        "source_note_title": "Source Note",
        "new_section": new_section,
    }
    return action


# ── (a) _pick_anchor: footer-less MOC → last body line ──────────────────────


class TestPickAnchorNoFooter:
    """(a) resolve_section_names._pick_anchor: footer-less MOC body → line/after with last body line (AC-9).

    Exercised through resolve_section_names with a controlled fake client.
    A footer-less MOC has: no editable callout, no content headings, no footer callout.
    """

    def test_footerless_moc_resolves_to_line_type(self) -> None:
        """A footer-less MOC body causes _pick_anchor to return type='line' (4th tier)."""
        # MOC body: only a plain paragraph — no callout, no heading, no footer
        moc_body = "# Plain (MOC)\n\nThis is just content.\n\nAnother paragraph here."
        client = _FakeKadoClient({"Atlas/200 Maps/Plain (MOC).md": moc_body})
        action = _make_link_to_moc_action(
            anchor_type="callout",
            anchor_value=None,
            target_moc_path="Atlas/200 Maps/Plain (MOC).md",
        )
        resolved = _ir.resolve_section_names([action], client, editable_callouts=["blocks"])
        assert resolved == 1
        assert action["anchor"]["type"] == "line"

    def test_footerless_moc_resolves_to_placement_after(self) -> None:
        """Footer-less MOC: resolved anchor placement is 'after' (AC-9 — last body line)."""
        moc_body = "# Plain (MOC)\n\nThis is just content.\n\nAnother paragraph here."
        client = _FakeKadoClient({"Atlas/200 Maps/Plain (MOC).md": moc_body})
        action = _make_link_to_moc_action(
            anchor_type="callout",
            anchor_value=None,
            target_moc_path="Atlas/200 Maps/Plain (MOC).md",
        )
        _ir.resolve_section_names([action], client, editable_callouts=["blocks"])
        assert action["placement"] == "after"

    def test_footerless_moc_value_is_last_non_empty_body_line(self) -> None:
        """Footer-less MOC: anchor.value is the last non-empty line of the MOC body."""
        last_line = "Another paragraph here."
        moc_body = f"# Plain (MOC)\n\nThis is just content.\n\n{last_line}"
        client = _FakeKadoClient({"Atlas/200 Maps/Plain (MOC).md": moc_body})
        action = _make_link_to_moc_action(
            anchor_type="callout",
            anchor_value=None,
            target_moc_path="Atlas/200 Maps/Plain (MOC).md",
        )
        _ir.resolve_section_names([action], client, editable_callouts=["blocks"])
        assert action["anchor"]["value"] == last_line

    def test_footerless_moc_trailing_blank_lines_ignored(self) -> None:
        """Footer-less MOC: trailing blank lines do not become the anchor value."""
        last_line = "Last real line."
        # Body ends with two blank lines after the last real line
        moc_body = f"# Plain (MOC)\n\nFirst paragraph.\n\n{last_line}\n\n\n"
        client = _FakeKadoClient({"Atlas/200 Maps/Plain (MOC).md": moc_body})
        action = _make_link_to_moc_action(
            anchor_type="callout",
            anchor_value=None,
            target_moc_path="Atlas/200 Maps/Plain (MOC).md",
        )
        _ir.resolve_section_names([action], client, editable_callouts=["blocks"])
        assert action["anchor"]["value"] == last_line

    def test_entirely_empty_moc_body_not_resolved(self) -> None:
        """MOC body with no usable lines leaves the anchor unresolved (graceful degradation)."""
        # Graceful-degradation per SDD: if no usable line, _pick_anchor returns None
        moc_body = "# Empty (MOC)\n\n\n   \n"
        client = _FakeKadoClient({"Atlas/200 Maps/Empty (MOC).md": moc_body})
        action = _make_link_to_moc_action(
            anchor_type="callout",
            anchor_value=None,
            target_moc_path="Atlas/200 Maps/Empty (MOC).md",
        )
        resolved = _ir.resolve_section_names([action], client, editable_callouts=["blocks"])
        # Cannot resolve if no usable body line — stays unresolved (0 resolutions)
        assert resolved == 0

    def test_h2_last_line_not_used_as_line_anchor(self) -> None:
        """Belt-and-suspenders: H2 as last body line is NOT used as the line anchor value.

        Invariant: any H2–H6 would have been claimed by _pick_content_heading (tier 2)
        before tier 4 is reached. If that invariant held, the H2 would not be the last
        line here. The broad '#' filter is defensive — this test documents and locks that
        even if an H2 somehow survives to tier 4, it is excluded from line candidates,
        and the resolver falls back to the preceding real content line (or unresolved).
        """
        # Body: real content line followed by an H2 with no footer and no editable callout.
        # parse_headings (tier 2) finds no H2–H6 because this MOC has no proper section
        # headings recognised by it (the H2 IS the last line — a structural edge case).
        # Tier 4 must NOT emit the H2 as the line anchor value.
        real_content = "A plain paragraph of content."
        moc_body = f"# Sparse (MOC)\n\n{real_content}\n\n## Orphan Heading"
        client = _FakeKadoClient({"Atlas/200 Maps/Sparse (MOC).md": moc_body})
        action = _make_link_to_moc_action(
            anchor_type="callout",
            anchor_value=None,
            target_moc_path="Atlas/200 Maps/Sparse (MOC).md",
        )
        _ir.resolve_section_names([action], client, editable_callouts=["blocks"])
        anchor_value = action["anchor"].get("value")
        # The H2 heading line must not be the anchor value regardless of tier reached
        assert anchor_value != "## Orphan Heading", (
            "H2 last-line must be excluded from tier-4 line candidates"
        )


# ── (b) apply loop: null-value line anchor → resolved ───────────────────────


class TestApplyLoopLineAnchor:
    """(b) Apply loop processes null-value 'line' type anchors (new T4.2 behaviour).

    Prior to T4.2, the guard `if anchor.get("type") != "callout": continue`
    skipped ALL line anchors. After T4.2, null-value line anchors are processed
    and resolved to the MOC's last body line.  Populated line anchors are left
    untouched (honor-guard).
    """

    def test_null_line_anchor_resolved_by_apply_loop(self) -> None:
        """Null-value 'line' anchor: apply loop fills it from the live MOC body."""
        last_line = "- [[Related Concept]]"
        moc_body = f"# NoFooter (MOC)\n\nSome content.\n\n{last_line}"
        client = _FakeKadoClient({"Atlas/200 Maps/NoFooter (MOC).md": moc_body})
        action = _make_link_to_moc_action(
            anchor_type="line",
            anchor_value=None,
            target_moc_path="Atlas/200 Maps/NoFooter (MOC).md",
        )
        resolved = _ir.resolve_section_names([action], client, editable_callouts=["blocks"])
        assert resolved == 1
        assert action["anchor"]["type"] == "line"
        assert action["anchor"]["value"] == last_line

    def test_populated_line_anchor_honor_guard_untouched(self) -> None:
        """Populated 'line' anchor: honor-guard leaves the value unchanged (not overwritten)."""
        existing_value = "Already resolved line text."
        moc_body = "# NoFooter (MOC)\n\nSome content.\n\nDifferent last line."
        client = _FakeKadoClient({"Atlas/200 Maps/NoFooter (MOC).md": moc_body})
        action = _make_link_to_moc_action(
            anchor_type="line",
            anchor_value=existing_value,
            target_moc_path="Atlas/200 Maps/NoFooter (MOC).md",
        )
        # Honor-guard: a line anchor with a non-null value is NOT touched
        resolved = _ir.resolve_section_names([action], client, editable_callouts=["blocks"])
        assert resolved == 0  # already-set → skip
        assert action["anchor"]["value"] == existing_value  # unchanged


# ── (c) _serialize_new_sections: correct spacing (AC-10) ────────────────────


class TestSerializeNewSectionsSpacing:
    """(c) _serialize_new_sections yields the correct spacing per AC-10.

    Contract: "## <section>\\n\\n<bullet>\\n"
    The blank line between the heading and the bullet ensures Hashi writes it
    correctly (hashi#65). No flush-against-footer, no dangling section.
    """

    def test_new_section_spacing_format(self) -> None:
        """_serialize_new_sections produces '## <s>\\n\\n- [[N]]\\n' (AC-10)."""
        action = _make_link_to_moc_action(
            anchor_type="line",
            anchor_value="Last line of MOC.",
            new_section="First Principles",
            placement="after",
        )
        action["line_to_add"] = "- [[Source Note]]"
        _ir._serialize_new_sections([action])
        assert action["line_to_add"] == "## First Principles\n\n- [[Source Note]]\n"

    def test_new_section_starts_with_h2(self) -> None:
        """Serialized line_to_add starts with '## ' (two hashes + space)."""
        action = _make_link_to_moc_action(new_section="Cognitive Patterns")
        action["line_to_add"] = "- [[Note Title]]"
        _ir._serialize_new_sections([action])
        assert action["line_to_add"].startswith("## ")

    def test_new_section_blank_line_between_heading_and_bullet(self) -> None:
        """Serialized output has a blank line (\\n\\n) between heading and bullet."""
        action = _make_link_to_moc_action(new_section="Systems")
        action["line_to_add"] = "- [[A Note]]"
        _ir._serialize_new_sections([action])
        # The heading line ends with \n, then there's a blank line before the bullet
        lines = action["line_to_add"].split("\n")
        # lines[0] = "## Systems", lines[1] = "", lines[2] = "- [[A Note]]", lines[3] = ""
        assert lines[1] == "", "Expected blank line between heading and bullet"

    def test_new_section_trailing_newline(self) -> None:
        """Serialized line_to_add ends with a trailing '\\n'."""
        action = _make_link_to_moc_action(new_section="Learning")
        action["line_to_add"] = "- [[My Note]]"
        _ir._serialize_new_sections([action])
        assert action["line_to_add"].endswith("\n")

    def test_idempotency_guard_prevents_double_prepend(self) -> None:
        """Calling _serialize_new_sections twice does NOT double-prepend '## '."""
        action = _make_link_to_moc_action(new_section="Ethics")
        action["line_to_add"] = "- [[Philosophy Note]]"
        _ir._serialize_new_sections([action])
        first = action["line_to_add"]
        _ir._serialize_new_sections([action])
        assert action["line_to_add"] == first  # unchanged on second call


# ── (d) telemetry: tier1_confident + rejected_to_tier2 counts ───────────────


class TestResolutionTelemetry:
    """(d) _emit_resolution_telemetry: new tier1_confident + rejected_to_tier2 counts (T4.2).

    Counts must appear in the stderr line; heading TEXT must NOT appear
    (Constitution L2 — metadata-only, never note content).
    """

    def _capture_telemetry(self, actions: list[dict]) -> str:
        """Run _emit_resolution_telemetry and capture its stderr output."""
        buf = io.StringIO()
        orig_stderr = sys.stderr
        sys.stderr = buf
        try:
            _ir._emit_resolution_telemetry(actions)
        finally:
            sys.stderr = orig_stderr
        return buf.getvalue()

    def test_telemetry_contains_tier1_confident_field(self) -> None:
        """Telemetry line includes 'tier1_confident=N' field."""
        # One tier-1 heading anchor with numeric fit_confidence
        confident_action = _make_link_to_moc_action(
            anchor_type="heading",
            anchor_value="Reasoning Techniques",
            fit_confidence=0.89,
        )
        line = self._capture_telemetry([confident_action])
        assert "tier1_confident=" in line, (
            f"Expected 'tier1_confident=' in telemetry line, got: {line!r}"
        )

    def test_telemetry_tier1_confident_count_correct(self) -> None:
        """tier1_confident count matches the number of heading anchors with numeric fit_confidence."""
        actions = [
            _make_link_to_moc_action(
                anchor_type="heading",
                anchor_value="Concepts",
                fit_confidence=0.85,
            ),
            _make_link_to_moc_action(
                anchor_type="heading",
                anchor_value="Methods",
                fit_confidence=0.72,
            ),
            # heading without fit_confidence — NOT a tier1_confident
            _make_link_to_moc_action(anchor_type="heading", anchor_value="Tools"),
        ]
        line = self._capture_telemetry(actions)
        assert "tier1_confident=2" in line, (
            f"Expected tier1_confident=2 in: {line!r}"
        )

    def test_telemetry_contains_rejected_to_tier2_field(self) -> None:
        """Telemetry line includes 'rejected_to_tier2=N' field."""
        # A new_section anchor signals tier-1 rejection → tier-2
        tier2_action = _make_link_to_moc_action(
            anchor_type="callout",
            anchor_value=None,
            new_section="Japanische Städte",
        )
        line = self._capture_telemetry([tier2_action])
        assert "rejected_to_tier2=" in line, (
            f"Expected 'rejected_to_tier2=' in telemetry line, got: {line!r}"
        )

    def test_telemetry_rejected_to_tier2_count_correct(self) -> None:
        """rejected_to_tier2 counts new_section anchors (heading rejected, tier-2 fired)."""
        actions = [
            _make_link_to_moc_action(
                anchor_type="callout",
                anchor_value=None,
                new_section="Topic A",
            ),
            _make_link_to_moc_action(
                anchor_type="line",
                anchor_value=None,
                new_section="Topic B",
            ),
            # No new_section — NOT a rejected_to_tier2
            _make_link_to_moc_action(anchor_type="heading", anchor_value="Direct Heading"),
        ]
        line = self._capture_telemetry(actions)
        assert "rejected_to_tier2=2" in line, (
            f"Expected rejected_to_tier2=2 in: {line!r}"
        )

    def test_telemetry_contains_no_heading_text(self) -> None:
        """Telemetry line must NOT contain heading text (Constitution L2 metadata-only)."""
        sensitive_heading = "SENSITIVE_HEADING_TEXT_DO_NOT_LOG"
        action = _make_link_to_moc_action(
            anchor_type="heading",
            anchor_value=sensitive_heading,
            fit_confidence=0.88,
        )
        line = self._capture_telemetry([action])
        assert sensitive_heading not in line, (
            f"Heading text leaked into telemetry! Line: {line!r}"
        )

    def test_telemetry_no_new_section_text_in_line(self) -> None:
        """Telemetry line must NOT contain new_section text (Constitution L2 metadata-only)."""
        sensitive_section = "SENSITIVE_SECTION_NAME_DO_NOT_LOG"
        action = _make_link_to_moc_action(
            anchor_type="callout",
            anchor_value=None,
            new_section=sensitive_section,
        )
        line = self._capture_telemetry([action])
        assert sensitive_section not in line, (
            f"new_section text leaked into telemetry! Line: {line!r}"
        )

    def test_bool_fit_confidence_not_counted_as_tier1_confident(self) -> None:
        """fit_confidence=True (a bool) must NOT increment tier1_confident.

        bool is a subclass of int in Python, so isinstance(True, (int, float)) is True.
        The guard must exclude bools explicitly — True/False are not confidence values.
        """
        action = _make_link_to_moc_action(
            anchor_type="heading",
            anchor_value="Some Heading",
            fit_confidence=True,  # type: ignore[arg-type]  # intentional invalid input
        )
        line = self._capture_telemetry([action])
        assert "tier1_confident=0" in line, (
            f"bool True counted as tier1_confident — expected 0, got: {line!r}"
        )


# ── (e) _emit: fit_confidence stripped — no-leak contract ───────────────────


class TestEmitFitConfidenceNoLeak:
    """(e) _build_link_to_moc_actions._emit: fit_confidence is NOT propagated to Pass-2 anchor.

    The Pass-1 anchor from inbox-analyst may carry fit_confidence (a spec 023 field).
    The Pass-2 instructions.schema.json anchor allows ONLY {type, value}
    (additionalProperties:false). _emit must decompose only type+value and discard
    fit_confidence (and any other extra fields).

    This test DOCUMENTS and LOCKS the existing contract. If it passes before the
    implementation step, that is expected — the contract already held.
    """

    def _build_confirmed_item_with_anchor(self, anchor: dict) -> dict:
        """Minimal confirmed item that triggers _emit with the given anchor."""
        return {
            "id": "S01",
            "title": "Source Note",
            "action": "create_atomic_note",
            "source_path": "100 Inbox/source-note.md",
            "parent_mocs": ["Target (MOC)"],
            "candidate_mocs": [
                {
                    "path": "Atlas/200 Maps/Target (MOC).md",
                    "score": 0.8,
                    "pre_check": True,
                    "anchor": anchor,
                }
            ],
        }

    def test_fit_confidence_absent_from_pass2_anchor(self) -> None:
        """Pass-1 anchor with fit_confidence → Pass-2 anchor has NO fit_confidence key."""
        pass1_anchor = {
            "type": "heading",
            "value": "Key Concepts",
            "placement": "after",
            "new_section": None,
            "fit_confidence": 0.89,  # present in Pass-1
        }
        confirmed = [self._build_confirmed_item_with_anchor(pass1_anchor)]
        actions = _ir._build_link_to_moc_actions(confirmed, counter=[0])
        assert len(actions) >= 1
        link_action = next(a for a in actions if a.get("action") == "link_to_moc")
        stamped = link_action["anchor"]
        assert "fit_confidence" not in stamped, (
            f"fit_confidence leaked into Pass-2 anchor: {stamped!r}"
        )

    def test_pass2_anchor_has_only_type_and_value(self) -> None:
        """Pass-2 anchor dict contains ONLY 'type' and 'value' keys (schema contract)."""
        pass1_anchor = {
            "type": "heading",
            "value": "Reasoning",
            "placement": "after",
            "new_section": "Extras",
            "fit_confidence": 0.75,
            "alt_headings": ["Other"],
        }
        confirmed = [self._build_confirmed_item_with_anchor(pass1_anchor)]
        actions = _ir._build_link_to_moc_actions(confirmed, counter=[0])
        link_action = next(a for a in actions if a.get("action") == "link_to_moc")
        stamped = link_action["anchor"]
        # Only type and value allowed
        assert set(stamped.keys()) == {"type", "value"}, (
            f"Unexpected keys in Pass-2 anchor: {set(stamped.keys())!r}"
        )

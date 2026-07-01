#!/usr/bin/env python3
# version: 0.1.0
"""test_spec022_schema_additions.py — Schema addition tests for spec 022 Phase 2.

Three additive optional fields:
  T2.1 — item-result.schema.json: anchor object on candidate_mocs[] items
  T2.2 — shared-ctx.schema.json: headings + editable_callouts on mocs[] items
  T2.3 — instructions.schema.json: new_section on link_to_moc action

Each schema: (a) artifact WITH the new field validates; (b) artifact WITHOUT still validates.

Spec: docs/XDD/specs/022-inbox-triage-improvements/
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


@pytest.fixture(scope="module")
def item_result_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "item-result.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def shared_ctx_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "shared-ctx.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def instructions_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "instructions.schema.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item_result(candidate_mocs: list) -> dict:
    """Minimal valid item-result with given candidate_mocs list."""
    return {
        "schema_version": "1",
        "stem": "my-inbox-note",
        "path": "100 Inbox/my-inbox-note.md",
        "type": "atomic",
        "type_confidence": 0.9,
        "actions": [
            {
                "kind": "create_atomic_note",
                "source_stem": "my-inbox-note",
                "suggested_title": "Some Atomic Note",
                "template": "Atomic Note.md",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": candidate_mocs,
                "tags_to_add": [],
            }
        ],
    }


def _make_shared_ctx(moc_extra: dict | None = None) -> dict:
    """Minimal valid shared-ctx with one moc item, optionally extended."""
    moc = {
        "path": "Atlas/200 Maps/Tech (MOC).md",
        "title": "Tech (MOC)",
        "topics": ["software", "engineering"],
        "is_classification": False,
    }
    if moc_extra:
        moc.update(moc_extra)
    return {
        "schema_version": "1",
        "run_id": "run-001",
        "mocs": [moc],
        "tag_prefixes": [],
        "classification_keywords": {},
    }


def _make_instructions_link_to_moc(extra: dict | None = None) -> dict:
    """Minimal valid instructions doc with one link_to_moc action, optionally extended."""
    action = {
        "id": "I01",
        "action": "link_to_moc",
        "target_moc": "Tech (MOC)",
        "anchor": {"type": "heading", "value": "Notes"},
        "placement": "after",
        "line_to_add": "- [[My Note]]",
    }
    if extra:
        action.update(extra)
    return {
        "schema_version": "2",
        "type": "tomo-instructions",
        "generated": "2026-06-15T10:00:00Z",
        "profile": "miyo",
        "actions": [action],
    }


# ===========================================================================
# T2.1 — item-result: anchor on candidate_mocs[] items
# ===========================================================================


class TestT21ItemResultAnchor:
    """anchor is an optional object on candidate_mocs[] items (spec 022 T2.1)."""

    def test_candidate_moc_with_anchor_validates(self, item_result_schema):
        """candidate_mocs item WITH anchor object passes validation."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Tech (MOC).md",
                "score": 0.85,
                "pre_check": True,
                "anchor": {
                    "type": "heading",
                    "value": "Notes",
                    "placement": "after",
                    "new_section": None,
                },
            }
        ]
        validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_candidate_moc_without_anchor_still_validates(self, item_result_schema):
        """candidate_mocs item WITHOUT anchor (old artifact shape) still passes (additive-only)."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Tech (MOC).md",
                "score": 0.85,
                "pre_check": True,
            }
        ]
        validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_candidate_moc_anchor_with_new_section_string(self, item_result_schema):
        """anchor.new_section as a non-null string validates."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Tech (MOC).md",
                "score": 0.9,
                "pre_check": False,
                "anchor": {
                    "type": "callout",
                    "value": "[!blocks] Key Concepts",
                    "placement": "inside",
                    "new_section": "## New Stuff",
                },
            }
        ]
        validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_candidate_moc_anchor_invalid_type_enum_rejected(self, item_result_schema):
        """anchor.type with invalid enum value is rejected."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Tech (MOC).md",
                "score": 0.9,
                "pre_check": False,
                "anchor": {
                    "type": "bad-type",
                    "value": "Notes",
                    "placement": "after",
                    "new_section": None,
                },
            }
        ]
        with pytest.raises(ValidationError):
            validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_candidate_moc_anchor_invalid_placement_enum_rejected(self, item_result_schema):
        """anchor.placement with invalid enum value is rejected."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Tech (MOC).md",
                "score": 0.9,
                "pre_check": False,
                "anchor": {
                    "type": "heading",
                    "value": "Notes",
                    "placement": "wrong",
                    "new_section": None,
                },
            }
        ]
        with pytest.raises(ValidationError):
            validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_candidate_moc_anchor_missing_value_rejected(self, item_result_schema):
        """anchor object missing the required 'value' key is rejected (key must be present; null is still a legal value)."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Tech (MOC).md",
                "score": 0.9,
                "pre_check": False,
                "anchor": {
                    "type": "heading",
                    "placement": "after",
                },
            }
        ]
        with pytest.raises(ValidationError):
            validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_empty_candidate_mocs_still_validates(self, item_result_schema):
        """Empty candidate_mocs array still validates (no items to check)."""
        validate(instance=_make_item_result([]), schema=item_result_schema)


# ===========================================================================
# T2.2 — shared-ctx: headings + editable_callouts on mocs[] items
# ===========================================================================


class TestT22SharedCtxMocFields:
    """headings and editable_callouts are optional arrays on mocs[] items (spec 022 T2.2)."""

    def test_moc_with_headings_validates(self, shared_ctx_schema):
        """mocs[] item WITH headings array passes validation."""
        validate(
            instance=_make_shared_ctx(
                {"headings": [{"text": "Notes", "level": 2}, {"text": "Resources", "level": 3}]}
            ),
            schema=shared_ctx_schema,
        )

    def test_moc_with_editable_callouts_validates(self, shared_ctx_schema):
        """mocs[] item WITH editable_callouts array passes validation."""
        validate(
            instance=_make_shared_ctx({"editable_callouts": ["[!blocks] Key Concepts", "[!info] Details"]}),
            schema=shared_ctx_schema,
        )

    def test_moc_with_both_new_fields_validates(self, shared_ctx_schema):
        """mocs[] item WITH both headings and editable_callouts passes validation."""
        validate(
            instance=_make_shared_ctx(
                {
                    "headings": [{"text": "Notes", "level": 2}],
                    "editable_callouts": ["[!blocks] Key Concepts"],
                }
            ),
            schema=shared_ctx_schema,
        )

    def test_moc_without_new_fields_still_validates(self, shared_ctx_schema):
        """mocs[] item WITHOUT headings/editable_callouts (old artifact) still passes (additive-only)."""
        validate(instance=_make_shared_ctx(), schema=shared_ctx_schema)

    def test_moc_headings_item_missing_text_rejected(self, shared_ctx_schema):
        """headings item missing required 'text' field is rejected."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_shared_ctx({"headings": [{"level": 2}]}),
                schema=shared_ctx_schema,
            )

    def test_moc_headings_item_missing_level_rejected(self, shared_ctx_schema):
        """headings item missing required 'level' field is rejected."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_shared_ctx({"headings": [{"text": "Notes"}]}),
                schema=shared_ctx_schema,
            )

    def test_moc_editable_callouts_non_string_item_rejected(self, shared_ctx_schema):
        """editable_callouts item that is not a string is rejected."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_shared_ctx({"editable_callouts": [42]}),
                schema=shared_ctx_schema,
            )

    def test_moc_with_has_footer_validates(self, shared_ctx_schema):
        """mocs[] item WITH has_footer boolean validates (review H1) — the field
        is emitted by shared-ctx-builder and consumed by inbox-analyst; it must
        be declared or additionalProperties:false would reject every footer MOC."""
        validate(instance=_make_shared_ctx({"has_footer": True}), schema=shared_ctx_schema)
        validate(instance=_make_shared_ctx({"has_footer": False}), schema=shared_ctx_schema)

    def test_moc_has_footer_non_bool_rejected(self, shared_ctx_schema):
        """has_footer must be a boolean."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_shared_ctx({"has_footer": "yes"}),
                schema=shared_ctx_schema,
            )

    def test_moc_editable_callouts_over_cap_rejected(self, shared_ctx_schema):
        """editable_callouts is capped at maxItems:4 (review M6) — matches the
        builder's _CALLOUTS_CAP truncation."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_shared_ctx(
                    {"editable_callouts": ["[!a] 1", "[!b] 2", "[!c] 3", "[!d] 4", "[!e] 5"]}
                ),
                schema=shared_ctx_schema,
            )

    def test_moc_extra_field_still_rejected(self, shared_ctx_schema):
        """mocs[] item with undeclared extra field is still rejected (additionalProperties: false)."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_shared_ctx({"unknown_extra": "nope"}),
                schema=shared_ctx_schema,
            )


# ===========================================================================
# T2.3 — instructions: new_section on link_to_moc
# ===========================================================================


class TestT23InstructionsLinkToMocNewSection:
    """new_section is Tomo-INTERNAL and stripped before the wire (#68 reverses
    spec 022 T2.3): the heading is baked into line_to_add by _serialize_new_sections,
    so new_section is redundant on the wire and Hashi's link_to_moc schema
    (additionalProperties:false) rejects it. Tomo's schema now matches Hashi's."""

    def test_link_to_moc_with_new_section_string_rejected(self, instructions_schema):
        """link_to_moc WITH new_section on the wire is now rejected (#68)."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_instructions_link_to_moc({"new_section": "## New Section"}),
                schema=instructions_schema,
            )

    def test_link_to_moc_with_new_section_null_rejected(self, instructions_schema):
        """Even new_section=null is rejected — the key itself is not allowed (#68)."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_instructions_link_to_moc({"new_section": None}),
                schema=instructions_schema,
            )

    def test_link_to_moc_without_new_section_validates(self, instructions_schema):
        """link_to_moc WITHOUT new_section is the only valid wire shape (#68)."""
        validate(instance=_make_instructions_link_to_moc(), schema=instructions_schema)

    def test_link_to_moc_extra_field_rejected(self, instructions_schema):
        """link_to_moc with undeclared extra field is rejected (additionalProperties: false)."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_instructions_link_to_moc({"mystery_field": "nope"}),
                schema=instructions_schema,
            )


# ===========================================================================
# T6.2 — item-result: alt_headings on candidate_mocs[].anchor (AC-16 ambiguous-fit advisory)
# ===========================================================================


class TestT62AnchorAltHeadings:
    """alt_headings is an optional [array, null] field on candidate_mocs[].anchor (spec 022 T6.2 / AC-16)."""

    def test_anchor_with_alt_headings_list_validates(self, item_result_schema):
        """anchor WITH alt_headings array of strings validates (AC-16 ambiguous-fit case)."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Self-Care (MOC).md",
                "score": 0.85,
                "pre_check": True,
                "anchor": {
                    "type": "heading",
                    "value": "Habits",
                    "placement": "after",
                    "new_section": None,
                    "alt_headings": ["Routines", "Morning Practice"],
                },
            }
        ]
        validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_anchor_without_alt_headings_still_validates(self, item_result_schema):
        """anchor WITHOUT alt_headings (old artifact) still validates — additive-only back-compat."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Self-Care (MOC).md",
                "score": 0.85,
                "pre_check": True,
                "anchor": {
                    "type": "heading",
                    "value": "Habits",
                    "placement": "after",
                    "new_section": None,
                },
            }
        ]
        validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_anchor_alt_headings_null_validates(self, item_result_schema):
        """anchor.alt_headings=null validates (explicit null is allowed)."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Self-Care (MOC).md",
                "score": 0.85,
                "pre_check": True,
                "anchor": {
                    "type": "heading",
                    "value": "Habits",
                    "placement": "after",
                    "new_section": None,
                    "alt_headings": None,
                },
            }
        ]
        validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_anchor_alt_headings_empty_list_validates(self, item_result_schema):
        """anchor.alt_headings=[] (empty list) validates."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Self-Care (MOC).md",
                "score": 0.85,
                "pre_check": True,
                "anchor": {
                    "type": "heading",
                    "value": "Habits",
                    "placement": "after",
                    "new_section": None,
                    "alt_headings": [],
                },
            }
        ]
        validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_anchor_alt_headings_non_string_item_rejected(self, item_result_schema):
        """anchor.alt_headings with a non-string item is rejected (items must be strings)."""
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Self-Care (MOC).md",
                "score": 0.85,
                "pre_check": True,
                "anchor": {
                    "type": "heading",
                    "value": "Habits",
                    "placement": "after",
                    "new_section": None,
                    "alt_headings": [42],
                },
            }
        ]
        with pytest.raises(ValidationError):
            validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)

    def test_anchor_alt_headings_empty_string_item_rejected(self, item_result_schema):
        """anchor.alt_headings with an empty-string item is rejected (minLength:1 on items).

        Empty strings produce `## ` (blank backtick-heading) in the render advisory.
        The schema must reject them at the source so the reducer never receives them.
        """
        candidate_mocs = [
            {
                "path": "Atlas/200 Maps/Self-Care (MOC).md",
                "score": 0.85,
                "pre_check": True,
                "anchor": {
                    "type": "heading",
                    "value": "Habits",
                    "placement": "after",
                    "new_section": None,
                    "alt_headings": [""],
                },
            }
        ]
        with pytest.raises(ValidationError):
            validate(instance=_make_item_result(candidate_mocs), schema=item_result_schema)


# ===========================================================================
# T1.1 — item-result: fit_confidence on candidate_mocs[].anchor (spec 023)
# ===========================================================================


def _make_anchor_moc(anchor_extra: dict | None = None) -> list:
    """candidate_mocs list with one item carrying a minimal valid anchor, optionally extended."""
    anchor = {
        "type": "heading",
        "value": "Notes",
        "placement": "after",
        "new_section": None,
    }
    if anchor_extra is not None:
        anchor.update(anchor_extra)
    return [
        {
            "path": "Atlas/200 Maps/Tech (MOC).md",
            "score": 0.85,
            "pre_check": True,
            "anchor": anchor,
        }
    ]


class TestT11FitConfidence:
    """fit_confidence is an optional [number, null] field on candidate_mocs[].anchor (spec 023 T1.1)."""

    def test_anchor_with_fit_confidence_number_validates(self, item_result_schema):
        """anchor WITH fit_confidence=0.89 validates."""
        validate(
            instance=_make_item_result(_make_anchor_moc({"fit_confidence": 0.89})),
            schema=item_result_schema,
        )

    def test_anchor_with_fit_confidence_null_validates(self, item_result_schema):
        """anchor WITH fit_confidence=null validates."""
        validate(
            instance=_make_item_result(_make_anchor_moc({"fit_confidence": None})),
            schema=item_result_schema,
        )

    def test_anchor_without_fit_confidence_validates(self, item_result_schema):
        """022-shaped anchor WITHOUT fit_confidence key still validates (back-compat)."""
        validate(
            instance=_make_item_result(_make_anchor_moc()),
            schema=item_result_schema,
        )

    def test_anchor_fit_confidence_above_one_rejected(self, item_result_schema):
        """anchor.fit_confidence=1.01 is rejected (maximum: 1)."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_item_result(_make_anchor_moc({"fit_confidence": 1.01})),
                schema=item_result_schema,
            )

    def test_anchor_fit_confidence_below_zero_rejected(self, item_result_schema):
        """anchor.fit_confidence=-0.1 is rejected (minimum: 0)."""
        with pytest.raises(ValidationError):
            validate(
                instance=_make_item_result(_make_anchor_moc({"fit_confidence": -0.1})),
                schema=item_result_schema,
            )

"""Tests for garden-audit-render.py — the ADR-026 two-artifact producer.

Tests are RED before garden-audit-render.py exists. After GREEN, all 26 tests
must pass. Both artifacts (markdown report + wire JSON) are projected from the
same garden-audit-doc dict (no drift by construction).

Coverage:
  - render_frontmatter: tomo.doc_type=garden-audit, state=pending-accept, skip-analysis
  - render_report: Summary counts, integrity/structure/advisory sections, empty
    sections omitted, index-lag + ACL caveats near top, fixable findings carry
    a checkbox with best-fix pre-selected, advisory read-only (no checkbox);
    zero-findings → "vault healthy"
  - build_wire_payload: schema_version "1", emit_digest present + valid, stable
    finding IDs match report, decision block present on fixable / absent on advisory
  - parity: findings in the report and wire share the same IDs (F01, F02, …)
  - reappeared_exclusions: shown in preamble when present
  - skipped_checks: shown in preamble when present
"""
# version: 0.6.0
import importlib.util
import json
import pathlib
import re
import sys

import jsonschema
import pytest

# ---------------------------------------------------------------------------
# Load the hyphen-named module under test
# ---------------------------------------------------------------------------
_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS_DIR = _ROOT / "tomo" / "scripts"
_SCRIPT = _SCRIPTS_DIR / "garden-audit-render.py"
_WIRE_SCHEMA = _ROOT / "tomo" / "schemas" / "garden-audit-wire.schema.json"

# Must insert scripts dir so 'lib.*' imports resolve inside the loaded module
sys.path.insert(0, str(_SCRIPTS_DIR))

spec = importlib.util.spec_from_file_location("garden_audit_render", _SCRIPT)
gar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gar)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_GENERATED = "2026-07-19T12:00:00Z"
_RUN_ID = "run-test-001"
_PROFILE = "miyo"


def _make_unparented_finding(fid: str = "F01") -> dict:
    return {
        "id": fid,
        "check": "unparented",
        "tier": "structure",
        "fixable": True,
        "target": {"path": "Notes/Orphan Note.md", "stem": "Orphan Note"},
        "detail": {
            "candidate_mocs": [
                {"target_moc": "MOCs/Writing MOC.md", "score": 0.8},
            ]
        },
        "decision": {"selected": True, "action": "link_to_moc"},
    }


_UNSET = object()  # sentinel — distinguishes "not passed" from "passed as None"


def _make_broken_up_finding(fid: str = "F02", up_source=_UNSET, up_value=_UNSET) -> dict:
    # up_source/up_value are OMITTED from detail unless explicitly passed (spec
    # 032 T5.1 prerequisite) — existing callers that don't pass them must keep
    # getting the pre-032 detail shape, byte-identical (CON-7).
    detail = {"up_target": "Deleted MOC"}
    if up_source is not _UNSET:
        detail["up_source"] = up_source
    if up_value is not _UNSET:
        detail["up_value"] = up_value
    return {
        "id": fid,
        "check": "broken_up",
        "tier": "integrity",
        "fixable": True,
        "target": {"path": "Notes/Broken Note.md", "stem": "Broken Note"},
        "detail": detail,
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _make_dead_link_finding(fid: str = "F03") -> dict:
    # dead_target is the raw wikilink stem from graph_audit.deadLinks[].target —
    # no brackets. The render displays it for context; the parser wraps it as
    # [[dead_target]] when building the edit_note_text match field.
    return {
        "id": fid,
        "check": "dead_link",
        "tier": "integrity",
        "fixable": True,
        "target": {"path": "Notes/Source Note.md", "stem": "Source Note"},
        "detail": {"dead_target": "Missing Note", "count": 2},
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _make_duplicate_stem_finding(fid: str = "F04") -> dict:
    return {
        "id": fid,
        "check": "duplicate_stem",
        "tier": "advisory",
        "fixable": False,
        "target": {"path": "Notes/Dup.md", "stem": "Dup"},
        "detail": {
            "dupes": ["Notes/Dup.md", "Archive/Dup.md"],
        },
    }


def _make_stale_moc_finding(fid: str = "F05") -> dict:
    return {
        "id": fid,
        "check": "stale_moc",
        "tier": "advisory",
        "fixable": False,
        "target": {"path": "MOCs/Old MOC.md", "stem": "Old MOC"},
        "detail": {"mtime": "2026-01-01T00:00:00Z"},
    }


def _make_parent_not_moc_finding(fid: str = "F06", up_target: str = "Real Note") -> dict:
    """spec 033 T2.1: the up:: target exists and is in scope but isn't a MOC —
    advisory, not fixable, no decision block at all. Matches exactly the shape
    garden-audit.py's _check_broken_up emits for up_broken_reason=='not-a-moc'
    (see tests/test_garden_audit_parser.py's `_parent_not_moc`)."""
    return {
        "id": fid,
        "check": "parent_not_moc",
        "tier": "advisory",
        "fixable": False,
        "target": {"path": "Notes/Broken.md", "stem": "Broken"},
        "detail": {
            "up_target": up_target,
            "up_source": "inline",
            "up_value": None,
            "up_broken_reason": "not-a-moc",
        },
    }


def _make_doc(findings=None, skipped_checks=None, skipped_checks_reason="", reappeared_exclusions=None) -> dict:
    return {
        "run_id": _RUN_ID,
        "generated": _GENERATED,
        "profile": _PROFILE,
        "findings": findings if findings is not None else [],
        "skipped_checks": skipped_checks if skipped_checks is not None else [],
        "skipped_checks_reason": skipped_checks_reason,
        "reappeared_exclusions": reappeared_exclusions if reappeared_exclusions is not None else [],
    }


def _load_wire_schema() -> dict:
    with _WIRE_SCHEMA.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _render_report(d: dict) -> str:
    """Render the full markdown report as a single string."""
    return gar.render_report(d)


def _build_wire(d: dict) -> dict:
    return gar.build_wire_payload(d)


# ---------------------------------------------------------------------------
# Frontmatter tests
# ---------------------------------------------------------------------------

class TestRenderFrontmatter:
    def test_doc_type_is_garden_audit(self):
        d = _make_doc()
        lines = gar.render_frontmatter(d)
        fm_text = "\n".join(lines)
        assert "garden-audit" in fm_text

    def test_state_is_pending_accept(self):
        d = _make_doc()
        lines = gar.render_frontmatter(d)
        fm_text = "\n".join(lines)
        assert "pending-accept" in fm_text

    def test_skip_inbox_analysis_flag_present(self):
        d = _make_doc()
        lines = gar.render_frontmatter(d)
        fm_text = "\n".join(lines)
        assert "tomo_skip_inbox_analysis" in fm_text
        assert "true" in fm_text.lower()

    def test_run_id_in_frontmatter(self):
        d = _make_doc()
        lines = gar.render_frontmatter(d)
        assert _RUN_ID in "\n".join(lines)

    def test_frontmatter_wrapped_in_triple_dash(self):
        d = _make_doc()
        lines = gar.render_frontmatter(d)
        assert lines[0] == "---"
        assert lines[-1] == "---"


# ---------------------------------------------------------------------------
# Report structure tests
# ---------------------------------------------------------------------------

class TestReportStructure:
    def test_report_has_no_html_comment(self):
        # Spec 030 two-artifact split: the markdown is human-facing DECISIONS
        # only — NO structural `<!-- garden-audit ... -->` comment. Structure
        # lives in the wire, joined by F-id.
        findings = [
            _make_broken_up_finding("F01"),
            _make_dead_link_finding("F02"),
            _make_unparented_finding("F03"),
            _make_duplicate_stem_finding("F04"),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert "<!-- garden-audit" not in report
        assert "<!--" not in report

    def test_caveats_present_index_lag(self):
        d = _make_doc()
        report = _render_report(d)
        assert "index" in report.lower() or "lag" in report.lower() or "snapshot" in report.lower()

    def test_caveats_present_acl(self):
        d = _make_doc()
        report = _render_report(d)
        assert "acl" in report.lower() or "access" in report.lower() or "permission" in report.lower()

    def test_zero_findings_shows_vault_healthy(self):
        d = _make_doc(findings=[])
        report = _render_report(d)
        assert "healthy" in report.lower() or "no findings" in report.lower()

    def test_zero_findings_no_integrity_section(self):
        d = _make_doc(findings=[])
        report = _render_report(d)
        assert "## Integrity" not in report

    def test_summary_shows_tier_counts(self):
        findings = [
            _make_broken_up_finding("F01"),
            _make_dead_link_finding("F02"),
            _make_unparented_finding("F03"),
        ]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        # Summary section must exist
        assert "## Summary" in report
        # Should mention integrity count (2) and structure count (1)
        assert "2" in report
        assert "1" in report

    def test_integrity_section_present_when_findings_exist(self):
        findings = [_make_broken_up_finding()]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        assert "## Integrity" in report or "integrity" in report.lower()

    def test_structure_section_present_when_findings_exist(self):
        findings = [_make_unparented_finding()]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        assert "## Structure" in report or "structure" in report.lower()

    def test_advisory_section_present_when_findings_exist(self):
        findings = [_make_duplicate_stem_finding()]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        assert "## Advisory" in report or "advisory" in report.lower()

    def test_empty_tier_sections_omitted(self):
        # Only advisory findings → no Integrity or Structure sections
        findings = [_make_duplicate_stem_finding()]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        assert "## Integrity" not in report
        assert "## Structure" not in report

    def test_fixable_finding_has_checkbox(self):
        findings = [_make_broken_up_finding(up_source="inline", up_value="[[Alte MOC]]")]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        assert "- [x] Apply" in report

    def test_fixable_finding_preselected_checked(self):
        # decision.selected=True → pre-checked box. Routable (T5.2): a
        # stale-cache/absent-source finding renders no checkbox at all.
        findings = [_make_broken_up_finding(up_source="inline", up_value="[[Alte MOC]]")]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        assert "- [x]" in report

    def test_advisory_finding_no_checkbox(self):
        findings = [_make_duplicate_stem_finding()]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        # Advisory findings carry no per-finding Apply checkbox. (The top-level
        # "- [ ] Approved" gate is always present and is not a per-finding box.)
        assert "] Apply" not in report
        assert "- [x]" not in report

    def test_reappeared_exclusions_in_preamble(self):
        reappeared = [
            {"target": {"type": "note", "value": "Notes/Temp.md"}, "checks": "all", "mode": "temporary", "until": "2026-01-01"}
        ]
        d = _make_doc(reappeared_exclusions=reappeared)
        report = _render_report(d)
        assert "reappear" in report.lower() or "lapsed" in report.lower() or "expired" in report.lower()

    def test_skipped_checks_in_preamble(self):
        d = _make_doc(skipped_checks=["orphan", "dead_link"], skipped_checks_reason="graph unavailable")
        report = _render_report(d)
        assert "orphan" in report.lower() or "skip" in report.lower() or "not run" in report.lower()

    def test_finding_id_present_in_report(self):
        findings = [_make_broken_up_finding("F01")]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        assert "F01" in report


# ---------------------------------------------------------------------------
# Wire payload tests
# ---------------------------------------------------------------------------

class TestWirePayload:
    def test_schema_version_is_one(self):
        d = _make_doc()
        wire = _build_wire(d)
        assert wire["schema_version"] == "1"

    def test_emit_digest_present_and_sha256_format(self):
        d = _make_doc()
        wire = _build_wire(d)
        digest = wire.get("emit_digest", "")
        assert re.match(r"^sha256:[a-f0-9]{64}$", digest), f"bad digest: {digest!r}"

    def test_emit_digest_is_stable(self):
        d = _make_doc()
        wire1 = _build_wire(d)
        wire2 = _build_wire(d)
        assert wire1["emit_digest"] == wire2["emit_digest"]

    def test_emit_digest_changes_on_finding_edit(self):
        d1 = _make_doc(findings=[_make_broken_up_finding("F01")])
        d2 = _make_doc(findings=[_make_dead_link_finding("F01")])
        w1 = _build_wire(d1)
        w2 = _build_wire(d2)
        assert w1["emit_digest"] != w2["emit_digest"]

    def test_wire_findings_match_doc_ids(self):
        findings = [_make_broken_up_finding("F01"), _make_unparented_finding("F02")]
        d = _make_doc(findings=findings)
        wire = _build_wire(d)
        wire_ids = {f["id"] for f in wire["findings"]}
        assert wire_ids == {"F01", "F02"}

    def test_fixable_finding_has_decision_in_wire(self):
        findings = [_make_broken_up_finding("F01")]
        d = _make_doc(findings=findings)
        wire = _build_wire(d)
        f = next(f for f in wire["findings"] if f["id"] == "F01")
        assert "decision" in f
        assert "selected" in f["decision"]
        assert "action" in f["decision"]

    def test_advisory_finding_no_decision_in_wire(self):
        findings = [_make_duplicate_stem_finding("F01")]
        d = _make_doc(findings=findings)
        wire = _build_wire(d)
        f = next(f for f in wire["findings"] if f["id"] == "F01")
        assert "decision" not in f

    def test_wire_schema_valid_empty(self):
        schema = _load_wire_schema()
        d = _make_doc()
        wire = _build_wire(d)
        jsonschema.validate(wire, schema)  # raises on failure

    def test_wire_schema_valid_with_findings(self):
        schema = _load_wire_schema()
        findings = [
            _make_broken_up_finding("F01"),
            _make_dead_link_finding("F02"),
            _make_unparented_finding("F03"),
            _make_duplicate_stem_finding("F04"),
            _make_stale_moc_finding("F05"),
        ]
        d = _make_doc(findings=findings)
        wire = _build_wire(d)
        jsonschema.validate(wire, schema)


# ---------------------------------------------------------------------------
# Wire schema declares up_source/up_value (spec 032 T2.2)
#
# detail is additionalProperties:true, so a validation-only assertion CANNOT
# go red — the fields already validate as unknown extra properties. These
# tests assert the DECLARATION itself in the schema JSON.
# ---------------------------------------------------------------------------

class TestWireSchemaUpSourceUpValue:
    def test_wire_schema_declares_up_source_enum(self):
        """garden-audit-wire.schema.json declares detail.up_source with an
        enum admitting 'inline', 'frontmatter' and null. [T2.2]
        """
        schema = _load_wire_schema()
        detail_props = schema["properties"]["findings"]["items"]["properties"]["detail"]["properties"]
        assert "up_source" in detail_props, "up_source must be declared in detail.properties"
        assert set(detail_props["up_source"]["enum"]) == {"inline", "frontmatter", None}

    def test_wire_schema_declares_up_value(self):
        """garden-audit-wire.schema.json declares detail.up_value. [T2.2]"""
        schema = _load_wire_schema()
        detail_props = schema["properties"]["findings"]["items"]["properties"]["detail"]["properties"]
        assert "up_value" in detail_props, "up_value must be declared in detail.properties"

    def test_up_source_up_value_absent_from_required_guard_against_creep(self):
        """Guard: up_source/up_value must NOT land in any 'required' array —
        every pre-change artefact lacks them (CON-7). Passes trivially today;
        it locks the property against a later 'add to required' regression.
        """
        schema = _load_wire_schema()
        finding_schema = schema["properties"]["findings"]["items"]
        detail_schema = finding_schema["properties"]["detail"]
        assert "up_source" not in finding_schema.get("required", [])
        assert "up_value" not in finding_schema.get("required", [])
        assert "up_source" not in detail_schema.get("required", [])
        assert "up_value" not in detail_schema.get("required", [])

    def test_finding_without_up_source_up_value_still_validates_guard_against_required_creep(self):
        """Guard: a finding without up_source/up_value still validates
        against the wire schema — every pre-032 artefact (CON-7). Passes
        trivially today (they're simply absent); guards a later regression
        that makes them required.
        """
        schema = _load_wire_schema()
        d = _make_doc(findings=[_make_broken_up_finding("F01")])
        wire = _build_wire(d)
        jsonschema.validate(wire, schema)

    def test_up_value_has_no_type_constraint_guard_against_creep(self):
        """Guard: up_value must stay UNCONSTRAINED — it carries a raw
        frontmatter property value that may be a list, a string, or null.
        If someone later adds e.g. "type": "string" to the schema, this
        test catches it because the list/null artefacts below would fail.
        """
        schema = _load_wire_schema()
        for value in (["Deleted MOC", "Other Ref"], "Deleted MOC", None):
            finding = _make_broken_up_finding("F01")
            finding["detail"] = {
                "up_target": "Deleted MOC",
                "up_source": "frontmatter",
                "up_value": value,
            }
            d = _make_doc(findings=[finding])
            wire = _build_wire(d)
            jsonschema.validate(wire, schema)


# ---------------------------------------------------------------------------
# Parity test: report finding IDs ↔ wire finding IDs
# ---------------------------------------------------------------------------

class TestReportWireParity:
    def test_finding_ids_match_between_report_and_wire(self):
        findings = [
            _make_broken_up_finding("F01"),
            _make_unparented_finding("F02"),
            _make_duplicate_stem_finding("F03"),
        ]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        wire = _build_wire(d)

        report_ids = set(re.findall(r"\bF\d+\b", report))
        wire_ids = {f["id"] for f in wire["findings"]}
        assert report_ids == wire_ids

    def test_severity_order_integrity_before_structure(self):
        # broken_up (integrity) must appear before unparented (structure) in the wire
        findings = [
            _make_unparented_finding("F01"),   # structure — came first in list
            _make_broken_up_finding("F02"),    # integrity — should precede structure
        ]
        d = _make_doc(findings=findings)
        wire = _build_wire(d)
        tiers = [f["tier"] for f in wire["findings"]]
        # integrity finding (F02) must appear before structure finding (F01)
        idx_integrity = next(i for i, t in enumerate(tiers) if t == "integrity")
        idx_structure = next(i for i, t in enumerate(tiers) if t == "structure")
        assert idx_integrity < idx_structure


# ---------------------------------------------------------------------------
# FIX 1 regression: doc_type=garden-audit must be valid in doc-frontmatter schema
# ---------------------------------------------------------------------------

class TestFrontmatterSchemaValidation:
    """Stamped frontmatter must be schema-valid (ADR-1 registers garden-audit as 4th peer)."""

    def _load_fm_schema(self) -> dict:
        schema_path = _ROOT / "tomo" / "schemas" / "doc-frontmatter.schema.json"
        with schema_path.open() as f:
            return json.load(f)

    def test_garden_audit_doc_type_in_enum(self):
        # The doc_type enum in doc-frontmatter.schema.json must include "garden-audit".
        # This test fails before the enum is extended.
        schema = self._load_fm_schema()
        enum_values = schema["properties"]["tomo"]["properties"]["doc_type"]["enum"]
        assert "garden-audit" in enum_values, f"garden-audit not in enum: {enum_values}"

    def test_build_tomo_block_garden_audit_does_not_raise(self):
        # Under TOMO_SCHEMA_STRICT=1 build_tomo_block raises SchemaValidationError when
        # doc_type is absent from the schema. This test drives the enum + oneOf fix.
        #
        # IMPORTANT: do NOT delete lib.doc_frontmatter from sys.modules — doing so
        # creates a second class object for SchemaValidationError that breaks
        # pytest.raises(SchemaValidationError) checks in other test files that hold
        # a reference to the original class (identity mismatch → uncaught raise).
        # Instead, call build_tomo_block directly with TOMO_SCHEMA_STRICT active;
        # the env var governs whether _validate() runs, not the module identity.
        import os

        old = os.environ.get("TOMO_SCHEMA_STRICT")
        os.environ["TOMO_SCHEMA_STRICT"] = "1"
        try:
            from lib.doc_frontmatter import build_tomo_block as _btb
            # Must not raise — garden-audit is now in the schema enum + oneOf
            block = _btb(doc_type="garden-audit", state="pending-accept", run_id="r-test")
            assert block["doc_type"] == "garden-audit"
            assert block["state"] == "pending-accept"
        finally:
            if old is None:
                os.environ.pop("TOMO_SCHEMA_STRICT", None)
            else:
                os.environ["TOMO_SCHEMA_STRICT"] = old

    def test_stamped_frontmatter_validates_against_fm_schema(self):
        # The full frontmatter dict emitted by render_frontmatter must validate.
        d = _make_doc()
        fm_lines = gar.render_frontmatter(d)
        # Parse the YAML between the --- fences
        fm_text = "\n".join(fm_lines[1:-1])  # strip leading/trailing ---
        import yaml as _yaml
        fm_dict = _yaml.safe_load(fm_text)
        schema = self._load_fm_schema()
        jsonschema.validate({"tomo": fm_dict["tomo"]}, schema)  # raises on failure


# ---------------------------------------------------------------------------
# FIX 2 regression: all-advisory run summary message
# ---------------------------------------------------------------------------

class TestAllAdvisoryRun:
    """All-advisory run → Summary states 'no fixable findings'; no checkbox affordance."""

    def test_all_advisory_summary_message(self):
        findings = [
            _make_duplicate_stem_finding("F01"),
            _make_stale_moc_finding("F02"),
        ]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        # Must contain an explicit "no fixable" message
        assert "no fixable" in report.lower() or "advisory" in report.lower()

    def test_all_advisory_no_checkbox_in_report(self):
        findings = [
            _make_duplicate_stem_finding("F01"),
            _make_stale_moc_finding("F02"),
        ]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        # No per-finding Apply box for an all-advisory run. The top-level
        # "- [ ] Approved" gate is still present (it is not a fixable box).
        assert "] Apply" not in report
        assert "- [x]" not in report

    def test_all_advisory_summary_says_no_fixable_findings(self):
        # The summary section must contain an EXPLICIT "no fixable findings" phrase.
        # "Advisory: 2" alone does not satisfy the PRD requirement.
        findings = [_make_duplicate_stem_finding("F01")]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        summary_start = report.find("## Summary")
        assert summary_start != -1
        summary_block = report[summary_start:summary_start + 500]
        assert "no fixable" in summary_block.lower(), (
            f"Summary should say 'no fixable findings'; got:\n{summary_block}"
        )


# ---------------------------------------------------------------------------
# FIX 1 regression: dead_link wire finding must carry decision.replace=""
# (editable by the user to specify a replacement target; empty = remove intent)
# ---------------------------------------------------------------------------

class TestDeadLinkWireReplace:
    """build_wire_payload must populate decision.replace='' on dead_link findings.

    The replace field is the editable slot the user fills in the wire to specify
    a replacement target for the dead wikilink. An empty string signals remove intent.
    garden-audit-parser.py reads decision.replace (not detail.replace_target).
    """

    def test_dead_link_wire_finding_has_decision_replace_field(self):
        findings = [_make_dead_link_finding("F01")]
        d = _make_doc(findings=findings)
        wire = _build_wire(d)
        f = next(f for f in wire["findings"] if f["id"] == "F01")
        assert "decision" in f
        assert "replace" in f["decision"], "decision.replace field missing from dead_link wire finding"

    def test_dead_link_wire_decision_replace_defaults_to_empty_string(self):
        findings = [_make_dead_link_finding("F01")]
        d = _make_doc(findings=findings)
        wire = _build_wire(d)
        f = next(f for f in wire["findings"] if f["id"] == "F01")
        assert f["decision"]["replace"] == "", (
            f"decision.replace should default to '' (remove intent), got {f['decision']['replace']!r}"
        )

    def test_non_dead_link_fixable_finding_has_no_replace_in_decision(self):
        # Other fixable checks (broken_up, unparented) must NOT get decision.replace
        findings = [_make_broken_up_finding("F01")]
        d = _make_doc(findings=findings)
        wire = _build_wire(d)
        f = next(f for f in wire["findings"] if f["id"] == "F01")
        assert "replace" not in f["decision"], (
            "decision.replace should only appear on dead_link findings"
        )

    def test_dead_link_wire_schema_valid_with_replace_field(self):
        schema = _load_wire_schema()
        findings = [_make_dead_link_finding("F01")]
        d = _make_doc(findings=findings)
        wire = _build_wire(d)
        # After adding replace to schema, this must validate without error
        jsonschema.validate(wire, schema)


class TestBrokenUpWireRepoint:
    """build_wire_payload must populate decision.repoint='' on broken_up findings.

    W1: the WIRE path needs a repoint slot mirroring the markdown "Repoint to:"
    field, so a wire-edited repoint points up:: at the user's chosen MOC rather
    than the broken original. Empty string = remove intent (parser falls back).
    """

    def test_broken_up_wire_finding_has_decision_repoint_field(self):
        findings = [_make_broken_up_finding("F01")]
        wire = _build_wire(_make_doc(findings=findings))
        f = next(f for f in wire["findings"] if f["id"] == "F01")
        assert "repoint" in f["decision"], "decision.repoint missing on broken_up"

    def test_broken_up_wire_decision_repoint_defaults_to_empty_string(self):
        findings = [_make_broken_up_finding("F01")]
        wire = _build_wire(_make_doc(findings=findings))
        f = next(f for f in wire["findings"] if f["id"] == "F01")
        assert f["decision"]["repoint"] == ""

    def test_non_broken_up_fixable_finding_has_no_repoint_in_decision(self):
        findings = [_make_dead_link_finding("F01")]
        wire = _build_wire(_make_doc(findings=findings))
        f = next(f for f in wire["findings"] if f["id"] == "F01")
        assert "repoint" not in f["decision"], (
            "decision.repoint should only appear on broken_up findings"
        )

    def test_broken_up_wire_schema_valid_with_repoint_field(self):
        schema = _load_wire_schema()
        findings = [_make_broken_up_finding("F01")]
        wire = _build_wire(_make_doc(findings=findings))
        jsonschema.validate(wire, schema)


# ---------------------------------------------------------------------------
# W1 regression: fixable finding with missing decision block → ValueError
# ---------------------------------------------------------------------------

class TestMalformedFindingGuard:
    """A fixable (non-advisory) finding without a decision block is a contract
    violation — _render_finding must raise ValueError, not silently skip."""

    def test_fixable_finding_missing_decision_raises(self):
        # Build a fixable finding that lacks the 'decision' key entirely.
        malformed = {
            "id": "F01",
            "check": "broken_up",
            "tier": "integrity",
            "fixable": True,
            "target": {"path": "Notes/Broken.md", "stem": "Broken"},
            "detail": {"up_target": "Deleted MOC"},
            # deliberately NO 'decision' key
        }
        d = _make_doc(findings=[malformed])
        with pytest.raises(ValueError, match="F01"):
            _render_report(d)


class TestClickableLinksAndFixSummary:
    """Regression: report note-refs must be [[wikilinks]] (clickable/hover-able in
    Obsidian), never `backticks`; and each fix must describe WHAT it does. Live-E2E
    surfaced `Deleted MOC` (dead) + a leaked Python list repr ['020 Active MOC']."""

    def test_broken_up_stem_renders_as_wikilink_not_backtick(self):
        report = _render_report(_make_doc(findings=[_make_broken_up_finding()]))
        assert "[[Broken Note]]" in report
        assert "`Broken Note`" not in report

    def test_broken_up_target_renders_as_wikilink(self):
        report = _render_report(_make_doc(findings=[_make_broken_up_finding()]))
        assert "[[Deleted MOC]]" in report

    def test_up_target_list_does_not_leak_python_repr(self):
        # Cache stores up:: as a multi-value list — must render [[020 Active MOC]],
        # never the raw list repr ['020 Active MOC'].
        f = _make_broken_up_finding()
        f["detail"]["up_target"] = ["020 Active MOC"]
        report = _render_report(_make_doc(findings=[f]))
        assert "[[020 Active MOC]]" in report
        assert "['020 Active MOC']" not in report
        assert "[020 Active MOC]" not in report.replace("[[020 Active MOC]]", "")

    def test_broken_up_fix_describes_both_repoint_and_remove(self):
        # FIX 3: every broken_up now offers repoint OR remove (not removal-only).
        # Routable (T5.2): a withheld finding has no Fix line to describe.
        f = _make_broken_up_finding(up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        assert "repoint" in report.lower()
        assert "remove" in report.lower()

    def test_broken_up_offers_repoint_field_for_every_finding(self):
        # FIX 3: the editable Repoint field renders for a plain broken_up removal
        # finding (action=edit_note_text), not just pre-marked repoints. Routable
        # (T5.2): a withheld finding renders no editable field.
        f = _make_broken_up_finding(up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        assert "**Repoint to:**" in report

    def test_broken_up_repoint_action_also_offers_repoint_field(self):
        f = _make_broken_up_finding(up_source="inline", up_value="[[Alte MOC]]")
        f["decision"]["action"] = "add_relationship"
        report = _render_report(_make_doc(findings=[f]))
        assert "**Repoint to:**" in report

    def test_unparented_fix_names_candidate_moc(self):
        report = _render_report(_make_doc(findings=[_make_unparented_finding()]))
        # candidate target_moc "MOCs/Writing MOC.md" → wikilink stem, path dropped
        assert "[[Writing MOC]]" in report
        assert "up::" in report

    def test_dead_link_fix_mentions_replacement(self):
        f = _make_dead_link_finding()
        f["decision"] = {"selected": True, "action": "edit_note_text", "replace": "[[New Target]]"}
        report = _render_report(_make_doc(findings=[f]))
        assert "[[New Target]]" in report
        assert "Replace" in report

    def test_fix_line_no_longer_says_apply_backtick_action(self):
        report = _render_report(_make_doc(findings=[_make_broken_up_finding(up_source="inline", up_value="[[Alte MOC]]")]))
        assert "Apply `edit_note_text`" not in report


# ---------------------------------------------------------------------------
# FIX 1: top-level Approved gate (ADR-1 revised — mirrors suggestions)
# ---------------------------------------------------------------------------

class TestTopLevelApproveGate:
    def test_approved_box_present_with_findings(self):
        report = _render_report(_make_doc(findings=[_make_broken_up_finding()]))
        assert "- [ ] Approved" in report

    def test_approved_box_present_on_zero_findings(self):
        # The gate renders even for a healthy vault (nothing to apply, but the
        # doc still flows through the pending-accept → accepted lifecycle).
        report = _render_report(_make_doc(findings=[]))
        assert "- [ ] Approved" in report

    def test_approved_box_unticked_by_default(self):
        report = _render_report(_make_doc(findings=[_make_dead_link_finding()]))
        # Present AND unticked — an omitted gate would fail the first assert.
        assert "- [ ] Approved" in report
        assert "- [x] Approved" not in report

    def test_approved_box_mentions_inbox(self):
        report = _render_report(_make_doc(findings=[_make_dead_link_finding()]))
        # Must tell the user to run /inbox after ticking.
        approved_line = next(
            ln for ln in report.splitlines() if "Approved" in ln
        )
        assert "/inbox" in approved_line


# ---------------------------------------------------------------------------
# FIX 2 (defensive render): a dirty cache storing a list as its str repr must
# still render clean [[stems]], never [[['…']]].
# ---------------------------------------------------------------------------

class TestDirtyListReprRender:
    def test_broken_up_stringified_list_renders_clean_wikilink(self):
        f = _make_broken_up_finding()
        f["detail"]["up_target"] = "['020 Active MOC']"  # dirty cache str-repr
        report = _render_report(_make_doc(findings=[f]))
        assert "[[020 Active MOC]]" in report
        assert "['020 Active MOC']" not in report
        assert "[[['" not in report

    def test_broken_up_stringified_multi_list_renders_all(self):
        f = _make_broken_up_finding()
        f["detail"]["up_target"] = "['020 Active MOC', '030 Reference MOC']"
        report = _render_report(_make_doc(findings=[f]))
        assert "[[020 Active MOC]]" in report
        assert "[[030 Reference MOC]]" in report
        assert "['020 Active MOC'" not in report

    def test_dirty_list_visible_line_has_no_html_comment(self):
        # Spec 030 two-artifact split: the report is human-facing only — no
        # structural HTML comment. The dirty list is unwrapped in the VISIBLE
        # detail line; the parser reconstructs match from the wire's up_target.
        f = _make_broken_up_finding()
        f["detail"]["up_target"] = "['020 Active MOC']"
        report = _render_report(_make_doc(findings=[f]))
        assert "<!-- garden-audit" not in report
        assert "Broken `up::` → [[020 Active MOC]]" in report


# ---------------------------------------------------------------------------
# Phase 7 (T7.2): Suggest opt-in render + --suggest enrichment
# ---------------------------------------------------------------------------

def _full_report(d: dict) -> str:
    """Frontmatter + body — the artifact --suggest enrichment operates on."""
    return "\n".join(gar.render_frontmatter(d)) + "\n" + gar.render_report(d)


class TestSuggestOptInRender:
    def test_dead_link_has_suggest_box(self):
        report = _render_report(_make_doc(findings=[_make_dead_link_finding("F01")]))
        assert "- [ ] Suggest targets" in report

    def test_broken_up_has_suggest_box(self):
        # Routable (T5.2): a withheld finding renders no Suggest opt-in either —
        # there is nothing to suggest a target for until the cache is refreshed.
        f = _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        assert "- [ ] Suggest targets" in report

    def test_unparented_has_suggest_box(self):
        # Change 2: structure findings now ALSO get the Suggest opt-in.
        report = _render_report(_make_doc(findings=[_make_unparented_finding("F01")]))
        assert "- [ ] Suggest targets" in report

    def test_orphan_has_suggest_box(self):
        f = _make_unparented_finding("F01")
        f["check"] = "orphan"
        report = _render_report(_make_doc(findings=[f]))
        assert "- [ ] Suggest targets" in report

    def test_unparented_has_file_under_field(self):
        report = _render_report(_make_doc(findings=[_make_unparented_finding("F01")]))
        assert "- **File under:**" in report

    def test_advisory_has_no_suggest_box(self):
        report = _render_report(_make_doc(findings=[_make_duplicate_stem_finding("F01")]))
        assert "Suggest targets" not in report

    def test_advisory_has_no_file_under_field(self):
        report = _render_report(_make_doc(findings=[_make_duplicate_stem_finding("F01")]))
        assert "File under:" not in report

    def test_suggest_box_unticked_by_default(self):
        report = _render_report(_make_doc(findings=[_make_dead_link_finding("F01")]))
        assert "- [x] Suggest targets" not in report


class TestIntegrityHeaderSaysIn:
    """Change 1: integrity headers read '<label> in: [[note]]' (the note is the
    container); structure/advisory stay '<label>: [[note]]' (note is the subject)."""

    def test_broken_up_header_says_in(self):
        report = _render_report(_make_doc(findings=[_make_broken_up_finding("F01")]))
        assert "### F01 — Broken up:: link in: [[Broken Note]]" in report

    def test_dead_link_header_says_in(self):
        report = _render_report(_make_doc(findings=[_make_dead_link_finding("F01")]))
        assert "### F01 — Dead link in: [[Source Note]]" in report

    def test_unparented_header_uses_colon(self):
        report = _render_report(_make_doc(findings=[_make_unparented_finding("F01")]))
        assert "### F01 — Unparented note: [[Orphan Note]]" in report
        assert " in: " not in report.split("## Structure")[-1].split("\n\n")[0]

    def test_advisory_header_uses_colon(self):
        report = _render_report(_make_doc(findings=[_make_duplicate_stem_finding("F01")]))
        assert "### F01 — Duplicate stem: [[Dup]]" in report


class TestSuggestEnrichment:
    """--suggest reads report + wire + cache, computes candidates for
    Suggest-ticked findings, and rewrites ONLY those blocks with a pick list."""

    def _dead_link_cache(self):
        # Cache note stems including a near-miss of the dead target "Missing Note".
        return [
            {"stem": "Missing Notes", "kind": "note", "path": "N/Missing Notes.md", "topics": []},
            {"stem": "Unrelated Thing", "kind": "note", "path": "N/Unrelated Thing.md", "topics": []},
        ]

    def _broken_up_cache(self):
        return [
            {"stem": "Writing MOC", "kind": "moc", "path": "MOCs/Writing MOC.md", "topics": ["writing"]},
            {"stem": "Cooking MOC", "kind": "moc", "path": "MOCs/Cooking MOC.md", "topics": ["cooking"]},
        ]

    def test_ticked_dead_link_gets_pick_list(self):
        doc = _make_doc(findings=[_make_dead_link_finding("F01")])
        report = _full_report(doc)
        wire = _build_wire(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        out = gar.enrich_report_with_suggestions(report, wire, self._dead_link_cache())
        assert "[[Missing Notes]]" in out
        assert "Pick one" in out

    def test_unticked_dead_link_untouched(self):
        doc = _make_doc(findings=[_make_dead_link_finding("F01")])
        report = _full_report(doc)
        wire = _build_wire(doc)
        out = gar.enrich_report_with_suggestions(report, wire, self._dead_link_cache())
        # No Suggest tick → block unchanged, no pick list.
        assert out == report
        assert "Pick one" not in out

    def test_ticked_broken_up_gets_moc_pick_list(self):
        # Routable (T5.2): a withheld finding renders no Suggest box to tick.
        f = _make_broken_up_finding("F01", up_source="inline", up_value="[[Writng MOC]]")
        f["detail"]["up_target"] = "Writng MOC"  # typo of "Writing MOC"
        doc = _make_doc(findings=[f])
        report = _full_report(doc)
        wire = _build_wire(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        out = gar.enrich_report_with_suggestions(report, wire, self._broken_up_cache())
        assert "[[Writing MOC]]" in out

    def test_approved_gate_and_other_findings_preserved(self):
        findings = [_make_dead_link_finding("F01"), _make_duplicate_stem_finding("F02")]
        doc = _make_doc(findings=findings)
        report = _full_report(doc)
        wire = _build_wire(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        out = gar.enrich_report_with_suggestions(report, wire, self._dead_link_cache())
        # Approved gate intact.
        assert "- [ ] Approved" in out
        # Advisory F02 block (no fix) is byte-for-byte present.
        assert "### F02 — Duplicate stem" in out

    def test_enrichment_is_idempotent(self):
        doc = _make_doc(findings=[_make_dead_link_finding("F01")])
        report = _full_report(doc)
        wire = _build_wire(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        once = gar.enrich_report_with_suggestions(report, wire, self._dead_link_cache())
        twice = gar.enrich_report_with_suggestions(once, wire, self._dead_link_cache())
        assert once == twice

    def _unparented_cache(self):
        # A MOC with weak (below-scan-threshold) topic overlap to the orphan note.
        return [
            {"stem": "Writing MOC", "kind": "moc", "path": "MOCs/Writing MOC.md",
             "topics": ["writing"]},
        ]

    def test_ticked_unparented_gets_moc_pick_list(self):
        # Change 2: a Suggest-ticked orphan/unparented gets MOC candidates even
        # below the scan threshold (the note had weak overlap).
        f = _make_unparented_finding("F01")
        f["detail"] = {"candidate_mocs": [], "topics": ["writing", "misc", "notes"]}
        doc = _make_doc(findings=[f])
        report = _full_report(doc)
        wire = _build_wire(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        out = gar.enrich_report_with_suggestions(report, wire, self._unparented_cache())
        assert "[[Writing MOC]]" in out
        assert "Pick one" in out

    def test_no_candidates_renders_no_suggestions_note(self):
        # Change 3: a Suggest-ticked finding with ZERO candidates gets an explicit
        # note (not silently unchanged — the user always gets feedback).
        doc = _make_doc(findings=[_make_dead_link_finding("F01")])
        report = _full_report(doc)
        wire = _build_wire(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        cache = [{"stem": "Zzz Qqq", "kind": "note", "path": "N/z.md", "topics": []}]
        out = gar.enrich_report_with_suggestions(report, wire, cache)
        assert "Pick one" not in out
        assert "No suggestions found" in out

    def test_no_suggestions_note_for_unparented(self):
        # Change 3 covers structure too: a ticked orphan with zero topic overlap.
        f = _make_unparented_finding("F01")
        f["detail"] = {"candidate_mocs": [], "topics": ["cooking"]}
        doc = _make_doc(findings=[f])
        report = _full_report(doc)
        wire = _build_wire(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        cache = [{"stem": "Writing MOC", "kind": "moc", "path": "MOCs/Writing MOC.md",
                  "topics": ["writing"]}]
        out = gar.enrich_report_with_suggestions(report, wire, cache)
        assert "No suggestions found" in out

    def test_no_suggestions_note_is_idempotent(self):
        doc = _make_doc(findings=[_make_dead_link_finding("F01")])
        report = _full_report(doc)
        wire = _build_wire(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        cache = [{"stem": "Zzz Qqq", "kind": "note", "path": "N/z.md", "topics": []}]
        once = gar.enrich_report_with_suggestions(report, wire, cache)
        twice = gar.enrich_report_with_suggestions(once, wire, cache)
        assert once == twice
        assert twice.count("No suggestions found") == 1

    def test_unticked_finding_gets_no_suggestions_note(self):
        # The no-suggestions note is only for Suggest-TICKED findings.
        doc = _make_doc(findings=[_make_dead_link_finding("F01")])
        report = _full_report(doc)
        wire = _build_wire(doc)
        cache = [{"stem": "Zzz Qqq", "kind": "note", "path": "N/z.md", "topics": []}]
        out = gar.enrich_report_with_suggestions(report, wire, cache)
        assert "No suggestions found" not in out

    def test_no_suggestions_note_for_broken_up(self):
        # Change 3 on the broken_up repoint path: the note has NO topics and the
        # cache MOC stem is dissimilar to the up-target "Deleted MOC" → neither
        # the topic nor the stem signal produces a candidate.
        # Routable (T5.2): a withheld finding renders no Suggest box to tick.
        f = _make_broken_up_finding("F01")
        f["detail"] = {
            "up_target": "Deleted MOC", "topics": [],
            "up_source": "inline", "up_value": "[[Deleted MOC]]",
        }
        doc = _make_doc(findings=[f])
        report = _full_report(doc)
        wire = _build_wire(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        cache = [{"stem": "Zzz Qqq MOC", "kind": "moc", "path": "MOCs/Zzz Qqq MOC.md",
                  "topics": ["quantum"]}]
        out = gar.enrich_report_with_suggestions(report, wire, cache)
        assert "No suggestions found" in out
        assert "Pick one" not in out

    def test_no_suggestions_note_for_orphan(self):
        # Change 3 on the orphan file-under path: zero topic overlap with the
        # cache MOC → suggest_file_under_mocs returns nothing.
        f = _make_unparented_finding("F01")
        f["check"] = "orphan"
        f["detail"] = {"candidate_mocs": [], "topics": ["cooking"]}
        doc = _make_doc(findings=[f])
        report = _full_report(doc)
        wire = _build_wire(doc)
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        cache = [{"stem": "Writing MOC", "kind": "moc", "path": "MOCs/Writing MOC.md",
                  "topics": ["writing"]}]
        out = gar.enrich_report_with_suggestions(report, wire, cache)
        assert "No suggestions found" in out
        assert "Pick one" not in out


# ---------------------------------------------------------------------------
# Spec 032 T5.1: property-edit disclosure at approval time
# ---------------------------------------------------------------------------
# A broken_up finding resident in frontmatter (up_source == "frontmatter") gets
# fixed via a YAML-property edit, which drops any comments in that property
# block irreversibly. The report must disclose this BEFORE the user ticks
# Apply — a post-hoc note is too late by construction. The wording is
# verbatim-locked (solution.md UI & UX); the property name is derived via
# marker_word(conventions.parent_marker) (ADR-6), never hardcoded to "up".

_DISCLOSURE_TARGET_LINE = (
    "- **Fix target:** note property `{prop}` — editing YAML properties."
)
_DISCLOSURE_WARNING_LINE = (
    "  ⚠️ Comments inside this note's property block will not survive the edit."
)


class TestPropertyEditDisclosure:
    def test_frontmatter_resident_renders_verbatim_disclosure_with_default_property(self):
        # Default (miyo) profile's parent marker is "up::" → marker_word → "up".
        f = _make_broken_up_finding(up_source="frontmatter", up_value=["[[Alte MOC]]"])
        report = _render_report(_make_doc(findings=[f]))
        assert _DISCLOSURE_TARGET_LINE.format(prop="up") in report
        assert _DISCLOSURE_WARNING_LINE in report

    def test_frontmatter_resident_disclosure_uses_derived_not_hardcoded_property(
        self, tmp_path, monkeypatch
    ):
        # ADR-6 proof: a profile configured with a DIFFERENT parent marker must
        # change the disclosed property name. If the renderer hardcoded "up",
        # this test would still see "up" and fail.
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "custom.yaml").write_text(
            "relationship_defaults:\n  parent:\n    marker: \"parent::\"\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gar, "DEFAULT_PROFILES_DIR", profiles_dir)

        f = _make_broken_up_finding(up_source="frontmatter", up_value=["[[Alte MOC]]"])
        d = _make_doc(findings=[f])
        d["profile"] = "custom"
        report = _render_report(d)
        assert _DISCLOSURE_TARGET_LINE.format(prop="parent") in report
        assert _DISCLOSURE_TARGET_LINE.format(prop="up") not in report

    def test_frontmatter_resident_disclosure_appears_before_apply_checkbox(self):
        # "At approval time" — the user must read the warning before ticking
        # Apply, not after.
        f = _make_broken_up_finding(up_source="frontmatter", up_value=["[[Alte MOC]]"])
        report = _render_report(_make_doc(findings=[f]))
        disclosure_idx = report.index(_DISCLOSURE_TARGET_LINE.format(prop="up"))
        apply_idx = report.index("Apply — tick to apply this fix")
        assert disclosure_idx < apply_idx

    def test_inline_resident_renders_no_disclosure(self):
        f = _make_broken_up_finding(up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        assert "Fix target:" not in report
        assert "⚠️" not in report

    def test_absent_up_source_renders_no_disclosure(self):
        # Pre-032 cache shape: up_source/up_value simply absent from detail.
        f = _make_broken_up_finding()
        report = _render_report(_make_doc(findings=[f]))
        assert "Fix target:" not in report
        assert "⚠️" not in report

    def test_non_broken_up_finding_renders_no_disclosure(self):
        report = _render_report(_make_doc(findings=[_make_unparented_finding()]))
        assert "Fix target:" not in report
        assert "⚠️" not in report

    def test_inline_resident_rendering_diverges_from_absent_up_source_since_t5_2(self):
        # Superseded by spec 032 T5.2: at T5.1 landing, "today" meant the
        # absent-up_source shape (pre-032 fixtures never carried up_source at
        # all), and it rendered byte-identical to an explicit inline finding —
        # this test used to assert exactly that equality. T5.2 gives that
        # absent shape its own meaning: it IS the stale-cache case (ADR-3's
        # _MISSING sentinel — up_value key absent), withheld with a reason and
        # remedy rather than an Apply checkbox. So the two are now expected to
        # DIFFER; see TestUnroutableFindings for the withheld-path coverage,
        # and test_inline_resident_matches_pinned_golden_broken_up_line below
        # for this file's CON-7 anchor on the still-routable inline case.
        f_absent = _make_broken_up_finding("F01")
        f_inline = _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]")
        report_absent = _render_report(_make_doc(findings=[f_absent]))
        report_inline = _render_report(_make_doc(findings=[f_inline]))
        assert report_inline != report_absent
        assert "Apply — tick to apply this fix" in report_inline
        assert "Not fixable this run" in report_absent

    def test_inline_resident_matches_pinned_golden_broken_up_line(self):
        # Pins the exact pre-032 detail line (also exercised in
        # TestDirtyListReprRender) so a future change to this block cannot
        # silently alter body-resident rendering without failing here too.
        f = _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        assert "Broken `up::` → [[Deleted MOC]]" in report


# ---------------------------------------------------------------------------
# Spec 032 T5.2: unroutable findings render their reason AND remedy
# ---------------------------------------------------------------------------
# A broken_up finding garden-audit-parser.py's _route_broken_up (ADR-3/ADR-5)
# cannot route must not silently render the normal Apply-checkbox flow — the
# report has to withhold it too, so the human-reviewed report and Pass-2 agree
# about what is (un)routable. Reason detection mirrors the parser's sentinel
# logic without needing the user's remove/repoint choice, since routability
# doesn't depend on it: up_value key absent → "stale-cache" (ADR-3 _MISSING
# sentinel — this is the pre-032 cache shape, and per the measured first-run
# reality every _make_broken_up_finding() default fixture IS this shape);
# up_value present but up_source not in {"inline", "frontmatter"} →
# "no-declaration-site".
#
# no-declaration-site wording: the SDD/PRD only specify verbatim wording for
# the stale-cache remedy (solution.md UI & UX); no-declaration-site is
# documented in garden-audit-parser.py as "unreachable in practice" (a broken
# state requires a target, and a target requires a declared source) with no
# specified user-facing text. The wording below is proposed, not spec-locked —
# it reuses the /explore-vault remedy because a cache refresh is the only
# recovery lever this system offers, but it is not a verbatim string.

_STALE_CACHE_REASON_LINE = (
    "- **Not fixable this run:** the discovery cache predates property routing."
)
_STALE_CACHE_REMEDY_LINE = (
    "  Run `/explore-vault` to refresh it, then re-run the audit."
)


class TestUnroutableFindings:
    def test_stale_cache_finding_renders_verbatim_reason_and_remedy(self):
        # Pre-032 cache shape (up_source/up_value both absent) — the measured,
        # default first-run reality (346 cache entries, 0 carrying up_value).
        f = _make_broken_up_finding("F01")
        report = _render_report(_make_doc(findings=[f]))
        assert _STALE_CACHE_REASON_LINE in report
        assert _STALE_CACHE_REMEDY_LINE in report

    def test_stale_cache_finding_renders_no_apply_checkbox(self):
        f = _make_broken_up_finding("F01")
        report = _render_report(_make_doc(findings=[f]))
        # Nothing to approve — no per-finding Apply or Suggest affordance.
        assert "] Apply" not in report
        assert "Suggest targets" not in report

    def test_no_declaration_site_finding_renders_reason_and_remedy(self):
        # up_value present (not stale) but up_source absent on a broken
        # finding — "unreachable in practice" per garden-audit-parser.py,
        # still withheld rather than guessed (ADR-5), never a body-oriented
        # fallback.
        f = _make_broken_up_finding("F01", up_source=None, up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        assert "Not fixable this run" in report
        assert "/explore-vault" in report
        assert "no-declaration-site" not in report  # internal reason code, stderr-only

    def test_no_declaration_site_finding_renders_no_apply_checkbox(self):
        f = _make_broken_up_finding("F01", up_source=None, up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        assert "] Apply" not in report

    def test_map_shaped_up_value_finding_renders_reason_and_remedy(self):
        # spec 032 T3.2: a map-shaped up_value gets its OWN reason — NOT
        # stale-cache (the cache is healthy here) — and its remedy must not
        # point at /explore-vault, since a refresh cannot fix an unsupported
        # shape.
        f = _make_broken_up_finding("F01", up_source="frontmatter", up_value={"a": 1})
        report = _render_report(_make_doc(findings=[f]))
        assert "Not fixable this run" in report
        assert "unsupported-shape" not in report  # internal reason code, stderr-only

    def test_map_shaped_up_value_finding_renders_no_apply_checkbox(self):
        f = _make_broken_up_finding("F01", up_source="frontmatter", up_value={"a": 1})
        report = _render_report(_make_doc(findings=[f]))
        assert "] Apply" not in report

    def test_fully_routable_run_has_no_withheld_text_or_summary(self):
        f = _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        assert "Not fixable this run" not in report
        assert "withheld" not in report.lower()

    def test_summary_line_names_count_and_reason(self):
        findings = [
            _make_broken_up_finding("F01"),  # stale-cache (absent up_value)
            _make_broken_up_finding("F02"),  # stale-cache
        ]
        report = _render_report(_make_doc(findings=findings))
        assert "2 findings withheld" in report
        assert "/explore-vault" in report

    def test_summary_line_names_unsupported_shape_count_and_reason(self):
        findings = [
            _make_broken_up_finding(
                "F01", up_source="frontmatter", up_value={"a": 1}
            ),
            _make_broken_up_finding(
                "F02", up_source="frontmatter", up_value={"b": 2}
            ),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert "2 findings withheld" in report
        assert "unsupported value shape" in report.lower()

    def test_summary_omitted_when_nothing_withheld(self):
        f = _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        assert "withheld" not in report.lower()

    def test_summary_omitted_on_zero_findings(self):
        report = _render_report(_make_doc(findings=[]))
        assert "withheld" not in report.lower()

    def test_stderr_carries_one_prefixed_line_per_withheld_finding(self, capsys):
        findings = [
            _make_broken_up_finding("F01"),  # stale-cache — withheld
            _make_broken_up_finding(
                "F02", up_source="inline", up_value="[[Alte MOC]]"
            ),  # routable — no stderr line
        ]
        gar._log_unroutable_findings(findings)
        err = capsys.readouterr().err
        lines = [ln for ln in err.splitlines() if ln.startswith("[garden-audit]")]
        assert len(lines) == 1
        assert "F01" in lines[0]
        assert "Broken Note" in lines[0]
        assert "stale-cache" in lines[0]

    def test_routable_finding_rendering_unaffected_con7(self):
        # CON-7: a routable finding's rendering is unaffected by T5.2 — same
        # Apply checkbox and Repoint field as the pinned T5.1 golden shape.
        f = _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        assert "Apply — tick to apply this fix" in report
        assert "**Repoint to:**" in report
        assert "Not fixable this run" not in report

    def test_realistic_withheld_count_stays_readable(self):
        # Measured first-run reality: the entire population can be withheld
        # (346 cache entries, 0 carrying up_value; 29 broken_up findings).
        findings = [_make_broken_up_finding(f"F{i:02d}") for i in range(1, 30)]
        report = _render_report(_make_doc(findings=findings))
        assert report.count("Not fixable this run") == 29
        assert "29 findings withheld" in report
        # The collective summary precedes the 29 identical per-finding blocks
        # — the reader gets the remedy once, up front, not by inference.
        summary_idx = report.find("29 findings withheld")
        first_block_idx = report.find("### F01")
        assert -1 < summary_idx < first_block_idx


# ---------------------------------------------------------------------------
# Spec 032 T5.3: routing-split line (ADR-4) — once per run, the population of
# broken_up findings split by declaration site.
# ---------------------------------------------------------------------------
# Verbatim (solution.md UI & UX, ADR-4): "Broken parents: N findings — B in
# the note body, P in a note property." N is deliberately B + P, NOT the raw
# broken_up finding count: a finding whose site can't be attributed (a
# stale-cache finding predating ADR-1, or the "unreachable in practice"
# no-declaration-site branch) is excluded from this line rather than folded
# into N — a mismatched "29 findings — 0 in body, 0 in property" would be
# true, useless, and alarming (the measured first-run reality: 346 cache
# entries, 0 carrying up_value, so every one of the 29 broken_up findings is
# unattributable on the very first run this ships). Those findings are
# already covered by TestUnroutableFindings' summary — this line isn't the
# only place they're surfaced, just not the place they're double-counted.
# The line is suppressed entirely whenever B + P == 0, covering both "no
# broken_up findings at all" and "every one is unattributable."

_SPLIT_LINE = "Broken parents: {total} findings — {body} in the note body, {prop} in a note property."


class TestBrokenUpSplitLine:
    def test_mixed_body_and_property_renders_verbatim_split(self):
        findings = [
            _make_broken_up_finding("F01", up_source="inline", up_value="[[A]]"),
            _make_broken_up_finding("F02", up_source="inline", up_value="[[B]]"),
            _make_broken_up_finding("F03", up_source="inline", up_value="[[C]]"),
            _make_broken_up_finding("F04", up_source="frontmatter", up_value="[[D]]"),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert _SPLIT_LINE.format(total=4, body=3, prop=1) in report

    def test_split_line_appears_exactly_once_regardless_of_finding_count(self):
        findings = [
            _make_broken_up_finding("F01", up_source="inline", up_value="[[A]]"),
            _make_broken_up_finding("F02", up_source="inline", up_value="[[B]]"),
            _make_broken_up_finding("F03", up_source="frontmatter", up_value="[[C]]"),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert report.count("Broken parents:") == 1

    def test_only_body_resident_still_renders_with_zero_property(self):
        # A zero here must be distinguishable from "the line never renders" —
        # otherwise "no property findings" and "routing broken" look the same.
        findings = [
            _make_broken_up_finding("F01", up_source="inline", up_value="[[A]]"),
            _make_broken_up_finding("F02", up_source="inline", up_value="[[B]]"),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert _SPLIT_LINE.format(total=2, body=2, prop=0) in report

    def test_only_property_resident_still_renders_with_zero_body(self):
        findings = [
            _make_broken_up_finding("F01", up_source="frontmatter", up_value="[[A]]"),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert _SPLIT_LINE.format(total=1, body=0, prop=1) in report

    def test_no_broken_up_findings_renders_no_split_line(self):
        report = _render_report(_make_doc(findings=[_make_unparented_finding()]))
        assert "Broken parents:" not in report

    def test_zero_findings_renders_no_split_line(self):
        report = _render_report(_make_doc(findings=[]))
        assert "Broken parents:" not in report

    def test_all_findings_unattributable_renders_no_split_line(self):
        # Decision (Q2): the measured first-run reality — every broken_up
        # finding is stale-cache, site unknown for all of them. A naive
        # count-everything line would read "29 findings — 0 in the note
        # body, 0 in a note property." — true, useless, and alarming. The
        # line must not render at all in this case.
        findings = [_make_broken_up_finding(f"F{i:02d}") for i in range(1, 30)]
        report = _render_report(_make_doc(findings=findings))
        assert "Broken parents:" not in report

    def test_no_declaration_site_finding_excluded_from_split(self):
        # up_value present (not stale) but up_source not in
        # {"frontmatter", "inline"} — "unreachable in practice" per
        # garden-audit-parser.py, but still unattributable to a site.
        findings = [
            _make_broken_up_finding("F01", up_source=None, up_value="[[Alte MOC]]"),
            _make_broken_up_finding("F02", up_source="inline", up_value="[[B]]"),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert _SPLIT_LINE.format(total=1, body=1, prop=0) in report

    def test_unsupported_shape_finding_still_counted_by_site(self):
        # T3.2: a map-shaped up_value is withheld (unsupported-shape), but its
        # declaration site IS known — ADR-4 wants population visibility
        # regardless of fixability, so it must still count toward the split.
        findings = [
            _make_broken_up_finding("F01", up_source="frontmatter", up_value={"a": 1}),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert _SPLIT_LINE.format(total=1, body=0, prop=1) in report

    def test_split_line_precedes_unroutable_summary(self):
        findings = [
            _make_broken_up_finding("F01", up_source="inline", up_value="[[A]]"),
            _make_broken_up_finding("F02"),  # stale-cache — withheld
        ]
        report = _render_report(_make_doc(findings=findings))
        split_idx = report.find("Broken parents:")
        withheld_idx = report.find("withheld this run")
        assert -1 < split_idx < withheld_idx

    def test_body_resident_finding_block_unaffected_con7(self):
        # CON-7: the split line must not alter a body-resident finding's own
        # per-finding block rendering.
        findings = [
            _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]"),
            _make_broken_up_finding("F02", up_source="frontmatter", up_value="[[B]]"),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert "Broken `up::` → [[Deleted MOC]]" in report
        assert "Apply — tick to apply this fix" in report
        assert "**Repoint to:**" in report


# ---------------------------------------------------------------------------
# spec 033 T4.3 / PRD F5: the Summary states how many flagged parents fall
# into each situation (broken_up vs parent_not_moc) — a reader can triage
# without reading 42 blocks. Same trap 032's declaration-site line named:
# a breakdown that implies a division when only one situation is populated
# ("42 findings — 42 unresolved, 0 untagged parents" is true, useless, and
# alarming). Unlike that line's body/property split (a neutral routing
# fact, shown with its zero), THIS split answers "should there be some?" —
# so a populated-but-lopsided count renders as a single sentence naming
# only the situation that's actually there, never a 0-count clause.
# ---------------------------------------------------------------------------

class TestFlaggedParentSituationCounts:
    def test_both_situations_present_states_both_counts_summing_to_total(self):
        findings = [
            _make_broken_up_finding("F01", up_source="inline", up_value="[[A]]"),
            _make_broken_up_finding("F02", up_source="inline", up_value="[[B]]"),
            _make_parent_not_moc_finding("F03", up_target="X"),
            _make_parent_not_moc_finding("F04", up_target="Y"),
            _make_parent_not_moc_finding("F05", up_target="Z"),
        ]
        report = _render_report(_make_doc(findings=findings))
        line = _line_containing(report, "Flagged parents:")
        # Reconciliation, not each side alone — recompute from the findings
        # list rather than hardcoding the numbers a second time.
        broken_up_n = sum(1 for f in findings if f["check"] == "broken_up")
        parent_not_moc_n = sum(1 for f in findings if f["check"] == "parent_not_moc")
        assert str(broken_up_n + parent_not_moc_n) in line
        assert str(broken_up_n) in line
        assert str(parent_not_moc_n) in line

    def test_only_broken_up_present_names_only_that_situation(self):
        findings = [
            _make_broken_up_finding("F01", up_source="inline", up_value="[[A]]"),
            _make_broken_up_finding("F02", up_source="inline", up_value="[[B]]"),
        ]
        report = _render_report(_make_doc(findings=findings))
        line = _line_containing(report, "Flagged parents:")
        assert "not found in the audited area" in line
        assert "not yet tagged as a MOC" not in line

    def test_only_parent_not_moc_present_names_only_that_situation(self):
        findings = [_make_parent_not_moc_finding("F01", up_target="X")]
        report = _render_report(_make_doc(findings=findings))
        line = _line_containing(report, "Flagged parents:")
        assert "not yet tagged as a MOC" in line
        assert "not found in the audited area" not in line

    def test_no_flagged_parents_no_line_at_all(self):
        findings = [_make_dead_link_finding("F01"), _make_duplicate_stem_finding("F02")]
        report = _render_report(_make_doc(findings=findings))
        assert "Flagged parents:" not in report

    def test_zero_findings_no_line_at_all(self):
        report = _render_report(_make_doc(findings=[]))
        assert "Flagged parents:" not in report

    def test_declaration_site_line_says_it_counts_survivors_only(self):
        # ADR-7: 032's own line ("Broken parents: N findings — B in the note
        # body, P in a note property.") now sums to a SMALLER N than before
        # this spec, because parent_not_moc findings have left the broken_up
        # population. The line must say so, not just silently drop.
        findings = [
            _make_broken_up_finding("F01", up_source="inline", up_value="[[A]]"),
            _make_parent_not_moc_finding("F02", up_target="X"),
        ]
        report = _render_report(_make_doc(findings=findings))
        split_line = _line_containing(report, "Broken parents:")
        # The verbatim spec-032 prefix survives untouched (substring, not
        # equality) — this test only proves the NEW clause was appended.
        assert _SPLIT_LINE.format(total=1, body=1, prop=0) in split_line
        assert "untagged" in split_line.lower()


# ---------------------------------------------------------------------------
# Fix-a: property-language for the ACTION, not the FINDING (T5.1/T5.2/T5.3
# follow-up). A property-resident (up_source == "frontmatter") broken_up
# finding is fixed via a YAML-property edit — but the Fix summary line and
# the Repoint hint still described a body edit ("up::", "the broken line"),
# contradicting the property-edit disclosure rendered right below them. This
# section locks the corrected, property-aware wording for those two lines,
# and the analogous self-contradiction in the unsupported-shape remedy
# (":102" — "this note's `up::` property" says inline-marker and YAML-key in
# the same phrase).
#
# Deliberately NOT touched (per rationale in the task): the check label
# ("Broken up:: link"), the `### F<id>` heading, and the detail line
# ("Broken `up::` → [[X]]") — those name the FINDING (a broken parent link
# exists), not the fix ACTION, and the detail line is pinned by
# test_inline_resident_matches_pinned_golden_broken_up_line above.

# The heading ("Broken up:: link") and the detail line ("Broken `up::` →
# [[X]]") legitimately keep "up::" — they name the FINDING and are DO-NOT-
# CHANGE per the task rationale. So the "self-contradiction is gone" proof
# below is scoped to the specific rendered line the fix corrected (the
# "**Fix:**" line / the "**Repoint to:**" line), never to the whole report.


def _line_starting_with(report: str, prefix: str) -> str:
    for line in report.splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f"no line starting with {prefix!r} in report:\n{report}")


class TestPropertyResidentFixLanguage:
    def test_frontmatter_resident_fix_line_names_property_not_up_marker(self):
        # spec 033 T4.2 reworded this exact line's wording (ADR-6, "not found
        # in the audited area") — the string below is the CURRENT verbatim
        # text, not the pre-033 one; TestBrokenUpAuditedAreaWording covers
        # the T4.2 criteria themselves.
        f = _make_broken_up_finding(
            "F01", up_source="frontmatter", up_value=["[[Alte MOC]]"]
        )
        report = _render_report(_make_doc(findings=[f]))
        fix_line = _line_starting_with(report, "**Fix:**")
        assert fix_line == (
            "**Fix:** The broken `up` property (was [[Deleted MOC]]) — not found "
            "in the audited area. Widen the audited scope if it exists elsewhere, "
            "repoint it to a MOC you enter below, or leave empty to remove the "
            "property value."
        )
        assert "up::" not in fix_line
        assert "the broken line" not in fix_line

    def test_frontmatter_resident_fix_line_uses_derived_property_non_default_marker(
        self, tmp_path, monkeypatch
    ):
        # ADR-6 proof — a single-marker test never exposes a hardcoded "up".
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "custom.yaml").write_text(
            "relationship_defaults:\n  parent:\n    marker: \"parent::\"\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gar, "DEFAULT_PROFILES_DIR", profiles_dir)

        f = _make_broken_up_finding(
            "F01", up_source="frontmatter", up_value=["[[Alte MOC]]"]
        )
        d = _make_doc(findings=[f])
        d["profile"] = "custom"
        report = _render_report(d)
        fix_line = _line_starting_with(report, "**Fix:**")
        assert fix_line == (
            "**Fix:** The broken `parent` property (was [[Deleted MOC]]) — not "
            "found in the audited area. Widen the audited scope if it exists "
            "elsewhere, repoint it to a MOC you enter below, or leave empty to "
            "remove the property value."
        )
        assert "up" not in fix_line
        assert "`up`" not in fix_line

    def test_frontmatter_resident_repoint_hint_names_property_not_up_marker(self):
        f = _make_broken_up_finding(
            "F01", up_source="frontmatter", up_value=["[[Alte MOC]]"]
        )
        report = _render_report(_make_doc(findings=[f]))
        assert (
            "- **Repoint to:** [[]]    ← enter the correct MOC to repoint the "
            "`up` property, or leave empty to remove"
        ) in report
        # Proves discrimination: the OLD hint wording must be fully gone, not
        # just partially — a loose "in" check on a fragment shared by both
        # old and new text would pass vacuously.
        assert "repoint up::" not in report

    def test_frontmatter_resident_repoint_hint_uses_derived_property_non_default_marker(
        self, tmp_path, monkeypatch
    ):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "custom.yaml").write_text(
            "relationship_defaults:\n  parent:\n    marker: \"parent::\"\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gar, "DEFAULT_PROFILES_DIR", profiles_dir)

        f = _make_broken_up_finding(
            "F01", up_source="frontmatter", up_value=["[[Alte MOC]]"]
        )
        d = _make_doc(findings=[f])
        d["profile"] = "custom"
        report = _render_report(d)
        assert (
            "- **Repoint to:** [[]]    ← enter the correct MOC to repoint the "
            "`parent` property, or leave empty to remove"
        ) in report
        assert "`up`" not in report

    def test_inline_resident_fix_line_reworded_repoint_hint_unchanged_con7(self):
        # spec 033 T4.2 reworded the Fix line (ADR-6) for BOTH declaration
        # sites — that CON-7 guarantee (from spec 032's property-language
        # fix) covered the property-vs-up:: contradiction, not this spec's
        # deliberate audited-area rewording. What T4.2 does NOT touch is the
        # separate "**Repoint to:**" hint line — still exactly as before.
        f = _make_broken_up_finding(
            "F01", up_source="inline", up_value="[[Alte MOC]]"
        )
        report = _render_report(_make_doc(findings=[f]))
        assert (
            "**Fix:** The broken `up::` (was [[Deleted MOC]]) — not found in "
            "the audited area. Widen the audited scope if it exists elsewhere, "
            "repoint it to a MOC you enter below, or leave empty to remove the "
            "broken line."
        ) in report
        assert (
            "- **Repoint to:** [[]]    ← enter the correct MOC to repoint "
            "up::, or leave empty to remove"
        ) in report

    def test_inline_resident_report_unaffected_findings_byte_identical_con7(self):
        # spec 032's CON-7 proved this line's OLD wording survived byte-for-
        # byte through THAT fix (68c4594) — a historical fact, still true at
        # that commit, not a promise that no later spec may ever reword it.
        # spec 033 T4.2 deliberately rewords the Fix line (ADR-6) and T4.3
        # appends a clause to the declaration-site split line (ADR-7), so a
        # full-report equality assertion against the pre-033 renderer no
        # longer holds. What CON-7 protects going forward is narrower and
        # still real: OTHER findings render byte-identically, and the
        # broken_up block's own detail line / heading / Repoint hint
        # (everything except the two known, declared changes) is untouched.
        import subprocess
        import tempfile

        pre_fix_sha = "24d46d278a50b88f5b7aaaddc2c39e9e8ecd87d7"
        content = subprocess.run(
            ["git", "show", f"{pre_fix_sha}:tomo/scripts/garden-audit-render.py"],
            cwd=_ROOT, capture_output=True, check=True, text=True,
        ).stdout

        with tempfile.TemporaryDirectory() as td:
            old_path = pathlib.Path(td) / "garden_audit_render_old.py"
            old_path.write_text(content, encoding="utf-8")
            old_spec = importlib.util.spec_from_file_location(
                "garden_audit_render_old", old_path
            )
            old_gar = importlib.util.module_from_spec(old_spec)
            old_spec.loader.exec_module(old_gar)

        findings = [
            _make_broken_up_finding(
                "F01", up_source="inline", up_value="[[Alte MOC]]"
            ),
            _make_dead_link_finding("F02"),
            _make_unparented_finding("F03"),
        ]
        doc = _make_doc(findings=findings)

        old_lines = old_gar.render_report(doc).splitlines()
        new_lines = gar.render_report(doc).splitlines()

        # spec 033 T4.3 adds a "Flagged parents:" line (+ trailing blank) to
        # the Summary — this pre-033 baseline has never seen it at all, a
        # second, separately declared addition on top of T4.2's reword.
        # Identify and strip it precisely before comparing anything else.
        flagged_idx = next(
            i for i, ln in enumerate(new_lines) if ln.startswith("Flagged parents:")
        )
        assert new_lines[flagged_idx + 1] == ""
        assert "not found in the audited area" in new_lines[flagged_idx]
        stripped_new_lines = new_lines[:flagged_idx] + new_lines[flagged_idx + 2:]

        assert len(old_lines) == len(stripped_new_lines), (
            "T4.2 reworded one line's text; T4.3's addition is now stripped"
        )

        changed = [
            i for i, (o, n) in enumerate(zip(old_lines, stripped_new_lines)) if o != n
        ]
        assert changed, "the fix under test changed nothing — assertion is hollow"
        # Exactly two lines differ: the declaration-site split line (T4.3's
        # ADR-7 clause) and F01's own Fix line (T4.2's reword). Everything
        # else — F02 (dead_link) and F03 (unparented) in full, and F01's own
        # heading/detail-line/Repoint-hint — is untouched.
        assert len(changed) == 2, (
            f"expected exactly the split line and the Fix line to change, got: "
            f"{[stripped_new_lines[i] for i in changed]}"
        )
        split_idx, fix_idx = (
            (changed[0], changed[1])
            if stripped_new_lines[changed[0]].startswith("Broken parents:")
            else (changed[1], changed[0])
        )
        assert stripped_new_lines[split_idx].startswith("Broken parents:")
        assert old_lines[split_idx].startswith("Broken parents:")
        assert "untagged" in stripped_new_lines[split_idx].lower()
        assert "untagged" not in old_lines[split_idx].lower()

        assert stripped_new_lines[fix_idx].startswith("**Fix:**")
        assert old_lines[fix_idx].startswith("**Fix:**")
        assert "not found in the audited area" in stripped_new_lines[fix_idx]
        assert "not found in the audited area" not in old_lines[fix_idx]


# ---------------------------------------------------------------------------
# spec 033 T4.2 / PRD F3, ADR-6: the broken_up fix line says the target was
# not found in the audited area — never that the note is gone — and points
# at the audited scope as something the user can widen. Remove and repoint
# both remain available; this only rewords the CLAIM the line makes about
# the target, not the fix mechanism (ADR-7's routing is untouched).
# ---------------------------------------------------------------------------

class TestBrokenUpAuditedAreaWording:
    def test_body_resident_fix_line_says_not_found_in_audited_area(self):
        f = _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        fix_line = _line_starting_with(report, "**Fix:**")
        assert "not found in the audited area" in fix_line

    def test_property_resident_fix_line_says_not_found_in_audited_area(self):
        f = _make_broken_up_finding(
            "F01", up_source="frontmatter", up_value=["[[Alte MOC]]"]
        )
        report = _render_report(_make_doc(findings=[f]))
        fix_line = _line_starting_with(report, "**Fix:**")
        assert "not found in the audited area" in fix_line

    def test_fix_line_never_asserts_the_note_does_not_exist(self):
        f = _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        fix_line = _line_starting_with(report, "**Fix:**").lower()
        for forbidden in ("does not exist", "no longer exists", "was deleted", "is gone"):
            assert forbidden not in fix_line

    def test_fix_line_points_at_audited_scope_as_user_controllable(self):
        f = _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        fix_line = _line_starting_with(report, "**Fix:**").lower()
        assert "widen" in fix_line
        assert "audited scope" in fix_line

    def test_remove_and_repoint_both_still_available_body_resident(self):
        f = _make_broken_up_finding("F01", up_source="inline", up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        fix_line = _line_starting_with(report, "**Fix:**").lower()
        assert "repoint" in fix_line
        assert "remove" in fix_line
        assert "**Repoint to:**" in report  # editable field still rendered

    def test_remove_and_repoint_both_still_available_property_resident(self):
        f = _make_broken_up_finding(
            "F01", up_source="frontmatter", up_value=["[[Alte MOC]]"]
        )
        report = _render_report(_make_doc(findings=[f]))
        fix_line = _line_starting_with(report, "**Fix:**").lower()
        assert "repoint" in fix_line
        assert "remove" in fix_line
        assert "**Repoint to:**" in report

    def test_property_resident_still_carries_fix_target_disclosure_adr7(self):
        # ADR-7 regression guard: T4.2 rewords the Fix line's CLAIM but must
        # not disturb spec 032's property-edit disclosure — a successful
        # edit_frontmatter fix drops YAML comments in the property block,
        # and that cost must still be visible before Apply is ticked.
        f = _make_broken_up_finding(
            "F01", up_source="frontmatter", up_value=["[[Alte MOC]]"]
        )
        report = _render_report(_make_doc(findings=[f]))
        assert "**Fix target:** note property `up`" in report
        assert (
            "Comments inside this note's property block will not survive "
            "the edit."
        ) in report


# ---------------------------------------------------------------------------
# unsupported-shape remedy (:102) — same self-contradiction, different spot:
# "this note's `up::` property" names both the inline marker and the YAML
# key in one phrase. This reason is derived only via T3.2's map-shape check
# (never gated on up_source here — see garden-audit-render.py comment), but
# in measured practice only ever arises for a frontmatter-sourced finding.
# ---------------------------------------------------------------------------

class TestUnsupportedShapeRemedyLanguage:
    def test_remedy_no_longer_says_up_marker_and_property_together(self):
        f = _make_broken_up_finding("F01", up_source="frontmatter", up_value={"a": 1})
        report = _render_report(_make_doc(findings=[f]))
        assert "`up::` property" not in report
        assert "`up` property has a value shape" in report

    def test_remedy_property_name_is_derived_not_hardcoded(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "custom.yaml").write_text(
            "relationship_defaults:\n  parent:\n    marker: \"parent::\"\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gar, "DEFAULT_PROFILES_DIR", profiles_dir)

        f = _make_broken_up_finding("F01", up_source="frontmatter", up_value={"a": 1})
        d = _make_doc(findings=[f])
        d["profile"] = "custom"
        report = _render_report(d)
        assert "`parent` property has a value shape" in report
        assert "`up::` property" not in report
        assert "`up` property" not in report


# ---------------------------------------------------------------------------
# Fix-b (Phase 5 follow-up to 68c4594): the fourth site. 68c4594 fixed
# property-language in the **Fix:** line, the **Repoint to:** hint, and
# _UNROUTABLE_REMEDY["unsupported-shape"] (the per-finding remedy) — but
# missed _UNROUTABLE_SUMMARY_TEXT["unsupported-shape"] (the once-per-run
# Summary-section line, _render_unroutable_summary). That line still said
# "a map-shaped `up::` value" — the SAME self-contradiction 68c4594 fixed
# elsewhere (inline-marker naming + "edit the property by hand" in one
# sentence), and now inconsistent with the per-finding remedy a few lines
# below it in the SAME report.
#
# no-declaration-site's Summary text is deliberately UNCHANGED: that reason
# is not gated to frontmatter (it fires when the declaration site is
# unknown), so inline-marker naming is correct there and matches its own
# untouched per-finding remedy. Same for stale-cache (spec-locked verbatim).
# ---------------------------------------------------------------------------


def _line_containing(report: str, needle: str) -> str:
    for line in report.splitlines():
        if needle in line:
            return line
    raise AssertionError(f"no line containing {needle!r} in report:\n{report}")


class TestUnsupportedShapeSummaryLanguage:
    def test_summary_line_names_property_not_up_marker(self):
        f = _make_broken_up_finding("F01", up_source="frontmatter", up_value={"a": 1})
        report = _render_report(_make_doc(findings=[f]))
        summary_line = _line_containing(report, "unsupported value shape")
        assert "`up::`" not in summary_line
        assert "`up` property" in summary_line

    def test_summary_and_per_finding_remedy_agree_on_noun(self):
        # This is the assertion that would have caught the miss: both lines
        # describe the SAME finding and must use the same noun for it.
        f = _make_broken_up_finding("F01", up_source="frontmatter", up_value={"a": 1})
        report = _render_report(_make_doc(findings=[f]))
        summary_line = _line_containing(report, "unsupported value shape")
        remedy_line = _line_containing(report, "Not fixable this run")
        assert "`up` property" in summary_line
        assert "`up` property" in remedy_line

    def test_summary_line_uses_derived_property_non_default_marker(
        self, tmp_path, monkeypatch
    ):
        # ADR-6 proof — a single-marker test never exposes a hardcoded "up".
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "custom.yaml").write_text(
            "relationship_defaults:\n  parent:\n    marker: \"parent::\"\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gar, "DEFAULT_PROFILES_DIR", profiles_dir)

        f = _make_broken_up_finding("F01", up_source="frontmatter", up_value={"a": 1})
        d = _make_doc(findings=[f])
        d["profile"] = "custom"
        report = _render_report(d)
        summary_line = _line_containing(report, "unsupported value shape")
        assert "`parent` property" in summary_line
        assert "`up`" not in summary_line
        assert "`up::`" not in summary_line

    def test_no_declaration_site_summary_text_unchanged_verbatim(self):
        f = _make_broken_up_finding("F01", up_source=None, up_value="[[Alte MOC]]")
        report = _render_report(_make_doc(findings=[f]))
        summary_line = _line_containing(report, "no declaration site")
        assert summary_line == (
            "- 1 no declaration site — no recorded declaration site for the "
            "broken `up::`. Run `/explore-vault` to refresh the cache, then "
            "re-run the audit."
        )

    def test_stale_cache_summary_text_unchanged_verbatim(self):
        f = _make_broken_up_finding("F01")
        report = _render_report(_make_doc(findings=[f]))
        summary_line = _line_containing(report, "stale cache")
        assert summary_line == (
            "- 1 stale cache — the discovery cache predates property routing. "
            "Run `/explore-vault` to refresh it, then re-run the audit."
        )

    def test_mixed_doc_body_resident_output_byte_identical_con7(self):
        # CON-7: prove the Summary-line fix leaves a body-resident (inline
        # up_source) finding's report untouched, the way 68c4594 proved it
        # for the Fix/Repoint lines — load the module as it stood right
        # before this fix (68c4594) under a DISTINCT module name, render a
        # MIXED doc (one withheld unsupported-shape finding alongside one
        # routable inline finding) through both, and assert the inline block
        # is byte-identical while the Summary line changed.
        import subprocess
        import tempfile

        pre_fix_sha = "68c4594"
        content = subprocess.run(
            ["git", "show", f"{pre_fix_sha}:tomo/scripts/garden-audit-render.py"],
            cwd=_ROOT, capture_output=True, check=True, text=True,
        ).stdout

        with tempfile.TemporaryDirectory() as td:
            old_path = pathlib.Path(td) / "garden_audit_render_pre_phase5.py"
            old_spec = importlib.util.spec_from_file_location(
                "garden_audit_render_pre_phase5", old_path
            )
            old_path.write_text(content, encoding="utf-8")
            old_gar = importlib.util.module_from_spec(old_spec)
            old_spec.loader.exec_module(old_gar)

        findings = [
            _make_broken_up_finding(
                "F01", up_source="frontmatter", up_value={"a": 1}
            ),  # unsupported-shape — withheld, Summary line changes
            _make_broken_up_finding(
                "F02", up_source="inline", up_value="[[Alte MOC]]"
            ),  # routable — untouched by this fix
        ]
        doc = _make_doc(findings=findings)

        old_report = old_gar.render_report(doc)
        new_report = gar.render_report(doc)

        old_lines = old_report.splitlines()
        new_lines = new_report.splitlines()

        # spec 033 T4.3 adds a "Flagged parents:" line (+ trailing blank) to
        # the Summary — absent from this 68c4594 baseline entirely, a third
        # sanctioned difference alongside T4.2's Fix-line reword. Strip it
        # first so every index below lines up between old and new.
        flagged_idx = next(
            i for i, ln in enumerate(new_lines) if ln.startswith("Flagged parents:")
        )
        assert new_lines[flagged_idx + 1] == ""
        assert "not found in the audited area" in new_lines[flagged_idx]
        new_lines = new_lines[:flagged_idx] + new_lines[flagged_idx + 2:]

        assert len(old_lines) == len(new_lines)

        def _block_indices(lines, fid):
            idx, inside = [], False
            for i, ln in enumerate(lines):
                if ln.startswith("### "):
                    inside = ln.startswith(f"### {fid} ")
                if inside:
                    idx.append(i)
            return idx

        # CON-7 asserted on the thing CON-7 names: the BODY-RESIDENT finding's
        # block, byte for byte. An earlier form of this test counted changed
        # lines across the whole report and required exactly one — a proxy that
        # held only while the Summary line was the sole property-side change.
        # It then failed for a later property-side fix that CON-7 does not
        # constrain at all, so the count was tightened into the real invariant.
        #
        # spec 033 T4.2 (ADR-6) later reworded the Fix line for EVERY broken_up
        # finding, body-resident included — a separate, deliberate change this
        # test does not own. So F02's block is no longer fully byte-identical
        # to 68c4594; what CON-7 still protects here is everything about F02
        # EXCEPT its own Fix line (heading, detail line, checkbox, Repoint
        # hint, Suggest opt-in).
        f02_old = _block_indices(old_lines, "F02")
        f02_new = _block_indices(new_lines, "F02")
        assert f02_old == f02_new

        f02_fix_positions = [i for i in f02_old if old_lines[i].startswith("**Fix:**")]
        assert len(f02_fix_positions) == 1
        f02_fix_idx = f02_fix_positions[0]

        f02_rest_old = [old_lines[i] for i in f02_old if i != f02_fix_idx]
        f02_rest_new = [new_lines[i] for i in f02_new if i != f02_fix_idx]
        assert f02_rest_old == f02_rest_new

        changed = [
            i for i, (o, n) in enumerate(zip(old_lines, new_lines)) if o != n
        ]
        assert changed, "the fix under test changed nothing — assertion is hollow"
        # Body-resident lines changed ONLY at F02's own Fix line — T4.2's
        # known, separate rewording, not a regression in the
        # unsupported-shape summary fix this test exists to prove.
        body_resident = set(f02_new) & set(changed)
        assert body_resident == {f02_fix_idx}, (
            f"body-resident lines changed beyond the known T4.2 Fix-line "
            f"rewording: {[new_lines[i] for i in sorted(body_resident - {f02_fix_idx})]}"
        )
        assert "not found in the audited area" in new_lines[f02_fix_idx]
        assert "not found in the audited area" not in old_lines[f02_fix_idx]

        summary = [i for i in changed if "unsupported value shape" in new_lines[i]]
        assert len(summary) == 1, f"expected one Summary line, got {summary}"
        assert "unsupported value shape" in old_lines[summary[0]]


class TestPropertyResidentDetailLine:
    """The per-finding detail line must not say `up::` for a parent that lives
    in a YAML property — the block already says "note property `up`" two lines
    below, and the two readings contradict each other in the same block.

    Scoped deliberately to the detail line: the section heading comes from a
    static per-check label shared by all broken_up findings and is a separate
    change.
    """

    def test_frontmatter_resident_detail_line_names_property_not_up_marker(self):
        f = _make_broken_up_finding(
            "F01", up_source="frontmatter", up_value=["[[Alte MOC]]"]
        )
        report = _render_report(_make_doc(findings=[f]))
        detail_line = _line_starting_with(report, "Broken `")
        assert detail_line == "Broken `up` property → [[Deleted MOC]]"
        assert "up::" not in detail_line

    def test_frontmatter_resident_detail_line_uses_derived_property(
        self, tmp_path, monkeypatch
    ):
        # ADR-6 proof — a single-marker test never exposes a hardcoded "up".
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "custom.yaml").write_text(
            "relationship_defaults:\n  parent:\n    marker: \"parent::\"\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gar, "DEFAULT_PROFILES_DIR", profiles_dir)

        f = _make_broken_up_finding(
            "F01", up_source="frontmatter", up_value=["[[Alte MOC]]"]
        )
        d = _make_doc(findings=[f])
        d["profile"] = "custom"
        report = _render_report(d)
        detail_line = _line_starting_with(report, "Broken `")
        assert detail_line == "Broken `parent` property → [[Deleted MOC]]"

    def test_body_resident_detail_line_is_unchanged(self):
        # CON-7: body-resident output stays byte-identical.
        f = _make_broken_up_finding("F01", up_source="inline", up_value=None)
        report = _render_report(_make_doc(findings=[f]))
        detail_line = _line_starting_with(report, "Broken `")
        assert detail_line == "Broken `up::` → [[Deleted MOC]]"

    def test_block_does_not_state_both_readings_for_one_finding(self):
        """The contradiction itself, asserted as one property of the block:
        below the heading, a property-resident finding never names `up::`.
        """
        f = _make_broken_up_finding(
            "F01", up_source="frontmatter", up_value=["[[Alte MOC]]"]
        )
        report = _render_report(_make_doc(findings=[f]))
        body = [
            ln for ln in report.splitlines()
            if ln.strip() and not ln.startswith("###")
        ]
        offenders = [ln for ln in body if "up::" in ln]
        assert offenders == [], f"body syntax on a property finding: {offenders}"


# ---------------------------------------------------------------------------
# spec 033 T4.1 — parent_not_moc advisory message names the target and
# inverts the suggestion (ADR-5). A per-check advisory table replaces the
# single generic literal for this check only; duplicate_stem/stale_moc must
# keep getting the untouched fallback line (CON-3).
# ---------------------------------------------------------------------------

class TestParentNotMocAdvisoryMessageGroupSizeOne:
    def test_message_names_target_before_asserting_forbidden_words_absent(self):
        f = _make_parent_not_moc_finding("F01", up_target="Real Note")
        report = _render_report(_make_doc(findings=[f]))
        advisory_line = _line_containing(report, "Real Note")
        # Target name present FIRST — a bare negative check passes trivially
        # against an empty/unrelated block.
        assert "[[Real Note]]" in advisory_line
        assert "broken" not in advisory_line
        assert "remove" not in advisory_line

    def test_no_checkbox_or_repoint_field(self):
        # Scoped to the finding's own block (after its ### heading) — the
        # report's top-level "- [ ] Approved" gate is unrelated and always
        # present, so checking the whole report would be a false positive.
        f = _make_parent_not_moc_finding("F01")
        report = _render_report(_make_doc(findings=[f]))
        heading_idx = next(
            i for i, ln in enumerate(report.splitlines()) if ln.startswith("### F01")
        )
        block = "\n".join(report.splitlines()[heading_idx:])
        assert "- [ ]" not in block
        assert "Repoint to:" not in block

    def test_group_size_one_carries_no_findings_count_clause(self):
        f = _make_parent_not_moc_finding("F01", up_target="Solo Target")
        report = _render_report(_make_doc(findings=[f]))
        advisory_line = _line_containing(report, "Solo Target")
        assert "findings in this report" not in advisory_line
        assert "resolves" not in advisory_line


class TestParentNotMocAdvisoryMessageGroupSizeMany:
    def test_group_size_two_says_resolves_both_not_resolves_all_two(self):
        findings = [
            _make_parent_not_moc_finding("F01", up_target="Pair"),
            _make_parent_not_moc_finding("F02", up_target="Pair"),
        ]
        report = _render_report(_make_doc(findings=findings))
        line = _line_containing(report, "[[Pair]] is a real note")
        assert "[[Pair]]" in line
        assert "resolves both" in line
        assert "resolves all 2" not in line

    def test_group_size_three_says_resolves_all_n(self):
        findings = [
            _make_parent_not_moc_finding(f"F0{i}", up_target="Trio") for i in range(1, 4)
        ]
        report = _render_report(_make_doc(findings=findings))
        line = _line_containing(report, "[[Trio]] is a real note")
        assert "3 findings in this report point at [[Trio]]" in line
        assert "resolves all 3" in line

    def test_count_clause_applies_to_every_group_member_not_just_one(self):
        findings = [
            _make_parent_not_moc_finding(f"F{i:02d}", up_target="Group") for i in range(1, 4)
        ]
        report = _render_report(_make_doc(findings=findings))
        matches = [ln for ln in report.splitlines() if "resolves all 3" in ln]
        assert len(matches) == 3, "every finding sharing the target must carry the clause"

    def test_count_clause_points_at_untagged_parents_block(self):
        findings = [
            _make_parent_not_moc_finding("F01", up_target="Shared"),
            _make_parent_not_moc_finding("F02", up_target="Shared"),
        ]
        report = _render_report(_make_doc(findings=findings))
        line = _line_containing(report, "[[Shared]] is a real note")
        assert '"Untagged parents"' in line


class TestUntaggedParentsBlockSuppression:
    """Suppression is its own test — a renderer that always emits the block
    would pass every shared-target assertion above."""

    def test_block_absent_when_no_finding_exists(self):
        report = _render_report(_make_doc(findings=[]))
        assert "Untagged parents" not in report

    def test_block_absent_when_every_target_is_unique(self):
        findings = [
            _make_parent_not_moc_finding("F01", up_target="Projects"),
            _make_parent_not_moc_finding("F02", up_target="Ideas"),
            _make_parent_not_moc_finding("F03", up_target="Archive"),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert "Untagged parents" not in report

    def test_block_absent_for_non_parent_not_moc_advisories(self):
        findings = [
            _make_duplicate_stem_finding("F01"),
            _make_stale_moc_finding("F02"),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert "Untagged parents" not in report


class TestUntaggedParentsBlockContent:
    def test_block_renders_when_a_target_is_shared(self):
        findings = [
            _make_parent_not_moc_finding("F12", up_target="Projects"),
            _make_parent_not_moc_finding("F15", up_target="Projects"),
            _make_parent_not_moc_finding("F19", up_target="Projects"),
        ]
        report = _render_report(_make_doc(findings=findings))
        assert "**Untagged parents" in report
        assert "[[Projects]]" in report

    def test_per_target_counts_agree_with_actual_finding_count(self):
        # Reconciliation, not each side alone: recompute expected counts from
        # the findings list itself rather than hardcoding them a second time.
        findings = [
            _make_parent_not_moc_finding("F01", up_target="Projects"),
            _make_parent_not_moc_finding("F02", up_target="Projects"),
            _make_parent_not_moc_finding("F03", up_target="Projects"),
            _make_parent_not_moc_finding("F04", up_target="Ideas"),
            _make_parent_not_moc_finding("F05", up_target="Ideas"),
        ]
        report = _render_report(_make_doc(findings=findings))
        projects_count = sum(
            1 for f in findings if f["detail"]["up_target"] == "Projects"
        )
        ideas_count = sum(1 for f in findings if f["detail"]["up_target"] == "Ideas")

        projects_line = _line_containing(report, "[[Projects]] —")
        ideas_line = _line_containing(report, "[[Ideas]] —")
        assert f"{projects_count} findings" in projects_line
        assert f"{ideas_count} findings" in ideas_line

        header_line = _line_starting_with(report, "**Untagged parents")
        assert "2 targets" in header_line
        assert f"{projects_count + ideas_count} findings" in header_line

    def test_reuses_each_findings_own_id_verbatim_never_recomputed(self):
        # F01 is an unrelated fixable finding ahead of the group in the list,
        # and the group's own ids (F12/F15/F19) are deliberately non-sequential
        # — a recomputed index would land on F01/F02/F03 instead.
        findings = [
            _make_broken_up_finding("F01"),
            _make_parent_not_moc_finding("F12", up_target="Projects"),
            _make_parent_not_moc_finding("F15", up_target="Projects"),
            _make_parent_not_moc_finding("F19", up_target="Projects"),
        ]
        report = _render_report(_make_doc(findings=findings))
        block_line = _line_containing(report, "[[Projects]] —")
        assert "F12" in block_line
        assert "F15" in block_line
        assert "F19" in block_line
        assert "F02" not in block_line
        assert "F03" not in block_line

    def test_row_order_follows_findings_order_not_alphabetical(self):
        # Row order is deterministic by construction — one ordered pass over
        # findings, with dict insertion order preserved through the filter
        # and the render loop — but nothing asserted it before this test. A
        # user keeping these reports in a vault gets diff noise on every run
        # if that order ever starts depending on something other than
        # encounter order (e.g. alphabetical sorting creeping in later).
        # "Zebra" appears first in findings but sorts AFTER "Apple" — the two
        # orderings disagree here, so this actually distinguishes them.
        findings = [
            _make_parent_not_moc_finding("F01", up_target="Zebra"),
            _make_parent_not_moc_finding("F02", up_target="Zebra"),
            _make_parent_not_moc_finding("F03", up_target="Apple"),
            _make_parent_not_moc_finding("F04", up_target="Apple"),
        ]
        report = _render_report(_make_doc(findings=findings))
        zebra_idx = report.index("[[Zebra]] —")
        apple_idx = report.index("[[Apple]] —")
        assert zebra_idx < apple_idx


class TestUntaggedParentsMissingTarget:
    def test_missing_up_target_does_not_crash_and_forms_no_group(self):
        f_missing = _make_parent_not_moc_finding("F01")
        del f_missing["detail"]["up_target"]
        f_empty = _make_parent_not_moc_finding("F02")
        f_empty["detail"]["up_target"] = ""
        report = _render_report(_make_doc(findings=[f_missing, f_empty]))  # must not raise
        assert "Untagged parents" not in report

    def test_missing_up_target_advisory_line_still_renders(self):
        f_missing = _make_parent_not_moc_finding("F01")
        del f_missing["detail"]["up_target"]
        report = _render_report(_make_doc(findings=[f_missing]))
        assert "### F01" in report


class TestAdvisoryFallbackByteIdenticalCon3:
    """CON-3: the per-check advisory table must fall back to today's exact
    literal line for every check that isn't parent_not_moc."""

    def test_duplicate_stem_and_stale_moc_line_unchanged(self):
        findings = [
            _make_duplicate_stem_finding("F01"),
            _make_stale_moc_finding("F02"),
        ]
        report = _render_report(_make_doc(findings=findings))
        advisory_lines = [
            ln for ln in report.splitlines() if ln.startswith("_Advisory")
        ]
        assert advisory_lines == [
            "_Advisory — no automated fix. Review and handle manually._",
            "_Advisory — no automated fix. Review and handle manually._",
        ]

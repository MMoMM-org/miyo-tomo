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
        findings = [_make_broken_up_finding()]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        assert "- [" in report  # checkbox pattern

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

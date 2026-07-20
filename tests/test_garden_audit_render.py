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
# version: 0.1.0
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


def _make_broken_up_finding(fid: str = "F02") -> dict:
    return {
        "id": fid,
        "check": "broken_up",
        "tier": "integrity",
        "fixable": True,
        "target": {"path": "Notes/Broken Note.md", "stem": "Broken Note"},
        "detail": {"up_target": "Deleted MOC"},
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _make_dead_link_finding(fid: str = "F03") -> dict:
    return {
        "id": fid,
        "check": "dead_link",
        "tier": "integrity",
        "fixable": True,
        "target": {"path": "Notes/Source Note.md", "stem": "Source Note"},
        "detail": {"dead_target": "[[Missing Note]]", "count": 2},
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
        # decision.selected=True → pre-checked box
        findings = [_make_broken_up_finding()]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        assert "- [x]" in report

    def test_advisory_finding_no_checkbox(self):
        findings = [_make_duplicate_stem_finding()]
        d = _make_doc(findings=findings)
        report = _render_report(d)
        # Advisory findings carry no checkbox
        assert "- [" not in report

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
        import os

        # Reload doc_frontmatter with TOMO_SCHEMA_STRICT=1 in effect
        import sys as _sys

        # Temporarily set the env var and force a fresh import of doc_frontmatter
        old = os.environ.get("TOMO_SCHEMA_STRICT")
        os.environ["TOMO_SCHEMA_STRICT"] = "1"
        try:
            # Remove cached module so it reloads with strict flag active
            mod_name = "lib.doc_frontmatter"
            if mod_name in _sys.modules:
                del _sys.modules[mod_name]
            from lib.doc_frontmatter import build_tomo_block as _btb
            # Must not raise
            block = _btb(doc_type="garden-audit", state="pending-accept", run_id="r-test")
            assert block["doc_type"] == "garden-audit"
            assert block["state"] == "pending-accept"
        finally:
            if old is None:
                os.environ.pop("TOMO_SCHEMA_STRICT", None)
            else:
                os.environ["TOMO_SCHEMA_STRICT"] = old
            # Restore module cache
            if mod_name in _sys.modules:
                del _sys.modules[mod_name]

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
        assert "- [" not in report

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

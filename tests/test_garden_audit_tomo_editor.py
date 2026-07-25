#!/usr/bin/env python3
# version: 0.3.0
"""test_garden_audit_tomo_editor.py — spec 030 Tomo-Editor wire channel.

Covers the additive wire decision fields (file_under, candidates, suggest_requested),
the top-level JSON-side `approved` gate, the apply-decision-only change-detection
digest (candidates/suggest_requested/approved excluded), --suggest writing
candidates into the wire and reading suggest_requested, build_from_wire reading
file_under, inbox-triage gating on wire.approved OR markdown Approved, the
approved-forces-JSON-path edge, and schema validation of the real fixture.

Deliverables A–F of the 2026-07-22 Hashi handoff-back, plus Deliverable G
(2026-07-23 handoff): the decision.suggested ran-marker — pending vs ran-and-empty
distinguishable, idempotent clearing, digest exclusion, schema validation.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "tomo" / "scripts"
SCHEMA = REPO / "tomo" / "schemas" / "garden-audit-wire.schema.json"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gar = _load("garden_audit_render", SCRIPTS / "garden-audit-render.py")
gap = _load("garden_audit_parser", SCRIPTS / "garden-audit-parser.py")
gas = _load("garden_audit_suggest", SCRIPTS / "garden-audit-suggest.py")
from lib.render_md import (  # noqa: E402
    compute_garden_audit_digest,
    compute_payload_digest,
)


# ── Doc builders ──────────────────────────────────────────────────────────────

def _doc(findings):
    return {
        "run_id": "run-editor-001",
        "generated": "2026-07-22T12:00:00Z",
        "profile": "miyo",
        "findings": findings,
    }


def _dead_link(fid="F01"):
    return {
        "id": fid, "check": "dead_link", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Src.md", "stem": "Src"},
        "detail": {"dead_target": "Missing Note", "count": 1},
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _broken_up(fid="F02"):
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Child.md", "stem": "Child"},
        "detail": {"up_target": "Deleted MOC"},
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _orphan(fid="F03", candidate=True):
    detail = {"candidate_mocs": [{"target_moc": "MOCs/Writing MOC.md", "score": 0.8}]} \
        if candidate else {"candidate_mocs": []}
    return {
        "id": fid, "check": "orphan", "tier": "structure", "fixable": True,
        "target": {"path": "Notes/Orphan.md", "stem": "Orphan"},
        "detail": detail,
        "decision": {"selected": True, "action": "link_to_moc"},
    }


def _advisory(fid="F09"):
    return {
        "id": fid, "check": "stale_moc", "tier": "advisory", "fixable": False,
        "target": {"path": "MOCs/Old.md", "stem": "Old"},
        "detail": {"mtime": "2026-01-01T00:00:00Z"},
    }


# ── Deliverable A: additive wire fields default-emitted ───────────────────────

class TestAdditiveFieldsDefaults:
    def test_dead_link_decision_has_new_fields(self):
        wire = gar.build_wire_payload(_doc([_dead_link()]))
        dec = wire["findings"][0]["decision"]
        assert dec["replace"] == ""
        assert dec["candidates"] == []
        assert dec["suggest_requested"] is False

    def test_broken_up_decision_has_new_fields(self):
        wire = gar.build_wire_payload(_doc([_broken_up()]))
        dec = wire["findings"][0]["decision"]
        assert dec["repoint"] == ""
        assert dec["candidates"] == []
        assert dec["suggest_requested"] is False

    def test_orphan_decision_has_file_under(self):
        wire = gar.build_wire_payload(_doc([_orphan()]))
        dec = wire["findings"][0]["decision"]
        assert dec["file_under"] == ""
        assert dec["candidates"] == []
        assert dec["suggest_requested"] is False

    def test_top_level_approved_defaults_false(self):
        wire = gar.build_wire_payload(_doc([_dead_link()]))
        assert wire["approved"] is False

    def test_top_level_approved_reflects_doc(self):
        doc = _doc([_dead_link()])
        doc["approved"] = True
        wire = gar.build_wire_payload(doc)
        assert wire["approved"] is True

    def test_advisory_finding_has_no_decision(self):
        wire = gar.build_wire_payload(_doc([_advisory()]))
        assert "decision" not in wire["findings"][0]


# ── Deliverable B: apply-decision-only digest ─────────────────────────────────

class TestChangeDetectionDigest:
    def test_candidates_excluded_from_digest(self):
        wire = gar.build_wire_payload(_doc([_orphan()]))
        base = wire["emit_digest"]
        # Tomo writes display-only candidates — must NOT flip the digest.
        wire["findings"][0]["decision"]["candidates"] = [
            {"stem": "MOCs/Writing MOC", "score": 0.9}
        ]
        assert compute_garden_audit_digest(wire) == base

    def test_suggest_requested_excluded_from_digest(self):
        wire = gar.build_wire_payload(_doc([_orphan()]))
        base = wire["emit_digest"]
        wire["findings"][0]["decision"]["suggest_requested"] = True
        assert compute_garden_audit_digest(wire) == base

    def test_approved_excluded_from_digest(self):
        wire = gar.build_wire_payload(_doc([_orphan()]))
        base = wire["emit_digest"]
        wire["approved"] = True
        assert compute_garden_audit_digest(wire) == base

    def test_detail_excluded_from_digest(self):
        wire = gar.build_wire_payload(_doc([_dead_link()]))
        base = wire["emit_digest"]
        wire["findings"][0]["detail"]["count"] = 999
        assert compute_garden_audit_digest(wire) == base

    def test_selected_flips_digest(self):
        wire = gar.build_wire_payload(_doc([_orphan()]))
        base = wire["emit_digest"]
        wire["findings"][0]["decision"]["selected"] = False
        assert compute_garden_audit_digest(wire) != base

    def test_replace_flips_digest(self):
        wire = gar.build_wire_payload(_doc([_dead_link()]))
        base = wire["emit_digest"]
        wire["findings"][0]["decision"]["replace"] = "[[New]]"
        assert compute_garden_audit_digest(wire) != base

    def test_repoint_flips_digest(self):
        wire = gar.build_wire_payload(_doc([_broken_up()]))
        base = wire["emit_digest"]
        wire["findings"][0]["decision"]["repoint"] = "[[Correct MOC]]"
        assert compute_garden_audit_digest(wire) != base

    def test_file_under_flips_digest(self):
        wire = gar.build_wire_payload(_doc([_orphan()]))
        base = wire["emit_digest"]
        wire["findings"][0]["decision"]["file_under"] = "[[000 Home MOC]]"
        assert compute_garden_audit_digest(wire) != base

    def test_is_wire_edited_false_when_only_candidates_added(self):
        wire = gar.build_wire_payload(_doc([_orphan()]))
        wire["findings"][0]["decision"]["candidates"] = [
            {"stem": "MOCs/Writing MOC", "score": 0.9}
        ]
        # emit_digest unchanged (candidates excluded) → not edited.
        assert gap._is_wire_edited(wire) is False

    def test_is_wire_edited_true_when_file_under_changed(self):
        wire = gar.build_wire_payload(_doc([_orphan()]))
        wire["findings"][0]["decision"]["file_under"] = "[[000 Home MOC]]"
        assert gap._is_wire_edited(wire) is True


class TestSuggestionsWireDigestUnaffected:
    """The suggestions wire uses compute_payload_digest — provably unchanged."""

    def test_suggestions_digest_hashes_whole_editable_payload(self):
        # A suggestions-style payload: adding any top-level field flips the
        # whole-payload digest — proving compute_payload_digest still hashes
        # everything (unlike the garden-audit apply-only digest).
        payload = {"schema_version": "1", "suggestions": [{"stem": "A"}]}
        base = compute_payload_digest(payload)
        payload["suggestions"][0]["note"] = "x"
        assert compute_payload_digest(payload) != base

    def test_garden_digest_differs_from_payload_digest(self):
        # The two functions are genuinely different — a candidates change moves
        # the whole-payload digest but not the apply-only digest.
        wire = gar.build_wire_payload(_doc([_orphan()]))
        wire["findings"][0]["decision"]["candidates"] = [{"stem": "X", "score": 1.0}]
        assert compute_payload_digest(wire) != wire["emit_digest"]
        assert compute_garden_audit_digest(wire) == wire["emit_digest"]


# ── Deliverable C: --suggest writes candidates + reads suggest_requested ───────

_CACHE = {
    "entries": [
        {"kind": "note", "stem": "Missing Notes"},
        {"kind": "note", "stem": "Missing Memo"},
        {"kind": "moc", "stem": "Writing MOC", "path": "MOCs/Writing MOC.md",
         "topics": ["writing"]},
    ]
}


def _write_pair(tmp_path, doc):
    report = "\n".join(gar.render_frontmatter(doc)) + "\n" + gar.render_report(doc)
    wire = gar.build_wire_payload(doc)
    rp = tmp_path / "report.md"
    wp = tmp_path / "report.json"
    cp = tmp_path / "cache.yaml"
    rp.write_text(report, encoding="utf-8")
    wp.write_text(json.dumps(wire), encoding="utf-8")
    import yaml
    cp.write_text(yaml.safe_dump(_CACHE), encoding="utf-8")
    return rp, wp, cp


class TestSuggestWritesWireCandidates:
    def test_markdown_suggest_tick_writes_wire_candidates(self, tmp_path):
        doc = _doc([_dead_link("F01")])
        rp, wp, cp = _write_pair(tmp_path, doc)
        # Tick "Suggest targets" in the markdown (human channel).
        md = rp.read_text(encoding="utf-8").replace(
            "- [ ] Suggest targets", "- [x] Suggest targets"
        )
        rp.write_text(md, encoding="utf-8")
        _report, wire, _n, _m = gas.run_suggest(str(rp), str(wp), str(cp))
        cands = wire["findings"][0]["decision"]["candidates"]
        assert cands, "expected candidates written into the wire"
        assert all(set(c) == {"stem", "score"} for c in cands)
        assert "Missing Notes" in {c["stem"] for c in cands}

    def test_wire_suggest_requested_drives_enrichment(self, tmp_path):
        doc = _doc([_dead_link("F01")])
        rp, wp, cp = _write_pair(tmp_path, doc)
        # NO markdown tick — instead set the wire's suggest_requested (editor channel).
        wire_in = json.loads(wp.read_text(encoding="utf-8"))
        wire_in["findings"][0]["decision"]["suggest_requested"] = True
        wp.write_text(json.dumps(wire_in), encoding="utf-8")
        _report, wire, _n, _m = gas.run_suggest(str(rp), str(wp), str(cp))
        cands = wire["findings"][0]["decision"]["candidates"]
        assert cands, "wire suggest_requested must drive enrichment"

    def test_suggest_does_not_make_wire_look_edited(self, tmp_path):
        doc = _doc([_dead_link("F01")])
        rp, wp, cp = _write_pair(tmp_path, doc)
        md = rp.read_text(encoding="utf-8").replace(
            "- [ ] Suggest targets", "- [x] Suggest targets"
        )
        rp.write_text(md, encoding="utf-8")
        _report, wire, _n, _m = gas.run_suggest(str(rp), str(wp), str(cp))
        # Baseline emit_digest is preserved (candidates excluded) → not edited.
        assert gap._is_wire_edited(wire) is False
        assert wire["emit_digest"] == compute_garden_audit_digest(wire)

    def test_pre_edited_wire_survives_suggest(self, tmp_path):
        # Regression (C-1): a user edits an apply-decision (file_under) in the
        # editor BEFORE running --suggest. --suggest must NOT re-stamp emit_digest
        # to the edited state, which would make _is_wire_edited read False and
        # SILENTLY DISCARD the user's decision. The pre-edit must survive.
        doc = _doc([_orphan("F01", candidate=True)])
        report = "\n".join(gar.render_frontmatter(doc)) + "\n" + gar.render_report(doc)
        wire = gar.build_wire_payload(doc)
        # User apply-edit committed into the wire (Hashi's channel).
        wire["findings"][0]["decision"]["file_under"] = "[[My MOC]]"
        rp = tmp_path / "report.md"
        wp = tmp_path / "report.json"
        cp = tmp_path / "cache.yaml"
        # Tick Suggest in the markdown so --suggest runs the enrichment path.
        rp.write_text(
            report.replace("- [ ] Suggest targets", "- [x] Suggest targets"),
            encoding="utf-8",
        )
        wp.write_text(json.dumps(wire), encoding="utf-8")
        import yaml
        cp.write_text(yaml.safe_dump(_CACHE), encoding="utf-8")

        _report, out_wire, _n, _m = gas.run_suggest(str(rp), str(wp), str(cp))

        # (a) the wire still reads as edited (baseline digest mismatch preserved),
        assert gap._is_wire_edited(out_wire) is True
        # (b) the user's file_under value is intact,
        assert out_wire["findings"][0]["decision"]["file_under"] == "[[My MOC]]"
        # (c) build_from_wire honours the user's chosen MOC.
        result = gap.build_from_wire(out_wire)
        assert result["confirmed_items"][0]["target_moc"] == "My MOC"

    def test_unrequested_finding_candidates_stay_empty(self, tmp_path):
        doc = _doc([_dead_link("F01"), _dead_link("F02")])
        rp, wp, cp = _write_pair(tmp_path, doc)
        # Tick only F01.
        lines = rp.read_text(encoding="utf-8").splitlines()
        out, ticked_f01 = [], False
        for ln in lines:
            if ln.startswith("### F01"):
                ticked_f01 = True
            if ln.startswith("### F02"):
                ticked_f01 = False
            if ticked_f01 and ln.strip().startswith("- [ ] Suggest targets"):
                ln = ln.replace("- [ ] Suggest targets", "- [x] Suggest targets")
            out.append(ln)
        rp.write_text("\n".join(out), encoding="utf-8")
        _report, wire, _n, _m = gas.run_suggest(str(rp), str(wp), str(cp))
        by_id = {f["id"]: f for f in wire["findings"]}
        assert by_id["F01"]["decision"]["candidates"]
        assert by_id["F02"]["decision"]["candidates"] == []


# ── Deliverable G (2026-07-23 Hashi handoff): suggested ran-marker ────────────

class TestSuggestPendingMarker:
    """Top-level suggest_pending gate (2026-07-24): Hashi blocks approve while
    true; Tomo initialises false at render and clears it after --suggest."""

    def test_render_suggest_pending_false(self):
        wire = gar.build_wire_payload(_doc([_dead_link("F01")]))
        assert wire["suggest_pending"] is False

    def test_helper_true_when_requested_not_suggested(self):
        wire = gar.build_wire_payload(_doc([_dead_link("F01")]))
        # Editor requests candidates (no run yet) → pending.
        wire["findings"][0]["decision"]["suggest_requested"] = True
        assert gar._wire_suggest_pending(wire["findings"]) is True

    def test_enrich_clears_suggest_pending(self, tmp_path):
        doc = _doc([_dead_link("F01")])
        rp, wp, cp = _write_pair(tmp_path, doc)
        wire_in = json.loads(wp.read_text(encoding="utf-8"))
        wire_in["findings"][0]["decision"]["suggest_requested"] = True
        wire_in["suggest_pending"] = True  # editor set it on the request
        wp.write_text(json.dumps(wire_in), encoding="utf-8")
        _report, wire, _n, _m = gas.run_suggest(str(rp), str(wp), str(cp))
        # --suggest stamped `suggested` → nothing left pending.
        assert wire["suggest_pending"] is False

    def test_suggest_pending_excluded_from_digest(self):
        wire = gar.build_wire_payload(_doc([_dead_link("F01")]))
        base = wire["emit_digest"]
        wire["suggest_pending"] = True
        assert compute_garden_audit_digest(wire) == base
        assert gap._is_wire_edited(wire) is False

    def test_wire_with_suggest_pending_validates(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        wire = gar.build_wire_payload(_doc([_dead_link("F01")]))
        wire["suggest_pending"] = True
        jsonschema.validate(instance=wire, schema=schema)


class TestSuggestedMarker:
    def test_markdown_tick_stamps_suggested(self, tmp_path):
        doc = _doc([_dead_link("F01")])
        rp, wp, cp = _write_pair(tmp_path, doc)
        md = rp.read_text(encoding="utf-8").replace(
            "- [ ] Suggest targets", "- [x] Suggest targets"
        )
        rp.write_text(md, encoding="utf-8")
        _report, wire, n, m = gas.run_suggest(str(rp), str(wp), str(cp))
        assert wire["findings"][0]["decision"]["suggested"] is True
        assert (n, m) == (1, 1)

    def test_wire_suggest_requested_stamps_suggested(self, tmp_path):
        doc = _doc([_dead_link("F01")])
        rp, wp, cp = _write_pair(tmp_path, doc)
        wire_in = json.loads(wp.read_text(encoding="utf-8"))
        wire_in["findings"][0]["decision"]["suggest_requested"] = True
        wp.write_text(json.dumps(wire_in), encoding="utf-8")
        _report, wire, n, _m = gas.run_suggest(str(rp), str(wp), str(cp))
        assert wire["findings"][0]["decision"]["suggested"] is True
        assert n == 1

    def test_ran_and_empty_distinguishable_from_pending(self, tmp_path):
        # THE Hashi Gap-A case: a requested finding whose run returned zero
        # candidates must NOT be wire-identical to one still awaiting a run.
        doc = _doc([_dead_link("F01")])
        rp, wp, cp = _write_pair(tmp_path, doc)
        cp.write_text("entries: []\n", encoding="utf-8")  # nothing clears the cutoff
        wire_in = json.loads(wp.read_text(encoding="utf-8"))
        wire_in["findings"][0]["decision"]["suggest_requested"] = True
        wp.write_text(json.dumps(wire_in), encoding="utf-8")
        _report, wire, n, m = gas.run_suggest(str(rp), str(wp), str(cp))
        dec = wire["findings"][0]["decision"]
        assert dec["suggested"] is True  # ran…
        assert dec["candidates"] == []   # …and came back empty
        assert dec["suggest_requested"] is True  # request flag untouched
        assert (n, m) == (1, 0)  # processed, zero with candidates — still a run

    def test_unrequested_rerun_clears_suggested(self, tmp_path):
        # Round 1: F01 ticked → suggested stamped. Round 2: tick removed →
        # suggested cleared + candidates emptied (default state restored).
        doc = _doc([_dead_link("F01")])
        rp, wp, cp = _write_pair(tmp_path, doc)
        plain_md = rp.read_text(encoding="utf-8")
        rp.write_text(
            plain_md.replace("- [ ] Suggest targets", "- [x] Suggest targets"),
            encoding="utf-8",
        )
        _r1, wire1, n1, _m1 = gas.run_suggest(str(rp), str(wp), str(cp))
        assert wire1["findings"][0]["decision"]["suggested"] is True
        assert n1 == 1
        # Round 2 on round-1's wire, with the tick removed.
        rp.write_text(plain_md, encoding="utf-8")
        wp.write_text(json.dumps(wire1), encoding="utf-8")
        _r2, wire2, n2, _m2 = gas.run_suggest(str(rp), str(wp), str(cp))
        dec = wire2["findings"][0]["decision"]
        assert "suggested" not in dec
        assert dec["candidates"] == []
        assert n2 == 0

    def test_suggested_excluded_from_digest(self):
        wire = gar.build_wire_payload(_doc([_orphan()]))
        base = wire["emit_digest"]
        wire["findings"][0]["decision"]["suggested"] = True
        assert compute_garden_audit_digest(wire) == base
        assert gap._is_wire_edited(wire) is False

    def test_wire_with_suggested_validates_against_schema(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        wire = gar.build_wire_payload(_doc([_dead_link("F01")]))
        wire["findings"][0]["decision"]["suggested"] = True
        jsonschema.validate(instance=wire, schema=schema)


# ── Deliverable D: build_from_wire reads file_under + precedence ───────────────

class TestBuildFromWireFileUnder:
    def test_file_under_used_as_target(self):
        f = _orphan("F01", candidate=False)
        f["decision"]["file_under"] = "[[000 Home MOC]]"
        wire = gar.build_wire_payload(_doc([f]))
        # rebuild (build_wire_payload resets file_under to "") — set it post-build
        wire["findings"][0]["decision"]["file_under"] = "[[000 Home MOC]]"
        result = gap.build_from_wire(wire)
        item = result["confirmed_items"][0]
        assert item["garden_action"] == "file_note"
        assert item["target_moc"] == "000 Home MOC"
        assert item["target_moc_path"] is None

    def test_file_under_wins_over_scan_candidate(self):
        wire = gar.build_wire_payload(_doc([_orphan("F01", candidate=True)]))
        wire["findings"][0]["decision"]["file_under"] = "[[My Chosen MOC]]"
        result = gap.build_from_wire(wire)
        assert result["confirmed_items"][0]["target_moc"] == "My Chosen MOC"

    def test_scan_candidate_used_when_no_file_under(self):
        wire = gar.build_wire_payload(_doc([_orphan("F01", candidate=True)]))
        result = gap.build_from_wire(wire)
        item = result["confirmed_items"][0]
        assert item["target_moc"] == "Writing MOC"
        assert item["target_moc_path"] == "MOCs/Writing MOC.md"

    def test_no_file_under_no_candidate_skips(self):
        wire = gar.build_wire_payload(_doc([_orphan("F01", candidate=False)]))
        result = gap.build_from_wire(wire)
        assert result["confirmed_items"] == []

    def test_candidates_never_auto_applied(self):
        # A finding with display-only candidates but no file_under and no scan
        # candidate → skipped (candidates are DISPLAY-ONLY, never a decision).
        wire = gar.build_wire_payload(_doc([_orphan("F01", candidate=False)]))
        wire["findings"][0]["decision"]["candidates"] = [
            {"stem": "Some MOC", "score": 0.99}
        ]
        result = gap.build_from_wire(wire)
        assert result["confirmed_items"] == []


# ── Deliverable E: approved-forces-JSON-path ──────────────────────────────────

class TestApprovedForcesJsonPath:
    def test_approved_makes_wire_authoritative_without_edit(self):
        # Digest still matches emit (no apply change) but approved:true → edited.
        wire = gar.build_wire_payload(_doc([_orphan("F01", candidate=True)]))
        assert gap._is_wire_edited(wire) is False  # baseline
        wire["approved"] = True
        assert gap._is_wire_edited(wire) is True

    def test_approved_all_default_still_applies_fixes(self):
        # The edge case: editor approves, changed NO decision. build_from_wire
        # (JSON path) must still produce the scan-candidate fix, not an empty md.
        wire = gar.build_wire_payload(_doc([_orphan("F01", candidate=True)]))
        wire["approved"] = True
        assert gap._is_wire_edited(wire) is True
        result = gap.build_from_wire(wire)
        assert len(result["confirmed_items"]) == 1
        assert result["confirmed_items"][0]["target_moc"] == "Writing MOC"

    def test_not_approved_not_edited_routes_to_report(self):
        wire = gar.build_wire_payload(_doc([_orphan("F01", candidate=True)]))
        assert gap._wire_is_json_approved(wire) is False
        assert gap._is_wire_edited(wire) is False


# ── Deliverable F: schema validates the real fixture + synthetic ──────────────

class TestSchemaValidation:
    def test_synthetic_wire_validates(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        wire = gar.build_wire_payload(
            _doc([_dead_link("F01"), _broken_up("F02"), _orphan("F03"), _advisory("F09")])
        )
        jsonschema.validate(instance=wire, schema=schema)

    def test_enriched_wire_validates(self, tmp_path):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        doc = _doc([_dead_link("F01")])
        rp, wp, cp = _write_pair(tmp_path, doc)
        md = rp.read_text(encoding="utf-8").replace(
            "- [ ] Suggest targets", "- [x] Suggest targets"
        )
        rp.write_text(md, encoding="utf-8")
        _report, wire, _n, _m = gas.run_suggest(str(rp), str(wp), str(cp))
        jsonschema.validate(instance=wire, schema=schema)

    def test_real_fixture_validates(self):
        fixture = REPO / "tomo-instance" / "tomo-tmp" / "garden-audit-wire.json"
        if not fixture.exists():
            pytest.skip("real fixture not present in this checkout")
        wire = json.loads(fixture.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(instance=wire, schema=schema)

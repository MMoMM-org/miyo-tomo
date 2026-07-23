#!/usr/bin/env python3
# version: 0.1.0
"""test_garden_audit_pushback.py — ack-driven advisory pushback + opt-in Apply.

User decisions 2026-07-23:
  1. decision.selected defaults FALSE everywhere (opt-in ticking).
  2. Advisories (stale_moc, duplicate_stem) get an Acknowledge channel —
     markdown `- [x] Acknowledge` tick OR wire finding-level `ack: true`.
     Pass-2 (--stamp-pushback) stamps the pushback ledger; the next scan
     suppresses the acked advisory until the window lapses.
  3. settings block in the exclusions YAML: stale_moc_days (default 90),
     advisory_pushback_days (default 30). The configure wizard preserves it.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import jsonschema
import yaml

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "tomo" / "scripts"
SCHEMAS = REPO / "tomo" / "schemas"
sys.path.insert(0, str(SCRIPTS))

from lib.garden_exclusions import (  # noqa: E402
    GardenExclusions,
    load_pushback_ledger,
    stamp_pushback,
)
from lib.render_md import compute_garden_audit_digest  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ga = _load("garden_audit", "garden-audit.py")
gar = _load("garden_audit_render", "garden-audit-render.py")
gap = _load("garden_audit_parser", "garden-audit-parser.py")

TODAY = date(2026, 7, 23)


# ── Doc fixtures ──────────────────────────────────────────────────────────────

def _doc(findings, **extra):
    d = {
        "run_id": "run-pushback-001",
        "generated": "2026-07-23T12:00:00Z",
        "profile": "miyo",
        "findings": findings,
    }
    d.update(extra)
    return d


def _stale_moc(fid="F01", path="Maps/Old MOC.md"):
    return {
        "id": fid, "check": "stale_moc", "tier": "advisory", "fixable": False,
        "target": {"path": path, "stem": Path(path).stem},
        "detail": {"mtime": "2026-01-01T00:00:00+00:00"},
    }


def _dup_stem(fid="F02"):
    return {
        "id": fid, "check": "duplicate_stem", "tier": "advisory", "fixable": False,
        "target": {"path": "Notes/Dup.md", "stem": "Dup"},
        "detail": {"dupes": ["Notes/Dup.md", "Archive/Dup.md"]},
    }


def _dead_link(fid="F03"):
    return {
        "id": fid, "check": "dead_link", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Src.md", "stem": "Src"},
        "detail": {"dead_target": "Missing Note", "count": 1},
        "decision": {"selected": False, "action": "edit_note_text"},
    }


# ── Settings loading ──────────────────────────────────────────────────────────

class TestSettings:
    def test_defaults_without_settings_block(self):
        excl = GardenExclusions.from_dict({"version": 1, "exclusions": []}, today=TODAY)
        assert excl.stale_moc_days == 90
        assert excl.advisory_pushback_days == 30

    def test_loaded_values(self):
        excl = GardenExclusions.from_dict(
            {"version": 1, "exclusions": [],
             "settings": {"stale_moc_days": 120, "advisory_pushback_days": 14}},
            today=TODAY,
        )
        assert excl.stale_moc_days == 120
        assert excl.advisory_pushback_days == 14

    def test_bad_values_fail_open_to_defaults(self):
        excl = GardenExclusions.from_dict(
            {"version": 1, "exclusions": [],
             "settings": {"stale_moc_days": "soon", "advisory_pushback_days": -5}},
            today=TODAY,
        )
        assert excl.stale_moc_days == 90
        assert excl.advisory_pushback_days == 30

    def test_missing_file_defaults(self, tmp_path):
        excl = GardenExclusions.from_paths(
            tmp_path / "none.yaml", tmp_path / "no-ledger.yaml", today=TODAY
        )
        assert excl.stale_moc_days == 90
        assert excl.advisory_pushback_days == 30


# ── Ledger stamp / prune / suppress ───────────────────────────────────────────

class TestLedger:
    def test_stamp_writes_entries(self, tmp_path):
        ledger = tmp_path / "ledger.yaml"
        written = stamp_pushback(
            ledger, [{"path": "Maps/Old MOC.md", "check": "stale_moc"}], 30, today=TODAY
        )
        assert written == [{
            "path": "Maps/Old MOC.md", "check": "stale_moc",
            "created": "2026-07-23", "until": "2026-08-22",
        }]
        assert load_pushback_ledger(ledger) == written

    def test_stamp_prunes_expired_and_replaces_restamped(self, tmp_path):
        ledger = tmp_path / "ledger.yaml"
        ledger.write_text(yaml.safe_dump({"version": 1, "entries": [
            {"path": "A.md", "check": "stale_moc",
             "created": "2026-05-01", "until": "2026-05-31"},   # expired → pruned
            {"path": "B.md", "check": "stale_moc",
             "created": "2026-07-20", "until": "2026-08-19"},   # kept
            {"path": "C.md", "check": "duplicate_stem",
             "created": "2026-07-01", "until": "2026-07-31"},   # re-stamped → replaced
        ]}), encoding="utf-8")
        entries = stamp_pushback(
            ledger, [{"path": "C.md", "check": "duplicate_stem"}], 30, today=TODAY
        )
        by_path = {(e["path"], e["check"]): e for e in entries}
        assert ("A.md", "stale_moc") not in by_path
        assert by_path[("B.md", "stale_moc")]["until"] == "2026-08-19"
        assert by_path[("C.md", "duplicate_stem")]["until"] == "2026-08-22"

    def test_from_paths_merges_ledger_into_exclusions(self, tmp_path):
        ledger = tmp_path / "ledger.yaml"
        stamp_pushback(ledger, [{"path": "Maps/Old MOC.md", "check": "stale_moc"}],
                       30, today=TODAY)
        excl = GardenExclusions.from_paths(tmp_path / "none.yaml", ledger, today=TODAY)
        assert excl.is_excluded(
            {"path": "Maps/Old MOC.md", "tags": []}, "stale_moc", today=TODAY
        ) is True
        # Same path, other check → NOT suppressed (per-check scoping).
        assert excl.is_excluded(
            {"path": "Maps/Old MOC.md", "tags": []}, "duplicate_stem", today=TODAY
        ) is False

    def test_ledger_entry_expires(self, tmp_path):
        ledger = tmp_path / "ledger.yaml"
        stamp_pushback(ledger, [{"path": "Maps/Old MOC.md", "check": "stale_moc"}],
                       30, today=date(2026, 6, 1))  # until 2026-07-01 < TODAY
        excl = GardenExclusions.from_paths(tmp_path / "none.yaml", ledger, today=TODAY)
        assert excl.is_excluded(
            {"path": "Maps/Old MOC.md", "tags": []}, "stale_moc", today=TODAY
        ) is False

    def test_ledger_shows_in_pushback_rules(self, tmp_path):
        ledger = tmp_path / "ledger.yaml"
        stamp_pushback(ledger, [{"path": "Maps/Old MOC.md", "check": "stale_moc"}],
                       30, today=TODAY)
        excl = GardenExclusions.from_paths(tmp_path / "none.yaml", ledger, today=TODAY)
        rules = excl.pushback_rules(today=TODAY)
        assert any(r["target"]["value"] == "Maps/Old MOC.md" for r in rules)


# ── Scan: opt-in default + settings wiring + ledger suppression ───────────────

def _no_graph(*a, **k):
    return {"orphans": [], "deadLinks": [], "total": {}}


class TestScan:
    def test_fixable_findings_start_unselected(self):
        # Falsifies the pre-2026-07-23 impl (selected: True).
        entries = [{
            "path": "Notes/Child.md", "stem": "Child", "kind": "note",
            "title": "Child", "up_state": "broken", "up_target": "Gone MOC",
            "topics": [], "tags": [],
        }]
        doc = ga.run_scan(entries, graph_audit_fn=_no_graph, list_dir_fn=lambda **k: [])
        fixable = [f for f in doc["findings"] if f["fixable"]]
        assert fixable, "expected at least one fixable finding"
        assert all(f["decision"]["selected"] is False for f in fixable)

    def test_doc_carries_advisory_pushback_days(self):
        doc = ga.run_scan([], graph_audit_fn=_no_graph, list_dir_fn=lambda **k: [],
                          advisory_pushback_days=14)
        assert doc["advisory_pushback_days"] == 14

    def test_ledgered_stale_moc_is_suppressed(self, tmp_path):
        ledger = tmp_path / "ledger.yaml"
        stamp_pushback(ledger, [{"path": "Maps/Old MOC.md", "check": "stale_moc"}],
                       30, today=TODAY)
        excl = GardenExclusions.from_paths(tmp_path / "none.yaml", ledger, today=TODAY)
        entries = [{
            "path": "Maps/Old MOC.md", "stem": "Old MOC", "kind": "moc",
            "title": "Old MOC", "up_state": "valid", "up_target": None,
            "topics": [], "tags": [],
        }]

        def old_list_dir(path=None, **kwargs):
            return [{"type": "file", "path": "Maps/Old MOC.md",
                     "modified": 1767225600000, "created": 1767225600000, "size": 1}]

        doc = ga.run_scan(entries, graph_audit_fn=_no_graph, list_dir_fn=old_list_dir,
                          exclusions=excl, today=TODAY)
        assert not any(f["check"] == "stale_moc" for f in doc["findings"])


# ── Render: Acknowledge line + opt-in preamble + wire ack ─────────────────────

class TestRender:
    def test_advisory_block_has_acknowledge_line_with_days(self):
        doc = _doc([_stale_moc()], advisory_pushback_days=14)
        report = gar.render_report(doc)
        assert "- [ ] Acknowledge — reviewed; pause this advisory for 14 days" in report

    def test_preamble_is_opt_in_and_apply_unticked(self):
        doc = _doc([_dead_link()])
        report = gar.render_report(doc)
        assert "Tick **Apply** on the fixes you want" in report
        assert "- [ ] Apply — tick to apply this fix" in report
        assert "- [x] Apply" not in report

    def test_wire_advisory_carries_ack_false_fixable_does_not(self):
        wire = gar.build_wire_payload(_doc([_stale_moc(), _dup_stem(), _dead_link()]))
        by_check = {f["check"]: f for f in wire["findings"]}
        assert by_check["stale_moc"]["ack"] is False
        assert by_check["duplicate_stem"]["ack"] is False
        assert "ack" not in by_check["dead_link"]

    def test_ack_flips_digest(self):
        wire = gar.build_wire_payload(_doc([_stale_moc()]))
        base = wire["emit_digest"]
        wire["findings"][0]["ack"] = True
        assert compute_garden_audit_digest(wire) != base
        assert gap._is_wire_edited(wire) is True

    def test_wire_with_ack_validates_against_schema(self):
        schema = json.loads(
            (SCHEMAS / "garden-audit-wire.schema.json").read_text(encoding="utf-8")
        )
        wire = gar.build_wire_payload(_doc([_stale_moc(), _dead_link()]))
        jsonschema.validate(instance=wire, schema=schema)
        wire["findings"][0]["ack"] = True
        jsonschema.validate(instance=wire, schema=schema)


# ── Parser: ack via both channels + --stamp-pushback CLI ──────────────────────

def _render_pair(doc):
    report = "\n".join(gar.render_frontmatter(doc)) + "\n" + gar.render_report(doc)
    wire = gar.build_wire_payload(doc)
    return report, wire


class TestParserAck:
    def test_markdown_ack_tick_yields_acked_advisories(self):
        doc = _doc([_stale_moc("F01"), _dup_stem("F02")], advisory_pushback_days=30)
        report, wire = _render_pair(doc)
        report = report.replace(
            "- [ ] Acknowledge", "- [x] Acknowledge", 1
        )  # tick ONLY F01
        result = gap.build_from_report(report, wire)
        assert result["acked_advisories"] == [
            {"id": "F01", "path": "Maps/Old MOC.md", "check": "stale_moc"}
        ]

    def test_unticked_ack_yields_nothing(self):
        doc = _doc([_stale_moc("F01")], advisory_pushback_days=30)
        report, wire = _render_pair(doc)
        result = gap.build_from_report(report, wire)
        assert result["acked_advisories"] == []

    def test_wire_ack_routes_json_path_and_yields_acked(self):
        doc = _doc([_stale_moc("F01")])
        _report, wire = _render_pair(doc)
        wire["findings"][0]["ack"] = True
        # ack flips the digest → the edited wire is authoritative (JSON path).
        assert gap._is_wire_edited(wire) is True
        result = gap.build_from_wire(wire)
        assert result["acked_advisories"] == [
            {"id": "F01", "path": "Maps/Old MOC.md", "check": "stale_moc"}
        ]

    def test_cli_stamp_pushback_writes_ledger(self, tmp_path):
        doc = _doc([_stale_moc("F01")], advisory_pushback_days=30)
        report, wire = _render_pair(doc)
        report = report.replace("- [ ] Acknowledge", "- [x] Acknowledge", 1)
        rp = tmp_path / "report.md"
        wp = tmp_path / "wire.json"
        ledger = tmp_path / "ledger.yaml"
        rp.write_text(report, encoding="utf-8")
        wp.write_text(json.dumps(wire), encoding="utf-8")
        rc = subprocess.run(
            [sys.executable, str(SCRIPTS / "garden-audit-parser.py"),
             "--file", str(rp), "--wire", str(wp),
             "--stamp-pushback", "--pushback-ledger", str(ledger),
             "--exclusions", str(tmp_path / "none.yaml")],
            capture_output=True, text=True, cwd=str(SCRIPTS.parent),
        )
        assert rc.returncode == 0, rc.stderr
        assert "stamped 1 acknowledged advisory(ies)" in rc.stderr
        entries = load_pushback_ledger(ledger)
        assert len(entries) == 1
        assert entries[0]["path"] == "Maps/Old MOC.md"
        assert entries[0]["check"] == "stale_moc"

    def test_cli_without_flag_does_not_write_ledger(self, tmp_path):
        doc = _doc([_stale_moc("F01")], advisory_pushback_days=30)
        report, wire = _render_pair(doc)
        report = report.replace("- [ ] Acknowledge", "- [x] Acknowledge", 1)
        rp = tmp_path / "report.md"
        wp = tmp_path / "wire.json"
        ledger = tmp_path / "ledger.yaml"
        rp.write_text(report, encoding="utf-8")
        wp.write_text(json.dumps(wire), encoding="utf-8")
        rc = subprocess.run(
            [sys.executable, str(SCRIPTS / "garden-audit-parser.py"),
             "--file", str(rp), "--wire", str(wp),
             "--pushback-ledger", str(ledger)],
            capture_output=True, text=True, cwd=str(SCRIPTS.parent),
        )
        assert rc.returncode == 0, rc.stderr
        assert not ledger.exists()


# ── Configure: settings round-trip ────────────────────────────────────────────

class TestConfigureSettingsRoundTrip:
    def test_wizard_rewrite_preserves_settings(self, tmp_path):
        out = tmp_path / "garden-audit-exclusions.yaml"
        out.write_text(yaml.safe_dump({
            "version": 1, "configured": True, "exclusions": [],
            "settings": {"stale_moc_days": 120, "advisory_pushback_days": 14},
        }), encoding="utf-8")
        choices = tmp_path / "choices.json"
        choices.write_text(json.dumps({"today": "2026-07-23", "exclusions": []}),
                           encoding="utf-8")
        rc = subprocess.run(
            [sys.executable, str(SCRIPTS / "garden-audit-configure.py"),
             "--write", "--choices", str(choices), "--output", str(out)],
            capture_output=True, text=True,
        )
        assert rc.returncode == 0, rc.stderr
        written = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert written["settings"] == {
            "stale_moc_days": 120, "advisory_pushback_days": 14,
        }
        assert written["configured"] is True

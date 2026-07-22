#!/usr/bin/env python3
# version: 0.2.0
"""test_garden_audit_suggest.py — Tests for garden-audit-suggest.py CLI (spec 030 T7.4).

The `--suggest` second-pass helper: reads the in-vault report + wire + MOC-structure
cache, enriches Suggest-ticked dead_link/broken_up blocks with candidate pick lists
(via garden-audit-render.enrich_report_with_suggestions), and writes the enriched
report back out. Mirrors garden-audit-configure.py as a mode-support helper.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent
_SCRIPTS_DIR = _ROOT / "tomo" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gar = _load("garden_audit_render", "garden-audit-render.py")
gas = _load("garden_audit_suggest", "garden-audit-suggest.py")


def _doc(findings):
    return {
        "run_id": "run-suggest-001", "generated": "2026-07-21T12:00:00Z",
        "profile": "miyo", "findings": findings, "skipped_checks": [],
        "skipped_checks_reason": "", "reappeared_exclusions": [],
    }


def _dead_link_finding(fid="F01"):
    return {
        "id": fid, "check": "dead_link", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Source Note.md", "stem": "Source Note"},
        "detail": {"dead_target": "Missing Note", "count": 2},
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _full_report(doc):
    return "\n".join(gar.render_frontmatter(doc)) + "\n" + gar.render_report(doc)


def _write_inputs(tmp_path, doc, cache_entries, *, tick_suggest=True):
    """Render report + wire, optionally tick Suggest, write all three inputs."""
    report = _full_report(doc)
    if tick_suggest:
        report = report.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
    wire = gar.build_wire_payload(doc)
    report_path = tmp_path / "report.md"
    wire_path = tmp_path / "wire.json"
    cache_path = tmp_path / "moc-structure-cache.yaml"
    report_path.write_text(report, encoding="utf-8")
    wire_path.write_text(json.dumps(wire), encoding="utf-8")
    cache_path.write_text(yaml.safe_dump({"entries": cache_entries}), encoding="utf-8")
    return report_path, wire_path, cache_path


_DEAD_CACHE = [
    {"stem": "Missing Notes", "kind": "note", "path": "N/Missing Notes.md", "topics": []},
]


class TestSuggestHelperFunction:
    def test_enrich_function_inserts_pick_list(self, tmp_path):
        doc = _doc([_dead_link_finding("F01")])
        rp, wp, cp = _write_inputs(tmp_path, doc, _DEAD_CACHE)
        out, _wire = gas.run_suggest(str(rp), str(wp), str(cp))
        assert "[[Missing Notes]]" in out
        assert "Pick one" in out

    def test_missing_cache_degrades_to_input_report(self, tmp_path):
        doc = _doc([_dead_link_finding("F01")])
        rp, wp, _ = _write_inputs(tmp_path, doc, _DEAD_CACHE)
        out, _wire = gas.run_suggest(str(rp), str(wp), str(tmp_path / "nope.yaml"))
        # No cache → no candidates, but the report is returned intact (no crash).
        assert "### F01 — Dead link" in out
        assert "Pick one" not in out

    def test_missing_wire_degrades_to_input_report(self, tmp_path):
        # _load_wire returns {} → no findings to join → all blocks preserved.
        doc = _doc([_dead_link_finding("F01")])
        rp, _, cp = _write_inputs(tmp_path, doc, _DEAD_CACHE)
        out, wire = gas.run_suggest(str(rp), str(tmp_path / "nope.json"), str(cp))
        assert "### F01 — Dead link" in out
        assert "Pick one" not in out
        assert wire is None  # unreadable wire → no enriched wire emitted


class TestSuggestCli:
    def test_cli_writes_enriched_report(self, tmp_path):
        doc = _doc([_dead_link_finding("F01")])
        rp, wp, cp = _write_inputs(tmp_path, doc, _DEAD_CACHE)
        out_path = tmp_path / "enriched.md"
        rc = subprocess.run(
            [sys.executable, str(_SCRIPTS_DIR / "garden-audit-suggest.py"),
             "--report", str(rp), "--wire", str(wp), "--cache", str(cp),
             "--output", str(out_path)],
            capture_output=True, text=True,
        )
        assert rc.returncode == 0, rc.stderr
        enriched = out_path.read_text(encoding="utf-8")
        assert "[[Missing Notes]]" in enriched

    def test_cli_missing_report_exits_nonzero(self, tmp_path):
        rc = subprocess.run(
            [sys.executable, str(_SCRIPTS_DIR / "garden-audit-suggest.py"),
             "--report", str(tmp_path / "nope.md"),
             "--wire", str(tmp_path / "w.json"),
             "--cache", str(tmp_path / "c.yaml"),
             "--output", str(tmp_path / "o.md")],
            capture_output=True, text=True,
        )
        assert rc.returncode != 0
        assert "report" in rc.stderr.lower()

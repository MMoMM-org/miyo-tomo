#!/usr/bin/env python3
# version: 0.1.0
"""test_garden_audit_stats.py — garden-audit-stats.py read-only overview (spec 030).

`/garden-audit stats` aggregates a fresh scan doc + the exclusion config into a
compact, deterministic overview relayed to the chat (no vault write). Covers:
  - aggregation by AREA (first path segment; root → "(root)") × CHECK
  - top-N area cap + explicit "others" row (no silent truncation)
  - totals per check + per tier + skipped_checks surfacing
  - active exclusions + pushback (days-remaining, soonest-first) with injected today
  - reappeared from doc.json
  - None-sentinel: explicit-missing --exclusions → exit 1; defaulted-absent → "none"
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_SCRIPTS = _ROOT / "tomo" / "scripts"
sys.path.insert(0, str(_SCRIPTS))


def _load_stats():
    spec = importlib.util.spec_from_file_location(
        "garden_audit_stats", _SCRIPTS / "garden-audit-stats.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gas = _load_stats()
from lib.garden_exclusions import GardenExclusions  # noqa: E402


# ── doc.json fixtures ─────────────────────────────────────────────────────────

def _finding(fid, check, path, tier):
    return {
        "id": fid, "check": check, "tier": tier, "fixable": True,
        "target": {"path": path, "stem": Path(path).stem}, "detail": {},
    }


def _doc(findings=None, skipped_checks=None, skipped_reason="", reappeared=None):
    return {
        "run_id": "run-stats-001", "generated": "2026-07-21T12:00:00Z", "profile": "miyo",
        "findings": findings or [],
        "skipped_checks": skipped_checks or [],
        "skipped_checks_reason": skipped_reason,
        "reappeared_exclusions": reappeared or [],
    }


def _sample_findings():
    return [
        # Calendar/ — 3 findings
        _finding("F01", "unparented", "Calendar/2026-07-19.md", "structure"),
        _finding("F02", "orphan", "Calendar/2026-07-20.md", "structure"),
        _finding("F03", "unparented", "Calendar/2026-07-21.md", "structure"),
        # Notes/ — 2 findings
        _finding("F04", "dead_link", "Notes/A.md", "integrity"),
        _finding("F05", "broken_up", "Notes/B.md", "integrity"),
        # root-level note → "(root)" — 1 finding
        _finding("F06", "duplicate_stem", "Loose.md", "advisory"),
    ]


# ── aggregate_by_area ─────────────────────────────────────────────────────────

class TestAggregateByArea:
    def test_groups_by_first_path_segment(self):
        agg = gas.aggregate_by_area(_sample_findings())
        rows = {r["area"]: r for r in agg["rows"]}
        assert rows["Calendar"]["total"] == 3
        assert rows["Calendar"]["unparented"] == 2
        assert rows["Calendar"]["orphan"] == 1
        assert rows["Notes"]["total"] == 2

    def test_root_level_note_area_is_root_label(self):
        agg = gas.aggregate_by_area(_sample_findings())
        areas = {r["area"] for r in agg["rows"]}
        assert "(root)" in areas
        root = next(r for r in agg["rows"] if r["area"] == "(root)")
        assert root["duplicate_stem"] == 1

    def test_sorted_by_total_desc(self):
        agg = gas.aggregate_by_area(_sample_findings())
        totals = [r["total"] for r in agg["rows"]]
        assert totals == sorted(totals, reverse=True)
        assert agg["rows"][0]["area"] == "Calendar"  # 3 = the most

    def test_top_n_cap_emits_others_row_no_silent_truncation(self):
        # 20 distinct areas, each 1 finding; cap at top_n=15 → 15 rows + others (5).
        findings = [
            _finding(f"F{i:02d}", "orphan", f"Area{i:02d}/note.md", "structure")
            for i in range(20)
        ]
        agg = gas.aggregate_by_area(findings, top_n=15)
        assert len(agg["rows"]) == 15
        assert agg["others_area_count"] == 5
        assert agg["others_total"] == 5

    def test_no_others_when_under_cap(self):
        agg = gas.aggregate_by_area(_sample_findings(), top_n=15)
        assert agg["others_area_count"] == 0
        assert agg["others_total"] == 0


# ── render_stats (full markdown) ──────────────────────────────────────────────

class TestRenderStats:
    def _render(self, doc, cfg, today=date(2026, 8, 1)):
        return gas.render_stats(doc, cfg, effective_today=today)

    def test_open_findings_section_present(self):
        out = self._render(_doc(_sample_findings()), None)
        assert "## Open findings by area" in out
        assert "Calendar" in out

    def test_totals_section_counts_per_check_and_tier(self):
        out = self._render(_doc(_sample_findings()), None)
        assert "## Totals" in out
        # 2 unparented, 1 orphan → structure tier = 3
        assert "unparented" in out and "structure" in out

    def test_skipped_checks_surfaced_with_reason(self):
        doc = _doc(
            _sample_findings(),
            skipped_checks=["orphan", "dead_link"],
            skipped_reason="graph unavailable",
        )
        out = self._render(doc, None)
        assert "graph unavailable" in out
        assert "orphan" in out and "dead_link" in out

    def test_active_exclusions_none_when_no_config(self):
        out = self._render(_doc(_sample_findings()), None)
        assert "## Active exclusions" in out
        assert "none configured" in out

    def test_active_exclusions_rendered(self):
        cfg = GardenExclusions.from_dict({
            "exclusions": [{
                "target": {"type": "path", "value": "Calendar/"},
                "checks": ["unparented", "orphan"], "mode": "permanent",
            }],
        }, today=date(2026, 8, 1))
        out = self._render(_doc(_sample_findings()), cfg)
        assert "path:Calendar/" in out
        assert "permanent" in out

    def test_pushback_days_remaining_and_soonest_first(self):
        cfg = GardenExclusions.from_dict({
            "exclusions": [
                {"target": {"type": "note", "value": "Later.md"}, "checks": "all",
                 "mode": "temporary", "until": "2026-09-01"},
                {"target": {"type": "note", "value": "Soon.md"}, "checks": "all",
                 "mode": "temporary", "until": "2026-08-11"},
            ],
        }, today=date(2026, 8, 1))
        out = self._render(_doc(), cfg, today=date(2026, 8, 1))
        assert "## On pushback" in out
        # Scope to the pushback section (both rules also appear under Active
        # exclusions above; ordering there is not the soonest-first contract).
        pushback = out[out.index("## On pushback"):]
        soon_idx = pushback.index("Soon.md")
        later_idx = pushback.index("Later.md")
        assert soon_idx < later_idx  # soonest-expiring first
        # days remaining: 2026-08-11 - 2026-08-01 = 10
        assert "10 days remaining" in pushback[soon_idx:later_idx]

    def test_reappeared_from_doc(self):
        doc = _doc(
            _sample_findings(),
            reappeared=[{
                "target": {"type": "path", "value": "Archive/"},
                "checks": ["orphan"], "mode": "temporary", "until": "2026-07-01",
            }],
        )
        out = self._render(doc, None)
        assert "## Reappeared" in out
        assert "Archive/" in out


# ── run_stats: None-sentinel explicit-vs-default ──────────────────────────────

class TestRunStatsExclusionsSentinel:
    def _write_doc(self, tmp_path):
        p = tmp_path / "doc.json"
        p.write_text(json.dumps(_doc(_sample_findings())), encoding="utf-8")
        return p

    def test_defaulted_absent_exclusions_says_none(self, tmp_path):
        doc = self._write_doc(tmp_path)
        # No exclusions file, explicit_exclusions=None → "none configured", no error.
        out = gas.run_stats(
            str(doc), None, explicit_exclusions=False,
            effective_today=date(2026, 8, 1),
            default_excl_path=str(tmp_path / "config" / "garden-audit-exclusions.yaml"),
        )
        assert "none configured" in out

    def test_explicit_missing_exclusions_raises(self, tmp_path):
        doc = self._write_doc(tmp_path)
        with __import__("pytest").raises(FileNotFoundError):
            gas.run_stats(
                str(doc), str(tmp_path / "nope.yaml"), explicit_exclusions=True,
                effective_today=date(2026, 8, 1),
            )


# ── CLI: bare invocation resolves cwd-relative defaults ───────────────────────

class TestStatsCli:
    def _instance(self, tmp_path):
        (tmp_path / "config").mkdir()
        (tmp_path / "tomo-tmp").mkdir()
        (tmp_path / "tomo-tmp" / "garden-audit-doc.json").write_text(
            json.dumps(_doc(_sample_findings())), encoding="utf-8"
        )
        return tmp_path

    def test_bare_run_resolves_defaults_and_prints_overview(self, tmp_path):
        inst = self._instance(tmp_path)
        rc = subprocess.run(
            [sys.executable, str(_SCRIPTS / "garden-audit-stats.py")],
            capture_output=True, text=True, cwd=str(inst),
        )
        assert rc.returncode == 0, rc.stderr
        assert "## Open findings by area" in rc.stdout
        assert "## Totals" in rc.stdout

    def test_explicit_missing_exclusions_exits_1(self, tmp_path):
        inst = self._instance(tmp_path)
        rc = subprocess.run(
            [sys.executable, str(_SCRIPTS / "garden-audit-stats.py"),
             "--exclusions", str(inst / "nope.yaml")],
            capture_output=True, text=True, cwd=str(inst),
        )
        assert rc.returncode == 1
        assert "not found" in rc.stderr.lower()

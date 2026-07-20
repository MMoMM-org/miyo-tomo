#!/usr/bin/env python3
# version: 0.2.0
"""test_garden_audit_configure.py — Tests for garden-audit-configure.py wizard helper (spec 030).

Covers both modes:
  --summarize: cluster detection, thresholds, zero-findings, multi-check breakdown
  --write:     schema-valid YAML output, configured:true always, permanent + temporary,
               empty exclusions list, validation errors
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import jsonschema
import yaml

# ──────────────────────────────────────────────────────────────────────────────
# Load module under test (hyphen-named)
# ──────────────────────────────────────────────────────────────────────────────
_SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
_SCHEMAS_DIR = Path(__file__).parent.parent / "tomo" / "schemas"
sys.path.insert(0, str(_SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "garden_audit_configure", _SCRIPTS_DIR / "garden-audit-configure.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

summarize = _mod.summarize
write_config = _mod.write_config

_EXCLUSIONS_SCHEMA_PATH = _SCHEMAS_DIR / "garden-audit-exclusions.schema.json"


def _load_exclusions_schema() -> dict:
    return json.loads(_EXCLUSIONS_SCHEMA_PATH.read_text())


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _finding(check: str, path: str) -> dict:
    """Minimal finding dict for summarize tests."""
    return {
        "check": check,
        "tier": "structure",
        "fixable": False,
        "target": {"path": path, "stem": Path(path).stem},
        "detail": {},
    }


def _make_doc(findings: list[dict]) -> dict:
    return {
        "run_id": "test-run",
        "generated": "2026-07-20T00:00:00Z",
        "profile": "miyo",
        "skipped_checks": [],
        "skipped_checks_reason": "",
        "reappeared_exclusions": [],
        "findings": findings,
    }


def _write_doc(tmp_path: Path, findings: list[dict]) -> str:
    doc_path = tmp_path / "garden-audit-doc.json"
    doc_path.write_text(json.dumps(_make_doc(findings)), encoding="utf-8")
    return str(doc_path)


def _simple_choices(tmp_path: Path, exclusions: list[dict], today: str = "2026-07-20") -> str:
    """Write choices JSON to a temp file and return the file path string."""
    choices_file = tmp_path / "garden-audit-choices.json"
    choices_file.write_text(
        json.dumps({"today": today, "exclusions": exclusions}), encoding="utf-8"
    )
    return str(choices_file)


# ──────────────────────────────────────────────────────────────────────────────
# --summarize tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSummarize:
    def test_zero_findings_outputs_healthy_message(self, tmp_path, capsys):
        doc_path = _write_doc(tmp_path, [])
        rc = summarize(doc_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "0 findings" in out

    def test_dominant_cluster_detected(self, tmp_path, capsys):
        """A folder with >= 10 findings qualifies as a cluster."""
        findings = [_finding("unparented", f"Calendar/Day{i}.md") for i in range(12)]
        doc_path = _write_doc(tmp_path, findings)
        rc = summarize(doc_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Calendar/" in out
        assert "12 findings" in out

    def test_small_folders_below_threshold_not_in_clusters(self, tmp_path, capsys):
        """Folders with small finding counts spread across many folders show no clusters.

        Each folder has 2 findings out of 20 total = 10% < 20% AND < 10 absolute.
        """
        # 10 folders × 2 findings each = 20 total; no folder >= 10 or >= 20%
        findings = []
        for folder_idx in range(10):
            for note_idx in range(2):
                findings.append(_finding("orphan", f"Folder{folder_idx}/Note{note_idx}.md"))
        doc_path = _write_doc(tmp_path, findings)
        rc = summarize(doc_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "No dominant clusters" in out

    def test_cluster_breakdown_by_check(self, tmp_path, capsys):
        """Cluster summary shows breakdown per check type."""
        findings = (
            [_finding("unparented", f"Archive/Note{i}.md") for i in range(7)]
            + [_finding("orphan", f"Archive/Note{i}.md") for i in range(7, 14)]
        )
        doc_path = _write_doc(tmp_path, findings)
        rc = summarize(doc_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Archive/" in out
        assert "unparented=" in out
        assert "orphan=" in out

    def test_pct_threshold_triggers_cluster(self, tmp_path, capsys):
        """A folder with >= 20% of total findings qualifies even if < 10 absolute."""
        # 6 findings in one folder out of 6 total = 100% > 20%
        findings = [_finding("broken_up", f"Special/Note{i}.md") for i in range(6)]
        doc_path = _write_doc(tmp_path, findings)
        rc = summarize(doc_path)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Special/" in out

    def test_missing_doc_exits_nonzero(self, tmp_path, capsys):
        rc = summarize(str(tmp_path / "missing.json"))
        assert rc != 0

    def test_clusters_sorted_descending(self, tmp_path, capsys):
        """Largest cluster appears first in output."""
        findings = (
            [_finding("unparented", f"Archive/Note{i}.md") for i in range(15)]
            + [_finding("orphan", f"Calendar/Day{i}.md") for i in range(10)]
        )
        doc_path = _write_doc(tmp_path, findings)
        summarize(doc_path)
        out = capsys.readouterr().out
        archive_pos = out.find("Archive/")
        calendar_pos = out.find("Calendar/")
        assert archive_pos < calendar_pos, "Archive (15) must appear before Calendar (10)"


# ──────────────────────────────────────────────────────────────────────────────
# --write tests
# ──────────────────────────────────────────────────────────────────────────────

class TestWriteConfig:
    def test_empty_exclusions_writes_schema_valid_yaml(self, tmp_path):
        out_path = tmp_path / "excl.yaml"
        rc = write_config(_simple_choices(tmp_path, []), str(out_path))
        assert rc == 0
        assert out_path.exists()
        data = yaml.safe_load(out_path.read_text())
        assert data["version"] == 1
        assert data["configured"] is True
        assert data["exclusions"] == []
        # Schema validation
        schema = _load_exclusions_schema()
        jsonschema.validate(instance=data, schema=schema)

    def test_configured_is_always_true(self, tmp_path):
        """configured: true must be present regardless of exclusions count."""
        out_path = tmp_path / "excl.yaml"
        write_config(_simple_choices(tmp_path, []), str(out_path))
        data = yaml.safe_load(out_path.read_text())
        assert data["configured"] is True

    def test_permanent_exclusion_written_correctly(self, tmp_path):
        out_path = tmp_path / "excl.yaml"
        excl = [{
            "target": {"type": "path", "value": "Calendar/"},
            "checks": ["unparented", "orphan"],
            "mode": "permanent",
            "reason": "daily notes never get up::",
        }]
        rc = write_config(_simple_choices(tmp_path, excl), str(out_path))
        assert rc == 0
        data = yaml.safe_load(out_path.read_text())
        schema = _load_exclusions_schema()
        jsonschema.validate(instance=data, schema=schema)
        e = data["exclusions"][0]
        assert e["target"] == {"type": "path", "value": "Calendar/"}
        assert e["checks"] == ["unparented", "orphan"]
        assert e["mode"] == "permanent"
        assert "until" not in e
        assert e["created"] == "2026-07-20"

    def test_temporary_exclusion_computes_until_date(self, tmp_path):
        out_path = tmp_path / "excl.yaml"
        excl = [{
            "target": {"type": "note", "value": "Projects/Big.md"},
            "checks": "all",
            "mode": "temporary",
            "reason": "mid-refactor",
            "push_back_days": 90,
        }]
        rc = write_config(_simple_choices(tmp_path, excl, today="2026-07-20"), str(out_path))
        assert rc == 0
        data = yaml.safe_load(out_path.read_text())
        schema = _load_exclusions_schema()
        jsonschema.validate(instance=data, schema=schema)
        e = data["exclusions"][0]
        assert e["mode"] == "temporary"
        expected_until = (date(2026, 7, 20) + timedelta(days=90)).isoformat()
        assert e["until"] == expected_until

    def test_temporary_default_push_back_90_days(self, tmp_path):
        """push_back_days defaults to 90 when not provided."""
        out_path = tmp_path / "excl.yaml"
        excl = [{
            "target": {"type": "tag", "value": "wip"},
            "checks": ["stale_moc"],
            "mode": "temporary",
            "reason": "work in progress",
            # no push_back_days
        }]
        rc = write_config(_simple_choices(tmp_path, excl, today="2026-07-20"), str(out_path))
        assert rc == 0
        data = yaml.safe_load(out_path.read_text())
        e = data["exclusions"][0]
        assert e["until"] == (date(2026, 7, 20) + timedelta(days=90)).isoformat()

    def test_checks_all_accepted(self, tmp_path):
        out_path = tmp_path / "excl.yaml"
        excl = [{
            "target": {"type": "path", "value": "Archive/"},
            "checks": "all",
            "mode": "permanent",
            "reason": "archived content",
        }]
        rc = write_config(_simple_choices(tmp_path, excl), str(out_path))
        assert rc == 0
        data = yaml.safe_load(out_path.read_text())
        schema = _load_exclusions_schema()
        jsonschema.validate(instance=data, schema=schema)
        assert data["exclusions"][0]["checks"] == "all"

    def test_invalid_check_name_exits_nonzero(self, tmp_path):
        out_path = tmp_path / "excl.yaml"
        excl = [{
            "target": {"type": "path", "value": "X/"},
            "checks": ["not_a_real_check"],
            "mode": "permanent",
            "reason": "test",
        }]
        rc = write_config(_simple_choices(tmp_path, excl), str(out_path))
        assert rc != 0
        assert not out_path.exists()

    def test_invalid_mode_exits_nonzero(self, tmp_path):
        out_path = tmp_path / "excl.yaml"
        excl = [{
            "target": {"type": "path", "value": "X/"},
            "checks": ["orphan"],
            "mode": "forever",  # invalid
            "reason": "test",
        }]
        rc = write_config(_simple_choices(tmp_path, excl), str(out_path))
        assert rc != 0

    def test_missing_reason_exits_nonzero(self, tmp_path):
        out_path = tmp_path / "excl.yaml"
        excl = [{
            "target": {"type": "path", "value": "X/"},
            "checks": ["orphan"],
            "mode": "permanent",
            # no reason
        }]
        rc = write_config(_simple_choices(tmp_path, excl), str(out_path))
        assert rc != 0

    def test_invalid_choices_json_exits_nonzero(self, tmp_path):
        """Choices file containing invalid JSON must cause nonzero exit."""
        out_path = tmp_path / "excl.yaml"
        bad_choices = tmp_path / "bad-choices.json"
        bad_choices.write_text("not-valid-json{{", encoding="utf-8")
        rc = write_config(str(bad_choices), str(out_path))
        assert rc != 0

    def test_missing_choices_file_exits_nonzero(self, tmp_path):
        """A choices file path that does not exist must cause nonzero exit."""
        out_path = tmp_path / "excl.yaml"
        rc = write_config(str(tmp_path / "nonexistent-choices.json"), str(out_path))
        assert rc != 0

    def test_multiple_exclusions_all_written(self, tmp_path):
        out_path = tmp_path / "excl.yaml"
        excl = [
            {"target": {"type": "path", "value": "Calendar/"}, "checks": ["unparented"], "mode": "permanent", "reason": "daily notes"},
            {"target": {"type": "path", "value": "Archive/"}, "checks": "all", "mode": "permanent", "reason": "archived"},
        ]
        rc = write_config(_simple_choices(tmp_path, excl), str(out_path))
        assert rc == 0
        data = yaml.safe_load(out_path.read_text())
        schema = _load_exclusions_schema()
        jsonschema.validate(instance=data, schema=schema)
        assert len(data["exclusions"]) == 2

    def test_output_dir_created_if_missing(self, tmp_path):
        out_path = tmp_path / "nested" / "deep" / "excl.yaml"
        rc = write_config(_simple_choices(tmp_path, []), str(out_path))
        assert rc == 0
        assert out_path.exists()

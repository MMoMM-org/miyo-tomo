#!/usr/bin/env python3
# version: 0.2.0
"""test_review_read_previous.py — review-read.py reads the previous review notes in its one paced pass and
writes them to the stage (spec 047 T3.2; ADR-5; PRD F2-AC6, F3-AC1, F3-AC2, F3-AC3).

WHAT THIS GUARDS, on the fake vault of tests/review_privacy_fixture.py through the script:
- the month walkthrough (SDD Implementation Examples): 2026-03 reads 2026-02 (found) and 2025-Q4 (missing);
  the quarter walkthrough: 2026-Q1 reads 2025-Q4 (missing) — the fixture's quarterly folder is empty, and an
  empty listing is `missing` with no cause (owner 2026-11-23, ADR-5 v1.6); a quarterly folder holding a note
  of another quarter is `missing` too;
- `report.previous` on stdout and in manifest.json: kind, name, role, path, state, cause?, partly_read,
  never the note's text;
- `previous/<kind>-<name>.json` per previous period, stamped with the read id, a found note's sections as
  line arrays, listed in `manifest.files.previous`; load gives the sections back as text;
- one summary (calls, retried, waited_s) covers the period's notes and the previous notes (F2-AC6).

Fakes only: synthetic notes, no live Kado.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from lib import review_stage as rs  # noqa: E402
from lib.kado_client import _MAX_RETRIES  # noqa: E402
from review_privacy_fixture import (  # noqa: E402
    CONFIG, DAILY, MONTHLY, QUARTER_CONFIG, QUARTERLY, build_vault,
)

TODAY = "2026-11-11"
FEB = f"{MONTHLY}2026-02.md"
OTHER_QUARTER = f"{QUARTERLY}2025-Q3.md"       # a note of another quarter: the listing answers, no 2025-Q4
ROW_KEYS = {"kind", "name", "role", "path", "state", "partly_read"}


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("review_read_previous_script", SCRIPTS_DIR / "review-read.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
    return tmp_path


def _read(mod, monkeypatch, capsys, instance, config, vault, period, kind):
    (instance / "config" / "vault-config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(mod, "KadoClient", lambda: vault)
    code = mod.main(["--profiles-dir", "profiles", "--today", TODAY, "--period", period, "--kind", kind])
    out, err = capsys.readouterr()
    assert code == 0 and err == "", err
    return json.loads(out)


def _vault(*, quarter: bool = False, other_quarter: bool = False):
    vault = build_vault(quarter=quarter)
    if other_quarter:
        vault.files[OTHER_QUARTER] = "# 2025-Q3\n\n## Theme\n- the Q3 theme\n"
    return vault


def _stage(instance: Path, stem: str) -> Path:
    return instance / "tomo-tmp" / "review" / stem


def _manifest(instance: Path, stem: str) -> dict:
    return json.loads((_stage(instance, stem) / "manifest.json").read_text(encoding="utf-8"))


# ── the month walkthrough: 2026-02 found, 2025-Q4 missing ──

def test_the_month_reads_its_previous_month_and_quarter(mod, instance, monkeypatch, capsys):
    out = _read(mod, monkeypatch, capsys, instance, CONFIG, _vault(), "2026-03", "month")
    assert out["status"] == "ok" and out["nothing_to_review"] is False
    rows = out["report"]["previous"]
    assert rows == [
        {"kind": "month", "name": "2026-02", "role": "previous-month", "path": FEB, "state": "found",
         "partly_read": False},
        {"kind": "quarter", "name": "2025-Q4", "role": "previous-quarter", "path": None, "state": "missing",
         "partly_read": False}]
    manifest = _manifest(instance, "2026-03_review")
    assert manifest["report"]["previous"] == rows
    assert manifest["files"]["previous"] == ["month-2026-02.json", "quarter-2025-Q4.json"]
    stage = _stage(instance, "2026-03_review")
    found = json.loads((stage / "previous" / "month-2026-02.json").read_text(encoding="utf-8"))
    assert found["read_id"] == out["read_id"] == manifest["read_id"]
    assert found["sections"]["Theme"] == ["month text [[2026-02-02]]"]
    assert found["sections"]["Reflections"] == ["own reflections"]
    missing = json.loads((stage / "previous" / "quarter-2025-Q4.json").read_text(encoding="utf-8"))
    assert missing == {"read_id": out["read_id"], "kind": "quarter", "name": "2025-Q4",
                       "role": "previous-quarter", "path": None, "state": "missing", "partly_read": False}
    loaded = rs.load(stage)["previous"]
    assert loaded[0]["sections"]["Theme"] == "month text [[2026-02-02]]"


def test_the_report_carries_no_previous_note_text(mod, instance, monkeypatch, capsys):
    out = _read(mod, monkeypatch, capsys, instance, CONFIG, _vault(), "2026-03", "month")
    printed = json.dumps(out)
    stored = json.dumps(_manifest(instance, "2026-03_review"))
    for text in ("month text", "own reflections", "the Q3 theme"):
        assert text not in printed and text not in stored
    assert all(set(r) <= ROW_KEYS | {"cause"} for r in out["report"]["previous"])


# ── the quarter walkthrough: 2025-Q4 missing ──

def test_the_quarter_reads_its_previous_quarter(mod, instance, monkeypatch, capsys):
    out = _read(mod, monkeypatch, capsys, instance, QUARTER_CONFIG, _vault(quarter=True), "2026-Q1", "quarter")
    assert out["status"] == "ok"
    assert out["report"]["previous"] == [
        {"kind": "quarter", "name": "2025-Q4", "role": "previous-quarter", "path": None, "state": "missing",
         "partly_read": False}]
    assert _manifest(instance, "2026-Q1_review")["files"]["previous"] == ["quarter-2025-Q4.json"]


@pytest.mark.parametrize("other_quarter", [False, True], ids=["empty-folder", "another-quarter"])
def test_a_quarterly_folder_without_the_note_is_missing(mod, instance, monkeypatch, capsys, other_quarter):
    # owner 2026-11-23: an empty listing is "no note found" (state missing, no cause), like a listing without it
    vault = _vault(quarter=True, other_quarter=other_quarter)
    out = _read(mod, monkeypatch, capsys, instance, QUARTER_CONFIG, vault, "2026-Q1", "quarter")
    (row,) = out["report"]["previous"]
    assert (row["state"], row["path"]) == ("missing", None) and "cause" not in row
    assert out["status"] == "ok" and out["nothing_to_review"] is False, "the review goes on"


# ── one paced pass, one summary (F2-AC6) ──

def test_one_summary_covers_the_period_and_the_previous_notes(mod, instance, monkeypatch, capsys):
    vault = _vault()
    vault.rate_limit(f"{DAILY}2026-03-23.md", failures=_MAX_RETRIES + 1)
    vault.rate_limit(FEB, failures=_MAX_RETRIES + 1)
    out = _read(mod, monkeypatch, capsys, instance, CONFIG, vault, "2026-03", "month")
    report = out["report"]
    assert report["calls"] == vault.call_count and report["retried"] == vault.attempt_count - vault.call_count
    assert report["retried"] >= 2 * _MAX_RETRIES, "both turned-away reads are in the one counter"
    assert report["not_read"] == [] and report["advice"] == ["raise-kado-limit"]
    assert report["previous"][0]["state"] == "found"
    assert vault.events.count(("read_note", FEB)) == 2, "the previous note was retried by the one end pass"

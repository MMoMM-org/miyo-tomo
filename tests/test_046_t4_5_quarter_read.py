#!/usr/bin/env python3
# version: 0.2.0
"""test_046_t4_5_quarter_read.py — review-doc.py on a quarter's stage (spec 046 T4.5; spec 047 T2.4; PRD F6-AC6,
047 F2-AC4).

A quarter's read was ``read-index.json`` plus one month part each (046 T3.4); since spec 047 T2.4 it is the
stage of ``lib/review_stage`` (a day file per day, child files, context.json, the manifest). On
tests/review_fake_vault with a quarter staged through ``review_stage.write``:
- ``write`` loads the stage through ``review_stage.load``: the source rule resolves dailies and monthly notes of
  every month, the quarter groups and marks render, the section checks and ``sections-changed`` run on the
  stored ``sections``; ``replace`` (needs-confirm) loads it too
- a day file missing or broken is ``read-invalid``, no manifest ``read-missing``, before any Kado call
- clean-up: success and ``replace --abort`` remove every content file of the stage (a stale legacy part too)
  and ``proposals.json``; a failed write keeps them all
- the habits count and average every day of the quarter that carries a value (047 F2-AC4)

RED before 047 T2.4: ``review-doc.py`` loaded ``read*.json`` through ``review_read_parts``, so a stage was
``read-missing``. All data is synthetic.
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

from review_fake_vault import ReviewFakeVault, split_frontmatter  # noqa: E402
from lib import review_stage  # noqa: E402
from lib.kado_client import KadoToolError  # noqa: E402
from lib.period import ISO  # noqa: E402
from test_review_doc import MONTHLY, WEEKLY, _config, _daily, _day, item, proposals, week_read  # noqa: E402

SCRIPT_PATH = SCRIPTS_DIR / "review-doc.py"
STEM = "2026-Q1_review"
DOC_PATH = "100 Inbox/2026-Q1 Review.md"
TEMPLATE = "Templates/t_quarterly.md"         # a saved name ends in .md (review_templates.template_name)
MARKER = "MARKER-45q private"
DAYS = [f"2026-{m:02d}-{d:02d}" for m in (1, 2, 3) for d in (5, 15, 25)]
ROWS = [{"id": "s1", "heading": "Highlights", "level": 2, "parent": None, "occurrence": 1,
         "description": "what stood out", "placement": "end"}]


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("review_doc_quarter_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _quarter_config(instance: Path, rows=None) -> None:
    _config(instance, trackers=False)
    path = instance / "config" / "vault-config.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["concepts"]["calendar"]["granularities"]["quarterly"] = {"enabled": True, "path": "Calendar/304 Quarterly/"}
    cfg["naming"]["calendar_patterns"]["quarterly"] = "YYYY-[Q]Q"
    cfg["review"]["quarterly"] = {"heading": "Tomo Review", "place": {"anchor": "Reflections", "placement": "inside"},
                                  "own_sections": ["Reflections"]}
    if rows is not None:
        cfg.setdefault("templates", {})["mapping"] = {"quarterly": TEMPLATE}
        cfg["review"]["quarterly"]["sections"] = {TEMPLATE: rows}
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")


@pytest.fixture
def inst(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
    _quarter_config(tmp_path)
    return tmp_path


def quarter_read(sections=None) -> dict:
    read = week_read(period={"kind": "quarter", "name": "2026-Q1", "start": "2026-01-01", "end": "2026-03-31"},
                     days=[_day(d) for d in DAYS])
    read["weekly"] = [{"path": f"{WEEKLY}2026-W07.md", "week": "2026-W07", "overlap_days": 7, "week_text": {}}]
    read["monthly"] = [{"path": f"{MONTHLY}2026-02.md", "month": "2026-02", "overlap_days": 28,
                        "duplicate": False, "month_text": {"Rückblick": "x"}}]
    read["only_in_monthly_links"], read["dailies_not_in_monthly"] = [], []
    if sections is not None:
        read["sections"] = sections
    return read


def stage_dir(inst: Path) -> Path:
    return inst / "tomo-tmp" / "review" / STEM


def stage_quarter(inst: Path, read: dict, props) -> Path:
    folder = stage_dir(inst)
    review_stage.write(folder, read, stem=STEM, rule=ISO,
                       sections_digest=review_stage.sections_digest(read.get("sections")))
    path = folder / "proposals.json"
    path.write_text(json.dumps(props), encoding="utf-8")
    return path


def run(script, monkeypatch, capsys, argv, fake):
    monkeypatch.setattr(script, "KadoClient", fake)
    code = script.main(["--profiles-dir", "profiles"] + argv)
    out, err = capsys.readouterr()
    assert MARKER not in out and MARKER not in err, "text leaked to stdout/stderr"
    assert code == 0, err
    return json.loads(out)


def write(script, monkeypatch, capsys, inst, props, fake=None, read=None, command="write", *extra):
    path = stage_quarter(inst, read or quarter_read(), props)
    fake = fake or ReviewFakeVault({})
    argv = [command, "--stem", STEM, "--proposals", str(path), "--run-id", "r-test", *extra]
    return run(script, monkeypatch, capsys, argv, fake), fake


def body_of(fake) -> list:
    return split_frontmatter(fake.text(DOC_PATH))[1].splitlines()


def names(inst: Path) -> list:
    return sorted(p.name for p in stage_dir(inst).iterdir())


STAGE_FILES = ["children", "context.json", "days", "manifest.json", "weeks.json"]
PROPS = proposals(done=[item(MARKER + " done", "2026-01-05", _daily("2026-03-25"), "2025-12-31")],
                  open=[item("outside only", "2025-12-31")],
                  monthly_only=[item("only there", f"{MONTHLY}2026-02.md")])


# ---------------------------------------------------------------- the loader feeds every check

def test_the_stage_holds_every_month(inst):
    """Guard: the fixture is a real quarter stage, so a test below that passes reads day files of three months."""
    stage_quarter(inst, quarter_read(), PROPS)
    days = sorted(p.name for p in (stage_dir(inst) / "days").iterdir())
    assert days == [f"{d}.json" for d in DAYS] and {d[:7] for d in DAYS} == {"2026-01", "2026-02", "2026-03"}
    assert sorted(p.name for p in (stage_dir(inst) / "children").iterdir()) == ["monthly-2026-02.json",
                                                                             "weekly-2026-W07.json"]


def test_a_quarter_write_resolves_sources_across_all_months(script, inst, monkeypatch, capsys):
    out, fake = write(script, monkeypatch, capsys, inst, PROPS)
    assert out["status"] == "written", out
    assert out["doc_path"] == DOC_PATH
    assert out["counts"]["done"] == 1 and out["counts"]["monthly_only"] == 1
    assert out["counts"]["open"] == 0
    assert out["rejected"] == [{"group": "open", "index": 0, "reason": "no-source-in-period"}]
    body = body_of(fake)
    done = [ln for ln in body if MARKER in ln]
    assert done and "[[2026-01-05]]" in done[0] and "[[2026-03-25]]" in done[0] and "2025-12-31" not in done[0]
    assert any("only there ([[2026-02]])" in ln for ln in body)


def test_a_quarter_document_renders_the_quarter_groups(script, inst, monkeypatch, capsys):
    out, fake = write(script, monkeypatch, capsys, inst, PROPS)
    heads = [ln for ln in body_of(fake) if ln.startswith("## ")]
    assert heads[-2:] == ["## Nur in den Monatsreviews", "## Nicht in den Monatsreviews"]
    assert out["counts"]["not_in_monthly"] == 0


def test_a_mapped_quarter_checks_sections_and_renders_the_quarter_marks(script, inst, monkeypatch, capsys):
    _quarter_config(inst, ROWS)
    defs = [{"key": "s1", "heading": "Highlights", "level": 2, "parent": None, "description": "what stood out",
             "keywords": [], "groups": [], "cap": 8}]
    props = {"language": "de", "groups": {}, "sections": [{"key": "s1", "items": [
        {**item("only monthly", f"{MONTHLY}2026-02.md"), "mark": "monthly_only"},
        {**item("never monthly", "2026-03-15"), "mark": "not_in_monthly"}]}]}
    out, fake = write(script, monkeypatch, capsys, inst, props, read=quarter_read(sections=defs))
    assert out["status"] == "written", out
    body = "\n".join(body_of(fake))
    assert "- [x] only monthly ([[2026-02]]) · nur im Monatsrückblick %%t1%%" in body
    assert "- [x] never monthly ([[2026-03-15]]) · in keinem Monatsrückblick %%t2%%" in body


def test_a_quarter_whose_index_sections_differ_from_the_rows_is_sections_changed(script, inst, monkeypatch, capsys):
    _quarter_config(inst, ROWS)
    defs = [{"key": "s9", "heading": "Gone", "level": 2, "parent": None, "description": "d",
             "keywords": [], "groups": [], "cap": 8}]
    fake = ReviewFakeVault({})
    out, _ = write(script, monkeypatch, capsys, inst, proposals(), fake, read=quarter_read(sections=defs))
    assert out["status"] == "refused" and out["problems"] == ["sections-changed"]
    assert fake.call_count == 0 and names(inst) == sorted(STAGE_FILES + ["proposals.json"])


def test_replace_needs_confirm_reads_the_quarter_through_the_loader(script, inst, monkeypatch, capsys):
    stage_quarter(inst, quarter_read(), PROPS)
    out = run(script, monkeypatch, capsys, ["replace", "--stem", STEM], ReviewFakeVault({}))
    assert out == {"status": "needs-confirm", "stem": STEM, "doc_path": DOC_PATH}


# ---------------------------------------------------------------- a missing or broken file

def _refused_before_kado(script, monkeypatch, capsys, inst) -> dict:
    fake = ReviewFakeVault({})
    out = run(script, monkeypatch, capsys,
              ["write", "--stem", STEM, "--proposals", str(stage_dir(inst) / "proposals.json")], fake)
    assert out["status"] == "refused" and fake.call_count == 0
    return out


def test_a_missing_day_file_is_read_invalid_and_keeps_the_files(script, inst, monkeypatch, capsys):
    stage_quarter(inst, quarter_read(), PROPS)
    (stage_dir(inst) / "days" / "2026-02-15.json").unlink()
    assert _refused_before_kado(script, monkeypatch, capsys, inst)["problems"] == ["read-invalid"]
    assert names(inst) == sorted(STAGE_FILES + ["proposals.json"])


def test_a_day_file_that_is_not_json_is_read_invalid(script, inst, monkeypatch, capsys):
    stage_quarter(inst, quarter_read(), PROPS)
    (stage_dir(inst) / "days" / "2026-03-25.json").write_text("{broken", encoding="utf-8")
    assert _refused_before_kado(script, monkeypatch, capsys, inst)["problems"] == ["read-invalid"]


def test_a_stage_without_its_manifest_is_read_missing(script, inst, monkeypatch, capsys):
    stage_quarter(inst, quarter_read(), PROPS)
    (stage_dir(inst) / "manifest.json").unlink()
    assert _refused_before_kado(script, monkeypatch, capsys, inst)["problems"] == ["read-missing"]


# ---------------------------------------------------------------- clean-up

def test_a_written_quarter_removes_every_content_file_and_the_proposals(script, inst, monkeypatch, capsys):
    stale = stage_dir(inst) / "read-2025-12.json"
    stage_dir(inst).mkdir(parents=True)
    stale.write_text('{"month":"2025-12","days":[]}\n', encoding="utf-8")
    path = stage_quarter(inst, quarter_read(), PROPS)
    stale.write_text('{"month":"2025-12","days":[]}\n', encoding="utf-8")         # left after the stage write
    out = run(script, monkeypatch, capsys, ["write", "--stem", STEM, "--proposals", str(path), "--run-id", "r"],
              ReviewFakeVault({}))
    assert out["status"] == "written"
    assert names(inst) == ["meta.json"]


def test_a_failed_quarter_write_keeps_every_stage_file(script, inst, monkeypatch, capsys):
    fake = ReviewFakeVault({})
    fake.fail[("write_note", DOC_PATH)] = KadoToolError("kado-write returned an error: denied")
    out, _ = write(script, monkeypatch, capsys, inst, PROPS, fake)
    assert out["status"] == "stopped" and out["problems"] == ["kado-write-failed"]
    assert names(inst) == sorted(STAGE_FILES + ["proposals.json"])


def test_replace_abort_removes_every_content_file_of_a_quarter_and_keeps_meta(script, inst, monkeypatch, capsys):
    stage_quarter(inst, quarter_read(), PROPS)
    (stage_dir(inst) / "meta.json").write_text('{"stem": "2026-Q1_review"}\n', encoding="utf-8")
    out = run(script, monkeypatch, capsys, ["replace", "--stem", STEM, "--abort"], ReviewFakeVault({}))
    assert out == {"status": "aborted", "stem": STEM}
    assert names(inst) == ["meta.json"]


def test_an_abort_keeps_files_that_are_not_stage_content(script, inst, monkeypatch, capsys):
    folder = inst / "tomo-tmp" / "review" / "2026-W13_review"
    folder.mkdir(parents=True)
    for name in ("read.json", "proposals.json", "meta.json", "notes.txt"):
        (folder / name).write_text("{}\n", encoding="utf-8")
    out = run(script, monkeypatch, capsys, ["replace", "--stem", "2026-W13_review", "--abort"], ReviewFakeVault({}))
    assert out["status"] == "aborted"
    assert sorted(p.name for p in folder.iterdir()) == ["meta.json", "notes.txt"]


# ---------------------------------------------------------------- 047 F2-AC4: habits over every day

def _habit_lines(fake) -> list:
    body = body_of(fake)
    lines = body[body.index("## Gewohnheiten") + 1:]
    return lines[:next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))]


def test_the_habits_count_and_average_every_day_of_the_quarter_that_carries_a_value(script, inst, monkeypatch,
                                                                                      capsys):
    """F2-AC4: a boolean tracker counts and a number tracker averages over every valued day of all three months,
    loaded from the day files of the stage."""
    _config(inst, trackers=True, fields=[{"name": "Sport", "type": "boolean"}, {"name": "Sleep", "type": "integer"}])
    _quarter_config_keep(inst)
    read = quarter_read()
    read["days"] = [_day(d, Sport="ja", Sleep=str(6 + i % 3)) for i, d in enumerate(DAYS)]
    out, fake = write(script, monkeypatch, capsys, inst, PROPS, read=read)
    assert out["status"] == "written", out
    lines = _habit_lines(fake)
    assert any(ln.startswith("- [x] Sport") and f" {len(DAYS)} " in ln for ln in lines), lines
    assert any(ln.startswith("- [x] Sleep: Durchschnitt 7,0") and f" {len(DAYS)} " in ln for ln in lines), lines


def _quarter_config_keep(instance: Path) -> None:
    """The quarter setup on top of the config ``_config`` just wrote (trackers kept)."""
    path = instance / "config" / "vault-config.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["concepts"]["calendar"]["granularities"]["quarterly"] = {"enabled": True, "path": "Calendar/304 Quarterly/"}
    cfg["naming"]["calendar_patterns"]["quarterly"] = "YYYY-[Q]Q"
    cfg["review"]["quarterly"] = {"heading": "Tomo Review", "place": {"anchor": "Reflections", "placement": "inside"},
                                  "own_sections": ["Reflections"]}
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

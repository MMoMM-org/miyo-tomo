#!/usr/bin/env python3
# version: 0.1.1
"""test_046_t4_5_quarter_read.py — review-doc.py on a quarter's split read (spec 046 T4.5; ADR-7; PRD F6-AC6).

A quarter's read is ``read-index.json`` plus one ``read-<YYYY-MM>.json`` per month (T3.4). On
tests/review_fake_vault with a quarter staged through ``lib/review_read_parts.write``:
- ``write`` loads all parts through ``review_read_parts.load``: the source rule resolves dailies and
  monthly notes from any part, the quarter groups and marks render, the section checks and
  ``sections-changed`` run on the index's ``sections``; ``replace`` (needs-confirm) loads it too
- a listed part missing or broken is ``read-invalid``, no read file ``read-missing``, before any Kado call
- clean-up: success and ``replace --abort`` remove every read file of the stage (index, parts, a stale
  part of another quarter) and ``proposals.json``; a failed write keeps them all
- the T3.4 review nits: a part named twice and a part name that only ``re.match`` admits are refused

RED before T4.5: ``review-doc.py`` read ``read.json`` only (a quarter stage is ``read-missing``), and
``_part_names`` accepted a duplicate and a trailing newline. All data is synthetic.
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
from lib import review_read_parts as rp  # noqa: E402
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
    rp.write(folder, rp.files_of(read, ISO))
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


READ_FILES = ["read-2026-01.json", "read-2026-02.json", "read-2026-03.json", "read-index.json"]
PROPS = proposals(done=[item(MARKER + " done", "2026-01-05", _daily("2026-03-25"), "2025-12-31")],
                  open=[item("outside only", "2025-12-31")],
                  monthly_only=[item("only there", f"{MONTHLY}2026-02.md")])


# ---------------------------------------------------------------- the loader feeds every check

def test_the_stage_is_the_split_layout():
    """Guard: the fixture is a real quarter split, so a test below that passes reads parts, not one file."""
    files = rp.files_of(quarter_read(), ISO)
    assert sorted(files) == READ_FILES
    index = json.loads(files["read-index.json"])
    assert "days" not in index and "monthly" not in index
    assert json.loads(files["read-2026-02.json"])["monthly"][0]["month"] == "2026-02"


def test_a_quarter_write_resolves_sources_across_all_month_parts(script, inst, monkeypatch, capsys):
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
    assert fake.call_count == 0 and names(inst) == sorted(READ_FILES + ["proposals.json"])


def test_replace_needs_confirm_reads_the_quarter_through_the_loader(script, inst, monkeypatch, capsys):
    stage_quarter(inst, quarter_read(), PROPS)
    out = run(script, monkeypatch, capsys, ["replace", "--stem", STEM], ReviewFakeVault({}))
    assert out == {"status": "needs-confirm", "stem": STEM, "doc_path": DOC_PATH}


# ---------------------------------------------------------------- a missing or broken part

def _refused_before_kado(script, monkeypatch, capsys, inst) -> dict:
    fake = ReviewFakeVault({})
    out = run(script, monkeypatch, capsys,
              ["write", "--stem", STEM, "--proposals", str(stage_dir(inst) / "proposals.json")], fake)
    assert out["status"] == "refused" and fake.call_count == 0
    return out


def test_a_missing_month_part_is_read_invalid_and_keeps_the_files(script, inst, monkeypatch, capsys):
    stage_quarter(inst, quarter_read(), PROPS)
    (stage_dir(inst) / "read-2026-02.json").unlink()
    assert _refused_before_kado(script, monkeypatch, capsys, inst)["problems"] == ["read-invalid"]
    assert names(inst) == ["proposals.json", "read-2026-01.json", "read-2026-03.json", "read-index.json"]


def test_a_part_that_is_not_json_is_read_invalid(script, inst, monkeypatch, capsys):
    stage_quarter(inst, quarter_read(), PROPS)
    (stage_dir(inst) / "read-2026-03.json").write_text("{broken", encoding="utf-8")
    assert _refused_before_kado(script, monkeypatch, capsys, inst)["problems"] == ["read-invalid"]


def test_parts_without_their_index_are_read_missing(script, inst, monkeypatch, capsys):
    stage_quarter(inst, quarter_read(), PROPS)
    (stage_dir(inst) / "read-index.json").unlink()
    assert _refused_before_kado(script, monkeypatch, capsys, inst)["problems"] == ["read-missing"]


# ---------------------------------------------------------------- clean-up

def test_a_written_quarter_removes_every_read_file_and_the_proposals(script, inst, monkeypatch, capsys):
    stale = stage_dir(inst) / "read-2025-12.json"
    stage_dir(inst).mkdir(parents=True)
    stale.write_text(rp.encode({"month": "2025-12", "days": []}), encoding="utf-8")
    out, _ = write(script, monkeypatch, capsys, inst, PROPS)
    assert out["status"] == "written"
    assert names(inst) == ["meta.json"]


def test_a_failed_quarter_write_keeps_every_read_file(script, inst, monkeypatch, capsys):
    fake = ReviewFakeVault({})
    fake.fail[("write_note", DOC_PATH)] = KadoToolError("kado-write returned an error: denied")
    out, _ = write(script, monkeypatch, capsys, inst, PROPS, fake)
    assert out["status"] == "stopped" and out["problems"] == ["kado-write-failed"]
    assert names(inst) == sorted(READ_FILES + ["proposals.json"])


def test_replace_abort_removes_every_read_file_of_a_quarter_and_keeps_meta(script, inst, monkeypatch, capsys):
    stage_quarter(inst, quarter_read(), PROPS)
    (stage_dir(inst) / "meta.json").write_text('{"stem": "2026-Q1_review"}\n', encoding="utf-8")
    out = run(script, monkeypatch, capsys, ["replace", "--stem", STEM, "--abort"], ReviewFakeVault({}))
    assert out == {"status": "aborted", "stem": STEM}
    assert names(inst) == ["meta.json"]


def test_a_week_abort_still_removes_only_read_json_and_the_proposals(script, inst, monkeypatch, capsys):
    folder = inst / "tomo-tmp" / "review" / "2026-W13_review"
    folder.mkdir(parents=True)
    for name in ("read.json", "proposals.json", "meta.json", "notes.txt"):
        (folder / name).write_text("{}\n", encoding="utf-8")
    out = run(script, monkeypatch, capsys, ["replace", "--stem", "2026-W13_review", "--abort"], ReviewFakeVault({}))
    assert out["status"] == "aborted"
    assert sorted(p.name for p in folder.iterdir()) == ["meta.json", "notes.txt"]


# ---------------------------------------------------------------- the T3.4 review nits

def _index_with(tmp_path: Path, part_list: list) -> Path:
    stage = tmp_path / "stage"
    rp.write(stage, rp.files_of(quarter_read(), ISO))
    index = json.loads((stage / "read-index.json").read_text(encoding="utf-8"))
    index["parts"] = part_list
    (stage / "read-index.json").write_text(rp.encode(index), encoding="utf-8")
    return stage


def test_a_part_named_twice_is_refused(tmp_path):
    stage = _index_with(tmp_path, ["read-2026-01.json", "read-2026-01.json", "read-2026-02.json",
                                   "read-2026-03.json"])
    with pytest.raises(rp.ReadFilesInvalid, match="twice"):
        rp.load(stage)


def test_a_part_name_with_a_trailing_newline_is_refused_as_a_name(tmp_path):
    stage = _index_with(tmp_path, ["read-2026-01.json\n", "read-2026-02.json", "read-2026-03.json"])
    with pytest.raises(rp.ReadFilesInvalid, match="names a part that is not"):
        rp.load(stage)


def test_stage_files_lists_only_exact_part_names(tmp_path):
    stage = tmp_path / "stage"
    stage.mkdir()
    for name in ("read-2026-01.json", "read-2026-01.json\n", "read-2026-01.json.bak"):
        (stage / name).write_text("{}", encoding="utf-8")
    assert [p.name for p in rp.stage_files(stage)] == ["read-2026-01.json"]

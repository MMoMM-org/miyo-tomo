#!/usr/bin/env python3
# version: 0.1.2
"""test_047_t4_4_condense_gate.py — the document waits for the condensing; the walk condenses (spec 047 T4.4).

PRD F6-AC1, SDD ADR-4, Internal API Changes (`condense-incomplete`), Application Data Models (`Sources`),
Implementation Gotchas (`replace --confirm` keeps `condensed.json` and `carryover.json`):
- `review-doc.py write` refuses `condense-incomplete` with no `condensed.json` or a unit `pending` / `retry`,
  before any Kado call, the stage kept; a `failed` unit is complete (named, not waited for); the carryover's
  state is no part of the gate;
- `review_stage.load` gives `condensed` read-id-checked and `carryover` only when its state is `passed`;
  `review_stage.units` gives weeks.json's units read-id-checked;
- `review_doc.Sources` leaves out the dailies of a not-condensed unit, so an item resting only on one of its
  days is rejected exactly as an item outside the period is (spec 045), and its link is dropped from a mixed one;
- `replace --confirm` after `review-exists` renders from the kept `condensed.json` and `carryover.json`;
- the e2e walk condenses: growth candidates from `growth/` files sourced by their creation day pass check, and
  a walk that skips the condensing is refused.
All data is synthetic.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import INBOX, MONTH, MONTH_PERIOD, MONTH_STEM, WEEK, WEEK_PERIOD, WEEK_STEM, Walk  # noqa: E402
from review_fake_vault import ReviewFakeVault  # noqa: E402
from review_privacy_fixture import CONFIG, MOCS, condense, condense_files, proposals  # noqa: E402
import test_review_doc as trd  # noqa: E402
from lib import review_doc as rd  # noqa: E402
from lib import review_stage  # noqa: E402

CONDENSED, CARRYOVER = "condensed.json", "carryover.json"
W13_TARGET = {f"{trd.WEEKLY}2026-W13.md": "# W13\n\n## In my own words\n"}


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("review_doc_t44_script", trd.SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def inst(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
    trd._config(tmp_path)
    return tmp_path


def _condensed(folder: Path) -> dict:
    return json.loads((folder / CONDENSED).read_text(encoding="utf-8"))


def _set_unit(folder: Path, unit: str, state: str) -> None:
    doc = _condensed(folder)
    doc["units"][unit] = {"state": state, "attempts": 2 if state == "failed" else 1}
    (folder / CONDENSED).write_text(json.dumps(doc), encoding="utf-8")


def _write(script, monkeypatch, capsys, inst, folder_stem, path, fake):
    return trd._run(script, monkeypatch, capsys,
                    ["write", "--stem", folder_stem, "--proposals", str(path), "--run-id", "r-test"], fake)


# ---------------------------------------------------------------- the refusal

def test_write_refuses_a_stage_without_condensed_json(script, inst, monkeypatch, capsys):
    props = trd.proposals(done=[trd.item(trd.MARKER, "2026-03-23")])
    stem, path = trd.stage(inst, trd.week_read(), props, condensed=False)
    fake = ReviewFakeVault(dict(W13_TARGET))
    code, out, _ = _write(script, monkeypatch, capsys, inst, stem, path, fake)
    assert code == 0 and out == {"status": "refused", "stem": stem, "problems": ["condense-incomplete"]}, out
    assert fake.writes == [], "refused before any Kado write"
    assert path.is_file() and (path.parent / "manifest.json").is_file(), "the stage and proposals are kept"


@pytest.mark.parametrize("state", ["pending", "retry"])
def test_write_refuses_a_unit_still_open(script, inst, monkeypatch, capsys, state):
    props = trd.proposals(done=[trd.item("x", "2026-03-23")])
    stem, path = trd.stage(inst, trd.week_read(), props)
    folder = path.parent
    _set_unit(folder, "2026-W13", state)
    fake = ReviewFakeVault(dict(W13_TARGET))
    code, out, _ = _write(script, monkeypatch, capsys, inst, stem, path, fake)
    assert out["status"] == "refused" and out["problems"] == ["condense-incomplete"], out
    assert fake.writes == [] and (folder / CONDENSED).is_file()


def test_the_refusal_comes_before_the_proposals_are_read(script, inst, monkeypatch, capsys):
    stem, path = trd.stage(inst, trd.week_read(), "not json", condensed=False)
    code, out, _ = _write(script, monkeypatch, capsys, inst, stem, path, ReviewFakeVault(dict(W13_TARGET)))
    assert out["problems"] == ["condense-incomplete"], out


def test_a_condensed_stage_is_written(script, inst, monkeypatch, capsys):
    props = trd.proposals(done=[trd.item("x", "2026-03-23")])
    stem, path = trd.stage(inst, trd.week_read(), props)
    fake = ReviewFakeVault(dict(W13_TARGET))
    code, out, _ = _write(script, monkeypatch, capsys, inst, stem, path, fake)
    assert out["status"] == "written", out
    assert not (path.parent / CONDENSED).exists(), "condensed.json is stage content, discarded after the write"


def test_an_open_carryover_does_not_hold_the_document_back(script, inst, monkeypatch, capsys):
    props = trd.proposals(done=[trd.item("x", "2026-03-23")])
    stem, path = trd.stage(inst, trd.week_read(), props)
    doc = _condensed(path.parent)
    doc["carryover"] = {"state": "retry", "attempts": 1, "notes": {}}
    (path.parent / CONDENSED).write_text(json.dumps(doc), encoding="utf-8")
    code, out, _ = _write(script, monkeypatch, capsys, inst, stem, path, ReviewFakeVault(dict(W13_TARGET)))
    assert out["status"] == "written", out



def test_write_refuses_read_invalid_when_weeks_json_holds_no_units(script, inst, monkeypatch, capsys):
    stem, path = trd.stage(inst, trd.week_read(), trd.proposals(done=[trd.item("x", "2026-03-23")]))
    weeks_path = path.parent / "weeks.json"
    weeks = json.loads(weeks_path.read_text(encoding="utf-8"))
    del weeks["units"]
    weeks_path.write_text(json.dumps(weeks), encoding="utf-8")
    fake = ReviewFakeVault(dict(W13_TARGET))
    code, out, _ = _write(script, monkeypatch, capsys, inst, stem, path, fake)
    assert code == 0 and out == {"status": "refused", "stem": stem, "problems": ["read-invalid"]}, out
    assert fake.writes == []


# ---------------------------------------------------------------- load and units

def _staged(tmp_path: Path, previous=()) -> Path:
    read = trd.week_read()
    read["previous"] = list(previous)
    folder = tmp_path / "s"
    review_stage.write(folder, read, stem="s", rule=trd.ISO, sections_digest="none")
    return folder


PREV = {"kind": "week", "name": "2026-W12", "role": "previous-week", "path": "Calendar/302 Weekly/2026-W12.md",
        "state": "found", "partly_read": False, "sections": {"Goals": "- run"}}


def _carry_file(folder: Path) -> dict:
    manifest = review_stage.manifest(folder)
    data = {"read_id": manifest["read_id"],
            "notes": [{"path": PREV["path"], "kind": "week", "name": "2026-W12", "items": 1}],
            "items": [{"id": "c1", "type": "open", "text": "run", "sources": ["2026-W12"]}]}
    (folder / CARRYOVER).write_text(json.dumps(data), encoding="utf-8")
    return data


@pytest.mark.parametrize("state, given", [("passed", True), ("pending", False), ("retry", False),
                                          ("failed", False)])
def test_load_gives_the_carryover_only_when_it_passed(tmp_path, state, given):
    folder = _staged(tmp_path, [PREV])
    data = _carry_file(folder)
    condensed = {"read_id": review_stage.manifest(folder)["read_id"], "units": {},
                 "carryover": {"state": state, "attempts": 1, "notes": {}}}
    (folder / CONDENSED).write_text(json.dumps(condensed), encoding="utf-8")
    loaded = review_stage.load(folder)
    assert loaded["condensed"] == condensed
    assert loaded["carryover"] == (data if given else None)


def test_load_refuses_a_condensed_json_of_another_read(tmp_path):
    folder = _staged(tmp_path)
    (folder / CONDENSED).write_text(json.dumps({"read_id": "another", "units": {}}), encoding="utf-8")
    with pytest.raises(review_stage.StageStale):
        review_stage.load(folder)


def test_load_without_condensed_json_gives_neither(tmp_path):
    folder = _staged(tmp_path, [PREV])
    _carry_file(folder)
    loaded = review_stage.load(folder)
    assert loaded["condensed"] is None and loaded["carryover"] is None


def test_units_are_weeks_json_units_read_id_checked(tmp_path):
    folder = _staged(tmp_path)
    weeks = json.loads((folder / "weeks.json").read_text(encoding="utf-8"))
    assert review_stage.units(folder) == weeks["units"]
    weeks["read_id"] = "another"
    (folder / "weeks.json").write_text(json.dumps(weeks), encoding="utf-8")
    with pytest.raises(review_stage.StageStale):
        review_stage.units(folder)


# ---------------------------------------------------------------- Sources: the failed unit

def test_sources_leave_out_the_days_of_a_not_condensed_unit():
    read = trd.month_read()
    read["not_condensed"] = [{"unit": "2026-W10", "days": [f"2026-03-{d:02d}" for d in range(2, 9)]}]
    sources = rd.Sources.of(read)
    assert sources.daily_of("2026-03-04") is None and sources.daily_of(trd._daily("2026-03-04")) is None
    assert sources.daily_of("2026-03-09") is not None and sources.daily_of("2026-03-01") is not None
    del read["not_condensed"]
    assert rd.Sources.of(read).daily_of("2026-03-04") is not None


def test_an_item_on_a_failed_units_day_is_rejected_as_spec_045_rejects_one(script, inst, monkeypatch, capsys):
    props = trd.proposals(done=[trd.item("on the failed unit", "2026-03-04"),
                                trd.item("outside the period", "2026-04-15"),
                                trd.item("mixed", "2026-03-04", "2026-03-24")])
    stem, path = trd.stage(inst, trd.month_read(), props)
    _set_unit(path.parent, "2026-W10", "failed")
    fake = ReviewFakeVault({f"{trd.MONTHLY}2026-03.md": "# 03\n\n## Reflections\n"})
    code, out, _ = _write(script, monkeypatch, capsys, inst, stem, path, fake)
    assert out["status"] == "written", out
    reasons = {r["index"]: r["reason"] for r in out["rejected"]}
    assert set(reasons) == {0, 1} and reasons[0] == reasons[1], out["rejected"]
    text = next(fake.text(p) for p in fake.writes if p.endswith(" Review.md"))
    mixed = next(line for line in text.split("\n") if "mixed" in line)
    assert "[[2026-03-24]]" in mixed and "2026-03-04" not in mixed, mixed


def test_a_failed_unit_is_not_waited_for(script, inst, monkeypatch, capsys):
    stem, path = trd.stage(inst, trd.month_read(), trd.proposals(done=[trd.item("x", "2026-03-24")]))
    _set_unit(path.parent, "2026-W10", "failed")
    code, out, _ = _write(script, monkeypatch, capsys, inst, stem, path,
                          ReviewFakeVault({f"{trd.MONTHLY}2026-03.md": "# 03\n\n## Reflections\n"}))
    assert out["status"] == "written" and out["rejected"] == [], out


# ---------------------------------------------------------------- the walk

@pytest.fixture
def walk(tmp_path, monkeypatch, capsys, request):
    w = Walk(tmp_path, monkeypatch, capsys, request.node.nodeid, config=CONFIG)
    w.vault._record = w.vault.recorded.append     # per test only: the e2e sweeps own review_e2e_walk.WRITES
    yield w
    assert [p for p in w.vault.recorded if not p.startswith(INBOX)] == []


def test_replace_confirm_renders_from_the_kept_condensed_and_carryover(walk):
    assert walk.pass1(WEEK_PERIOD, WEEK)["status"] == "written"
    assert walk.read(WEEK_PERIOD, WEEK)["status"] == "ok"
    out = walk.condense(WEEK_STEM, carry=True)
    assert out["proposer"]["carried"] is True, "the week's previous note was carried"
    stage = walk.stage(WEEK_STEM)
    kept = {name: (stage / name).read_bytes() for name in (CONDENSED, CARRYOVER)}
    out = walk.write(WEEK_STEM, WEEK, condense=False, carry=True)
    assert out["status"] == "refused" and out["problems"] == ["review-exists"], out
    assert {name: (stage / name).read_bytes() for name in kept} == kept, "the refusal keeps both files"
    out = walk.replace(WEEK_STEM, "--confirm")
    assert out["status"] == "replaced", out
    assert out["previous"][0] == {"kind": "week", "name": "2026-W12", "state": "found", "carried": 1}, out
    assert not (stage / CONDENSED).exists() and not (stage / CARRYOVER).exists(), "discarded after the write"


def test_a_walk_that_skips_the_condensing_is_refused(walk):
    assert walk.read(WEEK_PERIOD, WEEK)["status"] == "ok"
    out = walk.write(WEEK_STEM, WEEK, condense=False)
    assert out["status"] == "refused" and out["problems"] == ["condense-incomplete"], out
    assert walk.vault.recorded == []


def _local_ms(day: str) -> int:
    return int(datetime.combine(date.fromisoformat(day), datetime.min.time()).replace(hour=12).timestamp() * 1000)


def test_the_walk_condenses_growth_candidates_sourced_by_their_creation_day(walk):
    note = f"{MOCS}Topic MOC.md"
    walk.vault.stamp(note, created=_local_ms("2026-03-24"), modified=_local_ms("2026-03-24"))
    assert walk.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    stage = walk.stage(MONTH_STEM)
    plan = walk.run("review-digest", "plan", "--stem", MONTH_STEM)
    files = condense_files(plan, stage)
    growth = [(name, g) for name, d in files.items() if name.startswith("digests/") for g in d["growth"]]
    assert growth == [("digests/2026-W13.json",
                       {"text": "created condensed", "sources": ["2026-03-24"], "notes": [note]})], growth
    assert walk.condense(MONTH_STEM)["units"]["2026-W13"] == {"state": "passed"}
    out = walk.write(MONTH_STEM, MONTH, proposals(MONTH))
    assert out["status"] == "written", out


def test_condense_runs_silently_for_a_staged_read(tmp_path, capsys):
    folder = tmp_path / "review" / "2026-W13_review"
    review_stage.write(folder, trd.week_read(), stem=folder.name, rule=trd.ISO, sections_digest="none")
    out = condense(folder)
    assert out["units"] == {"2026-W13": {"state": "passed"}}
    assert capsys.readouterr() == ("", "")

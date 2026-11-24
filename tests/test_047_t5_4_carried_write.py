#!/usr/bin/env python3
# version: 0.2.0
"""test_047_t5_4_carried_write.py — carried items through ``review-doc.py write`` (spec 047 T5.4).

SDD ADR-6, ADR-12, Internal API Changes (the `carried-*` errors, the `carried-moved` notice, the new
`written` keys); PRD F4-AC10, F5-AC2, F6-AC2, F3-AC11. On tests/review_fake_vault with a week read staged
through lib/review_stage.write and condensed by the fixture agents (one `open` carryover item `c1` per
found previous note under the fixture's opt-in ``carry=True``, sourced by its stem):
- a carried group item is written with its carried label, the previous-note top line counts it, and
  `written` carries `previous`, `not_condensed`, `carry_failed` and `carried_moved`, each only when it
  has a fact (spec 046's result unchanged), counts and names only;
- `coverage` runs once over the document: a carryover id no item lists refuses `carried-missing (c1)`;
  a carried failure is an `errors` entry of `proposals-invalid`, never a `rejected` row;
- a carryover still `pending` or `retry` (or `failed`) at write time with a found note: the document is
  written with the carry-failed top line and no carried label (F6-AC2); a carried item is refused
  `carried-without-carryover`; with no found note there is no carry-failed line;
- with a mapping, `overflow` runs before `over-cap` is counted: a carried item of a full section moves to
  the group of its mark and is reported in `carried_moved`; a full section without a carried item is
  still refused `over-cap`;
- F6-AC2 partly: a found note whose own carry failed (the carryover passed for the other) says "found, not
  taken into account" while the other's item stays carried; with the whole carryover not passed every found
  note says so, beside the one carry-failed line.
All data is synthetic.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import test_review_doc as trd  # noqa: E402
from review_fake_vault import ReviewFakeVault, split_frontmatter  # noqa: E402
from test_046_t4_2_doc_sections import definitions_of, map_config, row  # noqa: E402

PREV_WEEK = f"{trd.WEEKLY}2026-W12.md"
PREV = {"kind": "week", "name": "2026-W12", "role": "previous-week", "path": PREV_WEEK, "state": "found",
        "partly_read": False, "sections": {"Goals": "- run"}}
MISSING = {"kind": "month", "name": "2026-02", "role": "previous-month", "path": None, "state": "missing",
           "partly_read": False}
TARGET = {f"{trd.WEEKLY}2026-W13.md": "# W13\n\n## In my own words\n"}
CARRY_FAILED_DE = "> Die letzten Rückblicke konnten nicht berücksichtigt werden."
PLAIN = trd.item("Aufgeräumt", "2026-03-23")


def carried(text: str, value: str, *sources: str, ids=("c1",)) -> dict:
    return {**trd.item(text, *sources), "carried": value, "carried_ids": list(ids)}


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("review_doc_t54_script", trd.SCRIPT_PATH)
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


def _read(*previous, **overrides) -> dict:
    return trd.week_read(previous=list(previous), **overrides)


def _set_carryover(path: Path, state: str) -> None:
    condensed = path.parent / "condensed.json"
    doc = json.loads(condensed.read_text(encoding="utf-8"))
    doc["carryover"] = {"state": state, "attempts": 1, "notes": {}}
    condensed.write_text(json.dumps(doc), encoding="utf-8")


def _set_note_states(path: Path, states: dict) -> None:
    condensed = path.parent / "condensed.json"
    doc = json.loads(condensed.read_text(encoding="utf-8"))
    doc["carryover"]["notes"] = dict(states)
    condensed.write_text(json.dumps(doc), encoding="utf-8")


def _write(script, monkeypatch, capsys, inst, read, props, *, carryover_state=None, note_states=None):
    stem, path = trd.stage(inst, read, props, carry=True)
    if carryover_state:
        _set_carryover(path, carryover_state)
    if note_states:
        _set_note_states(path, note_states)
    fake = ReviewFakeVault(dict(TARGET))
    code, out, _ = trd._run(script, monkeypatch, capsys,
                            ["write", "--stem", stem, "--proposals", str(path), "--run-id", "r-test"], fake)
    assert code == 0
    return out, fake


def _lines(fake) -> list:
    [path] = [p for p in fake.writes if p.endswith(" Review.md")]
    return split_frontmatter(fake.text(path))[1].splitlines()


# ---------------------------------------------------------------- written

def test_a_carried_group_item_is_written_with_its_label_and_counted_at_the_top(script, inst, monkeypatch, capsys):
    props = trd.proposals(done=[PLAIN], open=[carried("Jana anrufen", "not_mentioned", "2026-W12")])
    out, fake = _write(script, monkeypatch, capsys, inst, _read(PREV, MISSING), props)
    assert out["status"] == "written" and out["rejected"] == [], out
    lines = _lines(fake)
    assert "- [x] Jana anrufen ([[2026-W12]]) · nicht mehr erwähnt (letzter Rückblick) %%t2%%" in lines
    assert "> Letzter Rückblick · Woche 2026-W12: gefunden, 1 übernommen" in lines
    assert "> Letzter Rückblick · Monat 2026-02: keine Notiz für 2026-02 gefunden" in lines
    assert CARRY_FAILED_DE not in lines
    assert out["previous"] == [{"kind": "week", "name": "2026-W12", "state": "found", "carried": 1},
                               {"kind": "month", "name": "2026-02", "state": "missing", "carried": 0}]
    assert not {"not_condensed", "carry_failed", "carried_moved"} & set(out), "each key only when it has a fact"


def test_the_written_keys_carry_no_text_or_path(script, inst, monkeypatch, capsys):
    props = trd.proposals(done=[PLAIN], open=[carried(trd.MARKER, "not_mentioned", "2026-W12")])
    out, _ = _write(script, monkeypatch, capsys, inst, _read(PREV), props)
    extra = json.dumps({k: out.get(k) for k in ("previous", "not_condensed", "carry_failed", "carried_moved")})
    assert "Calendar/" not in extra and "run" not in extra and trd.MARKER not in extra


def test_a_failed_unit_is_named_in_written(script, inst, monkeypatch, capsys):
    stem, path = trd.stage(inst, trd.month_read(), trd.proposals(done=[trd.item("x", "2026-03-24")]))
    condensed = path.parent / "condensed.json"
    doc = json.loads(condensed.read_text(encoding="utf-8"))
    doc["units"]["2026-W10"] = {"state": "failed", "attempts": 2}
    condensed.write_text(json.dumps(doc), encoding="utf-8")
    fake = ReviewFakeVault({f"{trd.MONTHLY}2026-03.md": "# 03\n\n## Reflections\n"})
    _, out, _ = trd._run(script, monkeypatch, capsys,
                         ["write", "--stem", stem, "--proposals", str(path), "--run-id", "r-test"], fake)
    assert out["status"] == "written", out
    assert [u["unit"] for u in out["not_condensed"]] == ["2026-W10"]
    assert "> Nicht verdichtet: 2026-W10 (2026-03-02 – 2026-03-08)" in _lines(fake)


# ---------------------------------------------------------------- refusals

def test_coverage_refuses_a_carryover_id_no_item_lists(script, inst, monkeypatch, capsys):
    out, fake = _write(script, monkeypatch, capsys, inst, _read(PREV), trd.proposals(done=[PLAIN]))
    assert out == {"status": "refused", "stem": "2026-W13_review", "problems": ["proposals-invalid"],
                   "errors": ["carried-missing (c1)"]}, out
    assert fake.writes == []


def test_a_carried_failure_is_an_error_never_a_rejected_row(script, inst, monkeypatch, capsys):
    props = trd.proposals(done=[PLAIN], open=[carried("Jana", "not_mentioned", "2026-W12", "2026-03-24")])
    out, fake = _write(script, monkeypatch, capsys, inst, _read(PREV), props)
    assert out["status"] == "refused" and out["problems"] == ["proposals-invalid"], out
    assert out["errors"] == ["/groups/open/0: carried-gone-has-day"] and "rejected" not in out
    assert fake.writes == []


@pytest.mark.parametrize("state", ["pending", "retry", "failed"])
def test_a_carryover_not_passed_writes_the_carry_failed_line_and_no_carried_label(script, inst, monkeypatch, capsys,
                                                                                    state):
    out, fake = _write(script, monkeypatch, capsys, inst, _read(PREV), trd.proposals(done=[PLAIN]),
                       carryover_state=state)
    assert out["status"] == "written" and out["carry_failed"] is True, out
    lines = _lines(fake)
    assert CARRY_FAILED_DE in lines
    assert "> Letzter Rückblick · Woche 2026-W12: gefunden, nicht berücksichtigt" in lines
    assert not any("(letzter Rückblick)" in ln for ln in lines if ln.startswith("- [x]"))


@pytest.mark.parametrize("state", ["pending", "retry"])
def test_a_carried_proposal_without_a_passed_carryover_is_refused(script, inst, monkeypatch, capsys, state):
    props = trd.proposals(done=[PLAIN], open=[carried("Jana", "not_mentioned", "2026-W12")])
    out, fake = _write(script, monkeypatch, capsys, inst, _read(PREV), props, carryover_state=state)
    assert out["problems"] == ["proposals-invalid"], out
    assert out["errors"] == ["/groups/open/0: carried-without-carryover"] and fake.writes == []


def test_without_a_found_note_there_is_no_carry_failed_line(script, inst, monkeypatch, capsys):
    out, fake = _write(script, monkeypatch, capsys, inst, _read(MISSING), trd.proposals(done=[PLAIN]))
    assert out["status"] == "written" and "carry_failed" not in out, out
    assert out["previous"] == [{"kind": "month", "name": "2026-02", "state": "missing", "carried": 0}]
    assert CARRY_FAILED_DE not in _lines(fake)


# ---------------------------------------------------------------- overflow before over-cap

ROWS = [row("s1", "Wins", "under", level=2, cap=1)]


@pytest.fixture
def mapped_inst(inst):
    map_config(inst, ROWS)
    return inst


def _mapped(*previous) -> dict:
    return _read(*previous, sections=definitions_of(ROWS))


def test_overflow_moves_a_carried_item_of_a_full_section_before_over_cap(script, mapped_inst, monkeypatch, capsys):
    props = {"language": "de", "groups": {},
             "sections": [{"key": "s1", "items": [PLAIN, carried("Lief", "done", "2026-W12", "2026-03-24")]}]}
    out, fake = _write(script, monkeypatch, capsys, mapped_inst, _mapped(PREV), props)
    assert out["status"] == "written", out
    assert out["carried_moved"] == [{"key": "s1", "to": "done", "count": 1}]
    assert out["counts"]["s1"] == 1 and out["counts"]["done"] == 1
    assert "- [x] Lief ([[2026-W12]], [[2026-03-24]]) · erledigt (letzter Rückblick) %%t2%%" in _lines(fake)


def test_a_full_section_without_a_carried_item_is_still_over_cap(script, mapped_inst, monkeypatch, capsys):
    props = {"language": "de", "groups": {"open": [carried("Jana", "not_mentioned", "2026-W12")]},
             "sections": [{"key": "s1", "items": [PLAIN, trd.item("Noch was", "2026-03-24")]}]}
    out, fake = _write(script, monkeypatch, capsys, mapped_inst, _mapped(PREV), props)
    assert out["problems"] == ["proposals-invalid"] and out["errors"] == ["/sections/0/items: over-cap (s1)"], out
    assert fake.writes == []


# ---------------------------------------------------------------- F6-AC2: one of two notes not taken into account

PREV_FEB = f"{trd.MONTHLY}2026-02.md"
FEB = {"kind": "month", "name": "2026-02", "role": "previous-month", "path": PREV_FEB, "state": "found",
       "partly_read": True, "sections": {"Goals": "- read"}}


def test_one_of_two_notes_failing_its_carry_is_named_and_the_others_item_stays(script, inst, monkeypatch, capsys):
    props = trd.proposals(done=[PLAIN], open=[carried("Jana anrufen", "not_mentioned", "2026-W12")])
    out, fake = _write(script, monkeypatch, capsys, inst, _read(PREV, FEB), props,
                       note_states={PREV_WEEK: "passed", PREV_FEB: "failed"})
    assert out["status"] == "written" and "carry_failed" not in out, out
    lines = _lines(fake)
    assert "> Letzter Rückblick · Woche 2026-W12: gefunden, 1 übernommen" in lines
    assert "> Letzter Rückblick · Monat 2026-02: gefunden, nicht berücksichtigt, teilweise gelesen" in lines
    assert CARRY_FAILED_DE not in lines
    assert "- [x] Jana anrufen ([[2026-W12]]) · nicht mehr erwähnt (letzter Rückblick) %%t2%%" in lines
    assert out["previous"] == [
        {"kind": "week", "name": "2026-W12", "state": "found", "carried": 1},
        {"kind": "month", "name": "2026-02", "state": "found", "carried": 0, "carry_failed": True}]

#!/usr/bin/env python3
# version: 0.3.1
"""test_review_digest.py — spec 047 T4.2/T4.3: digest and carryover file checks, the condensed.json job state,
the ``review-digest.py plan | check`` CLI.

Lib part (``lib/review_digest.py``; PRD F1-AC1, F6-AC1, F6-AC2; SDD ADR-4). The
fixture is a month read of 2026-03 cut to two units: ``2026-W13`` (03-23 … 03-29,
03-28 an empty day that does not take part, 03-29 taking part only by a created
note) and ``2026-W14`` (03-30, 03-31; clipped). Every refusal case mutates one
field of a valid file and asserts the WHOLE error list, so each fixture produces
exactly one error code.

Mechanisms a mutation of ``lib/review_digest.py`` falsifies:
- ``days == the unit's taking-part days`` (F1-AC1) — dropping the comparison
  fails the left-out-day and the beyond-the-unit-day cases;
- every source a daily of the unit — a W14 day in W13's digest is refused;
- the unit's weekly-note stem accepted in ``child_notes`` only;
- theme days and section keys inside the unit / the mapping;
- growth ``notes`` ⊆ the unit's created notes and each growth source a day on
  which one of its notes was created — a growth source outside the unit is
  refused as outside, not as a day without a created note;
- the byte caps (digest ``cap_bytes``, carryover ``CARRYOVER_CAP``);
- carryover notes == the found previous notes, sources among them, ids unique;
- the state model: 1st counted failure ``retry``, 2nd ``failed``; a valid file
  passes, without an attempt when not counted; an invalid one is not touched
  when not counted;
- the per-note carryover failure removes only that note's items;
- no error string holds note text.

CLI part (``tomo/scripts/review-digest.py``; PRD F1-AC6, F6-AC1, F6-AC2, F6-AC4, F6-AC8;
SDD Internal API Changes, Complex Logic (b), (c), (d), ADR-4, ADR-8). Stages are written by
``review_stage.write`` from synthetic reads: 2026-W14 (two content days, previous week and month
found), 2026-03 (six units W09 … W14, previous month found, previous quarter missing) and 2026-Q1
(14 units, no previous note found). Mechanisms a mutation of the script falsifies:
- the rounds: one round up to ``MAX_PARALLEL`` jobs, a second above it;
- only taking-part units and their taking-part days are dispatched; growth files of the unit's
  creation days only; the job fields;
- the proposer's inputs in read order: context, passed digests, the passed carryover, the marked
  child level; never the manifest, a day or a growth file; ``carried`` follows the carryover;
- plan validates present files without an attempt, re-offers a unit failed in an earlier session,
  deletes a leftover ``proposals.json``;
- check: 1st failure ``retry`` with the errors, 2nd ``failed`` → ``not_condensed`` with all the
  unit's days; every unit failed → ``stopped nothing-condensed``, the stage kept; a carryover
  whole-file failure → ``carry_failed``; one note's invalid items → that note ``failed`` and its
  items removed from ``carryover.json``;
- (T4.4) the write order: ``condensed.json`` (the settled job state) before the settled
  ``carryover.json``, which is written with ``review_stage_codec.encode``; a crash between the two
  writes and a second check keeps the failed note and its removed items;
- the three refusals; no note text on stdout or stderr.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import review_digest as rd  # noqa: E402
from lib import review_stage as rs  # noqa: E402
from lib.period import ISO, Period  # noqa: E402

R = "2026-11-22T10-04-12Z-3f9a1c"
SECRET = "SECRET-NOTE-TEXT"
DAILY = "Calendar/301 Daily/{}.md"
W13_DAYS = [f"2026-03-{d}" for d in range(23, 30)]
W13_TAKING = ["2026-03-23", "2026-03-24", "2026-03-25", "2026-03-26", "2026-03-27", "2026-03-29"]
W14_DAYS = ["2026-03-30", "2026-03-31"]
MONTH_PREV = "Calendar/303 Monthly/2026-02.md"
QUARTER_PREV = "Calendar/304 Quarterly/2025-Q4.md"


def _day(d: str) -> dict:
    if d == "2026-03-28":
        return {"date": d, "dailies": [], "has_content": False, "tasks": [], "linked": []}
    return {"date": d, "dailies": [DAILY.format(d)], "has_content": d != "2026-03-29", "tasks": [], "linked": []}


READ = {
    "period": {"kind": "month", "name": "2026-03", "start": "2026-03-01", "end": "2026-03-31"},
    "days": [_day(d) for d in W13_DAYS + W14_DAYS],
    "growth": {"created": [
        {"path": "Notes/Alpha.md", "links": [], "day": "2026-03-25"},
        {"path": "Notes/Beta.md", "links": [], "day": "2026-03-29"},
        {"path": "Notes/Gamma.md", "links": [], "day": "2026-03-31"},
    ]},
    "weekly": [{"path": "Calendar/302 Weekly/2026-W13.md", "week": "2026-W13"}],
    "sections": [{"key": "s1", "heading": "Things I did well"}],
    "previous": [
        {"kind": "month", "name": "2026-02", "path": MONTH_PREV, "state": "found"},
        {"kind": "quarter", "name": "2025-Q4", "path": QUARTER_PREV, "state": "found"},
    ],
}
W13 = {"unit": "2026-W13", "week": "2026-W13", "days": W13_DAYS, "takes_part": True,
       "weekly_note": "weekly-2026-W13.json"}
W14 = {"unit": "2026-W14", "week": "2026-W14", "days": W14_DAYS, "takes_part": True, "weekly_note": None}
CAP = 8192
NO_FILE = object()

W13_DIGEST = {
    "read_id": R, "unit": "2026-W13", "days": W13_TAKING,
    "done": [{"text": f"5 km run {SECRET}", "sources": ["2026-03-24"]}],
    "open": [{"text": f"Call Jana {SECRET}", "sources": [DAILY.format("2026-03-25")]}],
    "notable": [],
    "themes": [{"text": f"Sleep {SECRET}", "days": ["2026-03-23"], "sources": ["2026-03-23"]}],
    "sections": [{"key": "s1", "items": [{"text": f"Kept calm {SECRET}", "sources": ["2026-03-26"]}]}],
    "child_notes": [{"text": f"Weekly says {SECRET}", "sources": ["2026-W13"]}],
    "growth": [{"text": f"Two new notes {SECRET}", "sources": ["2026-03-25", "2026-03-29"],
                "notes": ["Notes/Alpha.md", "Notes/Beta.md"]}],
}
CARRYOVER = {
    "read_id": R,
    "notes": [
        {"path": MONTH_PREV, "kind": "month", "name": "2026-02", "items": 2},
        {"path": QUARTER_PREV, "kind": "quarter", "name": "2025-Q4", "items": 2},
    ],
    "items": [
        {"id": "c1", "type": "intention", "text": f"Start running {SECRET}", "sources": ["2026-02", "2025-Q4"]},
        {"id": "c2", "type": "open", "text": f"Call Jana {SECRET}", "sources": ["2026-02"]},
        {"id": "c3", "type": "theme", "text": f"Sleep {SECRET}", "sources": ["2025-Q4"]},
    ],
}


def _text(data) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False)


def _digest(mutate=None, unit=W13, cap=CAP):
    """``mutate`` a copy of W13_DIGEST, or ``NO_FILE``."""
    if mutate is NO_FILE:
        return rd.check_digest(None, unit, READ, read_id=R, cap_bytes=cap)
    data = copy.deepcopy(W13_DIGEST)
    if mutate:
        mutate(data)
    return rd.check_digest(_text(data), unit, READ, read_id=R, cap_bytes=cap)


def _carry(mutate=None, read=READ):
    """``mutate`` a copy of CARRYOVER, or pass a raw text (``str``) or no file (``""`` → None)."""
    if isinstance(mutate, str):
        return rd.check_carryover(mutate or None, read, read_id=R)
    data = copy.deepcopy(CARRYOVER)
    if mutate:
        mutate(data)
    return rd.check_carryover(_text(data), read, read_id=R)


# ---------------------------------------------------------------- digests: valid

def test_the_w13_digest_passes():
    assert _digest() == []


def test_the_w14_digest_of_walkthrough_b_passes():
    digest = {"read_id": R, "unit": "2026-W14", "days": W14_DAYS,
              "done": [{"text": "5 km run", "sources": ["2026-03-31"]}], "open": [], "themes": [], "sections": [],
              "child_notes": [], "notable": [],
              "growth": [{"text": "Gamma", "sources": ["2026-03-31"], "notes": ["Notes/Gamma.md"]}]}
    assert rd.check_digest(_text(digest), W14, READ, read_id=R, cap_bytes=CAP) == []


def test_taking_part_days_follow_review_weeks_takes_part():
    assert rd.taking_part_days(W13, READ) == W13_TAKING


def test_a_child_note_may_also_name_a_day_of_its_unit():
    assert _digest(lambda d: d["child_notes"][0]["sources"].append("2026-03-27")) == []


# ---------------------------------------------------------------- digests: one fixture per error code

def _drop_day(d):
    d["days"].remove("2026-03-29")


DIGEST_CASES = [
    ("digest-missing", NO_FILE, ["digest-missing"]),
    ("schema", lambda d: d.pop("growth"), ["schema (/)"]),
    ("schema-nested", lambda d: d["done"][0].update(text=""), ["schema (/done/0/text)"]),
    ("read-id-mismatch", lambda d: d.update(read_id="other"), ["/read_id: read-id-mismatch"]),
    ("unit-mismatch", lambda d: d.update(unit="2026-W14"), ["/unit: unit-mismatch"]),
    ("days-mismatch-left-out", _drop_day, ["/days: days-mismatch"]),
    ("days-mismatch-empty-day", lambda d: d["days"].append("2026-03-28"), ["/days: days-mismatch"]),
    ("days-mismatch-other-unit", lambda d: d["days"].append("2026-03-30"), ["/days: days-mismatch"]),
    ("source-outside-unit", lambda d: d["done"][0].update(sources=["2026-03-30"]),
     ["/done/0/sources/0: source-outside-unit"]),
    ("source-outside-unit-unknown", lambda d: d["open"][0]["sources"].append("Notes/Alpha.md"),
     ["/open/0/sources/1: source-outside-unit"]),
    ("source-outside-unit-weekly-in-done", lambda d: d["done"][0].update(sources=["2026-W13"]),
     ["/done/0/sources/0: source-outside-unit"]),
    ("theme-day-outside-unit", lambda d: d["themes"][0]["days"].append("2026-03-31"),
     ["/themes/0/days/1: theme-day-outside-unit"]),
    ("unknown-section", lambda d: d["sections"][0].update(key="s9"), ["/sections/0/key: unknown-section"]),
    ("growth-note-outside-unit-w14", lambda d: d["growth"][0]["notes"].append("Notes/Gamma.md"),
     ["/growth/0/notes/2: growth-note-outside-unit"]),
    ("growth-note-outside-unit-not-created", lambda d: d["growth"][0]["notes"].append("Notes/Old.md"),
     ["/growth/0/notes/2: growth-note-outside-unit"]),
    ("growth-source-not-created-day", lambda d: d["growth"][0]["sources"].append("2026-03-24"),
     ["/growth/0/sources/2: growth-source-not-created-day"]),
    ("growth-source-outside-unit", lambda d: d["growth"][0]["sources"].__setitem__(0, "2026-03-30"),
     ["/growth/0/sources/0: source-outside-unit"]),
]


@pytest.mark.parametrize("name,mutate,expected", DIGEST_CASES, ids=[c[0] for c in DIGEST_CASES])
def test_each_digest_fixture_produces_exactly_its_error(name, mutate, expected):
    assert _digest(mutate) == expected


def test_not_json():
    assert rd.check_digest('{"read_id": ', W13, READ, read_id=R, cap_bytes=CAP) == ["not-json"]
    assert rd.check_digest("[1, 2]", W13, READ, read_id=R, cap_bytes=CAP) == ["schema (/)"]


def test_digest_too_large_counts_the_bytes_as_written():
    text = _text(W13_DIGEST)
    size = len(text.encode("utf-8"))
    assert rd.check_digest(text, W13, READ, read_id=R, cap_bytes=size) == []
    assert rd.check_digest(text, W13, READ, read_id=R, cap_bytes=size - 1) == ["digest-too-large"]


def test_the_weekly_stem_of_another_unit_is_outside():
    digest = {"read_id": R, "unit": "2026-W14", "days": W14_DAYS, "done": [], "open": [], "themes": [],
              "sections": [], "notable": [], "growth": [],
              "child_notes": [{"text": "x", "sources": ["2026-W13"]}]}
    assert rd.check_digest(_text(digest), W14, READ, read_id=R, cap_bytes=CAP) == [
        "/child_notes/0/sources/0: source-outside-unit"]


def test_a_read_without_a_mapping_knows_no_section():
    read = dict(READ)
    read.pop("sections")
    assert rd.check_digest(_text(W13_DIGEST), W13, read, read_id=R, cap_bytes=CAP) == [
        "/sections/0/key: unknown-section"]


# ---------------------------------------------------------------- carryover

def test_the_carryover_passes():
    check = _carry()
    assert (check.errors, check.whole, check.failed_notes, check.bad_items) == ([], False, [], [])
    assert check.notes == [MONTH_PREV, QUARTER_PREV]


def _missing_quarter():
    read = copy.deepcopy(READ)
    read["previous"][1]["state"] = "missing"
    return read


def _month_items_only(c):
    """The quarter note stays in ``notes`` (the read found no quarter note); no item rests on it."""
    c["items"] = [dict(c["items"][0], sources=["2026-02"]), c["items"][1]]


CARRY_CASES = [
    ("missing", "", READ, ["digest-missing"], True),
    ("not-json", "not json", READ, ["not-json"], True),
    ("schema", lambda c: c["items"][0].update(type="goal"), READ, ["schema (/items/0/type)"], True),
    ("read-id-mismatch", lambda c: c.update(read_id="other"), READ, ["/read_id: read-id-mismatch"], True),
    ("carryover-notes-mismatch-extra", _month_items_only, _missing_quarter(), ["/notes: carryover-notes-mismatch"],
     True),
    ("carryover-notes-mismatch-left-out", lambda c: c["notes"].pop(1), READ,
     ["/notes: carryover-notes-mismatch"], True),
    ("carry-source-unknown", lambda c: c["items"][1]["sources"].append("2025-Q3"), READ,
     ["/items/1/sources/1: carry-source-unknown"], False),
    ("carry-id-duplicate", lambda c: c["items"][2].update(id="c2"), READ, ["/items/2/id: carry-id-duplicate"], False),
]


@pytest.mark.parametrize("name,mutate,read,expected,whole", CARRY_CASES, ids=[c[0] for c in CARRY_CASES])
def test_each_carryover_fixture_produces_exactly_its_error(name, mutate, read, expected, whole):
    check = _carry(mutate, read=read)
    assert check.errors == expected
    assert check.whole is whole


def test_carryover_too_large_counts_the_bytes_as_written():
    text = _text(CARRYOVER)
    at_cap = text + " " * (rd.CARRYOVER_CAP - len(text.encode("utf-8")))
    assert rd.check_carryover(at_cap, READ, read_id=R).errors == []
    check = rd.check_carryover(at_cap + " ", READ, read_id=R)
    assert (check.errors, check.whole) == (["carryover-too-large"], True)
    assert rd.CARRYOVER_CAP == 12_288


def test_a_previous_note_path_is_a_valid_source():
    assert _carry(lambda c: c["items"][1].update(sources=[MONTH_PREV])).errors == []


def test_an_invalid_item_fails_the_notes_it_rests_on():
    check = _carry(lambda c: c["items"][1]["sources"].append("2025-Q3"))
    assert check.failed_notes == [MONTH_PREV]
    assert check.bad_items == [1]


def test_an_invalid_item_on_no_found_note_fails_no_note():
    check = _carry(lambda c: c["items"][2].update(sources=["2025-Q3"]))
    assert check.errors == ["/items/2/sources/0: carry-source-unknown"]
    assert (check.failed_notes, check.bad_items, check.whole) == ([], [2], False)


def test_settle_removes_only_the_failed_notes_items():
    data = copy.deepcopy(CARRYOVER)
    data["items"][2]["sources"] = ["2025-Q4", "2025-Q3"]   # c3 invalid, rests on the quarter note
    check = rd.check_carryover(_text(data), READ, read_id=R)
    assert check.failed_notes == [QUARTER_PREV]
    settled = rd.settle_carryover(data, check)
    assert [i["id"] for i in settled["items"]] == ["c2"]   # c1 rests on the quarter note too
    assert [(n["path"], n["items"]) for n in settled["notes"]] == [(MONTH_PREV, 1), (QUARTER_PREV, 0)]
    assert rd.check_carryover(_text(settled), READ, read_id=R).errors == []
    assert data["items"][0]["id"] == "c1"                    # the input is not changed


def test_settle_removes_a_noteless_invalid_item_alone():
    data = copy.deepcopy(CARRYOVER)
    data["items"][1]["sources"] = ["2025-Q3"]
    check = rd.check_carryover(_text(data), READ, read_id=R)
    settled = rd.settle_carryover(data, check)
    assert [i["id"] for i in settled["items"]] == ["c1", "c3"]
    assert [(n["path"], n["items"]) for n in settled["notes"]] == [(MONTH_PREV, 1), (QUARTER_PREV, 2)]


# ---------------------------------------------------------------- no note text in errors

def test_no_error_string_holds_note_text():
    errors = [e for _, mutate, _ in DIGEST_CASES for e in _digest(mutate)]
    errors += [e for _, mutate, read, _, _ in CARRY_CASES for e in _carry(mutate, read).errors]
    errors += _digest(lambda d: d["done"][0].update(sources=[f"2026-03-24 {SECRET}"]))
    errors += _carry(lambda c: c["items"][0].update(sources=[f"2025-Q3 {SECRET}"])).errors
    assert len(errors) == len(DIGEST_CASES) + len(CARRY_CASES) + 2
    assert not any(SECRET in e or "Jana" in e for e in errors)


# ---------------------------------------------------------------- the condensed.json state model

def test_new_state_holds_only_taking_part_units():
    resting = dict(W14, unit="2026-W15", takes_part=False)
    state = rd.new_state(R, [W13, W14, resting], carryover=True)
    assert state == {"read_id": R,
                     "units": {"2026-W13": {"state": "pending", "attempts": 0},
                               "2026-W14": {"state": "pending", "attempts": 0}},
                     "carryover": {"state": "pending", "attempts": 0, "notes": {}}}
    assert rd.new_state(R, [W13], carryover=False)["carryover"] == {"state": "none", "attempts": 0, "notes": {}}


def test_pending_retry_failed():
    job = {"state": "pending", "attempts": 0}
    first = rd.advance(job, ["/days: days-mismatch"], count=True)
    assert first == {"state": "retry", "attempts": 1}
    second = rd.advance(first, ["/days: days-mismatch"], count=True)
    assert second == {"state": "failed", "attempts": 2}
    assert rd.advance(second, [], count=True) == second       # failed is final for the run
    assert job == {"state": "pending", "attempts": 0}         # the input is not changed


def test_pending_passed_and_retry_passed():
    assert rd.advance({"state": "pending", "attempts": 0}, [], count=True) == {"state": "passed", "attempts": 1}
    assert rd.advance({"state": "retry", "attempts": 1}, [], count=True) == {"state": "passed", "attempts": 2}


def test_a_present_valid_file_passes_without_an_attempt():
    assert rd.advance({"state": "pending", "attempts": 0}, [], count=False) == {"state": "passed", "attempts": 0}
    assert rd.advance({"state": "pending", "attempts": 0}, ["digest-missing"], count=False) == {
        "state": "pending", "attempts": 0}
    assert rd.advance({"state": "passed", "attempts": 1}, ["digest-missing"], count=True) == {
        "state": "passed", "attempts": 1}


def _carry_job(state="pending", attempts=0):
    return {"state": state, "attempts": attempts, "notes": {}}


def test_carryover_whole_file_failure_retries_then_fails():
    check = _carry("not json")
    first = rd.advance_carryover(_carry_job(), check, count=True)
    assert first == {"state": "retry", "attempts": 1, "notes": {}}
    assert rd.advance_carryover(first, check, count=True) == {"state": "failed", "attempts": 2, "notes": {}}


def test_carryover_per_note_failure_after_the_retry():
    check = _carry(lambda c: c["items"][1]["sources"].append("2025-Q3"))
    first = rd.advance_carryover(_carry_job(), check, count=True)
    assert first["state"] == "retry"
    assert rd.advance_carryover(first, check, count=True) == {
        "state": "passed", "attempts": 2, "notes": {MONTH_PREV: "failed", QUARTER_PREV: "passed"}}


def test_carryover_every_note_failed_is_a_failed_carryover():
    check = _carry(lambda c: [i["sources"].append("2025-Q3") for i in c["items"]])
    assert sorted(check.failed_notes) == sorted([MONTH_PREV, QUARTER_PREV])
    assert rd.advance_carryover(_carry_job("retry", 1), check, count=True) == {
        "state": "failed", "attempts": 2, "notes": {MONTH_PREV: "failed", QUARTER_PREV: "failed"}}


def test_carryover_passes_with_every_note_passed():
    assert rd.advance_carryover(_carry_job(), _carry(), count=False) == {
        "state": "passed", "attempts": 0, "notes": {MONTH_PREV: "passed", QUARTER_PREV: "passed"}}
    assert rd.advance_carryover(_carry_job("none"), _carry("x"), count=True) == _carry_job("none")


def test_ready_not_condensed_and_nothing_condensed():
    state = rd.new_state(R, [W13, W14], carryover=False)
    assert not rd.ready(state)
    state["units"]["2026-W13"] = {"state": "failed", "attempts": 2}
    state["units"]["2026-W14"] = {"state": "passed", "attempts": 1}
    assert rd.ready(state) and not rd.nothing_condensed(state)
    assert rd.not_condensed(state, [W13, W14]) == [{"unit": "2026-W13", "days": W13_DAYS}]
    state["units"]["2026-W14"] = {"state": "failed", "attempts": 2}
    assert rd.nothing_condensed(state)
    state["carryover"] = _carry_job("retry", 1)
    assert not rd.ready(state)


# ================================================================ the CLI: review-digest.py plan | check

def _script():
    spec = importlib.util.spec_from_file_location("review_digest_cli_t43", SCRIPTS_DIR / "review-digest.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CLI = _script() if (SCRIPTS_DIR / "review-digest.py").is_file() else None
WEEKLY = "Calendar/302 Weekly/{}.md"
MONTHLY = "Calendar/303 Monthly/{}.md"
WEEK_PREV = WEEKLY.format("2026-W13")


def _cday(d: str, content: bool = True) -> dict:
    return {"date": d, "dailies": [DAILY.format(d)] if content else [],
            "sections": {"Daily Log": f"a line {SECRET}"} if content else {}, "fields": {}, "partly_read": False,
            "has_content": content, "links": [], "problems": [], "tasks": [], "linked": []}


def _found(kind: str, name: str, path: str) -> dict:
    return {"kind": kind, "name": name, "role": f"previous-{kind}", "path": path, "state": "found",
            "partly_read": False, "sections": {"Goals": f"- start running {SECRET}"}}


def _missing(kind: str, name: str) -> dict:
    return {"kind": kind, "name": name, "role": f"previous-{kind}", "path": None, "state": "missing",
            "partly_read": False}


def _read(period: Period, content, created=(), previous=(), **extra) -> dict:
    result = {"period": {"kind": period.kind, "name": period.name, "start": period.start.isoformat(),
                         "end": period.end.isoformat()},
              "days": [_cday(d.isoformat(), content(d.isoformat())) for d in period.days()],
              "open_tasks": [], "report": {"days": []}, "not_read": [], "previous": list(previous),
              "growth": {"created": [{"path": p, "links": [], "day": day} for p, day in created],
                         "mocs_changed": [], "mocs_linked_by_new": []}}
    result.update(extra)
    return result


def _stage(tmp_path: Path, stem: str, result: dict) -> Path:
    stage = tmp_path / "review" / stem
    rs.write(stage, result, stem=stem, rule=ISO, sections_digest="none")
    return stage


def _w14_stage(tmp_path: Path) -> Path:
    """Walkthrough (b): 2026-W14, dailies on 03-30 and 03-31 only; previous week and previous month found."""
    return _stage(tmp_path, "2026-W14_review", _read(
        Period.week(2026, 14), lambda d: d in ("2026-03-30", "2026-03-31"),
        previous=[_found("week", "2026-W13", WEEK_PREV), _found("month", "2026-02", MONTH_PREV)]))


MARCH_UNITS = [f"2026-W{n:02d}" for n in range(9, 15)]


def _march_stage(tmp_path: Path) -> Path:
    """Walkthrough (c)/(d): 2026-03, six units W09 … W14; 03-28 empty (no daily, nothing created); a note created
    on 03-10; the weekly note of W13; previous month found, previous quarter missing."""
    return _stage(tmp_path, "2026-03_review", _read(
        Period.month(2026, 3), lambda d: d != "2026-03-28", created=[("Notes/Alpha.md", "2026-03-10")],
        previous=[_found("month", "2026-02", MONTH_PREV), _missing("quarter", "2025-Q4")],
        weekly=[{"path": WEEKLY.format("2026-W13"), "week": "2026-W13",
                 "weekly_text": {"Wins": f"won {SECRET}"}}]))


def _q1_stage(tmp_path: Path, previous=None) -> Path:
    """Walkthrough (a): 2026-Q1, every day a daily; weekly and monthly child notes; no 2025-Q4 note."""
    weekly = [{"path": WEEKLY.format(w), "week": w, "weekly_text": {"Wins": f"won {SECRET}"}}
              for w in ("2026-W02", "2026-W03")]
    monthly = [{"path": MONTHLY.format(m), "month": m, "monthly_text": {"Wins": f"won {SECRET}"}}
               for m in ("2026-01", "2026-02")]
    return _stage(tmp_path, "2026-Q1_review", _read(
        Period.quarter(2026, 1), lambda d: True,
        previous=previous if previous is not None else [_missing("quarter", "2025-Q4")],
        weekly=weekly, monthly=monthly))


def _cli(capsys, *argv) -> dict:
    assert CLI is not None, "tomo/scripts/review-digest.py does not exist"
    assert CLI.main(list(argv)) == 0
    out, err = capsys.readouterr()
    assert out.isascii() and err == ""
    assert SECRET not in out and "start running" not in out
    return json.loads(out)


def _plan(capsys, stage: Path) -> dict:
    return _cli(capsys, "plan", "--stem", stage.name, "--tmp", str(stage.parent))


def _check(capsys, stage: Path) -> dict:
    return _cli(capsys, "check", "--stem", stage.name, "--tmp", str(stage.parent))


def _read_id(stage: Path) -> str:
    return json.loads((stage / "manifest.json").read_text(encoding="utf-8"))["read_id"]


def _units(stage: Path) -> list:
    return json.loads((stage / "weeks.json").read_text(encoding="utf-8"))["units"]


def _empty_digest(stage: Path, unit: dict, **groups) -> dict:
    loaded = rs.load(stage)
    data = {"read_id": _read_id(stage), "unit": unit["unit"], "days": rd.taking_part_days(unit, loaded),
            "done": [], "open": [], "notable": [], "themes": [], "sections": [], "child_notes": [], "growth": []}
    data.update(groups)
    return data


def _put(stage: Path, name: str, data) -> None:
    path = stage / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else _text(data), encoding="utf-8")


def _write_digests(stage: Path, names=None, **groups) -> None:
    for unit in _units(stage):
        if unit["takes_part"] and (names is None or unit["unit"] in names):
            first = rd.taking_part_days(unit, rs.load(stage))[0]
            body = {"done": [{"text": f"run {SECRET}", "sources": [first]}], **groups}
            _put(stage, f"digests/{unit['unit']}.json", _empty_digest(stage, unit, **body))


def _carryover(stage: Path, notes, items) -> dict:
    return {"read_id": _read_id(stage), "notes": [{"path": p, "kind": k, "name": n, "items": c}
                                                   for p, k, n, c in notes], "items": items}


def _march_carryover(stage: Path) -> dict:
    return _carryover(stage, [(MONTH_PREV, "month", "2026-02", 1)],
                      [{"id": "c1", "type": "intention", "text": f"Start running {SECRET}", "sources": ["2026-02"]}])


def _condensed(stage: Path) -> dict:
    return json.loads((stage / "condensed.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- plan: rounds and jobs

def test_plan_w14_is_one_round_of_its_digester_and_the_carryover(tmp_path, capsys):
    stage = _w14_stage(tmp_path)
    out = _plan(capsys, stage)
    assert (out["status"], out["stem"], out["read_id"], out["ready"]) == ("ok", stage.name, _read_id(stage), False)
    assert out["read_at"] == json.loads((stage / "manifest.json").read_text())["read_at"]
    assert out["rounds"] == [[
        {"agent": "review-digester", "unit": "2026-W14", "days": ["2026-03-30", "2026-03-31"],
         "day_files": ["days/2026-03-30.json", "days/2026-03-31.json"], "growth_files": [], "weekly_note": None,
         "sections": False, "section_files": [], "out": "digests/2026-W14.json", "cap_bytes": 8192},
        {"agent": "review-carryover", "previous_files": ["previous/week-2026-W13.json", "previous/month-2026-02.json"],
         "out": "carryover.json", "cap_bytes": 12288}]]
    assert (out["done"], out["not_condensed"], out["carryover_state"]) == ([], [], "pending")
    assert out["proposer"] == {"inputs": ["context.json"], "out": "proposals.json", "carried": False}
    assert _condensed(stage) == {"read_id": _read_id(stage),
                                 "units": {"2026-W14": {"state": "pending", "attempts": 0}},
                                 "carryover": {"state": "pending", "attempts": 0, "notes": {}}}
    assert not (stage / "digests").exists(), "agents create digests/ themselves (T1.4)"


def test_plan_march_dispatches_six_digesters_and_the_carryover_of_the_found_note(tmp_path, capsys):
    stage = _march_stage(tmp_path)
    out = _plan(capsys, stage)
    (jobs,) = out["rounds"]
    assert [j.get("unit") for j in jobs] == MARCH_UNITS + [None]
    by_unit = {j["unit"]: j for j in jobs[:-1]}
    assert by_unit["2026-W09"]["days"] == ["2026-03-01"]
    # 03-28 has no daily and nothing created: it does not take part and is not dispatched (F1-AC6)
    assert by_unit["2026-W13"]["days"] == [f"2026-03-{d}" for d in (23, 24, 25, 26, 27, 29)]
    assert "days/2026-03-28.json" not in by_unit["2026-W13"]["day_files"]
    assert by_unit["2026-W13"]["weekly_note"] == "children/weekly-2026-W13.json"
    assert by_unit["2026-W12"]["weekly_note"] is None
    # the creation day's growth file goes to its unit only
    assert by_unit["2026-W11"]["growth_files"] == ["growth/2026-03-10.json"]
    assert [u for u, j in by_unit.items() if j["growth_files"]] == ["2026-W11"]
    assert by_unit["2026-W14"]["days"] == ["2026-03-30", "2026-03-31"]       # clipped to the month
    assert jobs[-1]["previous_files"] == ["previous/month-2026-02.json"]     # the missing quarter is no input
    assert {j["cap_bytes"] for j in jobs[:-1]} == {json.loads((stage / "weeks.json").read_text())["digest_cap_bytes"]}


def test_plan_q1_without_a_found_note_is_fourteen_digesters_and_no_carryover(tmp_path, capsys):
    stage = _q1_stage(tmp_path)
    out = _plan(capsys, stage)
    (jobs,) = out["rounds"]
    assert [j["unit"] for j in jobs] == [f"2026-W{n:02d}" for n in range(1, 15)]
    assert {j["agent"] for j in jobs} == {"review-digester"}
    assert out["carryover_state"] == "none" and _condensed(stage)["carryover"]["state"] == "none"
    assert out["proposer"]["carried"] is False
    # a quarter marks against its monthly notes; the weekly notes go to their unit's digester
    assert out["proposer"]["inputs"] == ["context.json", "children/monthly-2026-01.json",
                                         "children/monthly-2026-02.json"]
    assert {j["unit"]: j["weekly_note"] for j in jobs if j["weekly_note"]} == {
        "2026-W02": "children/weekly-2026-W02.json", "2026-W03": "children/weekly-2026-W03.json"}


def test_plan_q1_with_a_found_note_is_still_one_round_of_fifteen(tmp_path, capsys):
    stage = _q1_stage(tmp_path, previous=[_found("quarter", "2025-Q4", "Calendar/304 Quarterly/2025-Q4.md")])
    (jobs,) = _plan(capsys, stage)["rounds"]
    assert len(jobs) == 15 and jobs[-1]["agent"] == "review-carryover"


def test_plan_rounds():
    """ADR-8: at most MAX_PARALLEL (16) jobs per round; one round for 15 units + the carryover, two above it."""
    assert CLI is not None
    assert CLI.MAX_PARALLEL == 16
    assert [len(r) for r in CLI.rounds(list(range(16)))] == [16]
    assert [len(r) for r in CLI.rounds(list(range(17)))] == [16, 1]
    assert CLI.rounds(list(range(17)))[1] == [16]
    assert CLI.rounds([]) == []


def test_a_unit_without_a_taking_part_day_is_not_dispatched(tmp_path, capsys):
    stage = _stage(tmp_path, "2026-03_review", _read(Period.month(2026, 3), lambda d: d >= "2026-03-02"))
    out = _plan(capsys, stage)
    assert [j["unit"] for j in out["rounds"][0]] == MARCH_UNITS[1:]
    assert "2026-W09" not in _condensed(stage)["units"]


def test_the_sections_flag_follows_the_mapping(tmp_path, capsys):
    stage = _stage(tmp_path, "2026-W14_review", _read(
        Period.week(2026, 14), lambda d: d == "2026-03-30",
        sections=[{"key": "s1", "heading": "Wins", "level": 2, "parent": None, "description": "",
                   "keywords": [], "groups": ["done"], "cap": 5}]))
    assert _plan(capsys, stage)["rounds"][0][0]["sections"] is True


def _section_rows(n: int) -> list:
    return [{"key": f"s{i}", "heading": f"Heading {i}", "level": 2, "parent": None, "description": "",
             "keywords": [], "groups": ["done"], "cap": 5} for i in range(1, n + 1)]


def _holds_sections(stage: Path, name: str) -> bool:
    return bool(json.loads((stage / name).read_text(encoding="utf-8")).get("sections"))


def test_section_files_name_the_context_file_that_holds_the_sections(tmp_path, capsys):
    stage = _stage(tmp_path, "2026-W14_review", _read(
        Period.week(2026, 14), lambda d: d == "2026-03-30", sections=_section_rows(1)))
    (job,) = _plan(capsys, stage)["rounds"][0]
    assert job["section_files"] == ["context.json"]


def test_section_files_name_the_spilled_part_when_context_is_over_the_ceiling(tmp_path, capsys):
    """A context over the ceiling is spilled into context-<n>.json parts; the head keeps no section, so the job
    names the part(s) that hold them, never the bare context.json."""
    tasks = [{"text": f"task {i} {SECRET} " + "x" * 400, "done": False, "done_date": None,
              "source": "Efforts/Next Todos.md", "label": "open today"} for i in range(120)]
    stage = _stage(tmp_path, "2026-W14_review", _read(
        Period.week(2026, 14), lambda d: d == "2026-03-30", sections=_section_rows(3), open_tasks=tasks))
    head = json.loads((stage / "context.json").read_text(encoding="utf-8"))
    assert head.get("parts") and not head.get("sections"), "fixture: the context must spill its sections"
    (job,) = _plan(capsys, stage)["rounds"][0]
    assert job["section_files"] == [n for n in head["parts"] if _holds_sections(stage, n)]
    assert job["section_files"] and "context.json" not in job["section_files"]
    keys = [s["key"] for n in job["section_files"]
            for s in json.loads((stage / n).read_text(encoding="utf-8"))["sections"]]
    assert keys == ["s1", "s2", "s3"]


def test_section_files_are_empty_without_a_mapping(tmp_path, capsys):
    stage = _stage(tmp_path, "2026-W14_review", _read(Period.week(2026, 14), lambda d: d == "2026-03-30"))
    (job,) = _plan(capsys, stage)["rounds"][0]
    assert (job["sections"], job["section_files"]) == (False, [])


# ---------------------------------------------------------------- plan on a continued read (walkthrough (c))

def test_plan_on_a_continued_read_validates_present_files_without_an_attempt(tmp_path, capsys):
    stage = _march_stage(tmp_path)
    _write_digests(stage, names=MARCH_UNITS[:4])
    _put(stage, "carryover.json", _march_carryover(stage))
    _put(stage, "proposals.json", {"groups": {"done": [{"text": SECRET, "sources": ["2026-03-01"]}]}})
    out = _plan(capsys, stage)
    assert out["done"] == MARCH_UNITS[:4]
    assert [[j["unit"] for j in r] for r in out["rounds"]] == [["2026-W13", "2026-W14"]]
    assert out["carryover_state"] == "passed"
    assert not (stage / "proposals.json").exists(), "a leftover proposals.json is deleted: the proposer runs again"
    state = _condensed(stage)
    assert {u: j["attempts"] for u, j in state["units"].items()} == dict.fromkeys(MARCH_UNITS, 0)
    assert [u for u, j in state["units"].items() if j["state"] == "passed"] == MARCH_UNITS[:4]
    assert state["carryover"] == {"state": "passed", "attempts": 0, "notes": {MONTH_PREV: "passed"}}
    assert out["proposer"] == {"inputs": ["context.json", *[f"digests/{u}.json" for u in MARCH_UNITS[:4]],
                                          "carryover.json", "children/weekly-2026-W13.json"],
                               "out": "proposals.json", "carried": True}
    assert not any(p.startswith(("days/", "growth/")) or p == "manifest.json" for p in out["proposer"]["inputs"])


def test_plan_leaves_an_invalid_present_file_pending(tmp_path, capsys):
    stage = _march_stage(tmp_path)
    _put(stage, "digests/2026-W09.json", "not json")
    out = _plan(capsys, stage)
    assert "2026-W09" in [j.get("unit") for j in out["rounds"][0]]
    assert _condensed(stage)["units"]["2026-W09"] == {"state": "pending", "attempts": 0}


def test_plan_offers_a_unit_failed_in_an_earlier_session_again(tmp_path, capsys):
    stage = _march_stage(tmp_path)
    _plan(capsys, stage)
    _write_digests(stage, names=MARCH_UNITS[1:])
    _put(stage, "carryover.json", _march_carryover(stage))
    _check(capsys, stage)
    out = _check(capsys, stage)
    assert out["units"]["2026-W09"]["state"] == "failed" and out["ready"] is True
    out = _plan(capsys, stage)                       # the next session continues the read
    assert [[j["unit"] for j in r] for r in out["rounds"]] == [["2026-W09"]]
    assert out["not_condensed"] == [] and out["ready"] is False
    assert _condensed(stage)["units"]["2026-W09"] == {"state": "pending", "attempts": 0}
    assert _check(capsys, stage)["units"]["2026-W09"]["state"] == "retry"    # one attempt + one retry again


def test_plan_offers_a_carryover_failed_in_an_earlier_session_again(tmp_path, capsys):
    stage = _w14_stage(tmp_path)
    _plan(capsys, stage)
    _write_digests(stage)
    _put(stage, "carryover.json", "not json")
    _check(capsys, stage)
    assert _check(capsys, stage)["carry_failed"] is True
    out = _plan(capsys, stage)
    assert [j["agent"] for j in out["rounds"][0]] == ["review-carryover"]
    assert out["carryover_state"] == "pending"


# ---------------------------------------------------------------- check: retry, failed, not condensed

def test_digest_naming_a_day_outside_its_unit_is_retried_then_failed(tmp_path, capsys):
    stage = _march_stage(tmp_path)
    _plan(capsys, stage)
    _write_digests(stage)
    _put(stage, "carryover.json", _march_carryover(stage))
    bad = _empty_digest(stage, next(u for u in _units(stage) if u["unit"] == "2026-W13"),
                        done=[{"text": f"run {SECRET}", "sources": ["2026-03-30"]}])
    _put(stage, "digests/2026-W13.json", bad)
    first = _check(capsys, stage)
    assert first["status"] == "ok" and first["ready"] is False
    assert first["units"]["2026-W13"] == {"state": "retry", "errors": ["/done/0/sources/0: source-outside-unit"]}
    assert first["units"]["2026-W09"] == {"state": "passed"}
    assert first["retry"] == [{"agent": "review-digester", "unit": "2026-W13",
                               "errors": ["/done/0/sources/0: source-outside-unit"]}]
    assert first["not_condensed"] == [] and first["carry_failed"] is False
    second = _check(capsys, stage)
    assert second["units"]["2026-W13"] == {"state": "failed", "errors": ["/done/0/sources/0: source-outside-unit"]}
    assert second["retry"] == [] and second["ready"] is True
    assert second["not_condensed"] == [{"unit": "2026-W13", "days": [f"2026-03-{d}" for d in range(23, 30)]}]
    assert _condensed(stage)["units"]["2026-W13"] == {"state": "failed", "attempts": 2}
    assert "digests/2026-W13.json" not in second["proposer"]["inputs"]
    assert "digests/2026-W12.json" in second["proposer"]["inputs"]


def test_a_fixed_retry_passes(tmp_path, capsys):
    stage = _w14_stage(tmp_path)
    _plan(capsys, stage)
    first = _check(capsys, stage)
    assert first["units"]["2026-W14"] == {"state": "retry", "errors": ["digest-missing"]}
    assert first["carryover"]["state"] == "retry" and first["carryover"]["errors"] == ["digest-missing"]
    assert [r["agent"] for r in first["retry"]] == ["review-digester", "review-carryover"]
    assert "unit" not in first["retry"][1]
    _write_digests(stage)
    assert _check(capsys, stage)["units"]["2026-W14"] == {"state": "passed"}
    assert _condensed(stage)["units"]["2026-W14"] == {"state": "passed", "attempts": 2}


def test_every_unit_failed_stops_nothing_condensed_and_keeps_the_stage(tmp_path, capsys):
    stage = _march_stage(tmp_path)
    _plan(capsys, stage)
    _put(stage, "carryover.json", _march_carryover(stage))
    assert _check(capsys, stage)["status"] == "ok"
    out = _check(capsys, stage)
    assert out == {"status": "stopped", "stem": stage.name, "problems": ["nothing-condensed"],
                   "not_condensed": [{"unit": u["unit"], "days": u["days"]} for u in _units(stage)]}
    assert (stage / "manifest.json").is_file() and (stage / "days").is_dir(), "the stage stays (F6-AC8)"
    assert {j["state"] for j in _condensed(stage)["units"].values()} == {"failed"}


# ---------------------------------------------------------------- check: the carryover (walkthrough (d))

def test_a_carryover_failing_as_a_whole_after_the_retry_is_carry_failed(tmp_path, capsys):
    stage = _march_stage(tmp_path)
    _plan(capsys, stage)
    _write_digests(stage)
    bad = _march_carryover(stage)
    bad["items"][0]["sources"] = ["2025-Q4"]
    _put(stage, "carryover.json", bad)
    first = _check(capsys, stage)
    assert first["carryover"] == {"state": "retry", "notes": [],
                                  "errors": ["/items/0/sources/0: carry-source-unknown"]}
    assert first["retry"] == [{"agent": "review-carryover", "errors": ["/items/0/sources/0: carry-source-unknown"]}]
    _put(stage, "carryover.json", "not json")
    second = _check(capsys, stage)
    assert second["carryover"] == {"state": "failed", "notes": [], "errors": ["not-json"]}
    assert (second["carry_failed"], second["ready"]) == (True, True)
    assert second["proposer"]["carried"] is False and "carryover.json" not in second["proposer"]["inputs"]


def test_one_notes_invalid_items_fail_that_note_only_and_leave_carryover_json(tmp_path, capsys):
    stage = _w14_stage(tmp_path)
    _plan(capsys, stage)
    _write_digests(stage)
    carry = _carryover(stage, [(WEEK_PREV, "week", "2026-W13", 2), (MONTH_PREV, "month", "2026-02", 1)], [
        {"id": "c1", "type": "intention", "text": f"Start running {SECRET}", "sources": ["2026-02"]},
        {"id": "c2", "type": "open", "text": f"Call Jana {SECRET}", "sources": ["2026-W13", "2025-Q3"]},
        {"id": "c3", "type": "open", "text": f"Book {SECRET}", "sources": ["2026-W13"]}])
    _put(stage, "carryover.json", carry)
    first = _check(capsys, stage)
    assert first["carryover"]["state"] == "retry"
    assert first["carryover"]["errors"] == ["/items/1/sources/1: carry-source-unknown"]
    second = _check(capsys, stage)
    assert second["carryover"] == {"state": "passed", "errors": ["/items/1/sources/1: carry-source-unknown"],
                                   "notes": [{"path": WEEK_PREV, "state": "failed", "items": 0},
                                             {"path": MONTH_PREV, "state": "passed", "items": 1}]}
    assert second["carry_failed"] is False and second["ready"] is True
    settled = json.loads((stage / "carryover.json").read_text(encoding="utf-8"))
    assert [i["id"] for i in settled["items"]] == ["c1"]
    assert [(n["path"], n["items"]) for n in settled["notes"]] == [(WEEK_PREV, 0), (MONTH_PREV, 1)]
    assert rs.load(stage)["carryover"] == settled
    assert second["proposer"]["carried"] is True and "carryover.json" in second["proposer"]["inputs"]
    assert _check(capsys, stage)["carryover"]["notes"] == second["carryover"]["notes"], "final, counted once"


def _one_note_failing(stage: Path, capsys) -> None:
    """W14 with the week note's items invalid twice: the second check fails that note."""
    _plan(capsys, stage)
    _write_digests(stage)
    _put(stage, "carryover.json", _carryover(stage, [(WEEK_PREV, "week", "2026-W13", 2),
                                                     (MONTH_PREV, "month", "2026-02", 1)], [
        {"id": "c1", "type": "intention", "text": f"Start running {SECRET}", "sources": ["2026-02"]},
        {"id": "c2", "type": "open", "text": f"Call Jana {SECRET}", "sources": ["2026-W13", "2025-Q3"]},
        {"id": "c3", "type": "open", "text": f"Book {SECRET}", "sources": ["2026-W13"]}]))
    assert _check(capsys, stage)["carryover"]["state"] == "retry"


def test_a_crash_between_the_two_writes_keeps_the_failed_note(tmp_path, capsys, monkeypatch):
    stage = _w14_stage(tmp_path)
    _one_note_failing(stage, capsys)
    real, writes = CLI.atomic_write_text, []

    def second_write_crashes(path, text):
        writes.append(Path(path).name)
        if len(writes) == 2:
            raise OSError("crash")
        real(path, text)

    monkeypatch.setattr(CLI, "atomic_write_text", second_write_crashes)
    assert CLI.main(["check", "--stem", stage.name, "--tmp", str(stage.parent)]) == 1
    capsys.readouterr()
    monkeypatch.setattr(CLI, "atomic_write_text", real)
    assert writes[0] == "condensed.json", "the job state is written first"
    after = _check(capsys, stage)
    assert after["carryover"]["notes"] == [{"path": WEEK_PREV, "state": "failed", "items": 0},
                                           {"path": MONTH_PREV, "state": "passed", "items": 1}], after
    settled = json.loads((stage / "carryover.json").read_text(encoding="utf-8"))
    assert [i["id"] for i in settled["items"]] == ["c1"]
    assert rs.load(stage)["carryover"] == settled
    assert _condensed(stage)["carryover"]["notes"] == {WEEK_PREV: "failed", MONTH_PREV: "passed"}


def test_the_settled_carryover_is_written_with_the_stage_encoder(tmp_path, capsys):
    from lib.review_stage_codec import encode
    stage = _w14_stage(tmp_path)
    _one_note_failing(stage, capsys)
    _check(capsys, stage)
    text = (stage / "carryover.json").read_text(encoding="utf-8")
    assert text == encode(json.loads(text)) and SECRET in text, "indent=1, UTF-8, one encoder"


def test_w14_passes_as_in_walkthrough_b(tmp_path, capsys):
    stage = _w14_stage(tmp_path)
    _plan(capsys, stage)
    _write_digests(stage)
    _put(stage, "carryover.json", _carryover(
        stage, [(WEEK_PREV, "week", "2026-W13", 2), (MONTH_PREV, "month", "2026-02", 1)],
        [{"id": "c1", "type": "intention", "text": "Start running again", "sources": ["2026-W13", "2026-02"]},
         {"id": "c2", "type": "open", "text": "Call Jana", "sources": ["2026-W13"]}]))
    out = _check(capsys, stage)
    assert out == {"status": "ok", "stem": stage.name, "units": {"2026-W14": {"state": "passed"}},
                   "carryover": {"state": "passed", "notes": [{"path": WEEK_PREV, "state": "passed", "items": 2},
                                                              {"path": MONTH_PREV, "state": "passed", "items": 1}]},
                   "retry": [], "not_condensed": [], "carry_failed": False, "ready": True,
                   "proposer": {"inputs": ["context.json", "digests/2026-W14.json", "carryover.json"],
                                "out": "proposals.json", "carried": True}}
    assert _plan(capsys, stage)["rounds"] == [] and _plan(capsys, stage)["ready"] is True


# ---------------------------------------------------------------- refusals

@pytest.mark.parametrize("command", ["plan", "check"])
def test_a_stage_without_a_manifest_is_refused_as_missing(tmp_path, capsys, command):
    (tmp_path / "review" / "x").mkdir(parents=True)
    assert _cli(capsys, command, "--stem", "x", "--tmp", str(tmp_path / "review")) == {
        "status": "refused", "stem": "x", "problems": ["stage-missing"]}
    assert _cli(capsys, command, "--stem", "absent", "--tmp", str(tmp_path / "review"))["problems"] == [
        "stage-missing"]


@pytest.mark.parametrize("command", ["plan", "check"])
def test_an_unreadable_stage_file_is_refused_as_invalid(tmp_path, capsys, command):
    stage = _w14_stage(tmp_path)
    (stage / "weeks.json").write_text("not json", encoding="utf-8")
    assert _cli(capsys, command, "--stem", stage.name, "--tmp", str(stage.parent))["problems"] == ["stage-invalid"]


@pytest.mark.parametrize("command", ["plan", "check"])
def test_a_stage_file_of_another_read_is_refused_as_stale(tmp_path, capsys, command):
    stage = _w14_stage(tmp_path)
    _put(stage, "condensed.json", rd.new_state("another-read", _units(stage), carryover=True))
    out = _cli(capsys, command, "--stem", stage.name, "--tmp", str(stage.parent))
    assert out == {"status": "refused", "stem": stage.name, "problems": ["read-stale"]}


def test_a_bad_stem_is_a_bad_invocation(tmp_path, capsys):
    assert CLI is not None
    with pytest.raises(SystemExit) as exc:
        CLI.main(["plan", "--stem", f"../{SECRET}", "--tmp", str(tmp_path)])
    assert exc.value.code == 2
    out, err = capsys.readouterr()
    assert SECRET not in out + err


def test_an_unexpected_exception_leaves_only_its_class_name(tmp_path, capsys, monkeypatch):
    stage = _w14_stage(tmp_path)

    def boom(*a, **kw):
        raise RuntimeError(f"cannot read {SECRET}")

    monkeypatch.setattr(CLI.review_stage, "load", boom)
    assert CLI.main(["plan", "--stem", stage.name, "--tmp", str(stage.parent)]) == 1
    out, err = capsys.readouterr()
    assert (out, err) == ("", "RuntimeError\n")

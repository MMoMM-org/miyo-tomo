#!/usr/bin/env python3
# version: 0.1.0
"""test_review_digest.py — spec 047 T4.2: digest and carryover file checks, the condensed.json job state.

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
  which one of its notes was created;
- the byte caps (digest ``cap_bytes``, carryover ``CARRYOVER_CAP``);
- carryover notes == the found previous notes, sources among them, ids unique;
- the state model: 1st counted failure ``retry``, 2nd ``failed``; a valid file
  passes, without an attempt when not counted; an invalid one is not touched
  when not counted;
- the per-note carryover failure removes only that note's items;
- no error string holds note text.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import review_digest as rd  # noqa: E402

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

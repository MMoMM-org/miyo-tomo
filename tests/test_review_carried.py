#!/usr/bin/env python3
# version: 0.1.1
"""test_review_carried.py — spec 047 T5.3: the document-level rules of a carried item (``lib/review_carried``).

Every row of the SDD trace table "A carried item checked (traced)" is one case below, on the W14 data of
walkthrough (b): ``Sources.previous`` = {2026-W13, 2026-02}, dailies 2026-03-30 and 2026-03-31, carryover
c1 {2026-W13, 2026-02}, c2 {2026-W13}; rows 6-8 on a month read (day 2026-03-12, weekly 2026-W11, previous
2026-02, carryover c4 {2026-02}). Beyond the table: the remaining error codes, the subset rule (F5-AC3),
one item over several ids (F4-AC7), one item with the note and the days (F4-AC6), ``overflow`` (F4-AC10)
and the two-day theme rule not applying to a carried item.

Mechanisms each test falsifies are named per rule in the T5.3 report (mutation table).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))

from lib import review_carried as rcar  # noqa: E402
from lib import review_doc as rd  # noqa: E402
from lib import review_sections as rs  # noqa: E402
from lib.review_sources import Sources  # noqa: E402

W14_READ = {
    "period": {"kind": "week"},
    "days": [{"date": "2026-03-30", "dailies": ["Daily/2026-03-30.md"]},
             {"date": "2026-03-31", "dailies": ["Daily/2026-03-31.md"]}],
    "previous": [{"path": "Reviews/2026-W13.md", "state": "found"},
                 {"path": "Reviews/2026-02.md", "state": "found"}],
}
CARRYOVER = {
    "read_id": "r1",
    "notes": [{"path": "Reviews/2026-W13.md", "kind": "week", "name": "2026-W13", "items": 2},
              {"path": "Reviews/2026-02.md", "kind": "month", "name": "2026-02", "items": 1}],
    "items": [{"id": "c1", "type": "intention", "text": "Start running again", "sources": ["2026-W13", "2026-02"]},
              {"id": "c2", "type": "open", "text": "Call Jana about the trip", "sources": ["2026-W13"]}],
}
MONTH_READ = {
    "period": {"kind": "month"},
    "days": [{"date": "2026-03-12", "dailies": ["Daily/2026-03-12.md"]}],
    "weekly": [{"path": "Reviews/2026-W11.md"}],
    "previous": [{"path": "Reviews/2026-02.md", "state": "found"}],
}
MONTH_CARRYOVER = {
    "read_id": "r2",
    "notes": [{"path": "Reviews/2026-02.md", "kind": "month", "name": "2026-02", "items": 1}],
    "items": [{"id": "c4", "type": "intention", "text": "Less screen time", "sources": ["Reviews/2026-02.md"]}],
}


def _item(text, carried, ids, sources, **extra):
    return {"text": text, "sources": list(sources), "carried": carried, "carried_ids": list(ids), **extra}


def _w14():
    return Sources.of(W14_READ)


def _month():
    return Sources.of(MONTH_READ)


# --- the trace table, row by row ----------------------------------------------------------

def test_row1_done_in_done_with_both_notes_and_a_day_is_accepted():
    item = _item("Started running again: 5 km run", "done", ["c1"], ["2026-W13", "2026-02", "2026-03-31"])
    assert rcar.check("done", item, _w14(), CARRYOVER, in_section=False) == (
        None, ["2026-W13", "2026-02", "2026-03-31"])


def test_row2_not_mentioned_in_open_with_its_note_only_is_accepted():
    item = _item("Call Jana about the trip", "not_mentioned", ["c2"], ["2026-W13"])
    assert rcar.check("open", item, _w14(), CARRYOVER, in_section=False) == (None, ["2026-W13"])


def test_row3_not_mentioned_with_a_day_is_gone_has_day():
    item = _item("Call Jana about the trip", "not_mentioned", ["c2"], ["2026-W13", "2026-03-30"])
    assert rcar.check("open", item, _w14(), CARRYOVER, in_section=False)[0] == "carried-gone-has-day"


def test_row4_a_previous_note_outside_its_ids_sources_is_refused():
    item = _item("Call Jana about the trip", "not_mentioned", ["c2"], ["2026-02"])
    assert rcar.check("open", item, _w14(), CARRYOVER, in_section=False)[0] == "carried-source-not-its-note (c2)"


def test_row5_done_in_themes_is_not_allowed():
    item = _item("Started running again", "done", ["c1"], ["2026-W13", "2026-03-31"])
    assert rcar.check("themes", item, _w14(), CARRYOVER, in_section=False)[0] == "carried-not-allowed (themes)"


def test_row6_still_open_with_not_in_weekly_in_a_section_is_accepted():
    item = _item("Less screen time", "still_open", ["c4"], ["2026-02", "2026-03-12"], mark="not_in_weekly")
    assert rcar.check("s3", item, _month(), MONTH_CARRYOVER, in_section=True, mark="not_in_weekly") == (
        None, ["2026-02", "2026-03-12"])


def test_row7_still_open_with_weekly_only_is_a_mark_conflict():
    item = _item("Less screen time", "still_open", ["c4"], ["2026-02", "2026-W11"], mark="weekly_only")
    assert rcar.check("s3", item, _month(), MONTH_CARRYOVER, in_section=True,
                      mark="weekly_only")[0] == "carried-mark-conflict"


def test_row8_not_mentioned_with_not_in_weekly_is_a_mark_conflict():
    item = _item("Less screen time", "not_mentioned", ["c4"], ["2026-02"], mark="not_in_weekly")
    assert rcar.check("s3", item, _month(), MONTH_CARRYOVER, in_section=True,
                      mark="not_in_weekly")[0] == "carried-mark-conflict"


def _plain(text):
    return {"text": text, "sources": ["2026-03-30"]}


SECTION_READ = {**W14_READ, "sections": [{"key": "s1", "cap": 2}]}


def test_row9_overflow_moves_the_carried_item_of_a_full_section_to_done():
    carried = _item("Started running again", "done", ["c1"], ["2026-W13", "2026-03-31"])
    proposals = {"groups": {}, "sections": [{"key": "s1", "items": [_plain("a"), carried, _plain("b")]}]}
    moved, notices = rcar.overflow(proposals, rs.definitions(SECTION_READ), CARRYOVER)
    assert [i["text"] for i in moved["sections"][0]["items"]] == ["a", "b"]
    assert moved["groups"]["done"] == [carried]
    assert notices == [{"key": "s1", "to": "done", "count": 1}]
    assert not rs.check(moved, SECTION_READ).errors                    # no refusal after the move


def test_row10_an_over_cap_section_without_a_carried_item_is_still_refused():
    proposals = {"groups": {}, "sections": [{"key": "s1", "items": [_plain("a"), _plain("b"), _plain("x")]}]}
    moved, notices = rcar.overflow(proposals, rs.definitions(SECTION_READ), CARRYOVER)
    assert moved == proposals and notices == []
    assert "/sections/0/items: over-cap (s1)" in rs.check(moved, SECTION_READ).errors


def test_row11_a_carryover_id_left_out_is_missing():
    proposals = {"groups": {"done": [_item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"])]}}
    assert rcar.coverage(proposals, CARRYOVER) == ["carried-missing (c2)"]


def test_row12_an_id_in_a_group_and_in_a_section_is_carried_twice():
    run = _item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"])
    proposals = {"sections": [{"key": "s1", "items": [run]}],
                 "groups": {"done": [copy.deepcopy(run)],
                            "open": [_item("Jana", "not_mentioned", ["c2"], ["2026-W13"])]}}
    assert rcar.coverage(proposals, CARRYOVER) == ["/groups/done/0/carried_ids/0: carried-twice (c1)"]


# --- the other error codes ----------------------------------------------------------------

def test_carried_without_carryover():
    item = _item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"])
    assert rcar.check("done", item, _w14(), None, in_section=False) == ("carried-without-carryover", [])


def test_carried_unknown_id():
    proposals = {"groups": {"done": [_item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"])],
                            "open": [_item("Jana", "not_mentioned", ["c2", "c9"], ["2026-W13"])]}}
    assert rcar.coverage(proposals, CARRYOVER) == ["/groups/open/0/carried_ids/1: carried-unknown (c9)"]


def test_an_id_with_a_trailing_newline_is_unknown_by_exact_match():
    proposals = {"groups": {"done": [_item("Run", "done", ["c1\n"], ["2026-W13", "2026-03-31"])],
                            "open": [_item("Jana", "not_mentioned", ["c2"], ["2026-W13"])]}}
    assert rcar.coverage(proposals, CARRYOVER) == [
        "/groups/done/0/carried_ids/0: carried-unknown (c1\n)", "carried-missing (c1)"]


def test_an_unknown_id_skips_the_subset_rule_coverage_names_it():
    item = _item("Run", "done", ["c9"], ["2026-W13", "2026-03-31"])
    assert rcar.check("done", item, _w14(), CARRYOVER, in_section=False)[0] is None


def test_carried_needs_previous_note():
    item = _item("Run", "done", ["c1"], ["2026-03-31"])
    assert rcar.check("done", item, _w14(), CARRYOVER, in_section=False) == (
        "carried-needs-previous-note", ["2026-03-31"])


def test_a_previous_source_the_read_did_not_find_is_no_previous_note():
    item = _item("Run", "done", ["c1"], ["2026-W12", "2026-03-31"])     # not a found previous note
    assert rcar.check("done", item, _w14(), CARRYOVER, in_section=False)[0] == "carried-needs-previous-note"


@pytest.mark.parametrize("carried, group", [("done", "done"), ("still_open", "open")])
def test_carried_needs_day(carried, group):
    item = _item("Run", carried, ["c1"], ["2026-W13"])
    assert rcar.check(group, item, _w14(), CARRYOVER, in_section=False)[0] == "carried-needs-day"


def test_carried_theme_done():
    carryover = copy.deepcopy(CARRYOVER)
    carryover["items"].append({"id": "c3", "type": "theme", "text": "Sleep", "sources": ["2026-02"]})
    proposals = {"groups": {"done": [_item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"]),
                                     _item("Sleep", "done", ["c3"], ["2026-02", "2026-03-31"])],
                            "open": [_item("Jana", "not_mentioned", ["c2"], ["2026-W13"])]}}
    assert rcar.coverage(proposals, carryover) == ["/groups/done/1/carried: carried-theme-done (c3)"]


def test_a_full_document_covers_every_id_once():
    proposals = {"groups": {"done": [_item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"])],
                            "open": [_item("Jana", "not_mentioned", ["c2"], ["2026-W13"])]}}
    assert rcar.coverage(proposals, CARRYOVER) == []


def test_coverage_without_carryover_names_nothing():
    assert rcar.coverage({"groups": {"done": [_plain("a")]}}, None) == []


# --- group and section values -------------------------------------------------------------

@pytest.mark.parametrize("group, carried, allowed", [
    ("done", "done", True), ("done", "still_open", False), ("done", "not_mentioned", False),
    ("open", "still_open", True), ("open", "not_mentioned", True), ("open", "done", False),
    ("themes", "still_open", True), ("themes", "not_mentioned", True), ("themes", "done", False),
    ("growth", "still_open", False), ("not_in_weekly", "still_open", False), ("weekly_only", "done", False),
])
def test_group_value_combinations(group, carried, allowed):
    sources = ["2026-W13"] if carried == "not_mentioned" else ["2026-W13", "2026-03-31", "2026-03-30"]
    error = rcar.check(group, _item("x", carried, ["c1"], sources), _w14(), CARRYOVER, in_section=False)[0]
    assert (error is None) if allowed else (error == f"carried-not-allowed ({group})")


@pytest.mark.parametrize("carried", ["done", "still_open", "not_mentioned"])
def test_a_section_takes_any_value(carried):
    sources = ["2026-W13"] if carried == "not_mentioned" else ["2026-W13", "2026-03-31"]
    assert rcar.check("s1", _item("x", carried, ["c1"], sources), _w14(), CARRYOVER, in_section=True)[0] is None


@pytest.mark.parametrize("mark", ["not_in_weekly", "not_in_monthly"])
@pytest.mark.parametrize("carried", ["done", "still_open"])
def test_not_in_marks_go_with_done_and_still_open(mark, carried):
    item = _item("x", carried, ["c4"], ["2026-02", "2026-03-12"], mark=mark)
    assert rcar.check("s3", item, _month(), MONTH_CARRYOVER, in_section=True, mark=mark)[0] is None


@pytest.mark.parametrize("mark", ["weekly_only", "monthly_only"])
def test_only_marks_conflict_with_done(mark):
    item = _item("x", "done", ["c4"], ["2026-02", "2026-03-12"], mark=mark)
    assert rcar.check("s3", item, _month(), MONTH_CARRYOVER, in_section=True, mark=mark)[0] == "carried-mark-conflict"


# --- F5-AC3, F4-AC6, F4-AC7 ------------------------------------------------------------------

def test_previous_sources_a_proper_subset_of_the_ids_sources_are_accepted():
    item = _item("Run", "done", ["c1"], ["2026-02", "2026-03-31"])     # c1 rests on W13 and 02; 02 alone is enough
    assert rcar.check("done", item, _w14(), CARRYOVER, in_section=False) == (None, ["2026-02", "2026-03-31"])


def test_subset_is_compared_by_stem_also_for_a_path_source():
    item = _item("Less", "still_open", ["c4"], ["Reviews/2026-02.md", "2026-03-12"])
    assert rcar.check("s3", item, _month(), MONTH_CARRYOVER, in_section=True)[0] is None


def test_one_item_over_ids_from_both_previous_notes_is_accepted_once():
    carryover = copy.deepcopy(CARRYOVER)
    carryover["items"] = [{"id": "c5", "type": "open", "text": "Tax", "sources": ["2026-W13"]},
                          {"id": "c6", "type": "open", "text": "Tax return", "sources": ["2026-02"]}]
    item = _item("Tax return", "still_open", ["c5", "c6"], ["2026-W13", "2026-02", "2026-03-30"])
    assert rcar.check("open", item, _w14(), carryover, in_section=False) == (
        None, ["2026-W13", "2026-02", "2026-03-30"])
    assert rcar.coverage({"groups": {"open": [item]}}, carryover) == []
    only_c5 = _item("Tax return", "still_open", ["c5"], ["2026-W13", "2026-02", "2026-03-30"])
    assert rcar.check("open", only_c5, _w14(), carryover, in_section=False)[0] == "carried-source-not-its-note (c5)"


def test_a_carried_item_the_days_also_hold_is_one_item_with_note_and_days():
    item = _item("Call Jana", "still_open", ["c2"], ["2026-W13", "2026-03-30", "2026-03-31"])
    proposals = {"groups": {"open": [item], "done": [_item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"])]}}
    assert rcar.check("open", item, _w14(), CARRYOVER, in_section=False) == (
        None, ["2026-W13", "2026-03-30", "2026-03-31"])
    assert rcar.coverage(proposals, CARRYOVER) == []


def test_the_two_day_theme_rule_does_not_apply_to_a_carried_item():
    item = _item("Sleep", "still_open", ["c1"], ["2026-W13", "2026-03-30"])       # one day only
    assert rd.check_item("themes", {"text": "Sleep", "sources": ["2026-03-30"]}, _w14())[0] == rd.THEME_DAYS
    assert rcar.check("themes", item, _w14(), CARRYOVER, in_section=False)[0] is None


# --- overflow (F4-AC10) ---------------------------------------------------------------------

def _theme_carryover():
    carryover = copy.deepcopy(CARRYOVER)
    carryover["items"] += [{"id": "c3", "type": "theme", "text": "Sleep", "sources": ["2026-02"]},
                           {"id": "c7", "type": "theme", "text": "Mood", "sources": ["2026-W13"]}]
    return carryover


def test_overflow_moves_to_group_of_mark():
    done = _item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"], mark="not_in_weekly")
    open_ = _item("Jana", "still_open", ["c2"], ["2026-W13", "2026-03-30"])
    gone = _item("Jana 2", "not_mentioned", ["c2", "c3"], ["2026-W13"])           # one id is no theme → open
    theme = _item("Sleep", "still_open", ["c3", "c7"], ["2026-02", "2026-03-30"])   # every id a theme → themes
    proposals = {"groups": {"open": [_plain("kept")]},
                 "sections": [{"key": "s1", "items": [done, _plain("a"), open_, gone, theme, _plain("b")]}]}
    before = copy.deepcopy(proposals)
    defs = {"s1": {"key": "s1", "cap": 2}}
    moved, notices = rcar.overflow(proposals, defs, _theme_carryover())
    assert proposals == before                                                     # input untouched
    assert [i["text"] for i in moved["sections"][0]["items"]] == ["a", "b"]
    assert moved["groups"]["themes"] == [theme]
    assert [i["text"] for i in moved["groups"]["open"]] == ["kept", "Jana 2", "Jana"]  # last carried moves first
    assert moved["groups"]["done"] == [{k: v for k, v in done.items() if k != "mark"}]  # child mark dropped
    assert notices == [{"key": "s1", "to": "themes", "count": 1}, {"key": "s1", "to": "open", "count": 2},
                       {"key": "s1", "to": "done", "count": 1}]


def test_overflow_stops_once_the_section_fits_and_moves_the_last_carried_first():
    first = _item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"])
    last = _item("Jana", "still_open", ["c2"], ["2026-W13", "2026-03-30"])
    proposals = {"sections": [{"key": "s1", "items": [first, _plain("a"), last]}]}
    moved, notices = rcar.overflow(proposals, {"s1": {"key": "s1", "cap": 2}}, CARRYOVER)
    assert moved["sections"][0]["items"] == [first, _plain("a")]
    assert moved["groups"] == {"open": [last]}
    assert notices == [{"key": "s1", "to": "open", "count": 1}]


def test_overflow_leaves_non_carried_items_over_the_cap():
    carried = _item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"])
    items = [_plain("a"), carried, _plain("b"), _plain("c")]
    moved, notices = rcar.overflow({"sections": [{"key": "s1", "items": items}]},
                                   {"s1": {"key": "s1", "cap": 2}}, CARRYOVER)
    assert [i["text"] for i in moved["sections"][0]["items"]] == ["a", "b", "c"]   # still over: 046 refuses it
    assert notices == [{"key": "s1", "to": "done", "count": 1}]
    assert any("over-cap (s1)" in e for e in rs.check(moved, SECTION_READ).errors)


def test_overflow_uses_the_default_cap_and_ignores_unknown_keys():
    from lib.review_config import DEFAULT_CAP
    carried = _item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"])
    full = [_plain(str(n)) for n in range(DEFAULT_CAP)] + [carried]
    moved, notices = rcar.overflow({"sections": [{"key": "s1", "items": list(full)}, {"key": "s9", "items": list(full)}]},
                                   {"s1": {"key": "s1"}}, CARRYOVER)
    assert len(moved["sections"][0]["items"]) == DEFAULT_CAP and moved["sections"][1]["items"] == full
    assert notices == [{"key": "s1", "to": "done", "count": 1}]


def test_overflow_within_the_cap_moves_nothing():
    proposals = {"sections": [{"key": "s1", "items": [_item("Run", "done", ["c1"], ["2026-W13", "2026-03-31"])]}]}
    assert rcar.overflow(proposals, {"s1": {"key": "s1", "cap": 2}}, CARRYOVER) == (proposals, [])


# --- module contract -------------------------------------------------------------------------

def test_module_header_and_size():
    path = TESTS_DIR.parent / "tomo" / "scripts" / "lib" / "review_carried.py"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[1] == "# version: 0.1.1"
    assert len(lines) <= 300

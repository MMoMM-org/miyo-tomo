#!/usr/bin/env python3
# version: 0.2.0
"""test_review_sections.py — lib/review_sections.py and the spec 046 proposals schema (046 T4.1).

Synthetic read.json / proposals.json dicts, no Kado:
- the schema: ``sections`` entries need a key ``^s[0-9]{1,3}$`` and items; ``mark`` is allowed on
  section items only (the group item schema is unchanged); the quarter groups ``monthly_only`` /
  ``not_in_monthly`` are valid group keys
- the per-kind group tables keep the week and month order, the quarter adds its pair
- the quarter groups: ``monthly_only`` needs a listed monthly note, a quarter without monthly notes
  rejects both groups with ``no-monthly-notes``, a week or month rejects them with
  ``quarter-only-group``
- the section checks: ``unknown-section`` (also with no mapping at all), ``duplicate-section``,
  ``over-cap``, ``double-placement`` (normalised text; sources + first line; across sections and
  groups; only with a mapping), ``mark-not-allowed`` per kind and without child notes, and the source
  rule for section items (``no-source-in-period``: a daily of the period, or the weekly / monthly
  note for a ``weekly_only`` / ``monthly_only`` mark)
- spec 045 proposals without ``sections`` and a read without ``sections`` give no section result and
  check_items exactly as before
- an echoed rendered line (`x ([[a]]) %%t1%%`) loses its id before its trailing link list (T4.2)
- spec 047 T5.4: a carried section item takes the carried branch after the 046 mark check, keeps
  `carried` and its mark, fails as an error never a rejected row (empty-text included); section_cap is
  public; an off-limits heading is never a section, so a carried item goes to the next section or its group

All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib import review_doc as rd  # noqa: E402
from lib import review_sections as rs  # noqa: E402
from test_review_doc import DAILY, WEEKLY, _day, item, month_read, proposals, week_read  # noqa: E402

MONTHLY = "Calendar/303 Monthly/"


def quarter_read(monthly=True, **overrides) -> dict:
    days = [f"2026-{m:02d}-{d:02d}" for m in (1, 2, 3) for d in (5, 15, 25)]
    read = week_read(period={"kind": "quarter", "name": "2026-Q1", "start": "2026-01-01", "end": "2026-03-31"},
                     days=[_day(d) for d in days], **overrides)
    read["weekly"] = [{"path": f"{WEEKLY}2026-W03.md", "week": "2026-W03", "overlap_days": 7}]
    read["monthly"] = ([{"path": f"{MONTHLY}2026-02.md", "month": "2026-02", "overlap_days": 28,
                         "duplicate": False}] if monthly else [])
    return read


def definition(key="s1", cap=8) -> dict:
    return {"key": key, "heading": "What went well", "level": 2, "parent": None, "description": "d",
            "keywords": [], "groups": ["done"], "cap": cap}


def mapped(read: dict, *defs: dict) -> dict:
    read["sections"] = list(defs) or [definition()]
    return read


def with_sections(props: dict, *entries: dict) -> dict:
    props["sections"] = list(entries)
    return props


def section(key: str, *items: dict) -> dict:
    return {"key": key, "items": list(items)}


def marked(text: str, mark: str, *sources: str) -> dict:
    return {**item(text, *sources), "mark": mark}


# ---------------------------------------------------------------- the schema

def test_sections_with_keys_and_items_are_valid():
    props = with_sections(proposals(), section("s1", item("a", "2026-03-24")), section("s999"),
                          section("s2", marked("b", "weekly_only", "2026-W13")))
    props["sections"][1]["items"] = []
    assert rd.proposal_problems(props) == []


@pytest.mark.parametrize("key", ["S1", "s", "s1000", "x1", "s1 ", "1", ""])
def test_a_section_key_outside_the_row_id_pattern_is_invalid(key):
    assert rd.proposal_problems(with_sections(proposals(), section(key))) == ["/sections/0/key"]


def test_a_section_entry_needs_key_and_items_and_nothing_else():
    assert rd.proposal_problems(with_sections(proposals(), {"key": "s1"})) == ["/sections/0"]
    assert rd.proposal_problems(with_sections(proposals(), {"items": []})) == ["/sections/0"]
    assert rd.proposal_problems(with_sections(proposals(), {"key": "s1", "items": [], "heading": "x"})) == [
        "/sections/0"]


def test_a_mark_is_allowed_on_section_items_only_and_from_the_four_marks():
    for mark in ("weekly_only", "not_in_weekly", "monthly_only", "not_in_monthly"):
        assert rd.proposal_problems(with_sections(proposals(), section("s1", marked("a", mark, "x")))) == []
    assert rd.proposal_problems(with_sections(proposals(), section("s1", marked("a", "done", "x")))) == [
        "/sections/0/items/0/mark"]
    assert rd.proposal_problems(proposals(done=[marked("a", "weekly_only", "x")])) == ["/groups/done/0"]


def test_the_quarter_groups_are_group_keys_and_habits_is_still_refused():
    assert rd.proposal_problems(proposals(monthly_only=[item("a", "x")], not_in_monthly=[item("b", "x")])) == []
    assert rd.proposal_problems(proposals(habits=[item("a", "x")])) == ["/groups"]


# ---------------------------------------------------------------- the group tables

def test_the_group_tables_keep_the_week_and_month_order_and_add_the_quarter_pair():
    base = ["done", "open", "themes", "growth", "habits"]
    assert list(rd.KIND_GROUPS["week"]) == base
    assert list(rd.KIND_GROUPS["month"]) == base + ["weekly_only", "not_in_weekly"]
    assert list(rd.KIND_GROUPS["quarter"]) == base + ["monthly_only", "not_in_monthly"]


def test_monthly_only_needs_a_monthly_note_and_the_quarter_groups_need_monthly_notes():
    props = proposals(monthly_only=[item("only there", f"{MONTHLY}2026-02.md"), item("daily", "2026-02-15"),
                                    item("weekly is no monthly", "2026-W03")],
                      not_in_monthly=[item("left out", "2026-01-05")])
    accepted, rejected, _ = rd.check_items(props, quarter_read())
    assert accepted["monthly_only"] == [{"text": "only there", "links": ["2026-02"]}]
    assert accepted["not_in_monthly"] == [{"text": "left out", "links": ["2026-01-05"]}]
    assert rejected == [{"group": "monthly_only", "index": 1, "reason": "no-source-in-period"},
                        {"group": "monthly_only", "index": 2, "reason": "no-source-in-period"}]
    accepted, rejected, _ = rd.check_items(props, quarter_read(monthly=False))
    assert "monthly_only" not in accepted and {r["reason"] for r in rejected} == {"no-monthly-notes"}
    for read in (week_read(), month_read()):
        accepted, rejected, _ = rd.check_items(props, read)
        assert "monthly_only" not in accepted and {r["reason"] for r in rejected} == {"quarter-only-group"}


def test_a_quarter_still_rejects_the_month_groups():
    _, rejected, _ = rd.check_items(proposals(weekly_only=[item("a", "2026-W03")]), quarter_read())
    assert rejected == [{"group": "weekly_only", "index": 0, "reason": "month-only-group"}]


# ---------------------------------------------------------------- no mapping: spec 045 unchanged

DOUBLED = proposals(done=[item("Same", "2026-03-24")], open=[item("same", "2026-03-24")])


def test_without_a_mapping_spec_045_proposals_give_no_section_result():
    result = rs.check(DOUBLED, week_read())
    assert (result.accepted, result.rejected, result.errors) == ({}, [], [])
    accepted, rejected, _ = rd.check_items(DOUBLED, week_read())
    assert [i["text"] for i in accepted["done"] + accepted["open"]] == ["Same", "same"] and rejected == []


def test_without_a_mapping_any_section_is_unknown():
    result = rs.check(with_sections(proposals(), section("s1", item("a", "2026-03-24"))), week_read())
    assert result.errors == ["/sections/0/key: unknown-section"] and result.accepted == {}


def test_without_a_mapping_no_double_placement_runs_even_beside_a_section():
    props = with_sections(proposals(done=[item("a", "2026-03-24")]), section("s1", item("a", "2026-03-24")))
    assert rs.check(props, week_read()).errors == ["/sections/0/key: unknown-section"]


# ---------------------------------------------------------------- keys and caps

def test_a_key_without_a_definition_is_unknown_and_a_known_one_is_accepted():
    props = with_sections(proposals(), section("s1", item("a", "2026-03-24")), section("s7", item("b", "2026-03-25")))
    result = rs.check(props, mapped(week_read()))
    assert result.errors == ["/sections/1/key: unknown-section"]
    assert result.accepted == {"s1": [{"text": "a", "links": ["2026-03-24"]}]}


def test_a_key_named_twice_is_refused_on_the_second_entry():
    props = with_sections(proposals(), section("s1", item("a", "2026-03-24")), section("s1", item("b", "2026-03-25")))
    assert rs.check(props, mapped(week_read())).errors == ["/sections/1/key: duplicate-section"]


def test_more_items_than_the_cap_are_refused_never_truncated():
    read = mapped(week_read(), definition("s1", cap=2), definition("s2", cap=3))
    days = ["2026-03-23", "2026-03-24", "2026-03-25"]
    props = with_sections(proposals(), section("s1", *[item(f"a{d}", d) for d in days]),
                          section("s2", *[item(f"b{d}", d) for d in days]))
    result = rs.check(props, read)
    assert result.errors == ["/sections/0/items: over-cap (s1)"]
    assert len(result.accepted["s1"]) == 3                       # refused as a whole, nothing cut


def test_the_cap_counts_the_proposed_items_before_the_source_rule():
    read = mapped(week_read(), definition("s1", cap=1))
    props = with_sections(proposals(), section("s1", item("ok", "2026-03-24"), item("no source", "Efforts/X.md")))
    assert rs.check(props, read).errors == ["/sections/0/items: over-cap (s1)"]


# ---------------------------------------------------------------- the source rule

def test_a_section_item_needs_a_daily_of_the_period():
    props = with_sections(proposals(), section("s1", item("ok", "2026-03-24", "Efforts/X.md"),
                                               item("outside", "2026-02-27"), item("weekly alone", "2026-W13"),
                                               item("  ", "2026-03-24")))
    result = rs.check(props, mapped(month_read()))
    assert result.errors == []
    assert result.accepted == {"s1": [{"text": "ok", "links": ["2026-03-24"]}]}
    assert result.rejected == [{"section": "s1", "index": 1, "reason": "no-source-in-period"},
                               {"section": "s1", "index": 2, "reason": "no-source-in-period"},
                               {"section": "s1", "index": 3, "reason": "empty-text"}]


def test_a_review_only_mark_rests_on_the_weekly_or_monthly_note():
    month = with_sections(proposals(), section("s1", marked("w", "weekly_only", f"{WEEKLY}2026-W13.md"),
                                               marked("w daily", "weekly_only", "2026-03-24"),
                                               marked("n", "not_in_weekly", "2026-03-24"),
                                               marked("n weekly", "not_in_weekly", "2026-W13")))
    result = rs.check(month, mapped(month_read()))
    assert result.errors == []
    assert result.accepted["s1"] == [{"text": "w", "links": ["2026-W13"], "mark": "weekly_only"},
                                     {"text": "n", "links": ["2026-03-24"], "mark": "not_in_weekly"}]
    assert [(r["index"], r["reason"]) for r in result.rejected] == [(1, "no-source-in-period"),
                                                                    (3, "no-source-in-period")]
    quarter = with_sections(proposals(), section("s1", marked("m", "monthly_only", "2026-02"),
                                                 marked("m weekly", "monthly_only", "2026-W03"),
                                                 item("weekly alone", "2026-W03")))
    result = rs.check(quarter, mapped(quarter_read()))
    assert result.accepted["s1"] == [{"text": "m", "links": ["2026-02"], "mark": "monthly_only"}]
    assert [(r["index"], r["reason"]) for r in result.rejected] == [(1, "no-source-in-period"),
                                                                    (2, "no-source-in-period")]


def test_a_theme_like_section_item_needs_only_one_day():
    props = with_sections(proposals(), section("s1", item("one day", "2026-03-24")))
    assert rs.check(props, mapped(week_read())).rejected == []


# ---------------------------------------------------------------- marks

@pytest.mark.parametrize("read_of, mark", [
    (week_read, "weekly_only"), (week_read, "not_in_monthly"),
    (month_read, "monthly_only"), (month_read, "not_in_monthly"),
    (quarter_read, "weekly_only"), (quarter_read, "not_in_weekly"),
])
def test_a_mark_of_another_kind_is_not_allowed(read_of, mark):
    props = with_sections(proposals(), section("s1", marked("a", mark, "2026-03-24", "2026-02-15")))
    result = rs.check(props, mapped(read_of()))
    assert result.errors == ["/sections/0/items/0/mark: mark-not-allowed"] and result.accepted == {"s1": []}


def test_a_mark_without_the_child_notes_read_is_not_allowed():
    month = with_sections(proposals(), section("s1", marked("a", "not_in_weekly", "2026-03-24")))
    assert rs.check(month, mapped(month_read())).errors == []
    assert rs.check(month, mapped(month_read(weekly=False))).errors == ["/sections/0/items/0/mark: mark-not-allowed"]
    quarter = with_sections(proposals(), section("s1", marked("a", "not_in_monthly", "2026-02-15")))
    assert rs.check(quarter, mapped(quarter_read())).errors == []
    assert rs.check(quarter, mapped(quarter_read(monthly=False))).errors == [
        "/sections/0/items/0/mark: mark-not-allowed"]


# ---------------------------------------------------------------- double placement

def test_the_same_normalised_text_in_a_section_and_a_group_is_refused_on_the_later_one():
    props = with_sections(proposals(done=[item("Finished  the   REPORT ([[2026-03-25]])", "2026-03-25")]),
                          section("s1", item("finished the report", "2026-03-24")))
    assert rs.check(props, mapped(week_read())).errors == ["/groups/done/0: double-placement"]


def test_the_same_text_in_two_sections_is_refused_on_the_later_one():
    read = mapped(week_read(), definition("s1"), definition("s2"))
    props = with_sections(proposals(), section("s1", item("Ran %% twice", "2026-03-24")),
                          section("s2", item("ran twice\n", "2026-03-25")))
    assert rs.check(props, read).errors == ["/sections/1/items/0: double-placement"]


def test_the_same_sources_and_first_line_are_refused_and_a_different_first_line_is_not():
    read = mapped(week_read(), definition("s1"), definition("s2"))
    props = with_sections(proposals(open=[item("Call Anna\nabout the offer", f"{DAILY}2026-03-24.md")]),
                          section("s1", item("call anna\nand the budget", "2026-03-24")),
                          section("s2", item("Call Bert\nabout the offer", "2026-03-24")))
    assert rs.check(props, read).errors == ["/groups/open/0: double-placement"]


def test_the_same_first_line_with_other_sources_is_not_a_double():
    props = with_sections(proposals(done=[item("Call Anna\nabout x", "2026-03-24")]),
                          section("s1", item("Call Anna\nabout y", "2026-03-25")))
    assert rs.check(props, mapped(week_read())).errors == []


def test_two_identical_group_items_are_a_double_only_with_a_mapping():
    assert rs.check(DOUBLED, mapped(week_read())).errors == ["/groups/open/0: double-placement"]
    assert rs.check(DOUBLED, week_read()).errors == []


@pytest.mark.parametrize("first, second", [
    ("Talked with [[Anna]] about the offer", "Talked with [[Bert]] about the offer"),
    ("Met [[Anna]]", "Met [[Bob]]"),
    ("[[Anna|the client]] called", "[[Bert|the client]] called"),
    ("[[Anna#Offer]] x", "[[Anna#Budget]] x"),
    ("![[chart-a.png]] x", "![[chart-b.png]] x"),
])
def test_an_inline_link_keeps_its_target_so_different_targets_are_not_a_double(first, second):
    props = with_sections(proposals(done=[item(first, "2026-03-24")]), section("s1", item(second, "2026-03-25")))
    assert rs.check(props, mapped(week_read())).errors == []


def test_an_inline_link_with_the_same_target_is_a_double_whatever_its_alias():
    props = with_sections(proposals(done=[item("Met [[Anna|her]]", "2026-03-24")]),
                          section("s1", item("met [[Anna]]", "2026-03-25")))
    assert rs.check(props, mapped(week_read())).errors == ["/groups/done/0: double-placement"]


def test_a_trailing_link_list_with_aliases_and_headings_normalises_away():
    props = with_sections(proposals(done=[item("Finished the report ([[2026-03-02|Mon]], [[2026-03-03#Log]])",
                                               "2026-03-24")]),
                          section("s1", item("finished the report ([[2026-03-25]])", "2026-03-25")))
    assert rs.check(props, mapped(week_read())).errors == ["/groups/done/0: double-placement"]


def test_an_echoed_rendered_line_loses_its_id_before_its_link_list():
    # the rendered form ends "([[stem]]) %%tN%%": the id goes first, so the list is trailing again (046 T4.2)
    props = with_sections(proposals(done=[item("Finished the report ([[2026-03-25]]) %%t1%%", "2026-03-24")]),
                          section("s1", item("finished the report", "2026-03-25")))
    assert rs.check(props, mapped(week_read())).errors == ["/groups/done/0: double-placement"]


@pytest.mark.parametrize("key", ["s1", "s7"])
def test_a_refused_section_entry_adds_no_double_placement(key):
    props = with_sections(proposals(), section("s1", item("a", "2026-03-23")), section(key, item("a", "2026-03-24")))
    error = "duplicate-section" if key == "s1" else "unknown-section"
    assert rs.check(props, mapped(week_read())).errors == [f"/sections/1/key: {error}"]
    props["groups"]["done"] = [item("a", "2026-03-24")]       # the pass still runs on the accepted places
    assert rs.check(props, mapped(week_read())).errors == [f"/sections/1/key: {error}",
                                                           "/groups/done/0: double-placement"]


# ---------------------------------------------------------------- spec 047 T5.4: the carried branch, sections

PREV_FEB = f"{MONTHLY}2026-02.md"
MONTH_CARRY = {"read_id": "r2", "notes": [{"path": PREV_FEB, "kind": "month", "name": "2026-02", "items": 2}],
               "items": [{"id": "c4", "type": "intention", "text": "screen", "sources": ["2026-02"]},
                         {"id": "c5", "type": "open", "text": "dentist", "sources": ["2026-02"]}]}


def carried(text: str, value: str, ids, *sources: str, mark=None) -> dict:
    out = {**item(text, *sources), "carried": value, "carried_ids": list(ids)}
    return {**out, "mark": mark} if mark else out


def carried_month(carryover=MONTH_CARRY, weekly=True) -> dict:
    read = mapped(month_read(weekly=weekly), definition("s1"), definition("s3"))
    read["previous"] = [{"kind": "month", "name": "2026-02", "path": PREV_FEB, "state": "found"}]
    read["carryover"] = carryover
    return read


def test_a_carried_section_item_is_accepted_with_its_carried_value_and_its_mark():
    props = with_sections(proposals(), section("s3", carried("Weniger Bildschirm", "still_open", ["c4"], "2026-02",
                                                             "2026-03-12", mark="not_in_weekly"),
                                               carried("Zahnarzt", "not_mentioned", ["c5"], PREV_FEB)))
    result = rs.check(props, carried_month())
    assert (result.errors, result.rejected) == ([], [])
    assert result.accepted["s3"] == [
        {"text": "Weniger Bildschirm", "links": ["2026-02", "2026-03-12"], "carried": "still_open",
         "mark": "not_in_weekly"},
        {"text": "Zahnarzt", "links": ["2026-02"], "carried": "not_mentioned"}]


def test_a_carried_section_failure_is_an_error_never_a_rejected_row():
    props = with_sections(proposals(), section("s1", carried("a", "still_open", ["c4"], "2026-02", "2026-W13",
                                                             mark="weekly_only"),
                                               carried("b", "done", ["c5"], "2026-03-12"),
                                               item("kein Tag", "2026-04-02")))
    result = rs.check(props, carried_month())
    assert result.errors == ["/sections/0/items/0: carried-mark-conflict",
                             "/sections/0/items/1: carried-needs-previous-note"]
    assert result.rejected == [{"section": "s1", "index": 2, "reason": rd.NO_SOURCE}]


def test_a_carried_section_item_without_a_carryover_is_refused():
    props = with_sections(proposals(), section("s1", carried("a", "done", ["c4"], "2026-02", "2026-03-12")))
    assert rs.check(props, carried_month(carryover=None)).errors == ["/sections/0/items/0: carried-without-carryover"]


def test_a_carried_item_keeps_the_spec_046_mark_check_first():
    props = with_sections(proposals(), section("s1", carried("a", "still_open", ["c4"], "2026-02", "2026-03-12",
                                                             mark="not_in_monthly")))
    assert rs.check(props, carried_month()).errors == ["/sections/0/items/0/mark: mark-not-allowed"]
    props = with_sections(proposals(), section("s1", carried("a", "still_open", ["c4"], "2026-02", "2026-03-12",
                                                             mark="not_in_weekly")))
    assert rs.check(props, carried_month(weekly=False)).errors == ["/sections/0/items/0/mark: mark-not-allowed"]


def test_a_whitespace_only_carried_section_item_is_an_empty_text_error():
    props = with_sections(proposals(), section("s1", carried(" \t ", "done", ["c4"], "2026-02", "2026-03-12")))
    result = rs.check(props, carried_month())
    assert (result.errors, result.rejected) == (["/sections/0/items/0: empty-text"], [])


def test_the_section_cap_is_public_and_the_one_rule_overflow_uses():
    from lib import review_carried as rcar
    from lib.review_config import DEFAULT_CAP

    assert rs.section_cap({"cap": 2}) == 2 and rs.section_cap({}) == DEFAULT_CAP
    assert rs.section_cap({"cap": True}) == DEFAULT_CAP
    full = with_sections(proposals(), section("s1", item("a", "2026-03-12"),
                                              carried("b", "done", ["c4"], "2026-02", "2026-03-12")))
    _, notices = rcar.overflow(full, {"s1": definition("s1", cap=1)}, MONTH_CARRY)
    assert notices == [{"key": "s1", "to": "done", "count": 1}]


def test_an_off_limits_heading_is_never_a_section_so_no_carried_item_lands_there():
    from lib import review_mapping as rm

    template = "# T\n\n## Health\n\n## Wins\n\n## Notes\n"
    heads = {h.heading: h for h in rm.analyse_template(template, [{"heading": "Health", "level": 2,
                                                                     "parent": None, "occurrence": 1}])}
    assert heads["Health"].state == "left-out" and heads["Health"].reason == rm.OFF_LIMITS
    assert heads["Wins"].state == "offered"
    # the off-limits heading never became a row, so the read has no definition for it
    read = carried_month()
    misplaced = with_sections(proposals(), section("s9", carried("a", "done", ["c4"], "2026-02", "2026-03-12")))
    assert rs.check(misplaced, read).errors == ["/sections/0/key: unknown-section"]
    in_next = with_sections(proposals(), section("s3", carried("a", "done", ["c4"], "2026-02", "2026-03-12")))
    assert rs.check(in_next, read).errors == []
    in_group = proposals(done=[carried("a", "done", ["c4"], "2026-02", "2026-03-12")])
    accepted, rejected, errors = rd.check_items(in_group, read)
    assert (rejected, errors) == ([], []) and accepted["done"][0]["carried"] == "done"

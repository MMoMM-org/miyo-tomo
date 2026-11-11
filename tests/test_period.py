#!/usr/bin/env python3
# version: 0.1.0
"""test_period.py — Behavioural tests for lib.period (spec 045 T1.1).

Covers the period arithmetic behind /review:
- the week rule (first day, min days in week 1): every row of the SDD
  walkthrough table, ISO == WeekRule(Monday, 4) against date.isocalendar()
  for every day 2020-2030, 52/53-week years
- months and the weeks overlapping them (ISO week 53 at both year ends)
- is_finished (end < today) and note_paths (flat, then the year folder:
  week year for weeks, calendar year for months)
- name formats: render and parse for GGGG-[W]WW, gggg-[W]ww, YYYY-MM and
  literals; check_format refuses YYYY with a week token (naming the
  year-end example) and literals containing "/", "\\" or ".."
- argument parsing to a request or an error object: '', month, setup, W13,
  2026-W13, M03, 2026-03, @<path>; invalid forms; a missing year picks the
  latest finished period; unfinished and future periods are refused with
  the last finished one named
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import period  # noqa: E402
from lib.period import (  # noqa: E402
    ISO,
    InvalidPeriod,
    Period,
    Request,
    RequestError,
    WeekRule,
    check_format,
    parse_args,
    parse_name,
    render_name,
)

TODAY = date(2026, 11, 11)  # a Wednesday in ISO 2026-W46
SUNDAY_FIRST = WeekRule(first_day=6, min_days_in_first_week=1)
FORMATS = {"week": "GGGG-[W]WW", "month": "YYYY-MM"}


def _parse(raw: str, **overrides):
    kwargs = dict(today=TODAY, rule=ISO, formats=FORMATS)
    kwargs.update(overrides)
    return parse_args(raw, **kwargs)


# --- the SDD walkthrough table -------------------------------------------------

def test_2026_03_26_is_iso_week_13_monday_to_sunday():
    assert ISO.week_of(date(2026, 3, 26)) == (2026, 13)
    week = Period.week(2026, 13)
    assert week.start == date(2026, 3, 23)
    assert week.end == date(2026, 3, 29)
    assert week.days() == [date(2026, 3, 23) + timedelta(days=i) for i in range(7)]
    assert week.name == "2026-W13"


def test_2026_12_31_is_week_53_of_2026_running_into_january():
    assert ISO.week_of(date(2026, 12, 31)) == (2026, 53)
    week = Period.week(2026, 53)
    assert week.start == date(2026, 12, 28)
    assert week.end == date(2027, 1, 3)
    assert ISO.weeks_in(2026) == 53


def test_2027_01_01_belongs_to_week_53_of_2026():
    assert ISO.week_of(date(2027, 1, 1)) == (2026, 53)


def test_2025_12_29_belongs_to_week_1_of_2026():
    assert ISO.week_of(date(2025, 12, 29)) == (2026, 1)
    assert Period.week(2026, 1).start == date(2025, 12, 29)


def test_2025_has_no_week_53():
    assert ISO.weeks_in(2025) == 52
    with pytest.raises(InvalidPeriod):
        Period.week(2025, 53)
    error = _parse("2025-W53")
    assert isinstance(error, RequestError)
    assert error.kind == "invalid-period"
    assert error.example == "2025-W52"


def test_sunday_first_one_day_rule_puts_2026_03_01_in_week_10():
    assert SUNDAY_FIRST.week_of(date(2026, 3, 1)) == (2026, 10)
    assert ISO.week_of(date(2026, 3, 1)) == (2026, 9)
    week = Period.week(2026, 10, SUNDAY_FIRST)
    assert week.start == date(2026, 3, 1)
    assert week.end == date(2026, 3, 7)


def test_week_53_belongs_to_the_old_week_year():
    request = _parse("2026-W53", today=date(2027, 1, 10))
    assert isinstance(request, Request)
    assert request.period.days()[-1] == date(2027, 1, 3)


# --- ISO invariant ---------------------------------------------------------------

def test_iso_rule_equals_isocalendar_for_every_day_2020_to_2030():
    day = date(2020, 1, 1)
    last = date(2030, 12, 31)
    while day <= last:
        iso = day.isocalendar()
        assert ISO.week_of(day) == (iso[0], iso[1]), day
        day += timedelta(days=1)


def test_iso_week_start_is_the_monday_isocalendar_names():
    for year in range(2020, 2031):
        for week in range(1, ISO.weeks_in(year) + 1):
            start = ISO.week_start(year, week)
            assert start.weekday() == 0
            assert start.isocalendar()[:2] == (year, week)


def test_iso_is_the_monday_four_day_rule():
    assert ISO == WeekRule(first_day=0, min_days_in_first_week=4)
    assert WeekRule.from_config("monday", 4) == ISO
    assert WeekRule.from_config("sunday", 1) == SUNDAY_FIRST


def test_week_rule_refuses_values_outside_the_calendar():
    with pytest.raises(ValueError):
        WeekRule(first_day=7, min_days_in_first_week=4)
    with pytest.raises(ValueError):
        WeekRule(first_day=0, min_days_in_first_week=0)
    with pytest.raises(ValueError):
        WeekRule.from_config("funday", 4)


def test_week_number_outside_the_year_is_refused():
    with pytest.raises(InvalidPeriod):
        Period.week(2026, 0)
    with pytest.raises(InvalidPeriod):
        Period.week(2026, 54)
    with pytest.raises(InvalidPeriod):
        Period.month(2026, 13)
    with pytest.raises(InvalidPeriod):
        Period.month(2026, 0)


# --- months and overlapping weeks ----------------------------------------------

def test_march_2026_is_the_calendar_month():
    month = Period.month(2026, 3)
    assert month.start == date(2026, 3, 1)
    assert month.end == date(2026, 3, 31)
    assert len(month.days()) == 31
    assert month.name == "2026-03"


def test_march_2026_overlaps_iso_weeks_9_to_14():
    names = [w.name for w in Period.month(2026, 3).weeks_overlapping(ISO)]
    assert names == ["2026-W09", "2026-W10", "2026-W11", "2026-W12", "2026-W13", "2026-W14"]


def test_january_2027_starts_with_week_53_of_2026():
    weeks = Period.month(2027, 1).weeks_overlapping(ISO)
    assert weeks[0].name == "2026-W53"
    assert weeks[0].year == 2026 and weeks[0].number == 53
    assert weeks[1].name == "2027-W01"


def test_december_2026_ends_with_week_53_of_2026():
    weeks = Period.month(2026, 12).weeks_overlapping(ISO)
    assert weeks[-1].name == "2026-W53"
    assert weeks[0].name == "2026-W49"


def test_overlapping_weeks_follow_the_configured_rule():
    names = [w.name for w in Period.month(2026, 3).weeks_overlapping(SUNDAY_FIRST)]
    assert names[0] == "2026-W10"
    assert names[-1] == "2026-W14"


def test_a_week_has_no_overlapping_weeks():
    with pytest.raises(ValueError):
        Period.week(2026, 13).weeks_overlapping(ISO)


# --- is_finished ------------------------------------------------------------------

def test_a_period_is_finished_only_when_its_end_lies_before_today():
    assert Period.week(2026, 45).is_finished(TODAY)          # ended 2026-11-08
    assert not Period.week(2026, 46).is_finished(TODAY)      # running
    assert not Period.week(2026, 47).is_finished(TODAY)      # future
    assert Period.month(2026, 10).is_finished(TODAY)
    assert not Period.month(2026, 11).is_finished(TODAY)
    assert Period.week(2026, 45).is_finished(date(2026, 11, 9))
    assert not Period.week(2026, 45).is_finished(date(2026, 11, 8))


def test_last_finished_period_of_each_kind():
    assert period.last_finished("week", TODAY, ISO).name == "2026-W45"
    assert period.last_finished("month", TODAY, ISO).name == "2026-10"
    assert period.last_finished("week", date(2027, 1, 4), ISO).name == "2026-W53"
    assert period.last_finished("month", date(2027, 1, 1), ISO).name == "2026-12"


# --- note_paths -----------------------------------------------------------------

def test_week_note_paths_are_flat_then_the_week_year_folder():
    paths = Period.week(2026, 53).note_paths("Calendar/302 Weekly/", "GGGG-[W]WW")
    assert paths == ["Calendar/302 Weekly/2026-W53.md", "Calendar/302 Weekly/2026/2026-W53.md"]


def test_month_note_paths_use_the_calendar_year_folder():
    paths = Period.month(2027, 1).note_paths("Calendar/303 Monthly", "YYYY-MM")
    assert paths == ["Calendar/303 Monthly/2027-01.md", "Calendar/303 Monthly/2027/2027-01.md"]


def test_note_paths_render_the_configured_format():
    paths = Period.week(2026, 10, SUNDAY_FIRST).note_paths("Weekly/", "[Week ]gggg-[W]ww")
    assert paths == ["Weekly/Week 2026-W10.md", "Weekly/2026/Week 2026-W10.md"]


# --- name formats: render and parse -------------------------------------------------

def test_render_iso_week_format():
    assert render_name(Period.week(2026, 13), "GGGG-[W]WW") == "2026-W13"
    assert render_name(Period.week(2026, 5), "GGGG-[W]W") == "2026-W5"
    assert render_name(Period.week(2026, 53), "GGGG-[W]WW") == "2026-W53"


def test_render_rule_week_format_follows_the_configured_rule():
    week = Period.week(2026, 10, SUNDAY_FIRST)
    assert render_name(week, "gggg-[W]ww") == "2026-W10"
    assert render_name(week, "GGGG-[W]WW") == "2026-W09"  # ISO week of its first day


def test_render_month_formats_and_literals():
    assert render_name(Period.month(2026, 3), "YYYY-MM") == "2026-03"
    assert render_name(Period.month(2026, 3), "YYYY-M") == "2026-3"
    assert render_name(Period.month(2026, 3), "[Month ]YYYY-MM[ (review)]") == "Month 2026-03 (review)"
    assert render_name(Period.week(2026, 13), "[Week ]GGGG-[W]WW") == "Week 2026-W13"


def test_render_refuses_a_format_of_the_other_kind():
    with pytest.raises(ValueError):
        render_name(Period.month(2026, 3), "GGGG-[W]WW")
    with pytest.raises(ValueError):
        render_name(Period.week(2026, 13), "YYYY-MM")


def test_parse_name_round_trips_each_format():
    assert parse_name("2026-W13", "GGGG-[W]WW", ISO) == Period.week(2026, 13)
    assert parse_name("2026-W5", "GGGG-[W]W", ISO) == Period.week(2026, 5)
    assert parse_name("2026-03", "YYYY-MM", ISO) == Period.month(2026, 3)
    assert parse_name("Week 2026-W13", "[Week ]GGGG-[W]WW", ISO) == Period.week(2026, 13)
    assert parse_name("Month 2026-03 (review)", "[Month ]YYYY-MM[ (review)]", ISO) == Period.month(2026, 3)


def test_parse_name_gggg_follows_the_rule_and_GGGG_stays_iso():
    by_rule = parse_name("2026-W10", "gggg-[W]ww", SUNDAY_FIRST)
    assert by_rule == Period.week(2026, 10, SUNDAY_FIRST)
    assert by_rule.start == date(2026, 3, 1)
    by_iso = parse_name("2026-W10", "GGGG-[W]WW", SUNDAY_FIRST)
    assert by_iso.start == date(2026, 3, 2)


def test_parse_name_returns_none_for_a_name_that_does_not_fit():
    assert parse_name("2026-03-26", "GGGG-[W]WW", ISO) is None
    assert parse_name("2026-W54", "GGGG-[W]WW", ISO) is None
    assert parse_name("2026-13", "YYYY-MM", ISO) is None
    assert parse_name("2026-W13", "YYYY-MM", ISO) is None
    assert parse_name("Notes", "YYYY-MM", ISO) is None
    assert parse_name("x2026-W13", "GGGG-[W]WW", ISO) is None


# --- check_format -------------------------------------------------------------------

def test_check_format_accepts_the_default_formats():
    assert check_format("GGGG-[W]WW", "week", ISO, today=TODAY) == []
    assert check_format("gggg-[W]ww", "week", SUNDAY_FIRST, today=TODAY) == []
    assert check_format("YYYY-MM", "month", ISO, today=TODAY) == []
    assert check_format("[Week ]GGGG-[W]WW", "week", ISO, today=TODAY) == []


def test_check_format_refuses_calendar_year_with_a_week_token_naming_the_year_end():
    problems = check_format("YYYY-[W]WW", "week", ISO, today=TODAY)
    assert [p.kind for p in problems] == ["calendar-year-with-week"]
    assert "2027-01-01" in problems[0].example
    assert "2027-W53" in problems[0].example
    assert "2026-W53" in problems[0].example


def test_check_format_year_end_example_follows_the_rule():
    problems = check_format("YYYY-[W]ww", "week", SUNDAY_FIRST, today=TODAY)
    assert [p.kind for p in problems] == ["calendar-year-with-week"]
    # under (Sunday, 1) the first mismatch after 2026 is 2026-12-27, week 1 of 2027
    assert "2026-12-27" in problems[0].example
    assert "2027-W01" in problems[0].example


@pytest.mark.parametrize("fmt", ["GGGG/[W]WW", "[a/b]GGGG-[W]WW", "GGGG\\[W]WW", "..GGGG-[W]WW", "[..]YYYY-MM"])
def test_check_format_refuses_literals_that_could_leave_the_folder(fmt):
    kind = "month" if "YYYY-MM" in fmt else "week"
    problems = check_format(fmt, kind, ISO, today=TODAY)
    assert "unsafe-format" in [p.kind for p in problems]


def test_check_format_refuses_a_format_of_the_wrong_kind_or_without_a_period():
    assert [p.kind for p in check_format("YYYY-MM", "week", ISO, today=TODAY)] == ["kind-mismatch"]
    assert [p.kind for p in check_format("GGGG-[W]WW", "month", ISO, today=TODAY)] == ["kind-mismatch"]
    assert [p.kind for p in check_format("[Weekly]", "week", ISO, today=TODAY)] == ["no-period-token"]
    assert [p.kind for p in check_format("[W]WW", "week", ISO, today=TODAY)] == ["no-year-token"]
    assert "unknown-token" in [p.kind for p in check_format("GGGG-[W]WW-DD", "week", ISO, today=TODAY)]


def test_check_format_requires_the_iso_rule_for_upper_case_week_tokens():
    assert [p.kind for p in check_format("GGGG-[W]WW", "week", SUNDAY_FIRST, today=TODAY)] == ["iso-tokens-need-iso-rule"]
    assert [p.kind for p in check_format("gggg-[W]WW", "week", ISO, today=TODAY)] == ["mixed-week-tokens"]


# --- argument parsing -----------------------------------------------------------------

def test_no_argument_is_the_last_finished_week():
    request = _parse("")
    assert isinstance(request, Request)
    assert request.kind == "week"
    assert request.period == Period.week(2026, 45)
    assert request.source == "default"
    assert request.year_inferred is False
    assert request.to_dict() == {"kind": "week", "period": "2026-W45", "year_inferred": False, "source": "default"}


def test_month_word_is_the_last_finished_month():
    request = _parse("month")
    assert request.kind == "month"
    assert request.period == Period.month(2026, 10)
    assert request.source == "default"


def test_setup_word_asks_for_the_setup():
    request = _parse("setup")
    assert request.kind == "setup"
    assert request.period is None
    assert request.to_dict() == {"kind": "setup"}


def test_default_week_follows_the_configured_rule():
    request = _parse("", rule=SUNDAY_FIRST)
    assert request.period.start == date(2026, 11, 1)
    assert request.period.end == date(2026, 11, 7)


def test_a_full_week_name_is_that_week():
    request = _parse("2026-W13")
    assert request.kind == "week"
    assert request.period == Period.week(2026, 13)
    assert request.source == "arg"
    assert request.year_inferred is False


def test_a_full_month_name_is_that_month():
    request = _parse("2026-03")
    assert request.kind == "month"
    assert request.period == Period.month(2026, 3)
    assert request.source == "arg"


def test_a_week_without_a_year_is_the_most_recent_finished_one():
    request = _parse("W13")
    assert request.period == Period.week(2026, 13)
    assert request.year_inferred is True
    assert _parse("w13").period == Period.week(2026, 13)
    assert _parse("W46").period == Period.week(2025, 46)   # 2026-W46 is running
    assert _parse("W53").period == Period.week(2020, 53)   # the last year with 53 weeks


def test_a_month_without_a_year_is_the_most_recent_finished_one():
    assert _parse("M03").period == Period.month(2026, 3)
    assert _parse("M3").year_inferred is True
    assert _parse("M11").period == Period.month(2025, 11)   # 2026-11 is running
    assert _parse("m10").period == Period.month(2026, 10)


def test_an_at_note_is_matched_against_the_configured_formats():
    week = _parse("@Calendar/302 Weekly/2026-W13.md")
    assert week.kind == "week"
    assert week.period == Period.week(2026, 13)
    assert week.source == "at"
    month = _parse("@Calendar/303 Monthly/2026-03.md")
    assert month.kind == "month"
    assert month.period == Period.month(2026, 3)
    assert _parse("@2026-W13").period == Period.week(2026, 13)
    assert _parse("@[[2026-W13]]").period == Period.week(2026, 13)
    assert _parse("@ Calendar/302 Weekly/2026-W13.md").period == Period.week(2026, 13)


def test_an_at_note_uses_the_configured_name_formats():
    formats = {"week": "[Week ]gggg-[W]ww", "month": "[Month ]YYYY-MM"}
    request = _parse("@Weekly/Week 2026-W10.md", rule=SUNDAY_FIRST, formats=formats)
    assert request.period == Period.week(2026, 10, SUNDAY_FIRST)
    assert _parse("@Monthly/Month 2026-03.md", formats=formats).period == Period.month(2026, 3)
    error = _parse("@Weekly/2026-W10.md", rule=SUNDAY_FIRST, formats=formats)
    assert error.kind == "not-periodic-note"


def test_an_at_note_that_fits_neither_format_is_not_a_periodic_note():
    error = _parse("@Calendar/301 Daily/2026-03-26.md")
    assert isinstance(error, RequestError)
    assert error.kind == "not-periodic-note"
    assert "GGGG-[W]WW" in error.expected and "YYYY-MM" in error.expected
    assert error.example == "2026-W45"
    assert error.to_dict() == {"kind": "not-periodic-note", "expected": error.expected, "example": "2026-W45"}


@pytest.mark.parametrize("raw, example", [
    ("2026-W54", "2026-W53"),
    ("2026-W00", "2026-W53"),
    ("2026-13", "2026-12"),
    ("2026-00", "2026-12"),
    ("month 2026-W13", "2026-10"),
    ("week 2026-03", "2026-W45"),
    ("W54", "2026-W45"),
    ("M13", "2026-10"),
])
def test_an_invalid_period_names_what_was_expected_and_one_example(raw, example):
    error = _parse(raw)
    assert isinstance(error, RequestError)
    assert error.kind == "invalid-period"
    assert error.expected
    assert error.example == example


def test_a_kind_word_with_a_matching_period_is_accepted():
    assert _parse("month 2026-03").period == Period.month(2026, 3)
    assert _parse("week 2026-W13").period == Period.week(2026, 13)
    assert _parse("week").period == Period.week(2026, 45)


def test_an_unfinished_period_is_refused_naming_the_last_finished_one():
    error = _parse("2026-W46")
    assert error.kind == "unfinished-period"
    assert error.last_finished == "2026-W45"
    assert error.example == "2026-W45"
    assert error.to_dict()["last_finished"] == "2026-W45"
    error = _parse("2026-11")
    assert error.kind == "unfinished-period"
    assert error.last_finished == "2026-10"


def test_a_future_period_is_refused_naming_the_last_finished_one():
    assert _parse("2027-W02").kind == "unfinished-period"
    assert _parse("2027-W02").last_finished == "2026-W45"
    assert _parse("2027-03").last_finished == "2026-10"
    at = _parse("@Calendar/302 Weekly/2026-W47.md")
    assert at.kind == "unfinished-period"
    assert at.last_finished == "2026-W45"


def test_the_week_that_ends_today_is_not_finished():
    error = _parse("2026-W46", today=date(2026, 11, 15))
    assert error.kind == "unfinished-period"
    assert _parse("2026-W46", today=date(2026, 11, 16)).period == Period.week(2026, 46)


def test_anything_else_is_an_unknown_argument():
    for raw in ("foo", "2026", "setup now", "--month", "2026-03-26", "@"):
        error = _parse(raw)
        assert isinstance(error, RequestError), raw
        assert error.kind == "unknown-argument", raw
        assert error.expected and error.example
        assert "@" in error.expected


def test_arguments_are_trimmed():
    assert _parse("  2026-W13  ").period == Period.week(2026, 13)
    assert _parse("  month ").period == Period.month(2026, 10)

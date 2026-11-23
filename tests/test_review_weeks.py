#!/usr/bin/env python3
# version: 0.1.0
"""test_review_weeks.py — the units of a period for condensing (spec 047 T2.2; PRD F1-AC1, F1-AC2; ADR-2).

Mechanisms a mutation of ``lib/review_weeks.py`` falsifies:
- clipping a month or quarter's weeks to the period (F1-AC2) — dropping the
  ``period.start <= d <= period.end`` filter fails the clipped-edge tests;
- a week review is never clipped and is one unit;
- the configured week rule, never hard-coded ISO — a Sunday/1 rule gives other
  unit names and other edges than ISO;
- greedy date-order packing under ``UNIT_BUDGET`` with suffixes ``a``, ``b``… —
  reordering, dropping or duplicating a day fails the exactly-once checks;
- a day's weight includes its growth files (the caller sums them; the packer
  must use the summed number, not a day-file-only number);
- a single day over the budget stays one unit alone and is named by
  ``over_budget``;
- ``takes_part``: content, tasks, linked notes or ≥ 1 created note;
- ``digest_cap`` = ``min(DIGEST_MAX, DIGEST_TOTAL // units)``.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.period import ISO, Period, WeekRule  # noqa: E402
from lib.review_weeks import (  # noqa: E402
    DIGEST_MAX,
    DIGEST_TOTAL,
    FILE_CEILING,
    UNIT_BUDGET,
    digest_cap,
    over_budget,
    takes_part,
    units,
)

SUNDAY_ONE = WeekRule(first_day=6, min_days_in_first_week=1)


def _even(period, weight=1000):
    return {d: weight for d in period.days()}


def _all_days(period):
    return set(period.days())


def _unit_days(result):
    return [d for u in result for d in u["days"]]


def _iso(d):
    return d.isoformat()


# --- constants -----------------------------------------------------------------


def test_constants_follow_adr_2():
    assert FILE_CEILING == 32_768
    assert UNIT_BUDGET == 81_920
    assert DIGEST_TOTAL == 114_688
    assert DIGEST_MAX == 8_192


# --- clipping (F1-AC2) -----------------------------------------------------------


def test_week_review_is_one_unit_not_clipped():
    week = Period.week(2026, 14, ISO)
    result = units(week, ISO, _even(week), set())
    assert [u["unit"] for u in result] == ["2026-W14"]
    assert result[0]["week"] == "2026-W14"
    assert result[0]["days"] == [_iso(d) for d in week.days()]
    assert result[0]["days"][0] == "2026-03-30" and result[0]["days"][-1] == "2026-04-05"


def test_month_under_iso_clips_its_edge_weeks():
    month = Period.month(2026, 3)
    result = units(month, ISO, _even(month), set())
    assert [u["unit"] for u in result] == [f"2026-W{n:02d}" for n in range(9, 15)]
    assert result[0]["days"] == ["2026-03-01"]
    assert result[-1]["days"] == ["2026-03-30", "2026-03-31"]
    assert _unit_days(result) == [_iso(d) for d in month.days()]


def test_quarter_under_iso_gives_fourteen_clipped_units():
    quarter = Period.quarter(2026, 1)
    result = units(quarter, ISO, _even(quarter), set())
    assert len(result) == 14
    assert result[0]["unit"] == "2026-W01"
    assert result[0]["days"] == ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    assert result[-1]["unit"] == "2026-W14"
    assert result[-1]["days"] == ["2026-03-30", "2026-03-31"]
    assert _unit_days(result) == [_iso(d) for d in quarter.days()]


def test_non_iso_week_rule_clips_under_that_rule():
    month = Period.month(2026, 3)
    result = units(month, SUNDAY_ONE, _even(month), set())
    assert [u["unit"] for u in result] == [f"2026-W{n:02d}" for n in range(10, 15)]
    assert result[0]["days"] == [f"2026-03-{d:02d}" for d in range(1, 8)]
    assert result[-1]["days"] == ["2026-03-29", "2026-03-30", "2026-03-31"]
    january = Period.month(2026, 1)
    first = units(january, SUNDAY_ONE, _even(january), set())[0]
    assert first["unit"] == "2026-W01"
    assert first["days"] == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_non_iso_week_review_uses_that_rule():
    week = Period.week(2026, 14, SUNDAY_ONE)
    result = units(week, SUNDAY_ONE, _even(week), set())
    assert len(result) == 1
    assert result[0]["days"][0] == "2026-03-29" and result[0]["days"][-1] == "2026-04-04"


# --- packing under the budget (F1-AC1) -------------------------------------------


def test_week_over_budget_splits_in_date_order_with_every_day_once():
    week = Period.week(2026, 13, ISO)
    weights = {d: 20_000 for d in week.days()}                   # 140,000 > 81,920
    result = units(week, ISO, weights, set())
    assert [u["unit"] for u in result] == ["2026-W13a", "2026-W13b"]
    assert all(u["week"] == "2026-W13" for u in result)
    assert result[0]["days"] == [_iso(d) for d in week.days()[:4]]   # 80,000 ≤ budget
    assert result[1]["days"] == [_iso(d) for d in week.days()[4:]]
    assert _unit_days(result) == [_iso(d) for d in week.days()]
    assert all(u["bytes"] <= UNIT_BUDGET for u in result)
    assert [u["bytes"] for u in result] == [80_000, 60_000]


def test_every_day_of_a_split_quarter_is_in_exactly_one_unit():
    quarter = Period.quarter(2026, 1)
    weights = {d: 15_000 + 1_000 * (i % 9) for i, d in enumerate(quarter.days())}
    result = units(quarter, ISO, weights, set())
    seen = _unit_days(result)
    assert sorted(seen) == seen
    assert len(seen) == len(set(seen)) == len(_all_days(quarter))
    assert set(seen) == {_iso(d) for d in quarter.days()}
    assert all(u["bytes"] <= UNIT_BUDGET for u in result)
    assert any(u["unit"].endswith("b") for u in result)


def test_growth_bytes_in_the_day_weight_split_the_week():
    week = Period.week(2026, 13, ISO)
    day_files = {d: 10_000 for d in week.days()}                   # 70,000 on day files alone
    assert len(units(week, ISO, day_files, set())) == 1
    with_growth = dict(day_files)
    with_growth[week.days()[5]] += 35_000                          # growth files on day 6: 50k + 45k > budget
    result = units(week, ISO, with_growth, set())
    assert [u["unit"] for u in result] == ["2026-W13a", "2026-W13b"]
    assert result[0]["days"] == [_iso(d) for d in week.days()[:5]]
    assert result[1]["days"] == [_iso(d) for d in week.days()[5:]]
    assert sum(u["bytes"] for u in result) == 105_000


def test_a_single_day_over_the_budget_is_a_unit_alone_and_named():
    week = Period.week(2026, 13, ISO)
    weights = {d: 5_000 for d in week.days()}
    heavy = week.days()[2]
    weights[heavy] = UNIT_BUDGET + 1
    result = units(week, ISO, weights, set())
    alone = [u for u in result if _iso(heavy) in u["days"]]
    assert len(alone) == 1 and alone[0]["days"] == [_iso(heavy)]
    assert _unit_days(result) == [_iso(d) for d in week.days()]
    assert over_budget(result) == [alone[0]["unit"]]


def test_over_budget_is_empty_when_every_unit_fits():
    quarter = Period.quarter(2026, 1)
    assert over_budget(units(quarter, ISO, _even(quarter), set())) == []


def test_a_day_missing_from_day_bytes_is_kept_and_weighs_nothing():
    week = Period.week(2026, 13, ISO)
    weights = _even(week)
    del weights[week.days()[3]]
    result = units(week, ISO, weights, set())
    assert result[0]["days"] == [_iso(d) for d in week.days()]
    assert result[0]["bytes"] == 6_000


# --- taking part ----------------------------------------------------------------


def test_unit_with_no_taking_part_day_does_not_take_part():
    month = Period.month(2026, 3)
    part = {date(2026, 3, 10)}
    result = units(month, ISO, _even(month), part)
    flags = {u["unit"]: u["takes_part"] for u in result}
    assert flags["2026-W11"] is True
    assert [name for name, flag in flags.items() if flag] == ["2026-W11"]


def test_takes_part_after_a_split_is_per_unit():
    week = Period.week(2026, 13, ISO)
    weights = {d: 20_000 for d in week.days()}
    result = units(week, ISO, weights, {week.days()[6]})
    assert [u["takes_part"] for u in result] == [False, True]


EMPTY_DAY = {"has_content": False, "tasks": [], "linked": []}


@pytest.mark.parametrize("day, created, expected", [
    (EMPTY_DAY, 0, False),
    (dict(EMPTY_DAY, has_content=True), 0, True),
    (dict(EMPTY_DAY, tasks=[{"text": "x"}]), 0, True),
    (dict(EMPTY_DAY, linked=[{"path": "DP"}]), 0, True),
    (EMPTY_DAY, 1, True),
    ({}, 0, False),
])
def test_takes_part_per_day(day, created, expected):
    assert takes_part(day, created) is expected


def test_a_day_with_only_created_notes_takes_part():
    assert takes_part(EMPTY_DAY, created=3) is True
    week = Period.week(2026, 13, ISO)
    day = week.days()[1]
    part = {d for d in week.days() if takes_part(EMPTY_DAY, 2 if d == day else 0)}
    assert units(week, ISO, _even(week), part)[0]["takes_part"] is True


# --- the digest cap -------------------------------------------------------------


def test_digest_cap_values():
    assert digest_cap(14) == 8_192
    assert digest_cap(16) == 7_168
    assert digest_cap(1) == DIGEST_MAX
    assert digest_cap(0) == DIGEST_MAX


def test_digest_cap_bounds_the_total():
    for n in range(1, 17):
        assert n * digest_cap(n) <= DIGEST_TOTAL
        assert digest_cap(n) <= DIGEST_MAX


def test_units_of_a_quarter_have_the_weeks_json_fields():
    quarter = Period.quarter(2026, 1)
    result = units(quarter, ISO, _even(quarter), set())
    assert all(set(u) == {"unit", "week", "days", "bytes", "takes_part"} for u in result)
    assert result[0]["bytes"] == 4_000
    assert date.fromisoformat(result[-1]["days"][-1]) == quarter.end
    assert date.fromisoformat(result[0]["days"][0]) == quarter.end - timedelta(days=89)

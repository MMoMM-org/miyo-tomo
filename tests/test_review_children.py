#!/usr/bin/env python3
# version: 0.1.0
"""test_review_children.py — the child-review level of a period read: a
quarter reads its dailies, the weekly notes of its weeks as sources and its
monthly notes with marks; a month keeps marking at the weekly level (spec
046 T3.2; ADR-6; PRD F6-AC4, F6-AC5).

WHAT THIS GUARDS: `CHILD` in lib/review_period.py (the quarter marks against
its monthly notes, not its weekly ones — RED when `CHILD[QUARTER]` is
`WEEK`), `_is_periodic` over the daily, weekly, monthly and quarterly
formats (`[[2026-02]]`, `[[2026-Q1]]` are never content), boundary weeks
clipped to the quarter's days with their week-level text tagged
`overlap_days` (the accepted deviation), the `monthly_status` /
`monthly_notes` report including absent months and `kado-empty`, and the end
pass recovering a monthly listing. The month and week read are pinned by
tests/test_review_period_golden.py.

The fixtures are tests/review_period_fixtures.py's `quarter_vault()`:
synthetic notes, fakes only, no live vault, no live Kado.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib.kado_client import _MAX_RETRIES  # noqa: E402
from lib.period import MONTH, WEEK, Period  # noqa: E402
from lib.review_children import (  # noqa: E402
    FOUND,
    KADO_EMPTY,
    NONE_FOUND,
    NOT_CONFIGURED,
    NOT_READ,
    ChildNotes,
    status,
)
from lib.review_period import ADVICE_CHECK_ACCESS, sources_from_config  # noqa: E402
from lib.review_weekly import weekly_content  # noqa: E402
from review_period_fixtures import (  # noqa: E402
    DAILY,
    FEB_NOTE,
    MONTHLY,
    Q1,
    WEEKLY,
    entry,
    quarter_sources,
    quarter_vault,
    reads_of,
    run,
)

FEB = Period.month(2026, 2)


def _flat(value) -> list:
    return list(value or [])


def _weekly(result, week: str) -> dict:
    return next(w for w in result["weekly"] if w["week"] == week)


# ── the marks: monthly level for a quarter, weekly level for a month ──

def test_quarter_marks_at_monthly_level():
    result = run(quarter_vault(), Q1, quarter_sources())
    assert result["only_in_monthly_links"] == ["Only-Monthly"]
    assert result["dailies_not_in_monthly"] == ["Only-Daily"]
    marked = result["only_in_monthly_links"] + _flat(result["dailies_not_in_monthly"])
    assert "Only-Weekly" not in marked
    assert "2026-02" not in marked and "2026-Q1" not in marked and "2026-W07" not in marked


def test_the_quarter_writes_no_weekly_marks():
    result = run(quarter_vault(), Q1, quarter_sources())
    assert "only_in_weekly_links" not in result and "dailies_not_in_weekly" not in result
    assert [w["week"] for w in result["weekly"]] == ["2026-W01", "2026-W07", "2026-W14"]


def test_the_same_notes_read_as_a_month_mark_at_weekly_level():
    vault = quarter_vault()
    result = run(vault, FEB, quarter_sources())
    assert result["only_in_weekly_links"] == ["Only-Weekly"]
    assert result["dailies_not_in_weekly"] == ["Only-Daily"]
    assert "monthly" not in result and "only_in_monthly_links" not in result
    assert "monthly_status" not in result["report"] and "monthly_notes" not in result["report"]
    assert not any(p.startswith(MONTHLY) for p in vault.paths_seen)


def test_a_month_note_never_read_puts_its_days_in_no_mark():
    # January and March have no monthly note: their dailies' links are not "left out" of one
    result = run(quarter_vault(), Q1, quarter_sources())
    assert "Jan Shared" not in result["dailies_not_in_monthly"]
    assert "Q End" not in result["dailies_not_in_monthly"]


def test_a_link_to_a_monthly_or_quarterly_note_is_navigation_only_with_its_format_configured():
    result = run(quarter_vault(), Q1, quarter_sources(quarterly_format=None))
    assert "2026-Q1" in result["only_in_monthly_links"]
    result = run(quarter_vault(), FEB, quarter_sources(monthly_format=None))
    assert "2026-02" in result["dailies_not_in_weekly"]


# ── reading the quarter ──

def test_a_quarter_reads_every_daily_and_the_day_after():
    vault = quarter_vault()
    result = run(vault, Q1, quarter_sources())
    assert len(result["days"]) == 90
    assert entry(result, "2026-02-10")["has_content"] is True
    assert entry(result, "2026-03-31")["fields"] == {"Mood": "2"}
    assert reads_of(vault, f"{DAILY}2026-04-01.md") == [f"{DAILY}2026-04-01.md"]


def test_boundary_weeks_are_clipped_to_the_quarter_and_their_week_text_tagged():
    result = run(quarter_vault(), Q1, quarter_sources())
    w01, w14 = _weekly(result, "2026-W01"), _weekly(result, "2026-W14")
    assert w01["overlap_days"] == 4 and w14["overlap_days"] == 2
    assert w01["day_blocks"] == {"2026-01-02": "- new year [[New Year]]"}
    assert w01["week_text"] == {"In my own words": "Own [[Week Own]]"}
    assert w14["day_blocks"] == {"2026-03-31": "- last [[Q End]]"}
    assert "Old Year" not in w01["links"] and "April Only" not in w14["links"]
    assert _weekly(result, "2026-W07")["overlap_days"] == 7


def test_monthly_notes_are_split_into_month_text_and_tagged():
    result = run(quarter_vault(), Q1, quarter_sources())
    assert result["monthly"] == [{
        "path": f"{MONTHLY}2026-02.md", "month": "2026-02", "overlap_days": 28, "duplicate": False,
        "day_blocks": {},
        "month_text": {"Highlights": "- [[Shared]] [[Only-Monthly]] [[2026-W07]] [[2026-02-10]] [[2026-Q1]]"},
        "links": ["Shared", "Only-Monthly", "2026-W07", "2026-02-10", "2026-Q1"],
    }]


def test_the_report_names_absent_months_and_weeks():
    result = run(quarter_vault(), Q1, quarter_sources())
    report = result["report"]
    assert report["monthly_status"] == FOUND
    assert report["monthly_notes"] == [
        {"month": "2026-01", "path": None, "state": "absent"},
        {"month": "2026-02", "path": f"{MONTHLY}2026-02.md", "state": "read"},
        {"month": "2026-03", "path": None, "state": "absent"},
    ]
    assert report["weekly_status"] == FOUND
    weeks = {row["week"]: row["state"] for row in report["weekly_notes"]}
    assert len(weeks) == 14
    assert [w for w, s in weeks.items() if s == "read"] == ["2026-W01", "2026-W07", "2026-W14"]


def test_a_quarter_without_monthly_or_weekly_notes_is_built_from_the_dailies():
    vault = quarter_vault()
    for path in [p for p in vault.files if p.startswith((WEEKLY, MONTHLY))]:
        del vault.files[path]
    vault.files[f"{WEEKLY}2025-W50.md"] = "# old"
    vault.files[f"{MONTHLY}2025-11.md"] = "# old"
    result = run(vault, Q1, quarter_sources())
    assert result["report"]["monthly_status"] == NONE_FOUND
    assert result["report"]["weekly_status"] == NONE_FOUND
    assert result["monthly"] == [] and result["weekly"] == []
    assert all(row["state"] == "absent" for row in result["report"]["monthly_notes"])
    assert "only_in_monthly_links" not in result and "dailies_not_in_monthly" not in result
    assert entry(result, "2026-02-10")["has_content"] is True


def test_an_empty_monthly_listing_is_kado_empty_with_the_access_hint():
    vault = quarter_vault()
    del vault.files[f"{MONTHLY}2026-02.md"]
    result = run(vault, Q1, quarter_sources())
    assert result["report"]["monthly_status"] == KADO_EMPTY
    assert result["report"]["kado_empty"] == ["monthly"]
    assert result["report"]["advice"] == [ADVICE_CHECK_ACCESS]
    assert result["report"]["monthly_notes"] == []


def test_a_quarter_without_monthly_config_says_not_configured_and_lists_nothing():
    vault = quarter_vault()
    for sources in (quarter_sources(monthly_folder=None), quarter_sources(monthly_format=None)):
        result = run(vault, Q1, sources)
        assert result["report"]["monthly_status"] == NOT_CONFIGURED
        assert result["monthly"] == [] and result["report"]["monthly_notes"] == []
        assert "only_in_monthly_links" not in result
    assert not any(p.startswith(MONTHLY) for p in vault.paths_seen)


# ── the end pass ──

def test_a_rate_limited_monthly_listing_recovered_by_the_end_pass_reads_the_monthly_notes():
    free = run(quarter_vault(), Q1, quarter_sources())
    vault = quarter_vault()
    vault.rate_limit(MONTHLY, failures=_MAX_RETRIES + 1)
    result = run(vault, Q1, quarter_sources())
    assert result == free
    assert result["report"]["monthly_status"] == FOUND
    assert reads_of(vault, f"{MONTHLY}2026-02.md") == [f"{MONTHLY}2026-02.md"]
    assert [p for m, p in vault.events if m == "list_dir" and p == MONTHLY] == [MONTHLY, MONTHLY]


def test_a_monthly_listing_that_still_fails_is_not_read_without_an_access_hint():
    vault = quarter_vault()
    vault.rate_limit(MONTHLY)
    result = run(vault, Q1, quarter_sources())
    assert result["report"]["monthly_status"] == NOT_READ
    assert result["not_read"] == [MONTHLY]
    assert result["report"]["kado_empty"] == [] and result["report"]["advice"] == []
    assert result["monthly"] == [] and result["report"]["monthly_notes"] == []
    assert result["report"]["weekly_status"] == FOUND


# ── privacy ──

def test_the_quarter_report_holds_no_note_text():
    report = json.dumps(run(quarter_vault(), Q1, quarter_sources())["report"])
    for text in ("Only-Monthly", "Shared", "Highlights", "tuesday", "Own"):
        assert text not in report


# ── the module's own parts ──

@pytest.mark.parametrize("configured, entries, listing, kado_empty, expected", [
    (False, [], None, [], NOT_CONFIGURED),
    (True, [{"path": "x"}], ["x"], [], FOUND),
    (True, [], ["y"], [], NONE_FOUND),
    (True, [], None, ["monthly"], KADO_EMPTY),
    (True, [], None, [], NOT_READ),
])
def test_status_of_a_child_level(configured, entries, listing, kado_empty, expected):
    child = ChildNotes(MONTH, MONTHLY if configured else None, "YYYY-MM")
    assert status(child, entries, listing, kado_empty) == expected


def test_child_labels_follow_the_granularity_names():
    assert ChildNotes(WEEK, WEEKLY, "GGGG-[W]WW").label == "weekly"
    assert ChildNotes(MONTH, MONTHLY, "YYYY-MM").label == "monthly"


def test_weekly_content_names_its_own_text_key():
    content = weekly_content(FEB_NOTE, Q1, daily_format="YYYY-MM-DD", own_sections=["Highlights"],
                             text_key="month_text")
    assert "week_text" not in content
    assert list(content["month_text"]) == ["Highlights"]
    assert "Plan Link" not in content["links"]


def test_sources_from_config_takes_the_monthly_and_quarterly_setup():
    config = {
        "concepts": {"calendar": {"granularities": {"daily": {"path": DAILY}, "monthly": {"path": MONTHLY}}}},
        "naming": {"calendar_patterns": {"monthly": "YYYY-MM", "quarterly": "YYYY-[Q]Q"}},
        "review": {"monthly": {"own_sections": ["Highlights", 3]}},
    }
    sources = sources_from_config(config, {})
    assert (sources.monthly_folder, sources.monthly_format, sources.quarterly_format) == (
        MONTHLY, "YYYY-MM", "YYYY-[Q]Q")
    assert sources.monthly_own_sections == ("Highlights",)
    bare = sources_from_config({"concepts": {"calendar": {"granularities": {"daily": {"path": DAILY}}}}}, {})
    assert bare.monthly_folder is None and bare.monthly_format is None and bare.quarterly_format is None

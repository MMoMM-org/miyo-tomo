#!/usr/bin/env python3
# version: 0.2.0
"""test_review_period.py — reading a period for /review: dailies flat and in
year folders, the day after the period, duplicates, link stems resolved to
vault paths, task notes read once, the weekly notes of a month with their
day blocks and week text, the two link differences, vault growth, the end
pass, and the Kado-empty reporting (spec 045 T3.3; PRD F3-AC5, F3-AC6,
F3-AC7, F3-AC9; SDD Complex Logic "month reading").

The day readers are stubs that follow the wave-B seam: a daily's `Name:: v`
lines are today's fields, `Y-Name:: v` lines are yesterday fields,
`linked:: <stem>` lines name a same-day note the day reads through
`read_note(stem)`. One test wires the real `lib.review_day` functions
through the period reader instead. Fixtures are synthetic; they share only
the structure of the owner's notes.
"""
from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault  # noqa: E402
from lib.kado_client import _MAX_RETRIES, KadoConnectionError  # noqa: E402
from lib.period import ISO, Period  # noqa: E402
from lib.review_pacer import ReviewPacer  # noqa: E402
from lib.review_period import (  # noqa: E402
    ADVICE_CHECK_ACCESS,
    DayReaders,
    PeriodSources,
    period_bounds_ms,
    read_period,
    sources_from_config,
)
from lib.review_weekly import (  # noqa: E402
    DEFAULT_WEEKLY_SKIP,
    daily_date,
    daily_name,
    weekly_content,
)

DAILY = "Calendar/301 Daily/"
WEEKLY = "Calendar/302 Weekly/"
PLANNER = "Efforts/300 Planner/"
MOCS = "100 MOCs/"
TASK_NOTE = "Efforts/500 OnGoing/Next Todos.md"
W13 = Period.week(2026, 13)              # 2026-03-23 .. 2026-03-29
MARCH = Period.month(2026, 3)
SETTINGS = {"sections": ["Daily Log"], "task_notes": [TASK_NOTE]}

_FIELD_RE = re.compile(r"^(Y-)?([A-Za-z]+):: (.+)$", re.M)
_LINK_RE = re.compile(r"\[\[([^\]|#]+)")
_LINKED_RE = re.compile(r"^linked:: (.+)$", re.M)
_TASK_RE = re.compile(r"^- \[([ x])\] (.+?)(?: ✅ (\d{4}-\d{2}-\d{2}))?$", re.M)


# ── the seam stubs ──

def stub_read_day(day, dailies, settings, read_note):
    text = "\n".join(dailies[p] for p in sorted(dailies))
    fields = {name: value for y, name, value in _FIELD_RE.findall(text) if not y}
    previous = {name: value for y, name, value in _FIELD_RE.findall(text) if y}
    linked, problems = [], []
    for stem in _LINKED_RE.findall(text):
        content = read_note(stem)
        if content is None:
            problems.append({"kind": "linked-missing", "path": stem})
        else:
            linked.append({"path": stem, "kind": "other", "text": content})
    body = "\n".join(line for line in text.splitlines()
                     if line and "::" not in line and not line.startswith(("#", "---", "tags:"))).strip()
    return {
        "date": day.isoformat(), "dailies": sorted(dailies), "sections": {"Daily Log": body},
        "fields": fields, "partly_read": False, "has_content": bool(body),
        "links": _LINK_RE.findall(text) + [item["path"] for item in linked],
        "problems": problems, "tasks": [], "linked": linked, "previous_day_fields": previous,
    }


def stub_yesterday_fields(text, settings):
    return {name: value for y, name, value in _FIELD_RE.findall(text) if y}


def stub_attribute_yesterday(entries, after_period):
    by_date = {e["date"]: dict(e) for e in entries}
    for entry in by_date.values():
        previous = entry.pop("previous_day_fields", {})
        before = (date.fromisoformat(entry["date"]) - timedelta(days=1)).isoformat()
        if before in by_date:
            by_date[before]["fields"] = dict(by_date[before]["fields"], **previous)
    ordered = [by_date[k] for k in sorted(by_date)]
    if ordered and after_period:
        ordered[-1]["fields"] = dict(ordered[-1]["fields"], **after_period)
    for entry in ordered:
        entry.pop("previous_day_fields", None)
    return ordered


def stub_task_note_tasks(path, text):
    tasks = [{"text": t, "done": mark == "x", "done_date": done or None, "source": path}
             for mark, t, done in _TASK_RE.findall(text)]
    for task in tasks:
        if not task["done"]:
            task["label"] = "open today"
    return tasks


def stub_done_in_period(tasks, start, end):
    return [t for t in tasks if t["done"] and t["done_date"] and start <= date.fromisoformat(t["done_date"]) <= end]


READERS = DayReaders(stub_read_day, stub_yesterday_fields, stub_attribute_yesterday,
                     stub_task_note_tasks, stub_done_in_period)


# ── fixtures ──

def week_sources(**extra) -> PeriodSources:
    return PeriodSources(daily_folder=DAILY, **extra)


def month_sources(**extra) -> PeriodSources:
    kw = dict(daily_folder=DAILY, weekly_folder=WEEKLY, weekly_format="GGGG-[W]WW",
              own_sections=["In my own words", "Reflections"], moc_folders=[MOCS])
    kw.update(extra)
    return PeriodSources(**kw)


def daily(day: date, text: str, year_folder: bool = False) -> tuple[str, str]:
    folder = f"{DAILY}{day.year}/" if year_folder else DAILY
    return f"{folder}{day.isoformat()}.md", f"---\ntags: [daily]\n---\n# {day.isoformat()}\n{text}\n"


def planner(day: date, text: str = "- planned") -> tuple[str, str]:
    return f"{PLANNER}DP-{day.isoformat()}.md", f"# Plan\n{text}\n"


TASK_NOTE_TEXT = "- [x] done in week ✅ 2026-03-24\n- [x] done before ✅ 2026-03-01\n- [ ] still open\n"


def week_vault(**files) -> ReviewFakeVault:
    base = dict([
        daily(date(2026, 3, 23), "Monday log [[Alpha]]\nSleep:: 6\nY-Mood:: 3"),
        daily(date(2026, 3, 24), "Tuesday log [[Beta]]\nY-Mood:: 4", year_folder=True),
        daily(date(2026, 3, 25), "Wednesday log\nlinked:: DP-2026-03-25"),
        daily(date(2026, 3, 26), ""),
        daily(date(2026, 3, 27), "Friday log [[Gamma]]\nlinked:: DP-2026-03-25"),
        daily(date(2026, 3, 29), "Sunday log\nSleep:: 8"),
        daily(date(2026, 3, 30), "Monday after [[AfterLink]]\nY-Mood:: 5\nSleep:: 7"),
        planner(date(2026, 3, 25)),
    ])
    base[TASK_NOTE] = TASK_NOTE_TEXT
    base.update(files)
    return ReviewFakeVault(base, folders=[DAILY, WEEKLY, MOCS])


W09_NOTE = """---
journal-start-date: 2026-02-23
---
# Weekly Review: [[2026-W09]]
## Theme of the week
Theme [[Theme Note]]
## Review of the Week
### [[2026-02-28|2026-02-28 Sat]]
- february text [[Feb Note]]
### [[2026-03-01|2026-03-01 Sun]]
#### Notes of the Day %% fold %%
- march text [[March Note]]
#### My final thoughts for that day
- thoughts [[Thought Note]]
#### Review Check
- [x] Review daily logs ✅ 2026-03-02 [[Check Note]]
### Learnings of the Week
- learned [[Learn Note]]
### In my own words
Own words [[Own Note]] and [[Alpha]]
## Organisation
### [[2026-03-02|2026-03-02 Mon]]
- plan [[Plan Note]]
"""

W13_NOTE = """# Weekly Review: [[2026-W13]]
## Review of the Week
### [[2026-03-23|2026-03-23 Mon]]
- monday block [[Alpha]] [[Delta]]
### [[2026-03-29|2026-03-29 Sun]]
- sunday block
#### Review Check
- [x] Review daily logs ✅ 2026-03-30
### Reflections
Reflection [[Epsilon]] [[2026-03-25]] [[2026-W13]]
### In my own words

## Organisation
- next week [[Zeta]]
"""


def month_vault(**files) -> ReviewFakeVault:
    base = dict([
        daily(date(2026, 3, 1), "first [[March Note]] [[Only Daily]]"),
        daily(date(2026, 3, 23), "monday [[Alpha]] [[Omega]] [[DP-2026-03-23]]\nlinked:: DP-2026-03-23"),
        daily(date(2026, 3, 24), "tuesday [[Beta]]", year_folder=True),
        daily(date(2026, 3, 31), "last day\nY-Mood:: 1"),
        daily(date(2026, 4, 1), "april\nY-Mood:: 9"),
        planner(date(2026, 3, 23)),
    ])
    base[f"{WEEKLY}2026/2026-W09.md"] = W09_NOTE
    base[f"{WEEKLY}2026-W13.md"] = W13_NOTE
    base[TASK_NOTE] = TASK_NOTE_TEXT
    base.update(files)
    return ReviewFakeVault(base, folders=[DAILY, WEEKLY, MOCS])


def run(vault, period, sources, settings=SETTINGS, readers=READERS):
    with ReviewPacer(vault) as pacer:
        return read_period(period, sources, settings, vault, pacer, readers=readers)


def day_report(result, day: str) -> dict:
    return next(d for d in result["report"]["days"] if d["date"] == day)


def entry(result, day: str) -> dict:
    return next(e for e in result["days"] if e["date"] == day)


def reads_of(vault, path: str) -> list:
    return [p for method, p in vault.events if method == "read_note" and p == path]


# ── names and bounds ──

def test_daily_name_renders_and_parses_the_default_and_a_literal_format():
    assert daily_name(date(2026, 3, 5), "YYYY-MM-DD") == "2026-03-05"
    assert daily_date("2026-03-05", "YYYY-MM-DD") == date(2026, 3, 5)
    assert daily_name(date(2026, 3, 5), "[Day] DD.MM.YYYY") == "Day 05.03.2026"
    assert daily_date("Day 05.03.2026", "[Day] DD.MM.YYYY") == date(2026, 3, 5)
    assert daily_date("DP-2026-03-05", "YYYY-MM-DD") is None
    assert daily_date("2026-13-05", "YYYY-MM-DD") is None


def test_period_bounds_are_inclusive_local_days_in_ms():
    start_ms, end_ms = period_bounds_ms(W13)
    assert (end_ms - start_ms + 1) == 7 * 86_400_000
    assert end_ms % 1000 == 999
    next_start, _ = period_bounds_ms(Period.week(2026, 14))
    assert next_start == end_ms + 1


# ── dailies ──

def test_dailies_found_flat_and_in_year_folder():
    vault = week_vault()
    result = run(vault, W13, week_sources())
    assert [d["date"] for d in result["days"]] == [d.isoformat() for d in W13.days()]
    assert entry(result, "2026-03-23")["dailies"] == [f"{DAILY}2026-03-23.md"]
    assert entry(result, "2026-03-24")["dailies"] == [f"{DAILY}2026/2026-03-24.md"]
    assert f"{DAILY}2026/2026-03-24.md" in vault.paths_seen
    assert day_report(result, "2026-03-24")["dailies"] == [{"path": f"{DAILY}2026/2026-03-24.md", "state": "found"}]
    assert day_report(result, "2026-03-26")["dailies"] == [{"path": f"{DAILY}2026-03-26.md", "state": "empty"}]
    assert day_report(result, "2026-03-28") == {"date": "2026-03-28", "dailies": [], "duplicate": False, "linked": []}
    assert entry(result, "2026-03-28")["has_content"] is False
    assert "dailies" not in result["report"]["kado_empty"]


def test_day_after_period_is_read_for_its_yesterday_fields_only():
    vault = week_vault()
    result = run(vault, W13, week_sources())
    after = f"{DAILY}2026-03-30.md"
    assert after in vault.paths_seen
    assert entry(result, "2026-03-29")["fields"] == {"Sleep": "8", "Mood": "5"}
    assert entry(result, "2026-03-23")["fields"] == {"Sleep": "6", "Mood": "4"}
    assert all(e["date"] <= "2026-03-29" for e in result["days"])
    assert not any("AfterLink" in e["links"] for e in result["days"])
    assert not any("Monday after" in str(e["sections"]) for e in result["days"])
    assert result["report"]["day_after"] == {"date": "2026-03-30", "dailies": [{"path": after, "state": "read"}]}


def test_absent_day_after_leaves_the_last_days_value_missing():
    vault = week_vault()
    del vault.files[f"{DAILY}2026-03-30.md"]
    result = run(vault, W13, week_sources())
    assert entry(result, "2026-03-29")["fields"] == {"Sleep": "8"}
    assert result["report"]["day_after"] == {"date": "2026-03-30", "dailies": []}


def test_two_dailies_for_one_date_are_both_read_and_reported_duplicate():
    flat, _ = daily(date(2026, 3, 23), "")
    nested, text = daily(date(2026, 3, 23), "Copy in the year folder [[Copy]]", year_folder=True)
    vault = week_vault(**{nested: text})
    result = run(vault, W13, week_sources())
    assert entry(result, "2026-03-23")["dailies"] == [flat, nested]
    assert flat in vault.paths_seen and nested in vault.paths_seen
    assert "Copy" in entry(result, "2026-03-23")["links"]
    report = day_report(result, "2026-03-23")
    assert report["duplicate"] is True
    assert [d["path"] for d in report["dailies"]] == [flat, nested]
    assert day_report(result, "2026-03-24")["duplicate"] is False


def test_empty_daily_listing_is_kado_empty_with_the_access_hint():
    vault = ReviewFakeVault({"Other/x.md": "x"}, folders=[])
    result = run(vault, W13, week_sources(), settings={"sections": ["Daily Log"]})
    assert result["report"]["kado_empty"] == ["dailies"]
    assert result["report"]["advice"] == [ADVICE_CHECK_ACCESS]
    assert all(e["dailies"] == [] for e in result["days"])
    assert len(result["days"]) == 7


# ── linked notes: stems resolved to paths ──

def test_a_link_stem_is_resolved_by_name_once_and_read_at_its_vault_path():
    vault = week_vault()
    result = run(vault, W13, week_sources())
    path = f"{PLANNER}DP-2026-03-25.md"
    lookups = [p for method, p in vault.events if method == "search_by_name"]
    assert lookups == ["DP-2026-03-25"]
    assert reads_of(vault, path) == [path]
    linked = {"name": "DP-2026-03-25", "path": path, "state": "read"}
    assert day_report(result, "2026-03-25")["linked"] == [linked]
    assert day_report(result, "2026-03-27")["linked"] == [linked]
    assert entry(result, "2026-03-25")["linked"][0]["vault_path"] == path


def test_a_stem_that_resolves_to_nothing_is_reported_missing_not_failed():
    path, text = daily(date(2026, 3, 25), "Wednesday\nlinked:: Gone-2026-03-25")
    vault = week_vault(**{path: text})
    result = run(vault, W13, week_sources())
    assert day_report(result, "2026-03-25")["linked"] == [{"name": "Gone-2026-03-25", "path": None, "state": "missing"}]
    assert result["not_read"] == []


def test_a_stem_resolves_only_to_an_exact_md_stem():
    vault = week_vault(**{"Other/DP-2026-03-25 Copy.md": "near miss", "Other/DP-2026-03-25.png": "x"})
    del vault.files[f"{PLANNER}DP-2026-03-25.md"]
    result = run(vault, W13, week_sources())
    assert day_report(result, "2026-03-25")["linked"][0]["state"] == "missing"


# ── task notes ──

def test_a_task_note_is_read_once_and_its_tasks_land_by_done_date():
    vault = week_vault()
    result = run(vault, W13, week_sources())
    assert reads_of(vault, TASK_NOTE) == [TASK_NOTE]
    assert entry(result, "2026-03-24")["tasks"] == [
        {"text": "done in week", "done": True, "done_date": "2026-03-24", "source": TASK_NOTE}]
    assert not any("done before" in str(e["tasks"]) for e in result["days"])
    assert result["open_tasks"] == [
        {"text": "still open", "done": False, "done_date": None, "source": TASK_NOTE, "label": "open today"}]
    assert result["report"]["task_notes"] == [{"path": TASK_NOTE, "state": "read"}]


def test_a_missing_task_note_is_reported_and_nothing_else_changes():
    vault = week_vault()
    del vault.files[TASK_NOTE]
    result = run(vault, W13, week_sources())
    assert result["report"]["task_notes"] == [{"path": TASK_NOTE, "state": "missing"}]
    assert result["open_tasks"] == []


# ── the end pass ──

def test_a_rate_limited_daily_is_recovered_by_the_end_pass():
    vault = week_vault()
    path = f"{DAILY}2026-03-23.md"
    vault.rate_limit(path, failures=_MAX_RETRIES + 1)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == []
    assert entry(result, "2026-03-23")["has_content"] is True
    assert "Alpha" in entry(result, "2026-03-23")["links"]
    assert day_report(result, "2026-03-23")["dailies"] == [{"path": path, "state": "found"}]


def test_a_daily_that_still_fails_at_the_end_is_not_read_and_marked_failed():
    vault = week_vault()
    path = f"{DAILY}2026-03-23.md"
    vault.rate_limit(path)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == [path]
    assert day_report(result, "2026-03-23")["dailies"] == [{"path": path, "state": "failed"}]
    assert entry(result, "2026-03-23")["has_content"] is False
    assert vault.min_interval == 0.0


def test_a_rate_limited_linked_note_is_recovered_without_a_second_daily_read():
    vault = week_vault()
    path = f"{PLANNER}DP-2026-03-25.md"
    vault.rate_limit(path, failures=_MAX_RETRIES + 1)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == []
    linked = {"name": "DP-2026-03-25", "path": path, "state": "read"}
    assert day_report(result, "2026-03-25")["linked"] == [linked]
    assert day_report(result, "2026-03-27")["linked"] == [linked]
    assert reads_of(vault, f"{DAILY}2026-03-25.md") == [f"{DAILY}2026-03-25.md"]


def test_a_rate_limited_name_lookup_is_recovered_by_the_end_pass():
    vault = week_vault()
    vault.rate_limit("DP-2026-03-25", failures=_MAX_RETRIES + 1)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == []
    assert day_report(result, "2026-03-25")["linked"][0]["state"] == "read"


def test_a_linked_note_that_still_fails_is_marked_failed():
    vault = week_vault()
    path = f"{PLANNER}DP-2026-03-25.md"
    vault.rate_limit(path)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == [path]
    assert day_report(result, "2026-03-25")["linked"] == [{"name": "DP-2026-03-25", "path": path, "state": "failed"}]


def test_a_connection_error_propagates():
    vault = week_vault()
    vault.connection_error = KadoConnectionError("down")
    with pytest.raises(KadoConnectionError):
        run(vault, W13, week_sources())


# ── weekly notes of a month ──

def test_month_resolves_weekly_notes_flat_and_in_the_week_year_folder():
    vault = month_vault()
    result = run(vault, MARCH, month_sources())
    paths = [w["path"] for w in result["weekly"]]
    assert paths == [f"{WEEKLY}2026/2026-W09.md", f"{WEEKLY}2026-W13.md"]
    assert [w["week"] for w in result["weekly"]] == ["2026-W09", "2026-W13"]
    assert result["report"]["weekly_status"] == "found"
    states = {w["week"]: w["state"] for w in result["report"]["weekly_notes"]}
    assert states == {"2026-W09": "read", "2026-W10": "absent", "2026-W11": "absent",
                      "2026-W12": "absent", "2026-W13": "read", "2026-W14": "absent"}
    assert f"{WEEKLY}2026/2026-W09.md" in vault.paths_seen


def test_week_notes_are_not_read_for_a_week_review():
    vault = month_vault()
    result = run(vault, W13, month_sources())
    assert "weekly" not in result
    assert "only_in_weekly_links" not in result
    assert not any(p.startswith(WEEKLY) for p in vault.paths_seen)


def test_day_blocks_keyed_by_date_end_at_their_level_and_drop_out_of_month_and_skipped_text():
    content = weekly_content(W09_NOTE, MARCH, daily_format="YYYY-MM-DD",
                             own_sections=["In my own words", "Reflections"])
    assert list(content["day_blocks"]) == ["2026-03-01"]
    block = content["day_blocks"]["2026-03-01"]
    assert "march text" in block and "thoughts" in block
    assert "Review Check" not in block and "Check Note" not in block
    assert "february" not in block and "learned" not in block
    assert "Plan Note" not in str(content)
    assert "2026-03-02" not in content["day_blocks"]
    assert content["week_text"] == {"In my own words": "Own words [[Own Note]] and [[Alpha]]"}
    assert content["links"] == ["March Note", "Thought Note", "Own Note", "Alpha"]
    assert DEFAULT_WEEKLY_SKIP == ("Review Check", "Organisation")


def test_week_level_text_is_tagged_with_week_and_overlap():
    result = run(month_vault(), MARCH, month_sources())
    w09, w13 = result["weekly"]
    assert (w09["week"], w09["overlap_days"]) == ("2026-W09", 1)
    assert (w13["week"], w13["overlap_days"]) == ("2026-W13", 7)
    assert w13["week_text"] == {"Reflections": "Reflection [[Epsilon]] [[2026-03-25]] [[2026-W13]]",
                                "In my own words": ""}
    assert w13["day_blocks"] == {"2026-03-23": "- monday block [[Alpha]] [[Delta]]",
                                 "2026-03-29": "- sunday block"}
    assert w09["duplicate"] is False


def test_only_in_weekly_links_and_dailies_not_in_weekly_are_computed():
    result = run(month_vault(), MARCH, month_sources())
    assert result["only_in_weekly_links"] == ["Thought Note", "Own Note", "Delta", "Epsilon"]
    assert result["dailies_not_in_weekly"] == ["Only Daily", "Omega", "Beta"]


def test_month_without_weekly_notes_says_none_found():
    vault = month_vault()
    del vault.files[f"{WEEKLY}2026/2026-W09.md"]
    del vault.files[f"{WEEKLY}2026-W13.md"]
    vault.files[f"{WEEKLY}2025-W50.md"] = "# old"
    result = run(vault, MARCH, month_sources())
    assert result["weekly"] == []
    assert result["report"]["weekly_status"] == "none-found"
    assert "weekly" not in result["report"]["kado_empty"]
    assert "only_in_weekly_links" not in result and "dailies_not_in_weekly" not in result


def test_month_without_weekly_config_says_not_configured_and_lists_nothing():
    vault = month_vault()
    for sources in (month_sources(weekly_folder=None), month_sources(weekly_format=None)):
        result = run(vault, MARCH, sources)
        assert result["report"]["weekly_status"] == "not-configured"
        assert result["weekly"] == []
        assert result["report"]["weekly_notes"] == []
        assert "only_in_weekly_links" not in result and "dailies_not_in_weekly" not in result
        assert "weekly" not in result["report"]["kado_empty"]
        assert result["report"]["advice"] == []
    assert not any(p.startswith(WEEKLY) for p in vault.paths_seen)
    assert len(result["days"]) == 31


def test_a_weekly_note_flat_and_in_the_year_folder_is_read_twice_and_marked_duplicate():
    nested = f"{WEEKLY}2026/2026-W13.md"
    vault = month_vault(**{nested: "# Weekly Review: [[2026-W13]]\n## Review of the Week\n"
                                   "### [[2026-03-24|2026-03-24 Tue]]\n- copy block [[Copy Link]]\n"})
    result = run(vault, MARCH, month_sources())
    w13 = [w for w in result["weekly"] if w["week"] == "2026-W13"]
    assert [w["path"] for w in w13] == [f"{WEEKLY}2026-W13.md", nested]
    assert all(w["duplicate"] is True for w in w13)
    assert w13[1]["day_blocks"] == {"2026-03-24": "- copy block [[Copy Link]]"}
    assert "Copy Link" in result["only_in_weekly_links"]
    assert "Beta" in result["dailies_not_in_weekly"]          # neither W13 copy mentions Tuesday's link
    w13_rows = [w for w in result["report"]["weekly_notes"] if w["week"] == "2026-W13"]
    assert w13_rows == [{"week": "2026-W13", "path": f"{WEEKLY}2026-W13.md", "state": "read"},
                        {"week": "2026-W13", "path": nested, "state": "read"}]
    assert next(w for w in result["weekly"] if w["week"] == "2026-W09")["duplicate"] is False


def test_empty_weekly_listing_is_kado_empty_not_none_found():
    vault = month_vault()
    del vault.files[f"{WEEKLY}2026/2026-W09.md"]
    del vault.files[f"{WEEKLY}2026-W13.md"]
    result = run(vault, MARCH, month_sources())
    assert result["report"]["weekly_status"] == "kado-empty"
    assert "weekly" in result["report"]["kado_empty"]
    assert ADVICE_CHECK_ACCESS in result["report"]["advice"]
    assert result["weekly"] == []


# ── growth ──

def _growth_vault(page_size=None) -> ReviewFakeVault:
    vault = week_vault(**{
        "Notes/New One.md": "new [[Topic MOC]] [[Alpha]]",
        "Notes/New Two.md": "new two [[Other MOC|alias]]",
        "Notes/Edge.md": "at the last millisecond",
        "Notes/Too Late.md": "one millisecond after",
        "Notes/Old.md": "old",
        f"{MOCS}Topic MOC.md": "moc",
        f"{MOCS}Other MOC.md": "moc",
        f"{MOCS}Quiet MOC.md": "moc",
    })
    start_ms, end_ms = period_bounds_ms(W13)
    vault.stamp("Notes/New One.md", created=start_ms, modified=start_ms)
    vault.stamp("Notes/New Two.md", created=start_ms + 5, modified=start_ms + 5)
    vault.stamp("Notes/Edge.md", created=end_ms, modified=end_ms)
    vault.stamp("Notes/Too Late.md", created=end_ms + 1, modified=end_ms + 1)
    vault.stamp("Notes/Old.md", created=start_ms - 1, modified=start_ms - 1)
    vault.stamp(f"{MOCS}Topic MOC.md", created=0, modified=start_ms - 1)
    vault.stamp(f"{MOCS}Other MOC.md", created=0, modified=start_ms + 100)
    vault.stamp(f"{MOCS}Quiet MOC.md", created=0, modified=end_ms)
    vault.page_size = page_size
    return vault


def test_growth_lists_created_notes_with_links_mocs_changed_and_mocs_linked_across_pages():
    vault = _growth_vault(page_size=2)
    result = run(vault, W13, week_sources(moc_folders=[MOCS]))
    growth = result["growth"]
    assert growth["created"] == [
        {"path": "Notes/Edge.md", "links": []},
        {"path": "Notes/New One.md", "links": ["Topic MOC", "Alpha"]},
        {"path": "Notes/New Two.md", "links": ["Other MOC"]},
    ]
    assert growth["mocs_changed"] == [f"{MOCS}Other MOC.md", f"{MOCS}Quiet MOC.md"]
    assert growth["mocs_linked_by_new"] == [f"{MOCS}Other MOC.md", f"{MOCS}Topic MOC.md"]
    start_ms, end_ms = period_bounds_ms(W13)
    created_filters = [f for f in vault.list_notes_filters if f and "createdAfter" in f]
    assert created_filters and all(f == {"createdAfter": start_ms, "createdBefore": end_ms} for f in created_filters)
    assert len(created_filters) >= 2          # the created query crossed pages with the filter repeated
    assert result["report"]["growth"] == {"created": 3, "mocs_changed": 2, "mocs_linked_by_new": 2,
                                          "moc_folders": 1, "kado_none": []}
    assert result["report"]["kado_empty"] == []
    assert result["report"]["advice"] == []


def test_moc_listing_costs_one_call_per_page_and_the_week_stays_within_budget():
    mocs = {f"{MOCS}MOC {n:02d}.md": "moc" for n in range(5)}
    vault = week_vault(**mocs)
    vault.page_size = 2
    result = run(vault, W13, week_sources(moc_folders=[MOCS]))
    moc_calls = [p for method, p in vault.events if method == "list_notes" and p == MOCS]
    assert len(moc_calls) == 3                      # 5 MOCs at 2 per page: ceil(5 / 2) pages, one call each
    assert result["report"]["growth"]["moc_folders"] == 1
    assert result["report"]["growth"]["kado_none"] == ["created"]
    assert vault.call_count <= 40, vault.events


def test_growth_without_moc_folders_queries_no_mocs():
    vault = _growth_vault()
    result = run(vault, W13, week_sources())
    assert result["growth"]["mocs_changed"] == [] and result["growth"]["mocs_linked_by_new"] == []
    assert result["report"]["growth"]["moc_folders"] == 0
    assert not any(method == "list_notes" and path == MOCS for method, path in vault.events)


def test_empty_growth_results_are_reported_as_kado_returned_none():
    vault = week_vault()
    result = run(vault, W13, week_sources(moc_folders=[MOCS]))
    assert result["growth"] == {"created": [], "mocs_changed": [], "mocs_linked_by_new": []}
    assert result["report"]["growth"]["kado_none"] == ["created", "mocs"]
    assert result["report"]["advice"] == []
    assert "created" not in result["report"]["kado_empty"] and "mocs" not in result["report"]["kado_empty"]
    assert result["report"]["kado_empty"] == []


# ── the real day reader through the period reader ──

REAL_DAILY_23 = """---
tags: [daily]
---
# 2026-03-23
## [[DP-2026-03-23|Dayplanner]]
```quoth
path: [[DP-2026-03-23#Plan]]
display: inline
```
## Daily Log
- wrote about [[Alpha]]
Sleep:: 6
Mood:: 3
## On This Day... last year - Monday
![[2025-03-23#Daily Log]]
"""


def test_real_review_day_reads_a_week_through_the_period_reader():
    from lib.review_day import DEFAULT_DATE_FORMAT

    settings = {"sections": ["Daily Log"], "skip_sections": ["On This Day... last year"],
                "task_notes": [TASK_NOTE], "max_chars_per_day": 12000,
                "date_format": DEFAULT_DATE_FORMAT, "yesterday_fields": ["Mood"]}
    planner_path = f"{PLANNER}DP-2026-03-23.md"
    vault = ReviewFakeVault({
        f"{DAILY}2026-03-23.md": REAL_DAILY_23,
        f"{DAILY}2026/2026-03-24.md": "# 2026-03-24\n## Daily Log\n- tuesday\nMood:: 4\n",
        f"{DAILY}2026-03-30.md": "# 2026-03-30\n## Daily Log\n- after text [[AfterLink]]\nMood:: 5\n",
        planner_path: "# Plan\n- [x] plan task ✅ 2026-03-23\n- planner text\n",
        "Calendar/301 Daily/2025/2025-03-23.md": "# 2025-03-23\n## Daily Log\n- last year [[LastYear]]\n",
        TASK_NOTE: TASK_NOTE_TEXT,
    }, folders=[DAILY])
    result = run(vault, W13, week_sources(), settings=settings, readers=None)

    day = entry(result, "2026-03-23")
    assert day["fields"] == {"Sleep": "6", "Mood": "4"}
    assert day["links"] == ["Alpha", "DP-2026-03-23"]
    assert day["linked"][0]["path"] == "DP-2026-03-23"
    assert day["linked"][0]["vault_path"] == planner_path
    assert day["linked"][0]["kind"] == "planner"
    assert {"text": "plan task", "done": True, "done_date": "2026-03-23", "source": "DP-2026-03-23"} in day["tasks"]
    assert entry(result, "2026-03-24")["tasks"] == [
        {"text": "done in week", "done": True, "done_date": "2026-03-24", "source": TASK_NOTE}]
    assert entry(result, "2026-03-29")["fields"] == {"Mood": "5"}
    assert not any("LastYear" in e["links"] or "AfterLink" in e["links"] for e in result["days"])
    assert result["open_tasks"][0]["label"] == "open today"
    assert [p for m, p in vault.events if m == "search_by_name"] == ["DP-2026-03-23"]
    assert reads_of(vault, planner_path) == [planner_path]
    assert reads_of(vault, TASK_NOTE) == [TASK_NOTE]
    assert day_report(result, "2026-03-23")["linked"] == [{"name": "DP-2026-03-23", "path": planner_path, "state": "read"}]
    assert "Calendar/301 Daily/2025/2025-03-23.md" not in vault.paths_seen


# ── call counts and config ──

def test_call_counts_for_a_fake_week_and_a_fake_month():
    week = week_vault()
    run(week, W13, week_sources(moc_folders=[MOCS]))
    month = month_vault()
    run(month, MARCH, month_sources())
    assert week.call_count <= 20, week.events
    assert month.call_count <= 45, month.events


def test_sources_from_config_takes_folders_formats_rule_and_moc_folders():
    config = {
        "concepts": {"calendar": {"granularities": {"daily": {"enabled": True, "path": DAILY},
                                                    "weekly": {"enabled": True, "path": WEEKLY}}},
                     "map_note": {"paths": [MOCS]}},
        "naming": {"calendar_patterns": {"daily": "YYYY-MM-DD", "weekly": "GGGG-[W]WW"}},
        "review": {"week": {"first_day": "monday", "min_days_in_first_week": 4},
                   "weekly": {"own_sections": ["In my own words"]}},
    }
    sources = sources_from_config(config, {})
    assert sources == PeriodSources(daily_folder=DAILY, daily_format="YYYY-MM-DD", weekly_folder=WEEKLY,
                                    weekly_format="GGGG-[W]WW", rule=ISO, own_sections=("In my own words",),
                                    weekly_skip_sections=DEFAULT_WEEKLY_SKIP, moc_folders=(MOCS,))
    bare = sources_from_config({"concepts": {"calendar": {"granularities": {"daily": {"path": DAILY}}}}}, {})
    assert bare.weekly_folder is None and bare.moc_folders == () and bare.daily_format == "YYYY-MM-DD"

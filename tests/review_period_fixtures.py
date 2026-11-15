#!/usr/bin/env python3
# version: 0.2.0
"""review_period_fixtures.py — the fixtures of the period-read tests
(tests/test_review_period.py and tests/test_review_period_end_pass.py;
spec 045 T3.3).

Lives in tests/, not tomo/scripts/lib/: never a production code path. Not
named `test_*`, so pytest does not collect it. Callers put tomo/scripts on
sys.path before importing it (the test files do).

The day readers are stubs that follow the wave-B seam: a daily's `Name:: v`
lines are today's fields, `Y-Name:: v` lines are yesterday fields,
`linked:: <stem>` lines name a same-day note the day reads through
`read_note(stem)`. Fixtures are synthetic; they share only the structure of
the owner's notes. `week_vault()` holds ISO week 2026-W13 with its day after,
a planner note and a task note; `month_vault()` holds March 2026 with two
weekly notes; `growth_vault()` adds stamped notes and MOCs around the W13
bounds; `quarter_vault()` holds 2026-Q1 with disagreeing dailies, weekly
and monthly notes (spec 046 T3.2).
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from review_fake_vault import ReviewFakeVault
from lib.period import Period
from lib.review_pacer import ReviewPacer
from lib.review_period import DayReaders, PeriodSources, period_bounds_ms, read_period

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


# ── sources and notes ──

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


MONTHLY = "Calendar/303 Monthly/"
Q1 = Period.quarter(2026, 1)             # 2026-01-01 .. 2026-03-31; weeks 2026-W01 .. 2026-W14

W01_NOTE = """# Weekly Review: [[2026-W01]]
## Review of the Week
### [[2025-12-30|2025-12-30 Tue]]
- old year [[Old Year]]
### [[2026-01-02|2026-01-02 Fri]]
- new year [[New Year]]
### In my own words
Own [[Week Own]]
"""

W07_NOTE = """# Weekly Review: [[2026-W07]]
## Review of the Week
### [[2026-02-10|2026-02-10 Tue]]
- tuesday [[Shared]] [[Only-Weekly]]
"""

W14_NOTE = """## Review of the Week
### [[2026-03-31|2026-03-31 Tue]]
- last [[Q End]]
### [[2026-04-01|2026-04-01 Wed]]
- april [[April Only]]
"""

FEB_NOTE = """# Monthly Review: [[2026-02]]
## Highlights
- [[Shared]] [[Only-Monthly]] [[2026-W07]] [[2026-02-10]] [[2026-Q1]]
## Organisation
- next [[Plan Link]]
"""


def quarter_sources(**extra) -> PeriodSources:
    kw = dict(monthly_folder=MONTHLY, monthly_format="YYYY-MM", quarterly_format="YYYY-[Q]Q",
              monthly_own_sections=["Highlights"])
    kw.update(extra)
    return month_sources(**kw)


def quarter_vault(**files) -> ReviewFakeVault:
    """Disagreeing notes: a link only in a weekly, only in a monthly, only in a daily, a link to `2026-02`."""
    base = dict([
        daily(date(2026, 1, 2), "jan [[New Year]] [[Jan Shared]]"),
        daily(date(2026, 2, 10), "tuesday [[Shared]] [[Only-Daily]] [[2026-02]]"),
        daily(date(2026, 3, 31), "end [[Q End]]"),
        daily(date(2026, 4, 1), "april\nY-Mood:: 2"),
    ])
    base[f"{WEEKLY}2026-W01.md"] = W01_NOTE
    base[f"{WEEKLY}2026-W07.md"] = W07_NOTE
    base[f"{WEEKLY}2026/2026-W14.md"] = W14_NOTE
    base[f"{MONTHLY}2026-02.md"] = FEB_NOTE
    base[TASK_NOTE] = TASK_NOTE_TEXT
    base.update(files)
    return ReviewFakeVault(base, folders=[DAILY, WEEKLY, MONTHLY, MOCS])


def growth_vault(page_size=None) -> ReviewFakeVault:
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


# ── running and reading a result ──

def run(vault, period, sources, settings=SETTINGS, readers=READERS):
    with ReviewPacer(vault) as pacer:
        return read_period(period, sources, settings, vault, pacer, readers=readers)


def day_report(result, day: str) -> dict:
    return next(d for d in result["report"]["days"] if d["date"] == day)


def entry(result, day: str) -> dict:
    return next(e for e in result["days"] if e["date"] == day)


def reads_of(vault, path: str) -> list:
    return [p for method, p in vault.events if method == "read_note" and p == path]

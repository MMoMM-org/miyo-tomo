#!/usr/bin/env python3
# version: 0.1.0
"""review_privacy_fixture.py — the marked vault of the /review privacy walk
(tests/test_review_privacy.py; spec 045 T5.4).

Lives in tests/, not tomo/scripts/lib/: never a production code path. Not
named `test_*`, so pytest does not collect it. Callers put tests/ on sys.path
before importing it (the test file does).

Pure data, kept apart from the walk and its assertions so the test file stays
within the constitution's file-size guidance: one marker string per kind of
journal content (`MARKERS`, with `MARKER_RE` and `KIND_OF` to find them
again), one readable tracker value (`READABLE`), the vault-config the scripts
read (`CONFIG`), the fake vault whose dailies, journal note, planner, task
note, weekly notes and templates each carry their markers (`build_vault()`),
and the model's proposals for a week and a month (`proposals(kind)`). All
text is synthetic; it shares only the structure of the owner's notes.
"""
from __future__ import annotations

import re
from datetime import date

from review_fake_vault import ReviewFakeVault

# One marker per kind of journal content; lowercase and `_` so it survives any rendering.
MARKERS = {
    "daily": "zzpriv_day_7f3a",        # daily-note text (body lines, tasks, the task note, a planner)
    "answer": "zzpriv_ans_7f3a",       # a journal answer: a prompt's text value in a daily, a 5-year journal
    "tracker": "zzpriv_trk_7f3a",      # a tracker value the habits cannot read
    "proposal": "zzpriv_prp_7f3a",     # the model's proposal text and the user's edits of it
    "weekly": "zzpriv_wkl_7f3a",       # weekly-note text: the target's body and headings
}
KIND_OF = {"day": "daily", "ans": "answer", "trk": "tracker", "prp": "proposal", "wkl": "weekly"}
MARKER_RE = re.compile(r"zzpriv_(day|ans|trk|prp|wkl)_7f3a")
DAY, ANS, TRK, PRP, WKL = (MARKERS[k] for k in ("daily", "answer", "tracker", "proposal", "weekly"))
# One tracker value the habits can read: it is counted into an average, so it may surface where a
# marker the parser rejects never would. Its only legitimate places are read.json and the habits
# line of the document (which the preview's section_md shows). A digit run no date, count or id has.
READABLE = "434343"
ANCHOR = f"Notes {WKL}"                 # the heading the user picks from the headings[] list

INBOX = "100 Inbox/"
DAILY = "Calendar/301 Daily/"
WEEKLY = "Calendar/302 Weekly/"
MONTHLY = "Calendar/303 Monthly/"
MOCS = "100 MOCs/"
JOURNAL = "Journal/"
PLANNER = "Efforts/300 Planner/"
TASK_NOTE = "Efforts/500 OnGoing/Next Todos.md"

CONFIG = {
    "profile": "miyo",
    "concepts": {
        "inbox": INBOX,
        "calendar": {"granularities": {"daily": {"enabled": True, "path": DAILY},
                                       "weekly": {"enabled": True, "path": WEEKLY},
                                       "monthly": {"enabled": True, "path": MONTHLY}}},
        "map_note": {"paths": [MOCS]},
    },
    "naming": {"calendar_patterns": {"daily": "YYYY-MM-DD", "weekly": "GGGG-[W]WW", "monthly": "YYYY-MM"}},
    "templates": {"base_path": "Templates/",
                  "mapping": {"weekly": "t_week.md", "monthly": "t_month.md", "daily": "t_day.md"}},
    "review": {
        "language": "en",
        "week": {"first_day": "monday", "min_days_in_first_week": 4},
        "daily": {"sections": [], "skip_sections": [], "task_notes": [TASK_NOTE], "max_chars_per_day": 12000},
        "weekly": {"heading": "Tomo Review", "place": {"anchor": "In my own words", "placement": "before"},
                   "own_sections": ["In my own words"]},
        "monthly": {"heading": "Tomo Review", "place": {"anchor": "Reflections", "placement": "before"},
                    "own_sections": ["Reflections"]},
    },
    "trackers": {"daily_note_trackers": {"today_fields": [{"name": "Sport", "type": "boolean"},
                                                          {"name": "Sleep", "type": "integer"},
                                                          {"name": "Energy", "type": "integer"}]}},
}


def _daily(day: str, text: str) -> tuple[str, str]:
    return f"{DAILY}{day}.md", f"---\ntags: [daily]\n---\n# {day}\n{text}\n"


def _weekly(name: str, start: date, *, target_without_anchor: bool = False) -> str:
    day = start.isoformat()
    lines = ["---", f"journal-start-date: {day}", "---", f"# {name}", "", f"week text {WKL}", "",
             "## Review of the Week", f"### [[{day}|{day} Mon]]", f"- day block {WKL} [[Alpha]]", ""]
    if target_without_anchor:       # the week flow's target: no anchor heading, one heading carrying the marker
        lines += [f"## Notes {WKL}", f"more {WKL}", "", "## Woche", f"text {WKL}", ""]
    else:
        lines += ["## In my own words", f"own words {WKL}", ""]
    return "\n".join(lines) + "\n"


def build_vault() -> ReviewFakeVault:
    files = dict([
        _daily("2026-03-01", f"first of march {DAY}\nSport:: yes\nSleep:: 6"),
        _daily("2026-03-10", f"{DAY} mid march\nSport:: no"),
        _daily("2026-03-23", f"monday {DAY} [[Alpha]]\nSport:: yes\nSleep:: 7\nGrateful:: {ANS}"),
        _daily("2026-03-24", f"tuesday {DAY}\n- [x] task {DAY} ✅ 2026-03-24\nSport:: yes\nSleep:: {TRK}"),
        _daily("2026-03-25", f"wednesday {DAY} [[5J-2026-03-25]] [[DP-2026-03-25|Dayplanner]]\nSport:: {TRK}\nSleep:: 8"),
        _daily("2026-03-26", f"thursday {DAY}\nSport:: yes\nSleep:: 6\nEnergy:: {READABLE}"),
        _daily("2026-03-27", f"friday {DAY}\nSport:: yes"),
        _daily("2026-03-29", f"sunday {DAY}\nSport:: yes\nSleep:: 7\nGrateful:: {ANS} again"),
        _daily("2026-03-30", f"monday after {DAY}\nSleep:: 7"),
        _daily("2026-03-31", f"last {DAY}\nSport:: no"),
        _daily("2026-04-01", f"april {DAY}"),
    ])
    files[f"{JOURNAL}5J-2026-03-25.md"] = f"# 5J-2026-03-25\nWhat made today good?\nAnswer {ANS} in journal\n"
    files[f"{PLANNER}DP-2026-03-25.md"] = f"# Plan\n- planned {DAY}\n"
    files[TASK_NOTE] = f"- [x] done {DAY} ✅ 2026-03-24\n- [ ] open {DAY}\n"
    files[f"{MOCS}Topic MOC.md"] = "moc\n"
    for name, start in (("2026-W09", date(2026, 2, 23)), ("2026-W10", date(2026, 3, 2)),
                        ("2026-W11", date(2026, 3, 9)), ("2026-W12", date(2026, 3, 16)),
                        ("2026-W14", date(2026, 3, 30))):
        files[f"{WEEKLY}{name}.md"] = _weekly(name, start)
    files[f"{WEEKLY}2026-W13.md"] = _weekly("2026-W13", date(2026, 3, 23), target_without_anchor=True)
    files["Templates/t_week.md"] = "---\ntags: weekly\n---\n# <% tp.file.title %>\n\n## Woche\n\n## In my own words\n\n"
    files["Templates/t_month.md"] = "# <% tp.file.title %>\n\n## Theme\n\n## Reflections\n\n"
    files["Templates/t_day.md"] = "## Daily Log\n\n## Habits\n"
    return ReviewFakeVault(files, folders=[DAILY, WEEKLY, MONTHLY, MOCS, INBOX])


def proposals(kind: str) -> dict:
    if kind == "week":
        groups = {"done": [{"text": f"Cleaned up {PRP}", "sources": ["2026-03-23", "2026-03-24"]}],
                  "open": [{"text": f"Taxes {PRP}", "sources": ["2026-03-26"]}],
                  "themes": [{"text": f"Sleep {PRP}", "sources": ["2026-03-23", "2026-03-25"]}]}
    else:
        groups = {"done": [{"text": f"March done {PRP}", "sources": ["2026-03-01", "2026-03-23"]}],
                  "weekly_only": [{"text": f"only weekly {PRP}", "sources": ["2026-W13"]}]}
    return {"language": "en", "groups": groups}

#!/usr/bin/env python3
# version: 0.1.0
"""review_scaled_quarter.py — a 2026-Q1 ``read_period`` result scaled to the T3.4 measurement (spec 046 T3.4).

Lives in tests/, never a production code path; not named `test_*`, so pytest
does not collect it. Callers put tomo/scripts on sys.path first.

The measurement (plan/phase-3.md, T3.4; 2026-11-15, test vault): one compact
`read.json` of 710,106 bytes; the compact `days` entries 179,969 / 164,293 /
181,763 bytes for 2026-01 / 02 / 03; the rest (184,081 bytes) weekly and
monthly notes, growth, report, open tasks and the mark lists. The breakdown of
that rest was not measured, so `scaled_quarter(shape)` builds two shapes that
both hit the measured totals exactly:

- ``children-heavy`` — the rest sits in the weekly and monthly notes (3 : 1),
  which go to the month parts: the hard case for a month part.
- ``index-heavy`` — the rest sits in growth and open tasks, which stay in the
  index: the hard case for the index.

The keys and nesting are those of `read_period`'s quarter result; every text
is synthetic filler (no journal text).
"""
from __future__ import annotations

import json
from typing import Dict, List

from lib.period import ISO, Period

MEASURED_TOTAL = 710_106
MEASURED_DAY_BYTES = {"2026-01": 179_969, "2026-02": 164_293, "2026-03": 181_763}
SHAPES = ("children-heavy", "index-heavy")
Q1 = Period.quarter(2026, 1)
DAILY = "Calendar/301 Daily/"
WEEKLY = "Calendar/302 Weekly/"
MONTHLY = "Calendar/303 Monthly/"
TASK_NOTE = "Efforts/500 OnGoing/Next Todos.md"
_WORDS = "synthetic filler text "


def compact_len(data) -> int:
    """Bytes of ``data`` in read.json's compact encoding, without the trailing newline."""
    return len(json.dumps(data, ensure_ascii=True, separators=(",", ":")))


def filler(n: int) -> str:
    return (_WORDS * (n // len(_WORDS) + 1))[:n]


def _shares(total: int, count: int) -> List[int]:
    q, r = divmod(total, count)
    return [q + (1 if i < r else 0) for i in range(count)]


def _day(day: str, text: str) -> dict:
    return {"dailies": [], "date": day, "fields": {"Sleep": "7"}, "has_content": True, "linked": [],
            "links": ["Alpha"], "partly_read": False, "problems": [], "sections": {"Daily Log": text}, "tasks": []}


def _days() -> List[dict]:
    out: List[dict] = []
    for month, target in MEASURED_DAY_BYTES.items():
        dates = [d.isoformat() for d in Q1.days() if d.isoformat()[:7] == month]
        base = sum(compact_len(_day(d, "")) for d in dates)
        out += [_day(d, filler(n)) for d, n in zip(dates, _shares(target - base, len(dates)))]
    return out


def _weekly() -> List[dict]:
    entries = []
    for week in Q1.weeks_overlapping(ISO):
        inside = [d.isoformat() for d in week.days() if Q1.start <= d <= Q1.end]
        entries.append({"path": f"{WEEKLY}{week.name}.md", "week": week.name, "overlap_days": len(inside),
                        "duplicate": False, "day_blocks": {d: "- day block" for d in inside},
                        "week_text": {"In my own words": ""}, "links": ["Alpha"]})
    return entries


def _monthly() -> List[dict]:
    return [{"path": f"{MONTHLY}{m.name}.md", "month": m.name, "overlap_days": len(m.days()), "duplicate": False,
             "day_blocks": {}, "month_text": {"Highlights": ""}, "links": ["Only-Monthly"]} for m in Q1.months()]


def _report(days: List[dict], weekly: List[dict], monthly: List[dict]) -> dict:
    return {
        "days": [{"date": d["date"], "dailies": [{"path": f"{DAILY}{d['date']}.md", "state": "found"}],
                  "duplicate": False, "linked": []} for d in days],
        "day_after": {"date": "2026-04-01", "dailies": [{"path": f"{DAILY}2026-04-01.md", "state": "read"}]},
        "task_notes": [{"path": TASK_NOTE, "state": "read"}],
        "weekly_status": "found", "weekly_notes": [{"week": w["week"], "path": w["path"], "state": "read"}
                                                   for w in weekly],
        "monthly_status": "found", "monthly_notes": [{"month": m["month"], "path": m["path"], "state": "read"}
                                                     for m in monthly],
        "growth": {"created": 40, "mocs_changed": 2, "mocs_linked_by_new": 1, "moc_folders": 1, "kado_none": []},
        "kado_empty": [], "advice": [], "not_read": [],
    }


def _skeleton() -> dict:
    days, weekly, monthly = _days(), _weekly(), _monthly()
    return {
        "period": {"kind": "quarter", "name": "2026-Q1", "start": "2026-01-01", "end": "2026-03-31"},
        "days": days, "weekly": weekly, "monthly": monthly,
        "only_in_monthly_links": ["Only-Monthly"], "dailies_not_in_monthly": ["Only-Daily"],
        "open_tasks": [{"done": False, "done_date": None, "source": TASK_NOTE, "text": ""} for _ in range(30)],
        "growth": {"created": [{"path": f"Notes/Created {i:03d}.md", "links": [""]} for i in range(40)],
                   "mocs_changed": ["100 MOCs/A MOC.md", "100 MOCs/B MOC.md"],
                   "mocs_linked_by_new": ["100 MOCs/A MOC.md"]},
        "not_read": [],
        "report": _report(days, weekly, monthly),
    }


def _pad(slots: List[tuple], total: int) -> None:
    """Spread ``total`` filler characters evenly over ``(container, key)`` string slots."""
    for (container, key), n in zip(slots, _shares(total, len(slots))):
        container[key] += filler(n)


def scaled_quarter(shape: str) -> dict:
    """A quarter result whose compact read.json is MEASURED_TOTAL bytes (with its newline), days as measured."""
    if shape not in SHAPES:
        raise ValueError(f"shape must be one of {SHAPES}")
    result = _skeleton()
    rest = MEASURED_TOTAL - (compact_len(result) + 1)
    if shape == "children-heavy":
        _pad([(w["week_text"], "In my own words") for w in result["weekly"]], rest * 3 // 4)
        _pad([(m["month_text"], "Highlights") for m in result["monthly"]], rest - rest * 3 // 4)
    else:
        _pad([(c["links"], 0) for c in result["growth"]["created"]], rest // 2)
        _pad([(t, "text") for t in result["open_tasks"]], rest - rest // 2)
    return result


def day_bytes(result: dict) -> Dict[str, int]:
    sums: Dict[str, int] = {}
    for day in result["days"]:
        sums[day["date"][:7]] = sums.get(day["date"][:7], 0) + compact_len(day)
    return sums

# review_weeks.py — the units of a /review period: weeks clipped to it, packed under the unit budget.
# version: 0.2.0
"""Units of a period for condensing in ``/review`` (spec 047 T2.2; PRD F1-AC1, F1-AC2; ADR-2).

``units`` turns a week, month or quarter into units: the weeks of the period
under the configured week rule, clipped to the period (a week review is one
unclipped unit), each split in date order into ``<week>a``, ``<week>b``… when
its days weigh more than ``UNIT_BUDGET``. A day's weight is the caller's
number: the indented UTF-8 bytes of its day file plus its growth files. Every
day of the period is in exactly one unit; a day heavier than the budget is a
unit alone and ``over_budget`` names it. ``takes_part`` decides whether a day
gives its unit something to condense. ``digest_cap`` is the byte cap of one
unit's digest.

Stdlib only; no file I/O.

Design notes: docs/tomo/scripts/lib/review_weeks.md
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping, Set

from lib.period import WEEK, Period, WeekRule

FILE_CEILING = 32_768
UNIT_BUDGET = 131_072
DIGEST_TOTAL = 114_688
DIGEST_MAX = 8_192

_SUFFIXES = "abcdefg"


def takes_part(day: Mapping[str, Any], created: int) -> bool:
    """A day with content, tasks, linked notes or at least one created note."""
    return bool(day.get("has_content") or day.get("tasks") or day.get("linked") or created > 0)


def _pack(days: List[date], day_bytes: Mapping[date, int]) -> List[List[date]]:
    groups: List[List[date]] = []
    current: List[date] = []
    size = 0
    for d in days:
        weight = day_bytes.get(d, 0)
        if current and size + weight > UNIT_BUDGET:
            groups.append(current)
            current, size = [], 0
        current.append(d)
        size += weight
    if current:
        groups.append(current)
    return groups


def units(period: Period, rule: WeekRule, day_bytes: Mapping[date, int],
          taking_part: Set[date]) -> List[Dict[str, Any]]:
    """The units of ``period`` in date order: ``{unit, week, days, bytes, takes_part}``."""
    weeks = [period] if period.kind == WEEK else period.weeks_overlapping(rule)
    out: List[Dict[str, Any]] = []
    for week in weeks:
        days = [d for d in week.days() if period.start <= d <= period.end]
        groups = _pack(days, day_bytes)
        for index, group in enumerate(groups):
            name = week.name if len(groups) == 1 else f"{week.name}{_SUFFIXES[index]}"
            out.append({
                "unit": name,
                "week": week.name,
                "days": [d.isoformat() for d in group],
                "bytes": sum(day_bytes.get(d, 0) for d in group),
                "takes_part": any(d in taking_part for d in group),
            })
    return out


def over_budget(unit_list: List[Dict[str, Any]]) -> List[str]:
    """Names of the units heavier than ``UNIT_BUDGET`` (a single day over it)."""
    return [u["unit"] for u in unit_list if u["bytes"] > UNIT_BUDGET]


def digest_cap(n_units: int) -> int:
    """Byte cap of one unit's digest: 14 units → 8,192, 16 → 7,168."""
    return min(DIGEST_MAX, DIGEST_TOTAL // max(1, n_units))

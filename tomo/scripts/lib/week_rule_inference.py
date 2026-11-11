# week_rule_inference.py — the week rule derived from the dates the existing weekly notes carry.
# version: 0.1.0
"""Infer the week rule of a weekly folder from its notes' own dates (spec 045, ADR-7).

``infer_rule(vault, notes, fmt)`` takes the ``(stem, path)`` pairs of a
folder listing and the proposal's name format, reads the dates of up to
``NOTES_TO_CHECK`` recent notes through any object with ``frontmatter(path)``
and ``note(path)`` (``lib.review_vault.Vault`` in production, a stub in the
tests), and returns an ``Inference``: ``inferred`` with the rule every dated
note supports, ``ambiguous`` when the notes contradict each other or none
carries a date, ``default`` when no name parses at all. ``checked`` records
every note read, with its start date and ``locale``, so the caller can match
names against their dates and pick a language.

Stdlib only; the Obsidian plugin configuration is never consulted.

Design notes: docs/tomo/scripts/lib/week_rule_inference.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Set, Tuple

from lib.period import ISO, WeekRule, parse_name
from lib.review_vault import frontmatter_start, heading_start

NOTES_TO_CHECK = 8


@dataclass
class Checked:
    stem: str
    path: str
    start: Optional[date]
    locale: Optional[str]


@dataclass
class Inference:
    verdict: str                          # inferred | ambiguous | default
    rule: Optional[WeekRule] = None
    checked: List[Checked] = field(default_factory=list)


def rules_fitting(year: int, number: int, start: date) -> Set[WeekRule]:
    """Every rule starting on ``start``'s weekday under which (year, number) begins on ``start``."""
    first_day = start.weekday()
    fitting: Set[WeekRule] = set()
    for min_days in range(1, 8):
        rule = WeekRule(first_day, min_days)
        try:
            if rule.week_of(start) == (year, number):
                fitting.add(rule)
        except Exception:  # noqa: BLE001 — a date outside the supported years fits nothing
            continue
    return fitting


def choose_rule(fitting: Set[WeekRule]) -> WeekRule:
    """ISO's 4 when the notes allow it, else 1 (week 1 holds 1 January), else the smallest."""
    by_min_days = {rule.min_days_in_first_week: rule for rule in fitting}
    for preferred in (4, 1):
        if preferred in by_min_days:
            return by_min_days[preferred]
    return by_min_days[min(by_min_days)]


def recent_candidates(notes: List[Tuple[str, str]], fmt: str) -> List[Tuple[str, str, int, int]]:
    """``(stem, path, year, number)`` of the names that parse, most recent first;
    every path of a duplicated stem stays."""
    found = []
    for stem, path in notes:
        period = parse_name(stem, fmt, ISO)
        if period is not None:
            found.append((stem, path, period.year, period.number))
    found.sort(key=lambda item: (item[2], item[3]), reverse=True)
    return found[:NOTES_TO_CHECK]


def _locale(frontmatter: dict) -> Optional[str]:
    value = frontmatter.get("locale")
    return value if isinstance(value, str) and value.strip() else None


def infer_rule(vault, notes: List[Tuple[str, str]], fmt: str) -> Inference:
    candidates = recent_candidates(notes, fmt)
    if not candidates:
        return Inference("default")
    checked: List[Checked] = []
    fitting: Optional[Set[WeekRule]] = None
    for stem, path, year, number in candidates:
        frontmatter = vault.frontmatter(path) or {}
        start = frontmatter_start(frontmatter)
        if start is None:
            text = vault.note(path)
            start = heading_start(text) if text else None
        checked.append(Checked(stem, path, start, _locale(frontmatter)))
        if start is None:
            continue
        rules = rules_fitting(year, number, start)
        fitting = rules if fitting is None else fitting & rules
    if not fitting:
        return Inference("ambiguous", None, checked)
    return Inference("inferred", choose_rule(fitting), checked)

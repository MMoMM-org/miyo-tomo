#!/usr/bin/env python3
# version: 0.1.0
"""test_week_rule_inference.py — Unit tests for lib/week_rule_inference.py (spec 045 T2.2).

Pins the inference on its own, without the script or Kado:
- rules_fitting keeps every (weekday-of-start, min_days) rule that reproduces
  the note's week number on its start date; a week-1 note pins min_days
- choose_rule prefers ISO's 4, then 1, then the smallest
- recent_candidates keeps the eight most recent parsing names, every path
  of a duplicated stem among them, and skips names that do not parse
- infer_rule intersects the rules over the dated notes: inferred, ambiguous
  (contradiction or no dates), default (no candidate); the note body is read
  only when the frontmatter holds no date; the locale is carried per note
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))

from lib.period import ISO, WeekRule  # noqa: E402
from lib.week_rule_inference import (  # noqa: E402
    NOTES_TO_CHECK, Checked, Inference, choose_rule, infer_rule, recent_candidates, rules_fitting,
)

FMT = "GGGG-[W]WW"


class StubVault:
    """``frontmatter``/``note`` by path, the calls recorded."""

    def __init__(self, frontmatter=None, notes=None):
        self._frontmatter = frontmatter or {}
        self._notes = notes or {}
        self.calls: list = []

    def frontmatter(self, path):
        self.calls.append(("frontmatter", path))
        return self._frontmatter.get(path)

    def note(self, path):
        self.calls.append(("note", path))
        return self._notes.get(path)


def _week_text(days) -> str:
    return "\n".join(f"### [[{d}|{d} Day]]" for d in days) + "\n"


# ---------------------------------------------------------------- rules_fitting / choose_rule

def test_rules_fitting_is_every_min_days_on_the_start_weekday():
    # 2026-01-01 is a Thursday: the Monday-first week around it holds 4 days of 2026,
    # so min_days 1..4 make it week 1 (week 12 = 16 March); 5..7 shift the count by one week.
    fitting = rules_fitting(2026, 12, date(2026, 3, 16))
    assert fitting == {WeekRule(0, n) for n in range(1, 5)}
    assert all(r.first_day == 0 for r in fitting)
    # Sunday-first: the week around 1 January holds 3 days of 2026, so only min_days 1..3 give week 12 on 15 March
    sunday = rules_fitting(2026, 12, date(2026, 3, 15))
    assert sunday == {WeekRule(6, n) for n in range(1, 4)}
    assert rules_fitting(2026, 5, date(2026, 3, 16)) == set()    # min_days shifts the count by one week at most


def test_rules_fitting_week_1_pins_min_days():
    # 2027-01-01 is a Friday: Monday-first week 1 starts 2026-12-28 only when min_days <= 3
    fitting = rules_fitting(2027, 1, date(2026, 12, 28))
    assert {r.min_days_in_first_week for r in fitting} == {1, 2, 3}
    assert all(r.first_day == 0 for r in fitting)


def test_rules_fitting_outside_the_supported_years_fits_nothing():
    assert rules_fitting(1, 1, date(1, 1, 1)) == set()


def test_choose_rule_prefers_iso_then_1_then_the_smallest():
    assert choose_rule({WeekRule(0, n) for n in range(1, 8)}) == ISO
    assert choose_rule({WeekRule(6, 1), WeekRule(6, 2), WeekRule(6, 3)}) == WeekRule(6, 1)
    assert choose_rule({WeekRule(6, 5), WeekRule(6, 6)}) == WeekRule(6, 5)


# ---------------------------------------------------------------- recent_candidates

def test_recent_candidates_keeps_the_most_recent_parsing_names():
    notes = [(f"2026-W{n:02d}", f"W/2026-W{n:02d}.md") for n in range(1, 11)]
    notes += [("Weekly Index", "W/Weekly Index.md"), ("2025-W50", "W/2025/2025-W50.md")]
    found = recent_candidates(notes, FMT)
    assert len(found) == NOTES_TO_CHECK == 8
    assert [c[0] for c in found] == [f"2026-W{n:02d}" for n in range(10, 2, -1)]
    assert found[0] == ("2026-W10", "W/2026-W10.md", 2026, 10)


def test_recent_candidates_keeps_every_path_of_a_duplicated_stem():
    notes = [("2026-W12", "W/2026-W12.md"), ("2026-W12", "W/2025/2026-W12.md"), ("2026-W11", "W/2026-W11.md")]
    found = recent_candidates(notes, FMT)
    assert [(c[0], c[1]) for c in found] == [
        ("2026-W12", "W/2026-W12.md"), ("2026-W12", "W/2025/2026-W12.md"), ("2026-W11", "W/2026-W11.md")]


# ---------------------------------------------------------------- infer_rule

def test_infer_rule_without_a_candidate_is_default():
    vault = StubVault()
    assert infer_rule(vault, [("Weekly Index", "W/Weekly Index.md")], FMT) == Inference("default")
    assert vault.calls == []


def test_infer_rule_from_frontmatter_dates_reads_no_note_body():
    vault = StubVault(frontmatter={
        "W/2026-W13.md": {"journal-start-date": "2026-03-23", "locale": "de"},
        "W/2026-W12.md": {"journal-end-date": "2026-03-22"},          # start = end - 6
    })
    result = infer_rule(vault, [("2026-W12", "W/2026-W12.md"), ("2026-W13", "W/2026-W13.md")], FMT)
    assert result.verdict == "inferred" and result.rule == ISO
    assert result.checked == [
        Checked("2026-W13", "W/2026-W13.md", date(2026, 3, 23), "de"),
        Checked("2026-W12", "W/2026-W12.md", date(2026, 3, 16), None),
    ]
    assert not any(c[0] == "note" for c in vault.calls)


def test_infer_rule_reads_the_body_only_when_the_frontmatter_has_no_date():
    days = [f"2026-03-{d:02d}" for d in range(15, 22)]                 # Sunday 15 .. Saturday 21
    vault = StubVault(frontmatter={"W/2026-W12.md": {"locale": "en"}},
                      notes={"W/2026-W12.md": _week_text(days)})
    result = infer_rule(vault, [("2026-W12", "W/2026-W12.md")], FMT)
    assert result.verdict == "inferred" and result.rule == WeekRule(6, 1)
    assert result.checked[0].start == date(2026, 3, 15) and result.checked[0].locale == "en"
    assert vault.calls == [("frontmatter", "W/2026-W12.md"), ("note", "W/2026-W12.md")]


def test_infer_rule_contradicting_starts_are_ambiguous():
    vault = StubVault(frontmatter={
        "W/2026-W13.md": {"journal-start-date": "2026-03-23"},        # Monday
        "W/2026-W12.md": {"journal-start-date": "2026-03-15"},        # Sunday
    })
    result = infer_rule(vault, [("2026-W13", "W/2026-W13.md"), ("2026-W12", "W/2026-W12.md")], FMT)
    assert result.verdict == "ambiguous" and result.rule is None
    assert len(result.checked) == 2


def test_infer_rule_no_dates_at_all_is_ambiguous():
    vault = StubVault(frontmatter={"W/2026-W13.md": {}}, notes={"W/2026-W13.md": _week_text(["2026-03-23"])})
    result = infer_rule(vault, [("2026-W13", "W/2026-W13.md")], FMT)
    assert result.verdict == "ambiguous" and result.rule is None
    assert result.checked == [Checked("2026-W13", "W/2026-W13.md", None, None)]


def test_infer_rule_a_week_1_note_pins_min_days_to_1():
    vault = StubVault(frontmatter={
        "W/2027-W01.md": {"journal-start-date": "2026-12-28"},
        "W/2026-W52.md": {"journal-start-date": "2026-12-21"},
    })
    result = infer_rule(vault, [("2027-W01", "W/2027-W01.md"), ("2026-W52", "W/2026-W52.md")], FMT)
    assert result.verdict == "inferred" and result.rule == WeekRule(0, 1)

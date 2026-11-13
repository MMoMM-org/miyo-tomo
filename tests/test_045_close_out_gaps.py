#!/usr/bin/env python3
# version: 0.1.0
"""test_045_close_out_gaps.py — spec 045 T6.4: criteria parts no test could fail.

The close-out trace (docs/XDD/specs/045-weekly-monthly-review/close-out.md §3)
found three criterion parts with an imperative in the runtime text, or a lib
behaviour, that no test pinned: deleting the line or changing the code left
every traced test green. Each test below fails under the mutation the
close-out names for it.

The two prose pins (F4-AC2, F4-AC5) only prove the imperative exists in
periodic-review/SKILL.md; whether the model follows it is the live walk's
evidence, as for tests/test_review_skill.py. The period-read test (F8-AC2)
drives lib.review_period over the month fixture of
tests/review_period_fixtures.py with its stub day readers.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SKILL = REPO_ROOT / "tomo" / "dot_claude" / "skills" / "periodic-review" / "SKILL.md"
for p in (str(SCRIPTS_DIR), str(TESTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from review_period_fixtures import DAILY, MARCH, entry, month_sources, month_vault, run  # noqa: E402


def _section(heading: str) -> str:
    """One `## ` section of the skill, whitespace collapsed."""
    text = SKILL.read_text(encoding="utf-8")
    begin = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", begin + 1)
    return re.sub(r"\s+", " ", text[begin:end if end != -1 else len(text)])


# ── Prose pins ─────────────────────────────────────────────────────────────


def test_the_groups_are_defined_for_the_model_with_the_two_day_theme_rule():
    """F4-AC2: the model is told what each group holds — done, open, a theme found on at least two days,
    growth from the read's lists, the two month-only groups from the link differences — and to leave an
    empty group out. The script enforces the two-day rule and the group set; this line is what the model
    sorts by."""
    text = _section("5. Propose and write the document")
    line = ("- `done`: what happened and got done; `open`: what stayed open; `themes`: a theme found on at least "
            "two days; `growth`: what the `growth` lists of `read.json` show; `weekly_only` and `not_in_weekly` "
            "(month only, when `read.json` holds `weekly`): what the `only_in_weekly_links` and "
            "`dailies_not_in_weekly` lists show. Leave out a group with nothing to propose.")
    assert line in text
    assert text.index("Write `tomo-tmp/review/<stem>/proposals.json`:") < text.index(line) \
        < text.index("python3 scripts/review-doc.py write --stem <stem>")


def test_every_proposal_is_written_in_the_setup_language():
    """F4-AC5: the proposals are in the review language of the setup. The script renders headings and fixed
    lines by `review.language`; the proposal text itself is the model's, so this is the only place the
    language reaches it."""
    text = _section("5. Propose and write the document")
    assert "`<language>` is the value of `review.language` in the config file." in text
    assert "- Every item is in `<language>`; its `sources` name the notes of `read.json` it rests on" in text
    assert text.index("`<language>` is the value of") < text.index("- Every item is in `<language>`")


# ── The period read ────────────────────────────────────────────────────────


def test_a_month_reads_the_day_after_it_for_the_last_days_yesterday_fields():
    """F8-AC2 for a month's last day: the reader reads the day after the period for every period kind, so a
    yesterday field written on 1 April counts for 31 March, and nothing else of that day is used. The week
    case is tests/test_review_period.py::test_day_after_period_is_read_for_its_yesterday_fields_only; the
    live vault has no 2026-04-01 daily, so the month's day after was never seen read."""
    vault = month_vault()
    after = f"{DAILY}2026-04-01.md"
    result = run(vault, MARCH, month_sources())
    assert after in vault.paths_seen
    assert entry(result, "2026-03-31")["fields"] == {"Mood": "9"}
    assert [e["date"] for e in result["days"]][-1] == "2026-03-31"
    assert not any("april" in str(e["sections"]) for e in result["days"])
    assert result["report"]["day_after"] == {"date": "2026-04-01", "dailies": [{"path": after, "state": "read"}]}

#!/usr/bin/env python3
# version: 0.1.1
"""test_045_close_out_gaps.py — spec 045 T6.4: criteria parts no test could fail.

The close-out trace (docs/XDD/specs/045-weekly-monthly-review/close-out.md §3)
found three criterion parts with an imperative in the runtime text, or a lib
behaviour, that no test pinned: deleting the line or changing the code left
every traced test green. The test below fails under the mutation the
close-out names for it.

The two prose pins of F4-AC2 (the groups, the two-day theme rule) and F4-AC5
(the setup language) were retired by spec 047 T6.3 with the step-5 proposal
prose; they are pinned against review-proposer.md in tests/test_047_agents.py
(`groups`, `themes-over-the-period`, `review-language`). The period-read test
(F8-AC2) drives lib.review_period over the month fixture of
tests/review_period_fixtures.py with its stub day readers.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
for p in (str(SCRIPTS_DIR), str(TESTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from review_period_fixtures import DAILY, MARCH, entry, month_sources, month_vault, run  # noqa: E402


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

#!/usr/bin/env python3
# version: 0.1.0
"""test_review_period_golden.py — the whole period read of the fake month and
the fake week, pinned against a recording of `main` before spec 046
generalised it (spec 046 T3.1; ADR-6; CON-2).

WHAT THIS GUARDS: every key of the `read_period` result — days, weekly entries,
both link differences (`only_in_weekly_links`, `dailies_not_in_weekly`),
growth, open tasks, not_read and the full report — for `month_vault()` over
March 2026 and `growth_vault()` over 2026-W13 from
tests/review_period_fixtures.py, read with its stub day readers. The
generalisation to a child-review level and the quarter must leave both
unchanged: without a mapping, the review output stays as in spec 045.

The goldens in tests/fixtures/046-t3-1-period-read-golden/ were recorded by
`record.py` beside them from an export of `main`; its docstring says when a
re-record is legitimate. A failure here is a changed read shape, not a stale
golden.

Fixtures and fakes only: no live vault, no live Kado.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from review_period_fixtures import (  # noqa: E402
    MARCH,
    MOCS,
    W13,
    growth_vault,
    month_sources,
    month_vault,
    run,
    week_sources,
)

GOLDEN_DIR = TESTS_DIR / "fixtures" / "046-t3-1-period-read-golden"


def _golden(name: str) -> dict:
    return json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _as_json(result: dict) -> dict:
    """The result as read.json would hold it: tuples become lists."""
    return json.loads(json.dumps(result, sort_keys=True, ensure_ascii=False))


CASES = {
    "month": lambda: run(month_vault(), MARCH, month_sources()),
    "week": lambda: run(growth_vault(), W13, week_sources(moc_folders=[MOCS])),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_period_read_unchanged_by_generalisation(name):
    result = _as_json(CASES[name]())
    golden = _golden(name)
    for key in sorted(set(golden) | set(result)):
        assert result.get(key) == golden.get(key), f"{name}: '{key}' differs from the main recording"


def test_month_golden_holds_weekly_entries_and_both_link_differences():
    # a golden without these keys would pin nothing of the month's weekly read
    golden = _golden("month")
    assert golden["weekly"] and golden["report"]["weekly_status"] == "found"
    assert golden["only_in_weekly_links"] and golden["dailies_not_in_weekly"]

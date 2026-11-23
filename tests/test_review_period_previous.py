#!/usr/bin/env python3
# version: 0.1.0
"""test_review_period_previous.py — the previous review notes inside the period read
(spec 047 T3.2; ADR-5; PRD F2-AC6, F3-AC1, F3-AC2, F3-AC3).

WHAT THIS GUARDS: `PeriodSources.quarterly_folder` from the setup (config over
profile); `read_period` lists and reads the previous notes BEFORE the reader's
end pass and resolves them after it, so a previous note turned away in the
first pass is retried by the end pass and found; the result gains `previous`
(one row per previous period, `sections` as line arrays for a found note) and
the report gains `previous` with metadata only (kind, name, role, path,
state, cause?, partly_read — never text); one pacer and one summary cover the
period's notes and the previous notes together (F2-AC6); a refusal of the
period's own dailies still stops the read while a refused previous note does
not.

Mechanisms a mutation falsifies:
- `test_a_previous_note_turned_away_is_retried_by_the_end_pass` — RED when
  `review_previous.prefetch` runs after `reader.finish()` (the turned-away
  read is then final: `not-read` / `failed`).
- `test_the_report_lists_the_previous_notes_without_text` — RED when the
  report rows carry `sections`.
- `test_one_summary_covers_the_period_and_the_previous_notes` — RED when the
  previous notes' turned-away reads are not retried by the run's one end pass
  (prefetch after `finish()`: `not_read` is then not empty).

Fixtures and fakes only (tests/review_period_fixtures.py, tests/review_fake_vault.py).
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib.kado_client import _MAX_RETRIES, KadoToolError  # noqa: E402
from lib.review_pacer import ReviewPacer  # noqa: E402
from lib.review_period import read_period, sources_from_config  # noqa: E402
from review_period_fixtures import (  # noqa: E402
    DAILY,
    MONTHLY,
    READERS,
    SETTINGS,
    W13,
    WEEKLY,
    daily,
    month_sources,
    run,
    week_vault,
)

QUARTERLY = "Calendar/304 Quarterly/"
W12_PATH, FEB_PATH = f"{WEEKLY}2026-W12.md", f"{MONTHLY}2026-02.md"
W12_NOTE = "# Weekly Review [[2026-W12]]\n\n## Next week\n- book the train PRIVATE-W12\n"
FEB_NOTE = "# Monthly Review [[2026-02]]\n\n## Goals\n- run twice a week PRIVATE-FEB\n"
FORBIDDEN = KadoToolError('kado-read returned an error: {"code":"FORBIDDEN","message":"Access denied by tag rules."}')
REPORT_KEYS = {"kind", "name", "role", "path", "state", "partly_read"}


def _sources(**extra):
    return month_sources(monthly_folder=MONTHLY, monthly_format="YYYY-MM", **extra)


def _vault(**files):
    return week_vault(**{W12_PATH: W12_NOTE, FEB_PATH: FEB_NOTE, **files})


def _row(rows, role):
    return next(r for r in rows if r["role"] == role)


# ── the setup (ADR-5: PeriodSources gains quarterly_folder) ──

def test_quarterly_folder_config_over_profile():
    profile = {"concept_defaults": {"calendar": {"granularities": {"quarterly": {"path": "Profile/Quarterly/"}}}}}
    bare = {"concepts": {"calendar": {"granularities": {"daily": {"path": DAILY}}}}}
    assert sources_from_config(bare, profile).quarterly_folder == "Profile/Quarterly/"
    config = {"concepts": {"calendar": {"granularities": {"daily": {"path": DAILY},
                                                          "quarterly": {"path": QUARTERLY}}}}}
    assert sources_from_config(config, profile).quarterly_folder == QUARTERLY
    assert sources_from_config(bare, {}).quarterly_folder is None


# ── one pass: before the end pass, resolved after it ──

def test_a_week_read_gains_its_previous_notes():
    result = run(_vault(), W13, _sources())
    rows = result["previous"]
    assert [(r["role"], r["name"], r["state"], r["path"]) for r in rows] == [
        ("previous-week", "2026-W12", "found", W12_PATH), ("previous-month", "2026-02", "found", FEB_PATH)]
    assert _row(rows, "previous-week")["sections"]["Next week"] == ["- book the train PRIVATE-W12"]
    assert result["not_read"] == []


def test_a_previous_note_turned_away_is_retried_by_the_end_pass():
    vault = _vault()
    vault.rate_limit(W12_PATH, failures=_MAX_RETRIES + 1)
    result = run(vault, W13, _sources())
    row = _row(result["previous"], "previous-week")
    assert (row["state"], row["path"]) == ("found", W12_PATH)
    assert result["not_read"] == []
    assert vault.events.count(("read_note", W12_PATH)) == 2, "first pass, then the end pass"


def test_a_previous_note_still_turned_away_is_not_read_failed_and_in_not_read():
    vault = _vault()
    vault.rate_limit(W12_PATH)
    result = run(vault, W13, _sources())
    row = _row(result["previous"], "previous-week")
    assert (row["state"], row["cause"]) == ("not-read", "failed")
    assert result["not_read"] == result["report"]["not_read"] == [W12_PATH]


def test_the_report_lists_the_previous_notes_without_text():
    result = run(_vault(), W13, _sources())
    rows = result["report"]["previous"]
    assert [(r["kind"], r["name"], r["role"], r["path"], r["state"], r["partly_read"]) for r in rows] == [
        ("week", "2026-W12", "previous-week", W12_PATH, "found", False),
        ("month", "2026-02", "previous-month", FEB_PATH, "found", False)]
    assert all(set(r) == REPORT_KEYS for r in rows)
    text = json.dumps(result["report"])
    assert "PRIVATE" not in text and "book the train" not in text


def test_the_report_names_the_cause_of_a_note_not_read():
    vault = _vault()
    vault.fail[("read_note", FEB_PATH)] = FORBIDDEN
    rows = run(vault, W13, _sources())["report"]["previous"]
    assert _row(rows, "previous-month") == {"kind": "month", "name": "2026-02", "role": "previous-month",
                                            "path": FEB_PATH, "state": "not-read", "cause": "refused",
                                            "partly_read": False}


def test_a_kind_not_set_up_costs_no_call():
    vault = _vault()
    result = run(vault, W13, month_sources())         # no monthly folder or format
    assert _row(result["previous"], "previous-month")["state"] == "not-set-up"
    assert not any(path == MONTHLY or path.startswith(MONTHLY) for _, path in vault.events)


def test_previous_rows_use_the_day_settings_limit():
    big = "# R\n\n## First\n" + "a" * 60 + "\n\n## Second\n" + "b" * 60 + "\n"
    result = run(_vault(**{W12_PATH: big}), W13, _sources(), settings=dict(SETTINGS, max_chars_per_day=70))
    row = _row(result["previous"], "previous-week")
    assert row["partly_read"] is True and "Second" not in row["sections"]
    assert _row(result["report"]["previous"], "previous-week")["partly_read"] is True


# ── one pacer, one summary (F2-AC6) ──

def _summary(vault):
    with ReviewPacer(vault) as pacer:
        result = read_period(W13, _sources(), SETTINGS, vault, pacer, readers=READERS)
        return result, pacer.summary(result["not_read"])


def test_one_summary_covers_the_period_and_the_previous_notes():
    day = f"{DAILY}2026-03-23.md"
    retried = {}
    for case, paths in (("daily", [day]), ("previous", [W12_PATH]), ("both", [day, W12_PATH])):
        vault = _vault()
        for path in paths:
            vault.rate_limit(path, failures=_MAX_RETRIES + 1)
        result, summary = _summary(vault)
        assert result["not_read"] == [] and summary["calls"] == vault.call_count
        retried[case] = summary["retried"]
    assert retried["daily"] > 0 and retried["previous"] > 0
    assert retried["both"] == retried["daily"] + retried["previous"]


# ── a refusal: the dailies stop the read, a previous note does not ──

def test_a_refused_previous_note_does_not_stop_the_read():
    vault = _vault()
    vault.fail[("read_note", W12_PATH)] = FORBIDDEN
    vault.fail[("list_dir", MONTHLY)] = FORBIDDEN
    result = run(vault, W13, _sources())
    assert [(r["state"], r.get("cause")) for r in result["previous"]] == [("not-read", "refused")] * 2
    assert any(e["has_content"] for e in result["days"])


@pytest.mark.parametrize("call", [("list_dir", DAILY), ("read_note", f"{DAILY}2026-03-23.md")],
                         ids=["daily-listing", "daily-read"])
def test_refused_dailies_still_stop_the_read(call):
    vault = _vault()
    vault.fail[("read_note", W12_PATH)] = FORBIDDEN
    vault.fail[call] = FORBIDDEN
    with pytest.raises(KadoToolError, match="FORBIDDEN"):
        run(vault, W13, _sources())


def test_the_dailies_are_listed_before_any_previous_note():
    vault = _vault(**dict([daily(date(2026, 3, 24), "x")]))
    run(vault, W13, _sources())
    first_previous = min(vault.events.index(e) for e in (("list_dir", WEEKLY), ("list_dir", MONTHLY)))
    assert vault.events.index(("list_dir", DAILY)) < first_previous

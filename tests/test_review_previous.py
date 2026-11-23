#!/usr/bin/env python3
# version: 0.1.1
"""test_review_previous.py — finding and reading the previous review notes of a period
(spec 047 T3.1; ADR-5; PRD F3-AC1..F3-AC5, F3-AC7..F3-AC10, F4-AC9, F6-AC7).

WHAT THIS GUARDS: `previous_periods` for every row of the SDD table "Previous
periods per kind" (a week's previous month is the month before the month the
week STARTS in); `locations` + `set_up` (config over profile, a kind without
folder or format is `not-set-up` with no Kado call); `prefetch` (before the
end pass) and `resolve` (after it) through the one `PacedReader`; the five
states with the `not-read` causes `refused` (a `KadoToolError` naming
`FORBIDDEN`, caught per call), `failed` (still pending after the end pass)
and `kado-none` (a listing answered with nothing); a `KadoAuthError` or any
other `KadoToolError` propagates; the note's text cleaned and cut at a heading
boundary at `max_chars`; at most four Kado calls for a week review.

Mechanisms a mutation falsifies:
- `test_found_in_the_year_subfolder` — RED when the year-subfolder candidate
  of `Period.note_paths` is not looked up.
- `test_forbidden_read_is_not_read_refused` /
  `test_forbidden_listing_is_not_read_refused` — RED when the `FORBIDDEN`
  catch is removed (the error escapes); the listing one also RED when the
  `if key in note.refused` guard of `_guarded` is removed (the refused
  folder is listed again after the end pass).
- `test_unquoted_forbidden_in_another_message_is_not_refused` — RED when the
  match is the bare word `FORBIDDEN` instead of Kado's quoted error code.
- `test_skeleton_only_note_is_empty` — RED when the `has_content` check is
  dropped (every note is `found`).

Fakes only (tests/review_fake_vault.py): synthetic notes, no live Kado.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib.kado_client import KadoAuthError, KadoToolError  # noqa: E402
from lib.period import ISO, MONTH, QUARTER, WEEK, Period, WeekRule  # noqa: E402
from lib.review_pacer import ReviewPacer  # noqa: E402
from lib.review_previous import (  # noqa: E402
    EMPTY,
    FAILED,
    FOUND,
    KADO_NONE,
    MISSING,
    NOT_READ,
    NOT_SET_UP,
    REFUSED,
    STATES,
    locations,
    prefetch,
    previous_periods,
    resolve,
    set_up,
)
from lib.review_reader import PacedReader  # noqa: E402
from review_fake_vault import ReviewFakeVault  # noqa: E402

WEEKLY = "Calendar/302 Weekly/"
MONTHLY = "Calendar/303 Monthly/"
QUARTERLY = "Calendar/304 Quarterly/"
FOLDERS = {WEEK: WEEKLY, MONTH: MONTHLY, QUARTER: QUARTERLY}
FORMATS = {WEEK: "GGGG-[W]WW", MONTH: "YYYY-MM", QUARTER: "YYYY-[Q]Q"}
W14 = Period.week(2026, 14)
MARCH = Period.month(2026, 3)
Q1 = Period.quarter(2026, 1)
FORBIDDEN = KadoToolError('kado-read returned an error: {"code":"FORBIDDEN","message":"Access denied by tag rules."}')

W13_NOTE = """---
tags: [review]
---
# Weekly Review [[2026-W13]]

[[2026-W12]] <- -> [[2026-W14]]

## What should I start doing?
- start running again
- call Jana about the trip

```dataview
LIST FROM "secret"
```
"""
FEB_NOTE = "# Monthly Review [[2026-02]]\n\n## Goals\n- start running again\n"
SKELETON = """---
tags: [review]
---
# Weekly Review <% tp.file.title %>

## What went well?
-

## What should I start doing?
- [ ]
Mood::
"""


def _reader(vault):
    pacer = ReviewPacer(vault)
    return PacedReader(vault, pacer), pacer


def _run(vault, period, *, folders=None, formats=None, rule=ISO, max_chars=12000):
    """set_up → prefetch → finish → resolve, as the period read will call them."""
    reader, pacer = _reader(vault)
    try:
        notes = set_up(period, rule, FOLDERS if folders is None else folders,
                       FORMATS if formats is None else formats)
        prefetch(reader, notes)
        reader.finish()
        return resolve(reader, notes, max_chars=max_chars)
    finally:
        pacer.close()


def _by_role(rows, role):
    return next(r for r in rows if r["role"] == role)


def _w14_vault(**files):
    data = {WEEKLY + "2026-W13.md": W13_NOTE, MONTHLY + "2026-02.md": FEB_NOTE}
    data.update(files)
    return ReviewFakeVault({k: v for k, v in data.items() if v is not None}, folders=[WEEKLY, MONTHLY, QUARTERLY])


# ── which previous periods (F3-AC1, F3-AC2, F3-AC3) ──

@pytest.mark.parametrize("period, expected", [
    (W14, [("previous-week", "2026-W13", date(2026, 3, 23)), ("previous-month", "2026-02", date(2026, 2, 1))]),
    (Period.week(2026, 1), [("previous-week", "2025-W52", date(2025, 12, 22)),
                            ("previous-month", "2025-11", date(2025, 11, 1))]),
    (MARCH, [("previous-month", "2026-02", date(2026, 2, 1)), ("previous-quarter", "2025-Q4", date(2025, 10, 1))]),
    (Period.month(2026, 1), [("previous-month", "2025-12", date(2025, 12, 1)),
                             ("previous-quarter", "2025-Q4", date(2025, 10, 1))]),
    (Q1, [("previous-quarter", "2025-Q4", date(2025, 10, 1))]),
], ids=["2026-W14", "2026-W01", "2026-03", "2026-01", "2026-Q1"])
def test_previous_periods_per_kind(period, expected):
    got = [(role, prev.name, prev.start) for role, prev in previous_periods(period, ISO)]
    assert got == expected


def test_previous_periods_week_under_sunday_one_day_rule():
    rule = WeekRule(first_day=6, min_days_in_first_week=1)
    week = Period.week(2026, 1, rule)
    assert week.start == date(2025, 12, 28)
    (role_w, prev_w), (role_m, prev_m) = previous_periods(week, rule)
    assert role_w == "previous-week" and prev_w.kind == WEEK
    assert prev_w.start == date(2025, 12, 21) and prev_w.end == date(2025, 12, 27)
    assert prev_w == Period.containing(WEEK, date(2025, 12, 27), rule)
    assert (role_m, prev_m.name) == ("previous-month", "2025-11")


def test_week_previous_month_is_decided_by_the_week_start():
    # W14 runs 2026-03-30 … 2026-04-05: April's previous month (2026-03) is not read
    names = [prev.name for _, prev in previous_periods(W14, ISO)]
    assert "2026-03" not in names


# ── finding (F3-AC4) ──

def test_found_flat():
    rows = _run(_w14_vault(), W14)
    assert _by_role(rows, "previous-week")["path"] == WEEKLY + "2026-W13.md"
    assert _by_role(rows, "previous-week")["state"] == FOUND


def test_found_in_the_year_subfolder():
    vault = _w14_vault(**{WEEKLY + "2026-W13.md": None, WEEKLY + "2026/2026-W13.md": W13_NOTE})
    row = _by_role(_run(vault, W14), "previous-week")
    assert (row["state"], row["path"]) == (FOUND, WEEKLY + "2026/2026-W13.md")


def test_note_under_another_name_is_missing_and_never_searched():
    vault = _w14_vault(**{MONTHLY + "2026-02.md": None, MONTHLY + "February 2026.md": FEB_NOTE})
    row = _by_role(_run(vault, W14), "previous-month")
    assert (row["state"], row["path"]) == (MISSING, None)
    assert "sections" not in row
    assert not any(method.startswith("search") for method, _ in vault.events)


def test_locations_config_over_profile():
    config = {"concepts": {"calendar": {"granularities": {"weekly": {"path": "Mine/Weekly/"}}}},
              "naming": {"calendar_patterns": {"weekly": "GGGG-[W]WW", "monthly": "YYYY-MM"}}}
    profile = {"concept_defaults": {"calendar": {"granularities": {
        "weekly": {"path": "Profile/Weekly/"}, "monthly": {"path": MONTHLY}, "quarterly": {"path": QUARTERLY}}}}}
    folders, formats = locations(config, profile)
    assert folders == {WEEK: "Mine/Weekly/", MONTH: MONTHLY, QUARTER: QUARTERLY}
    assert formats == {WEEK: "GGGG-[W]WW", MONTH: "YYYY-MM", QUARTER: None}


# ── the five states (F3-AC5, F3-AC7, F3-AC8, F3-AC9) ──

def test_every_state_is_one_of_five_and_the_read_continues():
    vault = _w14_vault()
    rows = _run(vault, W14)
    assert [r["role"] for r in rows] == ["previous-week", "previous-month"]
    for row in rows:
        assert row["state"] in STATES
        assert set(row) >= {"kind", "name", "role", "path", "state", "partly_read"}
        assert ("cause" in row) == (row["state"] == NOT_READ)


@pytest.mark.parametrize("case", ["found", "empty", "missing", "not-set-up", "not-read"])
def test_each_state_once_per_note_and_review_continues(case):
    files, formats = {}, dict(FORMATS)
    vault_fail = None
    if case == "empty":
        files[WEEKLY + "2026-W13.md"] = SKELETON
    elif case == "missing":
        files[WEEKLY + "2026-W13.md"] = None
        files[WEEKLY + "2026-W12.md"] = W13_NOTE
    elif case == "not-set-up":
        formats[WEEK] = None
    elif case == "not-read":
        vault_fail = ("read_note", WEEKLY + "2026-W13.md")
    vault = _w14_vault(**files)
    if vault_fail:
        vault.fail[vault_fail] = FORBIDDEN
    rows = _run(vault, W14, formats=formats)
    assert _by_role(rows, "previous-week")["state"] == case
    # the other note is read regardless: the review continues
    assert _by_role(rows, "previous-month")["state"] == FOUND


def test_skeleton_only_note_is_empty():
    row = _by_role(_run(_w14_vault(**{WEEKLY + "2026-W13.md": SKELETON}), W14), "previous-week")
    assert (row["state"], row["path"]) == (EMPTY, WEEKLY + "2026-W13.md")
    assert "sections" not in row


def test_any_user_text_is_found():
    row = _by_role(_run(_w14_vault(**{WEEKLY + "2026-W13.md": SKELETON + "\nSlept well all week.\n"}), W14),
                   "previous-week")
    assert row["state"] == FOUND


def test_only_a_tomo_block_is_found():
    note = SKELETON + "\n%% tomo-review 2026-W13 %%\n- [ ] Plan the trip with Jana\n%% tomo-review 2026-W13 %%\n"
    row = _by_role(_run(_w14_vault(**{WEEKLY + "2026-W13.md": note}), W14), "previous-week")
    assert row["state"] == FOUND
    assert any("Plan the trip with Jana" in line for lines in row["sections"].values() for line in lines)


def test_no_folder_or_format_is_not_set_up_without_a_call():
    vault = _w14_vault()
    rows = _run(vault, W14, folders={WEEK: None, MONTH: MONTHLY, QUARTER: QUARTERLY},
                formats={WEEK: "GGGG-[W]WW", MONTH: None, QUARTER: None})
    assert [(r["role"], r["state"], r["path"]) for r in rows] == [
        ("previous-week", NOT_SET_UP, None), ("previous-month", NOT_SET_UP, None)]
    assert vault.events == []


def test_forbidden_read_is_not_read_refused():
    vault = _w14_vault()
    vault.fail[("read_note", WEEKLY + "2026-W13.md")] = FORBIDDEN
    row = _by_role(_run(vault, W14), "previous-week")
    assert (row["state"], row["cause"]) == (NOT_READ, REFUSED)
    assert row["path"] == WEEKLY + "2026-W13.md"
    # refused once, never asked again after the end pass
    assert vault.events.count(("read_note", WEEKLY + "2026-W13.md")) == 1


def test_forbidden_listing_is_not_read_refused():
    vault = _w14_vault()
    vault.fail[("list_dir", MONTHLY)] = FORBIDDEN
    row = _by_role(_run(vault, W14), "previous-month")
    assert (row["state"], row["cause"], row["path"]) == (NOT_READ, REFUSED, None)
    # refused once, never listed again after the end pass
    assert vault.events.count(("list_dir", MONTHLY)) == 1


def test_auth_error_stops_the_read():
    vault = _w14_vault()
    vault.fail[("read_note", MONTHLY + "2026-02.md")] = KadoAuthError("Kado rejected the request (HTTP 401).")
    with pytest.raises(KadoAuthError):
        _run(vault, W14)


def test_unquoted_forbidden_in_another_message_is_not_refused():
    # only Kado's error code "FORBIDDEN" (quoted, as in {"code":"FORBIDDEN"}) is a denial
    vault = _w14_vault()
    vault.fail[("read_note", WEEKLY + "2026-W13.md")] = KadoToolError(
        "kado-read returned an error: FORBIDDEN word inside an unrelated message")
    with pytest.raises(KadoToolError, match="unrelated"):
        _run(vault, W14)


def test_tool_error_without_forbidden_is_not_refused():
    vault = _w14_vault()
    vault.fail[("read_note", WEEKLY + "2026-W13.md")] = KadoToolError("kado-read returned an error: boom")
    with pytest.raises(KadoToolError, match="boom"):
        _run(vault, W14)


def test_still_pending_after_the_end_pass_is_failed():
    vault = _w14_vault()
    vault.rate_limit(WEEKLY + "2026-W13.md", failures=None)
    vault.rate_limit(MONTHLY, failures=None)
    rows = _run(vault, W14)
    assert (_by_role(rows, "previous-week")["state"], _by_role(rows, "previous-week")["cause"]) == (NOT_READ, FAILED)
    assert (_by_role(rows, "previous-month")["state"], _by_role(rows, "previous-month")["cause"]) == (NOT_READ, FAILED)


def test_recovered_in_the_end_pass_is_found():
    vault = _w14_vault()
    vault.rate_limit(WEEKLY + "2026-W13.md", failures=5)
    assert _by_role(_run(vault, W14), "previous-week")["state"] == FOUND


def test_empty_listing_is_kado_none():
    vault = ReviewFakeVault({MONTHLY + "2026-02.md": FEB_NOTE}, folders=[WEEKLY, MONTHLY])
    row = _by_role(_run(vault, W14), "previous-week")
    assert (row["state"], row["cause"], row["path"]) == (NOT_READ, KADO_NONE, None)


# ── the text (F3-AC10, F4-AC5, F4-AC9) ──

def test_text_cleaned_into_sections():
    row = _by_role(_run(_w14_vault(), W14), "previous-week")
    assert row["partly_read"] is False
    assert row["sections"]["What should I start doing?"] == ["- start running again", "- call Jana about the trip"]
    joined = "\n".join(line for lines in row["sections"].values() for line in lines)
    assert "secret" not in joined and "dataview" not in joined     # query fences dropped
    assert "[[2026-W12]]" not in joined                               # navigation dropped
    assert "tags" not in joined                                       # frontmatter not body


def test_note_over_the_limit_cut_at_a_heading_boundary():
    big = "# R\n\n## First\n" + "a" * 50 + "\n\n## Second\n" + "b" * 50 + "\n\n## Third\n" + "c" * 50 + "\n"
    row = _by_role(_run(_w14_vault(**{WEEKLY + "2026-W13.md": big}), W14, max_chars=140), "previous-week")
    assert row["state"] == FOUND and row["partly_read"] is True
    assert "Third" not in row["sections"]
    assert "First" in row["sections"]
    assert all(not line or line == "a" * 50 or line == "b" * 50
               for lines in row["sections"].values() for line in lines)


def test_first_section_over_the_limit_is_hard_cut():
    big = "## Only\n" + "x" * 500 + "\n"
    row = _by_role(_run(_w14_vault(**{WEEKLY + "2026-W13.md": big}), W14, max_chars=100), "previous-week")
    assert row["partly_read"] is True
    assert sum(len(line) for lines in row["sections"].values() for line in lines) <= 100


def test_zero_limit_is_clamped():
    row = _by_role(_run(_w14_vault(), W14, max_chars=0), "previous-week")
    assert row["state"] == FOUND and row["partly_read"] is True


def test_off_limits_heading_kept_as_text():
    note = W13_NOTE + "\n## Health\n- knee hurts again\n"
    row = _by_role(_run(_w14_vault(**{WEEKLY + "2026-W13.md": note}), W14), "previous-week")
    assert row["sections"]["Health"] == ["- knee hurts again"]


def test_note_is_read_as_it_stands_now():
    applied = W13_NOTE.replace("- call Jana about the trip\n", "")
    row = _by_role(_run(_w14_vault(**{WEEKLY + "2026-W13.md": applied}), W14), "previous-week")
    joined = "\n".join(line for lines in row["sections"].values() for line in lines)
    assert "call Jana" not in joined and "start running again" in joined


@pytest.mark.parametrize("period", [W14, MARCH, Q1], ids=["week", "month", "quarter"])
def test_target_note_is_never_a_previous_note(period):
    own = {WEEK: WEEKLY + "2026-W14.md", MONTH: MONTHLY + "2026-03.md", QUARTER: QUARTERLY + "2026-Q1.md"}
    files = {own[period.kind]: "# Review\n- [ ] carried from the target note itself\n",
             QUARTERLY + "2025-Q4.md": "## Q4\n- plan\n", MONTHLY + "2025-12.md": "- dec\n"}
    vault = _w14_vault(**files)
    for _ in range(2):           # a start over reads anew and still never the target note
        rows = _run(vault, period)
        assert own[period.kind] not in {r["path"] for r in rows}
        assert all(r["name"] != period.name for r in rows)
    assert ("read_note", own[period.kind]) not in vault.events


# ── calls ──

def test_previous_notes_add_at_most_four_calls():
    vault = _w14_vault()
    rows = _run(vault, W14)
    assert [r["state"] for r in rows] == [FOUND, FOUND]
    assert vault.call_count <= 4
    assert sorted(vault.events) == sorted([("list_dir", WEEKLY), ("read_note", WEEKLY + "2026-W13.md"),
                                           ("list_dir", MONTHLY), ("read_note", MONTHLY + "2026-02.md")])


def test_resolve_adds_no_call():
    vault = _w14_vault()
    reader, pacer = _reader(vault)
    try:
        notes = set_up(W14, ISO, FOLDERS, FORMATS)
        prefetch(reader, notes)
        reader.finish()
        before = vault.call_count
        resolve(reader, notes, max_chars=12000)
        assert vault.call_count == before
    finally:
        pacer.close()

#!/usr/bin/env python3
# version: 0.1.0
"""test_review_period_end_pass.py — the end pass of a period read and the
cache keys behind it: a rate-limited daily, linked note, name lookup or
folder listing recovered by the end pass or still failing afterwards, the
reads a recovered listing makes after the end pass and the one `not_read`
list they end in, and the cache keys that keep a link stem, a note path, a
folder listing and a `listNotes` query apart (spec 045 T3.3; PRD F3-AC10,
F3-AC11, F3-AC12). The fixtures are tests/review_period_fixtures.py's;
tests/test_review_period.py holds the rest of the period read.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from lib.kado_client import _MAX_RETRIES, KadoConnectionError, KadoToolError  # noqa: E402
from review_period_fixtures import (  # noqa: E402
    DAILY,
    MARCH,
    MOCS,
    PLANNER,
    TASK_NOTE,
    W13,
    WEEKLY,
    daily,
    day_report,
    entry,
    growth_vault,
    month_sources,
    month_vault,
    reads_of,
    run,
    week_sources,
    week_vault,
)


# ── the end pass ──

def test_a_rate_limited_daily_is_recovered_by_the_end_pass():
    vault = week_vault()
    path = f"{DAILY}2026-03-23.md"
    vault.rate_limit(path, failures=_MAX_RETRIES + 1)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == []
    assert entry(result, "2026-03-23")["has_content"] is True
    assert "Alpha" in entry(result, "2026-03-23")["links"]
    assert day_report(result, "2026-03-23")["dailies"] == [{"path": path, "state": "found"}]


def test_a_daily_that_still_fails_at_the_end_is_not_read_and_marked_failed():
    vault = week_vault()
    path = f"{DAILY}2026-03-23.md"
    vault.rate_limit(path)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == [path]
    assert day_report(result, "2026-03-23")["dailies"] == [{"path": path, "state": "failed"}]
    assert entry(result, "2026-03-23")["has_content"] is False
    assert vault.min_interval == 0.0


def test_a_rate_limited_linked_note_is_recovered_without_a_second_daily_read():
    vault = week_vault()
    path = f"{PLANNER}DP-2026-03-25.md"
    vault.rate_limit(path, failures=_MAX_RETRIES + 1)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == []
    linked = {"name": "DP-2026-03-25", "path": path, "state": "read"}
    assert day_report(result, "2026-03-25")["linked"] == [linked]
    assert day_report(result, "2026-03-27")["linked"] == [linked]
    assert reads_of(vault, f"{DAILY}2026-03-25.md") == [f"{DAILY}2026-03-25.md"]


def test_a_rate_limited_name_lookup_is_recovered_by_the_end_pass():
    vault = week_vault()
    vault.rate_limit("DP-2026-03-25", failures=_MAX_RETRIES + 1)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == []
    assert day_report(result, "2026-03-25")["linked"][0]["state"] == "read"


def test_a_linked_note_that_still_fails_is_marked_failed():
    vault = week_vault()
    path = f"{PLANNER}DP-2026-03-25.md"
    vault.rate_limit(path)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == [path]
    assert day_report(result, "2026-03-25")["linked"] == [{"name": "DP-2026-03-25", "path": path, "state": "failed"}]


def test_a_connection_error_propagates():
    vault = week_vault()
    vault.connection_error = KadoConnectionError("down")
    with pytest.raises(KadoConnectionError):
        run(vault, W13, week_sources())


# ── a folder listing and the end pass ──

def test_a_rate_limited_daily_listing_recovered_by_the_end_pass_reads_the_whole_period():
    free = run(week_vault(), W13, week_sources())
    vault = week_vault()
    vault.rate_limit(DAILY, failures=_MAX_RETRIES + 1)
    result = run(vault, W13, week_sources())
    assert result == free
    assert result["not_read"] == []
    assert entry(result, "2026-03-23")["has_content"] is True
    assert entry(result, "2026-03-29")["fields"] == {"Sleep": "8", "Mood": "5"}
    assert result["report"]["day_after"]["dailies"] == [{"path": f"{DAILY}2026-03-30.md", "state": "read"}]
    dailies = [p for p in vault.files if p.startswith(DAILY)]
    assert all(reads_of(vault, p) == [p] for p in dailies), vault.events
    assert reads_of(vault, TASK_NOTE) == [TASK_NOTE]
    assert [p for m, p in vault.events if m == "list_dir"] == [DAILY, DAILY]


def test_a_daily_listing_that_still_fails_leaves_the_period_unread_without_an_access_hint():
    vault = week_vault()
    vault.rate_limit(DAILY)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == [DAILY]
    assert result["report"]["not_read"] == [DAILY]
    assert result["report"]["kado_empty"] == []
    assert result["report"]["advice"] == []
    assert len(result["days"]) == 7
    assert all(e["dailies"] == [] and e["has_content"] is False for e in result["days"])
    assert all(d["dailies"] == [] for d in result["report"]["days"])
    assert result["report"]["day_after"] == {"date": "2026-03-30", "dailies": []}
    assert result["report"]["task_notes"] == [{"path": TASK_NOTE, "state": "read"}]
    assert not any(p.startswith(DAILY) and p != DAILY for p in vault.paths_seen)


def test_a_daily_that_fails_after_a_recovered_listing_is_still_marked_failed():
    vault = week_vault()
    vault.rate_limit(DAILY, failures=_MAX_RETRIES + 1)
    path = f"{DAILY}2026-03-23.md"
    vault.rate_limit(path)
    result = run(vault, W13, week_sources())
    assert result["not_read"] == [path]
    assert day_report(result, "2026-03-23")["dailies"] == [{"path": path, "state": "failed"}]
    assert entry(result, "2026-03-24")["has_content"] is True


def test_a_rate_limited_weekly_listing_recovered_by_the_end_pass_reads_the_weekly_notes():
    free = run(month_vault(), MARCH, month_sources())
    vault = month_vault()
    vault.rate_limit(WEEKLY, failures=_MAX_RETRIES + 1)
    result = run(vault, MARCH, month_sources())
    assert result == free
    assert result["report"]["weekly_status"] == "found"
    assert [w["path"] for w in result["weekly"]] == [f"{WEEKLY}2026/2026-W09.md", f"{WEEKLY}2026-W13.md"]
    assert result["only_in_weekly_links"] == free["only_in_weekly_links"]
    assert result["not_read"] == []
    assert all(reads_of(vault, w["path"]) == [w["path"]] for w in result["weekly"])
    assert [p for m, p in vault.events if m == "list_dir" and p == WEEKLY] == [WEEKLY, WEEKLY]


def test_a_weekly_listing_that_still_fails_is_not_read_without_an_access_hint():
    vault = month_vault()
    vault.rate_limit(WEEKLY)
    result = run(vault, MARCH, month_sources())
    assert result["report"]["weekly_status"] == "not-read"
    assert result["not_read"] == [WEEKLY]
    assert result["report"]["kado_empty"] == []
    assert result["report"]["advice"] == []
    assert result["weekly"] == []
    assert result["report"]["weekly_notes"] == []
    assert "only_in_weekly_links" not in result and "dailies_not_in_weekly" not in result
    assert entry(result, "2026-03-23")["has_content"] is True
    assert not any(p.startswith(WEEKLY) and p != WEEKLY for p in vault.paths_seen)


def test_a_weekly_note_that_fails_after_a_recovered_weekly_listing_is_in_the_one_not_read_list():
    vault = month_vault()
    vault.rate_limit(WEEKLY, failures=_MAX_RETRIES + 1)
    path = f"{WEEKLY}2026-W13.md"
    vault.rate_limit(path)
    result = run(vault, MARCH, month_sources())
    assert result["not_read"] == [path]
    assert result["report"]["not_read"] == result["not_read"]
    assert {"week": "2026-W13", "path": path, "state": "failed"} in result["report"]["weekly_notes"]
    assert [w["path"] for w in result["weekly"]] == [f"{WEEKLY}2026/2026-W09.md"]
    assert result["report"]["weekly_status"] == "found"


# ── cache keys ──

def test_a_link_stem_equal_to_a_moc_folder_name_does_not_share_a_cache_entry():
    path, text = daily(date(2026, 3, 25), "Wednesday\nlinked:: Notes")
    vault = week_vault(**{path: text, "Other/Notes.md": "a note called Notes", "Notes/Topic MOC.md": "moc"})
    result = run(vault, W13, week_sources(moc_folders=["Notes"]))
    assert day_report(result, "2026-03-25")["linked"] == [{"name": "Notes", "path": "Other/Notes.md", "state": "read"}]
    assert result["report"]["growth"]["kado_none"] == ["created"]
    assert [p for m, p in vault.events if m == "list_notes" and p == "Notes"] == ["Notes"]


def test_a_link_stem_spelled_like_a_note_path_already_read_is_looked_up_not_served_that_note():
    # RED when the name: mark is dropped: the stem keys into the planner's text, which is then read as a path
    planner_path = f"{PLANNER}DP-2026-03-25.md"
    path, text = daily(date(2026, 3, 27), f"Friday log [[Gamma]]\nlinked:: {planner_path}")
    vault = week_vault(**{path: text})
    result = run(vault, W13, week_sources())
    assert day_report(result, "2026-03-25")["linked"] == [{"name": "DP-2026-03-25", "path": planner_path,
                                                            "state": "read"}]
    assert day_report(result, "2026-03-27")["linked"] == [{"name": planner_path, "path": None, "state": "missing"}]
    assert [p for m, p in vault.events if m == "search_by_name"] == ["DP-2026-03-25", planner_path]
    assert reads_of(vault, planner_path) == [planner_path]
    assert result["not_read"] == []


def test_a_task_note_spelled_like_the_daily_folder_is_refused_by_kado_not_served_the_listing():
    # RED when the dir: mark is dropped: the note read keys into the cached listing instead of reaching Kado
    vault = week_vault()
    with pytest.raises(KadoToolError):
        run(vault, W13, week_sources(), settings={"sections": ["Daily Log"], "task_notes": [DAILY]})
    assert [p for m, p in vault.events if m == "list_dir"] == [DAILY]
    assert reads_of(vault, DAILY) == [DAILY]


def test_the_created_query_and_a_moc_listing_over_the_same_prefix_are_two_reads():
    vault = growth_vault()
    result = run(vault, W13, week_sources(moc_folders=["/"]))
    assert [p for m, p in vault.events if m == "list_notes" and p == "/"] == ["/", "/"]
    assert f"{MOCS}Quiet MOC.md" in result["growth"]["mocs_changed"]
    assert result["growth"]["mocs_linked_by_new"] == [f"{MOCS}Other MOC.md", f"{MOCS}Topic MOC.md"]
    assert [c["path"] for c in result["growth"]["created"]] == ["Notes/Edge.md", "Notes/New One.md", "Notes/New Two.md"]

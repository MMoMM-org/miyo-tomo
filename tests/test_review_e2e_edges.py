#!/usr/bin/env python3
# version: 0.1.0
"""test_review_e2e_edges.py — the document edge cases, the setup rerun and a sparse period of /review end to end
on the fake vault (spec 045 T6.1 fix round; PRD Edge Cases, Secondary User Journeys 2 and 6, F5-AC1, Rule 7).

The third file over tests/review_e2e_walk.py. Pinned here, each run the way SKILL.md runs it: every item
unticked → `parse` says `nothing_to_deliver`, `preview` and `deliver` refuse `nothing-to-deliver`, nothing is
written; the review document renamed inside the inbox → `start` still lists it by its period (its frontmatter,
under the new path) while `parse` by stem reports `not-found` with the path the stage knows, so the skill offers
Start over; moved out of the inbox → not listed, `not-found` the same way; the Approved line deleted → `parse`
warns `approved-line-missing`, `preview` and `deliver` refuse it, nothing is delivered; `/review setup` with a
saved setup → `start` returns `current.<kind>` with the saved values, `match` proposes, and Confirm with a
correction replaces the saved setup (the other keys kept); a week with only a few dailies (2026-W14: three of
seven days) → the report names each day, the dailies found, and the document is written for the existing
weekly note. Every write attempted through the client is under the inbox prefix, per test and in the sweep.

The read-side edge cases of the PRD are unit-tested, not walked here: a linked Dayplanner or journal note that
is missing or cannot be read → tests/test_review_day.py::test_missing_linked_note_is_a_problem_of_that_day_and_the_day_still_read
and ::test_unreadable_linked_note_reported_the_same_way; two daily notes with the same date →
tests/test_review_period.py::test_two_dailies_for_one_date_are_both_read_and_reported_duplicate. All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import (  # noqa: E402
    APPROVED, CONFIG, INBOX, TICKED, WEEK, WEEK_DOC, WEEK_PERIOD, WEEK_STEM, WEEKLY, WRITES, Walk,
)

SPARSE_PERIOD, SPARSE_STEM = "2026-W14", "2026-W14_review"
SPARSE_PROPOSALS = {"language": "en", "groups": {
    "done": [{"text": "Closed the month", "sources": ["2026-03-30", "2026-03-31"]}],
    "open": [{"text": "April starts", "sources": ["2026-04-01"]}]}}


@pytest.fixture
def ready(tmp_path, monkeypatch, capsys, request):
    """A walk whose setup is confirmed for both kinds (the fixture config)."""
    w = Walk(tmp_path, monkeypatch, capsys, request.node.nodeid, config=CONFIG)
    yield w
    outside = [p for p in w.vault.recorded if not p.startswith(INBOX)]
    assert outside == [], f"Tomo wrote outside the inbox: {outside}"


def _approved_week(walk: Walk) -> str:
    assert walk.pass1(WEEK_PERIOD, WEEK)["status"] == "written"
    return walk.doc(WEEK_DOC)


# ── the user unticks everything ──────────────────────────────────────────────────────────


def test_everything_unticked_is_nothing_to_deliver_and_nothing_is_delivered(ready: Walk):
    walk = ready
    text = _approved_week(walk).replace("- [x] ", "- [ ] ").replace(APPROVED, TICKED, 1)
    walk.edit_document(WEEK_DOC, text)
    out = walk.parse(WEEK_STEM)
    assert out["status"] == "ok" and out["approved"] is True and out["nothing_to_deliver"] is True, out
    assert out["counts"]["kept"] == 0 and out["counts"]["unticked"] >= 3 and out["counts"]["added"] == 0
    assert walk.preview(WEEK_STEM)["problems"] == ["nothing-to-deliver"]
    out = walk.deliver(WEEK_STEM)
    assert out["status"] == "refused" and out["problems"] == ["nothing-to-deliver"] and "paths" not in out
    assert walk.vault.recorded == [WEEK_DOC] and f"{INBOX}{WEEK_STEM}_instructions.json" not in walk.vault.files
    assert walk.listing() == [(WEEK_STEM, "open")], "the document stays open for Start over"


# ── the review document renamed or moved ─────────────────────────────────────────────────


def test_renamed_review_document_is_listed_by_its_period_and_parse_reports_not_found(ready: Walk):
    walk = ready
    _approved_week(walk)
    renamed = f"{INBOX}My week 13.md"
    walk.vault.files[renamed] = walk.vault.files.pop(WEEK_DOC)               # renamed inside the inbox
    walk.vault.modified[renamed] = walk.vault.modified.pop(WEEK_DOC)
    out = walk.start()
    assert [(r["period"], r["stem"], r["state"], r["doc_path"]) for r in out["open_reviews"]] == [
        (WEEK_PERIOD, WEEK_STEM, "open", renamed)], "found by its period, under the new name"
    assert walk.parse(WEEK_STEM) == {"status": "not-found", "stem": WEEK_STEM, "doc_path": WEEK_DOC}
    assert walk.preview(WEEK_STEM)["status"] == "not-found", "the skill offers Start over"
    walk.vault.files["Archive/My week 13.md"] = walk.vault.files.pop(renamed)   # moved out of the inbox
    assert walk.start()["open_reviews"] == [], "a document outside the inbox is not a review Tomo offers"
    assert walk.parse(WEEK_STEM)["status"] == "not-found"
    assert walk.vault.recorded == [WEEK_DOC]


# ── the Approved line deleted ────────────────────────────────────────────────────────────


def test_deleted_approved_line_is_approved_line_missing_and_nothing_is_delivered(ready: Walk):
    walk = ready
    text = _approved_week(walk)
    assert text.count(f"{APPROVED}\n") == 1
    walk.edit_document(WEEK_DOC, text.replace(f"{APPROVED}\n", "", 1))
    out = walk.parse(WEEK_STEM)
    assert out["status"] == "ok" and out["approved"] is False and "approved-line-missing" in out["warnings"], out
    assert walk.preview(WEEK_STEM)["problems"] == ["approved-line-missing"]
    out = walk.deliver(WEEK_STEM)
    assert out["status"] == "refused" and out["problems"] == ["approved-line-missing"] and "paths" not in out
    assert walk.vault.recorded == [WEEK_DOC] and walk.listing() == [(WEEK_STEM, "open")]


# ── journey 2: /review setup with a saved setup ──────────────────────────────────────────


def test_setup_rerun_shows_the_saved_setup_and_a_confirmed_correction_replaces_it(ready: Walk):
    walk = ready
    out = walk.start("setup")
    assert out["status"] == "ok" and out["request"]["kind"] == "setup", out
    current = out["current"]
    assert current["week"]["folder"] == WEEKLY and current["week"]["heading"] == "Tomo Review"
    assert "invalid" not in current["week"] and current["month"] is not None
    before = yaml.safe_load((walk.root / "config" / "vault-config.yaml").read_text(encoding="utf-8"))
    saved = walk.setup(WEEK, heading="Wochenrückblick")                    # match → Correct the heading → Confirm
    assert saved["status"] == "written" and "review.weekly.heading" in saved["keys"], saved
    after = yaml.safe_load((walk.root / "config" / "vault-config.yaml").read_text(encoding="utf-8"))
    assert after["review"]["weekly"]["heading"] == "Wochenrückblick"
    assert after["review"]["weekly"]["place"] == before["review"]["weekly"]["place"]
    assert after["review"]["monthly"] == before["review"]["monthly"], "the other kind is untouched"
    assert walk.start("setup")["current"]["week"]["heading"] == "Wochenrückblick"
    assert walk.vault.recorded == [], "the setup writes only the config file"


# ── journey 6: a sparse period ───────────────────────────────────────────────────────────


def test_sparse_period_reads_its_few_dailies_and_writes_the_document(ready: Walk):
    walk = ready
    out = walk.start(SPARSE_PERIOD)
    assert out["request"]["start"] == "2026-03-30" and out["request"]["end"] == "2026-04-05"
    read = walk.read(SPARSE_PERIOD, WEEK)
    assert read["status"] == "ok" and read["nothing_to_review"] is False, read
    days = read["report"]["days"]
    assert [d["date"] for d in days] == [f"2026-03-{n}" for n in (30, 31)] + [f"2026-04-0{n}" for n in range(1, 6)]
    found = {d["date"]: [x["state"] for x in d["dailies"]] for d in days}
    assert found["2026-03-30"] == ["found"] and found["2026-03-31"] == ["found"] and found["2026-04-01"] == ["found"]
    assert all(found[f"2026-04-0{n}"] == [] for n in range(2, 6)), "four days without a daily are named, not hidden"
    out = walk.write(SPARSE_STEM, WEEK, SPARSE_PROPOSALS)
    assert out["status"] == "written" and out["target"] == f"{WEEKLY}{SPARSE_PERIOD}.md" and out["target_exists"]
    assert out["counts"]["done"] == 1 and out["counts"]["open"] == 1 and out["rejected"] == []
    assert walk.listing() == [(SPARSE_STEM, "open")] and walk.vault.recorded == [f"{INBOX}{SPARSE_PERIOD} Review.md"]


# ── the sweep: every write attempted so far, under the inbox prefix ──────────────────────


def test_every_write_attempted_so_far_was_under_the_inbox_prefix():
    """Order-independent: whatever ran before this test, every write attempted through the client was under
    the inbox; no count is assumed."""
    assert [(t, p) for t, p in WRITES if not p.startswith(INBOX)] == []

#!/usr/bin/env python3
# version: 0.1.5
"""test_review_e2e_edges.py — the document edge cases, the setup rerun and a sparse period of /review end to end
on the fake vault (spec 045 T6.1 fix round; PRD Edge Cases, Secondary User Journeys 2 and 6, F5-AC1, Rule 7).

The third file over tests/review_e2e_walk.py. Pinned here, each run the way SKILL.md runs it: every item
unticked → `parse` says `nothing_to_deliver`, `preview` and `deliver` refuse `nothing-to-deliver`, nothing is
written; the review document renamed inside the inbox → `start` still lists it by its period (its frontmatter,
under the new path) while `parse` by stem reports `not-found` with the path the stage knows, so the skill offers
Start over; moved out of the inbox → not listed, `not-found` the same way; the Approved line deleted → `parse`
warns `approved-line-missing`, `preview` and `deliver` refuse it, nothing is delivered; Approved and one item ticked
with the Obsidian Tasks plugin installed (` ✅ YYYY-MM-DD` appended to each line, Phase 6 live walk) → `parse` approves
with the same counts and items as a plain tick, the preview section and the delivered MD carry no marker; `/review setup` with a
saved setup → `start` returns `current.<kind>` with the saved values, `match` proposes, and Confirm with a
correction replaces the saved setup (the other keys kept); a week with only a few dailies (2026-W14: three of
seven days) → the report names each day, the dailies found, and the document is written for the existing
weekly note; a first setup whose config maps no weekly template (the owner's instance, Phase 6 live walk) → `match`
lists the templates folder's `template_candidates` and marks `needs_anchor`, the user's pick is passed back as
`--template`, Confirm saves the mapping key beside the setup, and the review then reads; the same setup with `0 none`
and a typed anchor (fix round 1) → the week-rule rerun carries `--template none` and lists the templates folder no
second time, the Correct rerun carries `--anchor` and keeps the heading, Confirm saves the anchor and no mapping
key; weekly notes that disagree on the first day (final fix round) → the first `match` reports `ambiguous`, the rerun
with the answer and every Correct rerun carrying `--first-day`/`--min-days` report `given`, so the week question is
asked once, and Confirm saves the answered rule. Every write attempted through the client is under the inbox prefix,
per test and in the sweep.

The read-side edge cases of the PRD are unit-tested, not walked here: a linked Dayplanner or journal note that
is missing or cannot be read → tests/test_review_day.py::test_missing_linked_note_is_a_problem_of_that_day_and_the_day_still_read
and ::test_unreadable_linked_note_reported_the_same_way; two daily notes with the same date →
tests/test_review_period.py::test_two_dailies_for_one_date_are_both_read_and_reported_duplicate. All data is synthetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import (  # noqa: E402
    APPROVED, CONFIG, INBOX, TICKED, WEEK, WEEK_DOC, WEEK_PERIOD, WEEK_STEM, WEEKLY, WRITES, Walk,
    config_without_setup,
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


# ── the Tasks plugin appends a done marker to every ticked line ─────────────────────────


def test_approved_and_an_item_ticked_through_the_tasks_plugin_parse_preview_and_deliver_without_the_marker(ready: Walk):
    # Phase 6 live walk (container session da0eedd9): with the Obsidian Tasks plugin installed, ticking a box appends
    # ` ✅ YYYY-MM-DD` to the line, so `- [x] Approved ✅ 2026-11-12` parsed as unapproved plus one stray item
    walk = ready
    text = _approved_week(walk)
    [tomo_line] = [ln for ln in text.splitlines() if ln.endswith("%%t1%%")]
    walk.edit_document(WEEK_DOC, text.replace(APPROVED, TICKED, 1))
    untouched = walk.parse(WEEK_STEM)
    assert untouched["status"] == "ok" and untouched["approved"] is True and untouched["warnings"] == [], untouched
    marked = text.replace(f"{APPROVED}\n", f"{TICKED} ✅ 2026-11-12\n", 1)
    marked = marked.replace(f"{tomo_line}\n", f"{tomo_line} ✅ 2026-11-12\n", 1)          # the item re-ticked
    assert marked.count("✅") == 2
    walk.edit_document(WEEK_DOC, marked)
    out = walk.parse(WEEK_STEM)
    assert out["status"] == "ok" and out["approved"] is True and out["warnings"] == [], out
    assert out["counts"] == untouched["counts"] and out["items"] == untouched["items"], out
    out = walk.preview(WEEK_STEM)
    assert out["status"] == "ok" and out["problems"] == [], out
    assert "✅" not in out["section_md"] and "2026-11-12" not in out["section_md"], out["section_md"]
    out = walk.deliver(WEEK_STEM)
    assert out["status"] == "delivered", out
    # the delivered MD and JSON carry the kept text without the marker (today's date is in their stamps, not the text)
    assert "✅" not in walk.doc(f"{INBOX}{WEEK_STEM}_instructions.md")
    assert "✅" not in json.dumps(walk.set_json(WEEK_STEM), ensure_ascii=False)
    assert walk.listing() == [(WEEK_STEM, "delivered")]


# ── a bare /review while a review is listed ──────────────────────────────────────────────


def test_bare_start_with_an_open_review_carries_no_request_before_or_after_its_delivery(ready: Walk):
    """Phase 6 live walk (container session 68459faa): open 2026-W13, a bare `/review` → `start` listed W13 and
    request 2026-W45 (default); after Continue → Deliver the skill ran `review-read.py --period 2026-W45`. Now the
    bare `start` carries no request while W13 is listed, and none after the delivery either (the delivered set is
    still listed), so the skill has no period to read; a named period keeps its request beside the listing."""
    walk = ready
    text = _approved_week(walk)
    walk.edit_document(WEEK_DOC, text.replace(APPROVED, TICKED, 1))
    out = walk.start()
    assert out["status"] == "ok" and [(r["stem"], r["state"]) for r in out["open_reviews"]] == [(WEEK_STEM, "open")]
    assert out["request"] is None and out["request_withheld"] == "open-reviews", out
    assert walk.parse(WEEK_STEM)["approved"] is True                             # Continue
    assert walk.preview(WEEK_STEM)["problems"] == []
    assert walk.deliver(WEEK_STEM)["status"] == "delivered"
    out = walk.start()                                                           # the next bare /review
    assert [(r["stem"], r["state"]) for r in out["open_reviews"]] == [(WEEK_STEM, "delivered")]
    assert out["request"] is None and out["request_withheld"] == "open-reviews", out
    assert not walk.stage("2026-W45_review").exists(), "no period was read for the default week"
    out = walk.start(SPARSE_PERIOD)                                              # a named period beside the listing
    assert out["request"]["period"] == SPARSE_PERIOD and "request_withheld" not in out
    assert [r["stem"] for r in out["open_reviews"]] == [WEEK_STEM]


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


# ── journey 1 again, the owner's instance: no weekly template mapped ─────────────────────


def test_first_setup_without_a_template_mapping_asks_for_the_template_and_saves_it(tmp_path, monkeypatch, capsys,
                                                                                    request):
    """Phase 6 live walk (container session 5b959432): `templates.mapping` without `weekly`, the templates folder
    holding `t_week*.md`. The first `match` lists the candidates and marks `needs_anchor` (both questions in one
    call); the skill's answer `2` is `--template t_week_privat`; its headings propose the anchor; Confirm saves
    `templates.mapping.weekly` beside the setup, and the review reads the period."""
    config = config_without_setup()
    config["templates"] = {"base_path": "Templates/", "mapping": {"daily": "t_day.md"}}
    walk = Walk(tmp_path, monkeypatch, capsys, request.node.nodeid, config=config)
    walk.vault.files["Templates/t_week_privat.md"] = "# Weekly\n\n## Theme\n\n## In my own words\n"
    assert walk.start(WEEK_PERIOD)["setup"]["week"] == "missing"
    first = walk.match(WEEK)
    assert first["status"] == "ok" and first["template_candidates"] == ["t_week", "t_week_privat"], first
    assert first["proposal"]["template"] is None and first["proposal"]["place"]["anchor"] is None
    assert first["needs_anchor"] is True and "Review of the Week" in first["anchor_candidates"], first
    saved = walk.setup(WEEK, "--template", "t_week_privat")                       # the user typed 2
    assert saved["status"] == "written" and "templates.mapping.weekly" in saved["keys"], saved
    after = yaml.safe_load((walk.root / "config" / "vault-config.yaml").read_text(encoding="utf-8"))
    assert after["templates"] == {"base_path": "Templates/", "mapping": {"daily": "t_day.md", "weekly": "t_week_privat.md"}}
    assert after["review"]["weekly"]["place"] == {"anchor": "In my own words", "placement": "before"}
    out = walk.start(WEEK_PERIOD)
    assert out["setup"] == {"week": "present", "month": "missing"}, out
    read = walk.read(WEEK_PERIOD, WEEK)
    assert read["status"] == "ok" and read["nothing_to_review"] is False, read
    assert walk.vault.recorded == [], "the setup writes only the config file"


def test_first_setup_with_no_template_keeps_that_answer_and_the_typed_anchor_on_every_rerun(tmp_path, monkeypatch,
                                                                                            capsys, request):
    """Fix round 1 of the live-walk fix: the user types `0` (no template) and then a heading. Each later `match`
    of step 2 — the week-rule rerun, a Correct rerun — carries `--template none` and, once given, `--anchor`, so the
    templates folder is listed once, the candidates are not offered again and the heading is not asked again;
    Confirm saves the anchor and touches no mapping key, and the review then reads the period."""
    config = config_without_setup()
    config["templates"] = {"base_path": "Templates/", "mapping": {"daily": "t_day.md"}}
    walk = Walk(tmp_path, monkeypatch, capsys, request.node.nodeid, config=config)
    first = walk.match(WEEK)
    assert first["template_candidates"] == ["t_week"] and first["needs_anchor"] is True, first
    assert "Review of the Week" in first["anchor_candidates"]
    p = first["proposal"]
    rerun = walk.match(WEEK, "--folder", p["folder"], "--format", p["format"], "--first-day", "monday",
                       "--min-days", "4", "--template", "none")                     # the week-rule rerun after `0`
    assert "template_candidates" not in rerun and rerun["proposal"]["template"] is None, rerun
    assert rerun["needs_anchor"] is True and rerun["anchor_candidates"] == first["anchor_candidates"]
    corrected = walk.match(WEEK, "--folder", p["folder"], "--template", "none",
                           "--anchor", "Review of the Week")                        # a Correct after the heading
    assert corrected["proposal"]["place"]["anchor"] == "Review of the Week", corrected
    assert "needs_anchor" not in corrected and "template_candidates" not in corrected
    assert [e for e in walk.vault.events if e == ("list_dir", "Templates/")] == [("list_dir", "Templates/")], \
        "the templates folder is listed once, on the first call"
    saved = walk.setup(WEEK, "--template", "none", "--anchor", "Review of the Week")
    assert saved["status"] == "written" and not any(k.startswith("templates.") for k in saved["keys"]), saved
    after = yaml.safe_load((walk.root / "config" / "vault-config.yaml").read_text(encoding="utf-8"))
    assert after["templates"] == {"base_path": "Templates/", "mapping": {"daily": "t_day.md"}}, "no mapping key"
    assert after["review"]["weekly"]["place"] == {"anchor": "Review of the Week", "placement": "before"}
    assert walk.start(WEEK_PERIOD)["setup"]["week"] == "present"
    read = walk.read(WEEK_PERIOD, WEEK)
    assert read["status"] == "ok" and read["nothing_to_review"] is False, read
    assert walk.vault.recorded == [], "the setup writes only the config file"


def test_ambiguous_weekly_notes_ask_the_week_question_once_and_every_rerun_keeps_the_answer(tmp_path, monkeypatch,
                                                                                            capsys, request):
    """Final fix round of the live-walk fix: the weekly notes disagree on the first day (one Sunday-dated note
    among the Monday ones), so the first `match` reports `ambiguous` and the skill asks the week question. The
    rerun with the answer (`--first-day monday --min-days 4`, the template carried) reports `given` — the notes
    still disagree, but the answer stands, so nothing asks again — and so does a Correct rerun that carries the
    answer; Confirm saves the answered rule."""
    walk = Walk(tmp_path, monkeypatch, capsys, request.node.nodeid, config=config_without_setup())
    walk.vault.files[f"{WEEKLY}2026-W15.md"] = ("---\njournal-start-date: 2026-04-12\n---\n# 2026-W15\n\n"
                                                "## Review of the Week\n\n## In my own words\n")   # a Sunday
    first = walk.match(WEEK)
    assert first["status"] == "ok" and first["evidence"]["week_rule"] == "ambiguous", first
    assert "template_candidates" not in first and "needs_anchor" not in first, "the mapped template answers both"
    p = first["proposal"]
    answer = ("--folder", p["folder"], "--format", p["format"], "--first-day", "monday", "--min-days", "4",
              "--template", p["template"])
    rerun = walk.match(WEEK, *answer)                                             # the week-rule rerun
    assert rerun["evidence"]["week_rule"] == "given", rerun
    assert (rerun["proposal"]["first_day"], rerun["proposal"]["min_days"]) == ("monday", 4)
    assert "2026-W15" in rerun["evidence"]["unmatched"], "the note the answer does not fit is still shown"
    corrected = walk.match(WEEK, *answer, "--anchor", p["place"]["anchor"])      # a Correct after the answer
    assert corrected["evidence"]["week_rule"] == "given", corrected
    assert corrected["proposal"]["place"]["anchor"] == p["place"]["anchor"]
    saved = walk.setup(WEEK, *answer)
    assert saved["status"] == "written" and "review.week.first_day" in saved["keys"], saved
    after = yaml.safe_load((walk.root / "config" / "vault-config.yaml").read_text(encoding="utf-8"))
    assert after["review"]["week"] == {"first_day": "monday", "min_days_in_first_week": 4}
    assert walk.start(WEEK_PERIOD)["setup"]["week"] == "present"
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

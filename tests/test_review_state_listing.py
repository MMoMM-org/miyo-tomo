#!/usr/bin/env python3
# version: 0.1.4
"""test_review_state_listing.py — lib/review_state.open_reviews, the listing `review-session.py start` prints
(spec 045 T2.3, T4.3, P5; SDD Complex Logic review_state OUTPUT; ADR-6).

Split out of tests/test_review_state.py (Phase 6, pre-live-walk; a pure move — the helpers are imported from
there). Pinned here: one entry per review document found by frontmatter (renamed documents included), stem from
review_stem or <period>_review, classified through stem_state (the fake records the set paths asked for — a
listing that classifies without the probe fails), ordered by period start under the configured rule AND name
formats, a missing review_kind inferred by parsing the period under the configured formats, unreadable,
period-less and stem-unsafe documents skipped with a reason, withdrawn reviews and applied reviews already
reported never listed, the half-withdrawn stem listed as failed-delivery until meta says withdrawn; an open
document whose stage still holds proposals.json carries new_read true (spec 047 walk F-R3b-3), any other stage false;
a document marked `tomo.state: discarded` is never listed and costs no Kado call, an open one beside it still is
(spec 047 walk F-R5-2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_state_helpers import (  # noqa: E402
    APPROVED, INBOX, PENDING, _doc, _empty_vault, _insert, _meta, _move, _set_bytes, _vault,
)
from lib import review_state as rs  # noqa: E402
from lib.period import WeekRule  # noqa: E402


# ---------------------------------------------------------------- open_reviews

def test_open_reviews_lists_every_document_by_period_with_its_state(tmp_path):
    _meta(tmp_path, "2026-W12_review", failed_step="set_md")
    docs = [
        (INBOX + "2026-W13 Review.md", _doc("2026-W13", "week", stem="2026-W13_review")),
        (INBOX + "My renamed review.md", _doc("2026-W12", "week", APPROVED, stem="2026-W12_review")),
        (INBOX + "2026-03 Review.md", _doc("2026-03", "month", APPROVED, stem="2026-03_review")),
        (INBOX + "2026-W09 Review.md", _doc("2026-W09", "week")),           # no review_stem key
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX)
    assert skipped == []
    assert [r.to_dict() for r in reviews] == [
        {"period": "2026-W09", "kind": "week", "doc_path": INBOX + "2026-W09 Review.md",
         "stem": "2026-W09_review", "state": "open", "new_read": False},
        {"period": "2026-03", "kind": "month", "doc_path": INBOX + "2026-03 Review.md",
         "stem": "2026-03_review", "state": "failed-delivery", "new_read": False},
        {"period": "2026-W12", "kind": "week", "doc_path": INBOX + "My renamed review.md",
         "stem": "2026-W12_review", "state": "failed-delivery", "new_read": False},
        {"period": "2026-W13", "kind": "week", "doc_path": INBOX + "2026-W13 Review.md",
         "stem": "2026-W13_review", "state": "open", "new_read": False},
    ]


def test_open_reviews_probes_the_set_of_every_approved_document_and_lists_a_delivered_one(tmp_path):
    """Falsifies a listing that classifies without the probe: the approved, delivered review would
    read failed-delivery, and the fake would record no read of its set."""
    _meta(tmp_path, "2026-W12_review", steps_done=["set_json", "set_md", "doc_mark"], failed_step="")
    vault, fake = _vault({INBOX + "2026-W12_review_instructions.json": _set_bytes(_insert(target="Calendar/2026-W12.md")),
                          "Calendar/2026-W12.md": "# W12\n",
                          INBOX + "2026-W11_review_instructions.json": _set_bytes(_move(True))})
    docs = [
        (INBOX + "2026-W13 Review.md", _doc("2026-W13", "week", PENDING, stem="2026-W13_review")),
        (INBOX + "2026-W12 Review.md", _doc("2026-W12", "week", APPROVED, stem="2026-W12_review")),
        (INBOX + "2026-W11 Review.md", _doc("2026-W11", "week", APPROVED, stem="2026-W11_review")),
        (INBOX + "2026-W10 Review.md", _doc("2026-W10", "week", APPROVED, stem="2026-W10_review")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, vault, INBOX)
    assert skipped == []
    assert [(r.period, r.state) for r in reviews] == [("2026-W10", "failed-delivery"), ("2026-W11", "applied"),
                                                      ("2026-W12", "delivered"), ("2026-W13", "open")]
    set_reads = [p for m, p in fake.events if m == "read_file"]
    assert sorted(set_reads) == sorted([INBOX + "2026-W12_review_instructions.json",
                                        INBOX + "2026-W11_review_instructions.json",
                                        INBOX + "2026-W10_review_instructions.json"])
    assert INBOX + "2026-W13_review_instructions.json" not in fake.paths_seen      # pending: no probe
    assert "Calendar/2026-W12.md" in fake.paths_seen                                 # the waiting insert's target


def test_open_reviews_never_lists_a_withdrawn_review_nor_an_applied_one_already_reported(tmp_path):
    _meta(tmp_path, "2026-W12_review", steps_done=["note", "set_json"], failed_step="", withdrawn=True)
    _meta(tmp_path, "2026-W11_review", steps_done=["set_json", "set_md", "doc_mark"], applied_reported=True)
    _meta(tmp_path, "2026-W10_review", steps_done=["set_json", "set_md", "doc_mark"])
    vault, fake = _vault({INBOX + "2026-W12_review_instructions.json": _set_bytes(_move()),
                          INBOX + "2026-W11_review_instructions.json": _set_bytes(_insert(True)),
                          INBOX + "2026-W10_review_instructions.json": _set_bytes(_insert(True)),
                          INBOX + "2026-W09_review_instructions.json": _set_bytes()})
    docs = [
        (INBOX + "2026-W12 Review.md", _doc("2026-W12", "week", APPROVED, stem="2026-W12_review")),
        (INBOX + "2026-W11 Review.md", _doc("2026-W11", "week", APPROVED, stem="2026-W11_review")),
        (INBOX + "2026-W10 Review.md", _doc("2026-W10", "week", APPROVED, stem="2026-W10_review")),
        (INBOX + "2026-W09 Review.md", _doc("2026-W09", "week", APPROVED, stem="2026-W09_review")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, vault, INBOX)
    assert skipped == []
    assert [(r.period, r.state) for r in reviews] == [("2026-W10", "applied")]
    assert INBOX + "2026-W12_review_instructions.json" not in fake.paths_seen      # withdrawn meta: no probe


def test_open_reviews_lists_a_half_withdrawn_stem_as_failed_delivery_until_meta_says_withdrawn(tmp_path):
    """`drop` emptied the set but its MD write failed: the set holds nothing, the MD lists the actions,
    meta.json is not marked. The listing offers it again (Resume or Drop) instead of hiding it."""
    _meta(tmp_path, "2026-W12_review", steps_done=["note", "set_json"], failed_step="set_md", withdrawn=False)
    _meta(tmp_path, "2026-W11_review", steps_done=["note", "set_json"], failed_step="set_md", withdrawn=True)
    vault, fake = _vault({INBOX + "2026-W12_review_instructions.json": _set_bytes(),
                          INBOX + "2026-W11_review_instructions.json": _set_bytes()})
    docs = [
        (INBOX + "2026-W12 Review.md", _doc("2026-W12", "week", APPROVED, stem="2026-W12_review")),
        (INBOX + "2026-W11 Review.md", _doc("2026-W11", "week", APPROVED, stem="2026-W11_review")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, vault, INBOX)
    assert skipped == []
    assert [(r.period, r.state) for r in reviews] == [("2026-W12", "failed-delivery")]
    assert [p for m, p in fake.events if m == "read_file"] == [INBOX + "2026-W12_review_instructions.json"]


def test_open_reviews_skips_an_unsafe_stem_never_classifying_it_as_meta_absent(tmp_path):
    (tmp_path / "meta.json").write_text(json.dumps({"failed_step": "x"}), encoding="utf-8")
    vault, fake = _vault({})
    docs = [
        (INBOX + "a.md", _doc("2026-W13", "week", stem="../x")),
        (INBOX + "b.md", _doc("2026-W12", "week", APPROVED, stem="..")),
        (INBOX + "c.md", _doc("2026/W11", "week")),                              # no stem key: period unsafe
        (INBOX + "d.md", _doc("2026-W10", "week", stem="2026-W10_review")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, vault, INBOX)
    assert [r.stem for r in reviews] == ["2026-W10_review"]
    assert skipped == [{"doc_path": INBOX + "a.md", "reason": "stem-unsafe"},
                       {"doc_path": INBOX + "b.md", "reason": "stem-unsafe"},
                       {"doc_path": INBOX + "c.md", "reason": "stem-unsafe"}]
    assert fake.events == []                                                     # nothing probed for them


def test_open_reviews_orders_by_the_configured_rule_and_formats_and_keeps_unparsable_last(tmp_path):
    # 2027-W01 under gggg-[W]ww + (Sunday, 1) starts 2026-12-27, before the month 2027-01
    # (2027-01-01); under the default GGGG-[W]WW the ISO rule applies whatever the rule
    # says and 2027-W01 starts 2027-01-04, after it — so the two orders differ.
    sunday = WeekRule(6, 1)
    docs = [
        (INBOX + "a.md", _doc("2027-W01", "week")),
        (INBOX + "b.md", _doc("2027-01", "month")),
        (INBOX + "c.md", _doc("2026-12", "month")),
        (INBOX + "d.md", _doc("not-a-period", "week")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX, rule=sunday,
                                       formats={"week": "gggg-[W]ww"})
    assert [r.period for r in reviews] == ["2026-12", "2027-W01", "2027-01", "not-a-period"]
    assert skipped == []
    reviews, _ = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX)        # the defaults: ISO
    assert [r.period for r in reviews] == ["2026-12", "2027-01", "2027-W01", "not-a-period"]


def test_open_reviews_infers_a_missing_kind_by_parsing_under_the_configured_formats(tmp_path):
    sunday = WeekRule(6, 1)
    week_without_w = _doc("2027.01", "week")
    del week_without_w["review_kind"]
    month = _doc("2027-01", "month")
    del month["review_kind"]
    docs = [(INBOX + "a.md", week_without_w), (INBOX + "b.md", month), (INBOX + "c.md", _doc("2026-12", "month"))]
    reviews, _ = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX, rule=sunday, formats={"week": "gggg.ww"})
    assert [(r.period, r.kind) for r in reviews] == [("2026-12", "month"), ("2027.01", "week"), ("2027-01", "month")]
    reviews, _ = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX)        # no W, no format: the letter guess
    assert [(r.period, r.kind) for r in reviews] == [("2026-12", "month"), ("2027-01", "month"), ("2027.01", "month")]


def test_open_reviews_skips_unreadable_and_period_less_documents(tmp_path):
    docs = [
        (INBOX + "broken.md", None),
        (INBOX + "no period.md", {"tomo": {"doc_type": "review", "state": "pending-approval"}}),
        (INBOX + "2026-W13 Review.md", _doc("2026-W13", "week")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX)
    assert [r.period for r in reviews] == ["2026-W13"]
    assert skipped == [{"doc_path": INBOX + "broken.md", "reason": "frontmatter-unreadable"},
                       {"doc_path": INBOX + "no period.md", "reason": "period-missing"}]


# ---------------------------------------------------------------- the staged new read (spec 047 F-R3b-3)

def test_an_open_document_whose_stage_holds_proposals_carries_new_read(tmp_path):
    """Falsifies a listing that never looks at the stage, and one that reads any stage file as a new read:
    the stage of W13 holds proposals.json (a Pass 1 whose write stopped), the stage of W12 only meta.json."""
    stage = tmp_path / "2026-W13_review"
    stage.mkdir()
    (stage / "proposals.json").write_text("{}", encoding="utf-8")
    _meta(tmp_path, "2026-W12_review", steps_done=[], failed_step="")
    docs = [(INBOX + "2026-W13 Review.md", _doc("2026-W13", "week", stem="2026-W13_review")),
            (INBOX + "2026-W12 Review.md", _doc("2026-W12", "week", stem="2026-W12_review"))]
    reviews, skipped = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX)
    assert skipped == []
    assert [(r.period, r.state, r.new_read) for r in reviews] == [("2026-W12", "open", False),
                                                                   ("2026-W13", "open", True)]
    assert reviews[1].to_dict()["new_read"] is True and reviews[0].to_dict()["new_read"] is False



# ---------------------------------------------------------------- a discarded review (spec 047 F-R5-2)

def test_a_discarded_document_is_never_listed_and_an_open_one_still_is(tmp_path):
    """Falsifies a listing that ignores the discard mark: W13 is marked `discarded` (the listing would classify it
    `open`), W12 is open. The discarded stem costs no probe."""
    _meta(tmp_path, "2026-W13_review", steps_done=[], failed_step="")
    vault, fake = _vault({})
    docs = [(INBOX + "2026-W13 Review.md", _doc("2026-W13", "week", "discarded", stem="2026-W13_review")),
            (INBOX + "2026-W12 Review.md", _doc("2026-W12", "week", stem="2026-W12_review"))]
    reviews, skipped = rs.open_reviews(docs, tmp_path, vault, INBOX)
    assert skipped == []
    assert [(r.period, r.state) for r in reviews] == [("2026-W12", "open")]
    assert fake.events == []
    assert getattr(rs, "DOC_STATE_DISCARDED", None) == "discarded"


# ---------------------------------------------------------------- the quarter (spec 046 T1.4)

def test_a_quarter_period_is_inferred_as_quarter():
    assert rs._infer_kind("2026-Q1", WeekRule(), dict(rs.DEFAULT_FORMATS)) == "quarter"
    assert rs._infer_kind("2026-W13", WeekRule(), dict(rs.DEFAULT_FORMATS)) == "week"
    assert rs._infer_kind("2026-03", WeekRule(), dict(rs.DEFAULT_FORMATS)) == "month"


def test_a_quarter_name_no_format_parses_keeps_the_letter_guess():
    formats = dict(rs.DEFAULT_FORMATS, quarter="[Q]Q YYYY")
    assert rs._infer_kind("2026-Q1", WeekRule(), formats) == "quarter"
    assert rs._infer_kind("2026-W54", WeekRule(), formats) == "week"


def test_open_reviews_lists_a_quarter_by_its_start_and_infers_its_kind(tmp_path):
    quarter = _doc("2026-Q1", "quarter")
    del quarter["review_kind"]
    docs = [(INBOX + "m.md", _doc("2026-02", "month")), (INBOX + "q.md", quarter),
            (INBOX + "w.md", _doc("2025-W52", "week"))]
    reviews, skipped = rs.open_reviews(docs, tmp_path, _empty_vault(), INBOX)
    assert skipped == []
    assert [(r.period, r.kind, r.stem) for r in reviews] == [
        ("2025-W52", "week", "2025-W52_review"), ("2026-Q1", "quarter", "2026-Q1_review"),
        ("2026-02", "month", "2026-02_review")]

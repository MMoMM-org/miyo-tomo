#!/usr/bin/env python3
# version: 0.1.0
"""test_review_state.py — lib/review_state.py, the one owner of /review's
open-review states (spec 045 T2.3; SDD Complex Logic review_state).

- STATES is the canonical six-state list in the SDD's order
- review_state: meta.failed_step → failed-delivery; approved without a set
  JSON → failed-delivery; pending-approval without a set → open; a set JSON
  handed in raises StateNotClassified (steps 3–7 arrive in T4.3); a missing
  or corrupt meta counts as absent
- read_meta: the content-free meta.json of a stem, None when missing or broken
- open_reviews: one entry per review document found by frontmatter (renamed
  documents included), stem from review_stem or <period>_review, ordered by
  period start under the rule, unreadable or period-less documents skipped
  with a reason
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))

from lib import review_state as rs  # noqa: E402
from lib.period import WeekRule  # noqa: E402

INBOX = "100 Inbox/"


def _doc(period: str, kind: str, state: str = "pending-approval", stem: str | None = None) -> dict:
    fm = {"tomo": {"doc_type": "review", "state": state, "run_id": "r1", "updated_at": "2026-11-11T10:00:00"},
          "review_period": period, "review_kind": kind, "review_target": f"Calendar/{period}.md",
          "review_target_exists": True, "review_language": "de"}
    if stem is not None:
        fm["review_stem"] = stem
    return fm


def _meta(root: Path, stem: str, **fields) -> None:
    stage = root / stem
    stage.mkdir(parents=True)
    (stage / "meta.json").write_text(json.dumps({"stem": stem, **fields}), encoding="utf-8")


# ---------------------------------------------------------------- the canonical list

def test_states_are_the_sdd_list_in_order():
    assert rs.STATES == ("open", "failed-delivery", "delivered", "applied", "move-refused", "target-missing")
    assert rs.OPEN == "open" and rs.FAILED_DELIVERY == "failed-delivery"


# ---------------------------------------------------------------- review_state

def test_failed_step_in_meta_is_failed_delivery():
    assert rs.review_state(_doc("2026-W13", "week"), {"failed_step": "set_md"}) == "failed-delivery"
    assert rs.review_state(_doc("2026-W13", "week", "approved"), {"failed_step": "note"}) == "failed-delivery"


def test_approved_without_a_set_json_is_failed_delivery():
    assert rs.review_state(_doc("2026-W13", "week", "approved"), None) == "failed-delivery"
    assert rs.review_state(_doc("2026-W13", "week", "approved"), {"steps_done": []}) == "failed-delivery"


def test_pending_approval_without_a_set_json_is_open():
    assert rs.review_state(_doc("2026-W13", "week"), None) == "open"
    assert rs.review_state(_doc("2026-W13", "week"), {"steps_done": [], "failed_step": None}) == "open"
    assert rs.review_state({"review_period": "2026-03"}, None) == "open"      # no tomo block at all


def test_a_set_json_is_not_classified_before_t4_3():
    with pytest.raises(rs.StateNotClassified):
        rs.review_state(_doc("2026-W13", "week", "approved"), {"steps_done": ["note", "set_json"]},
                        {"actions": []})
    with pytest.raises(rs.StateNotClassified):
        rs.review_state(_doc("2026-W13", "week"), None, {"actions": [{"applied": True}]},
                        target_exists=True, inbox_copy_exists=False)


def test_failed_step_wins_over_a_set_json():
    assert rs.review_state(_doc("2026-W13", "week", "approved"), {"failed_step": "doc_mark"},
                           {"actions": []}) == "failed-delivery"


# ---------------------------------------------------------------- read_meta

def test_read_meta_returns_the_meta_or_none(tmp_path):
    _meta(tmp_path, "2026-W13_review", failed_step="set_md", steps_done=["note"])
    assert rs.read_meta(tmp_path, "2026-W13_review") == {"stem": "2026-W13_review", "failed_step": "set_md",
                                                         "steps_done": ["note"]}
    assert rs.read_meta(tmp_path, "2026-W12_review") is None
    (tmp_path / "2026-W11_review").mkdir()
    (tmp_path / "2026-W11_review" / "meta.json").write_text("{not json", encoding="utf-8")
    assert rs.read_meta(tmp_path, "2026-W11_review") is None
    (tmp_path / "2026-W10_review").mkdir()
    (tmp_path / "2026-W10_review" / "meta.json").write_text("[1, 2]", encoding="utf-8")
    assert rs.read_meta(tmp_path, "2026-W10_review") is None


def test_read_meta_refuses_a_stem_that_leaves_the_root(tmp_path):
    assert rs.read_meta(tmp_path, "../etc") is None
    assert rs.read_meta(tmp_path, "a/b") is None
    assert rs.read_meta(tmp_path, "") is None


# ---------------------------------------------------------------- open_reviews

def test_open_reviews_lists_every_document_by_period_with_its_state(tmp_path):
    _meta(tmp_path, "2026-W12_review", failed_step="set_md")
    docs = [
        (INBOX + "2026-W13 Review.md", _doc("2026-W13", "week", stem="2026-W13_review")),
        (INBOX + "My renamed review.md", _doc("2026-W12", "week", "approved", stem="2026-W12_review")),
        (INBOX + "2026-03 Review.md", _doc("2026-03", "month", "approved", stem="2026-03_review")),
        (INBOX + "2026-W09 Review.md", _doc("2026-W09", "week")),           # no review_stem key
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path)
    assert skipped == []
    assert [r.to_dict() for r in reviews] == [
        {"period": "2026-W09", "kind": "week", "doc_path": INBOX + "2026-W09 Review.md",
         "stem": "2026-W09_review", "state": "open"},
        {"period": "2026-03", "kind": "month", "doc_path": INBOX + "2026-03 Review.md",
         "stem": "2026-03_review", "state": "failed-delivery"},
        {"period": "2026-W12", "kind": "week", "doc_path": INBOX + "My renamed review.md",
         "stem": "2026-W12_review", "state": "failed-delivery"},
        {"period": "2026-W13", "kind": "week", "doc_path": INBOX + "2026-W13 Review.md",
         "stem": "2026-W13_review", "state": "open"},
    ]


def test_open_reviews_orders_by_the_rule_and_keeps_unparsable_last(tmp_path):
    sunday = WeekRule(6, 1)
    docs = [
        (INBOX + "a.md", _doc("2027-W01", "week")),      # (Sun, 1): starts 2026-12-27
        (INBOX + "b.md", _doc("2026-12", "month")),      # starts 2026-12-01
        (INBOX + "c.md", _doc("not-a-period", "week")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, rule=sunday)
    assert [r.period for r in reviews] == ["2026-12", "2027-W01", "not-a-period"]
    assert skipped == []


def test_open_reviews_skips_unreadable_and_period_less_documents(tmp_path):
    docs = [
        (INBOX + "broken.md", None),
        (INBOX + "no period.md", {"tomo": {"doc_type": "review", "state": "pending-approval"}}),
        (INBOX + "2026-W13 Review.md", _doc("2026-W13", "week")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path)
    assert [r.period for r in reviews] == ["2026-W13"]
    assert skipped == [{"doc_path": INBOX + "broken.md", "reason": "frontmatter-unreadable"},
                       {"doc_path": INBOX + "no period.md", "reason": "period-missing"}]

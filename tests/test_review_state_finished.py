#!/usr/bin/env python3
# version: 0.1.0
"""test_review_state_finished.py — a completed delivery whose set the user deleted is finished, not failed
(spec 045 Phase 6, pre-live-walk fix; owner decision 2026-11-12; SDD Complex Logic stem_state step 3b).

A delivery that reached `doc_mark` wrote the set JSON and marked the document `approved`; Hashi applied it and
the user deleted the set JSON (and its MD) from the inbox by hand. The document still says `approved`, the set
is gone: until this fix `review_state` read that as "an approved document without a set" → `failed-delivery`
on every /review, and Resume → `deliver` refused `set-exists` (`second_set` is True on `doc_mark`), so the
skill said a set waits for Hashi although none was there. The rule now:

- approved document, no set JSON, meta records `doc_mark` in steps_done → None (finished, not listed —
  like `applied_reported` and withdrawn); `stem_state` still spends the one set read to learn the set is gone
- approved document, no set JSON, a begun delivery without `doc_mark` → `failed-delivery` (resumable: the
  loop writes the missing steps; `second_set` is False with no set at the path)
- approved document, no set JSON, meta None or never begun → `failed-delivery` unchanged (the record of the
  delivery is lost or the stage was never used: resume or drop is the honest offer)
- the neighbours are unchanged: a withdrawn meta is None whatever else; the half-withdrawn emptied set on a
  begun stem is `failed-delivery`; a fresh record over a fully applied set is `open`; a pending document
  with a complete record costs no read and is `open` as before
- `open_reviews` omits the finished stem while still listing the resumable one
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_review_state import (  # noqa: E402
    APPROVED, INBOX, PENDING, SET, STEM, _doc, _insert, _meta, _move, _probes, _set, _set_bytes, _vault,
)
from lib import review_state as rs  # noqa: E402

COMPLETE = {"steps_done": ["note", "set_json", "set_md", "doc_mark"], "failed_step": ""}
BEGUN = {"steps_done": ["note", "set_json", "set_md"], "failed_step": "doc_mark"}


def test_a_complete_delivery_whose_set_is_gone_is_finished_not_failed():
    """RED before the fix: the approved-without-a-set clause read it as failed-delivery."""
    doc = _doc("2026-W13", "week", APPROVED)
    assert rs.review_state(doc, COMPLETE, None) is None
    assert rs.review_state(doc, {"steps_done": ["set_json", "set_md", "doc_mark"]}, None) is None
    assert rs.review_state(doc, dict(COMPLETE, applied_reported=True), None) is None
    # stem_state reads the set once (the document is approved) and learns it is gone
    vault, fake = _vault({})
    assert rs.stem_state(vault, doc, COMPLETE, STEM, INBOX) is None
    assert _probes(fake) == [("read_file", SET)]


def test_a_begun_delivery_without_doc_mark_whose_set_is_gone_stays_failed_delivery():
    """The guard: only a delivery that reached doc_mark counts as finished; everything short of it resumes."""
    doc = _doc("2026-W13", "week", APPROVED)
    assert rs.review_state(doc, BEGUN, None) == "failed-delivery"
    assert rs.review_state(doc, {"steps_done": ["note", "set_json"], "failed_step": ""}, None) == "failed-delivery"
    assert rs.review_state(doc, {"steps_done": [], "failed_step": "set_json"}, None) == "failed-delivery"
    # no record at all, or one that never began: unchanged, failed-delivery (resume or drop)
    assert rs.review_state(doc, None, None) == "failed-delivery"
    assert rs.review_state(doc, {}, None) == "failed-delivery"
    assert rs.review_state(doc, {"steps_done": [], "failed_step": ""}, None) == "failed-delivery"
    vault, fake = _vault({})
    assert rs.stem_state(vault, doc, BEGUN, STEM, INBOX) == "failed-delivery"
    assert _probes(fake) == [("read_file", SET)]


def test_the_finished_rule_needs_the_approved_document_and_the_absent_set():
    """Its neighbours keep their readings: withdrawn, the half-withdrawn emptied set, the fresh record over an
    applied set, a complete record beside a present set, and a pending document with a complete record."""
    doc = _doc("2026-W13", "week", APPROVED)
    assert rs.review_state(doc, dict(COMPLETE, withdrawn=True), None) is None
    assert rs.review_state(doc, COMPLETE, _set()) == "failed-delivery"           # the emptied set, meta unmarked
    assert rs.review_state(doc, {"steps_done": [], "failed_step": ""}, _set(_move(True))) == "open"
    assert rs.review_state(doc, COMPLETE, _set(_move(True))) == "applied"
    assert rs.review_state(doc, COMPLETE, _set(_insert()), target_exists=True) == "delivered"
    assert rs.review_state(doc, COMPLETE, {"actions": "nope"}) == "delivered"
    # a pending document with a complete record: no set read, open as before
    pending = _doc("2026-W13", "week", PENDING)
    assert rs.review_state(pending, COMPLETE, None) == "open"
    vault, fake = _vault({})
    assert rs.stem_state(vault, pending, COMPLETE, STEM, INBOX) == "open"
    assert _probes(fake) == []


def test_open_reviews_omits_the_finished_stem_and_still_lists_the_resumable_one(tmp_path):
    _meta(tmp_path, "2026-W12_review", **COMPLETE)                               # the set deleted after applying
    _meta(tmp_path, "2026-W11_review", **BEGUN)                                  # died at the mark, the set gone
    _meta(tmp_path, "2026-W09_review", **COMPLETE)                               # complete, the set still there
    vault, fake = _vault({INBOX + "2026-W09_review_instructions.json": _set_bytes(_move(True))})
    docs = [
        (INBOX + "2026-W12 Review.md", _doc("2026-W12", "week", APPROVED, stem="2026-W12_review")),
        (INBOX + "2026-W11 Review.md", _doc("2026-W11", "week", APPROVED, stem="2026-W11_review")),
        (INBOX + "2026-W10 Review.md", _doc("2026-W10", "week", APPROVED, stem="2026-W10_review")),   # no meta
        (INBOX + "2026-W09 Review.md", _doc("2026-W09", "week", APPROVED, stem="2026-W09_review")),
    ]
    reviews, skipped = rs.open_reviews(docs, tmp_path, vault, INBOX)
    assert skipped == []
    assert [(r.period, r.state) for r in reviews] == [("2026-W09", "applied"), ("2026-W10", "failed-delivery"),
                                                      ("2026-W11", "failed-delivery")]
    set_reads = sorted(p for m, p in fake.events if m == "read_file")
    assert set_reads == sorted(INBOX + f"{p}_review_instructions.json" for p in ("2026-W09", "2026-W10",
                                                                                 "2026-W11", "2026-W12"))

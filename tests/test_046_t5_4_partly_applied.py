#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t5_4_partly_applied.py — a partly applied set and the section action kinds in review_state (046 T5.4).

SDD ADR-12 ("a set with any applied action can be overwritten by a new delivery, so a partly applied set is never
stuck"), Glossary "Partly applied set", Error Handling row "Set partly applied (one section failed at Hashi)";
docs/tomo/scripts/lib/review_state.md "WHY a Partly Applied Set Reads `open`". Mechanisms pinned:

- `partly_applied`: some actions carry `applied: true`, not all; never for an unreadable or emptied set;
- step 6a: a complete delivery whose set holds I01 applied and I02 not (Hashi failed it) reads `open`, not
  `delivered`, whatever the probes say; `stem_state` (what `start` and `status` print) returns `open` after the
  one set read, without a probe; `open_reviews` lists the stem `open`;
- a begun delivery without `doc_mark` over a partly applied set stays `failed-delivery` (step 3 first);
- `SECTION_ACTIONS` holds `replace_between_markers`: an unapplied section replace whose target is gone reads
  `target-missing`, and `stem_state` probes its `target_path`.

All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from review_state_helpers import (  # noqa: E402
    APPROVED, INBOX, SET, STEM, TARGET, _doc, _insert, _meta, _probes, _set, _set_bytes, _vault,
)
from lib import review_state as rs  # noqa: E402

COMPLETE = {"steps_done": ["set_json", "set_md", "doc_mark"], "failed_step": ""}
DOC = _doc("2026-W13", "week", APPROVED)


def _between(applied: bool = False, action_id: str = "I01") -> dict:
    return {"id": action_id, "action": "replace_between_markers", "target_path": TARGET,
            "start_marker": "%% tomo:s1 2026-W13 %%", "end_marker": "%% /tomo:s1 2026-W13 %%",
            "content": "- x", "applied": applied}


def _tomo_review(applied: bool = False) -> dict:
    return dict(_insert(applied), id="I02")


PARTLY = (_between(True), _tomo_review(False))      # I01 applied, I02 failed at Hashi (left unflagged)


def test_section_actions_hold_the_new_kind():
    assert rs.SECTION_ACTIONS == ("insert_under_marker", "replace_section", "replace_between_markers")


def test_partly_applied_is_some_applied_not_all():
    assert rs.partly_applied(_set(*PARTLY)) is True
    assert rs.partly_applied(_set(_between(False), _tomo_review(True))) is True
    for not_partly in (None, {}, _set(), {"actions": ["nope"]}, _set(_between(True), _tomo_review(True)),
                       _set(_between(False), _tomo_review(False)), _set(dict(_between(), applied="yes"))):
        assert rs.partly_applied(not_partly) is False, not_partly


def test_a_complete_delivery_with_one_failed_section_reads_open_not_delivered():
    for target_exists in (None, True, False):
        assert rs.review_state(DOC, COMPLETE, _set(*PARTLY), target_exists=target_exists) == "open"
    assert rs.review_state(DOC, None, _set(*PARTLY)) == "open"                      # a cleaned stage too
    assert rs.review_state(DOC, COMPLETE, _set(_between(False), _tomo_review(False)),
                           target_exists=True) == "delivered"                      # none applied: it waits
    assert rs.review_state(DOC, COMPLETE, _set(_between(True), _tomo_review(True))) == "applied"


def test_a_begun_delivery_over_a_partly_applied_set_stays_failed_delivery():
    assert rs.review_state(DOC, {"steps_done": ["set_json"], "failed_step": "set_md"}, _set(*PARTLY)) == \
        "failed-delivery"


def test_stem_state_reads_open_after_the_set_read_without_a_probe():
    vault, fake = _vault({SET: _set_bytes(*PARTLY), TARGET: "# target\n"})
    assert rs.stem_state(vault, DOC, COMPLETE, STEM, INBOX) == "open"
    assert _probes(fake) == [("read_file", SET)]


def test_start_lists_a_partly_applied_review_as_open(tmp_path):
    _meta(tmp_path, STEM, **COMPLETE)
    vault, _ = _vault({SET: _set_bytes(*PARTLY), TARGET: "# target\n"})
    reviews, skipped = rs.open_reviews([("Reviews/2026-W13 Review.md", DOC)], tmp_path, vault, INBOX)
    assert skipped == [] and [(r.stem, r.state) for r in reviews] == [(STEM, "open")]


def test_an_unapplied_section_replace_whose_target_is_gone_is_target_missing():
    assert rs.review_state(DOC, COMPLETE, _set(_between(False)), target_exists=False) == "target-missing"
    vault, fake = _vault({SET: _set_bytes(_between(False))})
    assert rs.stem_state(vault, DOC, COMPLETE, STEM, INBOX) == "target-missing"
    assert _probes(fake) == [("read_file", SET), ("read_frontmatter", TARGET)]

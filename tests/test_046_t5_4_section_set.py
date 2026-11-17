#!/usr/bin/env python3
# version: 0.1.2
"""test_046_t5_4_section_set.py — composing the instruction set of a mapped delivery (046 T5.4).

PRD F4-AC1; SDD ADR-12 ("ids I01…In in a fixed order: sections in mapping order, then Tomo Review"),
Integration Points data_flow, the Hashi kind order. The approved review is built as production builds it
(tests/test_046_t5_2_new_note_sections.approved). Mechanisms pinned:

- an existing note gets one action per section that lands as its own block (`insert_under_marker` or
  `replace_between_markers`), in mapping order, then the "Tomo Review" action; ids dense `I01…In`: a stopped,
  skipped, routed or empty section takes no id;
- the order follows the rows only: the items dict order and the choices dict order change no byte of the set;
- the section actions are composed also when "Tomo Review" emits nothing (`review-section-kept`, no content for
  a new one), and never when its part is refused (a plan problem: the set stays empty);
- an existing note's INSERT and REPLACE blocks count their escapes in `escaped_lines`, once, also when the
  sections are planned twice (a new "Tomo Review" re-plans with `review_at`);
- a new note stays one `move_note`; an empty section gets no marker pair spliced into it (`lands` is shared
  with `compose`), so a re-run finds no block for it and plans a first insert;
- every composed set validates against Tomo's schemas (the committed v4 schemas since T6.1).

All data is synthetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib import review_actions as ra  # noqa: E402
from lib import review_section_plan as rsp  # noqa: E402
from review_deliver_helpers import SCHEMAS, schema_errors  # noqa: E402
from test_046_t5_2_new_note_sections import (  # noqa: E402
    EXISTING, ITEMS, ROWS, approved, mapped, modes, plan, row,
)
from test_review_instructions import GENERATED, HEADING, MARKER, OWN, PERIOD, TARGET  # noqa: E402

ESCAPING = "quote %% tomo:s4 2026-W13 %% here"
WITH_GONE = EXISTING.replace("## Plans\n", "## Gone\ngone text\n\n## Plans\n")


def kinds(p: ra.ReviewPlan) -> list:
    return [(a["id"], a["action"], a.get("start_marker") or a.get("anchor", {}).get("value")) for a in p.actions]


def wire(p: ra.ReviewPlan) -> str:
    doc = ra.build_review_instruction_set(p, stem=f"{PERIOD}_review", generated=GENERATED, profile="miyo")
    return json.dumps(doc, ensure_ascii=False, sort_keys=False)


def assert_valid(p: ra.ReviewPlan) -> None:
    doc = json.loads(wire(p))
    for schema in SCHEMAS:
        assert schema_errors(doc, schema) == [], schema.name


def start(key):
    return rsp.start_marker(key, PERIOD)


# ---------------------------------------------------------------- ids and order

def test_sections_in_mapping_order_then_tomo_review_with_dense_ids():
    p = plan(target_text=EXISTING)
    assert p.problems == [] and modes(p) == {"s1": "insert", "s3": "missing", "s4": "insert"}
    assert kinds(p) == [("I01", "insert_under_marker", "Highlights"), ("I02", "insert_under_marker", "Plans"),
                        ("I03", "insert_under_marker", OWN)]                 # s3 stopped: no id, no gap
    s1, s4, tr = p.actions
    assert s1["placement"] == "inside" and s1["content"].startswith(start("s1") + "\n")
    assert s4["placement"] == "before" and s4["content"].endswith(rsp.end_marker("s4", PERIOD) + "\n")
    assert tr["content"].startswith(f"## {HEADING}\n{MARKER}\n")
    assert_valid(p)


def test_a_section_that_lands_takes_its_mapping_position():
    p = plan(target_text=WITH_GONE)
    assert modes(p) == {"s1": "insert", "s3": "insert", "s4": "insert"}
    assert [(i, v) for i, _, v in kinds(p)] == [("I01", "Highlights"), ("I02", "Gone"), ("I03", "Plans"),
                                                ("I04", OWN)]
    assert_valid(p)


@pytest.mark.parametrize("choices, landed", [
    ({"s3": "skip"}, ["Highlights", "Plans", OWN]),
    ({"s3": "review"}, ["Highlights", "Plans", OWN]),
], ids=["skip", "review"])
def test_a_skipped_or_routed_section_takes_no_id(choices, landed):
    p = plan(target_text=EXISTING, choices=choices)
    assert [v for _, _, v in kinds(p)] == landed and [i for i, _, _ in kinds(p)] == ["I01", "I02", "I03"]


def test_an_empty_section_emits_no_action():
    p = plan(review=approved(ROWS, {**ITEMS, "s1": []}), target_text=EXISTING)
    assert [(i, v) for i, _, v in kinds(p)] == [("I01", "Plans"), ("I02", OWN)]
    note = plan().note_text.split("---\n", 2)[2]
    again = plan(review=approved(ROWS, {**ITEMS, "s1": []}), target_text=note)
    assert modes(again)["s1"] == "replace"                          # the earlier block stays as it is
    assert [a.get("start_marker") for a in again.actions[:-1]] == [start("s4")]


def test_two_runs_with_shuffled_items_and_choices_are_byte_identical():
    review = approved()
    keys = {r["id"] for r in ROWS}
    groups = [(k, v) for k, v in review["groups"].items() if k not in keys]       # spec 045's: document order
    sections = [(k, v) for k, v in review["groups"].items() if k in keys]
    shuffled = {**review, "groups": dict(list(reversed(sections)) + groups)}
    assert list(shuffled["groups"]) != list(review["groups"]) and len(sections) == 4
    one = plan(review=review, target_text=EXISTING, choices={"s3": "review", "s4": "skip"})
    two = plan(review=shuffled, target_text=EXISTING, choices={"s4": "skip", "s3": "review"})
    assert wire(one) == wire(two)
    assert [v for _, _, v in kinds(one)] == ["Highlights", "Plans", OWN]     # skip answers no stop of s4's
    assert "### Gone\n- Verloren" in one.actions[-1]["content"]


def test_a_rerun_replaces_each_block_between_its_markers_then_tomo_review():
    note = plan().note_text.split("---\n", 2)[2]          # the new note as it lands, without its stamp
    again = plan(target_text=note)
    assert again.mode == "replace" and again.problems == [], again.problems
    assert kinds(again) == [("I01", "replace_between_markers", start("s1")),
                            ("I02", "replace_between_markers", start("s4")), ("I03", "replace_section", HEADING)]
    s1, s4, _ = again.actions
    assert s1["end_marker"] == rsp.end_marker("s1", PERIOD) and s1["scope"] == {"heading": "Highlights", "level": 2}
    assert "scope" not in s4 and s4["content"] == "- Plan A ([[2026-03-24]])"
    assert_valid(again)


# ---------------------------------------------------------------- Tomo Review emits nothing, or is refused

def test_the_sections_land_also_when_an_earlier_tomo_review_is_kept():
    rows = [row("s1", "Highlights", "end")]
    note = EXISTING.replace(f"## {OWN}\n", f"## {HEADING}\n{MARKER}\n- alt\n\n## {OWN}\n")
    p = plan(review=approved(rows, {"s1": ["neu"]}, groups={}, habits=False), target_text=note, rows=rows)
    assert p.notices == ["review-section-kept"] and p.problems == []
    assert kinds(p) == [("I01", "insert_under_marker", "Highlights")]
    assert_valid(p)


def test_the_sections_land_also_when_nothing_is_left_for_a_new_tomo_review():
    rows = [row("s4", "Plans", "before")]
    p = plan(review=approved(rows, {"s4": ["Plan A"]}, groups={}, habits=False), target_text=EXISTING, rows=rows,
             setup=mapped(rows, anchor="Plans", placement="before"))
    assert p.problems == [] and kinds(p) == [("I01", "insert_under_marker", "Plans")]


def test_a_refused_tomo_review_part_leaves_the_set_empty():
    note = EXISTING.replace("## Plans\n", f"## {HEADING}\nfremd\n\n## Plans\n")   # the user's own heading of that name
    p = plan(target_text=note)
    assert p.problems == ["user-heading-collision"] and modes(p)["s1"] == "insert"
    assert p.actions == []


# ---------------------------------------------------------------- escapes of the landed blocks

def test_an_existing_notes_insert_block_counts_its_escape_once():
    rows = [row("s1", "Highlights", "end")]
    review = approved(rows, {"s1": ["x"]})
    review["groups"]["s1"][0]["text"] = ESCAPING                    # set on the record directly
    p = plan(review=review, target_text=EXISTING, rows=rows)        # a new Tomo Review: planned twice
    [s1] = p.sections
    assert s1.mode == "insert" and s1.escaped_lines == 1
    assert "- quote %% tomo\\:s4 2026-W13 %% here" in p.actions[0]["content"]
    assert p.escaped_lines == 1 and p.preview()["escaped_lines"] == 1


def test_an_existing_notes_replace_block_counts_its_escape_once():
    rows = [row("s1", "Highlights", "end")]
    review = approved(rows, {"s1": ["x"]})
    review["groups"]["s1"][0]["text"] = ESCAPING
    note = plan(review=approved(rows, {"s1": ["alt"]}), rows=rows).note_text.split("---\n", 2)[2]
    p = plan(review=review, target_text=note, rows=rows)
    assert modes(p) == {"s1": "replace"} and p.actions[0]["action"] == "replace_between_markers"
    assert p.actions[0]["content"] == "- quote %% tomo\\:s4 2026-W13 %% here"
    assert p.escaped_lines == 1


def test_a_stopped_sections_escape_is_not_counted():
    rows = [row("s3", "Gone", "under")]
    review = approved(rows, {"s3": ["x"]})
    review["groups"]["s3"][0]["text"] = ESCAPING
    p = plan(review=review, target_text=EXISTING, rows=rows)
    assert modes(p) == {"s3": "missing"} and p.escaped_lines == 0


# ---------------------------------------------------------------- a new note

def test_a_new_note_stays_one_move_note():
    p = plan()
    assert [(a["id"], a["action"]) for a in p.actions] == [("I01", "move_note")]
    assert p.actions[0]["destination"] == TARGET


def test_a_new_notes_empty_section_gets_no_marker_pair():
    empty = approved(ROWS, {**ITEMS, "s1": []})
    p = plan(review=empty)
    assert modes(p)["s1"] == "insert"
    lines = p.note_text.split("\n")
    assert not any(rsp.start_marker("s1", PERIOD) in x or rsp.end_marker("s1", PERIOD) in x for x in lines)
    assert rsp.start_marker("s4", PERIOD) in lines and rsp.end_marker("s4", PERIOD) in lines   # s4 still spliced
    assert p.escaped_lines == 0
    note = p.note_text.split("---\n", 2)[2]
    still = plan(review=empty, target_text=note)
    assert modes(still)["s1"] == "insert" and start("s1") not in [a.get("start_marker") for a in still.actions]
    assert [v for _, _, v in kinds(still)] == [start("s4"), HEADING]   # s1 empty: nothing for it
    filled = plan(target_text=note)
    assert modes(filled)["s1"] == "insert"                              # no block found: a first delivery
    assert kinds(filled)[0] == ("I01", "insert_under_marker", "Highlights")

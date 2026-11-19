#!/usr/bin/env python3
# version: 0.1.9
"""test_review_section_plan.py — lib/review_section_plan.py, plan_section on an existing note (046 T5.1).

PRD F4-AC2, F4-AC3, F4-AC4, F5-AC1, F5-AC2, F5-AC3, F5-AC5; Rules 3, 4, 8, 9; SDD Runtime View /
Complex Logic (steps 1-8, traced examples 1-3), ADR-4, ADR-10, ADR-12. Numbered-line fixtures: every
note is built from a list whose indexes are the line numbers the assertions name.

- the three SDD traced examples and the seven layouts of the second SDD validation
- first delivery per placement (before -> before, under -> after, end -> inside, or before the first
  sub-heading when the heading has some: T6.3); replace with and without scope
- stops: section-missing, section-ambiguous, section-broken, section-moved, block-in-review-section,
  landing-off-limits, and the choices that answer them
- item lines escaped against marker text; JS trimEnd vs Python rstrip (U+0085, U+FEFF)
- every applied plan through a reference splice (Hashi's documented semantics): every character outside
  the markers unchanged
- the import direction after the spec 046 T5.2 split: review_actions -> review_new_note ->
  review_section_plan -> review_hashi_text, never back (static, and each module imported alone)

All data is synthetic.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))

from lib import review_hashi_text as rht  # noqa: E402
from lib import review_section_plan as rsp  # noqa: E402

WEEK, MONTH = "2026-W13", "2026-03"
ITEMS = [{"text": "Steuererklärung abgeschickt ([[2026-03-24]])"},
         {"text": "Drei Abende ohne Bildschirm", "lines": ["zweite Zeile"]}]
BODY = ["- Steuererklärung abgeschickt ([[2026-03-24]])", "- Drei Abende ohne Bildschirm", "  zweite Zeile"]


def row(key="s1", heading="A", level=4, parent=None, placement="under", occurrence=1) -> dict:
    return {"id": key, "heading": heading, "level": level, "parent": parent, "occurrence": occurrence,
            "placement": placement}


def start(key="s1", period=WEEK) -> str:
    return rsp.start_marker(key, period)


def end(key="s1", period=WEEK) -> str:
    return rsp.end_marker(key, period)


def note(lines: List[str]) -> str:
    return "\n".join(lines) + "\n"


def numbered(n: int, **at) -> List[str]:
    """``n`` filler lines, ``at`` maps ``"L<i>"`` to the line at index i."""
    lines = [f"text {i}" for i in range(n)]
    for name, value in at.items():
        lines[int(name[1:])] = value
    return lines


def plan(r: dict, lines: List[str], period=WEEK, items=ITEMS, **kw) -> rsp.SectionPlan:
    return rsp.plan_section(r, note(lines), period, items, **kw)


# --- the reference splice: Hashi's documented semantics, written independently ----------------

def _hashi_heading(lines, value):
    return next((h for h in rht.hashi_headings(lines) if h[2] == value), None)


def hashi_apply(text: str, action: dict) -> str:
    """The note after Hashi applies ``action`` (insertUnderMarker.ts / the replace_between_markers contract)."""
    lines = text.split("\n")
    trailing = text.endswith("\n")
    body = lines[:-1] if trailing else list(lines)
    if action["action"] == "insert_under_marker":
        head = _hashi_heading(lines, action["anchor"]["value"])
        assert head is not None, "anchor not found"
        if action["placement"] == "before":
            at = head[0]
        elif action["placement"] == "after":
            at = head[0] + 1
        else:
            nxt = next((h for h in rht.hashi_headings(lines) if h[0] > head[0] and h[1] <= head[1]), None)
            at = nxt[0] if nxt else len(lines)
        at = max(0, min(at, len(body)))
        body[at:at] = action["content"].split("\n")
        return "\n".join(body) + ("\n" if trailing else "")
    assert action["action"] == "replace_between_markers"
    fenced = rht.fenced_mask(lines)

    def is_marker(i, m):
        return not fenced[i] and lines[i].rstrip(rht.JS_WS) == m
    starts = [i for i in range(len(lines)) if is_marker(i, action["start_marker"])]
    assert len(starts) == 1, "start marker not found or duplicated"
    ends = [i for i in range(len(lines)) if is_marker(i, action["end_marker"])]
    after = [i for i in ends if i > starts[0]]
    assert after and len(ends) == 1, "end marker missing, duplicated or out of order"
    s, e = starts[0], after[0]
    if "scope" in action:
        heads = rht.hashi_headings(lines)
        scope = next((h for h in heads if h[2] == action["scope"]["heading"] and h[1] == action["scope"]["level"]),
                     None)
        assert scope is not None, "scope heading not found"
        nxt = next((h for h in heads if h[0] > scope[0] and h[1] <= scope[1]), None)
        assert scope[0] < s and e < (nxt[0] if nxt else len(lines)), "markers outside scope"
    new = action["content"].split("\n") if action["content"] else []
    body[s + 1:e] = new
    return "\n".join(body) + ("\n" if trailing else "")


def _marker_index(lines: List[str], marker: str) -> int:
    """The one unfenced line equal to ``marker`` after JavaScript's trimEnd."""
    fenced = rht.fenced_mask(lines)
    found = [i for i, ln in enumerate(lines) if not fenced[i] and ln.rstrip(rht.JS_WS) == marker]
    assert len(found) == 1, f"marker {marker!r} found {len(found)} times"
    return found[0]


def splice(before: str, p: rsp.SectionPlan) -> str:
    """The note after Hashi applies ``p``, asserting that every character outside the markers is unchanged."""
    action = p.action("I01", "Calendar/W13.md")
    assert action is not None, p.mode
    after = hashi_apply(before, action)
    old, new = before.split("\n"), after.split("\n")
    s = _marker_index(new, p.start_marker)
    e = _marker_index(new, p.end_marker)
    assert new[s + 1:e] == p.lines
    if p.mode == "insert":
        # the inserted block plus its one trailing blank line; everything else is the old note
        assert new[:s] + new[e + 2:] == old and new[e + 1] == ""
    else:
        os_, oe = _marker_index(old, p.start_marker), _marker_index(old, p.end_marker)
        assert new[:s + 1] == old[:os_ + 1] and new[e:] == old[oe:]
    return after


# --- the guard: every plan_section call in this module whose plan carries an action is spliced ----

_PLAN_SECTION = rsp.plan_section
SPLICED: List[str] = []


def _spliced_plan_section(r, note_text, period, items, **kw):
    p = _PLAN_SECTION(r, note_text, period, items, **kw)
    if p.action("I01", "Calendar/W13.md") is not None:
        splice(note_text, p)
        SPLICED.append(p.mode)
    return p


@pytest.fixture(autouse=True)
def _splice_every_applied_plan(monkeypatch):
    monkeypatch.setattr(rsp, "plan_section", _spliced_plan_section)


def test_guard_every_applied_plan_goes_through_the_splice():
    assert rsp.plan_section is _spliced_plan_section
    before = len(SPLICED)
    rsp.plan_section(row("s1", "A", 3, "Review", "end"), note(_two_sections()), WEEK, ITEMS)
    assert SPLICED[before:] == ["insert"]


def applied(r, lines, period=WEEK, **kw):
    """``(plan, note text after Hashi applies it)``; the splice check runs inside ``plan_section``."""
    before = note(lines)
    p = rsp.plan_section(r, before, period, ITEMS, **kw)
    assert p.action("I01", "Calendar/W13.md") is not None, p.mode
    return p, hashi_apply(before, p.action("I01", "Calendar/W13.md"))


# --- SDD traced examples ------------------------------------------------------------------

def _month_goals(block_at: Optional[int] = None) -> List[str]:
    lines = numbered(45, L0="# 2026-03", L20="### Goals and Wishes", L22="#### Work", L25="#### Contacts",
                     L28="#### Health", L31="#### Spare Time", L38="### I look forward to")
    if block_at is not None:
        lines[block_at:block_at + 3] = [start("s4", MONTH), "- old", end("s4", MONTH)]
    return lines


def test_traced_1_end_with_subsections_is_replaced_in_the_range_with_scope():
    r = row("s4", "Goals and Wishes", 3, None, "end")
    p, _ = applied(r, _month_goals(34), MONTH)
    assert p.mode == "replace" and p.scope == {"heading": "Goals and Wishes", "level": 3}
    assert p.notices == ["block-replaced"]


def test_traced_1_spare_time_off_limits_stops_the_rerun():
    r = row("s4", "Goals and Wishes", 3, None, "end")
    off = [{"heading": "Spare Time", "level": 4, "parent": "Goals and Wishes", "occurrence": 1}]
    p = plan(r, _month_goals(34), MONTH, off_limits=off)
    assert p.mode == "landing-off-limits" and p.stop == "landing-off-limits" and p.action("I01", "x") is None


def _week_wwg(lines_at=None) -> List[str]:
    lines = numbered(20, L0="# 2026-W13", L10="#### What Went Well This Week?", L18="#### What Should I Start Doing?")
    for i, v in (lines_at or {}).items():
        lines[i] = v
    return lines


def test_traced_2_under_rerun_replaced_with_scope():
    r = row("s1", "What Went Well This Week?", 4)
    p, _ = applied(r, _week_wwg({11: start(), 12: "- old", 14: end()}))
    assert p.mode == "replace" and p.scope == {"heading": "What Went Well This Week?", "level": 4}


def test_traced_2_end_marker_deleted_is_broken():
    r = row("s1", "What Went Well This Week?", 4)
    p = plan(r, _week_wwg({11: start(), 12: "- old"}))
    assert p.mode == "broken" and p.stop == "section-broken" and p.action("I01", "x") is None


def test_traced_2_fenced_start_is_a_hidden_copy_and_broken():
    r = row("s1", "What Went Well This Week?", 4)
    p = plan(r, _week_wwg({10: "#### What Went Well This Week?", 11: "```", 12: start(), 13: "```", 14: end()}))
    assert p.mode == "broken"


def _week_planning(block=True) -> List[str]:
    lines = numbered(56, L0="# 2026-W13", L44="### Check My Own Words", L50="### Planning")
    if block:
        lines[47:50] = [start("s3"), "- old", end("s3")]
    return lines


def test_traced_3_before_replaced_without_scope():
    p, _ = applied(row("s3", "Planning", 3, None, "before"), _week_planning())
    assert p.mode == "replace" and p.scope is None


def test_traced_3_before_off_limits_above_stops_first_delivery_and_rerun():
    off = [{"heading": "Check My Own Words", "level": 3, "parent": None, "occurrence": 1}]
    r = row("s3", "Planning", 3, None, "before")
    assert plan(r, _week_planning(False), off_limits=off).mode == "landing-off-limits"
    assert plan(r, _week_planning(True), off_limits=off).mode == "landing-off-limits"


def test_sdd_example_end_marker_lost_never_pairs_with_next_block():
    text = (f"#### A\n{start()}\n- x\n\n#### B\nuser text\n{start('s2')}\n- y\n{end('s2')}\n")
    p = rsp.plan_section(row("s1", "A"), text, WEEK, ITEMS)
    assert p.mode == "broken" and p.action("I01", "x") is None


# --- first delivery per placement ----------------------------------------------------------

def _two_sections() -> List[str]:
    return ["# W13", "## Review", "### A", "user text a", "#### A1", "a1 text", "### B", "b text"]


@pytest.mark.parametrize("heading, placement, anchor, hashi, at", [
    ("A", "before", "A", "before", 2), ("A", "under", "A", "after", 3),
    ("A", "end", "A1", "before", 4),             # T6.3: the end of A's own text, before its first sub-heading
    ("B", "end", "B", "inside", 8)])             # no sub-heading: the end of the section
def test_first_delivery_maps_the_placement_and_lands_where_hashi_puts_it(heading, placement, anchor, hashi, at):
    p, after = applied(row("s1", heading, 3, "Review", placement), _two_sections())
    assert p.mode == "insert" and p.anchor == anchor and p.hashi_placement == hashi and p.notices == []
    assert after.split("\n")[at] == p.start_marker
    content = p.action("I01", "n.md")["content"]
    assert content == "\n".join([start(), *BODY, end()]) + "\n"


def test_insert_action_shape():
    p = plan(row("s1", "A", 3, "Review", "end"), _two_sections())
    assert p.action("I02", "Calendar/W13.md") == {
        "id": "I02", "action": "insert_under_marker", "target_path": "Calendar/W13.md",
        "anchor": {"type": "heading", "value": "A1"}, "placement": "before",
        "content": "\n".join([start(), *BODY, end()]) + "\n"}
    assert plan(row("s1", "B", 3, "Review", "end"), _two_sections()).action("I01", "n")["placement"] == "inside"


def test_replace_action_shape_with_and_without_scope():
    lines = _two_sections()
    lines[4:4] = [start(), "- old", end()]
    under = plan(row("s1", "A", 3, "Review", "under"), lines).action("I01", "n.md")
    assert under == {"id": "I01", "action": "replace_between_markers", "target_path": "n.md",
                     "start_marker": start(), "end_marker": end(), "scope": {"heading": "A", "level": 3},
                     "content": "\n".join(BODY)}
    before = _two_sections()
    before[2:2] = [start(), "- old", end()]
    action = plan(row("s1", "A", 3, "Review", "before"), before).action("I01", "n.md")
    assert "scope" not in action and action["action"] == "replace_between_markers"


def test_rerun_twice_keeps_one_block_and_the_user_text():
    r = row("s1", "A", 3, "Review", "under")
    _, first = applied(r, _two_sections())
    p = rsp.plan_section(r, first, WEEK, [{"text": "neu"}])
    second = hashi_apply(first, p.action("I01", "n.md"))
    assert p.mode == "replace" and second.count(start()) == 1 and second.count(end()) == 1
    assert "user text a" in second and "- neu" in second and "Steuer" not in second


def test_empty_items_give_an_empty_block():
    p = rsp.plan_section(row("s1", "A", 3, "Review", "end"), note(_two_sections()), WEEK, [])
    assert p.lines == [] and p.action("I01", "n")["content"] == f"{start()}\n{end()}\n"


# --- the seven layouts of the second SDD validation -------------------------------------------

def test_layout_end_three_levels_deep_lands_in_the_own_body_before_the_first_sub_heading():
    """T6.3 (owner 2026-11-17): `end` is the end of G's own text, so an off-limits deepest heading no longer stops it."""
    lines = ["# M", "## G", "### G1", "#### G1a", "deep", "## Next"]
    p, after = applied(row("s1", "G", 2, None, "end"), lines)
    assert after.split("\n")[2] == p.start_marker and (p.anchor, p.hashi_placement) == ("G1", "before")
    off = [{"heading": "G1a", "level": 4, "parent": "G1", "occurrence": 1}]
    assert plan(row("s1", "G", 2, None, "end"), lines, off_limits=off).mode == "insert"
    with_sub = [{"heading": "G1", "level": 3, "parent": "G", "occurrence": 1, "with_subsections": True}]
    assert plan(row("s1", "G", 2, None, "end"), lines, off_limits=with_sub).mode == "insert"
    # a re-run keeps finding it in the range, not as moved
    p2 = rsp.plan_section(row("s1", "G", 2, None, "end"), after, WEEK, ITEMS)
    assert p2.mode == "replace" and p2.scope == {"heading": "G", "level": 2}


def test_layout_before_at_the_top_lands_in_the_preamble():
    lines = ["---", "a: 1", "---", "## First", "text"]
    p, after = applied(row("s1", "First", 2, None, "before"), lines)
    assert after.split("\n")[3] == p.start_marker
    p2 = rsp.plan_section(row("s1", "First", 2, None, "before"), after, WEEK, ITEMS)
    assert p2.mode == "replace" and p2.scope is None


def test_layout_under_with_user_text_keeps_it_below_the_block():
    lines = ["## A", "my own line 1", "my own line 2", "## B"]
    p, after = applied(row("s1", "A", 2, None, "under"), lines)
    out = after.split("\n")
    assert out[1] == p.start_marker and out[out.index(p.end_marker) + 2:][:2] == ["my own line 1", "my own line 2"]


def test_layout_same_text_at_another_level_is_ambiguous():
    lines = ["## A", "x", "### A", "y"]
    assert plan(row("s1", "A", 3, "A", "under"), lines).mode == "ambiguous"
    assert plan(row("s1", "A", 2, None, "under"), lines).stop == "section-ambiguous"


def test_layout_same_text_at_the_same_level_is_ambiguous_also_on_rerun():
    lines = ["## P", "### A", start(), "- old", end(), "## Q", "### A"]
    assert plan(row("s1", "A", 3, "P", "under"), lines).mode == "ambiguous"
    assert plan(row("s1", "A", 3, "P", "under"), ["## P", "### A", "## Q", "### A"]).mode == "ambiguous"


def test_layout_a_block_straddling_a_heading_is_broken():
    lines = ["## A", start(), "- x", "## B", end()]
    assert plan(row("s1", "A", 2, None, "end"), lines).mode == "broken"


def _with_review(extra: List[str]) -> List[str]:
    return ["# W13", "## A", "a text", "## Tomo Review", rht.marker_line(WEEK), "### Erledigt", "- x", *extra,
            "## C", "c text"]


def test_layout_a_block_inside_tomo_review_stops():
    lines = _with_review([start(), "- old", end()])
    p = plan(row("s1", "A", 2, None, "end"), lines)
    assert p.mode == "in-review" and p.stop == "block-in-review-section"
    assert plan(row("s1", "A", 2, None, "end"), lines, choice="skip").mode == "skip"


def test_layout_tomo_review_placed_inside_an_off_limits_heading():
    lines = ["## Own", "my words", "### Sub", "sub words", "## Next"]
    own = [{"heading": "Own", "level": 2, "parent": None, "occurrence": 1, "with_subsections": True}]
    assert rsp.place_off_limits(note(lines), "Own", "inside", own) is not None
    assert rsp.place_off_limits(note(lines), "Next", "before", own) is not None
    heading_only = [{"heading": "Own", "level": 2, "parent": None, "occurrence": 1}]
    assert rsp.place_off_limits(note(lines), "Own", "inside", heading_only) is None    # lands under "Sub"
    assert rsp.place_off_limits(note(lines), "Own", "before", own) is None              # preamble
    assert rsp.place_off_limits(note(lines), "Missing", "before", own) is None


# --- stops ------------------------------------------------------------------------------------

def test_missing_on_first_delivery_and_rerun_with_its_choices():
    lines = ["## B", "text"]
    p = plan(row("s1", "A", 2), lines)
    assert p.mode == "missing" and p.stop == "section-missing" and p.action("I01", "x") is None
    assert plan(row("s1", "A", 2), lines, choice="skip").mode == "skip"
    review = plan(row("s1", "A", 2), lines, choice="review")
    assert review.mode == "review" and review.lines == BODY and review.action("I01", "x") is None
    renamed = ["## A renamed", start(), "- old", end()]
    assert plan(row("s1", "A", 2), renamed).mode == "missing"


def test_missing_on_rerun_confirm_moved_replaces_scoped_where_it_sits():
    renamed = ["## A renamed", start(), "- old", end(), "## B"]
    p, _ = applied(row("s1", "A", 2), renamed, choice="confirm-moved")
    assert p.mode == "replace" and p.scope == {"heading": "A renamed", "level": 2}
    assert p.notices == ["block-replaced", "block-moved-confirmed"]
    assert plan(row("s1", "A", 2), ["## B"], choice="confirm-moved").mode == "missing"


def test_missing_on_rerun_with_an_intact_block_offers_no_review():
    """Rule 8 / F5-AC5: `review` would leave the earlier block and add a second copy into Tomo Review."""
    renamed = ["## A renamed", start(), "- old", end(), "## B"]
    p = plan(row("s1", "A", 2), renamed)
    assert p.mode == "missing" and p.offers == ("skip", "confirm-moved")
    refused = plan(row("s1", "A", 2), renamed, choice="review")
    assert refused.mode == "missing" and refused.offers == ("skip", "confirm-moved")
    assert plan(row("s1", "A", 2), renamed, choice="skip").mode == "skip"
    assert plan(row("s1", "A", 2), ["## B"]).offers == ("skip", "review"), "no block: review stays"


def test_ambiguous_on_rerun_with_an_intact_block_offers_no_review():
    lines = ["## A", start(), "- old", end(), "## A"]
    p = plan(row("s1", "A", 2), lines)
    assert p.mode == "ambiguous" and p.offers == ("skip",)
    assert plan(row("s1", "A", 2), lines, choice="review").mode == "ambiguous"
    assert plan(row("s1", "A", 2), lines, choice="skip").mode == "skip"
    assert plan(row("s1", "A", 2), ["## A", "## A"]).offers == ("skip", "review"), "no block: review stays"


BROKEN_MATERIAL = [
    pytest.param([start(), "- old"], id="start-only"),
    pytest.param(["- old", end()], id="end-only"),
    pytest.param([start(), "- old", end(), start(), "- y", end()], id="duplicated"),
    pytest.param(["```", start(), "```"], id="fenced-copy"),
    pytest.param(["> " + end()], id="quoted-copy"),
]


@pytest.mark.parametrize("block", BROKEN_MATERIAL)
@pytest.mark.parametrize(("lines_of", "stop"), [
    pytest.param(lambda b: ["## A renamed", *b, "## B"], "missing", id="missing"),
    pytest.param(lambda b: ["## A", *b, "## A"], "ambiguous", id="ambiguous"),
])
def test_a_stop_beside_any_earlier_block_material_offers_skip_only(block, lines_of, stop):
    """Rule 8 / F5-AC5: a broken earlier block stays in the note, so `review` would add a second Tomo copy."""
    lines = lines_of(block)
    p = plan(row("s1", "A", 2), lines)
    assert p.mode in (stop, "broken") and p.offers == ("skip",), (p.mode, p.offers)
    for choice in ("review", "confirm-moved"):
        refused = plan(row("s1", "A", 2), lines, choice=choice)
        assert refused.mode == p.mode and refused.offers == ("skip",), choice
    assert plan(row("s1", "A", 2), lines, choice="skip").mode == "skip"


def test_another_periods_or_sections_block_keeps_review():
    lines = ["## B", start("s1", MONTH), "- x", start("s2"), "- y"]
    assert plan(row("s1", "A", 2), lines).offers == ("skip", "review")


def test_mapped_by_level_parent_and_occurrence():
    lines = ["## P", "### A", "## Q", "#### A"]
    assert plan(row("s1", "A", 3, "Q"), lines).mode == "missing"          # parent differs
    assert plan(row("s1", "A", 3, "P", occurrence=2), lines).mode == "missing"


def test_ambiguous_when_hashis_first_match_by_text_and_level_is_another_heading():
    # the block was moved under the second "### X"; Hashi's scope lookup would find the first
    lines = ["## A", "a", "## P", "### X", "## Q", "### X", start(), "- old", end()]
    p = plan(row("s1", "A", 2), lines, choice="confirm-moved")
    assert p.mode == "ambiguous" and p.stop == "section-ambiguous"
    assert plan(row("s1", "A", 2), lines, choice="skip").mode == "skip"


def test_ambiguous_choices_skip_and_review():
    lines = ["## A", "## A"]
    assert plan(row("s1", "A", 2), lines, choice="skip").mode == "skip"
    assert plan(row("s1", "A", 2), lines, choice="review").mode == "review"
    assert plan(row("s1", "A", 2), lines, choice="confirm-moved").mode == "ambiguous"


@pytest.mark.parametrize("block", [
    pytest.param([start(), "- x"], id="start-without-end"),
    pytest.param(["- x", end()], id="end-without-start"),
    pytest.param([start(), "- x", end(), start(), "- y", end()], id="duplicated"),
    pytest.param([end(), "- x", start()], id="out-of-order"),
    pytest.param([start(), end(), end()], id="second-end"),
    pytest.param(["```", start(), "```", start(), "- x", end()], id="fenced-copy"),
    pytest.param(["  " + start(), start(), "- x", end()], id="indented-copy"),
    pytest.param(["> " + start(), start(), "- x", end()], id="quoted-copy"),
    pytest.param([f"see `{end()}`", start(), "- x", end()], id="inline-code-copy"),
    pytest.param([start() + "\u0085", "- x", end()], id="u0085-is-no-marker"),
])
def test_broken_blocks(block):
    lines = ["## A", *block, "## B"]
    p = plan(row("s1", "A", 2, None, "end"), lines)
    assert p.mode == "broken" and p.action("I01", "x") is None
    assert plan(row("s1", "A", 2, None, "end"), lines, choice="skip").mode == "skip"


def test_broken_heading_between_markers_offers_skip():
    lines = ["## A", start(), "### inner", end()]
    assert plan(row("s1", "A", 2, None, "end"), lines).mode == "broken"
    assert plan(row("s1", "A", 2, None, "end"), lines, choice="skip").mode == "skip"


def test_trailing_feff_and_whitespace_still_count_as_the_marker():
    lines = ["## A", start() + "﻿", "- old", end() + " \t\r", "## B"]
    p = plan(row("s1", "A", 2, None, "end"), lines)
    assert p.mode == "replace"


def test_markers_of_another_period_or_section_are_not_ours():
    lines = ["## A", start("s1", "2026-W12"), "- old", end("s1", "2026-W12"), start("s12"), end("s12")]
    p = plan(row("s1", "A", 2, None, "end"), lines)
    assert p.mode == "insert"


def test_moved_under_another_heading_stops_and_confirm_replaces_scoped():
    lines = ["## A", "a", "## B", start(), "- old", end(), "## C"]
    p = plan(row("s1", "A", 2, None, "end"), lines)
    assert p.mode == "moved" and p.stop == "section-moved" and p.block_at == {"heading": "B", "level": 2}
    assert plan(row("s1", "A", 2, None, "end"), lines, choice="skip").mode == "skip"
    confirmed, _ = applied(row("s1", "A", 2, None, "end"), lines, choice="confirm-moved")
    assert confirmed.scope == {"heading": "B", "level": 2}
    assert confirmed.notices == ["block-replaced", "block-moved-confirmed"]


def test_moved_into_a_subsection_of_under_is_moved():
    lines = ["## A", "### A1", start(), "- old", end(), "## B"]
    p = plan(row("s1", "A", 2, None, "under"), lines)
    assert p.mode == "moved" and p.block_at == {"heading": "A1", "level": 3}
    assert plan(row("s1", "A", 2, None, "end"), lines).mode == "replace"     # end: the whole range is home


def test_moved_into_the_preamble_is_never_replaced():
    lines = [start(), "- old", end(), "## A"]
    p = plan(row("s1", "A", 2, None, "under"), lines, choice="confirm-moved")
    assert p.mode == "moved" and p.block_at == {"heading": None, "level": None} and p.action("I01", "x") is None
    assert plan(row("s1", "A", 2, None, "under"), lines, choice="skip").mode == "skip"


def test_before_home_passes_over_a_tomo_review_directly_above():
    lines = ["## Above", start(), "- old", end(), "## Tomo Review", rht.marker_line(WEEK), "### Erledigt", "- x",
             "## Planning"]
    p, _ = applied(row("s1", "Planning", 2, None, "before"), lines)
    assert p.mode == "replace" and p.scope is None


def test_insert_inside_or_at_the_tomo_review_range_stops():
    # end of "A" when A's range ends at Tomo Review's heading: lands above it, allowed
    lines = _with_review([])
    assert plan(row("s1", "A", 2, None, "end"), lines).mode == "insert"
    # before "C", directly after Tomo Review: lands at the end of Tomo Review's range
    assert plan(row("s1", "C", 2, None, "before"), lines).mode == "in-review"
    # a section mapped to a heading inside Tomo Review
    p = plan(row("s1", "Erledigt", 3, "Tomo Review", "under"), lines)
    assert p.mode == "in-review"
    assert plan(row("s1", "Erledigt", 3, "Tomo Review", "under"), lines, choice="skip").mode == "skip"


def test_insert_at_the_new_tomo_review_insertion_point_stops():
    lines = ["## A", "a", "## B", "b"]
    # Tomo Review planned before "B" (index 2): an "end of A" insert lands at the same index
    assert plan(row("s1", "A", 2, None, "end"), lines, review_at=2).mode == "in-review"
    assert plan(row("s1", "A", 2, None, "under"), lines, review_at=2).mode == "insert"


def test_landing_off_limits_where_it_would_land_and_where_it_sits():
    lines = ["## Own", "words", "## A", "a"]
    own = [{"heading": "Own", "level": 2, "parent": None, "occurrence": 1}]
    p = plan(row("s1", "A", 2, None, "before"), lines, off_limits=own)
    assert p.mode == "landing-off-limits" and plan(row("s1", "A", 2, None, "before"), lines, off_limits=own,
                                                     choice="skip").mode == "landing-off-limits"
    assert plan(row("s1", "A", 2, None, "under"), lines, off_limits=own).mode == "insert"
    sits = ["## Own", start(), "- old", end(), "## A"]
    assert plan(row("s1", "A", 2, None, "under"), sits, off_limits=own, choice="confirm-moved").mode \
        == "landing-off-limits"


def test_a_choice_where_no_stop_arises_changes_nothing():
    lines = _two_sections()
    for choice in ("skip", "review", "confirm-moved"):
        assert plan(row("s1", "A", 3, "Review", "end"), lines, choice=choice).mode == "insert"


def test_unknown_choice_or_placement_is_refused():
    with pytest.raises(ValueError):
        plan(row("s1", "A", 3, "Review", "end"), _two_sections(), choice="maybe")
    with pytest.raises(ValueError):
        plan(row("s1", "A", 3, "Review", "review"), _two_sections())


# --- item lines --------------------------------------------------------------------------------

def test_item_line_holding_a_marker_is_escaped_and_the_next_run_is_not_broken():
    items = [{"text": "copy", "lines": [start(), f"and {end('s2')}"]}]
    p = rsp.plan_section(row("s1", "A", 3, "Review", "end"), note(_two_sections()), WEEK, items)
    assert p.lines == ["- copy", "  %% tomo\\:s1 2026-W13 %%", "  and %% /tomo\\:s2 2026-W13 %%"]
    assert p.escaped_lines == 2
    after = hashi_apply(note(_two_sections()), p.action("I01", "n"))
    assert rsp.plan_section(row("s1", "A", 3, "Review", "end"), after, WEEK, ITEMS).mode == "replace"


def test_heading_with_closing_hashes_is_anchored_by_hashis_text():
    lines = ["## A ##", "text", "## B"]
    p, _ = applied(row("s1", "A", 2, None, "under"), lines)
    assert p.anchor == "A ##"


def test_crlf_heading_is_no_heading_for_hashi():
    assert plan(row("s1", "A", 2), ["## A\r", "text"]).mode == "missing"


# --- the import direction (spec 046 T5.2 split) -------------------------------------------------

LIB = TESTS_DIR.parent / "tomo" / "scripts" / "lib"
# module -> the review modules it must never import (directly)
FORBIDDEN = {   # the order (T5.4): review_actions -> review_new_note -> review_section_set -> review_section_plan
    "review_hashi_text": {"review_actions", "review_new_note", "review_section_set", "review_section_plan",
                          "review_section_report"},
    "review_section_plan": {"review_actions", "review_new_note", "review_section_set", "review_section_report"},
    "review_section_set": {"review_actions", "review_new_note"},
    "review_new_note": {"review_actions"},
    # the T6.2 splits: review-instructions.py -> review_target_read -> review_delivery -> review_actions;
    # review_delivery -> review_section_report -> review_section_plan; review_kado_conflict imports no review lib
    "review_section_report": {"review_actions", "review_new_note", "review_section_set", "review_delivery"},
    "review_actions": {"review_delivery", "review_section_report", "review_target_read"},
    "review_delivery": {"review_target_read", "review_instructions_args", "review_kado_conflict"},
    "review_kado_conflict": {"review_actions", "review_delivery", "review_section_plan", "review_state"},
    "review_target_read": {"review_instructions_args", "review_kado_conflict"},
    "review_instructions_args": {"review_actions", "review_delivery", "review_target_read", "review_kado_conflict"},
    # the shared heading walk (T6.2): review_section_plan -> review_mapping, never back
    "review_mapping": {"review_section_plan", "review_hashi_text", "review_section_set", "review_actions"},
}


def _lib_imports(module: str) -> set:
    tree = ast.parse((LIB / f"{module}.py").read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "lib":
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("lib."):
            found.add(node.module.split(".", 1)[1])
        elif isinstance(node, ast.Import):
            found.update(a.name.split(".", 1)[1] for a in node.names if a.name.startswith("lib."))
    return found


@pytest.mark.parametrize("module", sorted(FORBIDDEN))
def test_a_lower_review_module_never_imports_a_higher_one(module):
    assert not _lib_imports(module) & FORBIDDEN[module], _lib_imports(module) & FORBIDDEN[module]


@pytest.mark.parametrize("order", [("review_section_plan", "review_actions"), ("review_actions", "review_section_plan"),
                                   ("review_new_note", "review_actions"), ("review_hashi_text", "review_actions"),
                                   ("review_section_set", "review_actions"), ("review_section_plan", "review_section_set"),
                                   ("review_section_report", "review_delivery"), ("review_kado_conflict",),
                                   ("review_target_read", "review_actions"), ("review_instructions_args",)])
def test_each_review_module_imports_alone_in_a_fresh_interpreter(order):
    code = f"import sys; sys.path.insert(0, {str(LIB.parent)!r}); " + "; ".join(f"from lib import {m}" for m in order)
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr

#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t6_3_end_own_text.py — `end` means the end of the heading's own text (spec 046 T6.3, owner 2026-11-17).

The joint run with Hashi (round 1) delivered `end` as Hashi `inside`, which appends at the end of the heading's
whole section: `### In my own words` got its block after its last `####` child, `## Organisation` at the end of the
file. Since T6.3 a mapped `end` at a heading with sub-headings is sent as `before` its first sub-heading; without
sub-headings it stays `inside`. Mechanisms a mutation falsifies:

- `review_section_plan._first_delivery` (the insertion point and the anchor of `end`): the block lands at the end of
  the parent's own body, before the first sub-heading, through the reference applier of
  tests/e2e_046_sections_walk.py (Hashi's documented `inside` = to the next same-or-higher heading); an empty own
  body puts it right under the heading line with one blank line before the sub-heading;
- the ambiguity check on the anchor actually sent (a first sub-heading whose text occurs twice);
- the landing check: an off-limits last or first sub-section no longer stops `end`;
- re-runs: the new position and an old one (after the last sub-section) are both replaced, scoped to the parent;
- `review_section_set.ordered`: a parent's `end` and its first sub-heading's `before` share one index; the parent's
  block comes first in `compose` and in a new note's splice, whatever the row order;
- `review_mapping.landing` / `review_setup_rows`: setup accepts an `end` whose last sub-section is off-limits, the
  "Tomo Review" place `inside` keeps the whole-section rule.

All text is synthetic (the W13 heading shape, no journal text).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from e2e_046_sections_walk import APPLY  # noqa: E402
from lib import review_mapping as rm  # noqa: E402
from lib import review_section_plan as rsp  # noqa: E402
from lib import review_section_set as rss  # noqa: E402
from lib import review_setup_rows as rsr  # noqa: E402

WEEK = "2026-W13"
ITEMS = [{"text": "one item"}]


def row(key, heading, level, parent=None, placement="end") -> dict:
    return {"id": key, "heading": heading, "level": level, "parent": parent, "occurrence": 1, "placement": placement}


def note(lines) -> str:
    return "\n".join(lines) + "\n"


def apply(text: str, action: dict) -> str:
    result, out = APPLY[action["action"]](text, action)
    assert result == "applied", (result, action)
    return out


def block(key: str, item: str = "- one item") -> list:
    return [rsp.start_marker(key, WEEK), item, rsp.end_marker(key, WEEK)]


W13 = ["# 2026-W13", "", "## Overview", "overview text", "",
       "### In my own words", "own words text", "",
       "#### What Went Well This Week?", "went well", "",
       "#### What Did Not Go Well?", "not well", "",
       "#### What Should I Start Doing?", "start", "",
       "#### What Should I Continue Doing?", "continue", "",
       "## Organisation", "",
       "### Planning", "planning text", "",
       "### Last Check", "last check text"]
OWN = row("s6", "In my own words", 3, "Overview")
ORG = row("s11", "Organisation", 2)


# --- first delivery ------------------------------------------------------------------------------

def test_end_with_sub_headings_lands_at_the_end_of_the_parents_own_text():
    p = rsp.plan_section(OWN, note(W13), WEEK, ITEMS)
    assert (p.mode, p.anchor, p.hashi_placement) == ("insert", "What Went Well This Week?", "before")
    out = apply(note(W13), p.action("I01", "w.md")).split("\n")
    at = out.index(rsp.start_marker("s6", WEEK))
    assert out[at - 3:at] == ["### In my own words", "own words text", ""]
    assert out[at:at + 5] == [*block("s6"), "", "#### What Went Well This Week?"]


def test_end_at_a_level_2_parent_lands_above_its_first_sub_heading_not_at_the_end_of_the_file():
    p = rsp.plan_section(ORG, note(W13), WEEK, ITEMS)
    assert (p.anchor, p.hashi_placement) == ("Planning", "before")
    out = apply(note(W13), p.action("I01", "w.md")).split("\n")
    at = out.index(rsp.start_marker("s11", WEEK))
    assert out[at - 2:at + 5] == ["## Organisation", "", *block("s11"), "", "### Planning"]
    assert out[-2] == "last check text", "nothing lands at the end of the file"


def test_end_without_sub_headings_stays_inside():
    lines = ["## A", "a text", "", "## B", "b text"]
    p = rsp.plan_section(row("s1", "A", 2), note(lines), WEEK, ITEMS)
    assert (p.anchor, p.hashi_placement) == ("A", "inside")
    out = apply(note(lines), p.action("I01", "w.md")).split("\n")
    assert out[:7] == ["## A", "a text", "", *block("s1"), ""] and out[7] == "## B"


def test_an_empty_own_body_puts_the_block_right_under_the_heading_line():
    lines = ["## Organisation", "### Planning", "planning text"]
    p = rsp.plan_section(ORG, note(lines), WEEK, ITEMS)
    assert p.blank_after is True
    out = apply(note(lines), p.action("I01", "w.md")).split("\n")
    assert out[:6] == ["## Organisation", *block("s11"), "", "### Planning"]


def test_a_first_sub_heading_whose_text_occurs_twice_is_ambiguous():
    lines = ["## A", "own", "### Notes", "x", "## B", "### Notes", "y"]
    p = rsp.plan_section(row("s1", "A", 2), note(lines), WEEK, ITEMS)
    assert p.mode == "ambiguous" and p.stop == "section-ambiguous" and p.offers == ("skip", "review")
    assert rsp.plan_section(row("s1", "A", 2), note(lines), WEEK, ITEMS, choice="review").mode == "review"


@pytest.mark.parametrize("off", [
    pytest.param({"heading": "What Should I Continue Doing?", "level": 4, "parent": "In my own words"}, id="last"),
    pytest.param({"heading": "What Went Well This Week?", "level": 4, "parent": "In my own words"}, id="first"),
    pytest.param({"heading": "What Went Well This Week?", "level": 4, "parent": "In my own words",
                  "with_subsections": True}, id="first-with-subsections"),
])
def test_an_off_limits_sub_section_no_longer_stops_end(off):
    p = rsp.plan_section(OWN, note(W13), WEEK, ITEMS, off_limits=[{**off, "occurrence": 1}])
    assert p.mode == "insert" and p.hashi_placement == "before"


def test_an_off_limits_parent_still_stops_end():
    off = [{"heading": "Overview", "level": 2, "parent": None, "occurrence": 1, "with_subsections": True}]
    assert rsp.plan_section(OWN, note(W13), WEEK, ITEMS, off_limits=off).mode == "landing-off-limits"


# --- re-runs ------------------------------------------------------------------------------------------

def test_a_rerun_replaces_the_new_block_scoped_to_the_parent():
    first = apply(note(W13), rsp.plan_section(OWN, note(W13), WEEK, ITEMS).action("I01", "w.md"))
    p = rsp.plan_section(OWN, first, WEEK, [{"text": "new item"}])
    assert p.mode == "replace" and p.scope == {"heading": "In my own words", "level": 3}
    out = apply(first, p.action("I01", "w.md"))
    assert out == first.replace("- one item", "- new item")


def test_a_block_an_earlier_run_left_after_the_last_sub_section_is_still_replaced_in_place():
    old = W13[:19] + [*block("s6"), ""] + W13[19:]
    p = rsp.plan_section(OWN, note(old), WEEK, [{"text": "new item"}])
    assert p.mode == "replace" and p.scope == {"heading": "In my own words", "level": 3} and p.notices == [
        "block-replaced"]


# --- one insertion index, two blocks ------------------------------------------------------------------

FIRST = row("s7", "What Went Well This Week?", 4, "In my own words", "before")


@pytest.mark.parametrize("rows", [[OWN, FIRST], [FIRST, OWN]], ids=["template-order", "reordered"])
def test_the_parents_block_comes_before_the_first_sub_headings_before_block(rows):
    items = {"s6": [{"text": "parent item"}], "s7": [{"text": "child item"}]}
    plans = rss.plan_existing(rows, note(W13), WEEK, items)
    assert {p.insert_at for p in plans} == {W13.index("#### What Went Well This Week?")}
    actions = rss.compose(plans, "w.md")
    assert [a["id"] for a in actions] == ["I01", "I02"]
    assert [a["content"].split("\n")[0] for a in actions] == [rsp.start_marker("s6", WEEK),
                                                               rsp.start_marker("s7", WEEK)]
    text = note(W13)
    for action in actions:
        text = apply(text, action)
    out = text.split("\n")
    at = out.index(rsp.start_marker("s6", WEEK))
    assert out[at - 2:at + 9] == ["own words text", "", *block("s6", "- parent item"), "",
                                  *block("s7", "- child item"), "", "#### What Went Well This Week?"]


@pytest.mark.parametrize("rows", [[OWN, FIRST], [FIRST, OWN]], ids=["template-order", "reordered"])
def test_a_new_notes_splice_keeps_the_parents_block_first(rows):
    items = {"s6": [{"text": "parent item"}], "s7": [{"text": "child item"}]}
    plans = rss.plan_new_note(rows, note(W13), WEEK, items)
    lines = note(W13).split("\n")
    rss.splice_blocks(lines, rss.insert_blocks(plans))
    at = lines.index(rsp.start_marker("s6", WEEK))
    assert lines[at:at + 9] == [*block("s6", "- parent item"), "", *block("s7", "- child item"), "",
                                "#### What Went Well This Week?"]


def test_an_off_limits_first_sub_heading_takes_the_parents_block_above_it():
    off = [{"heading": "What Went Well This Week?", "level": 4, "parent": "In my own words", "occurrence": 1}]
    p = rsp.plan_section(OWN, note(W13), WEEK, ITEMS, off_limits=off)
    out = apply(note(W13), p.action("I01", "w.md")).split("\n")
    assert out.index(rsp.end_marker("s6", WEEK)) < out.index("#### What Went Well This Week?")
    assert out[out.index("#### What Went Well This Week?") + 1] == "went well", "the off-limits body is untouched"


# --- setup: the landing rule ---------------------------------------------------------------------------

TEMPLATE = "\n".join(["# <% tp.file.title %>", "## Overview", "x", "### In my own words", "y",
                      "#### What Went Well This Week?", "", "#### What Should I Continue Doing?", "",
                      "## Organisation", "", "### Planning", "", "### Last Check", ""]) + "\n"


def _outline():
    stored = rm.outline(TEMPLATE)
    return rm.from_outline(stored, []), rm.outline_top(stored), stored


@pytest.mark.parametrize("heading, placement, expected", [
    ("In my own words", "end", "In my own words"),
    ("Organisation", "end", "Organisation"),
    ("In my own words", "inside", "What Should I Continue Doing?"),   # the "Tomo Review" place: the whole section
    ("Organisation", "inside", "Last Check"),
])
def test_landing_of_end_is_the_heading_itself_and_inside_the_last_sub_section(heading, placement, expected):
    heads, top, stored = _outline()
    line = next(e["line"] for e in stored["headings"] if e["heading"] == heading)
    assert rm.landing(heads, top, line, placement).heading == expected


def test_setup_accepts_end_beside_an_off_limits_last_sub_section_and_still_refuses_the_place_inside():
    stored = rm.outline(TEMPLATE)
    evidence = {"template": "t.md", "outline": stored, "resolved": {"template": "t.md", "kind": "plain"}}
    last = {"heading": "Last Check", "level": 3, "parent": "Organisation", "occurrence": 1}
    data = {"template": "t.md", "sections": [{**row("s1", "Organisation", 2), "description": "d", "cap": 8}],
            "off_limits": [last], "place": {"anchor": "Organisation", "placement": "inside"}}
    problems = rsr.problems(data, evidence, [])
    assert [(p.pointer, p.kind) for p in problems] == [("/place", "landing-off-limits")]


# --- end to end: the W13 heading shape through the four review scripts and the reference applier ----------

from dataclasses import replace as _replace  # noqa: E402

from e2e_046_sections_walk import KINDS, TEMPLATES, SectionWalk, blocks, user_text  # noqa: E402
from review_e2e_walk import INBOX  # noqa: E402

_W13_TEMPLATE = ("---\ntags: weekly\n---\n# <% tp.file.title %>\n\n## Overview\n\n### In my own words\n\n"
                 "#### What Went Well This Week?\n\n#### What Did Not Go Well?\n\n#### What Should I Start Doing?\n\n"
                 "#### What Should I Continue Doing?\n\n## Organisation\n\n### Planning\n\n### Last Check\n")
_W13_NOTE = "---\njournal-start-date: 2026-03-23\n---\n" + note(W13)
_E2E_ROWS = [{"heading": "In my own words", "level": 3, "parent": "Overview", "placement": "end"},
             {"heading": "Organisation", "level": 2, "parent": None, "placement": "end"},
             {"heading": "What Went Well This Week?", "level": 4, "parent": "In my own words", "placement": "before"}]


@pytest.fixture
def walk(tmp_path, monkeypatch, capsys, request):
    w = SectionWalk(tmp_path, monkeypatch, capsys, request.node.nodeid)
    yield w
    assert [p for p in w.vault.recorded if not p.startswith(INBOX)] == [], "Tomo wrote outside the inbox"


def test_the_w13_shape_end_to_end_lands_each_end_in_its_own_text_and_reruns_in_place(walk):
    k = _replace(KINDS["week"], template_text=_W13_TEMPLATE, target_text=_W13_NOTE,
                 rows=tuple((r["heading"], r["placement"]) for r in _E2E_ROWS))
    walk.vault.files[TEMPLATES + k.template] = k.template_text
    walk.vault.files[k.target] = k.target_text
    rows = [{**r, "occurrence": 1, "description": f"what {r['heading']} asks for", "cap": 8} for r in _E2E_ROWS]
    walk.match(k.kind)
    assert walk.setup(k.kind, sections=rows, off_limits=[])["status"] == "written"
    a, b, c = k.sources
    proposals = {"language": "en", "groups": {"done": [{"text": "Group item", "sources": [a]}]},
                 "sections": [{"key": f"s{i}", "items": [{"text": f"item {i} v1", "sources": [src]}]}
                              for i, src in ((1, a), (2, b), (3, c))]}
    assert walk.pass1(k.period, k.kind, proposals)["status"] == "written"
    walk.approve(k.doc)
    assert walk.deliver(k.stem)["status"] == "delivered"
    actions = walk.set_json(k.stem)["actions"]
    sent = [(a["id"], a["anchor"]["value"], a["placement"]) for a in actions[:3]]
    # s1 and s3 share one index: s3 follows s1, at s1's place; then s2
    assert sent == [("I01", "What Went Well This Week?", "before"), ("I02", "What Went Well This Week?", "before"),
                    ("I03", "Planning", "before")], sent
    assert [a["content"].split("\n")[0] for a in actions[:3]] == [rsp.start_marker(s, WEEK) for s in ("s1", "s3", "s2")]
    assert walk.hashi_apply(k.stem) == ["applied"] * len(actions)
    out = walk.vault.text(k.target).split("\n")
    s1, s2, s3 = (out.index(rsp.start_marker(s, WEEK)) for s in ("s1", "s2", "s3"))
    assert out[s1 - 2:s1] == ["own words text", ""] and out[s1 + 3:s1 + 4] == [""] and s3 == s1 + 4
    assert out[s3 + 3:s3 + 5] == ["", "#### What Went Well This Week?"], "s1, then s3, then the sub-heading"
    assert out[s2 - 2:s2] == ["## Organisation", ""] and out[s2 + 3:s2 + 5] == ["", "### Planning"]
    assert out[-2] == "last check text", "nothing lands at the end of the file"
    own = frozenset(walk.own_blank[k.target])
    assert user_text(walk.vault.text(k.target), own) == k.target_text
    applied = walk.vault.text(k.target)
    # the re-run replaces each block where it sits
    v2 = {**proposals, "sections": [{**s, "items": [{**s["items"][0], "text": s["items"][0]["text"].replace("v1", "v2")}]}
                                    for s in proposals["sections"]]}
    assert walk.pass1(k.period, k.kind, v2)["problems"] == ["review-exists"]
    assert walk.replace(k.stem, "--confirm")["status"] == "replaced"
    walk.approve(k.doc)
    assert walk.deliver(k.stem)["status"] == "delivered"
    again = walk.set_json(k.stem)["actions"]
    assert [(a["action"], a.get("scope")) for a in again[:3]] == [
        ("replace_between_markers", {"heading": "In my own words", "level": 3}),
        ("replace_between_markers", {"heading": "Organisation", "level": 2}),
        ("replace_between_markers", None)]
    walk.hashi_apply(k.stem)
    assert blocks(walk.vault.text(k.target)) == {s: [[line.replace("v1", "v2") for line in b] for b in bl]
                                                 for s, bl in blocks(applied).items()}
    assert user_text(walk.vault.text(k.target), own) == k.target_text

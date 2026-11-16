#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t5_3_readable_sections.py — the readable instructions of a /review section delivery.

Spec 046 T5.3 (PRD F4-AC7): a user without Hashi applies each section by hand. The first delivery is spec 045's
``insert_under_marker`` rendering (heading, placement, the block), the re-run is the new
``replace_between_markers`` branch of ``lib/render_md.py``: both marker lines, the scope, the lines to put between
them. Actions are built by ``review_section_plan.SectionPlan.action`` — the producer's own builder.

Mechanisms each test falsifies:
- the replace branch (not the unknown-action fallback): ``test_replace_names_both_markers_and_the_scope``
- the unscoped wording: ``test_replace_without_scope_says_the_whole_note``
- the bucket in ``_md_section_for``: ``test_replace_sits_with_the_section_inserts``
- ``_fenced_lines`` (no trailing-newline terminator, "\\n"-only split):
  ``test_replace_content_keeps_a_trailing_empty_line``, ``test_replace_content_keeps_a_line_separator``
- the empty-content sentence: ``test_empty_replace_content_says_remove_every_line``
- the code spans around markers and heading: ``test_a_backtick_in_a_marker_does_not_break_the_line``
- the whole document per section: ``test_document_shows_every_section_with_heading_placement_and_block``
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tomo" / "scripts"))

from lib import review_section_plan as rsp  # noqa: E402
from lib.render_md import _md_section_for, _render_action_md, render_instructions_md  # noqa: E402

TARGET = "Efforts/200 Journal/2026/2026-W13.md"
PERIOD = "2026-W13"
HEADING = "What Went Well This Week?"
START = rsp.start_marker("s1", PERIOD)
END = rsp.end_marker("s1", PERIOD)
LINES = ["- Spec 046 plan ([[2026-03-24]])", "- Hashi handoff sent"]


def _plan(mode: str, *, key="s1", lines=LINES, scope=None, anchor=HEADING, placement="inside"):
    return rsp.SectionPlan(key=key, mode=mode, start_marker=rsp.start_marker(key, PERIOD),
                           end_marker=rsp.end_marker(key, PERIOD), lines=list(lines), anchor=anchor,
                           hashi_placement=placement, scope=scope)


def _replace(scope=({"heading": HEADING, "level": 4}), **kw) -> dict:
    return _plan("replace", scope=scope, **kw).action("I02", TARGET)


def _insert(**kw) -> dict:
    return _plan("insert", **kw).action("I01", TARGET)


def _fence_body(md: str) -> list[str]:
    lines = md.split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("````"))
    fence = lines[start].removesuffix("markdown")
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == fence)
    assert end == len(lines) - 1, "the fence must close on the block's last line"
    return lines[start + 1:end]


# ---------------------------------------------------------------- the replace branch

def test_replace_names_both_markers_and_the_scope():
    md = _render_action_md(_replace(), {})
    head = md.split("\n")[:8]
    assert head == [
        f"### I02 — Replace Tomo's block under `{HEADING}` in [[2026-W13]]",
        "- [ ] Applied",
        "- **Target:** [[2026-W13]]",
        f"- **Scope:** the section under the level-4 heading `{HEADING}`, down to the next heading of "
        "level 4 or higher",
        f"- **Start marker line:** `{START}`",
        f"- **End marker line:** `{END}`",
        "- **Where:** every line between these two marker lines is replaced; both marker lines and all "
        "other text stay as they are",
        "- **Put these lines between them:**",
    ]
    assert _fence_body(md) == LINES
    assert "unknown action" not in md


def test_replace_without_scope_says_the_whole_note():
    md = _render_action_md(_replace(scope=None), {})
    assert md.split("\n")[0] == f"### I02 — Replace Tomo's block `{START}` in [[2026-W13]]"
    assert "- **Scope:** the whole note" in md.split("\n")
    assert "level-" not in md


def test_replace_sits_with_the_section_inserts():
    assert _md_section_for(_replace()) == _md_section_for(_insert()) == "tag_handler_updates"


def test_replace_content_keeps_a_trailing_empty_line():
    action = _replace(lines=["- one", ""])
    assert action["content"] == "- one\n"
    assert _fence_body(_render_action_md(action, {})) == ["- one", ""]


def test_replace_content_keeps_a_line_separator():
    action = _replace(lines=["one still one", "nel\x85end"])
    assert _fence_body(_render_action_md(action, {})) == ["one still one", "nel\x85end"]


def test_empty_replace_content_says_remove_every_line():
    md = _render_action_md(_replace(lines=[]), {})
    assert md.split("\n")[-1] == ("- **Put these lines between them:** none — remove every line between the "
                                  "two marker lines")
    assert "````" not in md


def test_a_backtick_in_a_marker_does_not_break_the_line():
    action = _replace(scope={"heading": "Use `code`", "level": 3})
    action["start_marker"] = "%% tomo:`s1` %%"
    md = _render_action_md(action, {})
    assert "- **Start marker line:** ``%% tomo:`s1` %%``" in md.split("\n")
    assert "the level-3 heading `` Use `code` ``" in md


# ---------------------------------------------------------------- the whole document

def test_document_shows_every_section_with_heading_placement_and_block():
    review = {"id": "I03", "action": "insert_under_marker", "target_path": TARGET,
              "anchor": {"type": "heading", "value": "In my own words"}, "placement": "before",
              "content": "## Tomo Review\n%% tomo-review 2026-W13 %%\n### Erledigt\n- alt\n"}
    actions = [_insert(placement="after"), _replace(key="s2"), review]
    md = render_instructions_md(actions, {"generated": "2026-03-30T09:00:00Z", "profile": "miyo"},
                                {"templater_hint": False})
    body = md.split("# Instructions\n", 1)[1]
    assert body.count("## Tag-Handler Updates") == 1
    blocks = re.split(r"\n### (?=I\d\d — )", body)[1:]
    assert [b.split(" — ", 1)[0] for b in blocks] == ["I01", "I02", "I03"]
    first, second, _ = blocks
    assert f"- **Anchor:** `{HEADING}` (heading, placement: after)" in first
    assert "\n".join([START, *LINES, END]) in first
    assert f"`{rsp.start_marker('s2', PERIOD)}`" in second and f"`{rsp.end_marker('s2', PERIOD)}`" in second
    assert "\n".join(LINES) in second

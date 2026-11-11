#!/usr/bin/env python3
# version: 0.1.0
"""test_instruction_render_section_actions.py — copy-ready render for section actions.

Spec 045 T1.5 (PRD F5-AC9): `insert_under_marker` and `replace_section` in
`lib/render_md.py` must let a user without Hashi apply a review section by
hand — the content inside a fence that no backtick run in it can close, the
placement worded against the anchor heading, `replace_section` under its own
"Replace the body of …" heading and in the same section bucket as its
sibling, and every block still opening with `### Inn — …` + `- [ ] Applied`.

Mechanisms each test falsifies:
- the fence (not a blockquote): `test_insert_content_is_fenced_not_quoted`
- the fence length rule (`render_helpers.fence_for`): `test_fence_outgrows_the_longest_backtick_run`
- the per-placement wording: `test_insert_*_names_the_anchor_heading`
- the replace branch (not the unknown-action fallback) and its bucket:
  `test_replace_section_*`
- the code span around a backticked anchor (`render_helpers.code_span`):
  `test_a_backtick_in_the_anchor_does_not_break_the_line`
- the peer-checkbox format: `test_every_section_action_keeps_the_peer_checkbox_format`
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib import render_helpers  # noqa: E402
from lib.render_md import (  # noqa: E402
    _md_section_for,
    _render_action_md,
    render_instructions_md,
)

TARGET = "Efforts/200 Journal/2026/2026-W13.md"
ANCHOR = "### In my own words"
CONTENT = (
    "### Tomo Review\n"
    "%% tomo-review 2026-W13 %%\n"
    "#### Erledigt\n"
    "- Spec 045 plan ([[2026-03-24]])\n"
    "#### Offen\n"
    "- The rerun path\n"
)


def _insert(**over) -> dict:
    action = {
        "id": "I01",
        "action": "insert_under_marker",
        "target_path": TARGET,
        "anchor": {"type": "heading", "value": ANCHOR},
        "placement": "before",
        "content": CONTENT,
    }
    action.update(over)
    return action


def _replace(**over) -> dict:
    action = {
        "id": "I02",
        "action": "replace_section",
        "target_path": TARGET,
        "anchor": {"type": "heading", "value": "### Tomo Review"},
        "content": CONTENT,
    }
    action.update(over)
    return action


def _fenced_body(md: str) -> tuple[str, str]:
    """The (fence, body) of the single fenced block in a rendered action."""
    lines = md.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("```"))
    fence = lines[start].removesuffix("markdown")
    assert set(fence) == {"`"}, f"the opening fence must be backticks + 'markdown': {lines[start]!r}"
    # CommonMark closes a fence on the first later line that is a run of at
    # least as many backticks — so a shorter run inside the body must not
    # count, and the last line must be the real close.
    closes = [
        i for i, line in enumerate(lines[start + 1:], start + 1)
        if set(line) == {"`"} and len(line) >= len(fence)
    ]
    assert closes == [len(lines) - 1], f"the fence must close once, on the last line: {closes}"
    return fence, "\n".join(lines[start + 1:closes[0]])


# ── the fence ───────────────────────────────────────────────────────────────


def test_insert_content_is_fenced_not_quoted():
    md = _render_action_md(_insert(), {})
    fence, body = _fenced_body(md)
    assert body == CONTENT.rstrip("\n")
    assert "  > " not in md, "the old blockquote rendering leaked through"


def test_replace_content_is_fenced_not_quoted():
    md = _render_action_md(_replace(), {})
    fence, body = _fenced_body(md)
    assert body == CONTENT.rstrip("\n")
    assert "  > " not in md


def test_fence_outgrows_the_longest_backtick_run():
    content = "intro\n````\ncode with a four-backtick fence\n````\n"
    md = _render_action_md(_insert(content=content), {})
    fence, body = _fenced_body(md)
    assert fence == "`````", f"fence must beat the content's longest run, got {fence!r}"
    assert body == content.rstrip("\n")


def test_empty_content_still_renders_a_closed_fence():
    md = _render_action_md(_replace(content=""), {})
    fence, body = _fenced_body(md)
    assert body == ""


# ── the placement wording ───────────────────────────────────────────────────


def test_insert_before_names_the_anchor_heading():
    md = _render_action_md(_insert(placement="before"), {})
    first = md.splitlines()[0]
    assert first == f"### I01 — Insert before `{ANCHOR}` in [[2026-W13]]"
    assert "Insert under" not in md
    assert f"immediately above the heading line `{ANCHOR}`" in md


def test_insert_inside_names_the_anchor_heading():
    md = _render_action_md(_insert(placement="inside"), {})
    first = md.splitlines()[0]
    assert first == f"### I01 — Insert inside `{ANCHOR}` in [[2026-W13]]"
    assert f"as the last lines of the section under `{ANCHOR}`" in md
    assert "next heading of the same or higher level" in md


def test_insert_after_names_the_anchor_heading():
    """`/review` never emits `after` (SDD ADR-3), but the tag-handler path
    may, and the renderer words whatever placement the action carries."""
    md = _render_action_md(_insert(placement="after"), {})
    first = md.splitlines()[0]
    assert first == f"### I01 — Insert after `{ANCHOR}` in [[2026-W13]]"
    assert f"immediately below the heading line `{ANCHOR}`" in md
    assert "above" in md, "after inserts above the section's own body — say so"


def test_insert_keeps_target_and_anchor_lines():
    md = _render_action_md(_insert(), {})
    assert "- **Target:** [[2026-W13]]" in md
    assert f"- **Anchor:** `{ANCHOR}` (heading, placement: before)" in md


# ── replace_section ─────────────────────────────────────────────────────────


def test_replace_section_has_its_own_heading():
    md = _render_action_md(_replace(), {})
    first = md.splitlines()[0]
    assert first == "### I02 — Replace the body of `### Tomo Review` in [[2026-W13]]"
    assert "unknown action" not in md
    assert "- **Target:** [[2026-W13]]" in md
    assert "- **Anchor:** `### Tomo Review` (heading)" in md


def test_replace_section_says_what_is_discarded_and_what_stays():
    md = _render_action_md(_replace(), {})
    assert "next heading of the same or higher level" in md
    assert "heading line itself stays" in md
    assert "- **Replace it with this block:**" in md


def test_replace_section_sits_beside_insert_under_marker():
    assert _md_section_for(_replace()) == _md_section_for(_insert())
    assert _md_section_for(_replace()) == "tag_handler_updates"


def test_replace_section_is_not_listed_as_a_new_file():
    doc = render_instructions_md([_replace()], {"generated": "2026-11-11T00:00:00Z"}, {})
    assert "## New Files" not in doc
    assert "## Tag-Handler Updates" in doc
    assert "(unknown action" not in doc


# ── a backtick in the anchor ────────────────────────────────────────────────


@pytest.mark.parametrize("kind", ["insert_under_marker", "replace_section"])
def test_a_backtick_in_the_anchor_does_not_break_the_line(kind):
    anchor = "## Notes on `git`"
    builder = _insert if kind == "insert_under_marker" else _replace
    md = _render_action_md(builder(anchor={"type": "heading", "value": anchor}), {})
    first = md.splitlines()[0]
    assert f"`` {anchor} ``" in first or f"``{anchor}``" in first, first
    assert f"`{anchor}`" not in first, "a single-backtick span ends at the first backtick"
    anchor_line = next(line for line in md.splitlines() if line.startswith("- **Anchor:**"))
    assert f"`{anchor}`" not in anchor_line


def test_an_anchor_that_starts_with_a_backtick_is_padded():
    anchor = "`code` first"
    md = _render_action_md(_insert(anchor={"type": "heading", "value": anchor}), {})
    assert f"`` {anchor} ``" in md.splitlines()[0]


# ── the peer-checkbox format ────────────────────────────────────────────────


@pytest.mark.parametrize("action", [_insert(), _insert(placement="inside"), _replace()])
def test_every_section_action_keeps_the_peer_checkbox_format(action):
    md = _render_action_md(action, {})
    lines = md.splitlines()
    assert lines[0].startswith(f"### {action['id']} — ")
    assert lines[1] == "- [ ] Applied"


# ── the shared helpers ──────────────────────────────────────────────────────


def test_fence_for_is_at_least_four_and_beats_the_longest_run():
    assert render_helpers.fence_for("plain") == "````"
    assert render_helpers.fence_for("```\ncode\n```") == "````"
    assert render_helpers.fence_for("````\ncode\n````") == "`````"


def test_code_span_pads_only_when_an_edge_is_a_backtick():
    assert render_helpers.code_span("plain") == "`plain`"
    assert render_helpers.code_span("has `one` x") == "``has `one` x``"
    assert render_helpers.code_span("has `one`") == "`` has `one` ``"
    assert render_helpers.code_span("`edge") == "`` `edge ``"
    assert render_helpers.code_span("``two``") == "``` ``two`` ```"

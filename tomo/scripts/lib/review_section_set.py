# review_section_set.py — the mapped sections of one /review delivery as a set, and the actions they compose.
# version: 0.1.0
"""Plan, route and compose the mapped sections of a ``/review`` delivery (spec 046 T5.2, T5.4; PRD
F4-AC1, F4-AC5, F2-AC12; SDD ADR-12).

``plan_existing`` plans every row placed in the note on an existing note's text, ``plan_new_note`` on
the text a new note is built from (None: a plain note), routing to "Tomo Review" a heading the text
lacks, holds twice or holds only inside a multi-line Templater span, unless the user's choice is
``skip``. ``routed_keys`` names those keys for Pass 1. ``review_parts`` gives the "Tomo Review"
sub-parts: analysis rows and routed sections in mapping order, headings display-neutralised.
``splice_blocks`` inserts a new note's blocks at ``SectionPlan.insert_at``.

``compose`` builds the instruction set's actions of an existing note: one per section whose plan is
``insert`` or ``replace`` and whose block holds lines, in mapping order, then the "Tomo Review" action
when there is one; ids ``I01…In`` dense over the emitted actions. ``landed_escapes`` counts the
escapes of the blocks that land as their own block (``insert`` and ``replace``; ``insert`` only for a
new note, whose text is spliced from inserts).

Imports ``review_section_plan``, never ``review_actions`` or ``review_new_note``. No Kado, no clock, no
file I/O.

Design notes: docs/tomo/scripts/lib/review_section_set.md
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from lib import review_section_plan as rsp
from lib.review_sections import REVIEW as ANALYSIS, display_heading
from lib.template_syntax import templater_inner_line_indexes

LANDING = (rsp.INSERT, rsp.REPLACE)


def action_id(n: int) -> str:
    """The ``n``-th action's id, from 1: ``I01``, ``I02``, …"""
    return f"I{n:02d}"


def _placed(rows: Sequence[dict]) -> List[dict]:
    return [r for r in rows if r.get("placement") in rsp.HASHI_PLACEMENT]


def plan_existing(rows: Sequence[dict], text: str, period: str, items: Dict[str, list], *,
                  choices: Optional[Dict[str, str]] = None, off_limits: Sequence[dict] = (),
                  review_at: Optional[int] = None) -> List[rsp.SectionPlan]:
    """Per row placed in the note, mapping order: its plan on an existing note's ``text``."""
    return [rsp.plan_section(r, text, period, items.get(str(r["id"])) or [],
                             choice=(choices or {}).get(str(r["id"])), off_limits=off_limits, review_at=review_at)
            for r in _placed(rows)]


def plan_new_note(rows: Sequence[dict], text: Optional[str], period: str, items: Dict[str, list], *,
                  choices: Optional[Dict[str, str]] = None, off_limits: Sequence[dict] = ()) -> List[rsp.SectionPlan]:
    """Per row placed in the note, mapping order: its plan on the new note's ``text``, routed where it cannot land."""
    inner = templater_inner_line_indexes(text) if text is not None else set()
    out = []
    for r in _placed(rows):
        key = str(r["id"])
        routed = rsp.SKIP if (choices or {}).get(key) == rsp.SKIP else rsp.REVIEW   # answers only a stop
        if text is None:
            p = rsp.SectionPlan(key, routed, rsp.start_marker(key, period), rsp.end_marker(key, period))
            p.lines, p.escaped_lines = rsp.block_lines(items.get(key) or [])
        else:
            p = rsp.plan_section(r, text, period, items.get(key) or [], choice=routed, off_limits=off_limits)
            if p.mode == rsp.INSERT and p.heading_at in inner:
                p.mode = routed                              # the heading exists only once Templater ran
        out.append(p)
    return out


def routed_keys(rows: Sequence[dict], text: Optional[str], period: str, off_limits: Sequence[dict] = ()) -> List[str]:
    """Pass 1: the keys a new note built from ``text`` routes to "Tomo Review"."""
    return [p.key for p in plan_new_note(rows, text, period, {}, off_limits=off_limits) if p.mode == rsp.REVIEW]


def splice_blocks(lines: List[str], inserts: Sequence[Tuple[int, List[str]]]) -> None:
    """Insert every ``(index, lines)``; at one index an earlier insert ends up above a later one."""
    for _, (at, block) in sorted(enumerate(inserts), key=lambda e: (e[1][0], e[0]), reverse=True):
        lines[at:at] = block


def review_parts(rows: Sequence[dict], plans: Sequence[rsp.SectionPlan], items: Dict[str, list]
                 ) -> Tuple[List[Tuple[str, List[List[str]]]], int]:
    """``([(sub-heading, [lines]), ...], escapes)``: analysis rows and routed sections in mapping order, non-empty."""
    routed = {p.key for p in plans if p.mode == rsp.REVIEW}
    parts: List[Tuple[str, List[List[str]]]] = []
    escaped = 0
    for r in rows:
        key = str(r["id"])
        if r.get("placement") == ANALYSIS or key in routed:
            lines, count = rsp.block_lines(items.get(key) or [])
            if lines:
                parts.append((display_heading(r["heading"]), [lines]))
                escaped += count
    return parts, escaped


def _lands(plan: rsp.SectionPlan, modes: Sequence[str] = LANDING) -> bool:
    return plan.mode in modes and bool(plan.lines)


def landed_escapes(plans: Sequence[rsp.SectionPlan], new_note: bool) -> int:
    """The escapes of the blocks that land as their own block: ``insert`` (spliced) for a new note, ``insert`` and
    ``replace`` (their actions) for an existing one."""
    modes = (rsp.INSERT,) if new_note else LANDING
    return sum(p.escaped_lines for p in plans if _lands(p, modes))


def compose(plans: Sequence[rsp.SectionPlan], target_path: str, review_action: Optional[dict] = None) -> List[dict]:
    """The existing note's actions: every landing section in ``plans``' order, then ``review_action`` (given without
    an id); ids dense."""
    actions = [p.action(action_id(n), target_path)
               for n, p in enumerate((p for p in plans if _lands(p)), start=1)]
    if review_action is not None:
        actions.append({"id": action_id(len(actions) + 1), **review_action})
    return actions

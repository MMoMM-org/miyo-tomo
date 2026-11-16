# review_section_report.py — what a /review delivery reports and records of its mapped section plans.
# version: 0.1.0
"""The delivery's readings of the mapped section plans besides the actions (spec 046 T5.5, T6.2; PRD F4-AC4,
F4-AC6, F3-AC4, F3-AC5; SDD ADR-12).

``report`` — per section with lines its key, mode, the row's configured placement, notices, scope level, a stop
with its choices, where a moved block sits, ``lines`` on request; ``record`` — ``{key, mode, placement (Hashi's),
scope_level}`` per section with lines, enums; ``untaken`` — the keys of the user's choices no plan took;
``dropped`` / ``empty`` read the parsed document's ``section_counts``; ``names`` and ``fields`` are the problem and
notice names and the output fields of all that.

Imports ``review_section_plan``, never ``review_actions``, ``review_new_note`` or ``review_section_set``. No Kado,
no clock, no file I/O.

Design notes: docs/tomo/scripts/lib/review_section_report.md
"""
from __future__ import annotations

from typing import Dict, List, Sequence

from lib import review_section_plan as rsp

CHOICE_INVALID = "choice-invalid"                      # a choice no plan took
SECTION_DROPPED, SECTION_EMPTY = "section-dropped", "section-empty"


def report(plans: Sequence[rsp.SectionPlan], *, lines: bool) -> List[dict]:
    """Per section whose block holds lines: what the preview and the delivery output show of it."""
    out: List[dict] = []
    for p in plans:
        if not p.lines:
            continue
        entry: Dict[str, object] = {"key": p.key, "mode": p.mode, "placement": p.placement, "notices": list(p.notices)}
        if p.scope is not None:
            entry["scope_level"] = p.scope["level"]
        if p.stop is not None:
            entry["stop"], entry["choices"] = p.stop, list(p.offers)
        if p.block_at is not None:
            entry["block_at"] = dict(p.block_at)
        if lines:
            entry["lines"] = list(p.lines)
        out.append(entry)
    return out


def record(plans: Sequence[rsp.SectionPlan]) -> List[dict]:
    """``delivered_plan.sections``: per section whose block holds lines, keys and enums only."""
    return [{"key": p.key, "mode": p.mode, "placement": p.hashi_placement,
             "scope_level": p.scope["level"] if p.scope is not None else None} for p in plans if p.lines]


def untaken(plans: Sequence[rsp.SectionPlan], choices: Dict[str, str]) -> List[str]:
    """The keys of ``choices`` no plan took: no such section, or the choice answers no stop of it."""
    by_key = {p.key: p for p in plans}

    def taken(key: str, choice: str) -> bool:
        p = by_key.get(key)
        if p is None:
            return False
        if choice == rsp.CONFIRM_MOVED:
            return rsp.BLOCK_MOVED_CONFIRMED in p.notices
        return p.mode == choice
    return [key for key, choice in choices.items() if not taken(key, choice)]


def dropped(counts: Dict[str, dict]) -> List[dict]:
    """``[{key, added}]`` per unticked section that held anything, Tomo's items or the user's."""
    return [{"key": key, "added": c["added"]} for key, c in counts.items()
            if c.get("ticked") is False and (c["kept"] or c["unticked"] or c["added"])]


def empty(counts: Dict[str, dict]) -> List[str]:
    """The keys of the ticked sections that receive nothing."""
    return [key for key, c in counts.items() if c.get("empty")]


def names(plans: Sequence[rsp.SectionPlan], counts: Dict[str, dict], choices: Dict[str, str]) -> List[str]:
    """The stops of the sections with lines, ``choice-invalid``, their notices, ``section-dropped`` / ``-empty``."""
    out = [p.stop for p in plans if p.stop is not None and p.lines]
    out += [CHOICE_INVALID] if untaken(plans, choices) else []
    out += [n for p in plans if p.lines for n in p.notices]
    return out + [SECTION_DROPPED] * bool(dropped(counts)) + [SECTION_EMPTY] * bool(empty(counts))


def fields(plans: Sequence[rsp.SectionPlan], counts: Dict[str, dict], choices: Dict[str, str], *,
           lines: bool) -> dict:
    """``sections``, ``dropped``, ``empty`` of a mapped plan (none without sections or counts), and
    ``choices_invalid`` when a choice was not taken."""
    out: Dict[str, object] = {}
    if plans or counts:
        out.update(sections=report(plans, lines=lines), dropped=dropped(counts), empty=empty(counts))
    invalid = untaken(plans, choices)
    if invalid:
        out["choices_invalid"] = invalid
    return out

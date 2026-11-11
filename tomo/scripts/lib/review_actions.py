# review_actions.py — the instruction set a /review delivery writes: where the section lands and what it holds.
# version: 0.1.0
"""Build the delivery plan of an approved review (spec 045, T4.1; PRD F4-AC7, F5-AC3 to F5-AC7,
F6-AC3; SDD "the review section and the heading-level rule", ADR-3, ADR-8, ADR-13).

``build_review_plan`` takes the ApprovedReview record (``ParsedDoc.approved_review()``), the
``ReviewSetup``, the ``Target`` (the note's path and text — None when absent — plus whether it
was found by name elsewhere and which duplicate the year subfolder holds) and, for a new note,
the ``Template`` texts, and returns a ``ReviewPlan``: the mode (``insert`` | ``replace`` |
``new-note``), the place, the section as it will land, the count of lines escaped here, the
Templater hint, the problems (``not-approved``, ``approved-line-missing``, ``nothing-to-deliver``,
``place-missing``, ``place-too-deep``, ``heading-renamed``, ``user-heading-collision``) with the
note's headings where the place is at fault, and the actions: one ``insert_under_marker``
(``before`` or ``inside``, never ``after``) when the target holds no marker of this period, one
``replace_section`` on the heading above the marker when it does — whatever that heading's text
— or one ``move_note`` for a new note that waits in the inbox stamped rendered-note/pending-move.
A heading with the review's text but no marker, a marker under an own section, or a marker
under a heading an earlier heading of the same text shadows is a collision: nothing is emitted.
Heading levels come from ``review_config.place_level``; every landed item line runs through
``review_doc.neutralised`` once more (idempotent); ids are stripped; the content ends with one
blank line and depends on nothing but the arguments. ``locate_target`` picks the target among the
configured paths (flat folder first, the duplicate named) and the by-name hits elsewhere.
``build_review_instruction_set`` wraps the actions in the wire envelope.

No Kado, no clock, no file I/O (the wire schema version is read from the schema file).

Design notes: docs/tomo/scripts/lib/review_actions.md
"""
from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from lib import review_config as rc
from lib import review_doc as rd
from lib import review_md
from lib.doc_frontmatter import build_tomo_block, merge_tomo_block_into_markdown
from lib.review_doc_parse import APPROVED_MISSING
from lib.review_vault import TEMPLATER_MARK
from lib.wire_version import wire_schema_version

WIRE_SCHEMA = "instructions.schema.json"
WIRE_TYPE = "tomo-instructions"
ACTION_ID = "I01"
INSERT, REPLACE, NEW_NOTE = "insert", "replace", "new-note"
NOT_APPROVED = "not-approved"
NOTHING_TO_DELIVER = "nothing-to-deliver"
PLACE_MISSING = "place-missing"
PLACE_TOO_DEEP = "place-too-deep"
HEADING_RENAMED = "heading-renamed"
HEADING_COLLISION = "user-heading-collision"
NOTE_DOC_TYPE, NOTE_STATE = "rendered-note", "pending-move"
PLAIN_LEVEL = 2          # the review heading of a plain new note, under its H1 title
_MARKER = "%% tomo-review {period} %%"
_CONTINUATION = "  "

Headings = List[Tuple[int, int, str]]     # (line index, level, text), review_md's shape


def marker_line(period_name: str) -> str:
    """The Obsidian comment that marks Tomo's section of ``period_name`` in the periodic note."""
    return _MARKER.format(period=period_name)


@dataclass(frozen=True)
class Target:
    path: str                                  # the note the section lands in, or the new note's destination
    text: Optional[str] = None                 # None when no note exists there
    moved: bool = False                        # found by name outside the configured paths
    duplicates: List[str] = field(default_factory=list)   # the same name at a later configured path


@dataclass(frozen=True)
class Template:
    raw: Optional[str] = None                  # the configured template's text, None when absent or unreadable
    variant: Optional[str] = None              # the Tomo variant's text, None when absent or unreadable


@dataclass
class ReviewPlan:
    mode: str
    target: str
    target_moved: bool
    duplicates: List[str]
    place: Dict[str, object]
    section_md: str = ""
    escaped_lines: int = 0
    templater_hint: bool = False
    variant_missing: bool = False
    problems: List[str] = field(default_factory=list)
    headings: List[str] = field(default_factory=list)
    actions: List[dict] = field(default_factory=list)
    note_path: Optional[str] = None            # the new note waiting in the inbox
    note_text: Optional[str] = None            # its stamped text

    def preview(self) -> dict:
        """The SDD preview shape; optional keys only when they carry something."""
        out: Dict[str, object] = {
            "mode": self.mode, "target": self.target, "place": dict(self.place), "section_md": self.section_md,
            "escaped_lines": self.escaped_lines, "templater_hint": self.templater_hint,
            "problems": list(self.problems),
        }
        for key, value in (("target_moved", self.target_moved), ("duplicates", list(self.duplicates)),
                           ("variant_missing", self.variant_missing), ("headings", list(self.headings))):
            if value:
                out[key] = value
        return out


# --- the target --------------------------------------------------------------------------

def locate_target(candidates: Sequence[str], texts: Dict[str, Optional[str]],
                  elsewhere: Sequence[str] = ()) -> Target:
    """The target among ``candidates`` (``Period.note_paths`` order) whose text ``texts`` holds, the
    later existing candidates as duplicates; else the first by-name hit ``elsewhere`` (moved); else
    a new note at the first candidate."""
    existing = [p for p in candidates if texts.get(p) is not None]
    if existing:
        return Target(existing[0], texts[existing[0]], False, existing[1:])
    moved = sorted(p for p in elsewhere if texts.get(p) is not None)
    if moved:
        return Target(moved[0], texts[moved[0]], True, [])
    return Target(candidates[0], None)


# --- the landed text ---------------------------------------------------------------------

def item_lines(item: dict) -> Tuple[List[str], int]:
    """``(landed lines, escaped count)`` of one kept item: the bullet line, continuation lines indented;
    ids stripped, every line escaped once through ``review_doc.neutralised``; ``[]`` for an empty item."""
    raw = [str(item.get("text") or ""), *(str(ln) for ln in item.get("lines") or [])]
    cleaned = [rd.ID_PATTERN.sub("", ln).strip() for ln in raw]
    while cleaned and not cleaned[0]:
        cleaned.pop(0)
    while cleaned and not cleaned[-1]:
        cleaned.pop()
    out: List[str] = []
    escaped = 0
    for index, line in enumerate(cleaned):
        safe = rd.neutralised(line) if line else line
        escaped += safe != line
        out.append(("- " if index == 0 else _CONTINUATION) + safe if safe else "")
    return out, escaped


def landed_groups(review: dict) -> Tuple[List[Tuple[str, List[List[str]]]], int]:
    """``([(group label, [item lines, ...]), ...], escaped count)``: groups in document order with at
    least one non-empty kept item; the ``unknown`` group has no label and is left out."""
    words = rd.labels(str(review.get("language") or ""))
    groups: List[Tuple[str, List[List[str]]]] = []
    escaped = 0
    for group, items in (review.get("groups") or {}).items():
        if group not in rd.GROUPS:
            continue
        landed: List[List[str]] = []
        for item in items or []:
            lines, count = item_lines(item)
            if lines:
                landed.append(lines)
                escaped += count
        if landed:
            groups.append((words[group], landed))
    return groups, escaped


def render_section(heading: str, level: int, period_name: str, groups: Sequence[Tuple[str, List[List[str]]]]
                   ) -> Tuple[str, str]:
    """``(section with its heading, body only)``; both end with one ``\\n`` — split on ``\\n`` by Hashi,
    that is the one blank line after the section."""
    body = [marker_line(period_name)]
    for label, items in groups:
        body.append(f"{'#' * (level + 1)} {label}")
        for lines in items:
            body.extend(lines)
    body_md = "\n".join(body) + "\n"
    return f"{'#' * level} {heading}\n{body_md}", body_md


# --- the target's structure ----------------------------------------------------------------

def _split_lines(text: str) -> Tuple[List[str], bool]:
    """``(lines, trailing newline)``: Hashi's ``content.split("\\n")`` without the element the final newline makes."""
    lines = text.split("\n")
    trailing = text.endswith("\n")
    if trailing:
        lines.pop()
    return lines, trailing


def _body_lines(lines: List[str]) -> Tuple[int, List[str]]:
    """``(offset, body lines)``: the lines after the frontmatter, if there is one."""
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return index + 1, lines[index + 1:]
    return 0, lines


def _marker_index(lines: List[str], marker: str) -> Optional[int]:
    fence = None
    for index, line in enumerate(lines):
        before = fence
        fence, _ = review_md.fence_state(fence, line)
        if before is None and fence is None and line.strip() == marker:
            return index
    return None


def _first(headings: Headings, text: str) -> Optional[Tuple[int, int, str]]:
    """The heading Hashi resolves ``text`` to: the first with that text."""
    return next((h for h in headings if h[2] == text), None)


def _refuse(plan: ReviewPlan, problem: str, headings: Headings) -> ReviewPlan:
    plan.problems.append(problem)
    plan.headings = [text for _, _, text in headings]
    return plan


def _level_or_refuse(plan: ReviewPlan, placement: str, anchor_level: int, headings: Headings) -> Optional[int]:
    try:
        return rc.place_level(placement, anchor_level)
    except rc.PlaceRefused:
        _refuse(plan, PLACE_TOO_DEEP, headings)
        return None


def _insertion(plan: ReviewPlan, setup: rc.ReviewSetup, anchor: str, headings: Headings, n_lines: int
               ) -> Optional[Tuple[int, int]]:
    """``(level, line index)`` of an insert at ``anchor``; None with the problem recorded."""
    found = _first(headings, anchor)
    if found is None:
        _refuse(plan, PLACE_MISSING, headings)
        return None
    if setup.placement == rc.INSIDE and anchor in setup.own_sections:
        _refuse(plan, HEADING_COLLISION, headings)
        return None
    level = _level_or_refuse(plan, setup.placement, found[1], headings)
    if level is None:
        return None
    if setup.placement == rc.BEFORE:
        return level, found[0]
    return level, review_md.section_end((headings, []), headings.index(found), n_lines)


# --- the plan ----------------------------------------------------------------------------

def _gate(review: dict, groups: list) -> Optional[str]:
    if APPROVED_MISSING in (review.get("warnings") or []):
        return APPROVED_MISSING
    if not review.get("approved"):
        return NOT_APPROVED
    if not groups:
        return NOTHING_TO_DELIVER
    return None


def build_review_plan(review: dict, setup: rc.ReviewSetup, target: Target, template: Optional[Template] = None,
                      *, anchor: Optional[str] = None, run_id: str, generated: str) -> ReviewPlan:
    """The plan for ``review`` into ``target``; ``anchor`` overrides the setup's (``--place-anchor``)."""
    anchor = anchor or setup.anchor
    plan = ReviewPlan(INSERT if target.text is not None else NEW_NOTE, target.path, target.moved,
                      list(target.duplicates), {"anchor": anchor, "placement": setup.placement})
    groups, plan.escaped_lines = landed_groups(review)
    gate = _gate(review, groups)
    if gate is not None:
        plan.problems.append(gate)
        return plan
    period = str(review.get("period") or "")
    if target.text is None:
        return _new_note(plan, setup, template or Template(), anchor, period, groups, run_id, generated)
    return _existing_note(plan, setup, target, anchor, period, groups)


def _existing_note(plan: ReviewPlan, setup: rc.ReviewSetup, target: Target, anchor: str, period: str,
                   groups: list) -> ReviewPlan:
    _, lines = _body_lines(_split_lines(target.text or "")[0])
    headings, _ = review_md.headings(lines)
    marker_at = _marker_index(lines, marker_line(period))
    if marker_at is not None:
        above = next((h for h in reversed(headings) if h[0] < marker_at), None)
        if above is None:
            return _refuse(plan, PLACE_MISSING, headings)
        _, level, text = above
        if text in setup.own_sections or _first(headings, text) != above:
            return _refuse(plan, HEADING_COLLISION, headings)
        if _level_or_refuse(plan, rc.BEFORE, level, headings) is None:
            plan.mode = REPLACE
            return plan
        plan.mode = REPLACE
        plan.place = {"anchor": text, "placement": REPLACE, "level": level}
        if text != setup.heading:
            plan.problems.append(HEADING_RENAMED)
        plan.section_md, body = render_section(text, level, period, groups)
        plan.actions = [{"id": ACTION_ID, "action": "replace_section", "target_path": target.path,
                         "anchor": {"type": "heading", "value": text}, "content": body}]
        return plan
    if _first(headings, setup.heading) is not None:
        return _refuse(plan, HEADING_COLLISION, headings)
    placed = _insertion(plan, setup, anchor, headings, len(lines))
    if placed is None:
        return plan
    level, _ = placed
    plan.place = {"anchor": anchor, "placement": setup.placement, "level": level}
    plan.section_md, _ = render_section(setup.heading, level, period, groups)
    plan.actions = [{"id": ACTION_ID, "action": "insert_under_marker", "target_path": target.path,
                     "anchor": {"type": "heading", "value": anchor}, "placement": setup.placement,
                     "content": plan.section_md}]
    return plan


def _template_choice(setup: rc.ReviewSetup, template: Template) -> Tuple[Optional[str], bool, bool]:
    """``(text, templater_hint, variant_missing)`` by ADR-8; text None means a plain note."""
    if setup.template is None or template.raw is None:
        return None, False, False
    if setup.template_variant is not None and template.variant is not None:
        return template.variant, TEMPLATER_MARK in template.variant, False
    return template.raw, TEMPLATER_MARK in template.raw, setup.template_variant is not None


def _new_note(plan: ReviewPlan, setup: rc.ReviewSetup, template: Template, anchor: str, period: str,
              groups: list, run_id: str, generated: str) -> ReviewPlan:
    text, plan.templater_hint, plan.variant_missing = _template_choice(setup, template)
    name = posixpath.basename(plan.target)
    name = name[:-3] if name.endswith(".md") else name
    if text is None:
        level = PLAIN_LEVEL
        plan.place = {"anchor": None, "placement": setup.placement, "level": level}
        plan.section_md, _ = render_section(setup.heading, level, period, groups)
        note = f"# {name}\n\n{plan.section_md}"
    else:
        all_lines, trailing = _split_lines(text)
        offset, lines = _body_lines(all_lines)
        headings, _ = review_md.headings(lines)
        placed = _insertion(plan, setup, anchor, headings, len(lines))
        if placed is None:
            return plan
        level, at = placed
        plan.place = {"anchor": anchor, "placement": setup.placement, "level": level}
        plan.section_md, _ = render_section(setup.heading, level, period, groups)
        # Hashi's spliceLines: the block's lines, trailing blank included, at the index
        all_lines[offset + at:offset + at] = plan.section_md.split("\n")
        note = "\n".join(all_lines) + ("\n" if trailing else "")
    block = build_tomo_block(NOTE_DOC_TYPE, NOTE_STATE, run_id)
    block["updated_at"] = generated
    plan.note_text = merge_tomo_block_into_markdown(note, block)
    plan.note_path = setup.inbox_path(f"{name}.md")
    plan.actions = [{"id": ACTION_ID, "action": "move_note", "source": plan.note_path, "destination": plan.target,
                     "title": name, "rendered_file": f"{name}.md", "source_inbox_item": None}]
    return plan


# --- the wire ----------------------------------------------------------------------------

def build_review_instruction_set(plan: ReviewPlan, *, stem: str, generated: str, profile: Optional[str]) -> dict:
    """The instruction set document for ``plan``; ``md_peer`` is ``<stem>_instructions``."""
    return {
        "schema_version": wire_schema_version(WIRE_SCHEMA),
        "type": WIRE_TYPE,
        "generated": generated,
        "profile": profile,
        "md_peer": f"{stem}_instructions",
        "actions": [dict(action) for action in plan.actions],
    }

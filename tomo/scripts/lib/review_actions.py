# review_actions.py — the instruction set a /review delivery writes: where the section lands and what it holds.
# version: 0.4.0
"""Build the delivery plan of an approved review (spec 045, T4.1; PRD F4-AC7, F5-AC3 to F5-AC7,
F6-AC3; SDD "the review section and the heading-level rule", ADR-3, ADR-8, ADR-13).

``build_review_plan`` takes the ApprovedReview record (``ParsedDoc.approved_review()``), the
``ReviewSetup``, the ``Target`` (the note's path and text — None when absent — plus whether it
was found by name elsewhere and which duplicate the year subfolder holds) and, for a new note,
the ``Template`` texts, and returns a ``ReviewPlan``: the mode (``insert`` | ``replace`` |
``new-note``), the place, the section as it will land, the count of lines escaped here, the
count of kept items that cannot land (``unlanded``: under a heading the parser did not know),
the Templater hint, the notice ``template_unmergeable`` (the template's frontmatter could not
take the stamp — a ``tomo:`` key already there or an unclosed fence — so the plain note was
built instead, with the merge helper's reason), the problems (``not-approved``, ``approved-line-missing``,
``nothing-to-deliver``, ``unlanded-items``, ``place-missing``, ``place-too-deep``,
``heading-renamed``, ``user-heading-collision``) with the note's headings where the place is at
fault, and the actions: one ``insert_under_marker`` (``before`` or ``inside``, never ``after``)
when the target holds no marker of this period, one ``replace_section`` on the heading above the
marker when it does — whatever that heading's text — or one ``move_note`` for a new note that
waits in the inbox stamped rendered-note/pending-move. The marker counts at column 0 only
(trailing whitespace tolerated); an indented copy is an item's continuation line. A heading
with the review's text but no marker, a marker under an own section, or a marker under a
heading an earlier heading of the same text shadows is a collision: nothing is emitted. A refused replace (the marker proves the
rerun) reports mode ``replace`` and the heading found above the marker as the place. Every heading
matched or emitted is the heading as Hashi's parser reads the file (``hashi_headings``: closing
hashes kept, every line opening with ``` or ~~~ toggles a fence, frontmatter included, the file
split on ``\\n`` only, ECMAScript's whitespace set ``JS_WS`` and line terminators — a CRLF line is
no heading); a configured anchor, the review heading and the own sections match a note heading
with or without closing hashes, the emitted anchor value is Hashi's text. Heading levels come
from ``review_config.place_level``; every
landed item line runs through ``review_doc.neutralised`` once more (idempotent); ids are
stripped; the content ends with one blank line and depends on nothing but the arguments.
``locate_target`` picks the target among the configured paths (flat folder first, the duplicate
named) and the by-name hits elsewhere. ``build_review_instruction_set`` wraps the actions in the
wire envelope.

No Kado, no clock, no file I/O (the wire schema version is read from the schema file).

Design notes: docs/tomo/scripts/lib/review_actions.md
"""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from lib import review_config as rc
from lib import review_doc as rd
from lib import review_md
from lib.doc_frontmatter import FrontmatterMergeError, build_tomo_block, merge_tomo_block_into_markdown
from lib.review_doc_parse import APPROVED_MISSING
from lib.review_vault import TEMPLATER_MARK
from lib.wire_version import wire_schema_version

WIRE_SCHEMA = "instructions.schema.json"
WIRE_TYPE = "tomo-instructions"
ACTION_ID = "I01"
INSERT, REPLACE, NEW_NOTE = "insert", "replace", "new-note"
NOT_APPROVED = "not-approved"
NOTHING_TO_DELIVER = "nothing-to-deliver"
UNLANDED_ITEMS = "unlanded-items"
PLACE_MISSING = "place-missing"
PLACE_TOO_DEEP = "place-too-deep"
HEADING_RENAMED = "heading-renamed"
HEADING_COLLISION = "user-heading-collision"
NOTE_DOC_TYPE, NOTE_STATE = "rendered-note", "pending-move"
PLAIN_LEVEL = 2          # the review heading of a plain new note, under its H1 title
_MARKER = "%% tomo-review {period} %%"
_CONTINUATION = "  "
# ECMAScript's `\s` and `String.prototype.trim()` set, as a literal: WhiteSpace (U+0009, U+000B, U+000C,
# U+FEFF, Unicode Zs) + LineTerminator (U+000A, U+000D, U+2028, U+2029). Python's `\s`/`str.strip()`
# differ (U+001C-001F and U+0085 in, U+FEFF out), so the mirror spells the set out.
JS_WS = ("\t\v\f﻿              "
         "  　\n\r  ")
_JS_LINE_TERMINATORS = "\n\r  "                  # what ECMAScript's `.` never matches
_JS_S = f"[{re.escape(JS_WS)}]"
_HASHI_FENCE_RE = re.compile(rf"^{_JS_S}*(?:```|~~~)")  # Hashi markdownStructure.ts CODE_FENCE_RE
_HASHI_HEADING_RE = re.compile(                           # Hashi markdownStructure.ts HEADING_RE: `.` and `$`
    rf"^(#{{1,6}}){_JS_S}+([^{re.escape(_JS_LINE_TERMINATORS)}]*)\Z")   # as ECMAScript reads them
_CLOSING_HASHES_RE = re.compile(r"[ \t]+#+$")

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
    unlanded: int = 0                          # kept items under an unknown heading: they cannot land
    templater_hint: bool = False
    variant_missing: bool = False
    template_unmergeable: Optional[str] = None  # the template could not take the stamp: the reason; plain note built
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
                           ("unlanded", self.unlanded), ("variant_missing", self.variant_missing),
                           ("template_unmergeable", self.template_unmergeable), ("headings", list(self.headings))):
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


def landed_groups(review: dict) -> Tuple[List[Tuple[str, List[List[str]]]], int, int]:
    """``([(group label, [item lines, ...]), ...], escaped count, unlanded count)``: groups in document
    order with at least one non-empty kept item; a group outside ``review_doc.GROUPS`` has no label,
    its non-empty kept items are counted as unlanded and left out."""
    words = rd.labels(str(review.get("language") or ""))
    groups: List[Tuple[str, List[List[str]]]] = []
    escaped = 0
    unlanded = 0
    for group, items in (review.get("groups") or {}).items():
        landed: List[List[str]] = []
        for item in items or []:
            lines, count = item_lines(item)
            if lines:
                landed.append(lines)
                escaped += count
        if group not in rd.GROUPS:
            unlanded += len(landed)
        elif landed:
            groups.append((words[group], landed))
    return groups, escaped, unlanded


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


def fenced_mask(lines: Sequence[str]) -> List[bool]:
    """Per line, whether Hashi's ``fencedLineMask`` marks it: every line opening with ``` or ~~~
    toggles the fence and is marked itself."""
    mask: List[bool] = []
    fenced = False
    for line in lines:
        if _HASHI_FENCE_RE.match(line):
            fenced = not fenced
            mask.append(True)
        else:
            mask.append(fenced)
    return mask


def hashi_headings(lines: Sequence[str]) -> Headings:
    """``(line index, level, text)`` of every heading as Hashi's ``parseHeadings`` reads these lines:
    the text after the hashes, trimmed by ECMAScript's set, closing hashes kept; a line holding a
    ``\\r``, U+2028 or U+2029 is no heading; fenced lines skipped."""
    fenced = fenced_mask(lines)
    found: Headings = []
    for index, line in enumerate(lines):
        if fenced[index]:
            continue
        match = _HASHI_HEADING_RE.match(line)
        if match:
            found.append((index, len(match.group(1)), match.group(2).strip(JS_WS)))
    return found


def bare(text: str) -> str:
    """``text`` without closing hashes and trailing whitespace: how two headings are compared."""
    return _CLOSING_HASHES_RE.sub("", text.rstrip())


def _marker_index(lines: List[str], marker: str) -> Optional[int]:
    """The first unfenced line that is ``marker`` at column 0, trailing whitespace tolerated; an
    indented copy (an item's continuation line) is not the marker."""
    fenced = fenced_mask(lines)
    return next((i for i, line in enumerate(lines) if not fenced[i] and line.rstrip() == marker), None)


def _first(headings: Headings, text: str) -> Optional[Tuple[int, int, str]]:
    """The first heading that is ``text`` with or without closing hashes; its own text is what Hashi
    resolves exactly to the same heading."""
    wanted = bare(text)
    return next((h for h in headings if bare(h[2]) == wanted), None)


def _resolved(headings: Headings, value: str) -> Optional[Tuple[int, int, str]]:
    """The heading Hashi resolves the anchor ``value`` to: the first whose text equals it exactly."""
    return next((h for h in headings if h[2] == value), None)


def _own(setup: rc.ReviewSetup, text: str) -> bool:
    wanted = bare(text)
    return any(bare(own) == wanted for own in setup.own_sections)


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
               ) -> Optional[Tuple[str, int, int]]:
    """``(the heading's text as Hashi reads it, level, line index)`` of an insert at ``anchor``; None
    with the problem recorded."""
    found = _first(headings, anchor)
    if found is None:
        _refuse(plan, PLACE_MISSING, headings)
        return None
    if setup.placement == rc.INSIDE and _own(setup, found[2]):
        _refuse(plan, HEADING_COLLISION, headings)
        return None
    level = _level_or_refuse(plan, setup.placement, found[1], headings)
    if level is None:
        return None
    if setup.placement == rc.BEFORE:
        return found[2], level, found[0]
    return found[2], level, review_md.section_end((headings, []), headings.index(found), n_lines)


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
    groups, plan.escaped_lines, plan.unlanded = landed_groups(review)
    gate = _gate(review, groups)
    if gate is not None:
        plan.problems.append(gate)
    elif target.text is None:
        _new_note(plan, setup, template or Template(), anchor, str(review.get("period") or ""), groups,
                  run_id, generated)
    else:
        _existing_note(plan, setup, target, anchor, str(review.get("period") or ""), groups)
    if plan.unlanded:
        plan.problems.append(UNLANDED_ITEMS)
    return plan


def _existing_note(plan: ReviewPlan, setup: rc.ReviewSetup, target: Target, anchor: str, period: str,
                   groups: list) -> ReviewPlan:
    lines, _ = _split_lines(target.text or "")
    headings = hashi_headings(lines)
    marker_at = _marker_index(lines, marker_line(period))
    if marker_at is not None:
        plan.mode = REPLACE                    # the marker proves the rerun; a refusal reports what it found
        above = next((h for h in reversed(headings) if h[0] < marker_at), None)
        if above is None:
            plan.place = {"anchor": None, "placement": REPLACE, "level": None}
            return _refuse(plan, PLACE_MISSING, headings)
        _, level, text = above
        plan.place = {"anchor": text, "placement": REPLACE, "level": level}
        if _own(setup, text) or _resolved(headings, text) != above:
            return _refuse(plan, HEADING_COLLISION, headings)
        if _level_or_refuse(plan, rc.BEFORE, level, headings) is None:
            return plan
        if bare(text) != bare(setup.heading):
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
    value, level, _ = placed
    plan.place = {"anchor": value, "placement": setup.placement, "level": level}
    plan.section_md, _ = render_section(setup.heading, level, period, groups)
    plan.actions = [{"id": ACTION_ID, "action": "insert_under_marker", "target_path": target.path,
                     "anchor": {"type": "heading", "value": value}, "placement": setup.placement,
                     "content": plan.section_md}]
    return plan


def _template_choice(setup: rc.ReviewSetup, template: Template) -> Tuple[Optional[str], bool, bool]:
    """``(text, templater_hint, variant_missing)`` by ADR-8; text None means a plain note."""
    if setup.template is None or template.raw is None:
        return None, False, False
    if setup.template_variant is not None and template.variant is not None:
        return template.variant, TEMPLATER_MARK in template.variant, False
    return template.raw, TEMPLATER_MARK in template.raw, setup.template_variant is not None


def _plain_note(plan: ReviewPlan, setup: rc.ReviewSetup, name: str, period: str, groups: list) -> str:
    """The note without a template: the title as H1, the review section at ``PLAIN_LEVEL``."""
    plan.place = {"anchor": None, "placement": setup.placement, "level": PLAIN_LEVEL}
    plan.section_md, _ = render_section(setup.heading, PLAIN_LEVEL, period, groups)
    return f"# {name}\n\n{plan.section_md}"


def _templated_note(plan: ReviewPlan, setup: rc.ReviewSetup, text: str, anchor: str, period: str, groups: list
                    ) -> Optional[str]:
    """The template ``text`` with the section placed by the before/inside rule; None with the problem recorded."""
    lines, trailing = _split_lines(text)
    placed = _insertion(plan, setup, anchor, hashi_headings(lines), len(lines))
    if placed is None:
        return None
    value, level, at = placed
    plan.place = {"anchor": value, "placement": setup.placement, "level": level}
    plan.section_md, _ = render_section(setup.heading, level, period, groups)
    # Hashi's spliceLines: the block's lines, trailing blank included, at the index
    lines[at:at] = plan.section_md.split("\n")
    return "\n".join(lines) + ("\n" if trailing else "")


def _new_note(plan: ReviewPlan, setup: rc.ReviewSetup, template: Template, anchor: str, period: str,
              groups: list, run_id: str, generated: str) -> ReviewPlan:
    text, plan.templater_hint, plan.variant_missing = _template_choice(setup, template)
    name = posixpath.basename(plan.target)
    name = name[:-3] if name.endswith(".md") else name
    block = build_tomo_block(NOTE_DOC_TYPE, NOTE_STATE, run_id)
    block["updated_at"] = generated
    if text is None:
        plan.note_text = merge_tomo_block_into_markdown(_plain_note(plan, setup, name, period, groups), block)
    else:
        note = _templated_note(plan, setup, text, anchor, period, groups)
        if note is None:
            return plan
        try:
            plan.note_text = merge_tomo_block_into_markdown(note, block)
        except FrontmatterMergeError as error:
            # the template's frontmatter cannot take the stamp: the plain note, as a missing template yields
            plan.template_unmergeable = str(error)
            plan.templater_hint = False
            plan.note_text = merge_tomo_block_into_markdown(_plain_note(plan, setup, name, period, groups), block)
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

# review_actions.py — the instruction set a /review delivery writes: where the section lands and what it holds.
# version: 0.6.1
"""Build the delivery plan of an approved review (spec 045; PRD F4-AC7, F5-AC3 to F5-AC7,
F6-AC3; SDD "the review section and the heading-level rule", ADR-3, ADR-8, ADR-13).

``build_review_plan`` takes the ApprovedReview record (``ParsedDoc.approved_review()``), the
``ReviewSetup``, the ``Target`` (the note's path and text — None when absent — plus whether it
was found by name elsewhere and which duplicate the year subfolder holds) and, for a new note,
the ``Template`` texts, and returns a ``ReviewPlan``: the mode (``insert`` | ``replace`` |
``new-note``), the place, the section as it will land, the count of lines escaped here, the
count of kept items that cannot land (``unlanded``: under a heading the parser did not know),
the Templater hint, the notice ``template_unmergeable`` (the template's frontmatter could not
take the stamp — a ``tomo:`` key already there or an unclosed fence — so the plain note was
built instead, with the merge helper's reason), the problems (``not-approved``,
``approved-line-missing``, ``nothing-to-deliver``, ``unlanded-items``, ``place-missing``,
``place-too-deep``, ``heading-renamed``, ``user-heading-collision``) with the note's headings
where the place is at fault, and the actions: one ``insert_under_marker`` (``before`` or ``inside``, never ``after``)
when the target holds no marker of this period, one ``replace_section`` on the heading above the
marker when it does — whatever that heading's text — or one ``move_note`` for a new note that
waits in the inbox stamped rendered-note/pending-move. The marker counts at column 0 only
(trailing whitespace tolerated); an indented copy is an item's continuation line. A heading
with the review's text but no marker, a marker under an own section, or a marker under a
heading an earlier heading of the same text shadows is a collision: nothing is emitted. A
refused replace (the marker proves the rerun) reports mode ``replace`` and the heading found
above the marker as the place. Every heading matched or emitted is the heading as Hashi's parser
reads the file (``review_hashi_text``); a configured anchor, the review heading and the own
sections match a note heading with or without closing hashes, the emitted anchor value is Hashi's
text. Heading levels come from ``review_config.place_level``; every landed item line is
``review_hashi_text.item_lines``' (escaped once more, idempotent; ids stripped); the content ends
with one blank line and depends on nothing but the arguments.

``locate_target`` picks the target among the configured paths (flat folder first, the duplicate
named) and the by-name hits elsewhere. ``pick_headings`` names the headings a heading pick
chooses from without a refusal (the target note's, or the chosen template's for a new note) —
the list a resume of a delivery begun with ``--place-anchor`` offers again.
``build_review_instruction_set`` wraps the actions in the wire envelope. Mapped rows (spec 046
T5.2): ``ReviewPlan.sections`` (``choices`` answer stops), analysis and routed sub-parts in "Tomo
Review", blocks spliced into a new note, ``landing-off-limits``, ``review-section-kept``. The new
note's text is composed by ``review_new_note``; imports go one way: this module ->
``review_new_note`` -> ``review_section_plan`` -> ``review_hashi_text``.

No Kado, no clock, no file I/O (the wire schema version is read from the schema file).

Design notes: docs/tomo/scripts/lib/review_actions.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from lib import review_config as rc
from lib import review_doc as rd
from lib import review_hashi_text as rht
from lib import review_md
from lib import review_new_note as rnn
from lib import review_section_plan as rsp
from lib.doc_frontmatter import FrontmatterMergeError
from lib.review_doc_parse import APPROVED_MISSING, SECTION_CHECKBOX_MISSING
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
PLAIN_LEVEL = 2          # the review heading of a plain new note, under its H1 title


@dataclass(frozen=True)
class Target:
    path: str                                  # the note the section lands in, or the new note's destination
    text: Optional[str] = None                 # None when no note exists there
    moved: bool = False                        # found by name outside the configured paths
    duplicates: List[str] = field(default_factory=list)   # the same name at a later configured path


@dataclass(frozen=True)
class _Mapped:
    """The mapped rows' share of the approved review, as the section planners take it."""
    items: Dict[str, list]                     # kept items per configured row key
    choices: Dict[str, str]                    # the user's answers to section stops
    escaped: int                               # the groups' escapes: the base a re-plan starts from


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
    sections: List[rsp.SectionPlan] = field(default_factory=list)   # per mapped row placed in the note
    notices: List[str] = field(default_factory=list)                # spec 046 notices, names only

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

def landed_groups(review: dict) -> Tuple[List[Tuple[str, List[List[str]]]], int, int]:
    """``([(group label, [item lines, ...]), ...], escaped count, unlanded count)``: groups in document
    order with at least one non-empty kept item; a group outside ``review_doc.GROUPS`` has no label,
    its non-empty kept items are counted as unlanded and left out."""
    words = rd.labels(str(review.get("language") or ""))
    groups: List[Tuple[str, List[List[str]]]] = []
    escaped = unlanded = 0
    for group, items in (review.get("groups") or {}).items():
        landed: List[List[str]] = []
        for item in items or []:
            lines, count = rht.item_lines(item)
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
    body = [rht.marker_line(period_name)]
    for label, items in groups:
        body.append(f"{'#' * (level + 1)} {label}")
        for lines in items:
            body.extend(lines)
    body_md = "\n".join(body) + "\n"
    return f"{'#' * level} {heading}\n{body_md}", body_md


# --- the target's headings ----------------------------------------------------------------

def _first(headings: rht.Headings, text: str) -> Optional[Tuple[int, int, str]]:
    """The first heading that is ``text`` with or without closing hashes; its own text is what Hashi
    resolves exactly to the same heading."""
    wanted = rht.bare(text)
    return next((h for h in headings if rht.bare(h[2]) == wanted), None)


def _resolved(headings: rht.Headings, value: str) -> Optional[Tuple[int, int, str]]:
    """The heading Hashi resolves the anchor ``value`` to: the first whose text equals it exactly."""
    return next((h for h in headings if h[2] == value), None)


def _own(setup: rc.ReviewSetup, text: str) -> bool:
    wanted = rht.bare(text)
    return any(rht.bare(own) == wanted for own in setup.own_sections)


def _refuse(plan: ReviewPlan, problem: str, headings: rht.Headings) -> ReviewPlan:
    plan.problems.append(problem)
    plan.headings = [text for _, _, text in headings]
    return plan


def _level_or_refuse(plan: ReviewPlan, placement: str, anchor_level: int, headings: rht.Headings) -> Optional[int]:
    try:
        return rc.place_level(placement, anchor_level)
    except rc.PlaceRefused:
        _refuse(plan, PLACE_TOO_DEEP, headings)
        return None


def _insertion(plan: ReviewPlan, setup: rc.ReviewSetup, anchor: str, headings: rht.Headings, text: str
               ) -> Optional[Tuple[str, int, int]]:
    """``(Hashi's heading text, level, line index)`` of an insert at ``anchor`` into ``text``; None on a problem."""
    found = _first(headings, anchor)
    if found is None:
        _refuse(plan, PLACE_MISSING, headings)
        return None
    if setup.off_limits and rsp.place_off_limits(text, anchor, setup.placement, setup.off_limits) is not None:
        plan.problems.append(rsp.STOPS[rsp.OFF_LIMITS_LANDING])   # "Tomo Review" and its sub-parts would land off limits
        return None
    if setup.placement == rc.INSIDE and _own(setup, found[2]):
        _refuse(plan, HEADING_COLLISION, headings)
        return None
    level = _level_or_refuse(plan, setup.placement, found[1], headings)
    if level is None:
        return None
    if setup.placement == rc.BEFORE:
        return found[2], level, found[0]
    n_lines = len(rht.split_lines(text)[0])
    return found[2], level, review_md.section_end((headings, []), headings.index(found), n_lines)


# --- the plan ----------------------------------------------------------------------------

def _gate(review: dict, groups: list) -> Optional[str]:
    warnings = review.get("warnings") or ()
    unreadable = next((w for w in (APPROVED_MISSING, SECTION_CHECKBOX_MISSING) if w in warnings), None)
    if unreadable is not None:
        return unreadable                       # a document the parser cannot read without guessing
    if not review.get("approved"):
        return NOT_APPROVED
    if not groups:
        return NOTHING_TO_DELIVER
    return None


def pick_headings(setup: rc.ReviewSetup, target: Target, template: Optional[rnn.Template] = None) -> List[str]:
    """The headings a heading pick chooses from, as a place problem names them: the target note's, else the
    chosen template's for a new note (as ``review_new_note.template_choice`` picks it), none for a plain note."""
    text = target.text
    if text is None:
        text = rnn.template_choice(setup, template or rnn.Template())[0]
    if text is None:
        return []
    return [heading for _, _, heading in rht.hashi_headings(rht.split_lines(text)[0])]


def build_review_plan(review: dict, setup: rc.ReviewSetup, target: Target, template: Optional[rnn.Template] = None,
                      *, anchor: Optional[str] = None, choices: Optional[Dict[str, str]] = None, run_id: str,
                      generated: str) -> ReviewPlan:
    """The plan for ``review`` into ``target``; ``anchor`` overrides the setup's (``--place-anchor``)."""
    anchor = anchor or setup.anchor
    plan = ReviewPlan(INSERT if target.text is not None else NEW_NOTE, target.path, target.moved,
                      list(target.duplicates), {"anchor": anchor, "placement": setup.placement})
    every, keys = review.get("groups") or {}, {str(r.get("id")) for r in setup.sections}
    groups, plan.escaped_lines, plan.unlanded = landed_groups({**review, "groups": {
        k: v for k, v in every.items() if k not in keys}})
    mapped = _Mapped({k: v for k, v in every.items() if k in keys}, choices or {}, plan.escaped_lines)
    sections_with_lines = [k for k, v in mapped.items.items() if rsp.block_lines(v)[0]]
    gate = _gate(review, groups or sections_with_lines)
    period = str(review.get("period") or "")
    if gate is not None:
        plan.problems.append(gate)
    elif target.text is None:
        _new_note(plan, setup, template or rnn.Template(), anchor, period, groups, run_id, generated, mapped)
    else:
        _existing_note(plan, setup, target, anchor, period, groups, mapped)
    if plan.unlanded:
        plan.problems.append(UNLANDED_ITEMS)
    return plan


def _sectioned(plan: ReviewPlan, setup: rc.ReviewSetup, text: Optional[str], period: str, groups: list,
               mapped: _Mapped, new_note: bool, review_at: Optional[int] = None) -> list:
    """Plans the mapped rows into ``plan.sections`` (a new "Tomo Review" at ``review_at``, existing note only);
    returns the "Tomo Review" content: analysis rows and routed sections, then ``groups``."""
    if not setup.sections:
        return groups
    if new_note:
        plan.sections = rsp.plan_new_note(setup.sections, text, period, mapped.items, choices=mapped.choices,
                                          off_limits=setup.off_limits)
    else:
        plan.sections = rsp.plan_existing(setup.sections, text, period, mapped.items, choices=mapped.choices,
                                          off_limits=setup.off_limits, review_at=review_at)
    parts, escaped = rsp.review_parts(setup.sections, plan.sections, mapped.items)
    if new_note:                               # the inserts are spliced into the new note: their escapes land
        escaped += sum(p.escaped_lines for p in plan.sections if p.mode == rsp.INSERT)
    plan.escaped_lines = mapped.escaped + escaped
    return parts + list(groups)


def _existing_note(plan: ReviewPlan, setup: rc.ReviewSetup, target: Target, anchor: str, period: str,
                   groups: list, mapped: _Mapped) -> ReviewPlan:
    lines, _ = rht.split_lines(target.text or "")
    headings = rht.hashi_headings(lines)
    marker_at = rht.marker_index(lines, rht.marker_line(period))
    groups = _sectioned(plan, setup, target.text, period, groups, mapped, False)
    if marker_at is not None:
        plan.mode = REPLACE                    # the marker proves the rerun; a refusal reports what it found
        above = next((h for h in reversed(headings) if h[0] < marker_at), None)
        if above is None:
            plan.place = {"anchor": None, "placement": REPLACE, "level": None}
            return _refuse(plan, PLACE_MISSING, headings)
        _, level, text = above
        plan.place = {"anchor": text, "placement": REPLACE, "level": level}
        if not groups:                         # nothing left for the earlier section: it stays as it is
            plan.notices.append(rsp.REVIEW_SECTION_KEPT)
            return plan
        if setup.off_limits and rsp.review_off_limits(target.text or "", period, setup.off_limits) is not None:
            return _refuse(plan, rsp.STOPS[rsp.OFF_LIMITS_LANDING], [])     # where it sits now: also off limits
        if _own(setup, text) or _resolved(headings, text) != above:
            return _refuse(plan, HEADING_COLLISION, headings)
        if _level_or_refuse(plan, rc.BEFORE, level, headings) is None:
            return plan
        if rht.bare(text) != rht.bare(setup.heading):
            plan.problems.append(HEADING_RENAMED)
        plan.section_md, body = render_section(text, level, period, groups)
        plan.actions = [{"id": ACTION_ID, "action": "replace_section", "target_path": target.path,
                         "anchor": {"type": "heading", "value": text}, "content": body}]
        return plan
    if not groups:
        return plan                            # nothing for a new "Tomo Review": no insert
    if _first(headings, setup.heading) is not None:
        return _refuse(plan, HEADING_COLLISION, headings)
    placed = _insertion(plan, setup, anchor, headings, target.text or "")
    if placed is None:
        return plan
    value, level, at = placed
    # Re-plan with the new "Tomo Review"'s index known: a section insert at `at` stops. Routing ignores
    # `review_at`, so the content planned above stays what lands.
    _sectioned(plan, setup, target.text, period, groups, mapped, False, review_at=at)
    plan.place = {"anchor": value, "placement": setup.placement, "level": level}
    plan.section_md, _ = render_section(setup.heading, level, period, groups)
    plan.actions = [{"id": ACTION_ID, "action": "insert_under_marker", "target_path": target.path,
                     "anchor": {"type": "heading", "value": value}, "placement": setup.placement,
                     "content": plan.section_md}]
    return plan


def _plain_note(plan: ReviewPlan, setup: rc.ReviewSetup, name: str, period: str, groups: list) -> str:
    """The note without a template: the title as H1, the review section at ``PLAIN_LEVEL``."""
    plan.place = {"anchor": None, "placement": setup.placement, "level": PLAIN_LEVEL}
    plan.section_md, _ = render_section(setup.heading, PLAIN_LEVEL, period, groups)
    return rnn.plain_note(name, plan.section_md)


def _templated_note(plan: ReviewPlan, setup: rc.ReviewSetup, text: str, anchor: str, period: str, groups: list,
                    mapped: _Mapped) -> Optional[str]:
    """The template ``text`` with the section by the before/inside rule and the blocks; None on a problem."""
    content = _sectioned(plan, setup, text, period, groups, mapped, True)
    inserts = [(p.insert_at, p.block()) for p in plan.sections if p.mode == rsp.INSERT]
    if content:
        placed = _insertion(plan, setup, anchor, rht.hashi_headings(rht.split_lines(text)[0]), text)
        if placed is None:
            return None
        value, level, at = placed
        plan.place = {"anchor": value, "placement": setup.placement, "level": level}
        plan.section_md, _ = render_section(setup.heading, level, period, content)
        inserts.append((at, plan.section_md.split("\n")))     # Hashi's spliceLines: trailing blank included
    return rnn.spliced(text, inserts)                          # a block at Tomo Review's index goes above it


def _new_note(plan: ReviewPlan, setup: rc.ReviewSetup, template: rnn.Template, anchor: str, period: str,
              groups: list, run_id: str, generated: str, mapped: _Mapped) -> ReviewPlan:
    text, plan.templater_hint, plan.variant_missing = rnn.template_choice(setup, template)
    name = rnn.note_name(plan.target)
    if text is None:
        plain = _sectioned(plan, setup, None, period, groups, mapped, True)
        plan.note_text = rnn.stamped(_plain_note(plan, setup, name, period, plain), run_id, generated)
    else:
        note = _templated_note(plan, setup, text, anchor, period, groups, mapped)
        if note is None:
            return plan
        try:
            plan.note_text = rnn.stamped(note, run_id, generated)
        except FrontmatterMergeError as error:
            # the template's frontmatter cannot take the stamp: the plain note, as a missing template yields
            plan.template_unmergeable = str(error)
            plan.templater_hint = False
            plain = _sectioned(plan, setup, None, period, groups, mapped, True)
            plan.note_text = rnn.stamped(_plain_note(plan, setup, name, period, plain), run_id, generated)
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

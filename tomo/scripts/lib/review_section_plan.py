# review_section_plan.py — whether one mapped review section goes into an existing note, and where.
# version: 0.5.3
"""Plan one kept, mapped section of a ``/review`` delivery into a note's text (spec 046 T5.1; PRD
F4-AC2, F4-AC3, F4-AC4, F5-AC1, F5-AC2, F5-AC3, F5-AC5; Rules 3, 4, 8, 9; SDD Runtime View /
Complex Logic, ADR-4, ADR-10, ADR-12).

``plan_section(row, note_text, period, items, *, choice, off_limits, review_at)`` returns a
``SectionPlan``: ``mode`` ``insert`` (no block yet: ``insert_under_marker`` at the mapped heading's
Hashi text, ``before`` -> ``before``, ``under`` -> ``after``, ``end`` -> ``inside``), ``replace``
(exactly one start and one end marker, in that order, in the row's home: ``replace_between_markers``,
scoped to the mapped heading for ``under`` / ``end``, unscoped for ``before``), ``skip`` / ``review``
(the user's choice at a stop) or a stop: ``missing``, ``ambiguous``, ``broken``, ``moved``,
``in-review``, ``landing-off-limits`` (``SectionPlan.stop`` names it). ``choice`` (``skip``,
``review``, ``confirm-moved``) answers only the stop that offers it — ``review`` never beside any marker of the
section and period, intact pair or not; ``SectionPlan.offers`` names what a stop that stays offers. ``review_at`` is the planned
insertion index of a new "Tomo Review" section; an existing one is found by its spec 045 marker.
``place_off_limits`` runs the landing check on spec 045's "Tomo Review" placement, ``review_off_limits`` where it sits.

The delivery's sections as a set — every row planned, a new note's routing, the "Tomo Review"
sub-parts, the splice and the composed actions — are ``review_section_set``'s (T5.4).

The note is read as Hashi reads it (``review_hashi_text``: ``split_lines``, ``fenced_mask``,
``hashi_headings``, ``JS_WS``); markers are unfenced lines equal to the marker after JavaScript's
``trimEnd``. Imports ``review_hashi_text``, never ``review_actions`` or ``review_section_set``. No Kado,
no clock, no file I/O.

Design notes: docs/tomo/scripts/lib/review_section_plan.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from lib import review_hashi_text as rht
from lib.review_mapping import HeadingKey, TemplateHeading, landing_off_limits, row_key

INSERT, REPLACE, SKIP, REVIEW = "insert", "replace", "skip", "review"
MISSING, AMBIGUOUS, BROKEN, MOVED, IN_REVIEW, OFF_LIMITS_LANDING = (
    "missing", "ambiguous", "broken", "moved", "in-review", "landing-off-limits")
STOPS = {MISSING: "section-missing", AMBIGUOUS: "section-ambiguous", BROKEN: "section-broken",
         MOVED: "section-moved", IN_REVIEW: "block-in-review-section", OFF_LIMITS_LANDING: "landing-off-limits"}
CONFIRM_MOVED = "confirm-moved"
CHOICES = (SKIP, REVIEW, CONFIRM_MOVED)
BLOCK_REPLACED, BLOCK_MOVED_CONFIRMED = "block-replaced", "block-moved-confirmed"
REVIEW_SECTION_KEPT = "review-section-kept"            # review_actions: an earlier Tomo Review a re-run keeps
HASHI_PLACEMENT = {"before": "before", "under": "after", "end": "inside"}
_SPEC045_PLACEMENT = {"before": "before", "inside": "end"}
_MARKER_TEXT_RE = re.compile(r"(%%[ \t]*/?tomo):")     # any section's marker text inside an item line


def start_marker(key: str, period: str) -> str:
    return f"%% tomo:{key} {period} %%"


def end_marker(key: str, period: str) -> str:
    return f"%% /tomo:{key} {period} %%"


@dataclass
class SectionPlan:
    key: str
    mode: str
    start_marker: str
    end_marker: str
    lines: List[str] = field(default_factory=list)       # the block's lines between the markers
    escaped_lines: int = 0
    anchor: Optional[str] = None                          # the mapped heading as Hashi reads it
    hashi_placement: Optional[str] = None
    placement: Optional[str] = None                       # the row's configured placement: before | under | end
    scope: Optional[Dict[str, object]] = None
    block_at: Optional[Dict[str, object]] = None          # a moved block: the heading it sits under (None: preamble)
    insert_at: Optional[int] = None                       # an insert: the line index Hashi inserts at
    heading_at: Optional[int] = None                      # an insert: the mapped heading's line index
    notices: List[str] = field(default_factory=list)
    offers: Tuple[str, ...] = ()                          # a stop: the choices that answer it

    @property
    def stop(self) -> Optional[str]:
        return STOPS.get(self.mode)

    def action(self, action_id: str, target_path: str) -> Optional[dict]:
        """The Hashi action of an ``insert`` or ``replace`` plan; None for every other mode."""
        if self.mode == INSERT:
            return {"id": action_id, "action": "insert_under_marker", "target_path": target_path,
                    "anchor": {"type": "heading", "value": self.anchor}, "placement": self.hashi_placement,
                    "content": "\n".join([self.start_marker, *self.lines, self.end_marker]) + "\n"}
        if self.mode == REPLACE:
            out = {"id": action_id, "action": "replace_between_markers", "target_path": target_path,
                   "start_marker": self.start_marker, "end_marker": self.end_marker}
            if self.scope is not None:
                out["scope"] = dict(self.scope)
            out["content"] = "\n".join(self.lines)
            return out
        return None

    def block(self) -> List[str]:
        """The insert's lines as Hashi splits its content: markers, items, the blank line after."""
        return [self.start_marker, *self.lines, self.end_marker, ""]


def block_lines(items: Sequence[dict]) -> Tuple[List[str], int]:
    """``(lines, escapes)``: every item through ``review_hashi_text.item_lines``, marker text escaped."""
    out: List[str] = []
    escaped = 0
    for item in items:
        lines, count = rht.item_lines(item)
        escaped += count
        for line in lines:
            safe = _MARKER_TEXT_RE.sub(r"\1\\:", line)
            escaped += safe != line
            out.append(safe)
    return out, escaped


# --- the note as Hashi reads it -----------------------------------------------------------------

@dataclass
class _Note:
    lines: List[str]
    fenced: List[bool]
    heads: rht.Headings
    keyed: List[TemplateHeading]          # per heading: the identity review_mapping gives a template heading

    @classmethod
    def read(cls, text: str) -> "_Note":
        lines = rht.split_lines(text)[0]
        heads = rht.hashi_headings(lines)
        keyed: List[TemplateHeading] = []
        stack: List[Tuple[Optional[HeadingKey], int]] = []
        seen: Dict[Tuple[str, int, Optional[str]], int] = {}
        for index, level, text_ in heads:
            while stack and stack[-1][1] >= level:
                stack.pop()
            parent = stack[-1][0].heading if stack and stack[-1][0] else None
            if level == 1:                         # never a row: occurrence 0, and no ancestor of anyone
                keyed.append(TemplateHeading(HeadingKey(rht.bare(text_), 1, None, 0), index + 1))
                stack.append((None, 1))
                continue
            seen[(rht.bare(text_), level, parent)] = n = seen.get((rht.bare(text_), level, parent), 0) + 1
            key = HeadingKey(rht.bare(text_), level, parent, n)
            keyed.append(TemplateHeading(key, index + 1, tuple(k for k, _ in stack if k)))
            stack.append((key, level))
        return cls(lines, rht.fenced_mask(lines), heads, keyed)

    def line(self, n: int) -> int:
        return self.heads[n][0]

    def range_end(self, n: int) -> int:
        """The last line of heading ``n``'s section: up to the next heading of its level or higher."""
        level = self.heads[n][1]
        nxt = next((h[0] for h in self.heads[n + 1:] if h[1] <= level), len(self.lines))
        return nxt - 1

    def above(self, p: int) -> Optional[int]:
        """The heading whose own body holds line ``p`` (or receives a line inserted at ``p``); None in the preamble."""
        return next((n for n in range(len(self.heads) - 1, -1, -1) if self.heads[n][0] < p), None)

    def first_hit(self, text: str, level: int) -> Optional[int]:
        return next((n for n, h in enumerate(self.heads) if h[2] == text and h[1] == level), None)

    def find(self, key: HeadingKey) -> Optional[int]:
        want = HeadingKey(rht.bare(key.heading or ""), key.level,
                          rht.bare(key.parent) if key.parent else None, key.occurrence)
        return next((n for n, k in enumerate(self.keyed) if k.key == want), None)

    def markers(self, marker: str) -> List[int]:
        return [i for i, ln in enumerate(self.lines) if not self.fenced[i] and ln.rstrip(rht.JS_WS) == marker]

    def copies(self, marker: str) -> int:
        """Lines holding ``marker`` anywhere: fenced, indented, quoted or inside other text included."""
        return sum(marker in ln for ln in self.lines)

    def covered(self, n: Optional[int], off_limits: Sequence[dict]) -> bool:
        return n is not None and landing_off_limits(self.keyed[n], off_limits) is not None

    def review_range(self, period: str) -> Optional[Tuple[int, int]]:
        """The existing "Tomo Review" section: the heading above its spec 045 marker, to its range end."""
        at = rht.marker_index(self.lines, rht.marker_line(period))
        n = self.above(at) if at is not None else None
        return None if n is None else (self.line(n), self.range_end(n))


# --- the plan ------------------------------------------------------------------------------------

def _stop(plan: SectionPlan, mode: str, choice: Optional[str], allowed: Tuple[str, ...] = (SKIP,),
          offers: Optional[Tuple[str, ...]] = None) -> SectionPlan:
    """``choice`` when ``allowed`` takes it, else the stop ``mode`` offering ``offers`` (default ``allowed``)."""
    if choice in allowed:
        plan.mode = choice
    else:
        plan.mode, plan.offers = mode, (allowed if offers is None else offers)
    return plan


def plan_section(row: dict, note_text: str, period: str, items: Sequence[dict], *, choice: Optional[str] = None,
                 off_limits: Sequence[dict] = (), review_at: Optional[int] = None) -> SectionPlan:
    """The plan of section ``row`` (placement before | under | end) into ``note_text``."""
    if choice is not None and choice not in CHOICES:
        raise ValueError(f"unknown choice: {choice}")
    placement = row.get("placement")
    if placement not in HASHI_PLACEMENT:
        raise ValueError(f"not a placement into a note: {placement}")
    key = str(row["id"])
    plan = SectionPlan(key, INSERT, start_marker(key, period), end_marker(key, period), placement=placement)
    plan.lines, plan.escaped_lines = block_lines(items)
    note = _Note.read(note_text)
    starts, ends = note.markers(plan.start_marker), note.markers(plan.end_marker)
    if note.copies(plan.start_marker) > len(starts) or note.copies(plan.end_marker) > len(ends):
        return _stop(plan, BROKEN, choice)                                  # step 3b: a hidden copy
    pair = len(starts) == 1 and len(ends) == 1 and ends[0] > starts[0]
    mapped = note.find(row_key(row))
    earlier = bool(starts or ends)                                          # any earlier block material
    routable = (SKIP,) if earlier else (SKIP, REVIEW)                       # Rule 8: one Tomo copy per section
    if mapped is None and not (pair and choice == CONFIRM_MOVED):
        return _stop(plan, MISSING, choice, routable,                       # step 5, also on a re-run
                     (SKIP, CONFIRM_MOVED) if pair else None)
    if mapped is not None and sum(h[2] == note.heads[mapped][2] for h in note.heads) > 1:
        return _stop(plan, AMBIGUOUS, choice, routable)                     # Rule 9: Hashi takes the first
    tr = note.review_range(period)
    if not starts and not ends:
        return _first_delivery(plan, note, mapped, placement, choice, off_limits, tr, review_at)
    if pair:
        return _rerun(plan, note, mapped, placement, (starts[0], ends[0]), choice, off_limits, tr)
    return _stop(plan, BROKEN, choice)                                      # step 8: any other count or order


def _first_delivery(plan, note: _Note, mapped: int, placement: str, choice, off_limits, tr, review_at) -> SectionPlan:
    p = {"before": note.line(mapped), "under": note.line(mapped) + 1, "end": note.range_end(mapped) + 1}[placement]
    if note.covered(note.above(p), off_limits):
        return _stop(plan, OFF_LIMITS_LANDING, choice, ())
    if (tr is not None and tr[0] < p <= tr[1] + 1) or p == review_at:
        return _stop(plan, IN_REVIEW, choice)          # Hashi runs every insert before replace_section
    plan.mode, plan.anchor, plan.hashi_placement = INSERT, note.heads[mapped][2], HASHI_PLACEMENT[placement]
    plan.insert_at, plan.heading_at = p, note.line(mapped)
    return plan


def _home(note: _Note, mapped: int, placement: str, tr, at: int) -> bool:
    if placement != "before":
        return note.line(mapped) < at <= note.range_end(mapped)
    prev = note.above(note.line(mapped))
    if tr is not None and tr[1] == note.line(mapped) - 1 and prev is not None and note.line(prev) >= tr[0]:
        prev = note.above(tr[0])                       # pass over a whole Tomo Review directly above
    return (note.line(prev) + 1 if prev is not None else 0) <= at < note.line(mapped)


def _rerun(plan, note: _Note, mapped: Optional[int], placement: str, block: Tuple[int, int], choice, off_limits,
           tr) -> SectionPlan:
    s, e = block
    if any(s < h[0] < e for h in note.heads):
        return _stop(plan, BROKEN, choice)                                  # straddles a heading
    if tr is not None and tr[0] < s <= tr[1]:
        return _stop(plan, IN_REVIEW, choice)
    near = note.above(s)
    if note.covered(near, off_limits):
        return _stop(plan, OFF_LIMITS_LANDING, choice, ())                  # where it actually sits
    if mapped is not None and _home(note, mapped, placement, tr, s) and (placement != "under" or near == mapped):
        _, level, text = note.heads[mapped]
        plan.scope = None if placement == "before" else {"heading": text, "level": level}
        plan.mode, plan.notices = REPLACE, [BLOCK_REPLACED]
        return plan
    if near is None:
        plan.block_at = {"heading": None, "level": None}
        return _stop(plan, MOVED, choice)                                   # never replaced without a scope
    _, level, text = note.heads[near]
    if note.first_hit(text, level) != near:
        return _stop(plan, AMBIGUOUS, choice)
    plan.block_at = {"heading": text, "level": level}
    if choice != CONFIRM_MOVED:
        return _stop(plan, MOVED, choice, offers=(SKIP, CONFIRM_MOVED))
    plan.scope = {"heading": text, "level": level}
    plan.mode, plan.notices = REPLACE, [BLOCK_REPLACED, BLOCK_MOVED_CONFIRMED]
    return plan


def place_off_limits(note_text: str, anchor: str, placement: str, off_limits: Sequence[dict]) -> Optional[dict]:
    """The off-limits row covering where spec 045's "Tomo Review" lands (``before`` / ``inside`` the first heading
    that is ``anchor`` with or without closing hashes); None when nothing covers it or the anchor is absent."""
    note = _Note.read(note_text)
    n = next((i for i, h in enumerate(note.heads) if rht.bare(h[2]) == rht.bare(anchor)), None)
    if n is None:
        return None
    p = note.line(n) if _SPEC045_PLACEMENT[placement] == "before" else note.range_end(n) + 1
    landing = note.above(p)
    return None if landing is None else landing_off_limits(note.keyed[landing], off_limits)


def review_off_limits(note_text: str, period: str, off_limits: Sequence[dict]) -> Optional[dict]:
    """The off-limits row covering an existing "Tomo Review" (the heading above its spec 045 marker) or the heading
    whose body holds that heading's line; None without a marker or a covering row."""
    note = _Note.read(note_text)
    tr = note.review_range(period)
    heads = [] if tr is None else [n for n in (note.above(tr[0] + 1), note.above(tr[0])) if n is not None]
    return next((r for r in (landing_off_limits(note.keyed[n], off_limits) for n in heads) if r), None)

# review_sections.py — the Pass 1 section side of /review: section proposals checked, parts rendered.
# version: 0.2.0
"""The user's mapped sections in the Pass 1 proposals of ``/review`` (spec 046, ADR-1, ADR-2).

``read.json`` carries ``sections`` (the SectionDefinitions) only when the
period kind has a mapping; ``definitions`` reads them, None without one.
``check`` takes ``proposals.json`` (schema-valid) and ``read.json`` and
returns a ``SectionCheck``: the accepted items per section key
(``{text, links, mark?}``), the rejected ones (``{section, index, reason}``:
``no-source-in-period``, ``empty-text``) and the refusal ``errors``
(``"<pointer>: <error>"``, pointers into ``proposals.json``):

- ``unknown-section``: a key with no definition (every key, without a mapping)
- ``duplicate-section``: a key named a second time
- ``over-cap (<key>)``: more proposed items than the section's ``cap``
- ``mark-not-allowed``: a mark that is not the period kind's, or whose child
  notes (a month's weekly, a quarter's monthly notes) were not read
- ``double-placement`` (only with a mapping): the same normalised text, or the
  same source set with the same normalised first line, as an earlier item of
  a section or a group; named on the later one

A section item follows ``review_doc.check_item`` with its mark as the group:
a ``weekly_only`` / ``monthly_only`` item rests on a listed weekly / monthly
note, every other section item on a daily of the period.

``parts(defs, rows, accepted)`` builds one ``SectionPart`` per definition in
``read.json`` order from the configured row of the same id (heading, level,
parent, placement); ``SectionsChanged`` when the keys differ. ``render_parts``
renders the mapped body: each part (``## <heading> %%<key>%%``, the section
checkbox ``- [x] <label> %%<key>%%``, unticked when empty, the italic landing
line, the items or the nothing-found bullet), then, when an analysis part or a
non-empty group is left, the ``## <review heading> %%review%%`` divider with its
landing line, the analysis parts and the non-empty groups. ``group_parts`` and
``part_items`` render the groups and the items of any part (a mark as the
``_LABELS`` suffix, ids global over the document), for both documents.

No Kado, no model, no file I/O.

Design notes: docs/tomo/scripts/lib/review_sections.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from lib import review_doc as rd
from lib.review_config import DEFAULT_CAP

UNKNOWN_SECTION = "unknown-section"
DUPLICATE_SECTION = "duplicate-section"
OVER_CAP = "over-cap"
MARK_NOT_ALLOWED = "mark-not-allowed"
DOUBLE_PLACEMENT = "double-placement"
REVIEW = "review"                                   # an analysis row's placement (F2-AC12)
REVIEW_ID = "%%review%%"

_LINK = r"!?\[\[[^\]\n]*\]\]"
_LINK_LIST = re.compile(rf"\(\s*{_LINK}(?:\s*,\s*{_LINK})*\s*\)\s*$")   # the trailing ([[a]], [[b]]) list
_INLINE_LINK = re.compile(r"!?\[\[([^\]|\n]*)(?:\|[^\]\n]*)?\]\]")      # [[a|b]] -> a, [[a#h]] -> a#h


@dataclass
class SectionCheck:
    accepted: Dict[str, List[dict]] = field(default_factory=dict)    # key -> [{text, links, mark?}]
    rejected: List[dict] = field(default_factory=list)               # [{section, index, reason}]
    errors: List[str] = field(default_factory=list)                  # ["<pointer>: <error>"]


def definitions(read: dict) -> Optional[Dict[str, dict]]:
    """The SectionDefinitions by key; None when ``read.json`` carries no mapping (no ``sections`` key)."""
    sections = read.get("sections") if isinstance(read, dict) else None
    if not isinstance(sections, list):
        return None
    return {str(d["key"]): d for d in sections if isinstance(d, dict) and d.get("key")}


class SectionsChanged(ValueError):
    """The section keys of ``read.json`` are not the configured rows: the mapping changed after the read."""


def _cap(definition: dict) -> int:
    cap = definition.get("cap")
    return cap if isinstance(cap, int) and not isinstance(cap, bool) else DEFAULT_CAP


def _error(pointer: str, error: str) -> str:
    return f"{pointer}: {error}"


def check(proposals: dict, read: dict) -> SectionCheck:
    """Every section check of ``proposals`` against ``read``; see the module docstring."""
    defs = definitions(read)
    entries = proposals.get("sections") or []
    result = SectionCheck()
    if defs is None and not entries:
        return result
    kind = str((read.get("period") or {}).get("kind"))
    has_children = rd.has_child_notes(read)
    sources = rd.Sources.of(read)
    seen = set()
    refused: set = set()                                # entry indexes refused by key, out of the double pass
    for i, entry in enumerate(entries):
        key, items = str(entry.get("key")), entry.get("items") or []
        if key not in (defs or {}):
            result.errors.append(_error(f"/sections/{i}/key", UNKNOWN_SECTION))
            refused.add(i)
            continue
        if key in seen:
            result.errors.append(_error(f"/sections/{i}/key", DUPLICATE_SECTION))
            refused.add(i)
            continue
        seen.add(key)
        if len(items) > _cap(defs[key]):
            result.errors.append(_error(f"/sections/{i}/items", f"{OVER_CAP} ({key})"))
        result.accepted[key] = []
        for j, item in enumerate(items):
            mark = item.get("mark")
            if mark is not None and rd.group_reason(str(mark), kind, has_children) is not None:
                result.errors.append(_error(f"/sections/{i}/items/{j}/mark", MARK_NOT_ALLOWED))
                continue
            reason, links = rd.check_item(str(mark or ""), item, sources)
            if reason is not None:
                result.rejected.append({"section": key, "index": j, "reason": reason})
                continue
            accepted = {"text": str(item["text"]), "links": links}
            if mark is not None:
                accepted["mark"] = str(mark)
            result.accepted[key].append(accepted)
    if defs is not None:
        result.errors.extend(_double_placements(proposals, refused))
    return result


# --- double placement -------------------------------------------------------------------

def _normalised_lines(text: object) -> List[str]:
    """The text's lines casefolded, whitespace collapsed, without ``%%`` marks and a trailing link list,
    each inline link reduced to its target; empty ones dropped."""
    bare = (rd.ID_PATTERN.sub("", ln).replace(rd.ID_MARK, "").rstrip() for ln in str(text).splitlines())
    lines = (" ".join(_INLINE_LINK.sub(r"\1", _LINK_LIST.sub("", ln)).casefold().split()) for ln in bare)
    return [ln for ln in lines if ln]


def _source_set(sources: object) -> frozenset:
    """The item's sources as note stems, so a listed path and its bare stem are one source."""
    return frozenset(rd.note_stem(str(s)).casefold() for s in sources or [])


def _places(proposals: dict, refused: set) -> Iterator[Tuple[str, dict]]:
    """Every item in document order with its pointer: the sections not ``refused``, then the groups in table order."""
    for i, entry in enumerate(proposals.get("sections") or []):
        if i in refused:
            continue
        for j, item in enumerate(entry.get("items") or []):
            yield f"/sections/{i}/items/{j}", item
    groups = proposals.get("groups") or {}
    for group in rd.MODEL_GROUPS:
        for j, item in enumerate(groups.get(group) or []):
            yield f"/groups/{group}/{j}", item


def _double_placements(proposals: dict, refused: set) -> List[str]:
    texts: set = set()
    firsts: set = set()
    errors: List[str] = []
    for pointer, item in _places(proposals, refused):
        lines = _normalised_lines(item.get("text"))
        if not lines:
            continue                                   # nothing but whitespace, marks or a link list: no finding to repeat
        text, first = " ".join(lines), (_source_set(item.get("sources")), lines[0])
        if text in texts or first in firsts:
            errors.append(_error(pointer, DOUBLE_PLACEMENT))
        texts.add(text)
        firsts.add(first)
    return errors


# --- the parts of the document ------------------------------------------------------------

@dataclass
class Landing:
    heading: str
    level: int
    parent: Optional[str]


@dataclass
class SectionPart:
    key: str
    heading: str
    placement: str                                       # before | under | end | review
    landing: Landing
    items: List[dict]                                    # [{text, links, mark?}]
    routed: bool = False                                 # lands in "Tomo Review" (set by delivery planning)

    @property
    def empty(self) -> bool:
        return not self.items

    @property
    def in_review(self) -> bool:
        return self.placement == REVIEW or self.routed


def parts(defs: Dict[str, dict], rows: Sequence[dict], accepted: Dict[str, List[dict]]) -> List[SectionPart]:
    """One part per definition in ``read.json`` order, its landing from the configured row of the same id."""
    by_id = {str(r.get("id")): r for r in rows}
    if set(defs) != set(by_id):
        raise SectionsChanged("the mapped sections changed since the period was read")
    out = []
    for key in defs:
        r = by_id[key]
        out.append(SectionPart(key=key, heading=str(r["heading"]), placement=str(r["placement"]),
                               landing=Landing(str(r["heading"]), int(r["level"]), r.get("parent")),
                               items=list(accepted.get(key) or [])))
    return out


def part_items(items: Sequence[dict], number: int, words: Dict[str, str]) -> Tuple[List[str], int]:
    """A part's item lines, ids from ``number + 1`` and a mark as suffix, or the nothing-found bullet; the last id."""
    lines: List[str] = [] if items else [f"- {words['nothing']}"]
    for entry in items:
        number += 1
        suffix = f" · {words['mark_' + entry['mark']]}" if entry.get("mark") else ""
        lines += rd.item_lines(entry["text"], entry.get("links") or [], number, suffix)
    return lines, number


def group_parts(inp: rd.DocInput, words: Dict[str, str], number: int, keep_empty: bool) -> Tuple[list, dict, int]:
    """``(lines, counts, last id)`` of the rendered groups; an empty one only with ``keep_empty`` (spec 045)."""
    lines: List[str] = []
    counts: Dict[str, int] = {}
    for group in rd.rendered_groups(inp):
        items = inp.groups.get(group) or []
        counts[group] = len(items)
        if items or keep_empty:
            body, number = part_items(items, number, words)
            lines += ["", f"## {words[group]}", *body]
    return lines, counts, number


def landing_line(part: SectionPart, words: Dict[str, str], review_heading: str) -> str:
    """Where the part lands: placement and heading, with level and parent unless it lands in "Tomo Review"."""
    land = part.landing
    if part.in_review:
        return f"*{words['lands']}: {words['review_h'].format(r=review_heading, h=land.heading)}*"
    where = [words["level"].format(level=land.level)]
    if land.parent:
        where.append(words["parent"].format(h=land.parent))
    return f"*{words['lands']}: {words[part.placement + '_h'].format(h=land.heading)} ({', '.join(where)})*"


def _section_part(part: SectionPart, words: Dict[str, str], number: int, review_heading: str) -> Tuple[list, int]:
    mark = f"{rd.ID_MARK}{part.key}{rd.ID_MARK}"
    box = " " if part.empty else "x"
    body, number = part_items(part.items, number, words)
    return ["", f"## {part.heading} {mark}", f"- [{box}] {words['take']} {mark}",
            landing_line(part, words, review_heading), *body], number


def render_parts(inp: rd.DocInput, words: Dict[str, str]) -> Tuple[List[str], Dict[str, int]]:
    """The mapped body and its counts (section keys and groups), ids global over the document."""
    lines: List[str] = []
    counts: Dict[str, int] = {}
    number = 0
    analysis = [p for p in inp.sections if p.placement == REVIEW]
    for part in (p for p in inp.sections if p.placement != REVIEW):
        body, number = _section_part(part, words, number, inp.review_heading)
        lines += body
        counts[part.key] = len(part.items)
    review: List[str] = []
    for part in analysis:
        body, number = _section_part(part, words, number, inp.review_heading)
        review += body
        counts[part.key] = len(part.items)
    groups, group_counts, number = group_parts(inp, words, number, keep_empty=False)
    counts.update(group_counts)
    if review or groups:
        place = words["place_h"].format(r=inp.review_heading, where=words[inp.placement], h=inp.anchor)
        lines += ["", f"## {inp.review_heading} {REVIEW_ID}", f"*{words['lands']}: {place}*", *review, *groups]
    return lines, counts

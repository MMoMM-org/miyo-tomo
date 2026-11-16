# review_sections.py — the Pass 1 section side of /review: the model's section proposals checked.
# version: 0.1.0
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
- ``over-cap``: more proposed items than the section's ``cap``
- ``mark-not-allowed``: a mark that is not the period kind's, or whose child
  notes (a month's weekly, a quarter's monthly notes) were not read
- ``double-placement`` (only with a mapping): the same normalised text, or the
  same source set with the same normalised first line, as an earlier item of
  a section or a group; named on the later one

A section item follows ``review_doc.check_item`` with its mark as the group:
a ``weekly_only`` / ``monthly_only`` item rests on a listed weekly / monthly
note, every other section item on a daily of the period.

No Kado, no model, no file I/O.

Design notes: docs/tomo/scripts/lib/review_sections.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

from lib import review_doc as rd
from lib.review_config import DEFAULT_CAP

UNKNOWN_SECTION = "unknown-section"
DUPLICATE_SECTION = "duplicate-section"
OVER_CAP = "over-cap"
MARK_NOT_ALLOWED = "mark-not-allowed"
DOUBLE_PLACEMENT = "double-placement"

_LINK = r"!?\[\[[^\]\n]*\]\]"
_LINKS = re.compile(rf"\(\s*{_LINK}(?:\s*,\s*{_LINK})*\s*\)|{_LINK}")


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
    for i, entry in enumerate(entries):
        key, items = str(entry.get("key")), entry.get("items") or []
        if key not in (defs or {}):
            result.errors.append(_error(f"/sections/{i}/key", UNKNOWN_SECTION))
            continue
        if key in seen:
            result.errors.append(_error(f"/sections/{i}/key", DUPLICATE_SECTION))
            continue
        seen.add(key)
        if len(items) > _cap(defs[key]):
            result.errors.append(_error(f"/sections/{i}/items", OVER_CAP))
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
        result.errors.extend(_double_placements(proposals))
    return result


# --- double placement -------------------------------------------------------------------

def _normalised_lines(text: object) -> List[str]:
    """The text's lines casefolded, whitespace collapsed, without ``%%`` marks and wiki links; empty ones dropped."""
    lines = (" ".join(_LINKS.sub(" ", ln).casefold().split())
             for ln in str(text).replace(rd.ID_MARK, "").splitlines())
    return [ln for ln in lines if ln]


def _source_set(sources: object) -> frozenset:
    """The item's sources as note stems, so a listed path and its bare stem are one source."""
    return frozenset(rd.note_stem(str(s)).casefold() for s in sources or [])


def _places(proposals: dict) -> Iterator[Tuple[str, dict]]:
    """Every item in document order with its pointer: the sections, then the groups in table order."""
    for i, entry in enumerate(proposals.get("sections") or []):
        for j, item in enumerate(entry.get("items") or []):
            yield f"/sections/{i}/items/{j}", item
    groups = proposals.get("groups") or {}
    for group in rd.MODEL_GROUPS:
        for j, item in enumerate(groups.get(group) or []):
            yield f"/groups/{group}/{j}", item


def _double_placements(proposals: dict) -> List[str]:
    texts: set = set()
    firsts: set = set()
    errors: List[str] = []
    for pointer, item in _places(proposals):
        lines = _normalised_lines(item.get("text"))
        if not lines:
            continue                                   # empty-text rejects it
        text, first = " ".join(lines), (_source_set(item.get("sources")), lines[0])
        if text in texts or first in firsts:
            errors.append(_error(pointer, DOUBLE_PLACEMENT))
        texts.add(text)
        firsts.add(first)
    return errors

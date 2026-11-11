# review_doc_parse.py — the edited review document of /review read back: Approved line, items by id, user items.
# version: 0.2.0
"""Parse the review document after the user edited it (spec 045, T3.7, PRD F5, ADR-9, ADR-13).

``parse_document`` reads the text of ``<period> Review.md`` and returns a
``ParsedDoc``: the frontmatter, whether the exact column-0 ``- [x] Approved``
line is ticked, every item in document order with its group, and the
warnings. Only an exact column-0 line is structure — the Approved line, a
``## `` group heading, a ``- [ ] `` / ``- [x] `` item start; every other
line after an item start is that item's text, verbatim. A checkbox line
carrying ``%%t<n>%%`` is Tomo's item (the id is stripped from the text, a
second occurrence of an id is a user item); a checkbox line without an id
is the user's. ``edited`` is structural: the item's ``[[stem]]`` link stems
(ordered, de-duplicated, ``|alias`` and ``#heading`` cut off) differ from
the ``pass1_links`` map ``review-doc.py write`` stored in ``meta.json``; an
id absent from the map is never edited. ``link_stems`` computes that map
from a rendered document — nothing text-derived, no digest. ``counts``
gives kept / unticked / deleted (by Pass 1 id) / added (the user's ticked
items); ``approved_review`` is the in-process ApprovedReview record with
the kept items' text for Phase 4 (never a file); ``public_items`` is the
same without text, for stdout.

No Kado, no file I/O. Needs PyYAML.

Design notes: docs/tomo/scripts/lib/review_doc_parse.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from lib import review_doc as rd

TOMO, USER = "tomo", "user"
UNKNOWN = "unknown"
APPROVED_MISSING = "approved-line-missing"
UNKNOWN_GROUP = "unknown-group"
DUPLICATE_GROUP = "duplicate-group"
FRONTMATTER_BROKEN = "frontmatter-broken"

_FENCE = "---"
_ITEM = re.compile(r"^- \[([ xX])\](?: (.*))?$")
_HEADING = re.compile(r"^## (.*?)\s*$")
_APPROVED = re.compile(r"^- \[([ xX])\] Approved$")
_LINK = re.compile(r"\[\[([^\]|#]+)")


@dataclass
class Item:
    group: str
    id: Optional[str]
    origin: str
    kept: bool
    text: str
    lines: List[str] = field(default_factory=list)
    edited: bool = False

    def link_stems(self) -> List[str]:
        """The ``[[stem]]`` stems of the text and continuation lines in order, each once; the tick state does not count."""
        stems: List[str] = []
        for stem in _LINK.findall("\n".join([self.text, *self.lines])):
            if stem.strip() and stem.strip() not in stems:
                stems.append(stem.strip())
        return stems

    def public(self) -> dict:
        """What stdout may carry: the id, the origin, the box, the edit flag; no text."""
        out: Dict[str, Any] = {"id": self.id} if self.id else {}
        out.update({"origin": self.origin, "kept": self.kept, "edited": self.edited})
        return out

    def record(self) -> dict:
        return {"id": self.id, "origin": self.origin, "edited": self.edited, "text": self.text, "lines": list(self.lines)}


@dataclass
class ParsedDoc:
    frontmatter: dict
    approved: bool
    items: List[Item]
    warnings: List[str]
    deleted: int                       # Pass 1 ids the document no longer carries
    group_order: List[str]

    def groups(self) -> Dict[str, List[Item]]:
        """Items per group in rendering order; ``unknown`` last when a heading matched no label."""
        out: Dict[str, List[Item]] = {group: [] for group in self.group_order}
        for item in self.items:
            out.setdefault(item.group, []).append(item)
        return out

    def counts(self) -> Dict[str, int]:
        tomo = [it for it in self.items if it.origin == TOMO]
        return {
            "kept": sum(1 for it in tomo if it.kept),
            "unticked": sum(1 for it in tomo if not it.kept),
            "deleted": self.deleted,
            "added": sum(1 for it in self.items if it.origin == USER and it.kept),
        }

    def nothing_to_deliver(self) -> bool:
        return not any(it.kept for it in self.items)

    def public_items(self) -> Dict[str, List[dict]]:
        return {group: [it.public() for it in items] for group, items in self.groups().items()}

    def approved_review(self, **extra: Any) -> dict:
        """The ApprovedReview record: kept items with their verbatim text, groups in rendering order."""
        front = self.frontmatter
        return {
            **extra,
            "period": front.get("review_period"), "kind": front.get("review_kind"),
            "language": front.get("review_language"), "approved": self.approved,
            "groups": {group: [it.record() for it in items if it.kept] for group, items in self.groups().items()},
            "counts": self.counts(), "warnings": list(self.warnings),
        }


# --- frontmatter -------------------------------------------------------------------------

def _split_frontmatter(lines: List[str]) -> tuple:
    """``(frontmatter or None, body lines)``; None when the block is missing, unclosed, unparsable or not a mapping."""
    if not lines or lines[0].strip() != _FENCE:
        return None, lines
    for index in range(1, len(lines)):
        if lines[index].strip() == _FENCE:
            return _load_yaml("\n".join(lines[1:index])), lines[index + 1:]
    return None, lines


def _load_yaml(text: str) -> Optional[dict]:
    import yaml

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _is_review(front: Optional[dict]) -> bool:
    tomo = front.get("tomo") if isinstance(front, dict) else None
    return isinstance(tomo, dict) and tomo.get("doc_type") == rd.DOC_TYPE


# --- the body ------------------------------------------------------------------------------

def _item_of(group: str, box: str, rest: str, seen_ids: Set[str]) -> Item:
    """The item a checkbox line starts; the first id on the line names Tomo's item unless it was seen already."""
    match = rd.ID_PATTERN.search(rest)
    item_id = match.group(1) if match else None
    text = (rest[:match.start()] + rest[match.end():]) if match else rest
    text = text.strip() if match else rest.rstrip()
    if item_id is not None and item_id not in seen_ids:
        seen_ids.add(item_id)
        return Item(group, item_id, TOMO, box.lower() == "x", text)
    return Item(group, None, USER, box.lower() == "x", text)


def _strip_trailing_blanks(lines: List[str]) -> List[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _parse_body(lines: Iterable[str], warnings: List[str]) -> tuple:
    """``(approved or None, items, group order)`` from the body lines by the column-0 grammar."""
    labels = rd.group_labels()
    approved: Optional[bool] = None
    items: List[Item] = []
    order: List[str] = []
    seen_ids: Set[str] = set()
    group: Optional[str] = None
    current: Optional[Item] = None
    for line in lines:
        gate = _APPROVED.match(line)
        if gate:
            if approved is None:
                approved = gate.group(1).lower() == "x"
            current = None
            continue
        heading = _HEADING.match(line)
        if heading:
            group = labels.get(heading.group(1))
            if group is None:
                group = UNKNOWN
                _warn(warnings, UNKNOWN_GROUP)
            elif group in order:
                _warn(warnings, DUPLICATE_GROUP)
            if group not in order:
                order.append(group)
            current = None
            continue
        start = _ITEM.match(line)
        if start and group is not None:
            current = _item_of(group, start.group(1), start.group(2) or "", seen_ids)
            items.append(current)
            continue
        if current is not None:
            current.lines.append(line)
    for item in items:
        _strip_trailing_blanks(item.lines)
    if UNKNOWN in order:
        order = [g for g in order if g != UNKNOWN] + [UNKNOWN]
    return approved, items, order


def _warn(warnings: List[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)


# --- the entry points ------------------------------------------------------------------------

def parse_document(text: str, pass1_links: Optional[Dict[str, List[str]]] = None,
                   pass1_total: Optional[int] = None) -> ParsedDoc:
    """Parse the document text. ``pass1_links`` is the id → link stems map of Pass 1 (``edited`` and
    ``deleted`` come from it); ``pass1_total`` alone gives ``deleted`` by count when the map is missing."""
    warnings: List[str] = []
    front, body = _split_frontmatter(text.splitlines())
    if not _is_review(front):
        _warn(warnings, FRONTMATTER_BROKEN)
    approved, items, order = _parse_body(body, warnings)
    if approved is None:
        _warn(warnings, APPROVED_MISSING)
    reference = pass1_links or {}
    for item in items:
        if item.origin == TOMO and item.id in reference and isinstance(reference[item.id], list):
            item.edited = item.link_stems() != [str(s) for s in reference[item.id]]
    seen = {it.id for it in items if it.origin == TOMO}
    deleted = len(set(reference) - seen) if reference else max(0, (pass1_total or 0) - len(seen))
    warnings.sort()
    return ParsedDoc(front if isinstance(front, dict) else {}, bool(approved), items, warnings, deleted, order)


def link_stems(text: str) -> Dict[str, List[str]]:
    """``{id: [link stem, ...]}`` of every Tomo item in a rendered document, for ``meta.json``."""
    return {it.id: it.link_stems() for it in parse_document(text).items if it.origin == TOMO and it.id}

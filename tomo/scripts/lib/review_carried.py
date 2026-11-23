# review_carried.py — the document-level rules of a /review item carried over from a previous review.
# version: 0.1.0
"""Carried items of the ``/review`` proposals (spec 047 T5.3, SDD ADR-6; PRD F4-AC6, F4-AC7, F4-AC10, F5-AC3).

A group or section item of ``proposals.json`` may carry ``carried`` (``done`` | ``still_open`` |
``not_mentioned``) with ``carried_ids`` (ids of ``carryover.json`` items). This module owns every rule of
such an item over the document; ``lib/review_digest.py`` owns the carryover file itself.

``check(group, item, sources, carryover, *, in_section, mark=None)`` → ``(error | None, links)`` for one
carried item, first failure wins: ``carried-without-carryover``; ``carried-not-allowed (<group>)`` (groups:
``done`` only in done, ``still_open`` / ``not_mentioned`` only in open and themes; a section takes any
value); ``carried-mark-conflict`` (a child mark other than ``not_in_weekly`` / ``not_in_monthly``, or one
with ``not_mentioned``); ``carried-needs-previous-note``; ``carried-source-not-its-note (<first id>)`` (the
item's previous-note stems not within the sources of its ids; skipped when an id is unknown);
``carried-gone-has-day`` (``not_mentioned`` with a day); ``carried-needs-day`` (``done`` / ``still_open``
without one). No two-day theme rule. ``links`` are ``resolve_sources``' links in source order.

``coverage(proposals, carryover)`` → ``"<pointer>: <error>"`` strings in document order (sections, then the
groups in ``MODEL_GROUPS`` order): ``carried-unknown (<id>)`` by exact match, ``carried-twice (<id>)`` on the
later item, ``carried-theme-done (<id>)``; then bare ``carried-missing (<id>)`` per id no item lists.
Without a carryover: nothing (``check`` names every carried item).

``overflow(proposals, defs, carryover)`` → ``(new proposals, notices)``: while a section of ``defs`` holds
more items than its cap and one of them is carried, the last carried item moves to the end of the group of
its mark (done → done; still_open / not_mentioned → themes when every id is a ``theme`` item, else open),
without its ``mark``. ``notices`` are ``{key, to, count}`` rows in first-move order. The input is not changed.

No Kado, no model, no file I/O.

Design notes: docs/tomo/scripts/lib/review_carried.md
"""
from __future__ import annotations

import copy
from typing import Dict, Iterator, List, Optional, Tuple

from lib.review_sources import Sources, note_stem, resolve_sources

DONE, STILL_OPEN, NOT_MENTIONED = "done", "still_open", "not_mentioned"
THEME = "theme"
ALLOWED = {"done": {DONE}, "open": {STILL_OPEN, NOT_MENTIONED}, "themes": {STILL_OPEN, NOT_MENTIONED}}
CHILD_MARK_OK = {"not_in_weekly", "not_in_monthly"}            # the only child marks a carried item may carry

WITHOUT_CARRYOVER = "carried-without-carryover"
NOT_ALLOWED = "carried-not-allowed"
MARK_CONFLICT = "carried-mark-conflict"
NEEDS_PREVIOUS = "carried-needs-previous-note"
NOT_ITS_NOTE = "carried-source-not-its-note"
GONE_HAS_DAY = "carried-gone-has-day"
NEEDS_DAY = "carried-needs-day"
UNKNOWN = "carried-unknown"
TWICE = "carried-twice"
MISSING = "carried-missing"
THEME_DONE = "carried-theme-done"


def _items_by_id(carryover: Optional[dict]) -> Dict[str, dict]:
    return {str(i.get("id")): i for i in (carryover or {}).get("items") or [] if isinstance(i, dict)}


def check(group: str, item: dict, sources: Sources, carryover: Optional[dict], *, in_section: bool,
          mark: Optional[str] = None) -> Tuple[Optional[str], List[str]]:
    """The first carried rule ``item`` breaks, or None, and its links; see the module docstring."""
    carried = str(item.get("carried"))
    if carryover is None:
        return WITHOUT_CARRYOVER, []
    if not in_section and carried not in ALLOWED.get(group, set()):
        return f"{NOT_ALLOWED} ({group})", []
    if mark is not None and (mark not in CHILD_MARK_OK or carried == NOT_MENTIONED):
        return MARK_CONFLICT, []
    got = resolve_sources(item, sources)
    if not got.previous:
        return NEEDS_PREVIOUS, got.links
    ids = [str(i) for i in item.get("carried_ids") or []]
    known = _items_by_id(carryover)
    if all(i in known for i in ids):
        allowed = {note_stem(str(s)) for i in ids for s in known[i].get("sources") or []}
        if not set(got.previous) <= allowed:
            return f"{NOT_ITS_NOTE} ({ids[0]})", got.links
    if carried == NOT_MENTIONED and got.days:
        return GONE_HAS_DAY, got.links
    if carried != NOT_MENTIONED and not got.days:
        return NEEDS_DAY, got.links
    return None, got.links                                     # no two-day theme rule for a carried item


def _places(proposals: dict) -> Iterator[Tuple[str, dict]]:
    """Every item with its pointer: the sections in order, then the groups in document order."""
    from lib.review_doc import MODEL_GROUPS                    # call time: review_doc imports this module (T5.4)
    for i, entry in enumerate(proposals.get("sections") or []):
        for j, item in enumerate(entry.get("items") or []):
            yield f"/sections/{i}/items/{j}", item
    groups = proposals.get("groups") or {}
    for group in MODEL_GROUPS:
        for j, item in enumerate(groups.get(group) or []):
            yield f"/groups/{group}/{j}", item


def coverage(proposals: dict, carryover: Optional[dict]) -> List[str]:
    """Every carryover id exactly once over the document; no unknown id; a theme id never carried done."""
    if carryover is None:
        return []
    known = _items_by_id(carryover)
    seen: set = set()
    errors: List[str] = []
    for pointer, item in _places(proposals):
        if not item.get("carried"):
            continue
        for k, cid in enumerate(str(i) for i in item.get("carried_ids") or []):
            if cid not in known:
                errors.append(f"{pointer}/carried_ids/{k}: {UNKNOWN} ({cid})")
                continue
            if cid in seen:
                errors.append(f"{pointer}/carried_ids/{k}: {TWICE} ({cid})")
            seen.add(cid)
            if item.get("carried") == DONE and known[cid].get("type") == THEME:
                errors.append(f"{pointer}/carried: {THEME_DONE} ({cid})")
    errors.extend(f"{MISSING} ({cid})" for cid in known if cid not in seen)
    return errors


def _target(item: dict, known: Dict[str, dict]) -> str:
    if item.get("carried") == DONE:
        return "done"
    ids = [str(i) for i in item.get("carried_ids") or []]
    every_theme = bool(ids) and all(known.get(i, {}).get("type") == THEME for i in ids)
    return "themes" if every_theme else "open"


def overflow(proposals: dict, defs: Dict[str, dict], carryover: Optional[dict]) -> Tuple[dict, List[dict]]:
    """Carried items of a full section moved into the group of their mark; see the module docstring."""
    from lib import review_sections as rs                      # call time: review_sections imports this module
    out = copy.deepcopy(proposals)
    known = _items_by_id(carryover)
    counts: Dict[Tuple[str, str], int] = {}
    for entry in out.get("sections") or []:
        key = str(entry.get("key"))
        if key not in defs:
            continue
        items = entry.get("items") or []
        cap = rs._cap(defs[key])
        while len(items) > cap:
            carried = [n for n, item in enumerate(items) if item.get("carried")]
            if not carried:
                break
            item = items.pop(carried[-1])
            item.pop("mark", None)
            to = _target(item, known)
            out.setdefault("groups", {}).setdefault(to, []).append(item)
            counts[(key, to)] = counts.get((key, to), 0) + 1
    return out, [{"key": key, "to": to, "count": n} for (key, to), n in counts.items()]

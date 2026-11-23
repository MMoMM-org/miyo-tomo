# review_sources.py — what a /review proposal's source may resolve to, and the one loop that resolves it.
# version: 0.1.0
"""Sources of a review read and the one source resolver (spec 047 T5.2, SDD ADR-6; split from review_doc, CON-5).

``Sources.of(read)`` keys every note a source may name by its listed path and by its stem: the dailies of the
period's days (never one of a day the read's ``not_condensed`` units hold) → ``(day, stem)``, the listed weekly and
monthly notes → stem, the found previous review notes (``read["previous"]`` rows in state ``found``) → stem.
``resolve_sources(item, sources, child_group)`` walks the item's sources in order — a daily first, then (for
``weekly_only`` / ``monthly_only`` only) a child note, then a previous note — and returns a ``Resolved``: the days,
the child-note hit count, the previous-note stems and the links, deduplicated in source order. A source that
resolves to nothing is skipped; a model string is a lookup key only, never a link. ``review_doc.check_item`` and
``review_carried.check`` both rest on it; ``review_doc`` re-exports these names.

No Kado, no model, no file I/O.

Design notes: docs/tomo/scripts/lib/review_sources.md
"""
from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

WEEKLY_ONLY, MONTHLY_ONLY = "weekly_only", "monthly_only"
_ONLY_IN_CHILD = (WEEKLY_ONLY, MONTHLY_ONLY)                         # rests on a child note, not on a daily


def note_stem(path: str) -> str:
    name = posixpath.basename(path.strip().strip("[]"))
    return name[:-3] if name.endswith(".md") else name


@dataclass
class Sources:
    """What a source may resolve to, keyed by the listed path and by its stem: a daily → (day, stem),
    a weekly or monthly note → stem, a found previous review note → stem."""

    dailies: Dict[str, Tuple[date, str]] = field(default_factory=dict)
    weeklies: Dict[str, str] = field(default_factory=dict)
    monthlies: Dict[str, str] = field(default_factory=dict)
    previous: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def of(cls, read: dict) -> "Sources":
        """The read's sources; the days of a unit in ``read["not_condensed"]`` give none."""
        sources = cls()
        not_condensed = {str(d) for unit in read.get("not_condensed") or [] for d in unit.get("days") or []}
        for entry in read.get("days") or []:
            if str(entry.get("date")) in not_condensed:
                continue
            try:
                day = date.fromisoformat(str(entry.get("date")))
            except ValueError:
                continue
            for path in entry.get("dailies") or []:
                stem = note_stem(str(path))
                sources.dailies[str(path)] = (day, stem)
                sources.dailies.setdefault(stem, (day, stem))
        found = [e for e in read.get("previous") or [] if e.get("state") == "found"]
        for entries, notes in ((read.get("weekly"), sources.weeklies), (read.get("monthly"), sources.monthlies),
                               (found, sources.previous)):
            for entry in entries or []:
                path = str(entry.get("path") or "")
                if path:
                    notes[path] = note_stem(path)
                    notes.setdefault(note_stem(path), note_stem(path))
        return sources

    def daily_of(self, source: str) -> Optional[Tuple[date, str]]:
        return self.dailies.get(source.strip()) or self.dailies.get(note_stem(source))

    def child_of(self, group: str, source: str) -> Optional[str]:
        """The weekly note of a ``weekly_only`` source, the monthly note of a ``monthly_only`` one."""
        notes = self.weeklies if group == WEEKLY_ONLY else self.monthlies
        return notes.get(source.strip()) or notes.get(note_stem(source))

    def previous_of(self, source: str) -> Optional[str]:
        return self.previous.get(source.strip()) or self.previous.get(note_stem(source))


@dataclass
class Resolved:
    days: set = field(default_factory=set)
    children: int = 0
    previous: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)


def resolve_sources(item: dict, sources: Sources, child_group: str = "") -> Resolved:
    """Days, child-note hits, previous-note hits and the links in source order; every check reads this."""
    out = Resolved()
    for source in (str(s) for s in item.get("sources") or []):
        daily = sources.daily_of(source)
        child = sources.child_of(child_group, source) if child_group in _ONLY_IN_CHILD and daily is None else None
        prev = sources.previous_of(source) if daily is None and child is None else None
        if daily is not None:
            out.days.add(daily[0])
        elif child is not None:
            out.children += 1
        elif prev is not None:
            out.previous.append(prev)
        link = daily[1] if daily is not None else child or prev
        if link and link not in out.links:
            out.links.append(link)
    return out

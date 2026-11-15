# review_children.py — the child-review notes of a period read: weekly notes of a month or quarter, monthly notes of a quarter.
# version: 0.1.0
"""Finding and reading child-review notes, and their report (spec 046, T3.2; ADR-6; PRD F6-AC4, F6-AC5).

A ``ChildNotes`` value is one level (kind ``week`` or ``month``, folder, name
format, own sections). ``find`` lists the folder once and resolves each child
of the period (the weeks it overlaps, or a quarter's months) to its flat and
year-folder paths; ``prefetch`` reads those notes before the end pass;
``read`` splits each with ``review_weekly.weekly_content`` (day blocks clipped
to the period, own-section text under ``<kind>_text``) into entries
``{path, <kind>, overlap_days, duplicate, ...}`` and report rows
``{<kind>, path, state}``; ``status`` names the level's outcome. Which levels a
period reads and marks is ``lib/review_period.py``'s ``CHILD`` table. Every
Kado call goes through the ``PacedReader`` the caller hands in.

Design notes: docs/tomo/scripts/lib/review_children.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from lib.period import WEEK, Period, WeekRule
from lib.review_config import GRANULARITY
from lib.review_weekly import weekly_content
from lib.vault_paths import path_key

FOUND, NONE_FOUND, KADO_EMPTY, NOT_READ = "found", "none-found", "kado-empty", "not-read"
NOT_CONFIGURED = "not-configured"

Found = Tuple[Optional[List[str]], List[Tuple[Period, List[str]]]]


@dataclass(frozen=True)
class ChildNotes:
    """One child-review level: where its notes live and how they are named."""

    kind: str
    folder: Optional[str]
    fmt: Optional[str]
    own_sections: Sequence[str] = ()

    @property
    def label(self) -> str:
        """``weekly`` / ``monthly``: the result key, the report prefix and the ``kado_empty`` name."""
        return GRANULARITY[self.kind]

    @property
    def configured(self) -> bool:
        return bool(self.folder and self.fmt)


def children_of(period: Period, kind: str, rule: WeekRule) -> List[Period]:
    """The weeks a month or quarter overlaps, or a quarter's months."""
    return period.weeks_overlapping(rule) if kind == WEEK else period.months()


def find(reader, period: Period, child: ChildNotes, rule: WeekRule) -> Found:
    """The folder listing and the note paths per child; no children without a listing."""
    listing = reader.folder(child.folder)
    if listing is None:
        return None, []
    keys = {path_key(p): p for p in listing}
    children = []
    for note in children_of(period, child.kind, rule):
        candidates = note.note_paths(child.folder, child.fmt)
        children.append((note, [keys[path_key(c)] for c in candidates if path_key(c) in keys]))
    return listing, children


def prefetch(reader, found: Found) -> None:
    """Read every child note once, before the end pass."""
    for _, paths in found[1]:
        for path in paths:
            reader.note(path)


def read(reader, period: Period, child: ChildNotes, found: Found, *, daily_format: str,
         skip_sections: Sequence[str]) -> Tuple[List[dict], List[dict]]:
    """``(entries, report rows)`` of the found children; an absent child is a row with ``path: None``."""
    entries, rows = [], []
    for note, paths in found[1]:
        overlap = sum(1 for d in note.days() if period.start <= d <= period.end)
        if not paths:
            rows.append({child.kind: note.name, "path": None, "state": "absent"})
        for path in paths:
            text = reader.note(path)
            rows.append({child.kind: note.name, "path": path, "state": "read" if text is not None else "failed"})
            if text is None:
                continue
            content = weekly_content(text, period, daily_format=daily_format, own_sections=child.own_sections,
                                     skip_sections=skip_sections, text_key=f"{child.kind}_text")
            entries.append({"path": path, child.kind: note.name, "overlap_days": overlap,
                            "duplicate": len(paths) > 1, **content})
    return entries, rows


def status(child: ChildNotes, entries: List[dict], listing: Optional[List[str]], kado_empty: Sequence[str]) -> str:
    """``not-configured``, ``found``, ``none-found``, ``kado-empty`` or ``not-read``."""
    if not child.configured:
        return NOT_CONFIGURED
    if entries:
        return FOUND
    if listing is not None:
        return NONE_FOUND
    return KADO_EMPTY if child.label in kado_empty else NOT_READ

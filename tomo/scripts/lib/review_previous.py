# review_previous.py — the previous review notes of a period read: which periods, found how, in which state, what text.
# version: 0.2.0
"""Finding and reading the previous review notes (spec 047, T3.1; ADR-5; PRD F3-AC1..F3-AC10, F4-AC9, F6-AC7).

``previous_periods`` names the previous periods of a review as ``(role,
period)``: a week reads the previous week and the month before the month the
week starts in, a month the previous month and the quarter before its
quarter, a quarter the previous quarter. ``locations`` reads each kind's
folder (config over profile) and name format from the vault config;
``set_up`` builds one ``PreviousNote`` per previous period without a Kado
call. ``prefetch`` lists each set-up note's folder (depth 2) and reads the
first of its ``Period.note_paths`` candidates the listing holds, before the
reader's ``finish()``; ``resolve`` turns each note into its row after it:
``{kind, name, role, path, state, cause?, partly_read, sections?}`` with
state ``found`` / ``empty`` / ``missing`` / ``not-set-up`` / ``not-read``,
cause (only for ``not-read``) ``refused`` / ``failed`` (a listing Kado answered
with nothing is ``missing``), and
``sections`` ``{heading: [lines]}`` (only for ``found``); ``report_rows`` gives
the same rows without ``sections`` for the report. A ``KadoToolError``
whose text carries Kado's quoted error code ``"FORBIDDEN"`` is caught per call
and makes the note ``refused``; every other error propagates. Every Kado call goes through the
``PacedReader`` the caller hands in.

Design notes: docs/tomo/scripts/lib/review_previous.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional, Set, Tuple

from lib.kado_client import KadoToolError
from lib.period import KINDS, MONTH, QUARTER, WEEK, Period, WeekRule
from lib.review_config import GRANULARITY, configured_formats, folder_for
from lib.review_day import SECTION_UNIT, cut_at_boundary, has_content
from lib.review_md import block_text, body, cleaned, headings, kept_lines, trailing_navigation
from lib.vault_paths import path_key

FOUND, EMPTY, MISSING, NOT_SET_UP, NOT_READ = "found", "empty", "missing", "not-set-up", "not-read"
STATES = (FOUND, EMPTY, MISSING, NOT_SET_UP, NOT_READ)
REFUSED, FAILED = "refused", "failed"
FORBIDDEN = "FORBIDDEN"
_FORBIDDEN_CODE = f'"{FORBIDDEN}"'    # the quoted code of {"code":"FORBIDDEN",...}
ROLE = {WEEK: "previous-week", MONTH: "previous-month", QUARTER: "previous-quarter"}


@dataclass
class PreviousNote:
    """One previous period: where its note would live, and which of its calls Kado refused."""

    role: str
    period: Period
    folder: Optional[str]
    fmt: Optional[str]
    refused: Set[str] = field(default_factory=set)    # the folder or note path Kado refused

    @property
    def configured(self) -> bool:
        return bool(self.folder and self.fmt)


def previous_periods(period: Period, rule: WeekRule) -> List[Tuple[str, Period]]:
    """``(role, previous period)`` in reading order; never the period itself."""
    if period.kind == WEEK:
        return [(ROLE[WEEK], period.previous(rule)),
                (ROLE[MONTH], Period.containing(MONTH, period.start).previous())]
    if period.kind == MONTH:
        return [(ROLE[MONTH], period.previous()),
                (ROLE[QUARTER], Period.containing(QUARTER, period.start).previous())]
    return [(ROLE[QUARTER], period.previous())]


def locations(config: dict, profile: dict) -> Tuple[Dict[str, Optional[str]], Dict[str, Optional[str]]]:
    """``({kind: folder}, {kind: name format})`` from the setup; None where the setup names none."""
    formats = configured_formats(config)
    return ({kind: folder_for(config, profile, GRANULARITY[kind]) for kind in KINDS},
            {kind: formats.get(kind) for kind in KINDS})


def set_up(period: Period, rule: WeekRule, folders: Mapping[str, Optional[str]],
           formats: Mapping[str, Optional[str]]) -> List[PreviousNote]:
    """One ``PreviousNote`` per previous period; no Kado call."""
    return [PreviousNote(role, prev, folders.get(prev.kind), formats.get(prev.kind))
            for role, prev in previous_periods(period, rule)]


def _guarded(note: PreviousNote, key: str, call: Callable[[], object]) -> object:
    """``call()``; a ``"FORBIDDEN"`` tool error marks ``key`` refused and answers None, also when asked again."""
    if key in note.refused:
        return None
    try:
        return call()
    except KadoToolError as exc:
        if _FORBIDDEN_CODE not in str(exc):
            raise
        note.refused.add(key)
        return None


def _listing(reader, note: PreviousNote) -> Optional[List[str]]:
    return _guarded(note, note.folder, lambda: reader.folder(note.folder))


def _path(note: PreviousNote, listing: List[str]) -> Optional[str]:
    """The first candidate (flat, then year subfolder) the listing holds."""
    keys = {path_key(p): p for p in listing}
    for candidate in note.period.note_paths(note.folder, note.fmt):
        if path_key(candidate) in keys:
            return keys[path_key(candidate)]
    return None


def prefetch(reader, notes: List[PreviousNote]) -> None:
    """List each set-up note's folder and read its note once, before the end pass."""
    for note in notes:
        if not note.configured:
            continue
        listing = _listing(reader, note)
        path = _path(note, listing) if listing else None
        if path:
            _guarded(note, path, lambda: reader.note(path))


def _kept_lines(text: str) -> List[str]:
    """The body without navigation, METADATA callouts, embed lines and breaks with their trailing navigation."""
    _, lines = body(text)
    return kept_lines(lines, trailing_navigation(lines, headings(lines)))


def _blocks(lines: List[str]) -> List[Tuple[str, List[str]]]:
    """``(heading, cleaned lines)`` per heading block in order; the text before the first heading under ``""``."""
    found = headings(lines)[0]
    starts = [i for i, _, _ in found]
    names = {i: text for i, _, text in found}
    bounds = ([0] if not starts or starts[0] != 0 else []) + starts + [len(lines)]
    out = []
    for start, end in zip(bounds, bounds[1:]):
        name = names.get(start, "")
        inner = cleaned(lines[start + 1:end] if start in names else lines[start:end])
        text = block_text(inner)
        if name or text:
            out.append((name, text.split("\n") if text else []))
    return out


def note_text(text: str, max_chars: int) -> Tuple[bool, Dict[str, List[str]], bool]:
    """``(has content, sections, partly_read)`` of a note, cut at a heading boundary at ``max_chars``."""
    blocks = _blocks(_kept_lines(text))
    if not has_content("\n".join(line for _, block in blocks for line in block)):
        return False, {}, False
    units = [(SECTION_UNIT, name, "\n".join(block)) for name, block in blocks]
    cut = cut_at_boundary(units, max(1, max_chars))
    sections: Dict[str, List[str]] = {}
    for _, name, kept in cut.kept:
        sections.setdefault(name, []).extend(kept.split("\n") if kept else [])
    return True, sections, cut.partly_read


def _row(note: PreviousNote, state: str, path: Optional[str] = None, cause: Optional[str] = None) -> dict:
    row = {"kind": note.period.kind, "name": note.period.name, "role": note.role,
           "path": path, "state": state, "partly_read": False}
    if cause:
        row["cause"] = cause
    return row


def _resolve_one(reader, note: PreviousNote, max_chars: int) -> dict:
    if not note.configured:
        return _row(note, NOT_SET_UP)
    listing = _listing(reader, note)
    if note.folder in note.refused:
        return _row(note, NOT_READ, cause=REFUSED)
    if not listing:
        if not reader.answered(reader.dir_key(note.folder)):
            return _row(note, NOT_READ, cause=FAILED)
        return _row(note, MISSING)      # answered with nothing: "no note found", no key hint
    path = _path(note, listing)
    if path is None:
        return _row(note, MISSING)
    text = _guarded(note, path, lambda: reader.note(path))
    if path in note.refused:
        return _row(note, NOT_READ, path, REFUSED)
    if text is None:
        return _row(note, MISSING) if path in reader.missing else _row(note, NOT_READ, path, FAILED)
    content, sections, partly_read = note_text(str(text), max_chars)
    if not content:
        return _row(note, EMPTY, path)
    row = _row(note, FOUND, path)
    row.update(partly_read=partly_read, sections=sections)
    return row


def resolve(reader, notes: List[PreviousNote], *, max_chars: int) -> List[dict]:
    """One row per previous note, after the reader's ``finish()``; answers from the reader's cache."""
    return [_resolve_one(reader, note, max_chars) for note in notes]


def report_rows(rows: List[dict]) -> List[dict]:
    """The rows of ``resolve`` without their text: the report's ``previous``."""
    return [{k: v for k, v in row.items() if k != "sections"} for row in rows]

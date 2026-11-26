# review_digest.py — file checks of a /review unit digest and the carryover; the condensed.json job state.
# version: 0.2.0
"""Digest and carryover checks for ``/review`` condensing (spec 047 T4.2; PRD F1-AC1, F6-AC1, F6-AC2; ADR-4).

``check_digest(text, unit, read, *, read_id, cap_bytes)`` gives the errors of
one ``digests/<unit>.json`` text (``None`` when the file is missing) against
its ``weeks.json`` unit and the ``review_stage.load`` result; ``[]`` = valid.
``check_carryover(text, read, *, read_id)`` gives a ``CarryoverCheck``:
``errors``, ``whole`` (a whole-file failure), ``bad_items`` (indices of invalid
items), ``failed_notes`` (found previous-note paths those items rest on) and
``notes`` (every found previous-note path). ``settle_carryover(data, check)``
returns the carryover without the invalid items and the items of the failed
notes, the notes' ``items`` recounted.

Errors: the file-level ``digest-missing``, ``not-json``, ``schema (<pointer>)``,
``digest-too-large``, ``carryover-too-large`` bare; every other code as
``<pointer>: <code>``. No error holds a value of the file.

Size: ``cap_bytes`` counts the UTF-8 bytes of the digest as compact JSON
without the growth ``notes`` and without every ``sources`` list; those paths
are bound by ``source-duplicate`` (a path twice in one ``sources`` list) and
``growth-note-duplicate`` (a created note listed twice in ``growth``) beside
the unit checks. ``CARRYOVER_CAP`` counts the carryover's bytes as written.

Job state (``condensed.json``): ``new_state(read_id, units, *, carryover)``;
``advance(job, errors, *, count)`` and ``advance_carryover(job, check, *,
count)`` return the next job (``pending``/``retry`` → ``passed``; counted
failures → ``retry``, then ``failed`` at ``MAX_ATTEMPTS``; uncounted failures
change nothing; ``passed``, ``failed``, ``none`` are final); ``ready``,
``not_condensed``, ``nothing_condensed`` read a state.

No file I/O beyond the two schemas; no Kado, no model. Needs jsonschema.

Design notes: docs/tomo/scripts/lib/review_digest.md
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from lib.review_doc import Sources, note_stem
from lib.review_weeks import takes_part

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
DIGEST_SCHEMA = SCHEMAS / "review-digest.schema.json"
CARRYOVER_SCHEMA = SCHEMAS / "review-carryover.schema.json"
CARRYOVER_CAP = 12_288
MAX_ATTEMPTS = 2

PENDING, RETRY, PASSED, FAILED, NONE = "pending", "retry", "passed", "failed", "none"
_FINAL, _OPEN = (PASSED, FAILED, NONE), (PENDING, RETRY)

MISSING, NOT_JSON, DIGEST_TOO_LARGE, CARRYOVER_TOO_LARGE = (
    "digest-missing", "not-json", "digest-too-large", "carryover-too-large")
READ_ID, UNIT, DAYS = "read-id-mismatch", "unit-mismatch", "days-mismatch"
SOURCE_OUTSIDE, THEME_DAY_OUTSIDE, UNKNOWN_SECTION = (
    "source-outside-unit", "theme-day-outside-unit", "unknown-section")
GROWTH_NOTE_OUTSIDE, GROWTH_SOURCE_NOT_CREATED = "growth-note-outside-unit", "growth-source-not-created-day"
SOURCE_DUPLICATE, GROWTH_NOTE_DUPLICATE = "source-duplicate", "growth-note-duplicate"
NOTES_MISMATCH, CARRY_SOURCE_UNKNOWN, CARRY_ID_DUPLICATE = (
    "carryover-notes-mismatch", "carry-source-unknown", "carry-id-duplicate")

_ENTRY_GROUPS = ("done", "open", "notable")


# ---------------------------------------------------------------- shared file steps

def _pointer(parts: Sequence[Any]) -> str:
    return "/" + "/".join(str(p) for p in parts) if parts else "/"


def _err(parts: Sequence[Any], code: str) -> str:
    return f"{_pointer(parts)}: {code}"


def _schema_errors(data: Any, schema_path: Path) -> List[str]:
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"schema ({p})" for p in sorted({_pointer(e.absolute_path) for e in validator.iter_errors(data)})]


def _bytes_as_written(text: str, _data: Any) -> int:
    return len(text.encode("utf-8"))


def _parse(text: Optional[str], cap: int, too_large: str, schema: Path, size=_bytes_as_written):
    """``(data or None, file-level errors)``: data only when the text is schema-valid JSON."""
    if text is None:
        return None, [MISSING]
    try:
        data = json.loads(text)
    except ValueError:
        return None, [NOT_JSON]
    errors = [too_large] if size(text, data) > cap else []
    problems = _schema_errors(data, schema)
    return (None, errors + problems) if problems else (data, errors)


# ---------------------------------------------------------------- digests

def _without_paths(value: Any, drop: Sequence[str] = ("sources",)) -> Any:
    if isinstance(value, dict):
        return {k: _without_paths(v, ("sources", "notes") if k == "growth" else drop)
                for k, v in value.items() if k not in drop}
    if isinstance(value, list):
        return [_without_paths(v, drop) for v in value]
    return value


def digest_bytes(_text: str, data: Any) -> int:
    """What ``cap_bytes`` measures: the compact UTF-8 JSON without growth ``notes`` and ``sources`` lists."""
    return len(json.dumps(_without_paths(data), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def taking_part_days(unit: Mapping[str, Any], read: Mapping[str, Any]) -> List[str]:
    """The unit's days that take part (``review_weeks.takes_part``), in date order."""
    days = set(unit.get("days") or [])
    counts = Counter(str(c.get("day")) for c in (read.get("growth") or {}).get("created") or [])
    return sorted(str(e["date"]) for e in read.get("days") or []
                  if str(e.get("date")) in days and takes_part(e, counts.get(str(e["date"]), 0)))


def _weekly_stems(unit: Mapping[str, Any], read: Mapping[str, Any]) -> Set[str]:
    if not unit.get("weekly_note"):
        return set()
    for entry in read.get("weekly") or []:
        if entry.get("week") == unit.get("week") and entry.get("path"):
            return {str(entry["path"]), note_stem(str(entry["path"]))}
    return set()


class _Unit:
    """What a source, a day and a created note of one unit may be."""

    def __init__(self, unit: Mapping[str, Any], read: Mapping[str, Any]):
        self.days = set(unit.get("days") or [])
        self.sources = Sources.of(dict(read))
        self.weekly = _weekly_stems(unit, read)
        self.created = {str(c["path"]): str(c.get("day")) for c in (read.get("growth") or {}).get("created") or []
                        if str(c.get("day")) in self.days}

    def day_of(self, source: str) -> Optional[str]:
        daily = self.sources.daily_of(source)
        day = daily[0].isoformat() if daily else None
        return day if day in self.days else None


def _duplicates(at: List[Any], values: Sequence[str], seen: Set[str], code: str) -> List[str]:
    """One ``<pointer>: <code>`` per value already in ``seen``; ``seen`` grows."""
    errors = []
    for j, value in enumerate(values):
        if value.strip() in seen:
            errors.append(_err(at + [j], code))
        seen.add(value.strip())
    return errors


def _check_sources(scope: _Unit, at: List[Any], sources: List[str], weekly_ok: bool) -> List[str]:
    return [_err(at + [j], SOURCE_OUTSIDE) for j, s in enumerate(sources)
            if scope.day_of(s) is None and not (weekly_ok and s.strip() in scope.weekly)
            ] + _duplicates(at, sources, set(), SOURCE_DUPLICATE)


def _check_growth(scope: _Unit, i: int, candidate: dict, listed: Set[str]) -> List[str]:
    errors = _duplicates(["growth", i, "notes"], candidate["notes"], listed, GROWTH_NOTE_DUPLICATE)
    created_days = set()
    for j, path in enumerate(candidate["notes"]):
        if path in scope.created:
            created_days.add(scope.created[path])
        else:
            errors.append(_err(["growth", i, "notes", j], GROWTH_NOTE_OUTSIDE))
    for j, source in enumerate(candidate["sources"]):
        day = scope.day_of(source)
        if day is None:
            errors.append(_err(["growth", i, "sources", j], SOURCE_OUTSIDE))
        elif day not in created_days:
            errors.append(_err(["growth", i, "sources", j], GROWTH_SOURCE_NOT_CREATED))
    return errors + _duplicates(["growth", i, "sources"], candidate["sources"], set(), SOURCE_DUPLICATE)


def check_digest(text: Optional[str], unit: Mapping[str, Any], read: Mapping[str, Any], *, read_id: str,
                 cap_bytes: int) -> List[str]:
    """The errors of one unit's digest text; ``[]`` when it may be used."""
    data, errors = _parse(text, cap_bytes, DIGEST_TOO_LARGE, DIGEST_SCHEMA, size=digest_bytes)
    if data is None:
        return errors
    scope = _Unit(unit, read)
    if data["read_id"] != read_id:
        errors.append(_err(["read_id"], READ_ID))
    if data["unit"] != unit.get("unit"):
        errors.append(_err(["unit"], UNIT))
    if sorted(data["days"]) != taking_part_days(unit, read):
        errors.append(_err(["days"], DAYS))
    for group in _ENTRY_GROUPS + ("child_notes",):
        for i, entry in enumerate(data[group]):
            errors += _check_sources(scope, [group, i, "sources"], entry["sources"], group == "child_notes")
    for i, theme in enumerate(data["themes"]):
        errors += [_err(["themes", i, "days", j], THEME_DAY_OUTSIDE)
                   for j, d in enumerate(theme["days"]) if d not in scope.days]
        errors += _check_sources(scope, ["themes", i, "sources"], theme["sources"], False)
    keys = {str(d.get("key")) for d in read.get("sections") or [] if isinstance(d, dict)}
    for i, section in enumerate(data["sections"]):
        if section["key"] not in keys:
            errors.append(_err(["sections", i, "key"], UNKNOWN_SECTION))
        for k, entry in enumerate(section["items"]):
            errors += _check_sources(scope, ["sections", i, "items", k, "sources"], entry["sources"], False)
    listed: Set[str] = set()
    for i, candidate in enumerate(data["growth"]):
        errors += _check_growth(scope, i, candidate, listed)
    return errors


# ---------------------------------------------------------------- carryover

@dataclass
class CarryoverCheck:
    errors: List[str] = field(default_factory=list)
    whole: bool = False
    bad_items: List[int] = field(default_factory=list)
    failed_notes: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def _found(read: Mapping[str, Any]) -> List[dict]:
    return [p for p in read.get("previous") or [] if p.get("state") == "found" and p.get("path")]


def _note_of(found: Sequence[dict]) -> Dict[str, str]:
    """Source (path or stem) → found previous-note path."""
    out: Dict[str, str] = {}
    for p in found:
        out[str(p["path"])] = str(p["path"])
        out.setdefault(note_stem(str(p["path"])), str(p["path"]))
    return out


def check_carryover(text: Optional[str], read: Mapping[str, Any], *, read_id: str) -> CarryoverCheck:
    """The checks of the carryover text against the found previous notes."""
    found = _found(read)
    check = CarryoverCheck(notes=[str(p["path"]) for p in found])
    data, check.errors = _parse(text, CARRYOVER_CAP, CARRYOVER_TOO_LARGE, CARRYOVER_SCHEMA)
    if data is None:
        check.whole = True
        return check
    if data["read_id"] != read_id:
        check.errors.append(_err(["read_id"], READ_ID))
    expected = sorted((str(p["path"]), p.get("kind"), p.get("name")) for p in found)
    if sorted((n["path"], n["kind"], n["name"]) for n in data["notes"]) != expected:
        check.errors.append(_err(["notes"], NOTES_MISMATCH))
    check.whole = bool(check.errors)
    note_of, seen, failed = _note_of(found), set(), set()
    for i, item in enumerate(data["items"]):
        item_errors = [_err(["items", i, "sources", j], CARRY_SOURCE_UNKNOWN)
                       for j, s in enumerate(item["sources"]) if s.strip() not in note_of]
        if item["id"] in seen:
            item_errors.append(_err(["items", i, "id"], CARRY_ID_DUPLICATE))
        seen.add(item["id"])
        if item_errors:
            check.errors += item_errors
            check.bad_items.append(i)
            failed |= {note_of[s.strip()] for s in item["sources"] if s.strip() in note_of}
    check.failed_notes = [p for p in check.notes if p in failed]
    return check


def settle_carryover(data: Mapping[str, Any], check: CarryoverCheck) -> dict:
    """``data`` without its invalid items and the failed notes' items, ``items`` recounted.
    Apply once, on the checked data: ``bad_items`` index its original ``items`` list."""
    note_of = _note_of(data["notes"])

    def rests_on(item: dict, paths: Set[str]) -> bool:
        return any(note_of.get(s.strip()) in paths for s in item["sources"])

    kept = [dict(item) for i, item in enumerate(data["items"])
            if i not in check.bad_items and not rests_on(item, set(check.failed_notes))]
    notes = [dict(n, items=sum(1 for item in kept if rests_on(item, {n["path"]}))) for n in data["notes"]]
    return {**dict(data), "notes": notes, "items": kept}


# ---------------------------------------------------------------- the condensed.json state model

def new_state(read_id: str, units: Sequence[Mapping[str, Any]], *, carryover: bool) -> dict:
    """Every taking-part unit pending; the carryover pending, or ``none`` without a found previous note."""
    return {"read_id": read_id,
            "units": {str(u["unit"]): {"state": PENDING, "attempts": 0} for u in units if u.get("takes_part")},
            "carryover": {"state": PENDING if carryover else NONE, "attempts": 0, "notes": {}}}


def advance(job: Mapping[str, Any], errors: Sequence[str], *, count: bool) -> dict:
    """The job after one check: counted (``check``) or not (``plan`` validating a present file)."""
    state, attempts = job["state"], int(job["attempts"])
    if state in _FINAL:
        return dict(job)
    if not errors:
        return dict(job, state=PASSED, attempts=attempts + (1 if count else 0))
    if not count:
        return dict(job)
    attempts += 1
    return dict(job, state=FAILED if attempts >= MAX_ATTEMPTS else RETRY, attempts=attempts)


def advance_carryover(job: Mapping[str, Any], check: CarryoverCheck, *, count: bool) -> dict:
    """``advance`` for the carryover; after the last counted attempt an item failure fails only its notes."""
    nxt = advance(job, check.errors, count=count)
    if job["state"] in _FINAL or (nxt["state"] == job["state"] and not count):
        return nxt
    if nxt["state"] == PASSED:
        return dict(nxt, notes={p: PASSED for p in check.notes})
    if nxt["state"] != FAILED or check.whole:
        return dict(nxt, notes={})
    notes = {p: FAILED if p in check.failed_notes else PASSED for p in check.notes}
    # notes == {} cannot reach here: without a found note new_state sets the job to none.
    return dict(nxt, state=FAILED if all(s == FAILED for s in notes.values()) else PASSED, notes=notes)


def ready(state: Mapping[str, Any]) -> bool:
    """No job pending or in retry."""
    jobs = list((state.get("units") or {}).values()) + [state.get("carryover") or {"state": NONE}]
    return all(j["state"] not in _OPEN for j in jobs)


def not_condensed(state: Mapping[str, Any], units: Sequence[Mapping[str, Any]]) -> List[dict]:
    """``[{unit, days}]`` of the failed units, in unit order, with all their days."""
    jobs = state.get("units") or {}
    return [{"unit": u["unit"], "days": list(u["days"])} for u in units
            if (jobs.get(u["unit"]) or {}).get("state") == FAILED]


def nothing_condensed(state: Mapping[str, Any]) -> bool:
    """Every unit job failed."""
    jobs = list((state.get("units") or {}).values())
    return bool(jobs) and all(j["state"] == FAILED for j in jobs)

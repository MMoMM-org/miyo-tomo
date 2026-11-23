# review_stage.py — the stage a /review read rests in: day, growth, child and context files, weeks.json, the manifest.
# version: 0.1.0
"""The stage folder of a ``/review`` read (spec 047 T2.3; PRD F1-AC2, F2-AC3, F6-AC5, F7-AC1; ADR-1/2/3/10).

``write(stage, result, *, stem, rule, sections_digest)`` discards the stage's
earlier material (``discard``), then writes a ``read_period`` result as
``days/<date>.json`` (every day of the result), ``growth/<date>.json`` (the
created notes of a day, ``{path, links}`` by path; ``<date>-<n>.json``
overflow parts), ``children/<label>-<name>[-<n>].json``,
``previous/<kind>-<name>.json``, ``context.json`` (+ ``context-<n>.json``
parts), ``weeks.json`` and ``manifest.json`` last; every file is stamped with
one ``read_id``. Agent-read files are ``review_stage_codec.encode``d and each
kept ≤ ``FILE_CEILING`` bytes: an oversized day is re-cut and ``partly_read``,
a child note clipped (``clipped``). Returns the manifest.

``load(stage)`` gives back the result ``write`` was given, plus ``previous``,
``condensed`` (``condensed.json`` or ``None``) and ``carryover``
(``carryover.json`` when the condensed carryover passed, else ``None``).
``StageMissing``: no manifest (also a pre-047 stage); ``StageInvalid``: an
unreadable file or unsafe name; ``StageStale``: a file of another read.
``discard(stage)`` keeps only ``meta.json`` and ``payloads.json``.
``can_continue(stage, period, digest)`` and ``sections_digest(definitions)``
are the continue check.

Design notes: docs/tomo/scripts/lib/review_stage.md
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from lib import review_day, review_weeks
from lib import run_id as run_ids
from lib.note_io import atomic_write_text
from lib.period import Period, WeekRule
from lib.review_stage_codec import (FILE_CEILING, child_doc, child_entry, compact, day_doc, day_entry, encode, fit,
                                    growth_files, merge, pack_parts, place, previous_doc, previous_entry, size, spill, text_key)

LAYOUT = 1
MANIFEST, CONTEXT, WEEKS = "manifest.json", "context.json", "weeks.json"
CONDENSED, CARRYOVER = "condensed.json", "carryover.json"
DAYS, GROWTH, CHILDREN, PREVIOUS, DIGESTS = "days", "growth", "children", "previous", "digests"
CHILD_LABELS = ("weekly", "monthly")
KEPT = ("meta.json", "payloads.json")
NO_SECTIONS = "none"
_NOT_CONTEXT = ("days", "growth", "report", "not_read", "previous") + CHILD_LABELS
_CONTENT_FILE_RE = re.compile(r"(?:context(?:-\d+)?|read(?:-[\w-]+)?|weeks|carryover|proposals|condensed)\.json")
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.json")
_SECTION, _LINKED = review_day.SECTION_UNIT, review_day.LINKED_UNIT


class StageMissing(Exception):
    """The stage holds no manifest: no complete read."""


class StageInvalid(Exception):
    """A stage file cannot be read back."""


class StageStale(Exception):
    """A stage file belongs to another read."""


def _put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)


def _period_dict(period: Period) -> dict:
    return {"kind": period.kind, "name": period.name, "start": period.start.isoformat(),
            "end": period.end.isoformat()}


# ---------------------------------------------------------------- days

def _day_text(read_id: str, entry: dict) -> str:
    text = encode(day_doc(read_id, entry))
    if size(text) <= FILE_CEILING:
        return text
    sections, linked = entry.get("sections") or {}, entry.get("linked") or []
    units = [(_SECTION, name, t) for name, t in sections.items()]
    units += [(_LINKED, item["path"], item.get("text", "")) for item in linked]

    def render(kept: Sequence[Tuple[str, str, str]]) -> str:
        texts = {(kind, name): t for kind, name, t in kept}
        kept_sections = {n: texts[(_SECTION, n)] for n in sections if (_SECTION, n) in texts}
        kept_linked = [dict(item, text=texts[(_LINKED, item["path"])]) for item in linked
                       if (_LINKED, item["path"]) in texts]
        has = any(review_day.has_content(t) for t in kept_sections.values())
        return encode(day_doc(read_id, dict(entry, sections=kept_sections, linked=kept_linked,
                                             partly_read=True, has_content=has)))

    return fit(units, render)


# ---------------------------------------------------------------- children and previous

def _child_text(read_id: str, entry: dict) -> str:
    text = encode(child_doc(read_id, entry, False))
    if size(text) <= FILE_CEILING:
        return text
    key = text_key(entry)
    own = (entry.get(key) or {}) if key else {}
    blocks = entry.get("day_blocks") or {}
    units = [(_SECTION, f"t:{h}", t) for h, t in own.items()] + [(_SECTION, f"d:{d}", t) for d, t in blocks.items()]

    def render(kept: Sequence[Tuple[str, str, str]]) -> str:
        texts = {name: t for _, name, t in kept}
        clipped = dict(entry, day_blocks={d: texts[f"d:{d}"] for d in blocks if f"d:{d}" in texts})
        if key:
            clipped[key] = {h: texts[f"t:{h}"] for h in own if f"t:{h}" in texts}
        return encode(child_doc(read_id, clipped, True))

    return fit(units, render)


def _child_files(read_id: str, result: dict) -> Tuple[Dict[str, str], List[str]]:
    files: Dict[str, str] = {}
    labels = [label for label in CHILD_LABELS if label in result]
    for label in labels:
        for entry in result[label]:
            base = f"{label}-{entry.get('week') or entry.get('month')}"
            name, n = f"{base}.json", 1
            while name in files:
                n += 1
                name = f"{base}-{n}.json"
            files[name] = _child_text(read_id, entry)
    return files, labels


# ---------------------------------------------------------------- context and weeks

def _context_files(read_id: str, result: dict) -> Dict[str, str]:
    growth = result.get("growth") or {}
    context = {"read_id": read_id, **{k: v for k, v in result.items() if k not in _NOT_CONTEXT},
               "growth": {"created_count": len(growth.get("created") or []),
                          "mocs_changed": list(growth.get("mocs_changed") or []),
                          "mocs_linked_by_new": list(growth.get("mocs_linked_by_new") or [])},
               "fields": {d["date"]: d["fields"] for d in result["days"] if d.get("fields")}}
    text = encode(context)
    if size(text) <= FILE_CEILING:
        return {CONTEXT: text}
    head, items = spill(context, keep=("read_id", "period"))
    parts = pack_parts(items, lambda n, chunk: encode({"read_id": read_id, "part": n, **place(chunk)}), first=2)
    names = [f"context-{n}.json" for n in range(2, len(parts) + 2)]
    return {CONTEXT: encode(dict(head, parts=names)), **dict(zip(names, parts))}


def _weeks_text(read_id: str, result: dict, rule: WeekRule, day_texts: Dict[str, str],
                growth: Dict[str, Dict[str, str]], children: Dict[str, str]) -> str:
    period = Period.containing(result["period"]["kind"], date.fromisoformat(result["period"]["start"]), rule)
    created = {day: sum(len(json.loads(t)["created"]) for t in files.values()) for day, files in growth.items()}
    day_bytes = {date.fromisoformat(d): size(t) + sum(size(g) for g in growth.get(d, {}).values())
                 for d, t in day_texts.items()}
    taking = {date.fromisoformat(e["date"]) for e in result["days"]
              if review_weeks.takes_part(e, created.get(e["date"], 0))}
    units = review_weeks.units(period, rule, day_bytes, taking)
    for unit in units:
        unit["day_files"] = [f"{d}.json" for d in unit["days"]]
        unit["growth_files"] = [n for d in unit["days"] for n in growth.get(d, {})]
        weekly = f"weekly-{unit['week']}.json"
        unit["weekly_note"] = weekly if weekly in children else None
    return encode({"read_id": read_id, "rule": {"first_day": rule.first_day,
                                                "min_days_in_first_week": rule.min_days_in_first_week},
                   "budget_bytes": review_weeks.UNIT_BUDGET, "digest_cap_bytes": review_weeks.digest_cap(len(units)),
                   "units": units})


# ---------------------------------------------------------------- write

def write(stage: Path, result: dict, *, stem: str, rule: WeekRule, sections_digest: str,
          read_id: Optional[str] = None, read_at: Optional[str] = None) -> dict:
    """Discard the stage, write ``result`` as stage files, the manifest last; returns the manifest."""
    read_id = read_id or run_ids.generate()
    read_at = read_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    discard(stage)
    day_texts = {e["date"]: _day_text(read_id, e) for e in result["days"]}
    growth = growth_files(read_id, (result.get("growth") or {}).get("created") or [], result["period"]["start"])
    children, labels = _child_files(read_id, result)
    previous = {f"{e['kind']}-{e['name']}.json": encode(previous_doc(read_id, e)) for e in result.get("previous", [])}
    context = _context_files(read_id, result)
    for folder, files in ((DAYS, {f"{d}.json": t for d, t in day_texts.items()}),
                          (GROWTH, {n: t for day in growth.values() for n, t in day.items()}),
                          (CHILDREN, children), (PREVIOUS, previous)):
        for name, text in files.items():
            _put(stage / folder / name, text)
    for name, text in context.items():
        _put(stage / name, text)
    _put(stage / WEEKS, _weeks_text(read_id, result, rule, day_texts, growth, children))
    manifest = {"layout": LAYOUT, "read_id": read_id, "read_at": read_at, "stem": stem, "period": result["period"],
                "sections_digest": sections_digest,
                "files": {"days": [f"{d}.json" for d in day_texts],
                          "growth": [n for day in growth.values() for n in day], "children": list(children),
                          "previous": list(previous), "context": list(context), "weeks": WEEKS},
                "child_labels": labels, "report": result.get("report"), "not_read": result.get("not_read", [])}
    _put(stage / MANIFEST, compact(manifest))
    return manifest


# ---------------------------------------------------------------- load

def _object(path: Path) -> dict:
    if not _NAME_RE.fullmatch(path.name):
        raise StageInvalid(f"unsafe stage file name: {path.name!r}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise StageInvalid(f"{path.name} unreadable") from None
    except ValueError:
        raise StageInvalid(f"{path.name} is not JSON") from None
    if not isinstance(data, dict):
        raise StageInvalid(f"{path.name} is not an object")
    return data


def _stamped(path: Path, read_id: str) -> dict:
    data = _object(path)
    if data.get("read_id") != read_id:
        raise StageStale(f"{path.name} belongs to another read")
    return data


def _manifest(stage: Path) -> dict:
    if not (stage / MANIFEST).is_file():
        raise StageMissing(f"no {MANIFEST} in {stage.name}")
    manifest = _object(stage / MANIFEST)
    if not isinstance(manifest.get("read_id"), str) or not isinstance(manifest.get("files"), dict):
        raise StageInvalid(f"{MANIFEST} has no read_id or file list")
    return manifest


def load(stage: Path) -> dict:
    """The read result of the stage plus ``previous``, ``condensed`` and ``carryover``."""
    manifest = _manifest(stage)
    read_id, files = manifest["read_id"], manifest["files"]
    names = files.get("context") or [CONTEXT]
    context = _stamped(stage / names[0], read_id)
    for name in context.get("parts") or []:
        part = _stamped(stage / name, read_id)
        merge(context, {k: v for k, v in part.items() if k not in ("read_id", "part")})
    _stamped(stage / files.get("weeks", WEEKS), read_id)
    created: List[dict] = []
    for name in files.get("growth", []):
        doc = _stamped(stage / GROWTH / name, read_id)
        created += [dict(c, day=doc["date"]) for c in doc["created"]]
    growth = context.get("growth") or {}
    result = {k: v for k, v in context.items() if k not in ("read_id", "parts", "fields", "growth")}
    result["growth"] = {"created": sorted(created, key=lambda c: c["path"]),
                        "mocs_changed": growth.get("mocs_changed", []),
                        "mocs_linked_by_new": growth.get("mocs_linked_by_new", [])}
    result.update(period=manifest["period"], report=manifest.get("report"), not_read=manifest.get("not_read", []),
                  days=[day_entry(_stamped(stage / DAYS / n, read_id)) for n in files.get("days", [])])
    for label in manifest.get("child_labels", []):
        result[label] = []
    for name in files.get("children", []):
        result.setdefault(name.split("-", 1)[0], []).append(child_entry(_stamped(stage / CHILDREN / name, read_id)))
    result["previous"] = [previous_entry(_stamped(stage / PREVIOUS / n, read_id)) for n in files.get("previous", [])]
    condensed = _stamped(stage / CONDENSED, read_id) if (stage / CONDENSED).exists() else None
    result["condensed"] = condensed
    passed = ((condensed or {}).get("carryover") or {}).get("state") == "passed"
    result["carryover"] = _stamped(stage / CARRYOVER, read_id) if passed else None
    return result


# ---------------------------------------------------------------- discard and continue

def discard(stage: Path) -> None:
    """Delete every stage file that may hold note content (the manifest first); keep meta.json and payloads.json."""
    if not stage.is_dir():
        return
    (stage / MANIFEST).unlink(missing_ok=True)
    for folder in (DAYS, GROWTH, CHILDREN, PREVIOUS, DIGESTS):
        shutil.rmtree(stage / folder, ignore_errors=True)
    for path in stage.iterdir():
        if path.is_file() and path.name not in KEPT and _CONTENT_FILE_RE.fullmatch(path.name):
            path.unlink()


def sections_digest(definitions: Optional[Sequence[dict]]) -> str:
    """``sha256:<hex>`` of the canonical JSON of the section definitions; ``none`` without any."""
    if not definitions:
        return NO_SECTIONS
    canonical = json.dumps(list(definitions), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("ascii")).hexdigest()


def can_continue(stage: Path, period: Period, digest: str) -> bool:
    """Whether the stored read matches layout, period, kind and section digest."""
    try:
        manifest = _manifest(stage)
    except (StageMissing, StageInvalid):
        return False
    return (manifest.get("layout") == LAYOUT and manifest.get("period") == _period_dict(period)
            and manifest.get("sections_digest") == digest)

# review_stage_codec.py — the bytes of a /review stage file: line-broken encoding, the ceiling, cutting and parts.
# version: 0.1.1
"""Encoding and size rules of the agent-read stage files (spec 047 T2.3; ADR-2), split out of ``review_stage``.

``encode(data)`` is the one written form: ``indent=1``, UTF-8 (``ensure_ascii``
off), one trailing newline; ``size(text)`` its UTF-8 bytes, the measure of
``FILE_CEILING``. ``lines_of(text)`` stores a text as its lines (a line over
``LINE_PIECE`` characters as a list of pieces); ``join_text`` gives it back.
``fit(units, render)`` re-cuts ``(kind, name, text)`` units through
``review_day.cut_at_boundary`` until ``render(kept)`` fits the ceiling:
three tries on a shrinking limit, then the hard cut of the first section
alone, shrunk by the overshoot until it fits or the limit is 1; every limit
≥ 1. ``day_text(read_id, entry)`` / ``child_text(read_id, entry)`` give a
day / child file's text and whether it was cut (``partly_read`` /
``clipped``); ``mark_partly_read(report, dates)`` a copy of the read report
with the dailies of those dates ``partly-read`` (``failed`` kept). ``pack_parts(items, render)`` packs items greedily
into rendered parts, each ≤ the ceiling unless one item alone is over it.
``spill(doc, keep)`` moves every list item and every entry of a
dict-of-dicts out of ``doc`` (keys in ``keep`` stay), ``place(items)`` builds
a partial doc from moved items, ``merge(into, part)`` joins a part back
(lists extended, dicts merged). ``day_doc`` / ``child_doc`` /
``previous_doc`` turn an entry into its file doc (texts as lines, the
``read_id``; a child's ``clipped``), ``day_entry`` / ``child_entry`` /
``previous_entry`` back; ``growth_files`` packs the created notes per day.
``compact`` is the script-only form of ``manifest.json``. No file I/O.

Design notes: docs/tomo/scripts/lib/review_stage_codec.md
"""
from __future__ import annotations

import copy
import json
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from lib import review_day
from lib.review_weeks import FILE_CEILING

LINE_PIECE = 1_000
_TRIES = (1.0, 0.8, 0.6)

Unit = Tuple[str, str, str]
Item = Tuple[Tuple[str, ...], bool, Any]

__all__ = ["FILE_CEILING", "LINE_PIECE", "child_doc", "child_entry", "child_text", "compact", "day_doc", "day_entry",
           "day_text", "encode", "fit", "growth_files", "join_text", "lines_of", "mark_partly_read", "merge",
           "pack_parts", "place", "previous_doc", "previous_entry", "size", "spill", "text_key"]


def encode(data: Any) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def size(text: str) -> int:
    return len(text.encode("utf-8"))


def lines_of(text: str) -> list:
    """``text`` as its lines; a line over ``LINE_PIECE`` characters as a list of pieces."""
    return [line if len(line) <= LINE_PIECE else [line[i:i + LINE_PIECE] for i in range(0, len(line), LINE_PIECE)]
            for line in str(text).split("\n")]


def join_text(lines: Any) -> str:
    if isinstance(lines, str):
        return lines
    return "\n".join(line if isinstance(line, str) else "".join(line) for line in lines)


def fit(units: Sequence[Unit], render: Callable[[Sequence[Unit]], str]) -> str:
    """``render`` of the units ``cut_at_boundary`` keeps under a limit that makes the text fit the ceiling."""
    room = max(1, FILE_CEILING - size(render([])))
    for factor in _TRIES:
        text = render(review_day.cut_at_boundary(units, max(1, int(room * factor))).kept)
        if size(text) <= FILE_CEILING:
            return text
    first = list(units[:1]) if units and units[0][0] == review_day.SECTION_UNIT else []
    base, limit = size(render([])), max(1, int(room * _TRIES[-1]))
    while True:
        text = render(review_day.cut_at_boundary(first, limit).kept)
        over = size(text) - base
        if not first or size(text) <= FILE_CEILING or limit == 1:
            return text
        limit = max(1, min(limit - 1, limit * room // max(1, over)))


def day_text(read_id: str, entry: dict) -> Tuple[str, bool]:
    """``(the day file's text, whether it was re-cut)``; a re-cut day is ``partly_read``, ``has_content`` recomputed."""
    text = encode(day_doc(read_id, entry))
    if size(text) <= FILE_CEILING:
        return text, False
    sections, linked = entry.get("sections") or {}, entry.get("linked") or []
    units = [(review_day.SECTION_UNIT, name, t) for name, t in sections.items()]
    units += [(review_day.LINKED_UNIT, item["path"], item.get("text", "")) for item in linked]

    def render(kept: Sequence[Unit]) -> str:
        texts = {(kind, name): t for kind, name, t in kept}
        kept_sections = {n: texts[(review_day.SECTION_UNIT, n)] for n in sections
                         if (review_day.SECTION_UNIT, n) in texts}
        kept_linked = [dict(item, text=texts[(review_day.LINKED_UNIT, item["path"])]) for item in linked
                       if (review_day.LINKED_UNIT, item["path"]) in texts]
        has = any(review_day.has_content(t) for t in kept_sections.values())
        return encode(day_doc(read_id, dict(entry, sections=kept_sections, linked=kept_linked,
                                             partly_read=True, has_content=has)))

    return fit(units, render), True


def child_text(read_id: str, entry: dict) -> str:
    """The child file's text, clipped at a heading boundary (``clipped``) when over the ceiling."""
    text = encode(child_doc(read_id, entry, False))
    if size(text) <= FILE_CEILING:
        return text
    key = text_key(entry)
    own = (entry.get(key) or {}) if key else {}
    blocks = entry.get("day_blocks") or {}
    units = [(review_day.SECTION_UNIT, f"t:{h}", t) for h, t in own.items()]
    units += [(review_day.SECTION_UNIT, f"d:{d}", t) for d, t in blocks.items()]

    def render(kept: Sequence[Unit]) -> str:
        texts = {name: t for _, name, t in kept}
        clipped = dict(entry, day_blocks={d: texts[f"d:{d}"] for d in blocks if f"d:{d}" in texts})
        if key:
            clipped[key] = {h: texts[f"t:{h}"] for h in own if f"t:{h}" in texts}
        return encode(child_doc(read_id, clipped, True))

    return fit(units, render)


def mark_partly_read(report: Any, dates: Sequence[str]) -> Any:
    """A deep copy of ``report`` with every non-``failed`` daily of ``dates`` set to ``partly-read``."""
    marked = copy.deepcopy(report)
    wanted = set(dates)
    days = marked.get("days") if isinstance(marked, dict) else None
    for day in days or []:
        if isinstance(day, dict) and day.get("date") in wanted:
            for daily in day.get("dailies") or []:
                if isinstance(daily, dict) and daily.get("state") != "failed":
                    daily["state"] = "partly-read"
    return marked


def pack_parts(items: Sequence[Any], render: Callable[[int, List[Any]], str], first: int = 1) -> List[str]:
    """Rendered parts numbered from ``first``, items in order, a part closed before the item that overflows it."""
    parts: List[str] = []
    chunk: List[Any] = []
    for item in items:
        trial = chunk + [item]
        if chunk and size(render(first + len(parts), trial)) > FILE_CEILING:
            parts.append(render(first + len(parts), chunk))
            chunk = [item]
        else:
            chunk = trial
    parts.append(render(first + len(parts), chunk))
    return parts


def _spill_value(path: Tuple[str, ...], value: Any, items: List[Item]) -> Any:
    if isinstance(value, list):
        items.extend((path, False, v) for v in value)
        return []
    if isinstance(value, dict):
        if value and all(isinstance(v, dict) for v in value.values()):
            items.extend((path + (k,), True, v) for k, v in value.items())
            return {}
        return {k: _spill_value(path + (k,), v, items) for k, v in value.items()}
    return value


def spill(doc: Dict[str, Any], keep: Sequence[str]) -> Tuple[Dict[str, Any], List[Item]]:
    """``(doc emptied of its list items and dict-of-dict entries, the moved items in order)``."""
    items: List[Item] = []
    head = {k: (v if k in keep else _spill_value((k,), v, items)) for k, v in doc.items()}
    return head, items


def place(items: Sequence[Item]) -> Dict[str, Any]:
    """A partial doc holding ``items`` at their paths."""
    out: Dict[str, Any] = {}
    for path, keyed, value in items:
        node = out
        for key in path[:-1]:
            node = node.setdefault(key, {})
        if keyed:
            node[path[-1]] = value
        else:
            node.setdefault(path[-1], []).append(value)
    return out


def merge(into: Dict[str, Any], part: Dict[str, Any]) -> Dict[str, Any]:
    """Join ``part`` into ``into``: lists extended, dicts merged, anything else set."""
    for key, value in part.items():
        if isinstance(value, list) and isinstance(into.get(key), list):
            into[key].extend(value)
        elif isinstance(value, dict) and isinstance(into.get(key), dict):
            merge(into[key], value)
        else:
            into[key] = value
    return into


# ---------------------------------------------------------------- per-file docs

def compact(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, separators=(",", ":")) + "\n"


def day_doc(read_id: str, entry: dict) -> dict:
    doc = {"read_id": read_id, **entry}
    if "sections" in entry:
        doc["sections"] = {name: lines_of(text) for name, text in entry["sections"].items()}
    if "linked" in entry:
        doc["linked"] = [dict(item, text=lines_of(item["text"])) if "text" in item else item
                         for item in entry["linked"]]
    return doc


def day_entry(doc: dict) -> dict:
    entry = {k: v for k, v in doc.items() if k != "read_id"}
    if "sections" in entry:
        entry["sections"] = {name: join_text(lines) for name, lines in entry["sections"].items()}
    if "linked" in entry:
        entry["linked"] = [dict(item, text=join_text(item["text"])) if "text" in item else item
                           for item in entry["linked"]]
    return entry


def text_key(entry: dict) -> Optional[str]:
    return next((k for k, v in entry.items() if k.endswith("_text") and isinstance(v, dict)), None)


def child_doc(read_id: str, entry: dict, clipped: bool) -> dict:
    doc = {"read_id": read_id, **entry, "clipped": clipped}
    key = text_key(entry)
    for name in ("day_blocks", key):
        if name and isinstance(entry.get(name), dict):
            doc[name] = {k: lines_of(v) for k, v in entry[name].items()}
    return doc


def child_entry(doc: dict) -> dict:
    entry = {k: v for k, v in doc.items() if k != "read_id" and not (k == "clipped" and not v)}
    for name in ("day_blocks", text_key(entry)):
        if name and isinstance(entry.get(name), dict):
            entry[name] = {k: join_text(v) for k, v in entry[name].items()}
    return entry


def previous_doc(read_id: str, entry: dict) -> dict:
    doc = {"read_id": read_id, **entry}
    if isinstance(entry.get("sections"), dict):
        doc["sections"] = {h: lines_of(t) for h, t in entry["sections"].items()}
    return doc


def previous_entry(doc: dict) -> dict:
    entry = {k: v for k, v in doc.items() if k != "read_id"}
    if isinstance(entry.get("sections"), dict):
        entry["sections"] = {h: join_text(v) for h, v in entry["sections"].items()}
    return entry


def growth_files(read_id: str, created: Sequence[dict], first_day: str) -> Dict[str, Dict[str, str]]:
    """``{date: {name: text}}`` of the created notes per creation day, parts at entry boundaries."""
    by_day: Dict[str, List[dict]] = {}
    for item in created:
        by_day.setdefault(str(item.get("day") or first_day), []).append(
            {"path": item["path"], "links": item.get("links", [])})
    out: Dict[str, Dict[str, str]] = {}
    for day in sorted(by_day):
        entries = sorted(by_day[day], key=lambda c: c["path"])

        def render(n: int, chunk: List[dict], day: str = day) -> str:
            return encode({"read_id": read_id, "date": day, **({"part": n} if n > 1 else {}), "created": chunk})

        out[day] = {(f"{day}.json" if n == 1 else f"{day}-{n}.json"): text
                    for n, text in enumerate(pack_parts(entries, render), 1)}
    return out

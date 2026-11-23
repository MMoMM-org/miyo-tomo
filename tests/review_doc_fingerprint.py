#!/usr/bin/env python3
# version: 0.1.1
"""review_doc_fingerprint.py — the structure of a /review document, without its wording (spec 047 ADR-11).

Spec 047 rebuilds how /review reads a period and writes its document; PRD F2-AC1
asks that the document keeps its shape. ``fingerprint(document_text)`` reads a
rendered ``<period> Review.md`` and returns a dict of structure only:

- ``approved``: the ``- [ ] Approved`` box (True / False, None when missing);
- ``callout``: the info callout's fields — the target state key (``exists`` / ``created`` /
  ``elsewhere``), the placement key (``before`` / ``inside``) and the counts of not-read and
  partly-read entries; ``top_lines``: other non-blank lines above the first part (spec 047 adds
  previous-note and not-condensed lines there);
- ``parts``: the part order — a group key by the heading label table (every language), a section key
  ``sN`` for a ``%%sN%%`` heading, ``review`` for the ``%%review%%`` divider, ``unknown`` otherwise;
  ``groups``: the group keys alone; ``sections``: each section's checkbox (True / False / None);
- ``counts``: items per part; ``marks``: per part, per item, the mark suffix keys (``weekly_only`` …,
  any ``mark_*`` label the table carries); ``links``: per part, per item, the kind of each source link
  (``daily`` / ``weekly`` / ``monthly`` / ``quarterly`` / ``previous`` / ``other``); ``habits``: the
  numbers of each habit item (script-rendered, never model wording).

A link is ``previous`` when its stem names a week, month or quarter that ends before the document's
period starts (``review_kind`` / ``review_period`` from the frontmatter; weeks are ISO weeks); a
periodic note overlapping the period keeps its kind. Item text, continuation lines, headings and
link stems never enter the fingerprint. ``diff(a, b)`` names the keys that differ — ``key`` or, for a
dict-valued key, ``key.subkey`` — sorted.

Test helper only: reads text, no Kado, no file I/O.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import yaml

from lib import review_doc as rd
from lib import review_sections as rs

_FENCE = "---"
_HEADING = re.compile(r"^## (.*?)[\s#]*$")
_ITEM = re.compile(r"^- \[([ xX])\] (.*)$")
_APPROVED = re.compile(r"^- \[([ xX])\] Approved\s*$")
_SECTION = re.compile(r"%%(s\d{1,3})%%")
_ID_TAIL = re.compile(r"\s*%%t\d+%%\s*$")
_LINKS_TAIL = re.compile(r" \((\[\[[^\]]+\]\](?:, \[\[[^\]]+\]\])*)\)$")
_STEM = re.compile(r"\[\[([^\]|#]+)")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_DAILY = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_WEEK = re.compile(r"(?<!\d)(\d{4})-W(\d{2})(?!\d)")
_QUARTER = re.compile(r"(?<!\d)(\d{4})-Q([1-4])(?!\d)")
_MONTH = re.compile(r"(?<!\d)(\d{4})-(\d{2})(?![\d-])")
_KIND_OF = {"week": "weekly", "month": "monthly", "quarter": "quarterly"}
REVIEW, UNKNOWN = "review", "unknown"


def _words(key: str) -> List[str]:
    return [table[key] for table in rd._LABELS.values() if key in table]


def _mark_words() -> List[Tuple[str, str]]:
    """``(suffix, mark key)`` for every ``mark_*`` label of every language, longest first."""
    pairs = {(f" · {word}", key[len("mark_"):]) for table in rd._LABELS.values()
             for key, word in table.items() if key.startswith("mark_")}
    return sorted(pairs, key=lambda p: -len(p[0]))


# --- periods ------------------------------------------------------------------------------------

def _month_span(year: int, month: int) -> Tuple[date, date]:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return date(year, month, 1), nxt - timedelta(days=1)


def _span(kind: str, name: str) -> Optional[Tuple[date, date]]:
    """The first and last day of a week / month / quarter named like ``2026-W13`` / ``2026-03`` / ``2026-Q1``."""
    try:
        if kind == "week" and (m := _WEEK.fullmatch(name)):
            start = date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
            return start, start + timedelta(days=6)
        if kind == "month" and (m := _MONTH.fullmatch(name)):
            return _month_span(int(m.group(1)), int(m.group(2)))
        if kind == "quarter" and (m := _QUARTER.fullmatch(name)):
            first = 3 * int(m.group(2)) - 2
            return _month_span(int(m.group(1)), first)[0], _month_span(int(m.group(1)), first + 2)[1]
    except ValueError:
        return None
    return None


def _link_kind(stem: str, period_start: Optional[date]) -> str:
    if _DAILY.search(stem):
        return "daily"
    for kind, pattern in (("week", _WEEK), ("quarter", _QUARTER), ("month", _MONTH)):
        m = pattern.search(stem)
        span = _span(kind, m.group(0)) if m else None
        if span is not None:
            return "previous" if period_start is not None and span[1] < period_start else _KIND_OF[kind]
    return "other"


# --- the document -------------------------------------------------------------------------------

def _split(text: str) -> Tuple[dict, List[str]]:
    lines = text.lstrip("﻿").splitlines()
    if lines and lines[0].strip() == _FENCE:
        for index in range(1, len(lines)):
            if lines[index].strip() == _FENCE:
                try:
                    front = yaml.safe_load("\n".join(lines[1:index]))
                except yaml.YAMLError:
                    front = None
                return (front if isinstance(front, dict) else {}), lines[index + 1:]
    return {}, lines


def _callout(line: str) -> Dict[str, Any]:
    body = line[len("> [!info] "):]
    fields = body.split(" · ")
    out: Dict[str, Any] = {"target": None, "placement": None, "not_read": 0, "partly_read": 0}
    target = fields[0] if fields else ""
    if any(target.endswith(f"({w})") for w in _words("exists")):
        out["target"] = "exists"
    elif any(target.endswith(f"({w})") for w in _words("created")):
        out["target"] = "created"
    elif any(f"({w.split('{')[0]}" in target for w in _words("elsewhere")):
        out["target"] = "elsewhere"
    for field in fields[1:]:
        for key in ("before", "inside"):
            if any(field.startswith(f'{w} "') for w in _words(key)):
                out["placement"] = key
        for key in ("not_read", "partly_read"):
            for word in _words(key):
                if field.startswith(f"{word}: "):
                    out[key] = len(field[len(word) + 2:].split(", "))
    return out


def _part_of(heading: str, labels: Dict[str, str]) -> str:
    section = _SECTION.search(heading)
    if section:
        return section.group(1)
    if rs.REVIEW_ID in heading:
        return REVIEW
    return labels.get(heading, UNKNOWN)


def _item_shape(rest: str, period_start: Optional[date], marks: List[Tuple[str, str]]) -> Tuple[list, list]:
    """``(mark keys, link kinds)`` of an item's checkbox line, read from its tail only."""
    line = _ID_TAIL.sub("", rest)
    found: List[str] = []
    stripped = True
    while stripped:
        stripped = False
        for suffix, key in marks:
            if line.endswith(suffix):
                line, stripped = line[: -len(suffix)], True
                found.insert(0, key)
                break
    tail = _LINKS_TAIL.search(line)
    kinds = [_link_kind(s.strip(), period_start) for s in _STEM.findall(tail.group(1))] if tail else []
    return found, kinds


def fingerprint(document_text: str) -> Dict[str, Any]:
    """The structure of a review document; never its wording."""
    front, body = _split(document_text)
    span = _span(str(front.get("review_kind")), str(front.get("review_period")))
    period_start = span[0] if span else None
    labels = rd.group_labels()
    marks = _mark_words()
    fp: Dict[str, Any] = {"approved": None, "callout": None, "top_lines": 0, "parts": [], "groups": [],
                          "sections": {}, "counts": {}, "marks": {}, "links": {}, "habits": []}
    part: Optional[str] = None
    for line in body:
        if not line.strip():
            continue
        gate = _APPROVED.match(line)
        if gate and fp["approved"] is None:
            fp["approved"] = gate.group(1).lower() == "x"
            continue
        heading = _HEADING.match(line)
        if heading:
            part = _part_of(heading.group(1), labels)
            fp["parts"].append(part)
            if part in rd.GROUPS:
                fp["groups"].append(part)
            for key in ("counts", "marks", "links"):
                fp[key].setdefault(part, 0 if key == "counts" else [])
            continue
        if part is None:
            if line.startswith("> [!info] ") and fp["callout"] is None:
                fp["callout"] = _callout(line)
            elif not line.startswith("# "):
                fp["top_lines"] += 1
            continue
        item = _ITEM.match(line)
        if not item:
            continue
        box = _SECTION.search(item.group(2))
        if box and box.group(1) == part:
            fp["sections"][part] = item.group(1).lower() == "x"
            continue
        found, kinds = _item_shape(item.group(2), period_start, marks)
        fp["counts"][part] += 1
        fp["marks"][part].append(found)
        fp["links"][part].append(kinds)
        if part == rd.HABITS:
            fp["habits"].append(_NUMBER.findall(_ID_TAIL.sub("", item.group(2))))
    for key in fp["parts"]:
        if re.fullmatch(r"s\d{1,3}", key):
            fp["sections"].setdefault(key, None)
    return fp


def diff(a: Dict[str, Any], b: Dict[str, Any]) -> List[str]:
    """The keys whose values differ; ``key.subkey`` inside a dict-valued key; sorted."""
    out: List[str] = []
    for key in sorted(set(a) | set(b)):
        va, vb = a.get(key), b.get(key)
        if va == vb:
            continue
        if isinstance(va, dict) and isinstance(vb, dict):
            out.extend(f"{key}.{sub}" for sub in sorted(set(va) | set(vb), key=str) if va.get(sub) != vb.get(sub))
        else:
            out.append(key)
    return out

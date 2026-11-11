# review_day.py — one day of /review: the daily's kept sections, fields, tasks and same-day notes.
# version: 0.3.0
"""Reading one day for ``/review`` (spec 045, T3.2; PRD F3-AC1..4, F3-AC8).

``read_day(day, dailies, settings, read_note)`` turns the daily text(s) of
one date into one ``ReadResult.days[]`` entry (SDD "same-day reading of one
daily"): same-day links collected from the whole body outside
``skip_sections`` and read once through ``read_note``; the configured
``sections`` kept with their subsections, or the whole body under ``text``
when no configured heading is found; query and embed fences and inline
queries dropped, never executed; a thematic break and the navigation block
behind it dropped, the words after a break kept; a same-day note without
its embeds, other-day sections, METADATA callout and navigation-only
lines; raw ``Name:: v`` fields, tasks with their ✅ date, the
``max_chars_per_day`` cap on a section boundary, ``has_content`` beyond the
template skeleton. The yesterday-named fields go to ``previous_day_fields``;
``attribute_yesterday`` moves them onto the entry dated D-1 and
``yesterday_fields`` reads only those of one text. ``task_note_tasks`` and
``done_in_period`` are the period-level task rules; ``day_settings`` builds
the settings dict. The markdown mechanics are ``lib/review_md.py``'s.
No Kado, no model, no file I/O.

Design notes: docs/tomo/scripts/lib/review_day.md
"""
from __future__ import annotations

import copy
import posixpath
import re
from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from lib.review_config import DEFAULT_MAX_CHARS, ReviewSetup
from lib.review_md import (HEADING_RE, INLINE_QUERY_RE, ISO_DATE_RE, LINK_RE, RULE_RE, YEAR_RE, block_text,
                           body, cleaned, fence_state, has_token, headings, is_navigation, metadata_mask,
                           ranges, trailing_navigation)
from lib.vault_config_edit import get_path

DEFAULT_DATE_FORMAT = "YYYY-MM-DD"
LINKED_MISSING = "linked-missing"
OPEN_TODAY = "open today"
TEXT_SECTION = "text"
KIND_MARKS = (("planner", ("planner", "dp-")), ("journal", ("journal", "5year", "5j-")))

_EMBED_LINE_RE = re.compile(r"^\s*(?:>\s*)*!\[\[")
_FIELD_RE = re.compile(r"^[\s>*+-]*(\*\*)?([A-Za-z][\w .&/-]*?)(?(1)\*\*)::(?!:)\s*(.*?)\s*$")
_TRAILING_LINK_RE = re.compile(r"\s*(?:\[\[[^\]]*\]\]|\[[^\]]*\]\([^)]*\))\s*$")
_TASK_RE = re.compile(r"^\s*(?:>\s*)*[-*+]\s+\[([ xX])\]\s+(.*?)\s*$")
_DONE_RE = re.compile(r"\s*✅\s*(\d{4}-\d{2}-\d{2})")
_TEMPLATER_RE = re.compile(r"<%.*?%>", re.DOTALL)
_INPUT_RE = re.compile(r"`INPUT\[[^`]*\]`")
_PLACEHOLDER_RES = (_TEMPLATER_RE, _INPUT_RE, INLINE_QUERY_RE)
_DAY_TOKEN_RE = re.compile(r"\[([^\]]*)\]|YYYY|YY|MM|M|DD|D")

ReadNote = Callable[[str], Optional[str]]


# --- settings -----------------------------------------------------------------------------

def yesterday_field_names(config: dict) -> List[str]:
    """The tracker names of ``trackers.daily_note_trackers.yesterday_fields``, in config order."""
    found, entries = get_path(config, ("trackers", "daily_note_trackers", "yesterday_fields"))
    if not found or not isinstance(entries, list):
        return []
    return [e["name"] for e in entries if isinstance(e, dict) and isinstance(e.get("name"), str) and e["name"]]


def day_settings(setup: ReviewSetup, config: dict) -> dict:
    """The ``settings`` dict of ``read_day`` from a ReviewSetup and the config."""
    pattern = get_path(config, ("naming", "calendar_patterns", "daily"))[1]
    return {
        "sections": list(setup.daily_sections),
        "skip_sections": list(setup.skip_sections),
        "task_notes": list(setup.task_notes),
        "max_chars_per_day": setup.max_chars_per_day,
        "date_format": pattern if isinstance(pattern, str) and pattern.strip() else DEFAULT_DATE_FORMAT,
        "yesterday_fields": yesterday_field_names(config),
    }


def render_day(day: date, fmt: str) -> str:
    """``day`` in a Moment-style name format (``YYYY``, ``YY``, ``MM``, ``M``, ``DD``, ``D``, ``[literal]``)."""
    values = {"YYYY": f"{day.year:04d}", "YY": f"{day.year % 100:02d}", "MM": f"{day.month:02d}",
              "M": str(day.month), "DD": f"{day.day:02d}", "D": str(day.day)}
    return _DAY_TOKEN_RE.sub(lambda m: m.group(1) if m.group(1) is not None else values[m.group(0)], fmt)


# --- links, fields, tasks, content --------------------------------------------------------

def _target(raw: str) -> str:
    name = raw.strip().replace("\\", "/")
    name = posixpath.basename(name.rstrip("/"))
    return name[:-3] if name.lower().endswith(".md") else name


def _links(lines: Iterable[str]) -> List[str]:
    """Wiki-link and embed targets, once each, in order of first appearance."""
    out: List[str] = []
    for line in lines:
        for raw in LINK_RE.findall(line):
            target = _target(raw)
            if target and target not in out:
                out.append(target)
    return out


def _fields(lines: Iterable[str]) -> Dict[str, str]:
    """``Name:: value`` and ``**Name**:: value`` with a value; a trailing link is cut, a meta-bind input is no value."""
    out: Dict[str, str] = {}
    for line in lines:
        match = _FIELD_RE.match(line)
        if not match:
            continue
        name, value = match.group(2).strip(), match.group(3)
        value = _INPUT_RE.sub("", value).strip()
        while True:
            cut = _TRAILING_LINK_RE.sub("", value)
            if cut == value:
                break
            value = cut
        if name and value:
            out[name] = value
    return out


def _tasks(lines: Iterable[str], source: str) -> List[dict]:
    out: List[dict] = []
    for line in lines:
        match = _TASK_RE.match(line)
        if not match:
            continue
        done, text = match.group(1).lower() == "x", match.group(2)
        found = _DONE_RE.search(text)
        done_date = found.group(1) if found else None
        text = _DONE_RE.sub("", text).strip()
        if text:
            out.append({"text": text, "done": done, "done_date": done_date, "source": source})
    return out


def _is_content(line: str) -> bool:
    s = re.sub(r"^(?:>\s*)+", "", line.strip())
    if not s or s.startswith("[!") or s.startswith("<") or RULE_RE.match(s) or HEADING_RE.match(s):
        return False
    for placeholder in _PLACEHOLDER_RES:
        s = placeholder.sub("", s)
    s = re.sub(r"^[-*+]\s*(?:\[[ xX]\]\s*)?", "", s).replace("**", "").strip()
    if not s or s.endswith("::") or s.endswith(":"):
        return False
    return re.search(r"\w", s) is not None


def _has_content(text: str) -> bool:
    fence: Optional[str] = None
    for line in text.splitlines():
        before = fence
        fence, _ = fence_state(fence, line)
        if before is None and fence is None and _is_content(line):
            return True
    return False


# --- the same-day note --------------------------------------------------------------------

def _names_other_day(heading: str, day: date) -> bool:
    iso = day.isoformat()
    if any(found != iso for found in ISO_DATE_RE.findall(heading)):
        return True
    without_dates = ISO_DATE_RE.sub("", heading)
    return any(found != str(day.year) for found in YEAR_RE.findall(without_dates))


def _linked_text(text: str, day: date, token: str) -> str:
    """The same-day note without embeds, queries, METADATA callouts, navigation-only lines,
    thematic breaks with their trailing navigation and the sections that name another date or year."""
    _, lines = body(text)
    structure = headings(lines)
    dropped = trailing_navigation(lines, structure, day, token)
    for start, end, _ in ranges(lines, structure, lambda h: _names_other_day(h, day), cut_at_rule=True):
        for i in range(start - 1, end):
            dropped[i] = True
    metadata = metadata_mask(lines)
    kept = [line for i, line in enumerate(lines) if not dropped[i] and not metadata[i]
            and not _EMBED_LINE_RE.match(line) and not is_navigation(line, day, token)]
    return block_text(cleaned(kept))


def _kind(target: str, text: str) -> str:
    haystack = (target + "\n" + body(text)[0]).lower()
    for kind, marks in KIND_MARKS:
        if any(mark in haystack for mark in marks):
            return kind
    return "other"


# --- one daily ------------------------------------------------------------------------------

def _settings(settings: dict) -> Tuple[List[str], List[str], List[str], int, str, set]:
    sections = settings.get("sections", settings.get("daily_sections")) or []
    skip = settings.get("skip_sections") or []
    task_stems = [_target(p) for p in settings.get("task_notes") or []]
    max_chars = settings.get("max_chars_per_day") or DEFAULT_MAX_CHARS
    fmt = settings.get("date_format") or DEFAULT_DATE_FORMAT
    return list(sections), list(skip), task_stems, int(max_chars), fmt, set(settings.get("yesterday_fields") or [])


def _parse_daily(text: str, settings: dict) -> Tuple[Dict[str, str], List[str], List[str]]:
    """``(kept sections {heading: text}, links outside skipped sections, links of the kept text)``;
    the whole body under ``TEXT_SECTION`` when no configured heading is found."""
    sections, skip, _, _, _, _ = _settings(settings)
    _, lines = body(text)
    structure = headings(lines)
    dropped = trailing_navigation(lines, structure)
    for start, end, _ in ranges(lines, structure, lambda h: any(h.startswith(p) for p in skip), cut_at_rule=True):
        for i in range(start - 1, end):
            dropped[i] = True
    kept: Dict[str, str] = {}
    kept_lines: List[str] = []
    for name in sections:
        parts: List[str] = []
        for start, end, _ in ranges(lines, structure, lambda h, n=name: h == n):
            block = [line for i, line in enumerate(lines[start:end], start) if not dropped[i]]
            parts.extend(cleaned(block))
            kept_lines.extend(block)
        if parts:
            kept[name] = block_text(parts)
    if not any(heading in sections for _, _, heading in structure[0]):
        kept_lines = [line for i, line in enumerate(lines) if not dropped[i]]
        if any(line.strip() for line in kept_lines):
            kept[TEXT_SECTION] = block_text(cleaned(kept_lines))
    body_links = _links(line for i, line in enumerate(lines) if not dropped[i])
    return kept, body_links, _links(kept_lines)


def _merge_sections(order: List[str], parts: List[Dict[str, str]]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for name in order:
        texts = [p[name] for p in parts if name in p]
        if texts:
            merged[name] = "\n\n".join(texts)
    return merged


def read_day(day: date, dailies: Dict[str, str], settings: dict, read_note: ReadNote) -> dict:
    """One ``ReadResult.days[]`` entry (plus ``previous_day_fields``) for ``day``."""
    sections, _, task_stems, max_chars, fmt, yesterday = _settings(settings)
    token = render_day(day, fmt)
    own = {_target(path) for path in dailies}
    parsed = [_parse_daily(text, settings) for text in dailies.values()]
    merged = _merge_sections(sections + [TEXT_SECTION], [p[0] for p in parsed])

    targets: List[str] = []
    for _, body_links, _ in parsed:
        for target in body_links:
            if (has_token(target, token) and target not in own and target not in task_stems
                    and target not in targets):
                targets.append(target)
    problems: List[dict] = []
    linked: List[dict] = []
    for target in targets:
        text = read_note(target)
        if text is None:
            problems.append({"kind": LINKED_MISSING, "path": target})
            continue
        linked.append({"path": target, "kind": _kind(target, text), "text": _linked_text(text, day, token)})

    units: List[Tuple[str, str, str]] = [("section", n, t) for n, t in merged.items()]
    units += [("linked", item["path"], item["text"]) for item in linked]
    kept_sections: Dict[str, str] = {}
    kept_linked: List[dict] = []
    total, partly, hard_cut = 0, False, False
    for kind, name, text in units:
        if total + len(text) > max_chars:
            partly = True
            if not kept_sections and not kept_linked and kind == "section":
                kept_sections[name], hard_cut = text[:max_chars].rstrip(), True
            break
        total += len(text)
        if kind == "section":
            kept_sections[name] = text
        else:
            kept_linked.append(next(item for item in linked if item["path"] == name))

    section_lines = [line for text in kept_sections.values() for line in text.splitlines()]
    fields = _fields(section_lines)
    tasks: List[dict] = []
    if hard_cut:
        tasks.extend(_tasks(section_lines, next(iter(dailies))))
    else:
        for path, (own_sections, _, _) in zip(dailies, parsed):
            lines = [line for name in kept_sections for line in own_sections.get(name, "").splitlines()]
            tasks.extend(_tasks(lines, path))
    for item in kept_linked:
        tasks.extend(_tasks(item["text"].splitlines(), item["path"]))
    links = _links(section_lines)
    for target in targets:
        if target not in links:
            links.append(target)
    return {
        "date": day.isoformat(),
        "dailies": list(dailies),
        "sections": kept_sections,
        "fields": {k: v for k, v in fields.items() if k not in yesterday},
        "previous_day_fields": {k: v for k, v in fields.items() if k in yesterday},
        "partly_read": partly,
        "has_content": any(_has_content(t) for t in kept_sections.values()),
        "links": links,
        "problems": problems,
        "tasks": tasks,
        "linked": kept_linked,
    }


def yesterday_fields(text: str, settings: dict) -> Dict[str, str]:
    """Only the ``yesterday_fields`` of one daily text (the daily after the period)."""
    yesterday = _settings(settings)[5]
    kept = _parse_daily(text, settings)[0]
    fields = _fields(line for body_text in kept.values() for line in body_text.splitlines())
    return {k: v for k, v in fields.items() if k in yesterday}


def attribute_yesterday(entries: List[dict], after_period: Optional[Dict[str, str]]) -> List[dict]:
    """Entries sorted by date, every ``previous_day_fields`` moved onto the entry dated D-1."""
    out = sorted((copy.deepcopy(e) for e in entries), key=lambda e: str(e.get("date")))
    last_index: Dict[str, int] = {str(e.get("date")): i for i, e in enumerate(out)}
    for entry in out:
        moved = entry.pop("previous_day_fields", None) or {}
        day = _as_date(entry.get("date"))
        if not moved or day is None:
            continue
        index = last_index.get((day - timedelta(days=1)).isoformat())
        if index is not None:
            out[index].setdefault("fields", {}).update(moved)
    if after_period and out:
        out[-1].setdefault("fields", {}).update(after_period)
    return out


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


# --- the period-level task rules ---------------------------------------------------------

def task_note_tasks(path: str, text: str) -> List[dict]:
    """Every task of a living task note; open ones labelled ``open today``."""
    _, lines = body(text)
    tasks = _tasks(cleaned(lines), path)
    for task in tasks:
        if not task["done"]:
            task["label"] = OPEN_TODAY
    return tasks


def done_in_period(tasks: Iterable[dict], start: date, end: date) -> List[dict]:
    """The tasks whose ✅ date lies in ``start..end`` (inclusive), whichever file holds them."""
    out: List[dict] = []
    for task in tasks:
        done_date = _as_date(task.get("done_date")) if task.get("done") else None
        if done_date is not None and start <= done_date <= end:
            out.append(task)
    return out

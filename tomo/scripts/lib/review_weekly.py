# review_weekly.py — the text side of a period read: daily names, link targets, a weekly note's day blocks.
# version: 0.1.0
"""Daily names, link targets and the split of a weekly note (spec 045, T3.3; PRD F3-AC5).

``daily_name`` / ``daily_date`` render and parse the daily name format
(``YYYY``, ``MM``, ``DD`` and ``[literals]``). ``link_targets`` lists the
wiki-link and embed targets of a text (alias and heading stripped, first
spelling kept); ``link_key`` is their comparison key (stem, ``path_key``).
``weekly_content`` splits one weekly note into day blocks keyed by the daily
their heading links (ending at the next heading of the same or a higher
level, blocks outside the period dropped), week-level text per own section,
and the links of both; sections whose heading starts with a skip prefix are
cut out. No Kado call is made here — ``lib/review_period.py`` reads.

Design notes: docs/tomo/scripts/lib/review_weekly.md
"""
from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional, Sequence, Set, Tuple

from lib.period import Period
from lib.vault_paths import path_key

DEFAULT_DAILY_FORMAT = "YYYY-MM-DD"
DEFAULT_WEEKLY_SKIP = ("Review Check", "Organisation")

_DAILY_TOKENS = {"YYYY": r"(?P<y>\d{4})", "MM": r"(?P<m>\d{2})", "DD": r"(?P<d>\d{2})"}
_LINK_RE = re.compile(r"\[\[([^\]|#]+)")
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


# --- daily names ---------------------------------------------------------------------

def _daily_parts(fmt: str) -> List[Tuple[str, str]]:
    parts: List[Tuple[str, str]] = []
    i = 0
    while i < len(fmt):
        if fmt[i] == "[":
            close = fmt.find("]", i + 1)
            parts.append(("literal", fmt[i + 1:] if close == -1 else fmt[i + 1:close]))
            i = len(fmt) if close == -1 else close + 1
            continue
        for token in _DAILY_TOKENS:
            if fmt.startswith(token, i):
                parts.append(("token", token))
                i += len(token)
                break
        else:
            parts.append(("literal", fmt[i]))
            i += 1
    return parts


def daily_name(day: date, fmt: str) -> str:
    """The daily note's stem for ``day`` under a ``YYYY``/``MM``/``DD`` format with ``[literals]``."""
    values = {"YYYY": f"{day.year:04d}", "MM": f"{day.month:02d}", "DD": f"{day.day:02d}"}
    return "".join(values[text] if kind == "token" else text for kind, text in _daily_parts(fmt))


def daily_date(name: str, fmt: str) -> Optional[date]:
    """The date a stem denotes under ``fmt``, or None when it is not a daily name."""
    pattern = "".join(_DAILY_TOKENS[text] if kind == "token" else re.escape(text)
                      for kind, text in _daily_parts(fmt))
    try:
        match = re.fullmatch(pattern, name)
        if match is None:
            return None
        return date(int(match["y"]), int(match["m"]), int(match["d"]))
    except (re.error, IndexError, ValueError):
        return None


# --- links ---------------------------------------------------------------------------

def clean_target(target: str) -> str:
    """A link target without ``|alias`` and ``#heading``, stripped."""
    return target.split("|", 1)[0].split("#", 1)[0].strip()


def link_key(target: str) -> str:
    stem = clean_target(target).rsplit("/", 1)[-1]
    return path_key(stem[:-3] if stem.lower().endswith(".md") else stem)


def unique_targets(targets: Sequence[str]) -> List[str]:
    """Cleaned targets in order, one per ``link_key``, first spelling kept."""
    seen: Set[str] = set()
    out: List[str] = []
    for raw in targets:
        target = clean_target(raw)
        key = link_key(target)
        if key and key not in seen:
            seen.add(key)
            out.append(target)
    return out


def link_targets(text: str) -> List[str]:
    """Wiki-link and embed targets of ``text``."""
    return unique_targets(_LINK_RE.findall(text))


# --- weekly notes ------------------------------------------------------------------

def _sections(lines: List[str]) -> List[Tuple[int, str, int, int]]:
    """``(level, heading, start, end)`` per heading outside fences; ``end`` is the next
    heading of the same or a higher level (exclusive line index)."""
    heads: List[Tuple[int, str, int]] = []
    fence: Optional[str] = None
    for n, line in enumerate(lines):
        opener = _FENCE_RE.match(line)
        if opener:
            mark = opener.group(1)[0]
            fence = mark if fence is None else (None if mark == fence else fence)
            continue
        if fence is None:
            match = _HEADING_RE.match(line)
            if match:
                heads.append((len(match.group(1)), match.group(2).strip(), n))
    out = []
    for i, (level, text, start) in enumerate(heads):
        end = next((s for lv, _, s in heads[i + 1:] if lv <= level), len(lines))
        out.append((level, text, start, end))
    return out


def heading_date(heading: str, daily_format: str) -> Optional[date]:
    """The date of the first link in ``heading`` whose stem is a daily name."""
    for target in _LINK_RE.findall(heading):
        day = daily_date(clean_target(target).rsplit("/", 1)[-1], daily_format)
        if day is not None:
            return day
    return None


def weekly_content(text: str, period: Period, *, daily_format: str, own_sections: Sequence[str],
                   skip_sections: Sequence[str] = DEFAULT_WEEKLY_SKIP) -> dict:
    """Day blocks of ``period`` keyed by date, week-level text per own section, their links."""
    lines = text.splitlines()
    sections = _sections(lines)
    skipped = [(s, e) for _, head, s, e in sections if any(head.startswith(p) for p in skip_sections)]

    def hidden(n: int) -> bool:
        return any(s <= n < e for s, e in skipped)

    def body(start: int, end: int) -> str:
        return "\n".join(line for n, line in enumerate(lines[start + 1:end], start + 1) if not hidden(n)).strip()

    day_blocks: Dict[str, str] = {}
    week_text: Dict[str, str] = {}
    for _, head, start, end in sections:
        if hidden(start):
            continue
        day = heading_date(head, daily_format)
        if day is not None:
            if period.start <= day <= period.end:
                key = day.isoformat()
                day_blocks[key] = (day_blocks.get(key, "") + "\n" + body(start, end)).strip()
            continue
        if head in own_sections:
            week_text[head] = (week_text.get(head, "") + "\n" + body(start, end)).strip()
    links = link_targets("\n".join(list(day_blocks.values()) + list(week_text.values())))
    return {"day_blocks": day_blocks, "week_text": week_text, "links": links}

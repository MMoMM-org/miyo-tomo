# review_md.py — the markdown structure a /review read works on: body, fences, sections, breaks, navigation.
# version: 0.1.0
"""Markdown structure for ``/review`` reading (spec 045, T3.2; PRD F3-AC1, F3-AC2, F3-AC4).

``body`` splits frontmatter from body lines; ``headings`` finds headings and
thematic breaks outside code fences; ``ranges`` gives a section its
subsections (cut at a break only when asked); ``trailing_navigation`` marks
a break and the navigation block behind it — a METADATA callout, a callout
of links only, navigation-only lines — and nothing else; ``cleaned`` drops
query and embed fences and inline queries, never executing them;
``is_navigation``, ``metadata_mask`` and ``has_token`` are the navigation
and day-name tests. No setting, no Kado, no model, no file I/O:
``review_day`` applies these rules to one daily.

Design notes: docs/tomo/scripts/lib/review_md.md
"""
from __future__ import annotations

import re
from datetime import date
from typing import Callable, Iterable, List, Optional, Tuple

QUERY_FENCES = ("dataview", "dataviewjs")
EMBED_FENCES = ("quoth", "dynbedded")

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
FENCE_RE = re.compile(r"^\s*(?:>\s*)*(`{3,}|~{3,})\s*([\w-]*)")
LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
INLINE_QUERY_RE = re.compile(r"`\$?=[^`]*`")
RULE_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
QUOTE_RE = re.compile(r"^(?:>\s*)+")
METADATA_RE = re.compile(r"^(?:>\s*)+\[!metadata\]", re.IGNORECASE)
_CALLOUT_RE = re.compile(r"^(?:>\s*)+\[![^\]]*\][-+]?[ \t]*(.*)$")
_NAV_SEP_RE = re.compile(r"<==|==>|<=|=>|<-|->|[|·•\-–—=<>*_#\s]")

Heading = Tuple[int, int, str]       # (line index, level, text)
Structure = Tuple[List[Heading], List[int]]   # (headings, thematic-break line indices)


# --- body, fences, headings --------------------------------------------------------------

def body(text: str) -> Tuple[str, List[str]]:
    """``(frontmatter text, body lines)``; the frontmatter is empty when there is none."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[1:i]), lines[i + 1:]
    return "", lines


def fence_state(fence: Optional[str], line: str) -> Tuple[Optional[str], Optional[str]]:
    """``(fence after this line, info string when this line opens one)``."""
    opener = FENCE_RE.match(line)
    if not opener:
        return fence, None
    mark = opener.group(1)[0]
    if fence is None:
        return mark, opener.group(2).lower()
    return (None if mark == fence else fence), None


def headings(lines: List[str]) -> Structure:
    """``(headings, thematic-break line indices)`` outside code fences."""
    found: List[Heading] = []
    rules: List[int] = []
    fence: Optional[str] = None
    for i, line in enumerate(lines):
        before = fence
        fence, _ = fence_state(fence, line)
        if before is not None or fence is not None:
            continue
        match = HEADING_RE.match(line)
        if match:
            found.append((i, len(match.group(1)), match.group(2).strip()))
        elif RULE_RE.match(line.strip()):
            rules.append(i)
    return found, rules


# --- sections ------------------------------------------------------------------------------

def section_end(structure: Structure, index: int, n_lines: int, cut_at_rule: bool = False) -> int:
    """First line after the section of ``headings[index]``: the next heading of its level or
    higher; with ``cut_at_rule`` also the first thematic break inside it."""
    found, rules = structure
    start, level, _ = found[index]
    end = n_lines
    for other, lvl, _ in found[index + 1:]:
        if lvl <= level:
            end = other
            break
    if cut_at_rule:
        end = min([end] + [r for r in rules if start < r < end])
    return end


def ranges(lines: List[str], structure: Structure, match: Callable[[str], bool],
           cut_at_rule: bool = False) -> List[Tuple[int, int, str]]:
    """``(start, end, heading)`` of every section whose heading ``match``es, in document order."""
    return [(start + 1, section_end(structure, i, len(lines), cut_at_rule), text)
            for i, (start, _, text) in enumerate(structure[0]) if match(text)]


# --- thematic breaks and the navigation block behind them ---------------------------------

def _callout_end(lines: List[str], start: int) -> int:
    """First line after the quoted block that starts at ``start``."""
    end = start
    while end < len(lines) and lines[end].lstrip().startswith(">"):
        end += 1
    return end


def _links_only(s: str) -> bool:
    return bool(LINK_RE.search(s)) and not _NAV_SEP_RE.sub("", LINK_RE.sub("", s))


def _is_link_callout(lines: List[str], start: int, end: int) -> bool:
    """A callout whose title has no text and whose body lines hold nothing but links."""
    title = _CALLOUT_RE.match(lines[start].lstrip())
    if not title or (title.group(1).strip() and not _links_only(title.group(1))):
        return False
    rest = [QUOTE_RE.sub("", line.strip()) for line in lines[start + 1:end]]
    rest = [s for s in rest if s]
    return bool(rest) and all(_links_only(s) for s in rest)


def trailing_navigation(lines: List[str], structure: Structure,
                        day: Optional[date] = None, token: Optional[str] = None) -> List[bool]:
    """Per line: a thematic break, or the navigation block that trails one — blank lines
    skipped, a METADATA callout block, a callout of links only, navigation-only lines; the
    first other line ends the block and stays, as does everything after it."""
    out = [False] * len(lines)
    for rule in structure[1]:
        out[rule] = True
        i = rule + 1
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            if _CALLOUT_RE.match(line.lstrip()):
                end = _callout_end(lines, i)
                if not (METADATA_RE.match(line.lstrip()) or _is_link_callout(lines, i, end)):
                    break
                for j in range(i, end):
                    out[j] = True
                i = end
                continue
            if not is_navigation(line, day, token):
                break
            out[i] = True
            i += 1
    return out


# --- cleaning ------------------------------------------------------------------------------

def cleaned(lines: Iterable[str]) -> List[str]:
    """Without query and embed fences and inline queries; other fences stay."""
    out: List[str] = []
    fence: Optional[str] = None
    dropping = False
    for line in lines:
        before = fence
        fence, info = fence_state(fence, line)
        if before is None and fence is not None:
            dropping = info in QUERY_FENCES or info in EMBED_FENCES
            if dropping:
                continue
        elif before is not None and fence is None and dropping:
            dropping = False
            continue
        if dropping:
            continue
        out.append(INLINE_QUERY_RE.sub("", line))
    return out


def block_text(lines: Iterable[str]) -> str:
    return "\n".join(lines).strip("\n")


# --- navigation and the day token ---------------------------------------------------------

def token_pattern(token: str) -> "re.Pattern[str]":
    """``token`` on digit boundaries: no digit directly before or after it."""
    return re.compile(r"(?<!\d)" + re.escape(token) + r"(?!\d)")


def has_token(target: str, token: str) -> bool:
    """Whether a note name carries the day token (``6.3.2026`` is not in ``16.3.2026``)."""
    return token_pattern(token).search(target) is not None


def is_navigation(line: str, day: Optional[date] = None, token: Optional[str] = None) -> bool:
    """Only wiki links to dated notes, arrows, separators and the day's own date on the line."""
    s = QUOTE_RE.sub("", line.strip())
    targets = LINK_RE.findall(s)
    if not targets:
        return False
    rest = LINK_RE.sub("", s)
    if day is not None:
        rest = rest.replace(day.isoformat(), "")
    if token:
        rest = token_pattern(token).sub("", rest)
    if _NAV_SEP_RE.sub("", rest):
        return False
    return all(ISO_DATE_RE.search(t) or YEAR_RE.search(t) or (token and has_token(t, token)) for t in targets)


def metadata_mask(lines: Iterable[str]) -> List[bool]:
    """Per line: inside a ``> [!METADATA]`` callout block (the quoted lines from its title on)."""
    out: List[bool] = []
    inside = False
    for line in lines:
        quoted = line.lstrip().startswith(">")
        inside = quoted and (inside or METADATA_RE.match(line.lstrip()) is not None)
        out.append(inside)
    return out

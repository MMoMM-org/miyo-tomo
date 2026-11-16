# review_hashi_text.py — a note's text as Hashi's parser reads it, and the lines one review item lands as.
# version: 0.1.0
"""The Hashi-parse mirror both /review planners share (spec 045 T4.1; spec 046 T5.2 split).

``review_actions`` (the "Tomo Review" section) and ``review_section_plan`` (the mapped sections)
must agree on where a heading, a fence or a marker is, so both read a note through this module
and nothing else: ``split_lines`` (``content.split("\\n")``), ``fenced_mask`` (every line opening
with ``` or ~~~ toggles a fence, frontmatter included), ``hashi_headings`` (closing hashes kept,
ECMAScript's whitespace set ``JS_WS`` and line terminators — a CRLF line is no heading), ``bare``
(how two headings compare), ``marker_line`` / ``marker_index`` (spec 045's marker at column 0,
trailing whitespace tolerated). ``item_lines`` gives the lines one kept item lands as: ids
stripped, every line through ``review_doc.neutralised``, continuations indented.

No Kado, no clock, no file I/O. Imports only ``review_doc``; never a planner.

Design notes: docs/tomo/scripts/lib/review_hashi_text.md
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from lib import review_doc as rd

_MARKER = "%% tomo-review {period} %%"
_CONTINUATION = "  "
# ECMAScript's `\s` and `String.prototype.trim()` set, as a literal: WhiteSpace (U+0009, U+000B, U+000C,
# U+FEFF, Unicode Zs) + LineTerminator (U+000A, U+000D, U+2028, U+2029). Python's `\s`/`str.strip()`
# differ (U+001C-001F and U+0085 in, U+FEFF out), so the mirror spells the set out.
JS_WS = ("\t\v\f﻿              "
         "  　\n\r  ")
_JS_LINE_TERMINATORS = "\n\r  "                  # what ECMAScript's `.` never matches
_JS_S = f"[{re.escape(JS_WS)}]"
_HASHI_FENCE_RE = re.compile(rf"^{_JS_S}*(?:```|~~~)")  # Hashi markdownStructure.ts CODE_FENCE_RE
_HASHI_HEADING_RE = re.compile(                           # Hashi markdownStructure.ts HEADING_RE: `.` and `$`
    rf"^(#{{1,6}}){_JS_S}+([^{re.escape(_JS_LINE_TERMINATORS)}]*)\Z")   # as ECMAScript reads them
_CLOSING_HASHES_RE = re.compile(r"[ \t]+#+$")

Headings = List[Tuple[int, int, str]]     # (line index, level, text), review_md's shape


def marker_line(period_name: str) -> str:
    """The Obsidian comment that marks Tomo's section of ``period_name`` in the periodic note."""
    return _MARKER.format(period=period_name)


def item_lines(item: dict) -> Tuple[List[str], int]:
    """``(landed lines, escaped count)`` of one kept item: the bullet line, continuation lines indented;
    ids stripped, every line escaped once through ``review_doc.neutralised``; ``[]`` for an empty item."""
    raw = [str(item.get("text") or ""), *(str(ln) for ln in item.get("lines") or [])]
    cleaned = [rd.ID_PATTERN.sub("", ln).strip() for ln in raw]
    while cleaned and not cleaned[0]:
        cleaned.pop(0)
    while cleaned and not cleaned[-1]:
        cleaned.pop()
    out: List[str] = []
    escaped = 0
    for index, line in enumerate(cleaned):
        safe = rd.neutralised(line) if line else line
        escaped += safe != line
        out.append(("- " if index == 0 else _CONTINUATION) + safe if safe else "")
    return out, escaped


def split_lines(text: str) -> Tuple[List[str], bool]:
    """``(lines, trailing newline)``: Hashi's ``content.split("\\n")`` without the element the final newline makes."""
    lines = text.split("\n")
    trailing = text.endswith("\n")
    if trailing:
        lines.pop()
    return lines, trailing


def fenced_mask(lines: Sequence[str]) -> List[bool]:
    """Per line, whether Hashi's ``fencedLineMask`` marks it: every line opening with ``` or ~~~
    toggles the fence and is marked itself."""
    mask: List[bool] = []
    fenced = False
    for line in lines:
        if _HASHI_FENCE_RE.match(line):
            fenced = not fenced
            mask.append(True)
        else:
            mask.append(fenced)
    return mask


def hashi_headings(lines: Sequence[str]) -> Headings:
    """``(line index, level, text)`` of every heading as Hashi's ``parseHeadings`` reads these lines:
    the text after the hashes, trimmed by ECMAScript's set, closing hashes kept; a line holding a
    ``\\r``, U+2028 or U+2029 is no heading; fenced lines skipped."""
    fenced = fenced_mask(lines)
    found: Headings = []
    for index, line in enumerate(lines):
        if fenced[index]:
            continue
        match = _HASHI_HEADING_RE.match(line)
        if match:
            found.append((index, len(match.group(1)), match.group(2).strip(JS_WS)))
    return found


def bare(text: str) -> str:
    """``text`` without closing hashes and trailing whitespace: how two headings are compared."""
    return _CLOSING_HASHES_RE.sub("", text.rstrip())


def marker_index(lines: List[str], marker: str) -> Optional[int]:
    """The first unfenced line that is ``marker`` at column 0, trailing whitespace tolerated; an
    indented copy (an item's continuation line) is not the marker."""
    fenced = fenced_mask(lines)
    return next((i for i, line in enumerate(lines) if not fenced[i] and line.rstrip() == marker), None)

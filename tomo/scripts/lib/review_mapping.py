# review_mapping.py — which template headings /review may offer as sections, and why the others are left out.
# version: 0.1.0
"""Template analysis for ``/review`` sections (spec 046, T1.2; PRD F2-AC3, F2-AC5, F2-AC11).

``analyse_template(text, off_limits)`` returns one ``TemplateHeading`` per heading of level
2..6: its identity ``key`` (text verbatim, level, parent heading, occurrence among identical
(text, level, parent)), the 1-based template ``line``, ``state`` (offered | left-out), the
``reason`` of a left-out (first rule wins, in ``REASONS`` order) and the ``flags`` of an
offered one (mixed, container, under-own). ``heading_tree(text)`` gives the same headings
unclassified, for any note. ``landing_off_limits(heading, off_limits)`` is the one landing
check: the row that covers the heading, or None. ``assign_ids`` gives rows their ``s<n>``
id, ``dropped`` names earlier rows a new template lacks. No setting file, no Kado, no
model, no file I/O.

Design notes: docs/tomo/scripts/lib/review_mapping.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

from lib.review_md import AUTOMATIC_FENCES, EMBED_LINE_RE, FIELD_RE, INLINE_QUERY_RE, fence_state, headings
from lib.template_syntax import TEMPLATER_RE, leading_block, templater_inner_line_indexes, templater_spans

TEMPLATER, LINK, PER_PERIOD, OFF_LIMITS, AUTOMATIC = REASONS = (
    "templater", "link", "per-period-parent", "off-limits", "automatic")
MIXED, CONTAINER, UNDER_OWN = "mixed", "container", "under-own"
REPEAT_PARENTS = 3                    # the same (text, level) under this many parents repeats per period
MAX_ID = 999                          # ids are ^s[0-9]{1,3}$

_CURSOR_RE = re.compile(r"<%[-_]?\s*tp\.file\.cursor\(\s*\d*\s*\)\s*[-_]?%>")
_BRACKET_RE = re.compile(r"""<%[-_]?\s*(["'])\[\1\s*[-_]?%>""")      # <%"["%> renders one '['
_MARKERS_RE = re.compile(r"^\s*(?:>\s*)*(?:(?:[-*+]|\d+[.)])\s+)?(?:\[.\]\s+)?")
_WIKI_RE = re.compile(r"!?\[\[[^\]]*\]\]")
_RESIDUE_RE = re.compile(r"[\s\-–—=<>*_#|·•:;,.!\[\]()\x00]")
_COMMENT_RE = re.compile(r"^\s*%%.*%%\s*$")
_BUTTON_RE = re.compile(r"^`?BUTTON\[")
_CALLOUT_TITLE_RE = re.compile(r"^\s*(?:>\s*)+\[![^\]]*\]")
_ID_RE = re.compile(r"^s([0-9]{1,3})$")


class HeadingKey(NamedTuple):
    heading: str
    level: int
    parent: Optional[str]
    occurrence: int


@dataclass
class TemplateHeading:
    key: HeadingKey
    line: int                                         # 1-based line in the template text
    ancestors: Tuple[HeadingKey, ...] = ()            # outermost first, the parent last
    body_kind: str = "empty"                          # empty | own | mixed | automatic-only
    state: str = "offered"
    reason: Optional[str] = None
    flags: Set[str] = field(default_factory=set)

    @property
    def heading(self) -> str:
        return self.key.heading

    @property
    def level(self) -> int:
        return self.key.level

    @property
    def parent(self) -> Optional[str]:
        return self.key.parent

    def left_out(self, reason: str) -> None:
        self.state, self.reason = "left-out", reason

    def as_dict(self) -> dict:
        return {"heading_key": self.key._asdict(), "line": self.line, "state": self.state,
                "reason": self.reason, "flags": sorted(self.flags)}


# --- lines and the heading tree ------------------------------------------------------------

def _body_lines(text: str) -> Tuple[List[str], int]:
    """Body lines split on ``\\n`` as ``template_syntax`` splits them, and the frontmatter line count."""
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    block = leading_block(text)
    offset = block.end_line if block.status == "ok" else 0
    return lines[offset:], offset


def _spanned_lines(text: str, offset: int) -> Set[int]:
    """Body indexes of every line a multi-line Templater span touches, its opening line included."""
    out: Set[int] = set()
    for span in templater_spans(text):
        extra = span["text"].count("\n")
        if extra:
            out.update(range(span["line"] - 1 - offset, span["line"] + extra - offset))
    return out


def _tree(text: str) -> Tuple[List[TemplateHeading], List[str], Set[int]]:
    lines, offset = _body_lines(text)
    inner = {i - offset for i in templater_inner_line_indexes(text)}
    found = [h for h in headings(lines)[0] if h[0] not in inner]
    spanned = _spanned_lines(text, offset)
    heads: List[TemplateHeading] = []
    stack: List[Tuple[Optional[HeadingKey], int]] = []
    seen: Dict[Tuple[str, int, Optional[str]], int] = {}
    for n, (index, level, text_) in enumerate(found):
        while stack and stack[-1][1] >= level:
            stack.pop()
        parent = stack[-1][0].heading if stack and stack[-1][0] else None
        if level == 1:
            stack.append((None, 1))
            continue
        seen[(text_, level, parent)] = occurrence = seen.get((text_, level, parent), 0) + 1
        key = HeadingKey(text_, level, parent, occurrence)
        end = found[n + 1][0] if n + 1 < len(found) else len(lines)
        heads.append(TemplateHeading(key, index + offset + 1, tuple(k for k, _ in stack if k),
                                     _body_kind(lines, index + 1, end, spanned)))
        stack.append((key, level))
    return heads, lines, spanned


def heading_tree(text: str) -> List[TemplateHeading]:
    """Every heading of level 2..6 with its identity and ancestors, unclassified."""
    return _tree(text)[0]


# --- line classes ----------------------------------------------------------------------------

def _line_class(line: str, in_callout: bool, spanned: bool) -> str:
    """auto | neutral | own for one unfenced body line."""
    if in_callout or not line.strip() or _COMMENT_RE.match(line):
        return "neutral"
    if spanned or FIELD_RE.match(line):
        return "auto"
    s = _MARKERS_RE.sub("", _BRACKET_RE.sub("[", line), count=1)
    if EMBED_LINE_RE.match(s) or _BUTTON_RE.match(s):
        return "auto"
    s = _CURSOR_RE.sub("", s)
    s, spans = TEMPLATER_RE.subn("\x00", s)
    s, queries = INLINE_QUERY_RE.subn("\x00", s)
    if (spans or queries) and not _RESIDUE_RE.sub("", _WIKI_RE.sub("", s)):
        return "auto"
    return "neutral" if not s.strip() else "own"


def _line_classes(lines: Sequence[str], start: int, end: int, spanned: Set[int]) -> Set[str]:
    classes: Set[str] = set()
    fence: Optional[str] = None
    automatic_fence = callout = False
    for i in range(start, end):
        before = fence
        fence, info = fence_state(fence, lines[i])
        if before is None and fence is not None:
            automatic_fence = info in AUTOMATIC_FENCES
        if before is not None or fence is not None:
            classes.add("auto" if automatic_fence else "own")
            continue
        callout = bool(_CALLOUT_TITLE_RE.match(lines[i])) or (callout and lines[i].lstrip().startswith(">"))
        classes.add(_line_class(lines[i], callout, i in spanned))
    return classes


def _body_kind(lines: Sequence[str], start: int, end: int, spanned: Set[int]) -> str:
    classes = _line_classes(lines, start, end, spanned)
    if "own" in classes:
        return "mixed" if "auto" in classes else "own"
    return "automatic-only" if "auto" in classes else "empty"


# --- the rules, first rule wins --------------------------------------------------------------

def _descendants(heads: Sequence[TemplateHeading], head: TemplateHeading) -> List[TemplateHeading]:
    return [d for d in heads if head.key in d.ancestors]


def _only(heads: Sequence[TemplateHeading], head: TemplateHeading, reasons: Tuple[str, ...]) -> bool:
    """The own body is empty and every heading below is left out for one of ``reasons``."""
    below = _descendants(heads, head)
    return head.body_kind == "empty" and bool(below) and all(d.reason in reasons for d in below)


def _repeat_parents(heads: Sequence[TemplateHeading]) -> Dict[Tuple[str, int], int]:
    parents: Dict[Tuple[str, int], Set[Optional[HeadingKey]]] = {}
    for h in heads:
        parents.setdefault((h.heading, h.level), set()).add(h.ancestors[-1] if h.ancestors else None)
    return {k: len(v) for k, v in parents.items()}


def _apply_structural(heads: Sequence[TemplateHeading]) -> None:
    by_key = {h.key: h for h in heads}
    repeats = _repeat_parents(heads)
    for h in heads:
        if "<%" in h.heading:
            h.left_out(TEMPLATER)
        elif "[[" in h.heading:
            h.left_out(LINK)
        elif (any(by_key[a].reason in (TEMPLATER, LINK) for a in h.ancestors)
              or repeats[(h.heading, h.level)] >= REPEAT_PARENTS):
            h.left_out(PER_PERIOD)
    for h in reversed(heads):
        if h.reason is None and _only(heads, h, (TEMPLATER, LINK, PER_PERIOD)):
            h.left_out(PER_PERIOD)


def _apply_off_limits(heads: Sequence[TemplateHeading], off_limits: Sequence[dict]) -> None:
    named = {row_key(r) for r in off_limits}
    for h in heads:
        if h.reason is not None:
            continue
        if landing_off_limits(h, off_limits) is not None:
            h.left_out(OFF_LIMITS)
        elif named.intersection(h.ancestors):
            h.flags.add(UNDER_OWN)


def _apply_automatic(heads: Sequence[TemplateHeading]) -> None:
    for h in reversed(heads):                        # sub-headings first: a container reads their verdicts
        if h.reason is not None:
            continue
        if h.body_kind == "automatic-only" or _only(heads, h, (AUTOMATIC,)):
            h.left_out(AUTOMATIC)
        elif h.body_kind == "mixed":
            h.flags.add(MIXED)
        elif h.body_kind == "empty" and _descendants(heads, h):
            h.flags.add(CONTAINER)


def analyse_template(text: str, off_limits: Sequence[dict]) -> List[TemplateHeading]:
    """Every heading of level 2..6, offered or left out with its reason (ADR-9)."""
    heads = heading_tree(text)
    _apply_structural(heads)
    _apply_off_limits(heads, off_limits)
    _apply_automatic(heads)
    return heads


# --- off-limits landing, row ids, dropped rows -----------------------------------------------

def row_key(row: dict) -> HeadingKey:
    """The heading identity a sections or off_limits row names."""
    return HeadingKey(row.get("heading"), row.get("level"), row.get("parent"), row.get("occurrence", 1))


def landing_off_limits(heading: TemplateHeading, off_limits: Sequence[dict]) -> Optional[dict]:
    """The row that covers ``heading``: one naming it, or a ``with_subsections`` row naming an ancestor."""
    for row in off_limits:
        key = row_key(row)
        if key == heading.key or (row.get("with_subsections") is True and key in heading.ancestors):
            return row
    return None


def _id_number(row: dict) -> Optional[int]:
    match = _ID_RE.match(str(row.get("id", "")))
    return int(match.group(1)) if match else None


def assign_ids(rows: Sequence[dict], previous: Sequence[dict]) -> List[dict]:
    """Copies of ``rows``, each with an id: its own, the previous row's of the same heading key, or the
    next number above every known id — a number is never given twice (ADR-10)."""
    earlier = {row_key(p): p["id"] for p in previous if _id_number(p) is not None}
    top = max((n for n in map(_id_number, [*previous, *rows]) if n is not None), default=0)
    out = []
    for row in rows:
        row = dict(row)
        if "id" not in row:
            if row_key(row) in earlier:
                row["id"] = earlier[row_key(row)]
            else:
                top += 1
                if top > MAX_ID:
                    raise ValueError(f"no section id left: s{MAX_ID} is the last")
                row["id"] = f"s{top}"
        out.append(row)
    return out


def dropped(previous: Sequence[dict], heads: Sequence[TemplateHeading]) -> List[dict]:
    """``{heading, level, parent}`` of every earlier row whose heading the new template lacks."""
    present = {(h.heading, h.level, h.parent) for h in heads}
    out: List[dict] = []
    for row in previous:
        named = {"heading": row.get("heading"), "level": row.get("level"), "parent": row.get("parent")}
        if tuple(named.values()) not in present and named not in out:
            out.append(named)
    return out

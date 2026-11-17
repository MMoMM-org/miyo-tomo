#!/usr/bin/env python3
# version: 0.1.0
"""e2e_046_sections_walk.py — the driver of the mapped /review end-to-end tests (spec 046 T6.2).

Lives in tests/, not tomo/scripts/lib/: never a production code path. Not named `test_*`, so pytest does not
collect it; not named `review_*` either, like the `test_046_*` files it serves (the SDD Directory Map guard globs
`tests/review_*.py`). Used by test_046_t6_2_e2e_sections.py; kept apart from tests/review_e2e_walk.py so that file
stays within the constitution's size guidance.

`SectionWalk` is tests/review_e2e_walk.Walk (the four review scripts in-process, called the way
tomo/dot_claude/skills/periodic-review/SKILL.md calls them, on the recording, guarded fake vault) with one
template, one existing target note and one mapping per kind (`KINDS`: week, month, quarter) and a quarterly
folder added to the vault.

`hashi_apply` is the reference applier: Hashi's documented semantics, written from the sources, applied to the
fake's files. `insert_under_marker` and `replace_section` follow Hashi's insertUnderMarker.ts / replaceSection.ts
with blockInsert.ts and sectionLocator.ts (heading anchors only: `before` at the heading line, `after` right below
it, `inside` above the next heading of the same or a higher level, or at the end; the content split on `\\n` and
spliced verbatim; a byte-identical block already present is `skipped-already`). `replace_between_markers` follows
the contract handoff `_outbox/for-hashi/2026-11-14_tomo-to-hashi_replace-between-markers.md` §2-3 (marker lines
unfenced, at column 0, `rstrip() == marker`; one start over the whole note; the first end after it; scope
range level-aware; only the lines strictly between replaced). Actions run in Hashi's planner order
(`KIND_ORDER`, `replace_between_markers` right after `replace_section`), stable by id within a kind; an applied
or skipped-already action is marked `applied: true` in the set JSON.

`user_text` strips every Tomo block (start marker to end marker) and the "Tomo Review" section from a note, so
a test can compare what is left with the note before Tomo touched it. All text is synthetic.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from review_e2e_walk import INBOX, Walk
from review_privacy_fixture import MONTHLY, WEEKLY

QUARTERLY = "Calendar/304 Quarterly/"
TEMPLATES = "Templates/"
KIND_ORDER = ("move_note", "insert_under_marker", "replace_section", "replace_between_markers")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")            # markdownStructure.ts HEADING_RE
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")                 # markdownStructure.ts CODE_FENCE_RE
_START_RE = re.compile(r"^%% tomo:(s\d+) (\S+) %%$")
REVIEW_HEADING = "Tomo Review"


@dataclass(frozen=True)
class Kind:
    kind: str                     # the review-session --kind
    period: str
    template: str                 # file name under Templates/
    template_text: str
    target: str
    target_text: str              # the user's note before any review
    rows: tuple                   # (heading, placement) per mapped section, in template order
    sources: tuple                # daily stems inside the period, for the proposals
    match_flags: tuple = ()

    @property
    def stem(self) -> str:
        return f"{self.period}_review"

    @property
    def doc(self) -> str:
        return f"{INBOX}{self.period} Review.md"

    @property
    def set_json(self) -> str:
        return f"{INBOX}{self.stem}_instructions.json"


def _template(tag: str, headings: tuple) -> str:
    return f"---\ntags: {tag}\n---\n# <% tp.file.title %>\n\n" + "".join(f"## {h}\n\n" for h in headings)


def _note(title: str, headings: tuple, frontmatter: str = "") -> str:
    body = "".join(f"## {h}\nmy own {h.lower()} text\n\n" for h in headings)
    return f"{frontmatter}# {title}\n\n{body}".rstrip("\n") + "\n"


_WEEK_H = ("Wins", "Lessons", "Notes", "Next", "In my own words")
_MONTH_H = ("Highlights", "Learned", "Notes", "Plans", "Reflections")
_QUARTER_H = ("Highlights", "Learned", "Notes", "Ahead", "Reflections")
KINDS = {
    "week": Kind("week", "2026-W13", "t_week.md", _template("weekly", _WEEK_H), f"{WEEKLY}2026-W13.md",
                 _note("2026-W13", _WEEK_H, "---\njournal-start-date: 2026-03-23\n---\n"),
                 (("Wins", "end"), ("Lessons", "under"), ("Next", "before")),
                 ("2026-03-23", "2026-03-24", "2026-03-26")),
    "month": Kind("month", "2026-03", "t_month.md", _template("monthly", _MONTH_H), f"{MONTHLY}2026-03.md",
                  _note("2026-03", _MONTH_H), (("Highlights", "end"), ("Learned", "under"), ("Plans", "before")),
                  ("2026-03-01", "2026-03-10", "2026-03-24")),
    "quarter": Kind("quarter", "2026-Q1", "t_quarter.md", _template("quarterly", _QUARTER_H),
                    f"{QUARTERLY}2026-Q1.md", _note("2026-Q1", _QUARTER_H),
                    (("Highlights", "end"), ("Learned", "under"), ("Ahead", "before")),
                    ("2026-03-01", "2026-03-10", "2026-03-24"), ("--template", "t_quarter.md")),
}


def section_rows(k: Kind) -> list[dict]:
    """The confirmed table rows of the setup dialogue, in template order (SKILL.md step 2, Confirm)."""
    return [{"heading": h, "level": 2, "parent": None, "occurrence": 1, "description": f"what {h} asks for",
             "placement": placement, "cap": 8} for h, placement in k.rows]


def proposals(k: Kind, version: str) -> dict:
    """The model's proposals: one item per mapped section (s1..s3) and one done item for the Tomo Review."""
    a, b, c = k.sources
    return {"language": "en",
            "groups": {"done": [{"text": f"Group item {version}", "sources": [a]}]},
            "sections": [{"key": f"s{i}", "items": [{"text": f"{h} item {version}", "sources": [src]}]}
                         for i, ((h, _), src) in enumerate(zip(k.rows, (a, b, c)), start=1)]}


class SectionWalk(Walk):
    """A Walk whose vault holds a frontmatter template and an existing target note per kind."""

    def __init__(self, root, monkeypatch, capsys, test_id, **kw):
        super().__init__(root, monkeypatch, capsys, test_id, **kw)
        self.vault.folders.add(QUARTERLY)
        for k in KINDS.values():
            for path, text in ((TEMPLATES + k.template, k.template_text), (k.target, k.target_text)):
                self.vault.files[path] = text
                self.vault.created.setdefault(path, 0)
                self.vault.modified.setdefault(path, 0)

        self.vault._record = self.vault.recorded.append     # per test only: the e2e sweeps own review_e2e_walk.WRITES

    def setup_mapped(self, k: Kind) -> dict:
        """match → the user confirms the table as proposed (rows in template order, none off-limits)."""
        out = self.match(k.kind, *k.match_flags)
        assert out["sections"]["mappable"] is True, out["sections"]
        offered = [c["heading_key"]["heading"] for c in out["sections"]["candidates"] if c["state"] == "offered"]
        assert all(h in offered for h, _ in k.rows), offered
        return self.setup(k.kind, *k.match_flags, sections=section_rows(k), off_limits=[])

    def edit(self, k: Kind, *pairs: tuple[str, str]) -> None:
        """The user edits the document in Obsidian: each (old, new) once, every old text present."""
        text = self.doc(k.doc)
        for old, new in pairs:
            assert old in text, (old, text)
            text = text.replace(old, new, 1)
        self.edit_document(k.doc, text)

    # ── Hashi, the reference applier ──
    def hashi_apply(self, stem: str) -> list[str]:
        path = f"{INBOX}{stem}_instructions.json"
        doc = json.loads(self.vault.text(path))
        order = sorted(doc["actions"], key=lambda a: KIND_ORDER.index(a["action"]))
        outcomes = {}
        for action in order:
            if action.get("applied") is True:
                outcomes[action["id"]] = "skipped-already"
                continue
            target = action["target_path"]
            if target not in self.vault.files:
                outcomes[action["id"]] = "failed"
                continue
            result, text = APPLY[action["action"]](self.vault.text(target), action)
            outcomes[action["id"]] = result
            if result != "failed":
                action["applied"] = True
            if result == "applied":
                self.vault.files[target] = text
                self.vault._bump(target)
        self.vault.files[path] = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
        self.vault._bump(path)
        return [outcomes[a["id"]] for a in doc["actions"]]


# ── Hashi's line primitives (blockInsert.ts, markdownStructure.ts, sectionLocator.ts) ──

def _fenced(lines: list[str]) -> list[bool]:
    mask, inside = [], False
    for line in lines:
        if _FENCE_RE.match(line):
            mask.append(True)
            inside = not inside
            continue
        mask.append(inside)
    return mask


def _headings(lines: list[str]) -> list[tuple[str, int, int]]:
    """(heading, level, line) of every unfenced ATX heading."""
    out = []
    for i, (line, fenced) in enumerate(zip(lines, _fenced(lines))):
        m = None if fenced else _HEADING_RE.match(line)
        if m:
            out.append((m.group(2).strip(), len(m.group(1)), i))
    return out


def _range(lines: list[str], heading: str, level: int | None = None) -> tuple[int, int] | None:
    """(heading line, next same-or-higher heading line or len) of the first match; any level when None."""
    heads = _headings(lines)
    for index, (text, lvl, line) in enumerate(heads):
        if text == heading and (level is None or lvl == level):
            nxt = next((h[2] for h in heads[index + 1:] if h[1] <= lvl), len(lines))
            return line, nxt
    return None


def _body(text: str) -> tuple[list[str], bool]:
    lines = text.split("\n")
    trailing = text.endswith("\n")
    return (lines[:-1] if trailing else lines), trailing


def _join(body: list[str], trailing: bool) -> str:
    return "\n".join(body) + ("\n" if trailing else "")


def _present(lines: list[str], block: list[str]) -> bool:
    return any(lines[i:i + len(block)] == block for i in range(len(lines) - len(block) + 1))


def _insert_under_marker(text: str, action: dict) -> tuple[str, str]:
    assert action["anchor"]["type"] == "heading", action["anchor"]
    lines = text.split("\n")
    found = _range(lines, action["anchor"]["value"])
    if found is None:
        return "failed", text
    at = {"before": found[0], "after": found[0] + 1, "inside": found[1]}[action["placement"]]
    block = action["content"].split("\n")
    if _present(lines, block):
        return "skipped-already", text
    body, trailing = _body(text)
    at = max(0, min(at, len(body)))
    return "applied", _join(body[:at] + block + body[at:], trailing)


def _replace_section(text: str, action: dict) -> tuple[str, str]:
    lines = text.split("\n")
    found = _range(lines, action["anchor"]["value"])
    if found is None:
        return "failed", text
    body, trailing = _body(text)
    start, end = found[0] + 1, min(found[1], len(body))
    new = action["content"].split("\n")
    if body[start:end] == new:
        return "skipped-already", text
    return "applied", _join(body[:start] + new + body[end:], trailing)


def _marker_lines(lines: list[str], marker: str) -> list[int]:
    return [i for i, (line, fenced) in enumerate(zip(lines, _fenced(lines)))
            if not fenced and line.rstrip() == marker and line[:1] not in (" ", "\t")]


def _replace_between_markers(text: str, action: dict) -> tuple[str, str]:
    start_m, end_m = action["start_marker"], action["end_marker"]
    if start_m == end_m:
        return "failed", text
    body, trailing = _body(text)
    starts, ends = _marker_lines(body, start_m), _marker_lines(body, end_m)
    if len(starts) != 1:
        return "failed", text
    start = starts[0]
    after = [e for e in ends if e > start]
    if not after or len(ends) != 1:
        return "failed", text
    end = after[0]
    scope = action.get("scope")
    if scope is not None:
        found = _range(body, scope["heading"], scope["level"])
        if found is None or not (found[0] <= start and end < found[1]):
            return "failed", text
    new = [] if action["content"] == "" else action["content"].split("\n")
    if body[start + 1:end] == new:
        return "skipped-already", text
    return "applied", _join(body[:start + 1] + new + body[end:], trailing)


APPLY = {"insert_under_marker": _insert_under_marker, "replace_section": _replace_section,
         "replace_between_markers": _replace_between_markers}


# ── what the tests compare ──

def blocks(text: str) -> dict[str, list[list[str]]]:
    """Per section id, the line lists between each start marker and its end marker."""
    lines = text.split("\n")
    out: dict[str, list[list[str]]] = {}
    for i, line in enumerate(lines):
        m = _START_RE.match(line)
        if m:
            end = lines.index(f"%% /tomo:{m.group(1)} {m.group(2)} %%", i)
            out.setdefault(m.group(1), []).append(lines[i + 1:end])
    return out


def marker_count(text: str, sid: str, period: str) -> tuple[int, int]:
    lines = text.split("\n")
    return lines.count(f"%% tomo:{sid} {period} %%"), lines.count(f"%% /tomo:{sid} {period} %%")


def user_text(text: str) -> str:
    """The note without the "Tomo Review" section and without Tomo's blocks: start marker to end marker inclusive,
    plus the one empty line after the end marker that a first insert's content carries (it ends with `\\n`)."""
    lines = text.split("\n")
    found = _range(lines, REVIEW_HEADING)
    if found is not None:
        lines = lines[:found[0]] + lines[found[1]:]
    kept, inside, closed = [], None, False
    for line in lines:
        m = _START_RE.match(line)
        if inside is None and m:
            inside = f"%% /tomo:{m.group(1)} {m.group(2)} %%"
            continue
        if inside is not None:
            if line == inside:
                inside, closed = None, True
            continue
        if closed and line == "":
            closed = False
            continue
        closed = False
        kept.append(line)
    assert inside is None, "an end marker is missing"
    return "\n".join(kept)

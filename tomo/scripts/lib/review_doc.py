# review_doc.py — the Pass 1 review document of /review: proposals checked against the period, then rendered.
# version: 0.3.0
"""The review document ``<period> Review.md`` (spec 045, T3.6, PRD F4, ADR-12, ADR-13).

Pure functions between the model's ``proposals.json`` and the document the
script writes: ``load_proposals`` / ``proposal_problems`` validate the file
against ``tomo/schemas/review-proposals.schema.json``; ``period_of`` rebuilds
the ``Period`` from ``read.json`` under the configured week rule;
``check_items`` applies the source rule (every item needs a daily of the
period, a ``weekly_only`` item a weekly note the reader listed, a theme two
distinct days, a text that is not empty; the month-only groups only for a
month with weekly notes) and returns the accepted items per group with their
links and the rejected ones with group, index and reason. A link is the stem
of a note ``read.json`` lists that a source resolved to — a daily of the
period or, for ``weekly_only``, a listed weekly — deduplicated in source
order; a source that resolves to nothing is dropped from the links, and no
model string is ever rendered as a link. ``render_document`` renders the
frontmatter (a schema-valid ``tomo:`` block plus the top-level ``review_*``
keys) and the body: title, info callout, ``- [ ] Approved``, one H2 per group
from the de/en label table (English otherwise), Tomo items as
``- [x] <text> ([[stem]], …) %%t<n>%%`` with the id on the checkbox line and
continuation lines indented by two spaces, a plain ``- …`` bullet for an
empty group. Every item line that starts with a structural marker (heading,
checkbox bullet, quote, fence, thematic break) is escaped with a leading
backslash so the text cannot forge a line Pass 2 would read (``neutralised``
is that predicate, shared with ``review_actions`` for the landing). Habits arrive
rendered from ``review_habits`` and get an id like every Tomo item; no habits
means no habits heading. ``ID_PATTERN`` and ``group_labels`` are the shared
vocabulary of ``review_doc_parse``, which reads the document back.
``mark_delivered`` (T4.2, F5-AC11) is the delivered mark: ``tomo.state``
becomes ``approved`` and the title line gets the language's "delivered"
word; idempotent, a marked text comes back unchanged.

No Kado, no model, no file I/O beyond the schema. Needs jsonschema and PyYAML.

Design notes: docs/tomo/scripts/lib/review_doc.md
"""
from __future__ import annotations

import json
import posixpath
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from lib.doc_frontmatter import build_tomo_block
from lib.period import KINDS, MONTH, Period, WeekRule

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "review-proposals.schema.json"

DOC_TYPE = "review"
DOC_STATE = "pending-approval"
DOC_STATE_DELIVERED = "approved"
DOC_SUFFIX = " Review"
APPROVED_LINE = "- [ ] Approved"
_FENCE = "---"
_DELIVERED_SEP = " — "

DONE, OPEN, THEMES, GROWTH, HABITS, WEEKLY_ONLY, NOT_IN_WEEKLY = (
    "done", "open", "themes", "growth", "habits", "weekly_only", "not_in_weekly")
GROUPS = (DONE, OPEN, THEMES, GROWTH, HABITS, WEEKLY_ONLY, NOT_IN_WEEKLY)
MODEL_GROUPS = tuple(g for g in GROUPS if g != HABITS)
MONTH_GROUPS = (WEEKLY_ONLY, NOT_IN_WEEKLY)
MIN_THEME_DAYS = 2

NO_SOURCE = "no-source-in-period"
THEME_DAYS = "theme-needs-two-days"
MONTH_ONLY = "month-only-group"
NO_WEEKLY = "no-weekly-notes"
EMPTY_TEXT = "empty-text"

ID_MARK = "%%"
ID_PATTERN = re.compile(r"%%(t\d+)%%")
_CONTINUATION = "  "
_ESCAPE = "\\"
# A line that would be structure in the document: heading, checkbox bullet, quote, fence, thematic break.
_STRUCTURAL = re.compile(r"#+(?:\s|$)|>|```|~~~|---|\*\*\*|___|(?:[-*+]|\d+[.)])\s+\[")
_RULE = re.compile(r"([-*_])(?:\s*\1){2,}\s*$")

_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        DONE: "Done", OPEN: "Open", THEMES: "Recurring themes", GROWTH: "Vault growth", HABITS: "Habits",
        WEEKLY_ONLY: "Only in the weekly reviews", NOT_IN_WEEKLY: "Not in the weekly reviews",
        "nothing": "nothing found", "target": "Target", "exists": "exists", "created": "will be created",
        "elsewhere": "found at {path}", "before": "before", "inside": "inside",
        "not_read": "not read", "partly_read": "partly read", "delivered": "delivered",
    },
    "de": {
        DONE: "Erledigt", OPEN: "Offen", THEMES: "Wiederkehrende Themen", GROWTH: "Vault-Wachstum",
        HABITS: "Gewohnheiten", WEEKLY_ONLY: "Nur in den Wochenreviews", NOT_IN_WEEKLY: "Nicht in den Wochenreviews",
        "nothing": "nichts gefunden", "target": "Ziel", "exists": "vorhanden", "created": "wird angelegt",
        "elsewhere": "gefunden unter {path}", "before": "vor", "inside": "in",
        "not_read": "nicht gelesen", "partly_read": "teilweise gelesen", "delivered": "geliefert",
    },
}


class ReadInvalid(ValueError):
    """``read.json`` does not carry a period this module can rebuild."""


def labels(language: str) -> Dict[str, str]:
    return _LABELS.get((language or "").lower(), _LABELS["en"])


def group_labels() -> Dict[str, str]:
    """Every group heading label of every language → its group key."""
    return {table[group]: group for table in _LABELS.values() for group in GROUPS}


def doc_name(period_name: str) -> str:
    return f"{period_name}{DOC_SUFFIX}.md"


# --- the proposals file ----------------------------------------------------------------

def _pointer(parts: Sequence[Any]) -> str:
    return "/" + "/".join(str(p) for p in parts) if parts else "/"


def proposal_problems(data: Any) -> List[str]:
    """Sorted JSON pointers of every schema violation; ``[]`` for a valid file."""
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return sorted({_pointer(err.absolute_path) for err in validator.iter_errors(data)})


def load_proposals(path: Path) -> Tuple[Optional[dict], List[str]]:
    """``(proposals, problems)``: the file as a dict when valid, else None and the pointers."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, ["/"]
    problems = proposal_problems(data)
    return (data, []) if not problems else (None, problems)


# --- the period and its sources --------------------------------------------------------

def period_of(read: dict, rule: WeekRule) -> Period:
    """The ``Period`` of ``read.json`` under ``rule``; ``ReadInvalid`` when the dates do not agree."""
    meta = read.get("period") if isinstance(read, dict) else None
    if not isinstance(meta, dict) or meta.get("kind") not in KINDS:
        raise ReadInvalid("read.json carries no period")
    try:
        start, end = date.fromisoformat(str(meta.get("start"))), date.fromisoformat(str(meta.get("end")))
        period = Period.containing(meta["kind"], start, rule)
    except ValueError as exc:
        raise ReadInvalid("read.json period dates unreadable") from exc
    if period.start != start or period.end != end:
        raise ReadInvalid("read.json period does not match the configured week rule")
    return period


def _stem(path: str) -> str:
    name = posixpath.basename(path.strip().strip("[]"))
    return name[:-3] if name.endswith(".md") else name


@dataclass
class Sources:
    """What a source may resolve to, keyed by the listed path and by its stem: a daily → (day, stem), a weekly → stem."""

    dailies: Dict[str, Tuple[date, str]] = field(default_factory=dict)
    weeklies: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def of(cls, read: dict) -> "Sources":
        sources = cls()
        for entry in read.get("days") or []:
            try:
                day = date.fromisoformat(str(entry.get("date")))
            except ValueError:
                continue
            for path in entry.get("dailies") or []:
                stem = _stem(str(path))
                sources.dailies[str(path)] = (day, stem)
                sources.dailies.setdefault(stem, (day, stem))
        for entry in read.get("weekly") or []:
            path = str(entry.get("path") or "")
            if path:
                sources.weeklies[path] = _stem(path)
                sources.weeklies.setdefault(_stem(path), _stem(path))
        return sources

    def daily_of(self, source: str) -> Optional[Tuple[date, str]]:
        return self.dailies.get(source.strip()) or self.dailies.get(_stem(source))

    def weekly_of(self, source: str) -> Optional[str]:
        return self.weeklies.get(source.strip()) or self.weeklies.get(_stem(source))


def _rejection(group: str, index: int, reason: str) -> dict:
    return {"group": group, "index": index, "reason": reason}


def _group_reason(group: str, kind: str, has_weeklies: bool) -> Optional[str]:
    if group not in MONTH_GROUPS:
        return None
    if kind != MONTH:
        return MONTH_ONLY
    return None if has_weeklies else NO_WEEKLY


def _check_item(group: str, item: dict, sources: Sources) -> Tuple[Optional[str], List[str]]:
    """``(reason, links)``: the rejection reason or None, and the stems of the resolved sources in source order."""
    if _clean(item.get("text")) == [""]:
        return EMPTY_TEXT, []
    days: set = set()
    weeklies = 0
    links: List[str] = []
    for source in (str(s) for s in item.get("sources") or []):
        daily = sources.daily_of(source)
        weekly = sources.weekly_of(source) if group == WEEKLY_ONLY and daily is None else None
        if daily is not None:
            days.add(daily[0])
            link = daily[1]
        elif weekly is not None:
            weeklies += 1
            link = weekly
        else:
            continue
        if link not in links:
            links.append(link)
    if (not weeklies) if group == WEEKLY_ONLY else (not days):
        return NO_SOURCE, links
    if group == THEMES and len(days) < MIN_THEME_DAYS:
        return THEME_DAYS, links
    return None, links


def check_items(proposals: dict, read: dict) -> Tuple[Dict[str, List[dict]], List[dict]]:
    """``(accepted {group: [{text, links}]}, rejected [{group, index, reason}])`` over the model groups.

    The month-only groups appear in ``accepted`` only for a month whose reader
    listed weekly notes; their items are rejected otherwise."""
    kind = str((read.get("period") or {}).get("kind"))
    has_weeklies = bool(read.get("weekly"))
    sources = Sources.of(read)
    accepted: Dict[str, List[dict]] = {}
    rejected: List[dict] = []
    groups = proposals.get("groups") or {}
    for group in MODEL_GROUPS:
        items = groups.get(group) or []
        group_reason = _group_reason(group, kind, has_weeklies)
        if group_reason is not None:
            rejected.extend(_rejection(group, i, group_reason) for i in range(len(items)))
            continue
        accepted[group] = []
        for index, item in enumerate(items):
            reason, links = _check_item(group, item, sources)
            if reason is not None:
                rejected.append(_rejection(group, index, reason))
                continue
            accepted[group].append({"text": str(item["text"]), "links": links})
    return accepted, rejected


# --- rendering ---------------------------------------------------------------------------

@dataclass
class DocInput:
    period_name: str
    kind: str
    language: str
    stem: str
    run_id: str
    target: str
    target_exists: bool
    target_found_elsewhere: Optional[str]
    anchor: str
    placement: str
    not_read: List[str]
    partly_read: List[str]
    month_groups: bool
    groups: Dict[str, List[dict]]        # group -> [{text, links}], habits included


def _clean(text: Any) -> List[str]:
    """The non-empty stripped lines of ``text`` without id marks, on every line separator; ``[""]`` for none."""
    lines = [ln.strip() for ln in str(text).replace(ID_MARK, "").splitlines()]
    return [ln for ln in lines if ln] or [""]


def neutralised(line: str) -> str:
    """``line`` with a leading backslash when it would be a heading, checkbox, quote, fence or thematic break.

    Idempotent: a line that already starts with the backslash matches no marker and is returned unchanged."""
    return _ESCAPE + line if _STRUCTURAL.match(line) or _RULE.match(line) else line


def item_lines(text: str, links: Sequence[str], number: int) -> List[str]:
    """The checkbox line with links and id, then the continuation lines; no line of the text is structure."""
    first, *rest = (neutralised(ln) for ln in _clean(text))
    link_part = f" ({', '.join(f'[[{link}]]' for link in links)})" if links else ""
    return [f"- [x] {first}{link_part} {ID_MARK}t{number}{ID_MARK}", *(_CONTINUATION + ln for ln in rest)]


def _callout(inp: DocInput, words: Dict[str, str]) -> str:
    if inp.target_found_elsewhere:
        state = words["elsewhere"].format(path=inp.target_found_elsewhere)
    else:
        state = words["exists"] if inp.target_exists else words["created"]
    parts = [f"{words['target']}: [[{_stem(inp.target)}]] ({state})",
             f"{words[inp.placement]} \"{inp.anchor}\""]
    if inp.not_read:
        parts.append(f"{words['not_read']}: {', '.join(_stem(p) for p in inp.not_read)}")
    if inp.partly_read:
        parts.append(f"{words['partly_read']}: {', '.join(inp.partly_read)}")
    return "> [!info] " + " · ".join(parts)


def _rendered_groups(inp: DocInput) -> List[str]:
    groups = [g for g in GROUPS if inp.month_groups or g not in MONTH_GROUPS]
    if not inp.groups.get(HABITS):
        groups.remove(HABITS)
    return groups


def render_document(inp: DocInput) -> Tuple[str, Dict[str, int]]:
    """``(document text, counts per rendered group)``."""
    import yaml

    words = labels(inp.language)
    lines = [f"# {inp.period_name}{DOC_SUFFIX}", _callout(inp, words), APPROVED_LINE]
    counts: Dict[str, int] = {}
    number = 0
    for group in _rendered_groups(inp):
        items = inp.groups.get(group) or []
        counts[group] = len(items)
        lines += ["", f"## {words[group]}"]
        if not items:
            lines.append(f"- {words['nothing']}")
        for entry in items:
            number += 1
            lines += item_lines(entry["text"], entry.get("links") or [], number)
    front = {
        "tomo": build_tomo_block(DOC_TYPE, DOC_STATE, inp.run_id),
        "review_period": inp.period_name, "review_kind": inp.kind, "review_target": inp.target,
        "review_target_exists": bool(inp.target_exists), "review_language": inp.language, "review_stem": inp.stem,
    }
    front_yaml = yaml.safe_dump(front, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{front_yaml}---\n" + "\n".join(lines) + "\n", counts


# --- the delivered mark ------------------------------------------------------------------

def _split(text: str) -> Tuple[Optional[dict], List[str], List[str]]:
    """``(frontmatter, its raw lines, body lines)``; frontmatter None when the block is missing or broken."""
    import yaml

    lines = text.split("\n")
    if not lines or lines[0].strip() != _FENCE:
        return None, [], lines
    for index in range(1, len(lines)):
        if lines[index].strip() == _FENCE:
            try:
                front = yaml.safe_load("\n".join(lines[1:index]))
            except yaml.YAMLError:
                return None, [], lines
            return (front if isinstance(front, dict) else None), lines[1:index], lines[index + 1:]
    return None, [], lines


def is_delivered(text: str, language: str) -> bool:
    """Whether ``text`` already carries the delivered mark: state approved and the word on the title line."""
    front, _, body = _split(text)
    tomo = front.get("tomo") if isinstance(front, dict) else None
    approved = isinstance(tomo, dict) and tomo.get("state") == DOC_STATE_DELIVERED
    title = next((ln for ln in body if ln.strip()), "")
    return approved and title.endswith(_DELIVERED_SEP + labels(language)["delivered"])


def mark_delivered(text: str, language: str, updated_at: str) -> str:
    """``text`` with ``tomo.state`` approved (``updated_at`` set) and the title line marked delivered.

    Idempotent: a marked text comes back unchanged; a text without a usable
    frontmatter or a ``tomo`` block is returned unchanged too (nothing to mark)."""
    import yaml

    front, _, body = _split(text)
    tomo = front.get("tomo") if isinstance(front, dict) else None
    if not isinstance(tomo, dict):
        return text
    word = _DELIVERED_SEP + labels(language)["delivered"]
    index = next((i for i, ln in enumerate(body) if ln.strip()), None)
    if index is not None and body[index].startswith("# ") and not body[index].endswith(word):
        body[index] = body[index].rstrip() + word
    if tomo.get("state") != DOC_STATE_DELIVERED:
        tomo["state"] = DOC_STATE_DELIVERED
        tomo["updated_at"] = updated_at
    front_yaml = yaml.safe_dump(front, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"{_FENCE}\n{front_yaml}{_FENCE}\n" + "\n".join(body)

# review_doc.py — the Pass 1 review document of /review: proposals checked against the period, then rendered.
# version: 0.5.2
"""The review document ``<period> Review.md`` (spec 045, PRD F4, ADR-12, ADR-13).

Pure functions between the model's ``proposals.json`` and the document the
script writes: ``load_proposals`` / ``proposal_problems`` validate the file
against ``tomo/schemas/review-proposals.schema.json``; ``period_of`` rebuilds
the ``Period`` from ``read.json`` under the configured week rule;
``check_items`` applies the source rule (every item needs a daily of the
period, a ``weekly_only`` item a weekly note the reader listed, a theme two
distinct days, a text that is not empty; the month-only groups only for a
month with weekly notes) and returns the accepted items per group with their
links and the rejected ones with group, index and reason. The groups come
from ``KIND_GROUPS`` per kind (the quarter's ``monthly_only`` needs a listed
monthly note, its pair only a quarter with monthly notes; ``group_reason``);
``check_item`` and ``group_reason`` also serve ``review_sections`` for the
section items. A link is the stem
of a note ``read.json`` lists that a source resolved to — a daily of the
period or, for ``weekly_only`` / ``monthly_only``, a listed weekly / monthly — deduplicated in source
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
means no habits heading. With a mapping (``DocInput.sections``) the body is
``review_sections.render_parts``; without one it is spec 045's byte for byte
(``review_sections.group_parts``, every group).
``ID_PATTERN`` and ``group_labels`` are the shared
vocabulary of ``review_doc_parse``, which reads the document back.
``mark_delivered`` (F5-AC11) is the delivered mark: ``tomo.state``
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
from lib.period import KINDS, MONTH, QUARTER, WEEK, Period, WeekRule

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
MONTHLY_ONLY, NOT_IN_MONTHLY = "monthly_only", "not_in_monthly"
MONTH_GROUPS = (WEEKLY_ONLY, NOT_IN_WEEKLY)
QUARTER_GROUPS = (MONTHLY_ONLY, NOT_IN_MONTHLY)
_BASE_GROUPS = (DONE, OPEN, THEMES, GROWTH, HABITS)
KIND_GROUPS = {WEEK: _BASE_GROUPS, MONTH: _BASE_GROUPS + MONTH_GROUPS, QUARTER: _BASE_GROUPS + QUARTER_GROUPS}
GROUPS = _BASE_GROUPS + MONTH_GROUPS + QUARTER_GROUPS
MODEL_GROUPS = tuple(g for g in GROUPS if g != HABITS)
CHILD_GROUPS = {MONTH: MONTH_GROUPS, QUARTER: QUARTER_GROUPS}       # the marks of a kind, against its child notes
_CHILD_NOTES = {MONTH: "weekly", QUARTER: "monthly"}                # the read.json key of those child notes
_ONLY_IN_CHILD = (WEEKLY_ONLY, MONTHLY_ONLY)                         # rests on a child note, not on a daily
MIN_THEME_DAYS = 2

NO_SOURCE = "no-source-in-period"
THEME_DAYS = "theme-needs-two-days"
MONTH_ONLY = "month-only-group"
QUARTER_ONLY = "quarter-only-group"
NO_WEEKLY = "no-weekly-notes"
NO_MONTHLY = "no-monthly-notes"
EMPTY_TEXT = "empty-text"
_OTHER_KIND = {MONTH: MONTH_ONLY, QUARTER: QUARTER_ONLY}
_NO_CHILD_NOTES = {MONTH: NO_WEEKLY, QUARTER: NO_MONTHLY}

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
        MONTHLY_ONLY: "Only in the monthly reviews", NOT_IN_MONTHLY: "Not in the monthly reviews",
        "nothing": "nothing found", "target": "Target", "exists": "exists", "created": "will be created",
        "elsewhere": "found at {path}", "before": "before", "inside": "inside",
        "not_read": "not read", "partly_read": "partly read", "delivered": "delivered",
        "take": "Use this section", "lands": "Lands", "level": "level {level}", "parent": 'under "{h}"',
        "before_h": 'before "{h}"', "under_h": 'right under "{h}"', "end_h": 'at the end of the text under "{h}"',
        "review_h": 'in the section "{r}" under "{h}"', "place_h": 'as the section "{r}" {where} "{h}"',
        "mark_weekly_only": "only in the weekly review", "mark_not_in_weekly": "in no weekly review",
        "mark_monthly_only": "only in the monthly review", "mark_not_in_monthly": "in no monthly review",
    },
    "de": {
        DONE: "Erledigt", OPEN: "Offen", THEMES: "Wiederkehrende Themen", GROWTH: "Vault-Wachstum",
        HABITS: "Gewohnheiten", WEEKLY_ONLY: "Nur in den Wochenreviews", NOT_IN_WEEKLY: "Nicht in den Wochenreviews",
        MONTHLY_ONLY: "Nur in den Monatsreviews", NOT_IN_MONTHLY: "Nicht in den Monatsreviews",
        "nothing": "nichts gefunden", "target": "Ziel", "exists": "vorhanden", "created": "wird angelegt",
        "elsewhere": "gefunden unter {path}", "before": "vor", "inside": "in",
        "not_read": "nicht gelesen", "partly_read": "teilweise gelesen", "delivered": "geliefert",
        "take": "Abschnitt übernehmen", "lands": "Landet", "level": "Ebene {level}", "parent": "unter „{h}“",
        "before_h": "vor „{h}“", "under_h": "direkt unter „{h}“", "end_h": "am Ende des Texts unter „{h}“",
        "review_h": "im Abschnitt „{r}“ unter „{h}“", "place_h": "als Abschnitt „{r}“ {where} „{h}“",
        "mark_weekly_only": "nur im Wochenrückblick", "mark_not_in_weekly": "in keinem Wochenrückblick",
        "mark_monthly_only": "nur im Monatsrückblick", "mark_not_in_monthly": "in keinem Monatsrückblick",
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


def note_stem(path: str) -> str:
    name = posixpath.basename(path.strip().strip("[]"))
    return name[:-3] if name.endswith(".md") else name


@dataclass
class Sources:
    """What a source may resolve to, keyed by the listed path and by its stem: a daily → (day, stem),
    a weekly or monthly note → stem."""

    dailies: Dict[str, Tuple[date, str]] = field(default_factory=dict)
    weeklies: Dict[str, str] = field(default_factory=dict)
    monthlies: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def of(cls, read: dict) -> "Sources":
        sources = cls()
        for entry in read.get("days") or []:
            try:
                day = date.fromisoformat(str(entry.get("date")))
            except ValueError:
                continue
            for path in entry.get("dailies") or []:
                stem = note_stem(str(path))
                sources.dailies[str(path)] = (day, stem)
                sources.dailies.setdefault(stem, (day, stem))
        for key, notes in (("weekly", sources.weeklies), ("monthly", sources.monthlies)):
            for entry in read.get(key) or []:
                path = str(entry.get("path") or "")
                if path:
                    notes[path] = note_stem(path)
                    notes.setdefault(note_stem(path), note_stem(path))
        return sources

    def daily_of(self, source: str) -> Optional[Tuple[date, str]]:
        return self.dailies.get(source.strip()) or self.dailies.get(note_stem(source))

    def child_of(self, group: str, source: str) -> Optional[str]:
        """The weekly note of a ``weekly_only`` source, the monthly note of a ``monthly_only`` one."""
        notes = self.weeklies if group == WEEKLY_ONLY else self.monthlies
        return notes.get(source.strip()) or notes.get(note_stem(source))


def _rejection(group: str, index: int, reason: str) -> dict:
    return {"group": group, "index": index, "reason": reason}


def has_child_notes(read: dict) -> bool:
    """Whether the reader listed the child notes a month (weekly) or a quarter (monthly) marks against."""
    key = _CHILD_NOTES.get(str((read.get("period") or {}).get("kind")))
    return bool(key and read.get(key))


def group_reason(group: str, kind: str, has_children: bool) -> Optional[str]:
    """Why a child group (or a section item's mark) is not allowed in ``kind``; None when it is."""
    for owner, groups in CHILD_GROUPS.items():
        if group in groups:
            if kind != owner:
                return _OTHER_KIND[owner]
            return None if has_children else _NO_CHILD_NOTES[owner]
    return None


def check_item(group: str, item: dict, sources: Sources) -> Tuple[Optional[str], List[str]]:
    """``(reason, links)``: the rejection reason or None, and the stems of the resolved sources in source order.

    ``group`` is the item's group, or a section item's mark ("" without one)."""
    if _clean(item.get("text")) == [""]:
        return EMPTY_TEXT, []
    days: set = set()
    weeklies = 0
    links: List[str] = []
    for source in (str(s) for s in item.get("sources") or []):
        daily = sources.daily_of(source)
        weekly = sources.child_of(group, source) if group in _ONLY_IN_CHILD and daily is None else None
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
    if (not weeklies) if group in _ONLY_IN_CHILD else (not days):
        return NO_SOURCE, links
    if group == THEMES and len(days) < MIN_THEME_DAYS:
        return THEME_DAYS, links
    return None, links


def check_items(proposals: dict, read: dict) -> Tuple[Dict[str, List[dict]], List[dict]]:
    """``(accepted {group: [{text, links}]}, rejected [{group, index, reason}])`` over the model groups.

    A child group appears in ``accepted`` only for its kind (month, quarter) when
    the reader listed that kind's child notes; its items are rejected otherwise."""
    kind = str((read.get("period") or {}).get("kind"))
    has_children = has_child_notes(read)
    sources = Sources.of(read)
    accepted: Dict[str, List[dict]] = {}
    rejected: List[dict] = []
    groups = proposals.get("groups") or {}
    for group in MODEL_GROUPS:
        items = groups.get(group) or []
        reason = group_reason(group, kind, has_children)
        if reason is not None:
            rejected.extend(_rejection(group, i, reason) for i in range(len(items)))
            continue
        accepted[group] = []
        for index, item in enumerate(items):
            reason, links = check_item(group, item, sources)
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
    month_groups: bool                   # a child group of the kind was accepted (month or quarter pair)
    groups: Dict[str, List[dict]]        # group -> [{text, links}], habits included
    sections: Optional[list] = None      # review_sections.SectionPart per mapped section; None = no mapping
    review_heading: str = "Tomo Review"


def _clean(text: Any) -> List[str]:
    """The non-empty stripped lines of ``text`` without id marks, on every line separator; ``[""]`` for none."""
    lines = [ln.strip() for ln in str(text).replace(ID_MARK, "").splitlines()]
    return [ln for ln in lines if ln] or [""]


def neutralised(line: str) -> str:
    """``line`` with a leading backslash when it would be a heading, checkbox, quote, fence or thematic break.

    Idempotent: a line that already starts with the backslash matches no marker and is returned unchanged."""
    return _ESCAPE + line if _STRUCTURAL.match(line) or _RULE.match(line) else line


def item_lines(text: str, links: Sequence[str], number: int, suffix: str = "") -> List[str]:
    """The checkbox line with links, ``suffix`` (a mark) and id, then the continuation lines; no line is structure."""
    first, *rest = (neutralised(ln) for ln in _clean(text))
    link_part = f" ({', '.join(f'[[{link}]]' for link in links)})" if links else ""
    return [f"- [x] {first}{link_part}{suffix} {ID_MARK}t{number}{ID_MARK}", *(_CONTINUATION + ln for ln in rest)]


def _callout(inp: DocInput, words: Dict[str, str], anchor: str) -> str:
    if inp.target_found_elsewhere:
        state = words["elsewhere"].format(path=inp.target_found_elsewhere)
    else:
        state = words["exists"] if inp.target_exists else words["created"]
    parts = [f"{words['target']}: [[{note_stem(inp.target)}]] ({state})",
             f"{words[inp.placement]} \"{anchor}\""]
    if inp.not_read:
        parts.append(f"{words['not_read']}: {', '.join(note_stem(p) for p in inp.not_read)}")
    if inp.partly_read:
        parts.append(f"{words['partly_read']}: {', '.join(inp.partly_read)}")
    return "> [!info] " + " · ".join(parts)


def rendered_groups(inp: DocInput) -> List[str]:
    groups = [g for g in KIND_GROUPS.get(inp.kind, KIND_GROUPS[WEEK])
              if inp.month_groups or g not in MONTH_GROUPS + QUARTER_GROUPS]
    if not inp.groups.get(HABITS):
        groups.remove(HABITS)
    return groups


def render_document(inp: DocInput) -> Tuple[str, Dict[str, int]]:
    """``(document text, counts per rendered group)``."""
    import yaml

    words = labels(inp.language)
    from lib import review_sections          # imports this module: the parts are rendered there

    anchor = inp.anchor if inp.sections is None else review_sections.display_heading(inp.anchor)
    lines = [f"# {inp.period_name}{DOC_SUFFIX}", _callout(inp, words, anchor), APPROVED_LINE]
    if inp.sections is None:
        body, counts, _ = review_sections.group_parts(inp, words, 0, keep_empty=True)
    else:
        body, counts = review_sections.render_parts(inp, words)
    lines += body
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

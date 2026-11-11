# review_doc.py — the Pass 1 review document of /review: proposals checked against the period, then rendered.
# version: 0.1.0
"""The review document ``<period> Review.md`` (spec 045, T3.6, PRD F4, ADR-12, ADR-13).

Pure functions between the model's ``proposals.json`` and the document the
script writes: ``load_proposals`` / ``proposal_problems`` validate the file
against ``tomo/schemas/review-proposals.schema.json``; ``period_of`` rebuilds
the ``Period`` from ``read.json`` under the configured week rule;
``check_items`` applies the source rule (every item needs a daily of the
period, a ``weekly_only`` item a weekly note the reader listed, a theme two
distinct days; the month-only groups only for a month with weekly notes) and
returns the accepted items per group with their link stems and the rejected
ones with group, index and reason; ``render_document`` renders the
frontmatter (a schema-valid ``tomo:`` block plus the top-level ``review_*``
keys) and the body: title, info callout, ``- [ ] Approved``, one H2 per group
from the de/en label table (English otherwise), Tomo items as
``- [x] <text> ([[stem]], …) %%t<n>%%`` with the id on the checkbox line and
continuation lines indented by two spaces, a plain ``- …`` bullet for an
empty group. Habits arrive rendered from ``review_habits`` and get an id like
every Tomo item; no habits means no habits heading.

No Kado, no model, no file I/O beyond the schema. Needs jsonschema and PyYAML.

Design notes: docs/tomo/scripts/lib/review_doc.md
"""
from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from lib.doc_frontmatter import build_tomo_block
from lib.period import KINDS, MONTH, Period, WeekRule

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "review-proposals.schema.json"

DOC_TYPE = "review"
DOC_STATE = "pending-approval"
DOC_SUFFIX = " Review"
APPROVED_LINE = "- [ ] Approved"

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

ID_MARK = "%%"
_CONTINUATION = "  "

_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        DONE: "Done", OPEN: "Open", THEMES: "Recurring themes", GROWTH: "Vault growth", HABITS: "Habits",
        WEEKLY_ONLY: "Only in the weekly reviews", NOT_IN_WEEKLY: "Not in the weekly reviews",
        "nothing": "nothing found", "target": "Target", "exists": "exists", "created": "will be created",
        "elsewhere": "found at {path}", "before": "before", "inside": "inside",
        "not_read": "not read", "partly_read": "partly read",
    },
    "de": {
        DONE: "Erledigt", OPEN: "Offen", THEMES: "Wiederkehrende Themen", GROWTH: "Vault-Wachstum",
        HABITS: "Gewohnheiten", WEEKLY_ONLY: "Nur in den Wochenreviews", NOT_IN_WEEKLY: "Nicht in den Wochenreviews",
        "nothing": "nichts gefunden", "target": "Ziel", "exists": "vorhanden", "created": "wird angelegt",
        "elsewhere": "gefunden unter {path}", "before": "vor", "inside": "in",
        "not_read": "nicht gelesen", "partly_read": "teilweise gelesen",
    },
}


class ReadInvalid(ValueError):
    """``read.json`` does not carry a period this module can rebuild."""


def labels(language: str) -> Dict[str, str]:
    return _LABELS.get((language or "").lower(), _LABELS["en"])


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
    """What a source may point at: dailies by path and by stem (→ date), weekly notes by path and stem."""

    dailies: Dict[str, date] = field(default_factory=dict)
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
                sources.dailies[str(path)] = day
                sources.dailies.setdefault(_stem(str(path)), day)
        for entry in read.get("weekly") or []:
            path = str(entry.get("path") or "")
            if path:
                sources.weeklies[path] = _stem(path)
                sources.weeklies.setdefault(_stem(path), _stem(path))
        return sources

    def day_of(self, source: str) -> Optional[date]:
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


def _item_reason(group: str, item: dict, sources: Sources) -> Optional[str]:
    raw = [str(s) for s in item.get("sources") or []]
    if group == WEEKLY_ONLY:
        return None if any(sources.weekly_of(s) for s in raw) else NO_SOURCE
    days = {d for d in (sources.day_of(s) for s in raw) if d is not None}
    if not days:
        return NO_SOURCE
    if group == THEMES and len(days) < MIN_THEME_DAYS:
        return THEME_DAYS
    return None


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
            reason = _item_reason(group, item, sources)
            if reason is not None:
                rejected.append(_rejection(group, index, reason))
                continue
            accepted[group].append({"text": str(item["text"]), "links": [_stem(str(s)) for s in item["sources"]]})
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


def _clean(text: str) -> List[str]:
    lines = [ln.strip() for ln in str(text).replace(ID_MARK, "").replace("\r", "").split("\n")]
    return [ln for ln in lines if ln] or [""]


def item_lines(text: str, links: Sequence[str], number: int) -> List[str]:
    """The checkbox line with links and id, then the continuation lines."""
    first, *rest = _clean(text)
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

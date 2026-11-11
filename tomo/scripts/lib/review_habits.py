# review_habits.py — the habits group of a review: tracker values of a period as counts and averages.
# version: 0.1.0
"""Habits as numbers for ``/review`` (spec 045, T3.5, PRD F8).

One pure function, ``habits(trackers, days, period_days, language)``: the
tracker definitions (``tracker_defs(config)`` reads them from the existing
``trackers.daily_note_trackers`` and ``end_of_day_fields`` lists), the raw
per-day field values the period reader produced (``ReadResult.days[]``:
``{date, fields: {name: raw}}``) and the review language give one item per
tracker that has a value on at least one day of the period: a count of days
true for a boolean tracker, an average over the days with a value for an
integer, duration (minutes) or time (minutes since midnight) tracker. Text
trackers are skipped. A day without the field or with an empty value is
*missing*, a value the type rule cannot read ("ja" for a number, "7" for a
yes/no field, an unrun Templater ``<% … %>``) is *unreadable*; both are
named by date and never counted as zero. ``yesterday_fields`` values are
attributed to the previous day (``shift_yesterday=False`` for a caller that
already did). Each item carries its structured numbers and the rendered
line from the de/en label table (English for any other language). No Kado,
no model, no I/O; the values stay in the result, never on stdout or stderr.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

from lib.review_config import tracker_types
from lib.vault_config_edit import get_path

NUMERIC_TYPES = ("integer", "duration", "time")
COUNT_TYPES = ("boolean",)

_YESTERDAY_LIST = ("trackers", "daily_note_trackers", "yesterday_fields")

_TRUE = {"true", "yes", "ja", "x", "1", "✅", "[x]", "done", "y", "j"}
_FALSE = {"false", "no", "nein", "0", "❌", "[ ]", "[]", "n", "-"}

_NUMBER = r"\d+(?:[.,]\d+)?"
_RE_NUMBER = re.compile(rf"^[+-]?{_NUMBER}$")
_RE_H_M = re.compile(rf"^({_NUMBER})\s*h(?:ours?|rs?)?\s*(?:(\d+)\s*(?:m(?:in(?:utes?)?)?)?)?$", re.IGNORECASE)
_RE_MINUTES = re.compile(r"^(\d+)\s*(?:m|min|mins|minutes?)$", re.IGNORECASE)
_RE_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
_RE_TEMPLATER = re.compile(r"<%.*%>", re.DOTALL)

_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "count": "{tracker}: {value} of {days} days",
        "average": "{tracker}: average {value} over {days} days",
        "period": "{days} days in the period",
        "missing": "missing: {dates}",
        "unreadable": "unreadable: {dates}",
        "decimal": ".",
    },
    "de": {
        "count": "{tracker}: {value} von {days} Tagen",
        "average": "{tracker}: Durchschnitt {value} über {days} Tage",
        "period": "{days} Tage im Zeitraum",
        "missing": "fehlt: {dates}",
        "unreadable": "unlesbar: {dates}",
        "decimal": ",",
    },
}


@dataclass(frozen=True)
class TrackerDef:
    name: str
    type: str
    yesterday: bool = False


def tracker_defs(config: dict) -> List[TrackerDef]:
    """The configured trackers in config order; ``yesterday`` marks the ``yesterday_fields`` list."""
    types = tracker_types(config)
    found, yesterday_fields = get_path(config, _YESTERDAY_LIST)
    yesterday = set()
    if found and isinstance(yesterday_fields, list):
        yesterday = {f.get("name") for f in yesterday_fields if isinstance(f, dict)}
    return [TrackerDef(name=name, type=type_, yesterday=name in yesterday) for name, type_ in types.items()]


# --- value rules -----------------------------------------------------------------------

class Unreadable(ValueError):
    """The raw value does not fit the tracker's type."""


def _text(raw: Any) -> Optional[str]:
    """The raw value as stripped text; None when there is no value."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return "true" if raw else "false"
    text = str(raw).strip()
    return text or None


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def parse_boolean(text: str) -> bool:
    key = text.lower()
    if key in _TRUE:
        return True
    if key in _FALSE:
        return False
    raise Unreadable(text)


def parse_integer(text: str) -> float:
    if _RE_NUMBER.match(text):
        return _number(text)
    raise Unreadable(text)


def parse_duration(text: str) -> float:
    """Minutes. ``7h30``, ``7h 30m``, ``7:30``, ``450m``, ``90 min``, ``1.5h``; a plain number is hours."""
    clock = _RE_CLOCK.match(text)
    if clock:
        return int(clock.group(1)) * 60 + int(clock.group(2))
    minutes = _RE_MINUTES.match(text)
    if minutes:
        return float(minutes.group(1))
    h_m = _RE_H_M.match(text)
    if h_m:
        return _number(h_m.group(1)) * 60 + (int(h_m.group(2)) if h_m.group(2) else 0)
    if _RE_NUMBER.match(text):
        return _number(text) * 60
    raise Unreadable(text)


def parse_time(text: str) -> float:
    """Minutes since midnight from ``HH:mm`` (``H:mm``, optional seconds)."""
    clock = _RE_CLOCK.match(text)
    if not clock:
        raise Unreadable(text)
    hours, minutes = int(clock.group(1)), int(clock.group(2))
    if hours > 23 or minutes > 59:
        raise Unreadable(text)
    return hours * 60 + minutes


_PARSERS = {
    "boolean": parse_boolean,
    "integer": parse_integer,
    "duration": parse_duration,
    "time": parse_time,
}


def parse_value(type_: str, raw: Any):
    """The typed value, None for no value; raises ``Unreadable`` for a value the type cannot read."""
    text = _text(raw)
    if text is None:
        return None
    if _RE_TEMPLATER.search(text):
        raise Unreadable(text)
    return _PARSERS[type_](text)


# --- rendering -------------------------------------------------------------------------

def render_value(type_: str, value: float, language: str) -> str:
    labels = _labels(language)
    if type_ == "boolean":
        return str(int(value))
    if type_ == "duration":
        total = int(round(value))
        return f"{total // 60}h {total % 60:02d}m"
    if type_ == "time":
        total = int(round(value)) % (24 * 60)
        return f"{total // 60:02d}:{total % 60:02d}"
    return f"{value:.1f}".replace(".", labels["decimal"])


def _labels(language: str) -> Dict[str, str]:
    return _LABELS.get((language or "").lower(), _LABELS["en"])


def render_line(item: dict, language: str) -> str:
    labels = _labels(language)
    main = labels[item["kind"]].format(
        tracker=item["tracker"], value=item["rendered"], days=item["days_with_value"],
    )
    parts = [labels["period"].format(days=item["days_in_period"])]
    for key in ("missing", "unreadable"):
        if item[key]:
            parts.append(labels[key].format(dates=", ".join(item[key])))
    return f"{main} ({'; '.join(parts)})"


# --- the habits group --------------------------------------------------------------------

def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _values_by_day(tracker: TrackerDef, days: Iterable[dict], shift: bool) -> Dict[date, Any]:
    """Raw values keyed by the day they describe; a later daily for the same day wins."""
    out: Dict[date, Any] = {}
    for entry in days:
        fields = entry.get("fields") or {}
        if tracker.name not in fields:
            continue
        day = _as_date(entry.get("date"))
        if day is None:
            continue
        if shift and tracker.yesterday:
            day = day - timedelta(days=1)
        out[day] = fields[tracker.name]
    return out


def _item(tracker: TrackerDef, values: Dict[date, Any], period: Sequence[date], language: str) -> Optional[dict]:
    readable: List[float] = []
    missing: List[str] = []
    unreadable: List[str] = []
    for day in sorted(period):
        if day not in values:
            missing.append(day.isoformat())
            continue
        try:
            value = parse_value(tracker.type, values[day])
        except Unreadable:
            unreadable.append(day.isoformat())
            continue
        if value is None:
            missing.append(day.isoformat())
            continue
        readable.append(float(value))
    if not readable:
        return None
    if tracker.type in COUNT_TYPES:
        kind, value = "count", float(sum(1 for v in readable if v))
    else:
        kind, value = "average", sum(readable) / len(readable)
    item = {
        "tracker": tracker.name,
        "type": tracker.type,
        "kind": kind,
        "value": int(value) if kind == "count" else value,
        "rendered": render_value(tracker.type, value, language),
        "days_with_value": len(readable),
        "days_in_period": len(period),
        "missing": missing,
        "unreadable": unreadable,
    }
    item["text"] = render_line(item, language)
    return item


def habits(
    trackers: Sequence[TrackerDef],
    days: Iterable[dict],
    period_days: Sequence[date],
    language: str,
    *,
    shift_yesterday: bool = True,
) -> List[dict]:
    """The habits items, one per tracker with a value in the period; ``[]`` means no habits group."""
    period = [d for d in (_as_date(p) for p in period_days) if d is not None]
    day_list = list(days)
    items: List[dict] = []
    for tracker in trackers:
        if tracker.type not in COUNT_TYPES + NUMERIC_TYPES:
            continue
        values = _values_by_day(tracker, day_list, shift_yesterday)
        item = _item(tracker, values, period, language)
        if item is not None:
            items.append(item)
    return items

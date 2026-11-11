# review_habits.py — the habits group of a review: tracker values of a period as counts and averages.
# version: 0.3.1
"""Habits as numbers for ``/review`` (spec 045, T3.5, PRD F8).

One pure function, ``habits(trackers, days, period_days, language)``: the
tracker definitions (``tracker_defs(config)`` reads them from the existing
``trackers.daily_note_trackers`` and ``end_of_day_fields`` lists), the raw
per-day field values the period reader produced (``ReadResult.days[]``:
``{date, fields: {name: raw}}``) and the review language give one item per
tracker that has a value on at least one day of the period: a count of days
true for a boolean tracker, an average over the days with a value for an
integer, duration (minutes) or time tracker. A time average is the circular
mean on the 24 h clock (23:30 and 00:30 give 00:00); when the times cancel
out (00:00 and 12:00) the average is undefined and the item says "no clear
average" with ``value: None``. Text trackers are skipped. A day without the
field, with an empty value or with a bare ``-`` placeholder is *missing* for
every tracker type (``parse_value`` classifies the raw value once, before
any type parser sees it), a value the type rule cannot read ("ja" for a
number, "7" for a yes/no field, an unrun Templater ``<% … %>``, a digit run
too long to be a tracker value) is *unreadable*; both are named by date and
never counted as zero, and no input value makes this module raise. Fields
arrive already attributed to
the day they describe — the reader owns the ``yesterday_fields`` shift to
D-1 — and are taken as given; a date listed twice keeps the later entry.
Each item carries its structured numbers and the rendered line from the
de/en label table (English for any other language). No Kado, no model, no
I/O; the values stay in the result, never on stdout or stderr.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence

from lib.review_config import tracker_types

NUMERIC_TYPES = ("integer", "duration", "time")
COUNT_TYPES = ("boolean",)

_TRUE = {"true", "yes", "ja", "x", "1", "✅", "[x]", "done", "y", "j"}
_FALSE = {"false", "no", "nein", "0", "❌", "[ ]", "[]", "n"}
_PLACEHOLDER = {"-"}

_DIGITS = r"\d{1,9}"
_NUMBER = rf"{_DIGITS}(?:[.,]{_DIGITS})?"
_RE_NUMBER = re.compile(rf"^[+-]?{_NUMBER}$")
_RE_H_M = re.compile(
    rf"^({_NUMBER})\s*h(?:ours?|rs?)?\s*(?:({_DIGITS})\s*(?:m(?:in(?:utes?)?)?)?)?$", re.IGNORECASE,
)
_RE_MINUTES = re.compile(rf"^({_DIGITS})\s*(?:m|min|mins|minutes?)$", re.IGNORECASE)
_RE_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
_RE_TEMPLATER = re.compile(r"<%.*%>", re.DOTALL)

MINUTES_PER_DAY = 24 * 60
_NO_DIRECTION = 1e-9

_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "count": "{tracker}: {value} of {days} days",
        "average": "{tracker}: average {value} over {days} days",
        "no_average": "{tracker}: {value} over {days} days",
        "no_average_value": "no clear average",
        "period": "{days} days in the period",
        "missing": "missing: {dates}",
        "unreadable": "unreadable: {dates}",
        "decimal": ".",
    },
    "de": {
        "count": "{tracker}: {value} von {days} Tagen",
        "average": "{tracker}: Durchschnitt {value} über {days} Tage",
        "no_average": "{tracker}: {value} über {days} Tage",
        "no_average_value": "kein klarer Durchschnitt",
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


def tracker_defs(config: dict) -> List[TrackerDef]:
    """The configured trackers in config order (today, yesterday and end-of-day lists)."""
    return [TrackerDef(name=name, type=type_) for name, type_ in tracker_types(config).items()]


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


def _minute_part(text: str, raw_minutes: Optional[str]) -> int:
    """The minute part of an hours-plus-minutes spelling; above 59 it is not minutes."""
    minutes = int(raw_minutes) if raw_minutes else 0
    if minutes > 59:
        raise Unreadable(text)
    return minutes


def parse_duration(text: str) -> float:
    """Minutes. ``7h30``, ``7h 30m``, ``7:30``, ``450m``, ``90 min``, ``1.5h``; a plain number is hours."""
    clock = _RE_CLOCK.match(text)
    if clock:
        return int(clock.group(1)) * 60 + _minute_part(text, clock.group(2))
    minutes = _RE_MINUTES.match(text)
    if minutes:
        return float(minutes.group(1))
    h_m = _RE_H_M.match(text)
    if h_m:
        return _number(h_m.group(1)) * 60 + _minute_part(text, h_m.group(2))
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
    """The typed value; None for no value or the bare ``-`` placeholder, whatever the type;
    raises ``Unreadable`` for a value the type cannot read."""
    text = _text(raw)
    if text is None or text in _PLACEHOLDER:
        return None
    if _RE_TEMPLATER.search(text):
        raise Unreadable(text)
    value = _PARSERS[type_](text)
    if isinstance(value, float) and not math.isfinite(value):
        raise Unreadable(text)
    return value


# --- averages --------------------------------------------------------------------------

def _half_up(value: float) -> int:
    return math.floor(value + 0.5)


def circular_mean_minutes(values: Sequence[float]) -> Optional[float]:
    """The mean of clock times (minutes since midnight) on the 24 h clock; None when they cancel out."""
    angles = [v / MINUTES_PER_DAY * 2 * math.pi for v in values]
    mean_cos = sum(math.cos(a) for a in angles) / len(angles)
    mean_sin = sum(math.sin(a) for a in angles) / len(angles)
    if math.hypot(mean_cos, mean_sin) < _NO_DIRECTION:
        return None
    minutes = math.atan2(mean_sin, mean_cos) / (2 * math.pi) * MINUTES_PER_DAY
    return round(minutes, 6) % MINUTES_PER_DAY


def average(type_: str, values: Sequence[float]) -> Optional[float]:
    """The average for a numeric tracker type; None only for a time average with no direction."""
    if type_ == "time":
        return circular_mean_minutes(values)
    return sum(values) / len(values)


# --- rendering -------------------------------------------------------------------------

def render_value(type_: str, value: Optional[float], language: str) -> str:
    labels = _labels(language)
    if value is None:
        return labels["no_average_value"]
    if type_ == "boolean":
        return str(int(value))
    if type_ == "duration":
        total = _half_up(value)
        return f"{total // 60}h {total % 60:02d}m"
    if type_ == "time":
        total = _half_up(value) % MINUTES_PER_DAY
        return f"{total // 60:02d}:{total % 60:02d}"
    return f"{value:.1f}".replace(".", labels["decimal"])


def _labels(language: str) -> Dict[str, str]:
    return _LABELS.get((language or "").lower(), _LABELS["en"])


def render_line(item: dict, language: str) -> str:
    labels = _labels(language)
    template = labels["no_average"] if item["value"] is None else labels[item["kind"]]
    main = template.format(
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


def _values_by_day(tracker: TrackerDef, days: Iterable[dict]) -> Dict[date, Any]:
    """Raw values keyed by the date the reader listed them under; a later entry for the same date wins."""
    out: Dict[date, Any] = {}
    for entry in days:
        fields = entry.get("fields") or {}
        if tracker.name not in fields:
            continue
        day = _as_date(entry.get("date"))
        if day is None:
            continue
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
        kind, value = "average", average(tracker.type, readable)
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
) -> List[dict]:
    """The habits items, one per tracker with a value in the period; ``[]`` means no habits group."""
    period = [d for d in (_as_date(p) for p in period_days) if d is not None]
    day_list = list(days)
    items: List[dict] = []
    for tracker in trackers:
        if tracker.type not in COUNT_TYPES + NUMERIC_TYPES:
            continue
        values = _values_by_day(tracker, day_list)
        item = _item(tracker, values, period, language)
        if item is not None:
            items.append(item)
    return items

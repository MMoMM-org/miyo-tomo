# period.py — weeks, months, quarters, the week rule and the /review argument.
# version: 0.2.0
"""Week, month and quarter arithmetic for ``/review`` (spec 045; quarter: spec 046).

Owns the week rule (first day of the week, minimum days in week 1; ISO is
Monday and 4), the ``Period`` value (a week, a calendar month or a calendar
quarter with its first and last day), the periodic name formats (Moment-style
``GGGG-[W]WW``, ``gggg-[W]ww``, ``YYYY-MM``, ``YYYY-[Q]Q`` with ``[...]``
literals), their rendering, parsing and safety check, the weeks overlapping a
month or quarter, a quarter's months, the note paths a period may live at, and
the parsing of the ``/review`` argument into a ``Request`` or a
``RequestError`` object.

Stdlib only. ``today`` is always passed in; nothing here reads the clock.
Years are supported in ``MIN_YEAR..MAX_YEAR`` (0002..9998); anything a
``date`` cannot hold raises ``InvalidPeriod`` like a week number outside its
year does.

Design notes: docs/tomo/scripts/lib/period.md
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, Union

WEEK = "week"
MONTH = "month"
QUARTER = "quarter"
SETUP = "setup"
KINDS = (WEEK, MONTH, QUARTER)

DAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DEFAULT_FORMATS = {WEEK: "GGGG-[W]WW", MONTH: "YYYY-MM", QUARTER: "YYYY-[Q]Q"}

# Longest token first so the scanner never splits GGGG into G+G+G+G.
_TOKENS = ("GGGG", "gggg", "YYYY", "WW", "ww", "MM", "W", "w", "M", "Q")
_ISO_WEEK_TOKENS = ("GGGG", "WW", "W")
_RULE_WEEK_TOKENS = ("gggg", "ww", "w")
_YEAR_TOKENS = ("GGGG", "gggg", "YYYY")
_NUMBER_TOKENS = {WEEK: ("WW", "ww", "W", "w"), MONTH: ("MM", "M"), QUARTER: ("Q",)}
_NAMES = {WEEK: "{y}-W{n:02d}", MONTH: "{y}-{n:02d}", QUARTER: "{y}-Q{n}"}
_EXAMPLES = {WEEK: "2026-W13", MONTH: "2026-03", QUARTER: "2026-Q1"}
_MAX_NUMBER = {WEEK: 53, MONTH: 12, QUARTER: 4}
_UNSAFE = ("/", "\\", "..")
_YEAR_SEARCH_LIMIT = 60
# date() holds 1..9999; a week may start in the year before its week year and end in the year after.
MIN_YEAR = 2
MAX_YEAR = 9998

# (kind, has a year, pattern); the shapes are disjoint, so the order only fixes the scan.
_ARG_RES = tuple((kind, full, re.compile(pattern)) for kind, full, pattern in (
    (WEEK, True, r"(\d{4})-[Ww](\d{1,2})"), (WEEK, False, r"[Ww](\d{1,2})"),
    (MONTH, True, r"(\d{4})-(\d{1,2})"), (MONTH, False, r"[Mm](\d{1,2})"),
    (QUARTER, True, r"(\d{4})-[Qq](\d{1,2})"), (QUARTER, False, r"[Qq](\d{1,2})")))


class InvalidPeriod(ValueError):
    """A week, month or quarter number that does not exist in its year, or a year outside
    ``MIN_YEAR..MAX_YEAR``."""


def check_year(year: int) -> None:
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise InvalidPeriod(f"year outside {MIN_YEAR:04d}..{MAX_YEAR:04d}")


@dataclass(frozen=True)
class WeekRule:
    """How weeks are counted: ``first_day`` 0 = Monday .. 6 = Sunday,
    ``min_days_in_first_week`` 1..7 (4 = ISO, 1 = week 1 holds 1 January)."""

    first_day: int = 0
    min_days_in_first_week: int = 4

    def __post_init__(self) -> None:
        if not 0 <= self.first_day <= 6:
            raise ValueError("first_day must be 0..6 (0 = Monday)")
        if not 1 <= self.min_days_in_first_week <= 7:
            raise ValueError("min_days_in_first_week must be 1..7")

    @classmethod
    def from_config(cls, first_day: Union[str, int], min_days: int) -> "WeekRule":
        if isinstance(first_day, str):
            name = first_day.strip().lower()
            if name not in DAY_NAMES:
                raise ValueError("first_day must name a weekday")
            first_day = DAY_NAMES.index(name)
        return cls(first_day=int(first_day), min_days_in_first_week=int(min_days))

    def week_start_of_year(self, week_year: int) -> date:
        """First day of week 1 of ``week_year``; ``InvalidPeriod`` when no date can hold it."""
        try:
            jan1 = date(week_year, 1, 1)
            start = jan1 - timedelta(days=(jan1.weekday() - self.first_day) % 7)
        except (ValueError, OverflowError):
            raise InvalidPeriod(f"year outside {MIN_YEAR:04d}..{MAX_YEAR:04d}") from None
        days_in_year_of_that_week = 7 - (jan1 - start).days
        if days_in_year_of_that_week >= self.min_days_in_first_week:
            return start
        return start + timedelta(days=7)

    def weeks_in(self, week_year: int) -> int:
        check_year(week_year)
        span = self.week_start_of_year(week_year + 1) - self.week_start_of_year(week_year)
        return span.days // 7

    def week_of(self, d: date) -> Tuple[int, int]:
        """``(week_year, week)`` of a date."""
        check_year(d.year)
        for week_year in (d.year + 1, d.year, d.year - 1):
            start = self.week_start_of_year(week_year)
            if d >= start:
                return week_year, (d - start).days // 7 + 1
        raise AssertionError("unreachable: every date lies in some week year")

    def week_start(self, week_year: int, week: int) -> date:
        if not 1 <= week <= self.weeks_in(week_year):
            raise InvalidPeriod("week number outside the year")
        return self.week_start_of_year(week_year) + timedelta(days=7 * (week - 1))


ISO = WeekRule(first_day=0, min_days_in_first_week=4)


@dataclass(frozen=True)
class Period:
    """A week, a calendar month or a calendar quarter; ``end`` is inclusive."""

    kind: str
    year: int
    number: int
    start: date
    end: date

    @classmethod
    def week(cls, year: int, number: int, rule: WeekRule = ISO) -> "Period":
        start = rule.week_start(year, number)
        return cls(WEEK, year, number, start, start + timedelta(days=6))

    @classmethod
    def month(cls, year: int, number: int) -> "Period":
        check_year(year)
        if not 1 <= number <= 12:
            raise InvalidPeriod("month number outside the year")
        last = calendar.monthrange(year, number)[1]
        return cls(MONTH, year, number, date(year, number, 1), date(year, number, last))

    @classmethod
    def quarter(cls, year: int, number: int) -> "Period":
        check_year(year)
        if not 1 <= number <= 4:
            raise InvalidPeriod("quarter number outside the year")
        return cls(QUARTER, year, number, cls.month(year, 3 * number - 2).start, cls.month(year, 3 * number).end)

    @classmethod
    def containing(cls, kind: str, d: date, rule: WeekRule = ISO) -> "Period":
        if kind == WEEK:
            return cls.week(*rule.week_of(d), rule)
        if kind == QUARTER:
            return cls.quarter(d.year, (d.month - 1) // 3 + 1)
        return cls.month(d.year, d.month)

    @property
    def name(self) -> str:
        return _NAMES[self.kind].format(y=self.year, n=self.number)

    def days(self) -> List[date]:
        return [self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)]

    def is_finished(self, today: date) -> bool:
        return self.end < today

    def previous(self, rule: WeekRule = ISO) -> "Period":
        return Period.containing(self.kind, self.start - timedelta(days=1), rule)

    def months(self) -> List["Period"]:
        """The three months of a quarter, in order; only for a quarter."""
        if self.kind != QUARTER:
            raise ValueError("months is defined for a quarter only")
        return [Period.month(self.year, 3 * self.number - 2 + i) for i in range(3)]

    def weeks_overlapping(self, rule: WeekRule = ISO) -> List["Period"]:
        """The weeks a month or quarter touches, in order; not for a week."""
        if self.kind == WEEK:
            raise ValueError("weeks_overlapping is defined for a month or quarter only")
        weeks = []
        week = Period.containing(WEEK, self.start, rule)
        while week.start <= self.end:
            weeks.append(week)
            week = Period.containing(WEEK, week.end + timedelta(days=1), rule)
        return weeks

    def note_paths(self, folder: str, fmt: str) -> List[str]:
        """Flat path first, then the year subfolder (week year for weeks, else calendar year)."""
        base = folder if folder.endswith("/") else folder + "/"
        name = render_name(self, fmt)
        return [f"{base}{name}.md", f"{base}{self.year}/{name}.md"]


def build(kind: str, year: int, number: int, rule: WeekRule = ISO) -> Period:
    """The period of ``kind`` with that number; ``InvalidPeriod`` when the year has none."""
    if kind == WEEK:
        return Period.week(year, number, rule)
    return Period.quarter(year, number) if kind == QUARTER else Period.month(year, number)


def last_finished(kind: str, today: date, rule: WeekRule = ISO) -> Period:
    current = Period.containing(kind, today, rule)
    return current.previous(rule)


# --- name formats ------------------------------------------------------------------

def _tokenize(fmt: str) -> List[Tuple[str, str]]:
    """``[("token", "GGGG"), ("literal", "-"), ...]``; an unknown letter is a token too."""
    parts: List[Tuple[str, str]] = []
    i = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch == "[":
            close = fmt.find("]", i + 1)
            if close == -1:
                parts.append(("literal", fmt[i + 1:]))
                break
            parts.append(("literal", fmt[i + 1:close]))
            i = close + 1
            continue
        for token in _TOKENS:
            if fmt.startswith(token, i):
                parts.append(("token", token))
                i += len(token)
                break
        else:
            parts.append(("token" if ch.isalpha() else "literal", ch))
            i += 1
    return parts


def _tokens_of(fmt: str) -> List[str]:
    return [text for kind, text in _tokenize(fmt) if kind == "token"]


def format_kind(fmt: str) -> Optional[str]:
    """``week``, ``month``, ``quarter`` or None when the format names none or more than one."""
    tokens = _tokens_of(fmt)
    found = [kind for kind, numbers in _NUMBER_TOKENS.items() if any(t in numbers for t in tokens)]
    return found[0] if len(found) == 1 else None


def _render(fmt: str, *, year: int, number: int, iso_year: int, iso_week: int, calendar_year: int) -> str:
    """Fill the tokens: GGGG/WW from the ISO pair, gggg/ww/MM from the period's own
    numbers, Q from the quarter's, YYYY from the calendar year; an unknown letter stays as it is."""
    values = {
        "GGGG": f"{iso_year:04d}", "WW": f"{iso_week:02d}", "W": str(iso_week),
        "gggg": f"{year:04d}", "ww": f"{number:02d}", "w": str(number),
        "YYYY": f"{calendar_year:04d}", "MM": f"{number:02d}", "M": str(number), "Q": str(number),
    }
    return "".join(values.get(text, text) if kind == "token" else text for kind, text in _tokenize(fmt))


def render_name(period: Period, fmt: str) -> str:
    if format_kind(fmt) != period.kind:
        raise ValueError("name format does not match the period kind")
    iso_year, iso_week = ISO.week_of(period.start) if period.kind == WEEK else (period.year, 0)
    return _render(fmt, year=period.year, number=period.number, iso_year=iso_year, iso_week=iso_week,
                   calendar_year=period.year)


def parse_name(name: str, fmt: str, rule: WeekRule = ISO) -> Optional[Period]:
    """The period a note name denotes under ``fmt``, or None when it does not fit."""
    kind = format_kind(fmt)
    if kind is None:
        return None
    pattern = []
    for part_kind, text in _tokenize(fmt):
        if part_kind == "literal":
            pattern.append(re.escape(text))
        elif text in _YEAR_TOKENS:
            pattern.append(r"(?P<year>\d{4})")
        elif text in ("WW", "ww", "MM"):
            pattern.append(r"(?P<number>\d{2})")
        elif text in ("W", "w", "M", "Q"):
            pattern.append(r"(?P<number>\d{1,2})")
        else:
            pattern.append(re.escape(text))
    try:
        match = re.fullmatch("".join(pattern), name)
    except re.error:
        return None  # a year or number token used twice
    if match is None:
        return None
    year, number = int(match.group("year")), int(match.group("number"))
    try:
        week_rule = ISO if any(t in _ISO_WEEK_TOKENS for t in _tokens_of(fmt)) else rule
        return build(kind, year, number, week_rule)
    except InvalidPeriod:
        return None


@dataclass(frozen=True)
class FormatProblem:
    kind: str
    example: str = ""


def _year_end_mismatch(rule: WeekRule, year: int) -> Optional[date]:
    """First date around the turn of ``year`` whose week year is not its calendar year."""
    d = date(year, 12, 25)
    last = date(year + 1, 1, 7)
    while d <= last:
        if rule.week_of(d)[0] != d.year:
            return d
        d += timedelta(days=1)
    return None


def check_format(fmt: str, kind: str, rule: WeekRule = ISO, *, today: date) -> List[FormatProblem]:
    """Problems that make ``fmt`` unusable as the name format of ``kind``; empty = fine."""
    problems: List[FormatProblem] = []
    if any(mark in fmt for mark in _UNSAFE):
        problems.append(FormatProblem("unsafe-format"))
    tokens = _tokens_of(fmt)
    unknown = sorted({t for t in tokens if t not in _TOKENS})
    if unknown:
        problems.append(FormatProblem("unknown-token", ", ".join(unknown)))
    known = [t for t in tokens if t in _TOKENS]
    fmt_kind = format_kind(fmt)
    if fmt_kind is None:
        problems.append(FormatProblem("no-period-token"))
        return problems
    if fmt_kind != kind:
        problems.append(FormatProblem("kind-mismatch"))
        return problems
    if not any(t in _YEAR_TOKENS for t in known):
        problems.append(FormatProblem("no-year-token"))
        return problems
    if fmt_kind == WEEK:
        problems.extend(_week_format_problems(fmt, known, rule, today))
    return problems


def _week_format_problems(fmt: str, tokens: List[str], rule: WeekRule, today: date) -> List[FormatProblem]:
    problems: List[FormatProblem] = []
    if "YYYY" in tokens:
        example = ""
        for year in range(today.year, min(today.year + _YEAR_SEARCH_LIMIT, MAX_YEAR)):
            d = _year_end_mismatch(rule, year)
            if d is not None:
                week_year, week = rule.week_of(d)
                iso_year, iso_week = ISO.week_of(d)
                named = _render(fmt, year=week_year, number=week, iso_year=iso_year, iso_week=iso_week,
                                calendar_year=d.year)
                example = f"{d.isoformat()} would be named {named} but lies in {week_year}-W{week:02d}"
                break
        problems.append(FormatProblem("calendar-year-with-week", example))
        return problems
    uses_iso = any(t in _ISO_WEEK_TOKENS for t in tokens)
    uses_rule = any(t in _RULE_WEEK_TOKENS for t in tokens)
    if uses_iso and uses_rule:
        problems.append(FormatProblem("mixed-week-tokens"))
    elif uses_iso and rule != ISO:
        problems.append(FormatProblem("iso-tokens-need-iso-rule"))
    return problems


# --- the /review argument -----------------------------------------------------------

@dataclass(frozen=True)
class Request:
    kind: str                       # week | month | quarter | setup
    period: Optional[Period] = None
    year_inferred: bool = False
    source: str = "arg"             # arg | at | default

    def to_dict(self) -> Dict[str, object]:
        if self.kind == SETUP:
            return {"kind": SETUP}
        return {"kind": self.kind, "period": self.period.name,
                "year_inferred": self.year_inferred, "source": self.source}


@dataclass(frozen=True)
class RequestError:
    kind: str                       # invalid-period | unfinished-period | not-periodic-note | unknown-argument
    expected: str
    example: str
    last_finished: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        out: Dict[str, object] = {"kind": self.kind, "expected": self.expected, "example": self.example}
        if self.last_finished is not None:
            out["last_finished"] = self.last_finished
        return out


_GRAMMAR = ("nothing (the last finished week), week, month, quarter, setup, a week like 2026-W13 or W13, "
            "a month like 2026-03 or M03, a quarter like 2026-Q1 or Q1, or @<weekly, monthly or quarterly note>")


def parse_args(raw: str, *, today: date, rule: WeekRule = ISO,
               formats: Optional[Dict[str, str]] = None) -> Union[Request, RequestError]:
    """The ``/review`` argument as a request, or the error the skill shows."""
    formats = dict(DEFAULT_FORMATS, **(formats or {}))
    text = raw.strip()
    if text.startswith("@"):
        return _parse_at(text[1:].strip(), today, rule, formats)
    words = text.split()
    if not words:
        return _default(WEEK, today, rule)
    if [w.lower() for w in words] == [SETUP]:
        return Request(SETUP)
    kind_word = words[0].lower() if words[0].lower() in KINDS else None
    rest = words[1:] if kind_word else words
    if len(rest) > 1:
        return _unknown(today, rule)
    if not rest:
        return _default(kind_word, today, rule)
    return _parse_period_word(rest[0], kind_word, today, rule)


def _default(kind: str, today: date, rule: WeekRule) -> Request:
    return Request(kind, last_finished(kind, today, rule), source="default")


def _unknown(today: date, rule: WeekRule) -> RequestError:
    return RequestError("unknown-argument", _GRAMMAR, last_finished(WEEK, today, rule).name)


def _invalid(kind: str, expected: str, today: date, rule: WeekRule, example: Optional[str] = None) -> RequestError:
    return RequestError("invalid-period", expected, example or last_finished(kind, today, rule).name)


def _finished_or_error(period: Period, today: date, rule: WeekRule, *, year_inferred: bool,
                       source: str) -> Union[Request, RequestError]:
    if not period.is_finished(today):
        last = last_finished(period.kind, today, rule).name
        return RequestError("unfinished-period", f"a finished {period.kind}", last, last_finished=last)
    return Request(period.kind, period, year_inferred=year_inferred, source=source)


def _parse_period_word(word: str, kind_word: Optional[str], today: date,
                       rule: WeekRule) -> Union[Request, RequestError]:
    found = next(((k, full, m) for k, full, regex in _ARG_RES for m in [regex.fullmatch(word)] if m), None)
    if found is None:
        return _unknown(today, rule)
    kind, full, match = found
    if kind_word and kind_word != kind:
        return _invalid(kind_word, f"a {kind_word} like {_EXAMPLES[kind_word]} after the word {kind_word}", today, rule)
    if full:
        return _parse_full(kind, int(match.group(1)), int(match.group(2)), today, rule)
    period = _latest_finished_with_number(kind, int(match.group(1)), today, rule)
    if period is None:
        return _invalid(kind, f"a {kind} number between 1 and {_MAX_NUMBER[kind]}", today, rule)
    return Request(kind, period, year_inferred=True, source="arg")


def _parse_full(kind: str, year: int, number: int, today: date, rule: WeekRule) -> Union[Request, RequestError]:
    if not MIN_YEAR <= year <= MAX_YEAR:
        return _invalid(kind, f"a year between {MIN_YEAR:04d} and {MAX_YEAR:04d}", today, rule)
    try:
        period = build(kind, year, number, rule)
    except InvalidPeriod:
        count = rule.weeks_in(year) if kind == WEEK else _MAX_NUMBER[kind]
        first, last = (_NAMES[kind].format(y=year, n=n) for n in (1, count))
        return _invalid(kind, f"a {kind} of {year} between {first} and {last}", today, rule, example=last)
    return _finished_or_error(period, today, rule, year_inferred=False, source="arg")


def _latest_finished_with_number(kind: str, number: int, today: date, rule: WeekRule) -> Optional[Period]:
    for year in range(today.year, today.year - _YEAR_SEARCH_LIMIT, -1):
        try:
            period = build(kind, year, number, rule)
        except InvalidPeriod:
            if kind != WEEK:
                return None
            continue
        if period.is_finished(today):
            return period
    return None


def _parse_at(text: str, today: date, rule: WeekRule, formats: Dict[str, str]) -> Union[Request, RequestError]:
    name = text.strip()
    if name.startswith("[[") and name.endswith("]]"):
        name = name[2:-2]
    name = name.rsplit("/", 1)[-1]
    if name.lower().endswith(".md"):
        name = name[:-3]
    if not name:
        return _unknown(today, rule)
    for kind in KINDS:
        period = parse_name(name, formats[kind], rule)
        if period is not None:
            return _finished_or_error(period, today, rule, year_inferred=False, source="at")
    expected = (f"a weekly note named like {formats[WEEK]}, a monthly note named like {formats[MONTH]} "
                f"or a quarterly note named like {formats[QUARTER]}")
    return RequestError("not-periodic-note", expected, last_finished(WEEK, today, rule).name)

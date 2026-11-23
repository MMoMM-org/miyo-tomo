# review_period.py — reads a period for /review: dailies, the day after, child-review notes, link differences, growth.
# version: 0.5.2
"""Reading a period for ``/review`` (spec 045, T3.3; PRD F3-AC5..7, F3-AC9).

Owns what lies between one day and the report: finding the dailies of every
day (flat and ``<folder>/<YYYY>/``, duplicates named), reading the daily of
the day after the period for its yesterday fields only, resolving the link
stems ``read_day`` asks for to vault paths (one ``byName`` per stem), reading
each living task note once for the period, the child-review notes by the
``CHILD`` table (spec 046 ADR-6: a month marks against its weekly notes; a
quarter reads its weekly notes as sources and marks against its monthly
notes; finding and reading them is ``lib/review_children.py``'s), the two
link differences per marked level (``only_in_<label>_links``,
``dailies_not_in_<label>``), vault growth from the created-notes query (each
entry with its local creation ``day``, ``created_day``) and the MOC
listings, and the per-source report. ``kado_empty`` and the
``check-key-access`` advice come from the daily and child folder listings
only; a growth query Kado answered with nothing is named in
``report.growth.kado_none``. Every level read carries a ``<label>_status``
(``not-configured`` without its folder and format).
Day reading is ``lib/review_day.py``'s: its functions arrive as a
``DayReaders`` value (default: imported lazily). Every Kado call goes through
``lib/review_reader.PacedReader`` on ``ReviewPacer.read``; ``read_period``
calls ``finish()`` itself, re-runs the days whose reads the end pass
recovered and, when the end pass recovered a daily or child folder listing,
resolves and reads that listing's notes then (the only reads after the end
pass); ``result["not_read"]`` and ``report["not_read"]`` are one list, set
after the last read, so the caller only prints ``pacer.summary(result["not_read"])``. A
folder listing still in ``not_read`` leaves its days or weeks empty with no
``kado_empty`` and no advice: a daily folder there is a period that could
not be read (``review-read.py`` stops with ``raise-kado-limit``), a child
folder there is ``<label>_status: not-read``. Connection and auth errors
propagate.

Design notes: docs/tomo/scripts/lib/review_period.md
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from lib import review_children as children
from lib.file_extensions import KNOWN_FILE_EXTENSIONS
from lib.moc_folders import moc_folder_prefixes
from lib.period import ISO, MONTH, QUARTER, WEEK, Period, WeekRule, parse_name
from lib.review_children import ChildNotes, Found
from lib.review_config import GRANULARITY, configured_formats, folder_for
from lib.review_reader import PacedReader
from lib.review_weekly import (
    DEFAULT_DAILY_FORMAT,
    DEFAULT_WEEKLY_SKIP,
    daily_date,
    daily_name,
    link_key,
    unique_targets,
)
from lib.vault_config_edit import get_path
from lib.vault_paths import path_key

ADVICE_CHECK_ACCESS = "check-key-access"
CHILD = {MONTH: WEEK, QUARTER: MONTH}    # the child-review level a period marks against
GROWTH_CREATED, GROWTH_MOCS = "created", "mocs"
PROBLEM_LINKED_MISSING = "linked-missing"
ROOT = "/"


@dataclass(frozen=True)
class PeriodSources:
    """Where a period's notes live; built by ``sources_from_config`` or by hand."""

    daily_folder: str
    daily_format: str = DEFAULT_DAILY_FORMAT
    weekly_folder: Optional[str] = None
    weekly_format: Optional[str] = None
    rule: WeekRule = ISO
    own_sections: Sequence[str] = ()
    weekly_skip_sections: Sequence[str] = DEFAULT_WEEKLY_SKIP
    moc_folders: Sequence[str] = ()
    monthly_folder: Optional[str] = None
    monthly_format: Optional[str] = None
    quarterly_format: Optional[str] = None
    monthly_own_sections: Sequence[str] = ()

    def child(self, kind: str) -> ChildNotes:
        if kind == WEEK:
            return ChildNotes(WEEK, self.weekly_folder, self.weekly_format, self.own_sections)
        return ChildNotes(MONTH, self.monthly_folder, self.monthly_format, self.monthly_own_sections)


@dataclass(frozen=True)
class DayReaders:
    """The ``lib/review_day.py`` functions a period read calls (the wave-B seam)."""

    read_day: Callable[[date, Dict[str, str], dict, Callable[[str], Optional[str]]], dict]
    yesterday_fields: Callable[[str, dict], Dict[str, str]]
    attribute_yesterday: Callable[[List[dict], Optional[Dict[str, str]]], List[dict]]
    task_note_tasks: Callable[[str, str], List[dict]]
    done_in_period: Callable[[List[dict], date, date], List[dict]]

    @classmethod
    def default(cls) -> "DayReaders":
        from lib import review_day

        return cls(review_day.read_day, review_day.yesterday_fields, review_day.attribute_yesterday,
                   review_day.task_note_tasks, review_day.done_in_period)


def sources_from_config(config: dict, profile: dict) -> PeriodSources:
    """The sources of a period from ``vault-config.yaml`` (config over profile)."""
    week = get_path(config, ("review", "week"))[1]
    week = week if isinstance(week, dict) else {}
    try:
        rule = WeekRule.from_config(week.get("first_day", "monday"), week.get("min_days_in_first_week", 4))
    except (ValueError, TypeError):
        rule = ISO
    daily_format = get_path(config, ("naming", "calendar_patterns", "daily"))[1]
    formats = configured_formats(config)
    return PeriodSources(
        daily_folder=folder_for(config, profile, "daily") or "",
        daily_format=daily_format.strip() if isinstance(daily_format, str) and daily_format.strip()
        else DEFAULT_DAILY_FORMAT,
        weekly_folder=folder_for(config, profile, GRANULARITY[WEEK]),
        weekly_format=formats.get(WEEK),
        rule=rule,
        own_sections=_own_sections(config, WEEK),
        moc_folders=moc_folder_prefixes(config),
        monthly_folder=folder_for(config, profile, GRANULARITY[MONTH]),
        monthly_format=formats.get(MONTH),
        quarterly_format=formats.get(QUARTER),
        monthly_own_sections=_own_sections(config, MONTH),
    )


def _own_sections(config: dict, kind: str) -> Tuple[str, ...]:
    own = get_path(config, ("review", GRANULARITY[kind], "own_sections"))[1]
    return tuple(s for s in own if isinstance(s, str)) if isinstance(own, list) else ()


def period_bounds_ms(period: Period) -> Tuple[int, int]:
    """Inclusive Unix-ms bounds of the period's local days, for Kado's filter."""
    start = datetime.combine(period.start, time.min).timestamp()
    end = datetime.combine(period.end + timedelta(days=1), time.min).timestamp()
    return int(round(start * 1000)), int(round(end * 1000)) - 1


def created_day(created: Any, period: Period) -> str:
    """The local ISO date of Kado's ``created`` ms inside ``period``; else the period's first day."""
    if isinstance(created, (int, float)) and not isinstance(created, bool):
        try:
            day = datetime.fromtimestamp(created / 1000).date()
        except (OverflowError, OSError, ValueError):
            day = None
        if day is not None and period.start <= day <= period.end:
            return day.isoformat()
    return period.start.isoformat()


# --- the period ---------------------------------------------------------------------

def _empty_day(day: date) -> dict:
    return {"date": day.isoformat(), "dailies": [], "sections": {}, "fields": {}, "partly_read": False,
            "has_content": False, "links": [], "problems": [], "tasks": [], "linked": [],
            "previous_day_fields": {}}


class _PeriodRead:
    def __init__(self, period: Period, sources: PeriodSources, settings: dict, client, pacer, readers: DayReaders):
        self.period, self.sources, self.settings, self.readers = period, sources, settings, readers
        self.reader = PacedReader(client, pacer)
        self.kado_empty: List[str] = []
        self.growth_kado_none: List[str] = []
        self.found: Dict[date, List[str]] = {}
        self.after = period.end + timedelta(days=1)
        self.task_notes: List[str] = [p for p in settings.get("task_notes") or [] if isinstance(p, str)]

    def _empty(self, key: str, source: str) -> None:
        if self.reader.answered(key) and source not in self.kado_empty:
            self.kado_empty.append(source)

    def _growth_none(self, key: str, part: str) -> None:
        if self.reader.answered(key) and part not in self.growth_kado_none:
            self.growth_kado_none.append(part)

    # dailies
    def _find_dailies(self) -> Optional[List[str]]:
        """Fill ``found`` from the daily folder listing; returns the listing (None: not answered or empty)."""
        listing = self.reader.folder(self.sources.daily_folder)
        if listing is None:
            self._empty(self.reader.dir_key(self.sources.daily_folder), "dailies")
        keys = {path_key(p): p for p in listing or []}
        base = self.sources.daily_folder.rstrip("/") + "/"
        for day in self.period.days() + [self.after]:
            name = daily_name(day, self.sources.daily_format)
            candidates = (f"{base}{name}.md", f"{base}{day.year}/{name}.md")
            self.found[day] = [keys[path_key(c)] for c in candidates if path_key(c) in keys]
        return listing

    def _texts(self, day: date) -> Dict[str, str]:
        texts = {}
        for path in self.found.get(day, []):
            text = self.reader.note(path)
            if text is not None:
                texts[path] = text
        return texts

    def _day_entry(self, day: date) -> dict:
        texts = self._texts(day)
        if not texts:
            return _empty_day(day)
        return self.readers.read_day(day, texts, self.settings, self.reader.target)

    def _after_fields(self) -> Optional[dict]:
        texts = self._texts(self.after)
        if not texts:
            return None
        fields: Dict[str, str] = {}
        for path in self.found[self.after]:
            for name, value in self.readers.yesterday_fields(texts.get(path, ""), self.settings).items():
                fields.setdefault(name, value)
        return fields

    def _run_days(self, days: Sequence[date], entries: Dict[date, dict], incomplete: Set[date]) -> None:
        for day in days:
            self.reader.hit_pending = False
            entries[day] = self._day_entry(day)
            if self.reader.hit_pending:
                incomplete.add(day)

    # task notes, once for the period
    def _tasks(self, days: List[dict]) -> Tuple[List[dict], List[dict]]:
        by_date = {e["date"]: e for e in days}
        open_tasks, report = [], []
        for path in self.task_notes:
            text = self.reader.note(path)
            if text is None:
                report.append({"path": path, "state": "failed" if path in self.reader.not_read else "missing"})
                continue
            report.append({"path": path, "state": "read"})
            tasks = self.readers.task_note_tasks(path, text)
            for task in self.readers.done_in_period(tasks, self.period.start, self.period.end):
                entry = by_date.get(str(task.get("done_date")))
                if entry is not None:
                    entry.setdefault("tasks", []).append(task)
            open_tasks.extend(t for t in tasks if not t.get("done"))
        return open_tasks, report

    # child-review notes
    def _levels(self) -> List[ChildNotes]:
        """The child levels read, weekly first; the marked one is ``CHILD[kind]``, the weekly notes always read."""
        marked = CHILD.get(self.period.kind)
        if marked is None:
            return []
        return [self.sources.child(k) for k in ([WEEK] if marked == WEEK else [WEEK, marked])]

    def _find_children(self, child: ChildNotes) -> Found:
        found = children.find(self.reader, self.period, child, self.sources.rule)
        if found[0] is None:
            self._empty(self.reader.dir_key(child.folder), child.label)
        return found

    def _is_periodic(self, target: str) -> bool:
        stem = target.strip().rsplit("/", 1)[-1]
        if daily_date(stem, self.sources.daily_format) is not None:
            return True
        formats = (self.sources.weekly_format, self.sources.monthly_format, self.sources.quarterly_format)
        return any(fmt and parse_name(stem, fmt, self.sources.rule) is not None for fmt in formats)

    @staticmethod
    def _content_links(entry: dict) -> List[str]:
        """A day's links without the same-day notes it read or missed (they are structure, not content)."""
        structural = {link_key(item["path"]) for item in entry.get("linked", []) + entry.get("problems", [])
                      if item.get("path")}
        return [t for t in entry.get("links", []) if link_key(t) not in structural]

    @staticmethod
    def _is_attachment(target: str) -> bool:
        """An embed or link to a file such as ``snow.png``: not a note a review could miss."""
        stem, dot, ext = target.rpartition(".")
        return bool(dot and stem) and ext.lower() != "md" and ext.lower() in KNOWN_FILE_EXTENSIONS

    def _compared(self, target: str) -> bool:
        return not self._is_periodic(target) and not self._is_attachment(target)

    def _link_differences(self, days: List[dict], notes: List[dict], kind: str) -> Tuple[List[str], List[str]]:
        daily_keys = {link_key(t) for e in days for t in e.get("links", [])}
        child_keys: Dict[str, Set[str]] = {}
        for note in notes:
            child_keys.setdefault(note[kind], set()).update(link_key(t) for t in note["links"])
        only_in_child = unique_targets([t for n in notes for t in n["links"]
                                        if link_key(t) not in daily_keys and self._compared(t)])
        not_in_child: List[str] = []
        for e in days:
            name = Period.containing(kind, date.fromisoformat(e["date"]), self.sources.rule).name
            if name not in child_keys:
                continue
            not_in_child.extend(t for t in self._content_links(e)
                                if link_key(t) not in child_keys[name] and self._compared(t))
        return only_in_child, unique_targets(not_in_child)

    def _child_result(self, child: ChildNotes, found: Optional[Found], days: List[dict],
                      result: Dict[str, Any], report: Dict[str, Any]) -> None:
        entries, rows = children.read(self.reader, self.period, child, found, daily_format=self.sources.daily_format,
                                      skip_sections=self.sources.weekly_skip_sections) if found else ([], [])
        label = child.label
        result[label] = entries
        if entries and child.kind == CHILD[self.period.kind]:
            result[f"only_in_{label}_links"], result[f"dailies_not_in_{label}"] = (
                self._link_differences(days, entries, child.kind))
        report[f"{label}_status"] = children.status(child, entries, found[0] if found else None, self.kado_empty)
        report[f"{label}_notes"] = rows

    # growth
    @staticmethod
    def _created_query(start_ms: int, end_ms: int) -> dict:
        return {"fields": ["links"], "filter": {"createdAfter": start_ms, "createdBefore": end_ms}}

    def _created_items(self, start_ms: int, end_ms: int) -> Optional[List[dict]]:
        return self.reader.notes(ROOT, **self._created_query(start_ms, end_ms))

    def _growth_fetch(self, start_ms: int, end_ms: int) -> None:
        self._created_items(start_ms, end_ms)
        for prefix in self.sources.moc_folders:
            self.reader.notes(prefix)

    def _growth(self, start_ms: int, end_ms: int) -> dict:
        created_items = self._created_items(start_ms, end_ms)
        if created_items is None:
            self._growth_none(self.reader.notes_key(ROOT, **self._created_query(start_ms, end_ms)), GROWTH_CREATED)
        created = [{"path": str(item.get("path")),
                    "links": unique_targets([str(link.get("target") or "") for link in item.get("links") or []
                                             if isinstance(link, dict)]),
                    "day": created_day(item.get("created"), self.period)}
                   for item in created_items or [] if item.get("path")]
        created.sort(key=lambda c: c["path"])
        mocs: List[dict] = []
        for prefix in self.sources.moc_folders:
            items = self.reader.notes(prefix)
            if items is None:
                self._growth_none(self.reader.notes_key(prefix), GROWTH_MOCS)
                continue
            mocs.extend(i for i in items if i.get("path"))
        linked = {link_key(t) for c in created for t in c["links"]}
        changed = sorted(str(m["path"]) for m in mocs
                         if isinstance(m.get("modified"), (int, float)) and start_ms <= m["modified"] <= end_ms)
        by_new = sorted(str(m["path"]) for m in mocs if link_key(str(m["path"])) in linked)
        return {"created": created, "mocs_changed": changed, "mocs_linked_by_new": by_new}

    # report
    def _daily_state(self, path: str, entry: dict) -> str:
        if path in self.reader.not_read or path in self.reader.missing:
            return "failed"
        if entry.get("partly_read"):
            return "partly-read"
        return "found" if entry.get("has_content") else "empty"

    def _linked_state(self, stem: str) -> str:
        path = self.reader.path_of(stem)
        return "failed" if stem in self.reader.not_read or (path and path in self.reader.not_read) else "missing"

    def _day_report(self, day: date, entry: dict) -> dict:
        paths = self.found.get(day, [])
        linked = [{"name": item["path"], "path": self.reader.path_of(item["path"]), "state": "read"}
                  for item in entry.get("linked", []) if item.get("path")]
        linked += [{"name": p["path"], "path": self.reader.path_of(p["path"]), "state": self._linked_state(p["path"])}
                   for p in entry.get("problems", []) if p.get("kind") == PROBLEM_LINKED_MISSING and p.get("path")]
        return {"date": day.isoformat(), "dailies": [{"path": p, "state": self._daily_state(p, entry)} for p in paths],
                "duplicate": len(paths) > 1, "linked": linked}

    def _after_end_pass(self, entries: Dict[date, dict], incomplete: Set[date], after_incomplete: bool,
                        after_fields: Optional[dict], daily_listing: Optional[List[str]],
                        found: Dict[str, Found]) -> Optional[dict]:
        """After ``finish()``: re-run from the cache, then read what a recovered listing exposed."""
        self._run_days(sorted(incomplete), entries, set())
        if after_incomplete:
            after_fields = self._after_fields()
        if daily_listing is None and self._find_dailies() is not None:
            # the end pass recovered the daily listing: nothing of the period was read yet
            self._run_days(self.period.days(), entries, set())
            after_fields = self._after_fields()
        for child in self._levels():
            if child.kind in found and found[child.kind][0] is None:
                found[child.kind] = self._find_children(child)
        return after_fields

    def run(self) -> dict:
        period, sources = self.period, self.sources
        daily_listing = self._find_dailies()
        entries: Dict[date, dict] = {}
        incomplete: Set[date] = set()
        self._run_days(period.days(), entries, incomplete)
        self.reader.hit_pending = False
        after_fields = self._after_fields()
        after_incomplete = self.reader.hit_pending
        for path in self.task_notes:
            self.reader.note(path)
        found: Dict[str, Found] = {}    # (listing, children) per configured child level
        for child in self._levels():
            if child.configured:
                found[child.kind] = self._find_children(child)
                children.prefetch(self.reader, found[child.kind])
        start_ms, end_ms = period_bounds_ms(period)
        self._growth_fetch(start_ms, end_ms)

        self.reader.finish()
        after_fields = self._after_end_pass(entries, incomplete, after_incomplete, after_fields, daily_listing, found)
        days = self.readers.attribute_yesterday([entries[d] for d in sorted(entries)], after_fields)
        for entry in days:
            for item in entry.get("linked", []):
                item["vault_path"] = self.reader.path_of(item["path"])
        open_tasks, task_report = self._tasks(days)
        growth = self._growth(start_ms, end_ms)

        result: Dict[str, Any] = {
            "period": {"kind": period.kind, "name": period.name,
                       "start": period.start.isoformat(), "end": period.end.isoformat()},
            "days": days, "open_tasks": open_tasks, "growth": growth,
        }
        report: Dict[str, Any] = {
            "days": [self._day_report(date.fromisoformat(e["date"]), e) for e in days],
            "day_after": {"date": self.after.isoformat(),
                          "dailies": [{"path": p, "state": "failed" if self.reader.note(p) is None else "read"}
                                      for p in self.found.get(self.after, [])]},
            "task_notes": task_report,
        }
        for child in self._levels():
            self._child_result(child, found.get(child.kind), days, result, report)
        report["growth"] = {"created": len(growth["created"]), "mocs_changed": len(growth["mocs_changed"]),
                            "mocs_linked_by_new": len(growth["mocs_linked_by_new"]),
                            "moc_folders": len(sources.moc_folders), "kado_none": list(self.growth_kado_none)}
        report["kado_empty"] = list(self.kado_empty)
        report["advice"] = [ADVICE_CHECK_ACCESS] if self.kado_empty else []
        result["report"] = report
        # last, after the last read of the run: the one list the caller hands to pacer.summary
        result["not_read"] = report["not_read"] = list(self.reader.not_read)
        return result


def read_period(period: Period, sources: PeriodSources, day_settings: dict, client, pacer, *,
                readers: Optional[DayReaders] = None) -> dict:
    """Read ``period`` through ``pacer`` on ``client``; returns the ``read.json`` body with its ``report``.

    ``day_settings`` is ``review_day.day_settings(setup, config)`` (its ``task_notes``
    are read here, once). ``pacer.finish()`` is called inside; ``result["not_read"]``
    is what still failed afterwards.
    """
    return _PeriodRead(period, sources, day_settings, client, pacer, readers or DayReaders.default()).run()

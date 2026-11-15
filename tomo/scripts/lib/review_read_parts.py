# review_read_parts.py — the read*.json files of a period read: one read.json, or a quarter's index and month parts.
# version: 0.1.0
"""The layout of what /review's reading step leaves for the model (spec 046 T3.4; ADR-7).

``files_of(result, rule)`` turns a ``read_period`` result into the files to
write, name → text, in the order the model reads them: ``read.json`` for a
week or a month; for a quarter ``read-index.json`` (every key but ``days``,
``weekly`` and ``monthly``, plus ``parts``: the month parts' names) and one
``read-<YYYY-MM>.json`` per month of the quarter (``month`` and that month's
``days``, ``weekly`` and ``monthly`` entries). A day goes to the month of its
``date``, a monthly note to its ``month``, a weekly note to the month holding
most of its days inside the quarter under ``rule`` (a tie: the earlier month).
All text is compact JSON, ASCII-escaped, with one trailing newline.

``write(stage, files)`` deletes every read file of the stage folder (the index
first), writes the parts and then the index, and returns the paths in
``files`` order. ``load(stage)`` gives back the one result: ``read.json`` as
it is, or the index joined with its parts in order. ``ReadFilesMissing``: no
read file; ``ReadFilesInvalid``: both layouts, an unreadable or mismatched
part, an unsafe part name. ``stage_files(stage)`` lists the read files present.

Design notes: docs/tomo/scripts/lib/review_read_parts.md
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List

from lib.note_io import atomic_write_text
from lib.period import QUARTER, WEEK, Period, WeekRule, build

READ_FILE = "read.json"
INDEX_FILE = "read-index.json"
PARTS_KEY = "parts"
MONTH_KEY = "month"
SPLIT_KEYS = ("days", "weekly", "monthly")
_PART_RE = re.compile(r"^read-(\d{4}-\d{2})\.json$")
_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


class ReadFilesMissing(Exception):
    """The stage folder holds no read file."""


class ReadFilesInvalid(Exception):
    """The read files cannot be joined into one result."""


def encode_body(data) -> str:
    return json.dumps(data, ensure_ascii=True, separators=(",", ":"))


def encode(data) -> str:
    return encode_body(data) + "\n"


def part_name(month: str) -> str:
    return f"read-{month}.json"


# ---------------------------------------------------------------- split

def majority_month(days: Iterable[date]) -> str:
    """The ``YYYY-MM`` holding most of ``days``; on a tie the earlier month."""
    counts: Dict[str, int] = {}
    for day in days:
        counts[day.isoformat()[:7]] = counts.get(day.isoformat()[:7], 0) + 1
    if not counts:
        raise ValueError("no days")
    return min(counts, key=lambda month: (-counts[month], month))


def _week_month(name: str, quarter: Period, rule: WeekRule) -> str:
    match = _WEEK_RE.match(str(name))
    if match is None:
        raise ValueError(f"weekly entry with an unreadable week name: {name!r}")
    week = build(WEEK, int(match.group(1)), int(match.group(2)), rule)
    return majority_month(d for d in week.days() if quarter.start <= d <= quarter.end)


def _month_of(key: str, entry: dict, quarter: Period, rule: WeekRule) -> str:
    if key == "days":
        return str(entry["date"])[:7]
    if key == "monthly":
        return str(entry[MONTH_KEY])
    return _week_month(entry["week"], quarter, rule)


def _split(result: dict, rule: WeekRule) -> Dict[str, str]:
    quarter = Period.containing(QUARTER, date.fromisoformat(result["period"]["start"]))
    months = [m.name for m in quarter.months()]
    keys = [key for key in SPLIT_KEYS if key in result]
    parts: Dict[str, dict] = {m: {MONTH_KEY: m, **{key: [] for key in keys}} for m in months}
    for key in keys:
        for entry in result[key]:
            month = _month_of(key, entry, quarter, rule)
            if month not in parts:
                raise ValueError(f"{key} entry outside {quarter.name}: {month}")
            parts[month][key].append(entry)
    index = {k: v for k, v in result.items() if k not in SPLIT_KEYS}
    index[PARTS_KEY] = [part_name(m) for m in months]
    files = {INDEX_FILE: encode(index)}
    files.update((part_name(m), encode(parts[m])) for m in months)
    return files


def files_of(result: dict, rule: WeekRule) -> Dict[str, str]:
    """Name → text of the files a read writes, the file the model reads first first."""
    if (result.get("period") or {}).get("kind") == QUARTER:
        return _split(result, rule)
    return {READ_FILE: encode(result)}


# ---------------------------------------------------------------- write

def stage_files(stage: Path) -> List[Path]:
    """The read files present in ``stage``: the index first, then the parts, then ``read.json``."""
    if not stage.is_dir():
        return []
    parts = sorted(p for p in stage.iterdir() if _PART_RE.match(p.name))
    return [p for p in (stage / INDEX_FILE,) if p.exists()] + parts + [
        p for p in (stage / READ_FILE,) if p.exists()]


def write(stage: Path, files: Dict[str, str]) -> List[Path]:
    """Clear the stage's read files (index first), write the parts, the index last; paths in ``files`` order."""
    stage.mkdir(parents=True, exist_ok=True)
    for path in stage_files(stage):
        path.unlink()
    for name in sorted(files, key=lambda n: n == INDEX_FILE):
        atomic_write_text(stage / name, files[name])
    return [stage / name for name in files]


# ---------------------------------------------------------------- load

def _object(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise ReadFilesInvalid(f"{path.name} unreadable") from None
    except ValueError:
        raise ReadFilesInvalid(f"{path.name} is not JSON") from None
    if not isinstance(data, dict):
        raise ReadFilesInvalid(f"{path.name} is not an object")
    return data


def _part_names(index: dict) -> List[str]:
    names = index.pop(PARTS_KEY, None)
    if not isinstance(names, list) or not names:
        raise ReadFilesInvalid("read-index.json has no part list")
    if not all(isinstance(n, str) and _PART_RE.match(n) for n in names):
        raise ReadFilesInvalid("read-index.json names a part that is not read-YYYY-MM.json")
    return names


def _join(stage: Path, index: dict) -> dict:
    result = index
    for name in _part_names(index):
        if not (stage / name).is_file():
            raise ReadFilesInvalid(f"{name} is listed but missing")
        part = _object(stage / name)
        if part.pop(MONTH_KEY, None) != _PART_RE.match(name).group(1):
            raise ReadFilesInvalid(f"{name} holds another month")
        for key in SPLIT_KEYS:
            if key in part:
                if not isinstance(part[key], list):
                    raise ReadFilesInvalid(f"{name} {key} is not a list")
                result.setdefault(key, []).extend(part[key])
    return result


def load(stage: Path) -> dict:
    """The one result of the stage's read files; ``ReadFilesMissing`` / ``ReadFilesInvalid``."""
    index_path, single = stage / INDEX_FILE, stage / READ_FILE
    if index_path.exists() and single.exists():
        raise ReadFilesInvalid("read.json and read-index.json both present")
    if index_path.exists():
        return _join(stage, _object(index_path))
    if single.exists():
        return _object(single)
    raise ReadFilesMissing(f"no read file in {stage.name}")

#!/usr/bin/env python3
# version: 0.1.0
"""test_review_read_parts.py — the read*.json layout of lib/review_read_parts.py (spec 046 T3.4; ADR-7;
SDD Quality Requirements "no read*.json part above 256 KB").

Mechanisms each test falsifies:
- a week and a month are one compact read.json (a split for every kind fails);
- a quarter is read-index.json (period, report, sections, part list, the
  dateless lists) plus one read-<YYYY-MM>.json per month, all three months
  even when one is empty;
- the assignment rule per key: days by date, monthly by its month, weekly by
  the majority month of its in-quarter days under the configured week rule
  (an ISO-only rebuild fails the rule test), ties to the earlier month;
- every file <= 256,000 bytes on both shapes of the 2026-Q1 fixture scaled to
  the measured bytes (tests/review_scaled_quarter.py);
- the loader joins the parts back into a result equal to the unsplit one;
- writing clears the other layout and parts of another quarter, index first,
  and writes the index last (a failed part write leaves no index);
- the loader refuses: no file (missing), both layouts, a listed part that is
  missing / not JSON / of another month, an unsafe part name, a bad part list.

All data is synthetic.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from review_scaled_quarter import SHAPES, scaled_quarter  # noqa: E402
from lib import review_read_parts as rp  # noqa: E402
from lib.period import ISO, WeekRule  # noqa: E402

PART_LIMIT = 256_000           # the conservative reading of the Read tool's 256 KB
MONTHS = ["2026-01", "2026-02", "2026-03"]
PARTS = [f"read-{m}.json" for m in MONTHS]
SPLIT_KEYS = ("days", "weekly", "monthly")


def _small_quarter() -> dict:
    """A quarter result with an empty February, a definitions list and every split key."""
    return {
        "period": {"kind": "quarter", "name": "2026-Q1", "start": "2026-01-01", "end": "2026-03-31"},
        "days": [{"date": "2026-01-02", "text": "a"}, {"date": "2026-03-31", "text": "b"}],
        "weekly": [{"week": "2026-W01", "path": "W/2026-W01.md"}, {"week": "2026-W05", "path": "W/2026-W05.md"},
                   {"week": "2026-W09", "path": "W/2026-W09.md"}, {"week": "2026-W14", "path": "W/2026-W14.md"}],
        "monthly": [{"month": "2026-03", "path": "M/2026-03.md"}],
        "only_in_monthly_links": ["Only-Monthly"], "dailies_not_in_monthly": [],
        "open_tasks": [{"text": "open", "done": False}], "growth": {"created": []}, "not_read": [],
        "report": {"monthly_status": "found"}, "sections": [{"key": "s1", "heading": "Wins"}],
    }


def _month_result(kind: str = "month") -> dict:
    return {"period": {"kind": kind, "name": "2026-03", "start": "2026-03-01", "end": "2026-03-31"},
            "days": [{"date": "2026-03-01"}], "weekly": [], "report": {}, "not_read": []}


def _parts(files: dict) -> dict:
    return {name: json.loads(text) for name, text in files.items()}


# ---------------------------------------------------------------- layout

@pytest.mark.parametrize("kind", ["week", "month"])
def test_a_week_and_a_month_are_one_compact_read_json(kind):
    result = _month_result(kind)
    files = rp.files_of(result, ISO)
    assert list(files) == ["read.json"]
    assert files["read.json"] == json.dumps(result, ensure_ascii=True, separators=(",", ":")) + "\n"


def test_a_quarter_is_an_index_and_one_part_per_month_in_order():
    files = _parts(rp.files_of(_small_quarter(), ISO))
    assert list(files) == ["read-index.json", *PARTS]
    index = files["read-index.json"]
    assert index["parts"] == PARTS
    assert set(index) == {"period", "report", "sections", "parts", "open_tasks", "growth", "not_read",
                          "only_in_monthly_links", "dailies_not_in_monthly"}
    for name, month in zip(PARTS, MONTHS):
        assert set(files[name]) == {"month", *SPLIT_KEYS} and files[name]["month"] == month
    assert files["read-2026-02.json"]["days"] == [] and files["read-2026-02.json"]["monthly"] == [], \
        "an empty month still has its part"


def test_each_entry_goes_to_the_month_it_belongs_to():
    files = _parts(rp.files_of(_small_quarter(), ISO))
    jan, feb, mar = (files[n] for n in PARTS)
    assert [d["date"] for d in jan["days"]] == ["2026-01-02"] and [d["date"] for d in mar["days"]] == ["2026-03-31"]
    assert [m["month"] for m in mar["monthly"]] == ["2026-03"]
    # W01 (Dec 29 - Jan 4, clipped to Jan 1-4), W05 (Jan 26 - Feb 1: six days January),
    # W09 (Feb 23 - Mar 1: six days February), W14 (Mar 30 - Apr 5, clipped to Mar 30-31)
    assert [w["week"] for w in jan["weekly"]] == ["2026-W01", "2026-W05"]
    assert [w["week"] for w in feb["weekly"]] == ["2026-W09"]
    assert [w["week"] for w in mar["weekly"]] == ["2026-W14"]


def test_a_weekly_note_is_placed_by_its_days_under_the_configured_week_rule():
    # RED when the week is rebuilt under ISO: ISO 2026-W05 is Jan 26 - Feb 1 (January),
    # under a Sunday rule with full first weeks it is Feb 1 - 7 (February)
    sunday_full = WeekRule(first_day=6, min_days_in_first_week=7)
    result = _small_quarter()
    result["weekly"] = [{"week": "2026-W05", "path": "W/2026-W05.md"}]
    assert [w["week"] for w in _parts(rp.files_of(result, ISO))["read-2026-01.json"]["weekly"]] == ["2026-W05"]
    assert [w["week"] for w in _parts(rp.files_of(result, sunday_full))["read-2026-02.json"]["weekly"]] == \
        ["2026-W05"]


def test_a_tie_goes_to_the_earlier_month():
    from datetime import date
    days = [date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 2)]
    assert rp.majority_month(days) == "2026-01"
    assert rp.majority_month(days[1:]) == "2026-02"


# ---------------------------------------------------------------- the measured shape

def _sizes(stage: Path) -> dict:
    return {p.name: p.stat().st_size for p in sorted(stage.iterdir())}


@pytest.mark.parametrize("shape", SHAPES)
def test_every_part_fits_the_read_limit_on_the_measured_shape(tmp_path, shape):
    # RED when the quarter is one file (710,106 bytes); the shape names which side carries the non-day bytes
    # (tests/review_scaled_quarter.py)
    result = scaled_quarter(shape)
    rp.write(tmp_path, rp.files_of(result, ISO))
    sizes = _sizes(tmp_path)
    print(shape, sizes)
    assert set(sizes) == {"read-index.json", *PARTS}
    assert all(size <= PART_LIMIT for size in sizes.values()), sizes


@pytest.mark.parametrize("shape", SHAPES)
def test_the_loader_joins_the_parts_into_the_unsplit_result(tmp_path, shape):
    result = scaled_quarter(shape)
    rp.write(tmp_path, rp.files_of(copy.deepcopy(result), ISO))
    assert rp.load(tmp_path) == result


@pytest.mark.parametrize("result", [_small_quarter(), _month_result("month"), _month_result("week")])
def test_the_loader_returns_what_was_written_for_every_kind(tmp_path, result):
    rp.write(tmp_path, rp.files_of(result, ISO))
    assert rp.load(tmp_path) == result


# ---------------------------------------------------------------- stale files

def _stale(stage: Path, *names: str) -> None:
    stage.mkdir(parents=True, exist_ok=True)
    for name in names:
        (stage / name).write_text('{"stale":true}\n', encoding="utf-8")


def test_a_quarter_write_removes_an_unsplit_read_json_and_other_quarters_parts(tmp_path):
    _stale(tmp_path, "read.json", "read-2025-12.json", "proposals.json", "meta.json")
    written = rp.write(tmp_path, rp.files_of(_small_quarter(), ISO))
    assert [p.name for p in written] == ["read-index.json", *PARTS]
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(["read-index.json", *PARTS, "proposals.json",
                                                                 "meta.json"])
    assert rp.load(tmp_path) == _small_quarter()


def test_a_month_write_removes_a_quarters_index_and_parts(tmp_path):
    rp.write(tmp_path, rp.files_of(_small_quarter(), ISO))
    rp.write(tmp_path, rp.files_of(_month_result(), ISO))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["read.json"]
    assert rp.load(tmp_path) == _month_result()


def test_a_failed_part_write_leaves_no_index(tmp_path, monkeypatch):
    rp.write(tmp_path, rp.files_of(_small_quarter(), ISO))           # an index from an earlier run
    real = rp.atomic_write_text

    def failing(path, text):
        if Path(path).name == "read-2026-02.json":
            raise OSError("disk full")
        real(path, text)

    monkeypatch.setattr(rp, "atomic_write_text", failing)
    with pytest.raises(OSError):
        rp.write(tmp_path, rp.files_of(_small_quarter(), ISO))
    assert not (tmp_path / "read-index.json").exists(), "an index lists only parts of its own run"
    with pytest.raises(rp.ReadFilesMissing):
        rp.load(tmp_path)


def test_stage_files_lists_only_the_read_files(tmp_path):
    _stale(tmp_path, "read.json", "read-index.json", "read-2026-01.json", "read-notes.json", "proposals.json")
    assert [p.name for p in rp.stage_files(tmp_path)] == ["read-index.json", "read-2026-01.json", "read.json"]


# ---------------------------------------------------------------- the loader refuses

def test_no_read_file_is_missing(tmp_path):
    with pytest.raises(rp.ReadFilesMissing):
        rp.load(tmp_path)
    with pytest.raises(rp.ReadFilesMissing):
        rp.load(tmp_path / "absent")


def _quarter_on_disk(stage: Path) -> None:
    rp.write(stage, rp.files_of(_small_quarter(), ISO))


def _edit_index(stage: Path, edit) -> None:
    path = stage / "read-index.json"
    index = json.loads(path.read_text(encoding="utf-8"))
    edit(index)
    path.write_text(json.dumps(index), encoding="utf-8")


@pytest.mark.parametrize("break_it", [
    lambda s: (s / "read.json").write_text("{}", encoding="utf-8"),                 # both layouts
    lambda s: (s / "read-2026-02.json").unlink(),                                    # a listed part missing
    lambda s: (s / "read-2026-02.json").write_text("{not json", encoding="utf-8"),
    lambda s: (s / "read-2026-02.json").write_text("[]", encoding="utf-8"),          # not an object
    lambda s: (s / "read-2026-02.json").write_text('{"month":"2026-01","days":[]}', encoding="utf-8"),
    lambda s: (s / "read-2026-02.json").write_text('{"month":"2026-02","days":{}}', encoding="utf-8"),
    lambda s: _edit_index(s, lambda i: i.update(parts=["../read-2026-01.json"])),    # unsafe name
    lambda s: _edit_index(s, lambda i: i.update(parts="read-2026-01.json")),         # not a list
    lambda s: _edit_index(s, lambda i: i.pop("parts")),
    lambda s: (s / "read-index.json").write_text("[]", encoding="utf-8"),
])
def test_a_broken_split_read_is_invalid(tmp_path, break_it):
    _quarter_on_disk(tmp_path)
    break_it(tmp_path)
    with pytest.raises(rp.ReadFilesInvalid):
        rp.load(tmp_path)


@pytest.mark.parametrize("text", ["{not json", "[]"])
def test_a_broken_read_json_is_invalid(tmp_path, text):
    (tmp_path / "read.json").write_text(text, encoding="utf-8")
    with pytest.raises(rp.ReadFilesInvalid):
        rp.load(tmp_path)

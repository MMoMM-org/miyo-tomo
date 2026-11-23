#!/usr/bin/env python3
# version: 0.1.0
"""test_review_stage.py — the stage a /review read rests in (lib/review_stage.py; spec 047 T2.3;
PRD F1-AC2, F2-AC3, F6-AC5, F7-AC1; SDD ADR-1, ADR-2, ADR-3, ADR-10, "Data Storage Changes").

Mechanisms each test falsifies:
- write leaves days/<date>.json for every day (empty days too), growth/<date>.json per creation day
  (entries {path, links} sorted by path, parts at entry boundaries over the ceiling), children/,
  context.json, weeks.json and manifest.json LAST (a write that dies before it leaves a stage load
  refuses as missing);
- every agent-read file is indent=1 UTF-8 with long texts as line arrays, ≤ 32,768 B and no line
  over 2,000 characters on the scaled 2026-Q1 fixture;
- an oversized day is re-cut through review_day.cut_at_boundary (≤ 3 tries, then the hard cut on
  the first section alone, every limit ≥ 1) and named partly_read; a child note over the ceiling
  is clipped at a heading boundary; context lists overflow into parts;
- load gives back what review_read_parts.load gave for the same read (month and quarter), plus
  previous / condensed / carryover; a quarter day file is the week read's day file (F1-AC2);
  context.json holds the link differences, per-day fields (F2-AC3) and growth counts only; load
  rebuilds growth.created; every created note sits in the growth file of its creation day;
  the read report is only in manifest.json;
- load refuses a stale file (read_id) and a pre-047 stage (missing);
- sections_digest is stable and follows a mapping row; can_continue needs layout, period, kind
  and digest equal;
- discard keeps only meta.json and payloads.json (F7-AC1); a new read discards first (F6-AC5).

All data is synthetic.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from review_cli_contract import load_script  # noqa: E402
from review_period_fixtures import (  # noqa: E402
    MARCH, MOCS, W13, growth_vault, month_sources, month_vault, quarter_sources, quarter_vault, run, week_sources,
)
from review_scaled_quarter import SHAPES, scaled_quarter  # noqa: E402
from lib import review_day  # noqa: E402
from lib import review_period  # noqa: E402
from lib import review_read_parts as rp  # noqa: E402
from lib import review_stage as rs  # noqa: E402
from lib.period import ISO, Period  # noqa: E402

CEILING = 32_768
LINE_MAX = 2_000
Q1 = Period.quarter(2026, 1)
AGENT_DIRS = ("days", "growth", "children", "previous")
DEFINITION = {"key": "s1", "heading": "Wins", "level": 2, "parent": None, "description": "what went well",
              "keywords": ["win"], "groups": ["done"], "cap": 5}


def _pdict(period: Period) -> dict:
    return {"kind": period.kind, "name": period.name, "start": period.start.isoformat(),
            "end": period.end.isoformat()}


def _day(day: str, **kw) -> dict:
    entry = {"date": day, "dailies": [], "sections": {"Daily Log": "a line"}, "fields": {}, "partly_read": False,
             "has_content": True, "links": [], "problems": [], "tasks": [], "linked": []}
    entry.update(kw)
    return entry


def _result(period: Period = W13, days=None, **extra) -> dict:
    result = {"period": _pdict(period),
              "days": days if days is not None else [_day(d.isoformat()) for d in period.days()],
              "open_tasks": [], "growth": {"created": [], "mocs_changed": [], "mocs_linked_by_new": []},
              "report": {"days": []}, "not_read": []}
    result.update(extra)
    return result


def _write(stage: Path, result: dict, **kw) -> dict:
    kw.setdefault("stem", stage.name)
    kw.setdefault("rule", ISO)
    kw.setdefault("sections_digest", "none")
    return rs.write(stage, result, **kw)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _agent_files(stage: Path):
    files = [p for d in AGENT_DIRS if (stage / d).is_dir() for p in sorted((stage / d).iterdir())]
    return files + sorted(stage.glob("context*.json")) + [stage / "weeks.json"]


def _without(loaded: dict) -> dict:
    out = dict(loaded)
    for key in ("previous", "condensed", "carryover"):
        out.pop(key)
    return out


def _old_load(tmp_path: Path, result: dict) -> dict:
    old = tmp_path / "old"
    rp.write(old, rp.files_of(result, ISO))
    return rp.load(old)


# ---------------------------------------------------------------- the files

def test_write_leaves_a_day_file_for_every_day_and_growth_per_creation_day(tmp_path):
    result = run(growth_vault(), W13, week_sources(moc_folders=[MOCS]))
    stage = tmp_path / "2026-W13-review"
    manifest = _write(stage, result)
    assert sorted(p.name for p in (stage / "days").iterdir()) == [f"{d.isoformat()}.json" for d in W13.days()]
    assert sorted(p.name for p in (stage / "growth").iterdir()) == ["2026-03-23.json", "2026-03-29.json"]
    assert _json(stage / "growth" / "2026-03-23.json")["created"] == [
        {"path": "Notes/New One.md", "links": ["Topic MOC", "Alpha"]},
        {"path": "Notes/New Two.md", "links": ["Other MOC"]}]
    for name in ("context.json", "weeks.json", "manifest.json"):
        assert (stage / name).is_file()
    assert manifest["files"]["days"] == [f"{d.isoformat()}.json" for d in W13.days()]
    assert manifest["files"]["context"] == ["context.json"] and manifest["files"]["weeks"] == "weeks.json"
    assert manifest["layout"] == 1 and manifest["period"] == _pdict(W13) and manifest["stem"] == stage.name


def test_empty_days_get_a_day_file_too(tmp_path):
    days = [_day(d.isoformat(), sections={}, has_content=False) for d in W13.days()]
    _write(tmp_path / "s", _result(days=days))
    assert len(list((tmp_path / "s" / "days").iterdir())) == 7


def test_children_get_one_file_per_entry_and_a_duplicate_a_number(tmp_path):
    result = run(month_vault(), MARCH, month_sources())
    weekly = result["weekly"]
    result["weekly"] = weekly + [dict(weekly[0], path=weekly[0]["path"] + "-dup.md", duplicate=True)]
    manifest = _write(tmp_path / "s", result)
    names = manifest["files"]["children"]
    first = weekly[0]["week"]
    assert f"weekly-{first}.json" in names and f"weekly-{first}-2.json" in names
    assert sorted(p.name for p in (tmp_path / "s" / "children").iterdir()) == sorted(names)
    assert _json(tmp_path / "s" / "children" / f"weekly-{first}.json")["clipped"] is False


def test_growth_parts_split_at_entry_boundaries_and_drop_nothing(tmp_path):
    created = [{"path": f"Notes/N{i:03d}.md", "links": ["x" * 900], "day": "2026-03-24"} for i in range(80)]
    result = _result(growth={"created": list(reversed(created)), "mocs_changed": [], "mocs_linked_by_new": []})
    manifest = _write(tmp_path / "s", result)
    names = [n for n in manifest["files"]["growth"]]
    assert names[0] == "2026-03-24.json" and len(names) > 2
    assert all(n == "2026-03-24.json" or n.startswith("2026-03-24-") for n in names)
    seen = []
    for i, name in enumerate(names):
        path = tmp_path / "s" / "growth" / name
        doc = _json(path)
        assert path.stat().st_size <= CEILING
        assert ("part" in doc) == (i > 0)
        seen += doc["created"]
    assert seen == [{"path": c["path"], "links": c["links"]} for c in created]


def test_manifest_is_written_last(tmp_path, monkeypatch):
    order = []
    real = rs.atomic_write_text
    monkeypatch.setattr(rs, "atomic_write_text", lambda path, text: (order.append(Path(path).name), real(path, text)))
    _write(tmp_path / "s", _result())
    assert order[-1] == "manifest.json" and order.count("manifest.json") == 1


def test_a_write_dying_before_the_manifest_leaves_a_stage_load_calls_missing(tmp_path, monkeypatch):
    real = rs.atomic_write_text

    def dying(path, text):
        if Path(path).name == "manifest.json":
            raise OSError("disk full")
        real(path, text)

    monkeypatch.setattr(rs, "atomic_write_text", dying)
    with pytest.raises(OSError):
        _write(tmp_path / "s", _result())
    assert (tmp_path / "s" / "days").is_dir()
    with pytest.raises(rs.StageMissing):
        rs.load(tmp_path / "s")


# ---------------------------------------------------------------- the encoding

def test_agent_files_are_indented_utf8_with_texts_as_line_arrays(tmp_path):
    day = _day("2026-03-23", sections={"Journal": "Grüße\nzweite Zeile"},
               linked=[{"path": "Note", "kind": "other", "text": "a\nb"}])
    result = _result(days=[day] + [_day(d.isoformat()) for d in W13.days()[1:]])
    _write(tmp_path / "s", result)
    path = tmp_path / "s" / "days" / "2026-03-23.json"
    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    assert text == json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    assert "Grüße" in text
    assert doc["sections"]["Journal"] == ["Grüße", "zweite Zeile"]
    assert doc["linked"][0]["text"] == ["a", "b"]
    manifest_text = (tmp_path / "s" / "manifest.json").read_text(encoding="utf-8")
    assert "\n" not in manifest_text.rstrip("\n")


def test_a_line_over_the_piece_length_becomes_pieces_that_join_back(tmp_path):
    long_line = "w" * 4_500
    day = _day("2026-03-23", sections={"Journal": f"short\n{long_line}"})
    result = _result(days=[day] + [_day(d.isoformat()) for d in W13.days()[1:]])
    _write(tmp_path / "s", result)
    text = (tmp_path / "s" / "days" / "2026-03-23.json").read_text(encoding="utf-8")
    assert max(len(line) for line in text.splitlines()) <= LINE_MAX
    assert rs.load(tmp_path / "s")["days"][0]["sections"]["Journal"] == f"short\n{long_line}"


@pytest.mark.parametrize("shape", SHAPES)
def test_indented_files_stay_under_the_ceiling(tmp_path, shape):
    result = scaled_quarter(shape)
    stage = tmp_path / "2026-Q1-review"
    _write(stage, result)
    files = _agent_files(stage)
    assert len(files) > 90
    for path in files:
        assert path.stat().st_size <= CEILING, f"{path.name}: {path.stat().st_size} bytes"
    if shape == "children-heavy":
        # index-heavy pads single link targets and task texts to 2-3 KB: not texts, never line-broken
        for path in files:
            longest = max(len(line) for line in path.read_text(encoding="utf-8").splitlines())
            assert longest <= LINE_MAX, f"{path.name}: a line of {longest} characters"


# ---------------------------------------------------------------- the cuts

def _sections(count: int, chars: int) -> dict:
    line = "word " * 9 + "word"
    return {f"S{i}": "\n".join([line] * (chars // (len(line) + 1))) for i in range(count)}


def _counting(monkeypatch):
    calls = []
    real = review_day.cut_at_boundary

    def wrapper(units, max_chars):
        calls.append((list(units), max_chars))
        return real(units, max_chars)

    monkeypatch.setattr(review_day, "cut_at_boundary", wrapper)
    return calls


def _one_day_stage(tmp_path, day: dict) -> Path:
    result = _result(days=[day] + [_day(d.isoformat()) for d in W13.days()[1:]])
    _write(tmp_path / "s", result)
    return tmp_path / "s" / "days" / "2026-03-23.json"


def test_an_oversized_day_is_recut_at_a_section_boundary_and_partly_read(tmp_path, monkeypatch):
    calls = _counting(monkeypatch)
    sections = _sections(10, 5_000)
    path = _one_day_stage(tmp_path, _day("2026-03-23", sections=sections))
    doc = _json(path)
    assert path.stat().st_size <= CEILING
    assert doc["partly_read"] is True
    kept = list(doc["sections"])
    assert kept and kept == list(sections)[:len(kept)] and len(kept) < 10
    assert all("\n".join(doc["sections"][k]) == sections[k] for k in kept)
    assert 1 <= len(calls) <= 3 and all(limit >= 1 for _, limit in calls)


def test_a_day_that_three_recuts_cannot_fit_gets_the_hard_cut(tmp_path, monkeypatch):
    calls = _counting(monkeypatch)
    tasks = [{"text": "t" * 400, "done": False, "done_date": None, "source": "x"} for _ in range(100)]
    path = _one_day_stage(tmp_path, _day("2026-03-23", sections=_sections(4, 3_000), tasks=tasks))
    doc = _json(path)
    assert len(calls) == 4
    units, limit = calls[-1]
    assert len(units) == 1 and units[0][0] == review_day.SECTION_UNIT and units[0][1] == "S0"
    assert all(limit >= 1 for _, limit in calls)
    assert doc["partly_read"] is True and list(doc["sections"]) in ([], ["S0"])


def test_a_single_huge_section_is_cut_hard_inside_the_ceiling(tmp_path):
    text = "x" * 60_000
    path = _one_day_stage(tmp_path, _day("2026-03-23", sections={"Journal": text}))
    doc = _json(path)
    assert path.stat().st_size <= CEILING and doc["partly_read"] is True
    joined = rs.load(tmp_path / "s")["days"][0]["sections"]["Journal"]
    assert joined and text.startswith(joined)


def test_a_child_note_over_the_ceiling_is_clipped_at_a_heading_boundary(tmp_path):
    result = run(month_vault(), MARCH, month_sources())
    big = result["weekly"][0]
    big["day_blocks"] = {f"2026-03-{d:02d}": "block line\n" * 600 for d in range(2, 9)}
    original = copy.deepcopy(big)
    _write(tmp_path / "s", result)
    path = tmp_path / "s" / "children" / f"weekly-{big['week']}.json"
    doc = _json(path)
    assert path.stat().st_size <= CEILING and doc["clipped"] is True
    loaded = rs.load(tmp_path / "s")["weekly"][0]
    kept = list(loaded["day_blocks"])
    assert 0 < len(kept) < 7 and kept == list(original["day_blocks"])[:len(kept)]
    assert all(loaded["day_blocks"][k] == original["day_blocks"][k] for k in kept)
    assert loaded["clipped"] is True


def test_context_lists_overflow_into_parts_that_join_back(tmp_path):
    tasks = [{"text": f"open task {i} " + "y" * 300, "done": False, "source": "T.md"} for i in range(300)]
    result = _result(open_tasks=tasks, dailies_not_in_weekly=[f"Link {i}" for i in range(2_000)])
    manifest = _write(tmp_path / "s", result)
    names = manifest["files"]["context"]
    assert names[0] == "context.json" and len(names) > 2
    assert _json(tmp_path / "s" / "context.json")["parts"] == names[1:]
    for name in names:
        assert (tmp_path / "s" / name).stat().st_size <= CEILING
    loaded = rs.load(tmp_path / "s")
    assert loaded["open_tasks"] == tasks and loaded["dailies_not_in_weekly"] == result["dailies_not_in_weekly"]


# ---------------------------------------------------------------- the loader

@pytest.mark.parametrize("case", ["month", "quarter"])
def test_load_gives_back_what_the_read_parts_loader_gave(tmp_path, case):
    if case == "month":
        result = run(month_vault(), MARCH, month_sources())
    else:
        result = run(quarter_vault(), Q1, quarter_sources())
    result["sections"] = [DEFINITION]
    expected = _old_load(tmp_path, result)
    _write(tmp_path / "new", result)
    loaded = rs.load(tmp_path / "new")
    assert _without(loaded) == expected
    assert loaded["previous"] == [] and loaded["condensed"] is None and loaded["carryover"] is None


def test_load_gives_back_the_scaled_quarter(tmp_path):
    result = scaled_quarter("children-heavy")
    _write(tmp_path / "new", result)
    assert _without(rs.load(tmp_path / "new")) == _old_load(tmp_path, result) | {
        "growth": dict(result["growth"], created=[dict(c, day="2026-01-01") for c in result["growth"]["created"]])}


def test_a_quarter_day_file_holds_the_week_reads_day_entry(tmp_path):
    vault_q, vault_w = quarter_vault(), quarter_vault()
    _write(tmp_path / "q", run(vault_q, Q1, quarter_sources()))
    _write(tmp_path / "w", run(vault_w, Period.week(2026, 7), quarter_sources()))
    quarter_day = _json(tmp_path / "q" / "days" / "2026-02-10.json")
    week_day = _json(tmp_path / "w" / "days" / "2026-02-10.json")
    quarter_day.pop("read_id"), week_day.pop("read_id")
    assert quarter_day == week_day and quarter_day["has_content"] is True


def test_context_holds_link_differences_fields_and_growth_counts_only(tmp_path):
    result = run(month_vault(), MARCH, month_sources())
    result["sections"] = [DEFINITION]
    _write(tmp_path / "s", result)
    context = _json(tmp_path / "s" / "context.json")
    assert context["only_in_weekly_links"] == result["only_in_weekly_links"]
    assert context["dailies_not_in_weekly"] == result["dailies_not_in_weekly"]
    assert context["fields"] == {d["date"]: d["fields"] for d in result["days"] if d["fields"]}
    assert context["fields"]
    assert context["sections"] == [DEFINITION] and context["period"] == _pdict(MARCH)
    assert set(context["growth"]) == {"created_count", "mocs_changed", "mocs_linked_by_new"}
    assert context["growth"]["created_count"] == len(result["growth"]["created"])
    for key in ("days", "weekly", "report", "not_read"):
        assert key not in context


def test_load_rebuilds_growth_created_from_the_growth_files(tmp_path):
    result = run(growth_vault(), W13, week_sources(moc_folders=[MOCS]))
    _write(tmp_path / "s", result)
    loaded = rs.load(tmp_path / "s")
    assert loaded["growth"] == json.loads(json.dumps(result["growth"]))
    assert loaded["growth"]["created"]


def test_growth_goes_to_the_day_it_was_created(tmp_path):
    result = run(growth_vault(), W13, week_sources(moc_folders=[MOCS]))
    days = {c["path"]: c["day"] for c in result["growth"]["created"]}
    assert days == {"Notes/New One.md": "2026-03-23", "Notes/New Two.md": "2026-03-23",
                    "Notes/Edge.md": "2026-03-29"}
    result["growth"]["created"].append({"path": "Notes/Undated.md", "links": []})
    _write(tmp_path / "s", result)
    homes = {}
    for path in (tmp_path / "s" / "growth").iterdir():
        doc = _json(path)
        for entry in doc["created"]:
            assert entry["path"] not in homes
            homes[entry["path"]] = doc["date"]
    assert homes == dict(days, **{"Notes/Undated.md": "2026-03-23"})


def test_the_created_day_is_the_local_day_of_kados_created_or_the_first_day():
    start_ms, end_ms = review_period.period_bounds_ms(W13)
    assert review_period.created_day(start_ms, W13) == "2026-03-23"
    assert review_period.created_day(end_ms, W13) == "2026-03-29"
    assert review_period.created_day(start_ms + 3 * 86_400_000, W13) == "2026-03-26"
    for unusable in (None, "x", True, 0, -1, 10 ** 20):
        assert review_period.created_day(unusable, W13) == "2026-03-23"


def test_no_agent_file_holds_the_read_report(tmp_path):
    result = run(month_vault(), MARCH, month_sources())
    result["report"]["marker"] = "REPORT-ONLY-MARKER"
    _write(tmp_path / "s", result)
    for path in _agent_files(tmp_path / "s"):
        assert "REPORT-ONLY-MARKER" not in path.read_text(encoding="utf-8"), path.name
    assert "REPORT-ONLY-MARKER" in (tmp_path / "s" / "manifest.json").read_text(encoding="utf-8")
    assert rs.load(tmp_path / "s")["report"]["marker"] == "REPORT-ONLY-MARKER"


def test_weeks_json_names_the_files_and_the_weekly_note_of_each_unit(tmp_path):
    result = run(month_vault(), MARCH, month_sources())
    result["growth"]["created"] = [{"path": "Notes/A.md", "links": [], "day": "2026-03-10"}]
    _write(tmp_path / "s", result)
    weeks = _json(tmp_path / "s" / "weeks.json")
    assert weeks["rule"] == {"first_day": 0, "min_days_in_first_week": 4}
    assert weeks["budget_bytes"] == 81_920 and weeks["digest_cap_bytes"] == 8_192
    weekly = {w["week"] for w in result["weekly"]}
    covered = []
    for unit in weeks["units"]:
        assert unit["day_files"] == [f"{d}.json" for d in unit["days"]]
        size = sum((tmp_path / "s" / "days" / n).stat().st_size for n in unit["day_files"])
        size += sum((tmp_path / "s" / "growth" / n).stat().st_size for n in unit["growth_files"])
        assert unit["bytes"] == size
        assert unit["weekly_note"] == (f"weekly-{unit['week']}.json" if unit["week"] in weekly else None)
        covered += unit["days"]
    assert covered == [d.isoformat() for d in MARCH.days()]
    unit_10 = next(u for u in weeks["units"] if "2026-03-10" in u["days"])
    assert unit_10["growth_files"] == ["2026-03-10.json"] and unit_10["takes_part"] is True


@pytest.mark.parametrize("target", ["days/2026-03-24.json", "growth/2026-03-23.json", "context.json", "weeks.json",
                                    "condensed.json"])
def test_load_refuses_a_file_of_another_read(tmp_path, target):
    result = run(growth_vault(), W13, week_sources(moc_folders=[MOCS]))
    stage = tmp_path / "s"
    _write(stage, result)
    path = stage / target
    doc = _json(path) if path.exists() else {"units": {}, "carryover": {"state": "none"}}
    doc["read_id"] = "another-read"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(rs.StageStale):
        rs.load(stage)


def test_load_refuses_a_stale_child_file(tmp_path):
    _write(tmp_path / "s", run(month_vault(), MARCH, month_sources()))
    path = next((tmp_path / "s" / "children").iterdir())
    doc = _json(path)
    doc["read_id"] = "another-read"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(rs.StageStale):
        rs.load(tmp_path / "s")


def test_load_reads_a_condensed_file_of_this_read(tmp_path):
    manifest = _write(tmp_path / "s", _result())
    condensed = {"read_id": manifest["read_id"], "units": {}, "carryover": {"state": "none", "attempts": 0}}
    (tmp_path / "s" / "condensed.json").write_text(json.dumps(condensed), encoding="utf-8")
    loaded = rs.load(tmp_path / "s")
    assert loaded["condensed"] == condensed and loaded["carryover"] is None


@pytest.mark.parametrize("legacy", [None, "read.json", "read-index.json"])
def test_load_refuses_a_stage_without_a_manifest_as_missing(tmp_path, legacy):
    stage = tmp_path / "s"
    stage.mkdir()
    if legacy:
        (stage / legacy).write_text("{}\n", encoding="utf-8")
    with pytest.raises(rs.StageMissing):
        rs.load(stage)


def test_load_refuses_an_unsafe_file_name_in_the_manifest(tmp_path):
    _write(tmp_path / "s", _result())
    manifest = _json(tmp_path / "s" / "manifest.json")
    manifest["files"]["days"][0] = "../../x.json"
    (tmp_path / "s" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(rs.StageInvalid):
        rs.load(tmp_path / "s")


# ---------------------------------------------------------------- continue and the digest

def _definitions(**change):
    mod = load_script("review-read.py")
    row = {"id": "s1", "heading": "Wins", "level": 2, "parent": None, "description": "what went well",
           "keywords": ["win"], "groups": ["done"], "cap": 5, "placement": "end"}
    row.update(change)
    other = {"id": "s2", "heading": "Mood", "level": 2, "parent": None, "description": "mood over the month",
             "keywords": [], "groups": [], "cap": 3, "placement": "review"}
    return mod.section_definitions(SimpleNamespace(sections=[row, other]))


def test_sections_digest_is_stable_and_follows_a_mapping_row():
    first = rs.sections_digest(_definitions())
    assert first.startswith("sha256:") and first == rs.sections_digest(_definitions())
    assert rs.sections_digest([dict(reversed(list(d.items()))) for d in _definitions()]) == first
    assert rs.sections_digest(_definitions(cap=6)) != first
    assert rs.sections_digest(_definitions(heading="Big wins")) != first
    assert rs.sections_digest([]) == rs.sections_digest(None) == "none"


def test_can_continue_only_when_layout_period_kind_and_digest_match(tmp_path):
    stage = tmp_path / "s"
    assert rs.can_continue(stage, W13, "none") is False
    _write(stage, _result(), sections_digest="sha256:abc")
    assert rs.can_continue(stage, W13, "sha256:abc") is True
    assert rs.can_continue(stage, W13, "sha256:other") is False
    assert rs.can_continue(stage, Period.week(2026, 12), "sha256:abc") is False
    assert rs.can_continue(stage, MARCH, "sha256:abc") is False
    manifest = _json(stage / "manifest.json")
    (stage / "manifest.json").write_text(json.dumps(dict(manifest, layout=0)), encoding="utf-8")
    assert rs.can_continue(stage, W13, "sha256:abc") is False
    (stage / "manifest.json").write_text("not json", encoding="utf-8")
    assert rs.can_continue(stage, W13, "sha256:abc") is False


# ---------------------------------------------------------------- discard

def _litter(stage: Path) -> None:
    for name in ("digests/2026-W13.json", "previous/week-2026-W12.json", "carryover.json", "proposals.json",
                 "condensed.json", "read.json", "read-index.json", "read-2026-01.json", "context-2.json",
                 "meta.json", "payloads.json", "days/2025-01-01.json"):
        (stage / name).parent.mkdir(parents=True, exist_ok=True)
        (stage / name).write_text("{}\n", encoding="utf-8")


def test_discard_leaves_only_meta_and_payloads(tmp_path):
    stage = tmp_path / "s"
    _write(stage, run(growth_vault(), W13, week_sources(moc_folders=[MOCS])))
    _litter(stage)
    rs.discard(stage)
    assert sorted(p.name for p in stage.iterdir()) == ["meta.json", "payloads.json"]
    rs.discard(tmp_path / "absent")


def test_a_new_read_discards_all_earlier_material_first(tmp_path):
    stage = tmp_path / "s"
    stage.mkdir()
    _litter(stage)
    manifest = _write(stage, _result())
    for gone in ("digests", "previous", "carryover.json", "proposals.json", "condensed.json", "read.json",
                 "read-index.json", "read-2026-01.json", "context-2.json", "days/2025-01-01.json"):
        assert not (stage / gone).exists(), gone
    assert (stage / "meta.json").exists() and (stage / "payloads.json").exists()
    assert rs.load(stage)["period"] == _pdict(W13)
    assert all(_json(p)["read_id"] == manifest["read_id"] for p in _agent_files(stage))

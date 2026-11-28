#!/usr/bin/env python3
# version: 0.5.1
"""test_review_read.py — Behavioural tests for review-read.py (spec 045 T3.4, T3.8;
PRD F3-AC8..F3-AC13; SDD Internal API Changes, Error Handling).

On tests/review_fake_vault with the fixtures of tests/review_period_fixtures
and the real lib.review_day readers:
- a week and a month run print the per-day report (dailies with their
  states, duplicates, linked notes read / missing / failed), the day after,
  task notes, weekly status, calls, retried, waited_s, not_read, kado_empty
  and advice; read.json is written under tomo-tmp/review/<stem>/ and carries
  the period, the days and the report; stdout carries no daily text
- injected 429s: retried > 0 and advice raise-kado-limit; a note that still
  fails in the end pass is in not_read and marked failed
- the daily folder listing still in not_read after the end pass: status
  stopped, advice raise-kado-limit, nothing written
- a listing the end pass recovered: every read after it is sent at 2 s
- no daily with content: nothing_to_review true, advice check-key-access,
  no read.json; an empty daily listing says the same with kado_empty
- Kado unreachable / auth: status stopped with error.kind, nothing written
- no stopped output (dailies-not-read, kado-unreachable) carries the
  nothing_to_review key: a stop says the period was not read, the flag
  would say it was read and found empty
- one KadoClient per run, built once, its counters are the report's
- setup missing / invalid, daily folder not configured: stopped with problems
- exit 2 for a bad invocation (including --stem ".", "", whitespace or a
  path mark), exit 1 with the class name only on an unexpected exception
- a week stays <= 45 calls and a month <= 170 without retries (the SDD's
  Quality Requirement, Performance; owner decision 2026-11-12)
- spec 046 T3.3: the stored read carries `sections` (the SectionDefinition fields,
  key = row id, analysis rows included) only with a mapping; without a mapping
  the loaded month equals the T3.1 golden recording; a mapped month's read
  equals the unmapped one's once `sections` is popped; `--kind quarter --period
  2026-Q1` reads the quarter
- spec 047 T2.4 (the stage, lib/review_stage): a new read prints continued false,
  read_id, read_at, stage, units and the report, never read_path / read_parts;
  the manifest is compact, a day file indent=1; days/ holds only the period's
  days and the day after gives only its yesterday fields (F1-AC6); an unchanged
  stored read continues with no Kado call, the stored report and the first
  read_at (F6-AC4); --fresh, a changed mapping, an invalid manifest or a stale
  file discard it (discarded fresh | sections-changed | stage-invalid) and a
  pre-047 stage is discarded without the key; every stop and nothing_to_review
  writes nothing and leaves nothing to continue, --fresh before a stop too
  (F2-AC5); missing weekly / monthly notes are none-found with an empty level;
  --measure prints the bytes of every stage file (growth/ included), the unit
  bytes (day + growth files), over_ceiling and over_budget and writes no file;
  the scaled 2026-Q1 read loads back as read_period returned it; a stamped
  weeks.json without its units is a stage-invalid discard, not exit 1
- spec 047 walk F-R5-2: after review-doc.py discard the period is read anew
  (continued false, Kado called), never continued on the old read

All data is synthetic.
"""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "review-read.py"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault  # noqa: E402
from review_period_fixtures import (  # noqa: E402
    DAILY,
    MOCS,
    PLANNER,
    TASK_NOTE,
    READERS,
    SETTINGS,
    WEEKLY,
    daily,
    growth_vault,
    month_sources,
    month_vault,
    quarter_vault,
    week_vault,
)
from lib.kado_client import _MAX_RETRIES, KadoAuthError, KadoConnectionError  # noqa: E402
from lib.review_pacer import ADVICE_RAISE_LIMIT, MAX_INTERVAL_S  # noqa: E402
from lib.review_period import ADVICE_CHECK_ACCESS  # noqa: E402
from lib.review_weeks import UNIT_BUDGET  # noqa: E402
from lib.review_period import read_period as real_read_period  # noqa: E402
from lib import review_stage as rs  # noqa: E402
from review_scaled_quarter import SHAPES, scaled_quarter  # noqa: E402

TODAY = "2026-11-11"
MONTHLY = "Calendar/303 Monthly/"
QUARTERLY = "Calendar/304 Quarterly/"
MARKER = "BODY-MARKER-7f3a private journal line"
GOLDEN_DIR = TESTS_DIR / "fixtures" / "046-t3-1-period-read-golden"
PACER_COUNTERS = ("calls", "retried", "waited_s")
W13_STEM = "2026-W13_review"


# ---------------------------------------------------------------- harness

@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("review_read_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _config(instance: Path, *, review: dict | None = None, daily_path: str | None = DAILY,
            naming: dict | None = None) -> None:
    granularities: dict = {"weekly": {"enabled": True, "path": WEEKLY}, "monthly": {"enabled": True, "path": MONTHLY}}
    if daily_path is not None:
        granularities["daily"] = {"enabled": True, "path": daily_path}
    cfg: dict = {
        "concepts": {"inbox": "100 Inbox/", "calendar": {"granularities": granularities},
                     "map_note": {"paths": [MOCS]}},
        "naming": {"calendar_patterns": naming if naming is not None
                   else {"daily": "YYYY-MM-DD", "weekly": "GGGG-[W]WW", "monthly": "YYYY-MM"}},
    }
    if review is None:
        review = {
            "language": "en",
            "week": {"first_day": "monday", "min_days_in_first_week": 4},
            "daily": {"sections": [], "skip_sections": [], "task_notes": [TASK_NOTE], "max_chars_per_day": 12000},
            "weekly": {"heading": "Tomo Review", "place": {"anchor": "In my own words", "placement": "before"},
                       "own_sections": ["In my own words", "Reflections"]},
            "monthly": {"heading": "Tomo Review", "place": {"anchor": "Reflections", "placement": "inside"},
                        "own_sections": ["Reflections"]},
        }
    cfg["review"] = review
    (instance / "config" / "vault-config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
    _config(tmp_path)
    return tmp_path


def _run(mod, monkeypatch, capsys, argv, fake):
    monkeypatch.setattr(mod, "KadoClient", fake)
    code = mod.main(["--profiles-dir", "profiles", "--today", TODAY] + argv)
    out, err = capsys.readouterr()
    assert MARKER not in out and MARKER not in err, "daily text leaked to stdout/stderr"
    return code, (json.loads(out) if out else None), err


def _week(mod, monkeypatch, capsys, fake, *extra):
    return _run(mod, monkeypatch, capsys, ["--period", "2026-W13", "--kind", "week", *extra], fake)


def _month(mod, monkeypatch, capsys, fake, *extra):
    return _run(mod, monkeypatch, capsys, ["--period", "2026-03", "--kind", "month", *extra], fake)


def _stage(instance: Path, stem: str = W13_STEM) -> Path:
    return instance / "tomo-tmp" / "review" / stem


def _manifest(instance: Path, stem: str = W13_STEM) -> Path:
    return _stage(instance, stem) / "manifest.json"


def _loaded(instance: Path, stem: str = W13_STEM) -> dict:
    """The stored read as review-doc.py loads it, without the keys later phases fill."""
    read = rs.load(_stage(instance, stem))
    for key in ("previous", "condensed", "carryover"):
        read.pop(key)
    return read


def day_of(out: dict, day: str) -> dict:
    return next(d for d in out["report"]["days"] if d["date"] == day)


def _week_with_links() -> ReviewFakeVault:
    """The W13 fixture plus a same-day planner link, a missing same-day note and a duplicated daily."""
    wed_path, wed_text = daily(date(2026, 3, 25), f"Wednesday {MARKER}\n[[DP-2026-03-25|Dayplanner]]\nSleep:: 7")
    thu_path, thu_text = daily(date(2026, 3, 26), "Thursday [[Missing-2026-03-26]]")
    dup_path, dup_text = daily(date(2026, 3, 24), "Tuesday flat copy")
    return week_vault(**{wed_path: wed_text, thu_path: thu_text, dup_path: dup_text})


# ---------------------------------------------------------------- the week report

def test_a_week_run_prints_the_per_day_report_and_writes_read_json(mod, instance, monkeypatch, capsys):
    fake = _week_with_links()
    code, out, err = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and err == ""
    assert out["status"] == "ok" and out["stem"] == W13_STEM and out["nothing_to_review"] is False
    assert out["period"] == {"kind": "week", "name": "2026-W13", "start": "2026-03-23", "end": "2026-03-29"}
    report = out["report"]
    assert [d["date"] for d in report["days"]] == [f"2026-03-{n}" for n in range(23, 30)]
    assert day_of(out, "2026-03-23")["dailies"] == [{"path": f"{DAILY}2026-03-23.md", "state": "found"}]
    assert day_of(out, "2026-03-23")["duplicate"] is False
    tue = day_of(out, "2026-03-24")
    assert tue["duplicate"] is True
    assert sorted(d["path"] for d in tue["dailies"]) == [f"{DAILY}2026-03-24.md", f"{DAILY}2026/2026-03-24.md"]
    assert day_of(out, "2026-03-25")["linked"] == [
        {"name": "DP-2026-03-25", "path": f"{PLANNER}DP-2026-03-25.md", "state": "read"}]
    assert day_of(out, "2026-03-26")["linked"] == [{"name": "Missing-2026-03-26", "path": None, "state": "missing"}]
    assert day_of(out, "2026-03-28")["dailies"] == [], "no daily on Saturday"
    assert report["day_after"] == {"date": "2026-03-30", "dailies": [{"path": f"{DAILY}2026-03-30.md", "state": "read"}]}
    assert report["task_notes"] == [{"path": TASK_NOTE, "state": "read"}]
    assert report["growth"]["moc_folders"] == 1
    assert report["calls"] == fake.call_count and report["retried"] == 0
    assert report["waited_s"] == round(fake.retry_wait_s + fake.pace_wait_s, 1)
    assert report["not_read"] == [] and report["kado_empty"] == [] and report["advice"] == []
    assert "weekly_status" not in report
    assert out["continued"] is False and "discarded" not in out
    assert out["stage"] == f"tomo-tmp/review/{W13_STEM}" and out["units"] == 1
    assert "read_path" not in out and "read_parts" not in out, "spec 047 removed the read files' keys"
    manifest = json.loads(_manifest(instance).read_text(encoding="utf-8"))
    assert out["read_id"] == manifest["read_id"] and out["read_at"] == manifest["read_at"]
    read = _loaded(instance)
    assert read["period"] == out["period"]
    assert len(read["days"]) == 7 and read["not_read"] == []
    assert read["report"] == report, "the manifest carries the printed report"
    assert any(MARKER in json.dumps(e) for e in read["days"]), "the content rests in the stage"
    assert "sections" not in json.dumps(report) and "fields" not in json.dumps(report)


def test_a_month_run_reports_the_weekly_notes_and_stays_within_the_call_budget(mod, instance, monkeypatch, capsys):
    fake = month_vault()
    code, out, _ = _month(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok" and out["stem"] == "2026-03_review"
    report = out["report"]
    assert len(report["days"]) == 31
    assert report["weekly_status"] == "found"
    assert {w["path"] for w in report["weekly_notes"] if w["path"]} == {f"{WEEKLY}2026/2026-W09.md", f"{WEEKLY}2026-W13.md"}
    assert all(w["state"] == "read" for w in report["weekly_notes"] if w["path"])
    assert report["calls"] == fake.call_count <= 170, fake.events
    read = _loaded(instance, "2026-03_review")
    assert [w["week"] for w in read["weekly"]] == ["2026-W09", "2026-W13"]
    # F3-AC5: the links only a weekly note carries (no daily links them; the periodic notes' own names do not
    # count) and the links of a day's block that the weekly of its week lacks, in document and day order
    assert read["only_in_weekly_links"] == ["Thought Note", "Own Note", "Delta", "Epsilon"]
    assert read["dailies_not_in_weekly"] == ["Only Daily", "Omega", "Beta"]
    # the weekly's blocks of days outside the month (W09's 2026-02-28) are dropped, their links with them
    assert [sorted(w["day_blocks"]) for w in read["weekly"]] == [["2026-03-01"], ["2026-03-23", "2026-03-29"]]
    assert "Feb Note" not in read["weekly"][0]["links"] and "Feb Note" not in read["only_in_weekly_links"]


def test_a_week_run_reports_what_the_week_grew(mod, instance, monkeypatch, capsys):
    """F3-AC7 through the script: the printed counts and the stored read's lists name the notes created in the week,
    the MOCs changed in it and the MOCs the new notes link to."""
    code, out, _ = _week(mod, monkeypatch, capsys, growth_vault())
    assert code == 0 and out["status"] == "ok"
    assert out["report"]["growth"] == {"created": 3, "mocs_changed": 2, "mocs_linked_by_new": 2,
                                       "moc_folders": 1, "kado_none": []}
    growth = _loaded(instance)["growth"]
    assert [c["path"] for c in growth["created"]] == ["Notes/Edge.md", "Notes/New One.md", "Notes/New Two.md"]
    assert growth["mocs_changed"] == [f"{MOCS}Other MOC.md", f"{MOCS}Quiet MOC.md"]
    assert growth["mocs_linked_by_new"] == [f"{MOCS}Other MOC.md", f"{MOCS}Topic MOC.md"]


def test_a_week_stays_within_forty_five_calls_without_retries(mod, instance, monkeypatch, capsys):
    fake = _week_with_links()
    _, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert out["report"]["retried"] == 0
    assert out["report"]["calls"] == fake.call_count <= 45, fake.events


def test_one_client_per_run_built_once_before_the_first_call_under_one_pacer(mod, instance, monkeypatch, capsys):
    fake = week_vault()
    built = []

    def factory():
        built.append(fake.call_count)
        return fake

    code, out, _ = _run(mod, monkeypatch, capsys, ["--period", "2026-W13", "--kind", "week"], factory)
    assert code == 0 and built == [0], "one client, built before any call"
    assert out["report"]["calls"] == fake.call_count
    assert fake.min_interval == 0.0, "the pacer restored the client's interval at the end"
    assert fake.attempt_gate is None
    assert all(s["interval"] == 0.3 for s in fake.sends), "every send of the run was paced"


# ---------------------------------------------------------------- rate limits

def test_injected_429s_give_retried_waited_and_the_advice(mod, instance, monkeypatch, capsys):
    fake = week_vault()
    fake.rate_limit(f"{DAILY}2026-03-23.md", failures=2)
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok"
    report = out["report"]
    assert report["retried"] == 2 and report["waited_s"] > 0
    assert report["advice"] == [ADVICE_RAISE_LIMIT]
    assert report["not_read"] == []
    assert _manifest(instance).exists()


def test_a_note_that_still_fails_in_the_end_pass_is_not_read_and_marked_failed(mod, instance, monkeypatch, capsys):
    fake = week_vault()
    path = f"{DAILY}2026-03-23.md"
    fake.rate_limit(path)
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok"
    assert out["report"]["not_read"] == [path]
    assert day_of(out, "2026-03-23")["dailies"] == [{"path": path, "state": "failed"}]
    assert out["report"]["advice"] == [ADVICE_RAISE_LIMIT]
    assert _loaded(instance)["not_read"] == [path]


def test_the_daily_listing_still_not_read_after_the_end_pass_stops_the_run_and_writes_nothing(
        mod, instance, monkeypatch, capsys):
    # RED when the stop is removed: a review without its dailies would be built from seven empty days
    fake = week_vault()
    fake.rate_limit(DAILY)
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0
    assert out["status"] == "stopped" and out["problems"] == ["dailies-not-read"]
    assert out["report"]["not_read"] == [DAILY]
    assert ADVICE_RAISE_LIMIT in out["report"]["advice"]
    assert "stage" not in out and "read_id" not in out
    assert not (instance / "tomo-tmp").exists()


def test_reads_after_a_listing_recovered_by_the_end_pass_are_sent_at_the_widest_interval(
        mod, instance, monkeypatch, capsys):
    # RED when ReviewPacer.finish() restores the interval: the dailies would be sent at 0 s on a full window
    fake = week_vault()
    fake.rate_limit(DAILY, failures=_MAX_RETRIES + 1)
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok" and out["report"]["not_read"] == []
    assert day_of(out, "2026-03-23")["dailies"] == [{"path": f"{DAILY}2026-03-23.md", "state": "found"}]
    end_pass = max(i for i, s in enumerate(fake.sends) if s["path"] == DAILY)
    after = fake.sends[end_pass + 1:]
    assert len(after) >= 7, "the period's dailies are read after the end pass"
    assert all(s["interval"] == MAX_INTERVAL_S for s in after), [s["interval"] for s in after]
    assert fake.min_interval == 0.0, "restored once the run is over"
    assert _manifest(instance).exists()


# ---------------------------------------------------------------- nothing to review

def test_no_daily_with_content_is_nothing_to_review_without_the_access_hint_and_no_file(
        mod, instance, monkeypatch, capsys):
    # RED when the nothing_to_review check is removed: a stage would be written for an empty week.
    # RED while the script appends check-key-access on nothing_to_review: Kado listed every daily (Phase 6 live walk)
    files = dict(daily(date(2026, 3, 23 + i), "") for i in range(7))
    fake = ReviewFakeVault({**files, TASK_NOTE: "- [ ] open\n"}, folders=[DAILY, WEEKLY, MOCS])
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok"
    assert out["nothing_to_review"] is True
    assert out["report"]["advice"] == []
    assert out["report"]["kado_empty"] == []
    assert all(d["dailies"] == [{"path": f"{DAILY}{d['date']}.md", "state": "empty"}] for d in out["report"]["days"])
    assert "stage" not in out and "read_id" not in out
    assert not (instance / "tomo-tmp").exists()


def test_a_week_without_dailies_in_a_folder_that_holds_other_dates_gets_no_access_hint(mod, instance, monkeypatch,
                                                                                       capsys):
    """Phase 6 live walk: the test vault's dailies end 2026-09-12; a later week got `check-key-access` although Kado
    listed the folder. The listing answered with notes, none of the period: nothing to review, no advice."""
    files = dict(daily(date(2026, 3, 2 + i), f"march {i}") for i in range(7))              # 2026-W10, not W13
    fake = ReviewFakeVault({**files, TASK_NOTE: "- [ ] open\n"}, folders=[DAILY, WEEKLY, MOCS])
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok" and out["nothing_to_review"] is True
    assert all(d["dailies"] == [] for d in out["report"]["days"]) and len(out["report"]["days"]) == 7
    assert out["report"]["kado_empty"] == [] and out["report"]["advice"] == []
    assert "stage" not in out and not (instance / "tomo-tmp").exists()


def test_an_empty_daily_listing_is_nothing_to_review_and_kado_empty(mod, instance, monkeypatch, capsys):
    fake = ReviewFakeVault({TASK_NOTE: "- [ ] open\n"}, folders=[DAILY, WEEKLY, MOCS])
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok" and out["nothing_to_review"] is True
    assert out["report"]["kado_empty"] == ["dailies"]
    assert out["report"]["advice"] == [ADVICE_CHECK_ACCESS]
    assert "stage" not in out and not (instance / "tomo-tmp").exists()


# ---------------------------------------------------------------- Kado stops

def test_kado_unreachable_stops_the_run_and_writes_nothing(mod, instance, monkeypatch, capsys):
    fake = week_vault()
    fake.connection_error = KadoConnectionError("down")
    code, out, err = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and err == ""
    assert out == {"status": "stopped", "stem": W13_STEM, "error": {"kind": "kado-unreachable", "detail": "down"}}
    assert not (instance / "tomo-tmp").exists()


def test_a_refused_key_stops_the_run_as_kado_auth(mod, instance, monkeypatch, capsys):
    fake = week_vault()
    fake.auth_error = KadoAuthError("401")
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "stopped" and out["error"]["kind"] == "kado-auth"
    assert not (instance / "tomo-tmp").exists()


def test_a_client_that_cannot_be_built_is_kado_unreachable(mod, instance, monkeypatch, capsys):
    def factory():
        raise KadoConnectionError("no .mcp.json")

    code, out, _ = _run(mod, monkeypatch, capsys, ["--period", "2026-W13", "--kind", "week"], factory)
    assert code == 0 and out["status"] == "stopped" and out["error"]["kind"] == "kado-unreachable"


def _stop_dailies_not_read(fake: ReviewFakeVault) -> None:
    fake.rate_limit(DAILY)


def _stop_kado_unreachable(fake: ReviewFakeVault) -> None:
    fake.connection_error = KadoConnectionError("down")


@pytest.mark.parametrize("arrange, expected", [
    (_stop_dailies_not_read, {"problems": ["dailies-not-read"]}),
    (_stop_kado_unreachable, {"error": {"kind": "kado-unreachable", "detail": "down"}}),
])
def test_a_stopped_output_never_carries_nothing_to_review(mod, instance, monkeypatch, capsys, arrange, expected):
    # RED (dailies-not-read) when the flag is computed before the not-read stop: seven never-read days
    # look like an empty period, and a consumer keying on the flag would say "check key access"
    fake = week_vault()
    arrange(fake)
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "stopped"
    assert all(out[key] == value for key, value in expected.items())
    assert "nothing_to_review" not in out, out
    assert not (instance / "tomo-tmp").exists()


# ---------------------------------------------------------------- setup and arguments

def test_a_missing_setup_stops_without_a_call(mod, instance, monkeypatch, capsys):
    _config(instance, review={"language": "en"})
    fake = week_vault()
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "stopped" and out["problems"] == ["setup-missing"]
    assert fake.call_count == 0 and not (instance / "tomo-tmp").exists()


def test_an_invalid_setup_stops_with_its_pointers(mod, instance, monkeypatch, capsys):
    _config(instance, review={"language": "en", "weekly": {"heading": "Tomo Review"}})
    fake = week_vault()
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "stopped" and out["problems"] == ["setup-invalid"]
    assert "/review/weekly/place/anchor" in out["errors"]
    assert fake.call_count == 0


def test_a_daily_folder_nobody_names_stops_before_any_call(mod, instance, monkeypatch, capsys):
    _config(instance, daily_path=None)
    fake = week_vault()
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "stopped" and out["problems"] == ["daily-not-configured"]
    assert fake.call_count == 0


def test_the_period_is_resolved_under_the_configured_week_rule(mod, instance, monkeypatch, capsys):
    review = {
        "language": "en", "week": {"first_day": "sunday", "min_days_in_first_week": 1},
        "daily": {"sections": [], "skip_sections": [], "task_notes": [], "max_chars_per_day": 12000},
        "weekly": {"heading": "Tomo Review", "place": {"anchor": "In my own words", "placement": "before"},
                   "own_sections": []},
    }
    _config(instance, review=review, naming={"daily": "YYYY-MM-DD", "weekly": "gggg-[W]ww", "monthly": "YYYY-MM"})
    fake = week_vault()
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok"
    assert out["period"]["start"] == "2026-03-22" and out["period"]["end"] == "2026-03-28"


def test_a_given_stem_names_the_stage_folder(mod, instance, monkeypatch, capsys):
    code, out, _ = _week(mod, monkeypatch, capsys, week_vault(), "--stem", "custom_review")
    assert code == 0 and out["stem"] == "custom_review"
    assert out["stage"] == "tomo-tmp/review/custom_review"
    assert _manifest(instance, "custom_review").exists()


@pytest.mark.parametrize("argv", [
    ["--kind", "week"],
    ["--period", "2026-W13"],
    ["--period", "2026-W13", "--kind", "year"],
    ["--period", "2026-Q5", "--kind", "quarter"],
    ["--period", "2026-03", "--kind", "quarter"],
    ["--period", "2026-03", "--kind", "week"],
    ["--period", "2026-W13", "--kind", "month"],
    ["--period", "2026-W60", "--kind", "week"],
    ["--period", "2026-W13", "--kind", "week", "--stem", "../x"],
    ["--period", "2026-W13", "--kind", "week", "--stem", "a/b"],
    ["--period", "2026-W13", "--kind", "week", "--stem", "a\\b"],
    ["--period", "2026-W13", "--kind", "week", "--stem", ".."],
    ["--period", "2026-W13", "--kind", "week", "--stem", "."],       # Path(tmp) / "." is the review folder itself
    ["--period", "2026-W13", "--kind", "week", "--stem", ""],
    ["--period", "2026-W13", "--kind", "week", "--stem", "  "],
])
def test_a_bad_invocation_exits_2(mod, instance, monkeypatch, capsys, argv):
    _quarter_setup(instance)                    # a quarter name that does not fit is judged once a setup exists
    with pytest.raises(SystemExit) as exc:
        _run(mod, monkeypatch, capsys, argv, week_vault())
    assert exc.value.code == 2


def test_an_unexpected_exception_prints_only_the_class_name(mod, instance, monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise RuntimeError(MARKER)

    monkeypatch.setattr(mod, "read_period", boom)
    code, out, err = _week(mod, monkeypatch, capsys, week_vault())
    assert code == 1 and out is None
    assert err == "RuntimeError\n"
    assert not (instance / "tomo-tmp").exists()


# ---------------------------------------------------------------- spec 046 T3.3: definitions, compact, quarter, measure

TEMPLATE = "t_weekly_test.md"
ROWS = [
    {"id": "s1", "heading": "Wins", "level": 2, "parent": None, "occurrence": 1,
     "description": "What went well this week", "keywords": ["win"], "groups": ["done"], "placement": "under",
     "cap": 5},
    {"id": "s7", "heading": "Patterns", "level": 3, "parent": "Reflections", "occurrence": 2,
     "description": "Recurring themes across days", "placement": "review"},
]


def _edit_config(instance: Path, edit) -> None:
    path = instance / "config" / "vault-config.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(cfg)
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")


def _map_week(instance: Path, rows=ROWS) -> None:
    def edit(cfg):
        cfg["templates"] = {"mapping": {"weekly": TEMPLATE}}
        cfg["review"]["weekly"]["sections"] = {TEMPLATE: rows}
    _edit_config(instance, edit)


def _compact(data) -> str:
    return json.dumps(data, ensure_ascii=True, separators=(",", ":")) + "\n"


def test_a_mapped_week_carries_the_section_definitions_keyed_by_row_id(mod, instance, monkeypatch, capsys):
    """F1-AC1: the definitions reach the model in the stage (context.json); key = the row id, the SectionDefinition fields only,
    defaults filled, the analysis row (placement review) included and alone marked analysis (046 T4.4), the
    rows' order kept."""
    _map_week(instance)
    code, out, _ = _week(mod, monkeypatch, capsys, week_vault())
    assert code == 0 and out["status"] == "ok"
    read = _loaded(instance)
    assert read["sections"] == [
        {"key": "s1", "heading": "Wins", "level": 2, "parent": None, "description": "What went well this week",
         "keywords": ["win"], "groups": ["done"], "cap": 5},
        {"key": "s7", "heading": "Patterns", "level": 3, "parent": "Reflections",
         "description": "Recurring themes across days", "keywords": [], "groups": [], "cap": 8, "analysis": True},
    ]
    assert "sections" not in out and "sections" not in out["report"], "definitions are for the model's file only"


@pytest.mark.parametrize("arrange", [
    lambda instance: None,                                                     # no template configured
    lambda instance: _edit_config(instance, lambda c: c.update(templates={"mapping": {"weekly": TEMPLATE}})),
])
def test_without_a_mapping_the_stage_has_no_sections_key(mod, instance, monkeypatch, capsys, arrange):
    # RED when the key is always written: an empty list would change the spec 045 shape (CON-2)
    arrange(instance)
    code, out, _ = _week(mod, monkeypatch, capsys, week_vault())
    assert code == 0 and out["status"] == "ok"
    assert "sections" not in _loaded(instance)
    assert "sections" not in json.loads((_stage(instance) / "context.json").read_text(encoding="utf-8"))


def _map_month(instance: Path) -> None:
    def edit(cfg):
        cfg["templates"] = {"mapping": {"monthly": TEMPLATE}}
        cfg["review"]["monthly"]["sections"] = {TEMPLATE: ROWS}
    _edit_config(instance, edit)


def _month_read(mod, instance, monkeypatch, capsys) -> dict:
    code, out, _ = _month(mod, monkeypatch, capsys, month_vault())
    assert code == 0 and out["status"] == "ok"
    return _loaded(instance, "2026-03_review")


def test_a_mapped_month_reads_the_same_notes_days_and_weekly_entries_as_an_unmapped_one(mod, instance, monkeypatch,
                                                                                       capsys):
    """F1-AC1 / CON-2: the mapping only adds the definitions; the same vault read with and without it gives the
    same stored read once `sections` is taken out — no day, note or weekly entry is dropped or added."""
    unmapped = _month_read(mod, instance, monkeypatch, capsys)
    _map_month(instance)
    mapped = _month_read(mod, instance, monkeypatch, capsys)
    assert "sections" not in unmapped
    assert [s["key"] for s in mapped.pop("sections")] == ["s1", "s7"]
    assert unmapped["days"] and unmapped["weekly"], "the comparison covers days and weekly entries"
    assert mapped == unmapped


def test_the_manifest_is_compact_and_the_agent_files_line_broken(mod, instance, monkeypatch, capsys):
    """ADR-2: manifest.json is script-only and compact; a day file is indent=1 UTF-8 for the agents."""
    _map_week(instance)
    _week(mod, monkeypatch, capsys, week_vault())
    text = _manifest(instance).read_text(encoding="utf-8")
    assert text == _compact(json.loads(text)), "separators (',', ':'), ASCII-escaped, one trailing newline"
    day = (_stage(instance) / "days" / "2026-03-23.json").read_text(encoding="utf-8")
    assert day == json.dumps(json.loads(day), indent=1, ensure_ascii=False) + "\n"


def _golden_read(golden_sources):
    def read(period, sources, settings, client, pacer):
        return real_read_period(period, golden_sources, SETTINGS, client, pacer, readers=READERS)
    return read


def _without_growth_day(read: dict) -> dict:
    """The stored read with the creation day the stage keeps per created note (spec 047 T1.5) taken out."""
    read["growth"]["created"] = [{k: v for k, v in c.items() if k != "day"} for c in read["growth"]["created"]]
    return read


def test_without_a_mapping_the_month_read_equals_the_golden(mod, instance, monkeypatch, capsys):
    """CON-2 difference pinned: the T3.1 recording of the unmapped month, read through the script and loaded back
    from the stage, is the golden (plus the pacing counters the script always merged into the report)."""
    monkeypatch.setattr(mod, "read_period", _golden_read(month_sources()))
    code, out, _ = _month(mod, monkeypatch, capsys, month_vault())
    assert code == 0 and out["status"] == "ok"
    read = _without_growth_day(_loaded(instance, "2026-03_review"))
    for key in PACER_COUNTERS:
        assert read["report"].pop(key) == out["report"][key]
    # spec 047 T3.2: the report's previous rows postdate the golden (month_sources() sets up no previous kind)
    assert [r["state"] for r in read["report"].pop("previous")] == ["not-set-up", "not-set-up"]
    golden = json.loads((GOLDEN_DIR / "month.json").read_text(encoding="utf-8"))
    assert read == golden


def _quarter_setup(instance: Path) -> None:
    def edit(cfg):
        cfg["concepts"]["calendar"]["granularities"]["quarterly"] = {"enabled": True, "path": QUARTERLY}
        cfg["naming"]["calendar_patterns"]["quarterly"] = "YYYY-[Q]Q"
        cfg["review"]["quarterly"] = {"heading": "Tomo Review", "place": {"anchor": "Conclusions",
                                                                         "placement": "before"},
                                      "own_sections": []}
        cfg["review"]["monthly"]["own_sections"] = ["Highlights"]     # the fixture's monthly note's own section
    _edit_config(instance, edit)


def test_a_quarter_run_reads_the_quarter_and_marks_against_the_monthly_notes(mod, instance, monkeypatch, capsys):
    # RED while --kind is limited to week and month: argparse exits 2 on --kind quarter
    _quarter_setup(instance)
    code, out, _ = _run(mod, monkeypatch, capsys, ["--period", "2026-Q1", "--kind", "quarter"], quarter_vault())
    assert code == 0 and out["status"] == "ok" and out["stem"] == "2026-Q1_review"
    assert out["period"] == {"kind": "quarter", "name": "2026-Q1", "start": "2026-01-01", "end": "2026-03-31"}
    report = out["report"]
    assert len(report["days"]) == 90
    assert report["monthly_status"] == "found"
    assert [m["path"] for m in report["monthly_notes"] if m["path"]] == [f"{MONTHLY}2026-02.md"]
    read = _loaded(instance, "2026-Q1_review")
    assert {"monthly", "only_in_monthly_links", "dailies_not_in_monthly", "weekly"} <= set(read)
    assert "Only-Monthly" in read["only_in_monthly_links"]


# ---------------------------------------------------------------- spec 047 T2.4: --measure on the stage

MEASURE_KEYS = {"calls", "retried", "waited_s", "not_read", "bytes", "units", "over_ceiling", "over_budget"}


def _stage_bytes(stage: Path) -> dict:
    return {str(p.relative_to(stage)): p.stat().st_size for p in sorted(stage.rglob("*")) if p.is_file()}


def _written_then_measured(mod, instance, monkeypatch, capsys, argv, vault, stem):
    """The bytes of every stage file of a normal run and its weeks.json, then the --measure run of the same read
    (the stage removed in between)."""
    code, _, _ = _run(mod, monkeypatch, capsys, argv, vault())
    assert code == 0
    stage = _stage(instance, stem)
    written = _stage_bytes(stage)
    weeks = json.loads((stage / "weeks.json").read_text(encoding="utf-8"))
    shutil.rmtree(stage)
    code, out, err = _run(mod, monkeypatch, capsys, [*argv, "--measure"], vault())
    assert code == 0 and err == "" and out["status"] == "ok"
    assert not stage.exists(), "--measure writes no file"
    return written, weeks, out


def test_measure_writes_no_file_and_prints_the_bytes_of_every_stage_file(mod, instance, monkeypatch, capsys):
    """ADR-2, CON-3: --measure is the same read without a stage; the printed bytes are what each stage file would
    hold (read_id and read_at keep their length); the privacy assertion of _run covers stdout and stderr."""
    _map_week(instance)
    written, weeks, out = _written_then_measured(mod, instance, monkeypatch, capsys,
                                                 ["--period", "2026-W13", "--kind", "week"], growth_vault, W13_STEM)
    assert set(out) == {"status", "stem", "period", "nothing_to_review", "measure"}
    measure = out["measure"]
    assert set(measure) == MEASURE_KEYS
    assert measure["retried"] == 0 and measure["not_read"] == 0
    assert measure["bytes"] == written
    assert any(name.startswith("growth/") for name in measure["bytes"]), "growth files are measured"
    assert measure["units"] == [{"unit": u["unit"], "bytes": u["bytes"]} for u in weeks["units"]]
    assert measure["over_ceiling"] == [] and measure["over_budget"] == []


def test_measure_of_a_week_unit_counts_its_day_and_growth_files(mod, instance, monkeypatch, capsys):
    # RED when a unit's bytes leave out the growth files: the week weighs its day files alone
    written, _, out = _written_then_measured(mod, instance, monkeypatch, capsys,
                                             ["--period", "2026-W13", "--kind", "week"], growth_vault, W13_STEM)
    expected = sum(n for name, n in written.items() if name.startswith(("days/", "growth/")))
    assert out["measure"]["units"] == [{"unit": "2026-W13", "bytes": expected}]


def test_measure_of_a_quarter_names_its_units(mod, instance, monkeypatch, capsys):
    _quarter_setup(instance)
    written, weeks, out = _written_then_measured(mod, instance, monkeypatch, capsys,
                                                 ["--period", "2026-Q1", "--kind", "quarter"], quarter_vault,
                                                 "2026-Q1_review")
    measure = out["measure"]
    assert measure["bytes"] == written
    assert [u["unit"] for u in measure["units"]] == [u["unit"] for u in weeks["units"]]
    assert measure["units"][0]["unit"] == "2026-W01" and len(measure["units"]) == 14


def test_measure_names_a_file_over_the_ceiling_and_a_unit_over_the_budget(mod, instance, monkeypatch, capsys):
    """A day whose links alone (non-text content, never cut) outweigh the ceiling and the unit budget."""
    heavy = copy.deepcopy(scaled_quarter(SHAPES[0]))
    heavy["days"][10]["links"] = [f"Link {i:05d} " + "z" * 40 for i in range(3_000)]
    _quarter_setup(instance)
    monkeypatch.setattr(mod, "read_period", _scaled_read(heavy))
    code, out, _ = _quarter(mod, monkeypatch, capsys, quarter_vault(), "--measure")
    assert code == 0 and out["status"] == "ok"
    assert out["measure"]["over_ceiling"] == [f"days/{heavy['days'][10]['date']}.json"]
    heavy_units = [u["unit"] for u in out["measure"]["units"] if u["bytes"] > UNIT_BUDGET]
    assert out["measure"]["over_budget"] == heavy_units and heavy_units[0].startswith("2026-W02")
    assert len(heavy_units) == 1, "the heavy day is a unit alone, the rest of its week in another"
    assert not (instance / "tomo-tmp").exists()


# ---------------------------------------------------------------- spec 047 T2.4: the stage of a quarter

Q1_STEM = "2026-Q1_review"


def _quarter(mod, monkeypatch, capsys, fake, *extra):
    return _run(mod, monkeypatch, capsys, ["--period", "2026-Q1", "--kind", "quarter", *extra], fake)


def _scaled_read(result):
    def read(period, sources, settings, client, pacer):
        return copy.deepcopy(result)
    return read


def test_a_quarter_writes_a_day_file_per_day_and_its_child_notes(mod, instance, monkeypatch, capsys):
    _quarter_setup(instance)
    code, out, _ = _quarter(mod, monkeypatch, capsys, quarter_vault())
    assert code == 0 and out["status"] == "ok" and out["units"] == 14
    stage = _stage(instance, Q1_STEM)
    assert len(list((stage / "days").iterdir())) == 90
    assert "monthly-2026-02.json" in {p.name for p in (stage / "children").iterdir()}
    assert not list(stage.glob("read*.json"))


def test_a_pre_047_stage_is_discarded_and_read_anew(mod, instance, monkeypatch, capsys):
    # RED while a stage without a manifest is kept: an unsplit read.json would be a second, older read
    _quarter_setup(instance)
    stage = _stage(instance, Q1_STEM)
    stage.mkdir(parents=True)
    for name in ("read.json", "read-index.json", "read-2026-01.json"):
        (stage / name).write_text('{"period":{"kind":"quarter"},"days":[]}\n', encoding="utf-8")
    (stage / "meta.json").write_text("{}\n", encoding="utf-8")
    code, out, _ = _quarter(mod, monkeypatch, capsys, quarter_vault())
    assert code == 0 and out["status"] == "ok" and out["continued"] is False
    assert "discarded" not in out, "no stored read of this layout was discarded"
    assert not list(stage.glob("read*.json")) and (stage / "meta.json").exists()
    assert len(_loaded(instance, Q1_STEM)["days"]) == 90


@pytest.mark.parametrize("shape", SHAPES)
def test_on_the_measured_shape_the_stage_loads_back_what_read_period_returned(mod, instance, monkeypatch, capsys,
                                                                               shape):
    """SDD Quality Requirements: on 2026-Q1 scaled to the measured bytes the loader gives back what read_period
    returned (plus the pacing counters the script merges and the creation day of each created note)."""
    _quarter_setup(instance)
    scaled = scaled_quarter(shape)
    monkeypatch.setattr(mod, "read_period", _scaled_read(scaled))
    code, out, _ = _quarter(mod, monkeypatch, capsys, quarter_vault())
    assert code == 0 and out["status"] == "ok"
    read = _without_growth_day(_loaded(instance, Q1_STEM))
    for key in PACER_COUNTERS:
        assert read["report"].pop(key) == out["report"][key]
    assert read == scaled


# ---------------------------------------------------------------- spec 047 T2.4: continue, start over, discard

def test_continued_read_makes_no_kado_call(mod, instance, monkeypatch, capsys):
    """F6-AC4: an interrupted Pass 1 continues on the stored read — no Kado call, the stored report, the
    read_at of the first read."""
    _, first, _ = _week(mod, monkeypatch, capsys, _week_with_links())
    fake = _week_with_links()
    code, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok"
    assert fake.call_count == 0, fake.events
    assert out["continued"] is True and out["nothing_to_review"] is False
    assert out["read_id"] == first["read_id"] and out["read_at"] == first["read_at"]
    assert out["report"] == first["report"] and out["stage"] == first["stage"] and out["units"] == first["units"]
    assert "discarded" not in out


def _reread(mod, instance, monkeypatch, capsys, between, *extra):
    _, first, _ = _week(mod, monkeypatch, capsys, week_vault())
    between(instance)
    fake = week_vault()
    code, out, _ = _week(mod, monkeypatch, capsys, fake, *extra)
    assert code == 0 and out["status"] == "ok", out
    assert out["continued"] is False and fake.call_count > 0
    assert out["read_id"] != first["read_id"]
    return out


def _break_manifest(instance: Path) -> None:
    _manifest(instance).write_text("{broken", encoding="utf-8")


def _weeks_without_units(instance: Path) -> None:
    """A weeks.json of this read (its read_id stamped) that lacks its units: loads, but has nothing to count."""
    path = _stage(instance) / "weeks.json"
    weeks = json.loads(path.read_text(encoding="utf-8"))
    weeks.pop("units")
    path.write_text(json.dumps(weeks), encoding="utf-8")


def _stale_day_file(instance: Path) -> None:
    path = _stage(instance) / "days" / "2026-03-24.json"
    path.write_text(json.dumps(dict(json.loads(path.read_text(encoding="utf-8")), read_id="other")),
                    encoding="utf-8")


@pytest.mark.parametrize("between, extra, discarded", [
    (lambda instance: None, ("--fresh",), "fresh"),
    (_map_week, (), "sections-changed"),
    (_break_manifest, (), "stage-invalid"),
    (_stale_day_file, (), "stage-invalid"),
    (_weeks_without_units, (), "stage-invalid"),     # RED while the unit count is read outside the stored check
])
def test_a_stored_read_that_cannot_continue_is_discarded_and_read_anew(mod, instance, monkeypatch, capsys,
                                                                       between, extra, discarded):
    # RED while every run reads anew without saying so, or a changed mapping continues on the old definitions
    out = _reread(mod, instance, monkeypatch, capsys, between, *extra)
    assert out["discarded"] == discarded
    manifest = json.loads(_manifest(instance).read_text(encoding="utf-8"))
    assert manifest["read_id"] == out["read_id"]


def test_a_new_read_leaves_no_material_of_the_old_one(mod, instance, monkeypatch, capsys):
    _week(mod, monkeypatch, capsys, growth_vault())
    stray = _stage(instance) / "growth" / "2026-03-23.json"
    assert stray.exists()
    (_stage(instance) / "proposals.json").write_text("{}", encoding="utf-8")
    _week(mod, monkeypatch, capsys, week_vault(), "--fresh")
    assert not stray.exists() and not (_stage(instance) / "proposals.json").exists()


def test_fresh_and_a_stop_leave_nothing_to_continue(mod, instance, monkeypatch, capsys):
    """Error Handling: with --fresh the stored read is discarded first, so a stop leaves nothing to continue."""
    _week(mod, monkeypatch, capsys, week_vault())
    down = week_vault()
    down.connection_error = KadoConnectionError("down")
    _, out, _ = _week(mod, monkeypatch, capsys, down, "--fresh")
    assert out["status"] == "stopped"
    assert not _manifest(instance).exists()
    _, out, _ = _week(mod, monkeypatch, capsys, week_vault())
    assert out["continued"] is False


def _stop_kado_auth(fake: ReviewFakeVault) -> None:
    fake.auth_error = KadoAuthError("401")


def _nothing(fake: ReviewFakeVault) -> None:
    for path in [p for p in fake.files if p.startswith(DAILY)]:
        fake.files[path] = ""


@pytest.mark.parametrize("arrange, config", [
    (_stop_kado_unreachable, None), (_stop_kado_auth, None), (_stop_dailies_not_read, None), (_nothing, None),
    (lambda fake: None, {"review": {"language": "en"}}),
    (lambda fake: None, {"review": {"language": "en", "weekly": {"heading": "Tomo Review"}}}),
    (lambda fake: None, {"daily_path": None}),
])
def test_a_stop_or_nothing_to_review_writes_nothing_and_leaves_nothing_to_continue(mod, instance, monkeypatch,
                                                                                    capsys, arrange, config):
    """F2-AC5: kado-unreachable, kado-auth, dailies-not-read, nothing_to_review, setup-missing, setup-invalid and
    daily-not-configured write nothing; the next good run is a new read."""
    if config is not None:
        _config(instance, **config)
    fake = week_vault()
    arrange(fake)
    _, out, _ = _week(mod, monkeypatch, capsys, fake)
    assert out["status"] == "stopped" or out["nothing_to_review"] is True, out
    assert not (instance / "tomo-tmp").exists()
    _config(instance)
    _, out, _ = _week(mod, monkeypatch, capsys, week_vault())
    assert out["status"] == "ok" and out["continued"] is False


# ---------------------------------------------------------------- spec 047 T2.4: what the stage holds

def test_the_stage_holds_only_the_periods_days_and_the_day_after_gives_its_yesterday_fields(
        mod, instance, monkeypatch, capsys):
    """F1-AC6: days/ holds the seven days of the week, no file of the day after; from the day after only the
    fields that name the day before reach the stage (on the period's last day)."""
    def edit(cfg):
        cfg["trackers"] = {"daily_note_trackers": {"yesterday_fields": [{"name": "Sleep", "type": "number"}]}}
    _edit_config(instance, edit)
    after_path, after_text = daily(date(2026, 3, 30), f"Monday after {MARKER}-after\nSleep:: 6\nZest:: 9")
    code, out, _ = _week(mod, monkeypatch, capsys, week_vault(**{after_path: after_text}))
    assert code == 0 and out["status"] == "ok"
    stage = _stage(instance)
    assert sorted(p.name for p in (stage / "days").iterdir()) == [f"2026-03-{d}.json" for d in range(23, 30)]
    stored = "\n".join(p.read_text(encoding="utf-8") for p in stage.rglob("*.json"))
    assert f"{MARKER}-after" not in stored and "Zest" not in stored
    last = _loaded(instance)["days"][-1]
    assert last["date"] == "2026-03-29" and last["fields"].get("Sleep") == "6"


def test_a_month_without_weekly_notes_reports_none_found_and_stores_none(mod, instance, monkeypatch, capsys):
    """F2-AC5: a missing weekly note is reported as spec 045 defines (weekly_status none-found) and the stored read
    gives back an empty weekly level, not a missing one."""
    files = {p: t for p, t in month_vault().files.items() if not p.startswith(WEEKLY)}
    files[f"{WEEKLY}2025-W40.md"] = "# another year's week\n"             # the folder answers, with no week of March
    code, out, _ = _month(mod, monkeypatch, capsys, ReviewFakeVault(files, folders=[DAILY, WEEKLY, MOCS]))
    assert code == 0 and out["status"] == "ok"
    assert out["report"]["weekly_status"] == "none-found"
    assert _loaded(instance, "2026-03_review")["weekly"] == []


def test_a_quarter_without_monthly_notes_reports_none_found_and_stores_none(mod, instance, monkeypatch, capsys):
    """F2-AC5: a quarter's missing monthly notes are reported as spec 046 defines (monthly_status none-found)."""
    _quarter_setup(instance)
    vault = quarter_vault()
    files = {p: t for p, t in vault.files.items() if not p.startswith(MONTHLY)}
    files[f"{MONTHLY}2025-07.md"] = "# another year's month\n"
    code, out, _ = _quarter(mod, monkeypatch, capsys, ReviewFakeVault(files, folders=sorted(vault.folders)))
    assert code == 0 and out["status"] == "ok"
    assert out["report"]["monthly_status"] == "none-found"
    assert _loaded(instance, Q1_STEM)["monthly"] == []


# ---------------------------------------------------------------- spec 047 walk F-R5-2: a discarded review

def _discard_the_open_review(instance: Path) -> None:
    """review-doc.py discard on the stem, as the skill's Discard runs it: the stage holds the read, meta.json the
    document's path, and the document is Tomo's open review."""
    from note_fake_vault import NoteFakeVault
    doc = "100 Inbox/2026-W13 Review.md"
    (_stage(instance) / "meta.json").write_text(json.dumps({"stem": W13_STEM, "doc_path": doc}), encoding="utf-8")
    (_stage(instance) / "proposals.json").write_text("{}", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("review_doc_script_discard", SCRIPTS_DIR / "review-doc.py")
    review_doc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review_doc)
    review_doc.KadoClient = NoteFakeVault({doc: "---\ntomo:\n  doc_type: review\n  state: pending-approval\n---\n"})
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        assert review_doc.main(["discard", "--stem", W13_STEM]) == 0
    assert json.loads(printed.getvalue())["status"] == "discarded"


def test_after_a_discard_the_period_is_read_anew_not_continued(mod, instance, monkeypatch, capsys):
    # RED while review-doc.py has no discard: the stored read would continue (no Kado call, continued true)
    out = _reread(mod, instance, monkeypatch, capsys, _discard_the_open_review)
    assert "discarded" not in out                                # the stage was empty, not thrown away by the read
    assert not (_stage(instance) / "proposals.json").exists()

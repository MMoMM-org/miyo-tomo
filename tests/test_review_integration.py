#!/usr/bin/env python3
# version: 0.1.0
"""test_review_integration.py — review-read.py over Privat-Test through a live Kado
(spec 045 T6.2; PRD Assumptions; SDD Quality Requirements).

Opt-in on three counts, every test skips otherwise: ``-m integration``,
``TOMO_LIVE_KADO=1`` and a Kado that answers. The Kado URL and key come from
``KADO_URL``/``KADO_TOKEN`` or, read-only, from ``tomo-instance/.mcp.json``
(``host.docker.internal`` becomes ``127.0.0.1`` for the host). The owner runs:

    TOMO_LIVE_KADO=1 ./venv/bin/python -m pytest tests/test_review_integration.py -m integration -q

Two runs of ``review-read.py`` the way the skill drives it (one per module:
2026-W13 as a week, 2026-03 as a month) on a throw-away instance directory
with a synthetic review setup over the vault's real folders. The client is
the real ``KadoClient`` with every tool call recorded and every ``kado-write``
held back and recorded instead of sent, so the counters are the client's own
and no write can reach the vault. The tests read the stdout JSON and the
structure of ``read.json`` (paths, kinds, states, counts) and never a note's
text; no assertion message carries text either:

- every March daily is found once, under its flat path; the week's days too
- the same-day Dayplanner of every day with content is read; the planner of
  the day after the period is not requested; the day after's daily is read
  for the week and absent for the month
- the same-day 5-year-journal note is read; no earlier year of it is
  requested (no read under a year subfolder, no name query for another year)
- a month finds the weekly notes W09..W13 and reports W14 absent; a week
  requests no weekly note
- a week stays within 40 calls, a month within 140, nothing stays unread
- no write was performed

All data is the vault's own; only names reach this file.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "review-read.py"
INSTANCE_MCP_JSON = REPO_ROOT / "tomo-instance" / ".mcp.json"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.kado_client import KadoClient, KadoError, _extract_from_mcp_json  # noqa: E402

pytestmark = pytest.mark.integration

OPT_IN = "TOMO_LIVE_KADO"
TODAY = "2026-11-11"
DAILY = "Calendar/301 Daily/"
WEEKLY = "Calendar/302 Weekly/"
MONTHLY = "Calendar/303 Monthly/"
JOURNAL = "Calendar/305 5 Year Journal/"
PLANNER = "Efforts/300 Planner/"
MOCS = "Atlas/200 Maps/"
WEEK_LIMIT, MONTH_LIMIT = 40, 140

W13_DAYS = [date(2026, 3, 23) + timedelta(days=i) for i in range(7)]
MARCH_DAYS = [date(2026, 3, 1) + timedelta(days=i) for i in range(31)]
NOT_FAILED = {"found", "empty", "partly-read"}
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_JOURNAL_YEAR_RE = re.compile(r"5J-(\d{4})-")


def daily_path(day: date) -> str:
    return f"{DAILY}{day.isoformat()}.md"


def planner_path(day: date) -> str:
    return f"{PLANNER}DP-{day.isoformat()}.md"


# ---------------------------------------------------------------- the live Kado

def _live_settings() -> Optional[Tuple[str, str]]:
    """``(url, token)`` from the environment, else from the instance's .mcp.json; None without both."""
    url, token = os.environ.get("KADO_URL"), os.environ.get("KADO_TOKEN")
    if not (url and token) and INSTANCE_MCP_JSON.is_file():
        try:
            found_url, found_token = _extract_from_mcp_json(json.loads(INSTANCE_MCP_JSON.read_text(encoding="utf-8")))
        except (OSError, ValueError, AttributeError):
            found_url, found_token = None, None
        url, token = url or found_url, token or found_token
    if not (url and token):
        return None
    return url.replace("host.docker.internal", "127.0.0.1"), token


@pytest.fixture(scope="module")
def live() -> Tuple[str, str]:
    if os.environ.get(OPT_IN) != "1":
        pytest.skip(f"live Kado run is opt-in: {OPT_IN}=1 with -m integration")
    settings = _live_settings()
    if settings is None:
        pytest.skip(f"no Kado settings: KADO_URL and KADO_TOKEN, or {INSTANCE_MCP_JSON}")
    try:
        KadoClient(base_url=settings[0], token=settings[1]).list_dir("/", depth=1, limit=1)
    except KadoError as exc:
        pytest.skip(f"Kado does not answer at {settings[0]}: {type(exc).__name__}")
    return settings


class GuardedClient(KadoClient):
    """The real client with every tool call recorded and every kado-write held back."""

    def __init__(self, base_url: str, token: str):
        super().__init__(base_url=base_url, token=token)
        self.requests: List[Tuple[str, dict]] = []
        self.writes: List[dict] = []

    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        self.requests.append((tool_name, dict(arguments)))
        if tool_name == "kado-write":
            self.writes.append(dict(arguments))
            return {}
        return super()._call_tool(tool_name, arguments)


# ---------------------------------------------------------------- the instance

def _instance(root: Path) -> Path:
    """A throw-away instance: the vault's real folders under a synthetic review setup."""
    (root / "config").mkdir()
    (root / "profiles").mkdir()
    (root / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
    cfg = {
        "concepts": {
            "inbox": "100 Inbox/",
            "calendar": {"granularities": {"daily": {"enabled": True, "path": DAILY},
                                           "weekly": {"enabled": True, "path": WEEKLY},
                                           "monthly": {"enabled": True, "path": MONTHLY}}},
            "map_note": {"paths": [MOCS]},
        },
        "naming": {"calendar_patterns": {"daily": "YYYY-MM-DD", "weekly": "GGGG-[W]WW", "monthly": "YYYY-MM"}},
        "review": {
            "language": "en",
            "week": {"first_day": "monday", "min_days_in_first_week": 4},
            "daily": {"sections": [], "skip_sections": [], "task_notes": [], "max_chars_per_day": 12000},
            "weekly": {"heading": "Tomo Review", "place": {"anchor": "In my own words", "placement": "before"},
                       "own_sections": ["In my own words"]},
            "monthly": {"heading": "Tomo Review", "place": {"anchor": "Reflections", "placement": "inside"},
                        "own_sections": ["Reflections"]},
        },
    }
    (root / "config" / "vault-config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return root


def _load_script():
    spec = importlib.util.spec_from_file_location("review_read_integration_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class Run:
    out: dict
    client: "GuardedClient"
    root: Path

    @property
    def report(self) -> dict:
        return self.out["report"]

    def read_json(self) -> dict:
        return json.loads((self.root / self.out["read_path"]).read_text(encoding="utf-8"))

    def day(self, day: date) -> dict:
        return next(d for d in self.report["days"] if d["date"] == day.isoformat())

    def read_paths(self) -> List[str]:
        return [args["path"] for tool, args in self.client.requests if tool == "kado-read"]

    def name_queries(self) -> List[str]:
        return [args["query"] for tool, args in self.client.requests
                if tool == "kado-search" and args.get("operation") == "byName"]

    def requested_names(self) -> List[str]:
        """Every path read and every name searched: what the run asked Kado for."""
        return self.read_paths() + self.name_queries()


def _run_period(live: Tuple[str, str], root: Path, period: str, kind: str) -> Run:
    mod = _load_script()
    client = GuardedClient(*live)
    buffer = io.StringIO()
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(root)
        mp.setattr(mod, "KadoClient", lambda: client)
        with contextlib.redirect_stdout(buffer):
            code = mod.main(["--profiles-dir", "profiles", "--today", TODAY, "--period", period, "--kind", kind])
    assert code == 0, f"review-read.py exited {code}"
    out = json.loads(buffer.getvalue())
    assert out["status"] == "ok", {k: out.get(k) for k in ("status", "problems", "error")}
    assert out["nothing_to_review"] is False and out["read_path"], out.get("read_path")
    return Run(out, client, root)


@pytest.fixture(scope="module")
def week_run(live, tmp_path_factory) -> Run:
    return _run_period(live, _instance(tmp_path_factory.mktemp("w13")), "2026-W13", "week")


@pytest.fixture(scope="module")
def month_run(live, tmp_path_factory) -> Run:
    return _run_period(live, _instance(tmp_path_factory.mktemp("march")), "2026-03", "month")


def _planner_dates(names: List[str]) -> List[str]:
    return [m.group(0) for name in names if "DP-" in name for m in [_DATE_RE.search(name)] if m]


# ---------------------------------------------------------------- the dailies

def test_every_march_daily_is_found_once_under_its_flat_path(month_run):
    days = month_run.report["days"]
    assert [d["date"] for d in days] == [d.isoformat() for d in MARCH_DAYS]
    found = {d["date"]: [x["path"] for x in d["dailies"]] for d in days}
    missing = [d.isoformat() for d in MARCH_DAYS if found[d.isoformat()] != [daily_path(d)]]
    assert missing == [], f"days without exactly their flat daily: {missing} -> {[found[m] for m in missing]}"
    assert [d["date"] for d in days if d["duplicate"]] == []
    failed = [(d["date"], x["state"]) for d in days for x in d["dailies"] if x["state"] not in NOT_FAILED]
    assert failed == []
    read = month_run.read_json()
    assert [e["dailies"] for e in read["days"]] == [[daily_path(d)] for d in MARCH_DAYS]


def test_the_week_finds_its_seven_dailies(week_run):
    days = week_run.report["days"]
    assert [(d["date"], [x["path"] for x in d["dailies"]]) for d in days] == \
        [(d.isoformat(), [daily_path(d)]) for d in W13_DAYS]
    assert [x["state"] for d in days for x in d["dailies"] if x["state"] not in NOT_FAILED] == []


# ---------------------------------------------------------------- the planner

def test_the_same_day_dayplanner_is_read_for_every_day_with_content(week_run):
    with_content = [date.fromisoformat(d["date"]) for d in week_run.report["days"]
                    if any(x["state"] == "found" for x in d["dailies"])]
    assert with_content, "no day of 2026-W13 with content"
    not_read = [d.isoformat() for d in with_content
                if {"path": planner_path(d), "state": "read"}
                not in [{"path": item["path"], "state": item["state"]} for item in week_run.day(d)["linked"]]]
    assert not_read == [], f"days whose same-day planner is not among the read linked notes: {not_read}"
    kinds = {(e["date"], item["vault_path"]): item["kind"] for e in week_run.read_json()["days"]
             for item in e["linked"]}
    assert all(kinds.get((d.isoformat(), planner_path(d))) == "planner" for d in with_content), kinds


@pytest.mark.parametrize("run_name, period_days, after", [
    ("week_run", W13_DAYS, date(2026, 3, 30)),
    ("month_run", MARCH_DAYS, date(2026, 4, 1)),
])
def test_the_planner_of_the_day_after_is_not_requested(request, run_name, period_days, after):
    run: Run = request.getfixturevalue(run_name)
    allowed = {d.isoformat() for d in period_days}
    outside = sorted(set(_planner_dates(run.requested_names())) - allowed)
    assert outside == [], f"planner dates requested outside the period: {outside}"
    assert after.isoformat() not in _planner_dates(run.requested_names())
    assert run.report["day_after"]["date"] == after.isoformat()


def test_the_day_after_daily_is_read_for_the_week_and_absent_for_the_month(week_run, month_run):
    assert week_run.report["day_after"]["dailies"] == [{"path": daily_path(date(2026, 3, 30)), "state": "read"}]
    assert month_run.report["day_after"]["dailies"] == []


# ---------------------------------------------------------------- the 5-year journal

def test_the_same_day_journal_is_read_and_no_earlier_year_of_it(month_run, week_run):
    for run in (month_run, week_run):
        reads = run.read_paths()
        same_day = [p for p in reads if p.startswith(f"{JOURNAL}5J-2026-03-")]
        assert same_day, f"no same-day 5-year-journal note read among {len(reads)} reads"
        year_folders = sorted(p for p in reads if p.startswith(JOURNAL) and p[len(JOURNAL):].split("/")[0].isdigit())
        assert year_folders == [], f"journal notes read under a year subfolder: {year_folders}"
        other_years = sorted({m.group(1) for name in run.requested_names()
                              for m in [_JOURNAL_YEAR_RE.search(name)] if m and m.group(1) != "2026"})
        assert other_years == [], f"journal years requested besides 2026: {other_years}"


# ---------------------------------------------------------------- the weekly notes

def test_a_month_finds_w09_to_w13_and_reports_w14_absent(month_run):
    assert month_run.report["weekly_status"] == "found"
    assert month_run.report["weekly_notes"] == [
        *({"week": f"2026-W{n:02d}", "path": f"{WEEKLY}2026-W{n:02d}.md", "state": "read"} for n in range(9, 14)),
        {"week": "2026-W14", "path": None, "state": "absent"},
    ]
    read = month_run.read_json()
    assert [w["week"] for w in read["weekly"]] == [f"2026-W{n:02d}" for n in range(9, 14)]
    assert "only_in_weekly_links" in read and "dailies_not_in_weekly" in read


def test_a_week_requests_no_weekly_note(week_run):
    weekly_reads = [p for p in week_run.read_paths() if p.startswith(WEEKLY)]
    assert weekly_reads == [] and "weekly_notes" not in week_run.report


# ---------------------------------------------------------------- the budget and the writes

@pytest.mark.parametrize("run_name, limit", [("week_run", WEEK_LIMIT), ("month_run", MONTH_LIMIT)])
def test_the_calls_stay_within_the_sdd_limit_and_nothing_stays_unread(request, run_name, limit):
    run: Run = request.getfixturevalue(run_name)
    report = run.report
    assert report["calls"] == run.client.call_count == len(run.client.requests) - len(run.client.writes)
    assert report["calls"] <= limit, f"{run_name}: {report['calls']} calls, limit {limit}, retried {report['retried']}"
    assert report["not_read"] == [] and report["kado_empty"] == []


def test_no_write_was_performed(week_run, month_run):
    for run in (week_run, month_run):
        assert run.client.writes == [], [w.get("path") for w in run.client.writes]
        assert [tool for tool, _ in run.client.requests if tool != "kado-read" and tool != "kado-search"] == []

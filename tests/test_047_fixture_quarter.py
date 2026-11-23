#!/usr/bin/env python3
# version: 0.1.0
"""test_047_fixture_quarter.py — the fake vault holds a quarter and the previous notes (spec 047 T1.2, ADR-11).

Pins the extension of tests/review_privacy_fixture.py and tests/review_e2e_walk.py that the spec 047 baseline
(T1.3) and the rebuilt read run on: a quarterly folder and a quarter setup in the fixture config; weekly notes
2026-W12 and W13 and monthly notes 2026-01 and 2026-02 (the previous notes of a week and a month); no 2025-Q4
note; dailies from 2026-01-01 to 2026-03-31 with a content day in every ISO week the quarter overlaps; quarterly
proposals valid against review-proposals.schema.json; and the walk running Pass 1 and Pass 2 of 2026-Q1 on the
current flow.

The ISO weeks counted are W01 … W14 of 2026: the quarter starts on Thursday 2026-01-01, inside W01 (Mon
2025-12-29 … Sun 2026-01-04), and ends on Tuesday 2026-03-31, inside W14 (Mon 2026-03-30 … Sun 2026-04-05).
The rebuilt read condenses a quarter per ISO week clipped to the quarter (SDD Complex Logic (a): 14 units), so
every one of the 14 weeks needs a day inside the quarter holding content, or that unit is empty. All text is
synthetic.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import jsonschema
import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import (  # noqa: E402
    INBOX, QUARTER, QUARTER_DOC, QUARTER_PERIOD, QUARTER_STEM, QUARTER_TARGET, Walk,
)
from review_privacy_fixture import (  # noqa: E402
    CONFIG, DAILY, DAY, MONTHLY, QUARTER_CONFIG, QUARTERLY, WEEKLY, build_vault, proposals,
)

SCHEMA = TESTS_DIR.parent / "tomo" / "schemas" / "review-proposals.schema.json"
Q_START, Q_END = date(2026, 1, 1), date(2026, 3, 31)
ISO_WEEKS = [f"2026-W{n:02d}" for n in range(1, 15)]          # W01 (from 2025-12-29) … W14 (to 2026-04-05)
_DAILY_RE = re.compile(rf"^{re.escape(DAILY)}(\d{{4}}-\d{{2}}-\d{{2}})\.md$")
# the March dailies of the month walk before spec 047: the quarter's extra March days never join them
MONTH_DAYS = ["2026-03-01", "2026-03-10", "2026-03-23", "2026-03-24", "2026-03-25", "2026-03-26", "2026-03-27",
              "2026-03-29", "2026-03-30", "2026-03-31"]


def _dailies(files: dict) -> dict[date, str]:
    out = {}
    for path, text in files.items():
        m = _DAILY_RE.match(path)
        if m:
            out[date.fromisoformat(m.group(1))] = text
    return out


def _body(text: str) -> list[str]:
    """The daily's lines after its frontmatter and title, blank lines dropped."""
    lines = text.split("---\n", 2)[2].splitlines()
    return [ln for ln in lines[1:] if ln.strip()]


def _iso(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


# ── the config ──


def test_the_fixture_config_has_a_quarterly_folder_and_the_quarter_setup_is_its_own_config():
    granularities = CONFIG["concepts"]["calendar"]["granularities"]
    assert QUARTERLY == "Calendar/304 Quarterly/"
    assert granularities["quarterly"] == {"enabled": True, "path": QUARTERLY}
    assert CONFIG["naming"]["calendar_patterns"]["quarterly"] == "YYYY-[Q]Q"
    assert "quarterly" not in CONFIG["review"], "the week and month walks keep `quarter: missing` at start"
    quarterly = QUARTER_CONFIG["review"]["quarterly"]
    assert quarterly["heading"] == "Tomo Review" and quarterly["place"] == {"anchor": "Reflections",
                                                                            "placement": "before"}
    assert QUARTER_CONFIG["templates"]["mapping"]["quarterly"] == "t_quarter.md"
    rest = {k: v for k, v in QUARTER_CONFIG["review"].items() if k != "quarterly"}
    assert rest == CONFIG["review"], "the quarter setup adds review.quarterly and nothing else under review"


# ── the vault ──


def test_the_vault_holds_the_previous_notes_and_no_2025_q4_note():
    vault = build_vault(quarter=True)
    for name in ("2026-W12", "2026-W13"):
        assert f"{WEEKLY}{name}.md" in vault.files, name
    for name in ("2026-01", "2026-02"):
        assert f"{MONTHLY}{name}.md" in vault.files, name
    assert [p for p in vault.files if "2025-Q4" in p] == []
    assert [p for p in vault.files if p.startswith(QUARTERLY)] == [], "the quarterly folder is empty"
    assert QUARTERLY.rstrip("/") in vault.folders or QUARTERLY in vault.folders, vault.folders


def test_the_dailies_span_the_quarter_with_a_content_day_in_every_iso_week():
    days = _dailies(build_vault(quarter=True).files)
    inside = sorted(d for d in days if Q_START <= d <= Q_END)
    assert inside[0] == Q_START and inside[-1] == Q_END, (inside[0], inside[-1])
    with_content = {_iso(d) for d in inside if _body(days[d])}
    assert sorted(with_content) == ISO_WEEKS, sorted(set(ISO_WEEKS) ^ with_content)
    assert _iso(Q_START) == "2026-W01" and _iso(Q_START - timedelta(days=3)) == "2026-W01"
    assert _iso(Q_END) == "2026-W14" and _iso(Q_END + timedelta(days=5)) == "2026-W14"


def test_the_default_vault_keeps_the_months_dailies_and_holds_the_quarter_from_january():
    """The month walk reads March: its days stay those of spec 045 (the read report is unchanged)."""
    days = _dailies(build_vault().files)
    march = sorted(d.isoformat() for d in days if d.month == 3 and d.year == 2026)
    assert march == MONTH_DAYS
    assert min(d for d in days) == Q_START
    quarter_only = set(_dailies(build_vault(quarter=True).files)) - set(days)
    assert quarter_only and all(d.month == 3 for d in quarter_only), sorted(quarter_only)


def test_the_added_dailies_hold_only_synthetic_structure():
    """Every daily the quarter extension adds is one synthetic line: its date, its ISO week and the day marker."""
    before_047 = {date.fromisoformat(d) for d in MONTH_DAYS} | {date(2026, 4, 1)}
    days = _dailies(build_vault(quarter=True).files)
    added = {d: t for d, t in days.items() if d not in before_047}
    assert sorted(d.isoformat() for d in added) == [
        "2026-01-01", "2026-01-05", "2026-01-12", "2026-01-19", "2026-01-26", "2026-02-02", "2026-02-09",
        "2026-02-16", "2026-02-23", "2026-03-04", "2026-03-18"]
    for day, text in added.items():
        assert text.startswith(f"---\ntags: [daily]\n---\n# {day.isoformat()}\n"), text
        assert _body(text) == [f"quarter day {day.isoformat()} {_iso(day)} {DAY}"], text


# ── the proposals ──


def test_the_quarterly_proposals_are_valid_against_todays_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    props = proposals("quarter")
    jsonschema.Draft202012Validator(schema).validate(props)
    groups = props["groups"]
    assert {"done", "monthly_only"} <= set(groups), groups
    assert all(s.startswith("2026-0") for g in groups.values() for i in g for s in i["sources"])
    assert any(s in ("2026-01", "2026-02") for i in groups["monthly_only"] for s in i["sources"])


# ── the walk ──


def test_the_walk_names_the_quarter():
    assert (QUARTER, QUARTER_PERIOD, QUARTER_STEM) == ("quarter", "2026-Q1", "2026-Q1_review")
    assert QUARTER_TARGET == f"{QUARTERLY}2026-Q1.md" and QUARTER_DOC == f"{INBOX}2026-Q1 Review.md"


@pytest.fixture
def quarter_walk(tmp_path, monkeypatch, capsys, request):
    w = Walk(tmp_path, monkeypatch, capsys, request.node.nodeid, config=QUARTER_CONFIG, quarter=True)
    w.vault._record = w.vault.recorded.append     # per test only: the e2e sweeps own review_e2e_walk.WRITES
    yield w
    outside = [p for p in w.vault.recorded if not p.startswith(INBOX)]
    assert outside == [], f"Tomo wrote outside the inbox: {outside}"


def test_the_walk_runs_pass_1_and_pass_2_of_the_quarter_on_the_current_flow(quarter_walk: Walk):
    w = quarter_walk
    out = w.start(QUARTER_PERIOD)
    assert out["request"]["kind"] == QUARTER and out["request"]["start"] == "2026-01-01", out
    assert out["setup"]["quarter"] == "present", out["setup"]
    read = w.read(QUARTER_PERIOD, QUARTER)
    assert read["status"] == "ok" and read["nothing_to_review"] is False, read
    found = {d["date"] for d in read["report"]["days"] if any(x["state"] == "found" for x in d["dailies"])}
    assert sorted({_iso(date.fromisoformat(d)) for d in found}) == ISO_WEEKS
    out = w.write(QUARTER_STEM, QUARTER)
    assert out["status"] == "written" and out["doc_path"] == QUARTER_DOC and out["target"] == QUARTER_TARGET, out
    assert out["target_exists"] is False and out["counts"]["done"] == 1 and out["counts"]["monthly_only"] == 1, out
    text = w.doc(QUARTER_DOC)
    assert "[[2026-02]]" in text, "the monthly_only item links its monthly note"
    w.approve(QUARTER_DOC)
    assert w.parse(QUARTER_STEM)["approved"] is True
    assert w.preview(QUARTER_STEM)["problems"] == []
    out = w.deliver(QUARTER_STEM)
    assert out["status"] == "delivered", out
    assert w.hashi_apply(QUARTER_STEM) == ["applied"]
    target = w.vault.text(QUARTER_TARGET)
    assert "%% tomo-review 2026-Q1 %%" in target and target.index("## Tomo Review") < target.index("## Reflections")
    assert w.status(QUARTER_STEM)["state"] == "applied"

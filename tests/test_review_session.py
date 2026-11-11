#!/usr/bin/env python3
# version: 0.1.2
"""test_review_session.py — Behavioural tests for review-session.py (spec 045 T2.2).

Covers the setup preview and the confirmed-input step, on tests/review_fake_vault:
- match: the week rule inferred from journal-start-date / day-heading links,
  ambiguous on contradicting starts, partial headings or no dates at all,
  default when there is nothing to compare with; a configured rule wins over
  the inference; two notes with the same stem are both checked and listed
- match: ISO names give GGGG-[W]WW + Monday; Sunday-dated names give the
  Sunday rule and gggg-[W]ww; a Sunday rule given by flags re-lists the ISO
  notes it no longer matches; --first-day and --min-days only together
- match: a found listing without a parsing name says "no notes to compare";
  an empty listing is folder_listing kado-none, never "no notes"
- match: template kinds plain|templater|missing|unreadable (no-access hint),
  place and daily sections proposed from the templates, configured values win
- match: unsafe-format stops before any Kado call; Kado unreachable / auth
  stop the preview; format problems are listed
- match: the daily-path fix only when the folder lookup finds the other spelling
- match never requests the Obsidian plugin config (.obsidian) from Kado
- setup-input: a confirmed proposal becomes a schema-valid writer input;
  invalid input returns pointers; nothing is written then
- exit codes: 0 for every outcome, 2 for a bad invocation, 1 + class name only
  on an unexpected exception; stdout never carries note text
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "review-session.py"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault  # noqa: E402
from lib.kado_client import KadoAuthError, KadoConnectionError, KadoToolError  # noqa: E402
from lib import review_config as rc  # noqa: E402

TODAY = "2026-11-11"
WEEKLY = "Calendar/302 Weekly/"
MONTHLY = "Calendar/303 Monthly/"
DAILY = "Calendar/301 Daily/"
TEMPLATES = "X/Templates/"
BODY_MARKER = "BODY-MARKER-9c1e private journal line"

WEEK_TEMPLATE = (
    "---\nweek: <% tw %>\n---\n"
    "# Weekly Review: <%\"[\"%>[<% tw %>]]\n\n## Theme of the week\n\n## Overview\n\n"
    "### Habits\n\n```dataview\n# not a heading\n```\n\n## In my own words\n"
)
MONTH_TEMPLATE = "# Monthly Review\n\n## Theme of the Month\n\n## Reflections\n"
DAY_TEMPLATE = (
    "## Habit\n\n## [[DP-<% tp.date.now(\"YYYY-MM-DD\") %>|Dayplanner]]\n\n"
    "## Daily Log\n\n## End of the Day\n"
)


def _weekly(name: str, start: str | None = None, headings=(), locale="de") -> str:
    front = ["---", f"locale: {locale}", f"week: {name}"]
    if start is not None:
        front.append(f"journal-start-date: {start}")
    front.append("---")
    body = [f"# Weekly Review: [[{name}]]", "", BODY_MARKER, ""]
    for day in headings:
        body += [f"### [[{day}|{day} Day]]", "", f"{BODY_MARKER} {day}", ""]
    return "\n".join(front + body) + "\n"


def _iso_files() -> dict:
    files = {
        WEEKLY + "2026-W13.md": _weekly("2026-W13", "2026-03-23"),
        WEEKLY + "2026-W12.md": _weekly("2026-W12", "2026-03-16"),
        WEEKLY + "2026-W11.md": _weekly("2026-W11", "2026-03-09"),
        WEEKLY + "2026-W10.md": _weekly("2026-W10", "2026-03-02"),
        WEEKLY + "2026-W09.md": _weekly("2026-W09", "2026-02-23"),
        WEEKLY + "2026-W14.md": _weekly("2026-W14"),
        WEEKLY + "2025/2025-W50.md": _weekly("2025-W50", "2025-12-08"),
        WEEKLY + "Weekly Index.md": "# Index\n\n" + BODY_MARKER + "\n",
    }
    return files


def _templates() -> dict:
    return {
        TEMPLATES + "t_week.md": WEEK_TEMPLATE,
        TEMPLATES + "t_month.md": MONTH_TEMPLATE,
        TEMPLATES + "t_day.md": DAY_TEMPLATE,
    }


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("review_session", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module      # the script's dataclasses resolve their module here
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    profile = {"concept_defaults": {
        "inbox": "100 Inbox/",
        "calendar": {"granularities": {
            "daily": {"enabled": True, "path": DAILY},
            "weekly": {"enabled": True, "path": WEEKLY},
            "monthly": {"enabled": True, "path": MONTHLY},
        }},
    }}
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump(profile), encoding="utf-8")
    return tmp_path


def _config(instance: Path, *, templates=None, daily_path=None, naming=None, review=None) -> None:
    cfg: dict = {"concepts": {"inbox": "100 Inbox/"}}
    if daily_path is not None:
        cfg["concepts"]["calendar"] = {"granularities": {"daily": {"enabled": True, "path": daily_path}}}
    if templates is not None:
        cfg["templates"] = templates
    if naming is not None:
        cfg["naming"] = {"calendar_patterns": naming}
    if review is not None:
        cfg["review"] = review
    (instance / "config" / "vault-config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")


def _templates_config(**mapping) -> dict:
    return {"base_path": TEMPLATES, "mapping": mapping}


def _run(mod, monkeypatch, capsys, argv, fake: ReviewFakeVault):
    monkeypatch.setattr(mod, "KadoClient", fake)
    code = mod.main(["--profiles-dir", "profiles"] + argv)
    out, err = capsys.readouterr()
    assert not any(".obsidian" in p for p in fake.paths_seen), "plugin config requested (ADR-7)"
    assert BODY_MARKER not in out and BODY_MARKER not in err
    return code, (json.loads(out) if out else None), out, err


def _match(mod, monkeypatch, capsys, fake, *extra, kind="week"):
    return _run(mod, monkeypatch, capsys, ["match", "--kind", kind, "--today", TODAY, *extra], fake)


# ---------------------------------------------------------------- match: week rule

def test_match_infers_iso_from_journal_start_dates(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_templates_config(weekly="t_week.md"))
    fake = ReviewFakeVault({**_iso_files(), **_templates()})
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok" and out["kind"] == "week"
    p, ev = out["proposal"], out["evidence"]
    assert p["folder"] == WEEKLY
    assert p["format"] == "GGGG-[W]WW"
    assert (p["first_day"], p["min_days"]) == ("monday", 4)
    assert ev["week_rule"] == "inferred"
    assert ev["folder_listing"] == "found"
    assert ev["notes_checked"] == 7
    assert sorted(ev["matched"]) == ["2025-W50", "2026-W09", "2026-W10", "2026-W11", "2026-W12", "2026-W13", "2026-W14"]
    assert ev["unmatched"] == ["Weekly Index"]
    assert p["language"] == "de"
    assert ev["format_problems"] == []
    assert "error" not in out


def test_match_infers_the_rule_from_day_heading_links(mod, instance, monkeypatch, capsys):
    _config(instance)
    days = [f"2026-03-{d:02d}" for d in range(16, 23)]
    fake = ReviewFakeVault({WEEKLY + "2026-W12.md": _weekly("2026-W12", headings=days)})
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["evidence"]["week_rule"] == "inferred"
    assert (out["proposal"]["first_day"], out["proposal"]["min_days"]) == ("monday", 4)
    assert ("read_note", WEEKLY + "2026-W12.md") in fake.events


def test_match_partial_day_headings_do_not_count_as_dates(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault({WEEKLY + "2026-W12.md": _weekly("2026-W12", headings=["2026-03-18", "2026-03-19", "2026-03-20"])})
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["evidence"]["week_rule"] == "ambiguous"
    assert out["evidence"]["notes_checked"] == 1


def test_match_contradicting_starts_are_ambiguous(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault({
        WEEKLY + "2026-W13.md": _weekly("2026-W13", "2026-03-23"),   # Monday
        WEEKLY + "2026-W12.md": _weekly("2026-W12", "2026-03-15"),   # Sunday
    })
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["evidence"]["week_rule"] == "ambiguous"
    assert (out["proposal"]["first_day"], out["proposal"]["min_days"]) == ("monday", 4)
    assert out["proposal"]["format"] == "GGGG-[W]WW"


def test_match_notes_without_dates_are_ambiguous(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault({WEEKLY + "2026-W13.md": _weekly("2026-W13"), WEEKLY + "2026-W12.md": _weekly("2026-W12")})
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["evidence"]["week_rule"] == "ambiguous"
    assert sorted(out["evidence"]["matched"]) == ["2026-W12", "2026-W13"]


def test_match_infers_a_sunday_rule_from_sunday_starts(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault({
        WEEKLY + "2026-W10.md": _weekly("2026-W10", "2026-03-01"),   # SDD walkthrough: (Sun, 1) -> 2026-W10
        WEEKLY + "2026-W09.md": _weekly("2026-W09", "2026-02-22"),
    })
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    p, ev = out["proposal"], out["evidence"]
    assert ev["week_rule"] == "inferred"
    assert (p["first_day"], p["min_days"]) == ("sunday", 1)
    assert p["format"] == "gggg-[W]ww"
    assert sorted(ev["matched"]) == ["2026-W09", "2026-W10"] and ev["unmatched"] == []
    assert ev["format_problems"] == []


def test_match_week_1_note_pins_min_days(mod, instance, monkeypatch, capsys):
    _config(instance)
    # 2027-01-01 is a Friday: Monday-first week 1 starts 2026-12-28 only when min_days <= 3.
    fake = ReviewFakeVault({WEEKLY + "2027-W01.md": _weekly("2027-W01", "2026-12-28")})
    code, out, *_ = _match(mod, monkeypatch, capsys, fake, "--today", "2027-03-01")
    assert out["evidence"]["week_rule"] == "inferred"
    assert (out["proposal"]["first_day"], out["proposal"]["min_days"]) == ("monday", 1)
    assert out["proposal"]["format"] == "gggg-[W]ww"
    assert out["evidence"]["matched"] == ["2027-W01"]


def test_match_sunday_flags_relist_the_iso_notes_as_unmatched(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault(_iso_files())
    code, out, *_ = _match(mod, monkeypatch, capsys, fake, "--first-day", "sunday", "--min-days", "1")
    p, ev = out["proposal"], out["evidence"]
    assert (p["first_day"], p["min_days"]) == ("sunday", 1)
    assert p["format"] == "gggg-[W]ww"
    assert ev["week_rule"] == "inferred"          # what the notes showed, not the flags
    assert sorted(ev["unmatched"]) == ["2025-W50", "2026-W09", "2026-W10", "2026-W11", "2026-W12", "2026-W13", "Weekly Index"]
    assert ev["matched"] == ["2026-W14"]           # undated: matched by name alone


def test_match_configured_rule_wins_over_the_inference(mod, instance, monkeypatch, capsys):
    # flags > config > inference > defaults: a confirmed Sunday/1 setup is never
    # overridden by what the ISO-dated notes show; the evidence still reports them.
    _config(instance, review={"week": {"first_day": "sunday", "min_days_in_first_week": 1}})
    fake = ReviewFakeVault(_iso_files())
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    p, ev = out["proposal"], out["evidence"]
    assert code == 0 and out["status"] == "ok"
    assert (p["first_day"], p["min_days"]) == ("sunday", 1)
    assert p["format"] == "gggg-[W]ww"
    assert ev["week_rule"] == "inferred"          # what the notes showed, not the config
    assert sorted(ev["unmatched"]) == ["2025-W50", "2026-W09", "2026-W10", "2026-W11", "2026-W12", "2026-W13", "Weekly Index"]
    assert ev["matched"] == ["2026-W14"]
    assert not any("no notes" in h.lower() for h in out["hints"])


def test_match_keeps_two_notes_with_the_same_stem(mod, instance, monkeypatch, capsys):
    # the same name in the folder and in a year subfolder: both are checked and both are listed
    _config(instance)
    fake = ReviewFakeVault({
        WEEKLY + "2026-W12.md": _weekly("2026-W12", "2026-03-16"),          # Monday
        WEEKLY + "2025/2026-W12.md": _weekly("2026-W12", "2026-03-15"),     # Sunday: the hidden copy contradicts
    })
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    ev = out["evidence"]
    assert ev["notes_checked"] == 2
    assert ev["week_rule"] == "ambiguous"
    assert ev["matched"] == ["2026-W12"] and ev["unmatched"] == ["2026-W12"]
    assert ("read_frontmatter", WEEKLY + "2025/2026-W12.md") in fake.events
    assert ("read_frontmatter", WEEKLY + "2026-W12.md") in fake.events

    fake = ReviewFakeVault({
        WEEKLY + "2026-W12.md": _weekly("2026-W12", "2026-03-16"),
        WEEKLY + "2025/2026-W12.md": _weekly("2026-W12", "2026-03-16"),
    })
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    ev = out["evidence"]
    assert ev["notes_checked"] == 2 and ev["week_rule"] == "inferred"
    assert ev["matched"] == ["2026-W12", "2026-W12"] and ev["unmatched"] == []


def test_match_given_format_wins_and_its_problems_are_listed(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault(_iso_files())
    code, out, *_ = _match(mod, monkeypatch, capsys, fake, "--format", "YYYY-[W]WW")
    assert out["status"] == "ok" and out["proposal"]["format"] == "YYYY-[W]WW"
    kinds = [fp["kind"] for fp in out["evidence"]["format_problems"]]
    assert kinds == ["calendar-year-with-week"]
    assert out["evidence"]["format_problems"][0]["example"]


# ---------------------------------------------------------------- match: listing

def test_match_folder_without_notes_is_default_iso_and_found(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault({WEEKLY + "attachments/banner.png": b"\x89PNG", MONTHLY + "attachments/banner.png": b"\x89PNG"})
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    ev = out["evidence"]
    assert ev["folder_listing"] == "found"
    assert ev["week_rule"] == "default" and ev["notes_checked"] == 0
    assert ev["matched"] == [] and ev["unmatched"] == []
    assert out["proposal"]["format"] == "GGGG-[W]WW"
    assert (out["proposal"]["first_day"], out["proposal"]["min_days"]) == ("monday", 4)
    assert any("no notes to compare" in h and WEEKLY in h for h in out["hints"])
    assert not any("Kado key" in h for h in out["hints"])
    code, out, *_ = _match(mod, monkeypatch, capsys, fake, kind="month")
    assert out["proposal"]["format"] == "YYYY-MM" and out["evidence"]["week_rule"] == "default"
    assert out["evidence"]["folder_listing"] == "found"
    assert any("no notes to compare" in h and MONTHLY in h for h in out["hints"])


def test_match_parsing_names_are_notes_to_compare_even_when_unmatched(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault(_iso_files())
    _, out, *_ = _match(mod, monkeypatch, capsys, fake, "--first-day", "sunday", "--min-days", "1")
    assert out["evidence"]["unmatched"]
    assert not any("no notes" in h.lower() for h in out["hints"])
    fake = ReviewFakeVault({WEEKLY + "Weekly Index.md": "# Index\n"})
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["evidence"]["unmatched"] == ["Weekly Index"] and out["evidence"]["week_rule"] == "default"
    assert any("no notes to compare" in h for h in out["hints"])


@pytest.mark.parametrize("fake", [ReviewFakeVault({}, folders=[WEEKLY]), ReviewFakeVault({})],
                         ids=["empty-listing", "path-not-found"])
def test_match_empty_listing_is_kado_none_never_no_notes(mod, instance, monkeypatch, capsys, fake):
    _config(instance)
    code, out, raw, _ = _match(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "ok"
    assert out["evidence"]["folder_listing"] == "kado-none"
    assert out["evidence"]["week_rule"] == "default"
    assert out["evidence"]["matched"] == [] and out["evidence"]["unmatched"] == []
    assert "no notes" not in raw.lower()
    assert any("Kado key" in h and WEEKLY in h for h in out["hints"])


def test_match_lists_the_folder_once_two_levels_deep(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault(_iso_files())
    _match(mod, monkeypatch, capsys, fake)
    listings = [e for e in fake.events if e[0] == "list_dir"]
    assert listings == [("list_dir", WEEKLY)]


# ---------------------------------------------------------------- match: template, place, sections

def test_match_template_kinds(mod, instance, monkeypatch, capsys):
    fake = ReviewFakeVault({**_iso_files(), **_templates()})
    _config(instance, templates=_templates_config(weekly="t_week.md", monthly="t_month.md"))
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["proposal"]["template"] == "t_week.md" and out["proposal"]["template_kind"] == "templater"
    _, out, *_ = _match(mod, monkeypatch, capsys, fake, kind="month")
    assert out["proposal"]["template"] == "t_month.md" and out["proposal"]["template_kind"] == "plain"

    _config(instance)
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["proposal"]["template"] is None and out["proposal"]["template_kind"] == "missing"

    _config(instance, templates=_templates_config(weekly="t_gone.md"))
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["proposal"]["template"] == "t_gone.md" and out["proposal"]["template_kind"] == "missing"
    assert not any("no access" in h for h in out["hints"])

    _config(instance, templates=_templates_config(weekly="t_week.md"))
    fake.fail[("read_note", TEMPLATES + "t_week.md")] = KadoToolError("kado-read returned an error: PERMISSION_DENIED")
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["proposal"]["template"] == "t_week.md" and out["proposal"]["template_kind"] == "unreadable"
    assert any("no access" in h for h in out["hints"])


def test_match_proposes_place_and_daily_sections_from_the_templates(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_templates_config(weekly="t_week.md", monthly="t_month.md", daily="t_day.md"))
    fake = ReviewFakeVault({**_iso_files(), **_templates()})
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    p = out["proposal"]
    assert p["heading"] == "Tomo Review"
    assert p["place"] == {"anchor": "In my own words", "placement": "before"}
    assert p["own_sections"] == []
    assert p["daily_sections"] == ["Habit", "Daily Log", "End of the Day"]
    assert [h["text"] for h in out["evidence"]["template_headings"]] == [
        "Theme of the week", "Overview", "Habits", "In my own words"]
    _, out, *_ = _match(mod, monkeypatch, capsys, fake, kind="month")
    assert out["proposal"]["place"] == {"anchor": "Reflections", "placement": "before"}
    assert out["proposal"]["daily_sections"] == ["Habit", "Daily Log", "End of the Day"]


def test_match_without_a_template_leaves_the_anchor_open(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault(_iso_files())
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["proposal"]["place"] == {"anchor": None, "placement": "before"}
    assert out["proposal"]["daily_sections"] == []
    assert out["evidence"]["template_headings"] == []


def test_match_configured_values_win_over_the_guess(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_templates_config(weekly="t_week.md", daily="t_day.md"),
            naming={"weekly": "gggg-[W]ww"},
            review={"language": "en",
                    "week": {"first_day": "monday", "min_days_in_first_week": 4},
                    "daily": {"sections": ["Daily Log"]},
                    "weekly": {"heading": "Review by Tomo",
                               "place": {"anchor": "Overview", "placement": "inside"},
                               "own_sections": ["In my own words"]}})
    fake = ReviewFakeVault({**_iso_files(), **_templates()})
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    p = out["proposal"]
    assert p["format"] == "gggg-[W]ww"
    assert p["heading"] == "Review by Tomo"
    assert p["place"] == {"anchor": "Overview", "placement": "inside"}
    assert p["own_sections"] == ["In my own words"]
    assert p["daily_sections"] == ["Daily Log"]
    assert p["language"] == "en"
    assert out["evidence"]["week_rule"] == "inferred"
    assert "2026-W13" in out["evidence"]["matched"]


def test_match_month_lists_names_and_needs_no_week_rule(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault({
        MONTHLY + "2026-03.md": "---\nlocale: de\n---\n# March\n" + BODY_MARKER + "\n",
        MONTHLY + "2026-02.md": "# Feb\n",
        MONTHLY + "2025/2025-12.md": "# Dec\n",
        MONTHLY + "Monthly Index.md": "# Index\n",
    })
    _, out, *_ = _match(mod, monkeypatch, capsys, fake, kind="month")
    p, ev = out["proposal"], out["evidence"]
    assert p["folder"] == MONTHLY and p["format"] == "YYYY-MM"
    assert p["first_day"] is None and p["min_days"] is None
    assert ev["week_rule"] == "default" and ev["notes_checked"] == 0
    assert sorted(ev["matched"]) == ["2025-12", "2026-02", "2026-03"]
    assert ev["unmatched"] == ["Monthly Index"]
    assert p["language"] == "en"
    assert not any(e[0] in ("read_note", "read_frontmatter") for e in fake.events)


# ---------------------------------------------------------------- match: stops and fixes

def test_match_unsafe_format_stops_before_any_kado_call(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault(_iso_files())
    code, out, *_ = _match(mod, monkeypatch, capsys, fake, "--format", "GGGG/[W]WW")
    assert code == 0 and out["status"] == "stopped"
    assert out["error"]["kind"] == "unsafe-format"
    assert "proposal" not in out
    assert fake.events == []


def test_match_kado_unreachable_stops(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault(_iso_files())
    fake.connection_error = KadoConnectionError("Kado unreachable at 127.0.0.1:23026 (ConnectionRefusedError)")
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert code == 0 and out["status"] == "stopped"
    assert out["error"]["kind"] == "kado-unreachable"
    assert "127.0.0.1:23026" in out["error"]["detail"]
    assert "proposal" not in out


def test_match_kado_auth_refused_stops(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = ReviewFakeVault(_iso_files())
    fake.auth_error = KadoAuthError("401")
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["status"] == "stopped" and out["error"]["kind"] == "kado-auth"


def test_match_connection_lost_during_the_template_read_stops(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_templates_config(weekly="t_week.md"))
    fake = ReviewFakeVault({**_iso_files(), **_templates()})
    fake.fail[("read_note", TEMPLATES + "t_week.md")] = KadoConnectionError("lost")
    code, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["status"] == "stopped" and out["error"]["kind"] == "kado-unreachable"


def test_match_client_construction_failure_is_unreachable(mod, instance, monkeypatch, capsys):
    _config(instance)
    from lib.kado_client import KadoError

    def no_client(*a, **k):
        raise KadoError("Kado base URL not found")
    monkeypatch.setattr(mod, "KadoClient", no_client)
    code = mod.main(["--profiles-dir", "profiles", "match", "--kind", "week", "--today", TODAY])
    out = json.loads(capsys.readouterr()[0])
    assert code == 0 and out["status"] == "stopped" and out["error"]["kind"] == "kado-unreachable"


def test_match_daily_path_fix_only_when_the_other_spelling_exists(mod, instance, monkeypatch, capsys):
    _config(instance, daily_path="Calendar/301 Daily/ ")
    fake = ReviewFakeVault({**_iso_files(), DAILY + "2026-03-23.md": "# day\n"})
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert out["daily_path_fix"] == {"configured": "Calendar/301 Daily/ ", "found": "Calendar/301 Daily/"}

    fake = ReviewFakeVault(_iso_files())
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert "daily_path_fix" not in out
    assert ("list_dir", DAILY) in fake.events

    _config(instance, daily_path=DAILY)
    fake = ReviewFakeVault({**_iso_files(), DAILY + "2026-03-23.md": "# day\n"})
    _, out, *_ = _match(mod, monkeypatch, capsys, fake)
    assert "daily_path_fix" not in out
    assert not any(e == ("list_dir", DAILY) for e in fake.events)


def test_match_never_requests_the_plugin_config(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_templates_config(weekly="t_week.md", daily="t_day.md"), daily_path="Calendar/301 Daily/ ")
    fake = ReviewFakeVault({**_iso_files(), **_templates(),
                            ".obsidian/plugins/periodic-notes/data.json": '{"weekly": {"format": "gggg-[W]ww"}}'})
    _match(mod, monkeypatch, capsys, fake)          # _run asserts no .obsidian path was seen
    assert fake.events


# ---------------------------------------------------------------- setup-input

def _proposal(**overrides) -> dict:
    data = {
        "folder": WEEKLY, "format": "GGGG-[W]WW", "first_day": "monday", "min_days": 4,
        "template": "t_week.md", "template_kind": "templater",
        "heading": "Tomo Review", "place": {"anchor": "In my own words", "placement": "before"},
        "own_sections": ["In my own words"], "daily_sections": ["Habit", "Daily Log"], "language": "de",
    }
    data.update(overrides)
    return data


def _setup_input(mod, monkeypatch, capsys, instance, data, kind="week", *extra):
    path = instance / "confirmed.json"
    path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
    fake = ReviewFakeVault({})
    return _run(mod, monkeypatch, capsys,
                ["setup-input", "--kind", kind, "--confirmed", str(path), "--today", TODAY, *extra], fake)


def test_setup_input_writes_a_schema_valid_writer_input(mod, instance, monkeypatch, capsys):
    data = _proposal(daily_path_fix={"configured": "Calendar/301 Daily/ ", "found": DAILY})
    code, out, *_ = _setup_input(mod, monkeypatch, capsys, instance, data)
    assert code == 0 and out["status"] == "ok"
    assert out["input_path"] == "tomo-tmp/review/setup-week.json"
    written = json.loads((instance / out["input_path"]).read_text(encoding="utf-8"))
    assert rc.input_problems(written, today=None) == []
    assert "template_kind" not in written
    assert written["kind"] == "week" and written["daily_path_fix"] == DAILY
    assert written["template"] == "t_week.md" and written["place"]["anchor"] == "In my own words"


def test_setup_input_month_drops_the_null_week_rule(mod, instance, monkeypatch, capsys):
    data = _proposal(folder=MONTHLY, format="YYYY-MM", first_day=None, min_days=None,
                     template=None, template_kind="missing")
    code, out, *_ = _setup_input(mod, monkeypatch, capsys, instance, data, "month")
    assert out["status"] == "ok" and out["input_path"] == "tomo-tmp/review/setup-month.json"
    written = json.loads((instance / out["input_path"]).read_text(encoding="utf-8"))
    assert "first_day" not in written and "min_days" not in written
    assert written["template"] is None and written["kind"] == "month"
    assert rc.input_problems(written, today=None) == []


def test_setup_input_invalid_returns_pointers_and_writes_nothing(mod, instance, monkeypatch, capsys):
    data = _proposal(place={"anchor": None, "placement": "before"}, format="YYYY-[W]WW")
    code, out, *_ = _setup_input(mod, monkeypatch, capsys, instance, data)
    assert code == 0 and out["status"] == "invalid"
    assert out["errors"] == ["/place/anchor"]
    assert not (instance / "tomo-tmp").exists()

    data = _proposal(format="YYYY-[W]WW")
    code, out, *_ = _setup_input(mod, monkeypatch, capsys, instance, data)
    assert out["status"] == "invalid" and out["errors"] == ["/format"]
    assert out["problems"][0]["kind"] == "calendar-year-with-week"


def test_setup_input_refuses_a_kind_mismatch_and_non_json(mod, instance, monkeypatch, capsys):
    code, out, *_ = _setup_input(mod, monkeypatch, capsys, instance, _proposal(kind="month"))
    assert out["status"] == "invalid" and out["errors"] == ["/kind"]
    code, out, *_ = _setup_input(mod, monkeypatch, capsys, instance, "{not json")
    assert code == 0 and out["status"] == "invalid" and out["errors"] == ["/"]
    code, out, *_ = _setup_input(mod, monkeypatch, capsys, instance, "[1, 2]")
    assert out["status"] == "invalid" and out["errors"] == ["/"]


def test_setup_input_missing_file_is_a_usage_error(mod, instance, monkeypatch, capsys):
    code = mod.main(["setup-input", "--kind", "week", "--confirmed", "nope.json"])
    out, err = capsys.readouterr()
    assert code == 2 and out == "" and "nope.json" not in err and "FileNotFoundError" in err


def test_setup_input_output_override(mod, instance, monkeypatch, capsys):
    code, out, *_ = _setup_input(mod, monkeypatch, capsys, instance, _proposal(), "week", "--output", "x/in.json")
    assert out["status"] == "ok" and out["input_path"] == "x/in.json" and (instance / "x" / "in.json").exists()


# ---------------------------------------------------------------- exit codes

def test_unexpected_exception_exits_1_with_the_class_name_only(mod, instance, monkeypatch, capsys):
    _config(instance)

    def boom(*a, **k):
        raise RuntimeError("secret detail " + BODY_MARKER)
    monkeypatch.setattr(mod, "match", boom)
    code = mod.main(["match", "--kind", "week"])
    out, err = capsys.readouterr()
    assert code == 1 and out == "" and err == "RuntimeError\n"


@pytest.mark.parametrize("argv", [["nope"], ["match"], ["match", "--kind", "year"],
                                  ["match", "--kind", "week", "--min-days", "9"],
                                  ["match", "--kind", "week", "--first-day", "someday"],
                                  ["match", "--kind", "week", "--first-day", "sunday"],
                                  ["match", "--kind", "week", "--min-days", "1"],
                                  ["setup-input", "--kind", "week"]])
def test_usage_errors_exit_2(mod, instance, capsys, argv):
    with pytest.raises(SystemExit) as info:
        mod.main(argv)
    assert info.value.code == 2


def test_stdout_is_ascii_escaped(mod, instance, monkeypatch, capsys):
    _config(instance, review={"language": "de", "weekly": {"heading": "Überblick"}})
    fake = ReviewFakeVault(_iso_files())
    _, out, raw, _ = _match(mod, monkeypatch, capsys, fake)
    assert raw.isascii() and out["proposal"]["heading"] == "Überblick"

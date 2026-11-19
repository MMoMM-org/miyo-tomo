#!/usr/bin/env python3
# version: 0.1.1
"""test_review_session_sections.py — `review-session.py match` proposes the section mapping, off-limits rows,
the quarter and a checked template choice (spec 046 T2.1, #267).

PRD F2-AC1, F2-AC9, F6-AC1, F7-AC1, F7-AC2, F7-AC3; SDD Internal API Changes, ADR-9, ADR-13:
- a readable template gives `sections.candidates`, one per template heading (level 2..6): `heading_key`, `state`,
  `reason`, `flags`, `defaults {placement, cap}` and the `saved` row; a saved row comes back as the defaults, a
  saved off-limits row leaves its heading out as `off-limits` and comes back in `sections.off_limits`;
- no template, or a template without a heading a row may sit on, gives `sections` with `candidates == []` and
  `mappable: false` (the key is always there: a no-op that omits it fails);
- `match` writes `tomo-tmp/review/rows-<kind>.json` with the rows it shows (setup text only) and, after a template
  change, returns as `dropped` the earlier rows the new template lacks;
- a typed or configured template Kado does not find is `template_not_found` with the candidates and a null template;
- the configured anchor counts only while the resolved template is the configured one;
- a quarter with no setup proposes folder, format (from its notes, else `YYYY-[Q]Q`), template, place, language and
  rows; `match` saves nothing; `start` removes a stale rows file.

Runs in tmp_path on tests/review_fake_vault; all text synthetic; the BODY marker sits in body lines only.
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
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault  # noqa: E402

TODAY = "2026-11-11"
WEEKLY = "Calendar/302 Weekly/"
QUARTERLY = "Calendar/304 Quarterly/"
TEMPLATES = "X/900 Support/930 Templater/"
BODY = "BODY-MARKER-91c4 private line"
ROWS = Path("tomo-tmp/review")

T_SECTIONS = ("---\ntags: weekly\n---\n# <% tp.file.title %>\n\n"
              "## Habits\n```dataview\nTABLE sleep\n```\n\n"
              "## <% tp.date.now() %>\n\n"
              f"## Overview\n{BODY}\n```dataview\nLIST\n```\n\n"
              f"## In my own words\n### What Went Well This Week?\n{BODY}\n\n### Lessons\n")
T_PLAIN = "# Weekly\n\n## Theme\n\n## Reflections\n"
T_NO_ELIGIBLE = "# <% tp.file.title %>\n\n## <% tp.date.now() %>\n\n## [[Link]]\n"
T_QUARTER = "# <% tp.file.title %>\n\n## Quarter goals\n\n## Reflections\n"

LESSONS = {"heading": "Lessons", "level": 3, "parent": "In my own words", "occurrence": 1}
WENT_WELL = {"heading": "What Went Well This Week?", "level": 3, "parent": "In my own words", "occurrence": 1}
SAVED_ROW = {"id": "s1", **LESSONS, "description": "What the week taught", "keywords": ["gelernt"],
             "placement": "under", "cap": 3}
ROW_FIELDS = {"heading", "level", "parent", "occurrence", "description", "keywords", "placement", "cap"}


def _templates() -> dict:
    return {TEMPLATES + "t_week_sections.md": T_SECTIONS, TEMPLATES + "t_week_plain.md": T_PLAIN,
            TEMPLATES + "t_week_none.md": T_NO_ELIGIBLE, TEMPLATES + "t_quarter.md": T_QUARTER,
            TEMPLATES + "t_day.md": "## Daily Log\n"}


def _vault(**extra) -> ReviewFakeVault:
    weekly = {WEEKLY + "2026-W13.md": f"---\njournal-start-date: 2026-03-23\n---\n# 2026-W13\n\n## Notes\n{BODY}\n"}
    return ReviewFakeVault({**_templates(), **weekly, **extra}, folders=[WEEKLY, QUARTERLY, TEMPLATES])


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("review_session_sections", SCRIPTS_DIR / "review-session.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    profile = {"concept_defaults": {"inbox": "100 Inbox/", "calendar": {"granularities": {
        "weekly": {"enabled": True, "path": WEEKLY},
        "quarterly": {"enabled": True, "path": QUARTERLY},
    }}}}
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump(profile), encoding="utf-8")
    return tmp_path


def _config(instance: Path, *, mapping=None, review=None) -> Path:
    cfg: dict = {"concepts": {"inbox": "100 Inbox/"},
                 "templates": {"base_path": TEMPLATES, "mapping": {"daily": "t_day.md", **(mapping or {})}}}
    if review is not None:
        cfg["review"] = review
    path = instance / "config" / "vault-config.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return path


def _match(mod, monkeypatch, capsys, fake, *extra, kind="week"):
    monkeypatch.setattr(mod, "KadoClient", fake)
    code = mod.main(["--profiles-dir", "profiles", "match", "--kind", kind, "--today", TODAY, *extra])
    out, err = capsys.readouterr()
    assert BODY not in out and BODY not in err, "note or template body text reached stdout or stderr"
    result = json.loads(out)
    assert code == 0 and result["status"] == "ok", (code, result, err)
    return result


def _rows_file(instance: Path, kind: str = "week") -> dict:
    return json.loads((instance / ROWS / f"rows-{kind}.json").read_text(encoding="utf-8"))


def _by_heading(out: dict) -> dict:
    return {c["heading_key"]["heading"]: c for c in out["sections"]["candidates"]}


# ---------------------------------------------------------------- F2-AC1: the candidates of a readable template

def test_a_readable_template_gives_one_candidate_per_heading_with_key_state_reason_flags_and_defaults(
        mod, instance, monkeypatch, capsys):
    _config(instance, mapping={"weekly": "t_week_sections.md"})
    out = _match(mod, monkeypatch, capsys, _vault())
    sections = out["sections"]
    assert sections["template"] == "t_week_sections.md" and sections["mappable"] is True
    assert sections["off_limits"] == [] and sections["dropped"] == []
    by = _by_heading(out)
    assert list(by) == ["Habits", "<% tp.date.now() %>", "Overview", "In my own words",
                        "What Went Well This Week?", "Lessons"], "every heading, in template order"
    assert by["Lessons"] == {"heading_key": LESSONS, "state": "offered", "reason": None, "flags": [],
                             "defaults": {"placement": "end", "cap": 8}, "saved": None}
    assert by["Overview"]["flags"] == ["mixed"] and by["In my own words"]["flags"] == ["container"]
    assert (by["Habits"]["state"], by["Habits"]["reason"]) == ("left-out", "automatic")
    assert by["Habits"]["defaults"] == {"placement": "review", "cap": 8}, "an automatic heading takes analysis rows"
    templater = by["<% tp.date.now() %>"]
    assert (templater["state"], templater["reason"], templater["defaults"]) == ("left-out", "templater", None)


def test_saved_rows_come_back_as_the_defaults_and_saved_off_limits_leave_their_heading_out(
        mod, instance, monkeypatch, capsys):
    off = {**WENT_WELL, "with_subsections": False}
    _config(instance, mapping={"weekly": "t_week_sections.md"},
            review={"weekly": {"sections": {"t_week_sections.md": [SAVED_ROW]},
                               "off_limits": {"t_week_sections.md": [off]}}})
    out = _match(mod, monkeypatch, capsys, _vault())
    by = _by_heading(out)
    assert by["Lessons"]["saved"] == {**SAVED_ROW, "groups": []}
    assert by["Lessons"]["defaults"] == {"placement": "under", "cap": 3}
    assert (by["What Went Well This Week?"]["state"], by["What Went Well This Week?"]["reason"]) == \
        ("left-out", "off-limits")
    assert out["sections"]["off_limits"] == [off]


def test_rows_saved_for_another_template_are_not_this_templates_rows(mod, instance, monkeypatch, capsys):
    _config(instance, mapping={"weekly": "t_week_sections.md"},
            review={"weekly": {"sections": {"t_week_plain.md": [SAVED_ROW]}}})
    out = _match(mod, monkeypatch, capsys, _vault())
    assert _by_heading(out)["Lessons"]["saved"] is None


# ---------------------------------------------------------------- F2-AC9: nothing to map

@pytest.mark.parametrize("extra", [["--template", "none"], ["--template", "t_week_none"]])
def test_no_template_or_no_eligible_heading_is_an_explicit_empty_mapping(mod, instance, monkeypatch, capsys, extra):
    _config(instance)
    out = _match(mod, monkeypatch, capsys, _vault(), *extra)
    assert "sections" in out, "the skill reads `mappable`; an omitted block is not an answer"
    assert out["sections"]["candidates"] == [] and out["sections"]["mappable"] is False
    assert _rows_file(instance)["rows"] == []


def test_a_template_with_only_automatic_headings_is_mappable_for_analysis_rows(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = _vault(**{TEMPLATES + "t_week_auto.md": "# W\n\n## Sleep\n```dataview\nTABLE sleep\n```\n"})
    out = _match(mod, monkeypatch, capsys, fake, "--template", "t_week_auto")
    assert out["sections"]["mappable"] is True
    assert [c["reason"] for c in out["sections"]["candidates"]] == ["automatic"]


# ---------------------------------------------------------------- rows-<kind>.json and dropped (F7-AC3)

def test_match_writes_the_rows_it_shows_with_setup_text_only(mod, instance, monkeypatch, capsys):
    _config(instance, mapping={"weekly": "t_week_sections.md"},
            review={"weekly": {"sections": {"t_week_sections.md": [SAVED_ROW]}}})
    _match(mod, monkeypatch, capsys, _vault())
    raw = (instance / ROWS / "rows-week.json").read_text(encoding="utf-8")
    assert BODY not in raw, "template or note body text in the rows file"
    data = json.loads(raw)
    assert data["kind"] == "week" and data["template"] == "t_week_sections.md"
    assert [r["heading"] for r in data["rows"]] == ["Overview", "In my own words", "What Went Well This Week?",
                                                    "Lessons"], "the offered headings, the saved row in its place"
    assert all(set(r) <= ROW_FIELDS for r in data["rows"]), data["rows"]
    lessons = data["rows"][-1]
    assert lessons == {**LESSONS, "description": "What the week taught", "keywords": ["gelernt"],
                       "placement": "under", "cap": 3}


def test_after_a_template_change_dropped_names_the_earlier_rows_the_new_template_lacks(
        mod, instance, monkeypatch, capsys):
    _config(instance)
    first = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_sections")
    assert first["sections"]["dropped"] == []
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_plain")
    assert out["sections"]["dropped"] == [
        {"heading": "Overview", "level": 2, "parent": None},
        {"heading": "In my own words", "level": 2, "parent": None},
        {"heading": "What Went Well This Week?", "level": 3, "parent": "In my own words"},
        {"heading": "Lessons", "level": 3, "parent": "In my own words"},
    ]
    assert _rows_file(instance)["template"] == "t_week_plain.md", "the file now holds the rows shown last"
    again = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_plain")
    assert again["sections"]["dropped"] == [], "the same template again drops nothing"


def test_a_same_template_rerun_drops_nothing_even_for_a_row_the_template_lacks(mod, instance, monkeypatch, capsys):
    _config(instance)
    (instance / ROWS).mkdir(parents=True)
    rows = {"kind": "week", "template": "t_week_plain.md",
            "rows": [{**LESSONS, "keywords": [], "placement": "end", "cap": 8}]}
    (instance / ROWS / "rows-week.json").write_text(json.dumps(rows), encoding="utf-8")
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_plain")
    assert out["sections"]["dropped"] == [], "dropped is named only after a template change"


def test_a_template_change_to_no_template_drops_every_earlier_row(mod, instance, monkeypatch, capsys):
    _config(instance)
    _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_plain")
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "none")
    assert out["sections"]["dropped"] == [{"heading": "Theme", "level": 2, "parent": None},
                                          {"heading": "Reflections", "level": 2, "parent": None}]


def test_rows_files_are_kept_per_kind(mod, instance, monkeypatch, capsys):
    _config(instance)
    _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_plain")
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_quarter", kind="quarter")
    assert out["sections"]["dropped"] == [], "the week's rows are not the quarter's earlier mapping"
    assert _rows_file(instance)["template"] == "t_week_plain.md"
    assert _rows_file(instance, "quarter")["template"] == "t_quarter.md"


def test_start_removes_a_stale_rows_file(mod, instance, monkeypatch, capsys):
    _config(instance)
    (instance / ROWS).mkdir(parents=True)
    for kind in ("week", "month", "quarter"):
        (instance / ROWS / f"rows-{kind}.json").write_text('{"rows": []}\n', encoding="utf-8")
    (instance / ROWS / "setup-week.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(mod, "KadoClient", _vault())
    assert mod.main(["--profiles-dir", "profiles", "start", "--args=2026-W13", "--today", TODAY]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert sorted(p.name for p in (instance / ROWS).iterdir()) == ["setup-week.json"]


# ---------------------------------------------------------------- F7-AC1: a template that is not found

def test_a_typed_template_that_is_not_found_is_reported_with_the_candidates_and_a_null_template(
        mod, instance, monkeypatch, capsys):
    _config(instance, mapping={"weekly": "t_week_plain.md"})
    _match(mod, monkeypatch, capsys, _vault())
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_gone")
    assert out["template_not_found"] == {"name": "t_week_gone.md", "source": "typed"}
    assert out["proposal"]["template"] is None and out["sections"]["template"] is None
    assert out["template_candidates"] == ["t_week_none", "t_week_plain", "t_week_sections"]
    assert out["sections"]["candidates"] == [] and out["sections"]["dropped"] == []
    assert _rows_file(instance)["template"] == "t_week_plain.md", "a name not found shows no rows: the file stays"


def test_a_configured_template_that_is_not_found_is_reported_as_configured(mod, instance, monkeypatch, capsys):
    _config(instance, mapping={"weekly": "t_week_deleted.md"})
    out = _match(mod, monkeypatch, capsys, _vault())
    assert out["template_not_found"] == {"name": "t_week_deleted.md", "source": "configured"}
    assert out["proposal"]["template"] is None
    assert out["template_candidates"] == ["t_week_none", "t_week_plain", "t_week_sections"]


def test_a_found_template_carries_no_not_found_key(mod, instance, monkeypatch, capsys):
    _config(instance, mapping={"weekly": "t_week_plain.md"})
    assert "template_not_found" not in _match(mod, monkeypatch, capsys, _vault())
    assert "template_not_found" not in _match(mod, monkeypatch, capsys, _vault(), "--template", "none")


# ---------------------------------------------------------------- F7-AC2: the configured anchor

def test_the_configured_anchor_counts_only_for_the_configured_template(mod, instance, monkeypatch, capsys):
    _config(instance, mapping={"weekly": "t_week_sections.md"},
            review={"weekly": {"heading": "Tomo Review", "place": {"anchor": "Habits", "placement": "inside"}}})
    same = _match(mod, monkeypatch, capsys, _vault())
    assert same["proposal"]["place"] == {"anchor": "Habits", "placement": "inside"}
    same_typed = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_sections")
    assert same_typed["proposal"]["place"]["anchor"] == "Habits"
    corrected = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_plain")
    assert corrected["proposal"]["place"]["anchor"] == "Reflections", "proposed anew from the corrected template"


# ---------------------------------------------------------------- F6-AC1: the quarter

def test_a_quarter_without_setup_proposes_folder_format_template_place_language_and_rows(
        mod, instance, monkeypatch, capsys):
    _config(instance, mapping={"quarterly": "t_quarter.md"})
    out = _match(mod, monkeypatch, capsys, _vault(), kind="quarter")
    p = out["proposal"]
    assert (p["folder"], p["format"], p["template"]) == (QUARTERLY, "YYYY-[Q]Q", "t_quarter.md")
    assert p["place"] == {"anchor": "Reflections", "placement": "before"} and p["language"] == "en"
    assert p["first_day"] is None and p["min_days"] is None
    assert [c["heading_key"]["heading"] for c in out["sections"]["candidates"]] == ["Quarter goals", "Reflections"]
    assert _rows_file(instance, "quarter")["template"] == "t_quarter.md"


def test_a_quarter_format_follows_the_existing_quarterly_notes(mod, instance, monkeypatch, capsys):
    _config(instance)
    notes = {QUARTERLY + "2025 Q4.md": "# Q4\n", QUARTERLY + "2026 Q1.md": "# Q1\n"}
    out = _match(mod, monkeypatch, capsys, _vault(**notes), kind="quarter")
    assert out["proposal"]["format"] == "YYYY [Q]Q"
    assert out["evidence"]["matched"] and out["evidence"]["unmatched"] == []

    notes = {QUARTERLY + "Q1 2026.md": "# Q1\n"}
    assert _match(mod, monkeypatch, capsys, _vault(**notes), kind="quarter")["proposal"]["format"] == "[Q]Q YYYY"
    notes = {QUARTERLY + "Quarter plans.md": "# x\n"}
    assert _match(mod, monkeypatch, capsys, _vault(**notes), kind="quarter")["proposal"]["format"] == "YYYY-[Q]Q", \
        "no name that parses: the default"


def test_a_configured_or_typed_quarter_format_beats_the_notes(mod, instance, monkeypatch, capsys):
    _config(instance)
    notes = {QUARTERLY + "2026 Q1.md": "# Q1\n"}
    out = _match(mod, monkeypatch, capsys, _vault(**notes), "--format", "YYYY-[Q]Q", kind="quarter")
    assert out["proposal"]["format"] == "YYYY-[Q]Q"


# ---------------------------------------------------------------- nothing is saved

def test_match_saves_nothing(mod, instance, monkeypatch, capsys):
    config = _config(instance, mapping={"weekly": "t_week_sections.md"},
                     review={"weekly": {"sections": {"t_week_sections.md": [SAVED_ROW]}}})
    before = config.read_bytes()
    fake = _vault()
    _match(mod, monkeypatch, capsys, fake)
    _match(mod, monkeypatch, capsys, fake, "--template", "t_week_plain")
    assert config.read_bytes() == before
    assert sorted(p.name for p in (instance / ROWS).iterdir()) == ["rows-week.json"]
    assert {e[0] for e in fake.events} <= {"list_dir", "read_note", "read_frontmatter"}, "reads only, no write"

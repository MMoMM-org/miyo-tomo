#!/usr/bin/env python3
# version: 0.1.2
"""test_review_setup_input_rows.py — `review-session.py setup-input` refuses what may not be saved and saves the rest
(spec 046 T2.2).

PRD F2-AC4, F2-AC10, F2-AC11, F2-AC12, Rule 4; SDD Internal API Changes, Error Handling, ADR-3, ADR-10, ADR-13:
- refusals: `template-not-found` (a name `match` did not find, rows for a template `match` did not show, rows
  without any `match`), `section-left-out` with its reason, `section-not-in-template`, `section-off-limits`,
  `landing-off-limits` (a `before` under an off-limits previous heading, the "Tomo Review" place in an off-limits
  subtree; an `end` whose last sub-section is off-limits is accepted since T6.3), `analysis-not-automatic`; `duplicate-section`,
  `duplicate-off-limits`, `duplicate-section-id` and a malformed id (`schema`) from `review_config.input_problems`;
- a `mixed` heading is accepted; accepted rows reach the writer input with ids (kept from the saved rows, else the
  next free number); the rows file is deleted on save and kept on a refusal;
- the evidence is the rows file `match` wrote: eligibility fields in the confirmed file change nothing;
- a saved row whose heading the template lost is named in `match`'s `dropped`.

Every scenario runs `match` first, as the skill does, then `setup-input` on a confirmed file built from the proposal.
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

from lib import review_config as rc  # noqa: E402
from lib.kado_client import KadoToolError  # noqa: E402
from review_fake_vault import ReviewFakeVault  # noqa: E402

TODAY = "2026-11-11"
WEEKLY = "Calendar/302 Weekly/"
TEMPLATES = "X/900 Support/930 Templater/"
BODY = "BODY-MARKER-5e2a private line"
ROWS = Path("tomo-tmp/review")
TEMPLATE = "t_week_rows.md"

T_ROWS = ("---\ntags: weekly\n---\n# <% tp.file.title %>\n\n"
          "## Habits\n```dataview\nTABLE sleep\n```\n\n"
          "## <% tp.date.now() %>\n### Notes\n\n"
          "## [[Link]]\n\n"
          f"## Overview\n{BODY}\n```dataview\nLIST\n```\n\n"
          "## Reflections\n### Private\n\n### Lessons\n\n"
          "## Planning\nwords\n\n"
          "## Goals\n### Work\n\n### Health\n")


def key(heading, level=2, parent=None, occurrence=1) -> dict:
    return {"heading": heading, "level": level, "parent": parent, "occurrence": occurrence}


OVERVIEW, PLANNING, GOALS, HABITS = key("Overview"), key("Planning"), key("Goals"), key("Habits")
REFLECTIONS = key("Reflections")
PRIVATE, LESSONS = key("Private", 3, "Reflections"), key("Lessons", 3, "Reflections")
HEALTH = key("Health", 3, "Goals")


def row(k: dict, placement="end", **extra) -> dict:
    return {**k, "description": "What this section asks for", "placement": placement, **extra}


def off(k: dict, with_subsections=False) -> dict:
    return {**k, "with_subsections": with_subsections}


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("review_session_setup_rows", SCRIPTS_DIR / "review-session.py")
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
        "weekly": {"enabled": True, "path": WEEKLY}}}}}
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump(profile), encoding="utf-8")
    _config(tmp_path)
    return tmp_path


def _config(instance: Path, review=None, mapping=TEMPLATE) -> None:
    cfg: dict = {"concepts": {"inbox": "100 Inbox/"},
                 "templates": {"base_path": TEMPLATES, "mapping": {"weekly": mapping}}}
    if review is not None:
        cfg["review"] = review
    (instance / "config" / "vault-config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")


def _vault() -> ReviewFakeVault:
    files = {TEMPLATES + TEMPLATE: T_ROWS, TEMPLATES + "t_week_plain.md": "# W\n\n## Theme\n\n## Planning\n",
             WEEKLY + "2026-W13.md": f"---\njournal-start-date: 2026-03-23\n---\n# 2026-W13\n\n## Notes\n{BODY}\n"}
    return ReviewFakeVault(files, folders=[WEEKLY, TEMPLATES])


def _main(mod, monkeypatch, capsys, *argv, fake=None) -> dict:
    monkeypatch.setattr(mod, "KadoClient", fake or _vault())
    code = mod.main(["--profiles-dir", "profiles", *argv, "--today", TODAY])
    out, err = capsys.readouterr()
    assert BODY not in out and BODY not in err
    assert code == 0, (code, out, err)
    return json.loads(out)


def _match(mod, monkeypatch, capsys, *extra, fake=None) -> dict:
    out = _main(mod, monkeypatch, capsys, "match", "--kind", "week", *extra, fake=fake)
    assert out["status"] == "ok", out
    return out


def _setup(mod, monkeypatch, capsys, instance, proposal: dict, **confirmed) -> dict:
    path = instance / "confirmed.json"
    path.write_text(json.dumps({"kind": "week", **proposal, **confirmed}), encoding="utf-8")
    return _main(mod, monkeypatch, capsys, "setup-input", "--kind", "week", "--confirmed", str(path))


def _matched_setup(mod, monkeypatch, capsys, instance, *flags, **confirmed) -> dict:
    proposal = _match(mod, monkeypatch, capsys, *flags)["proposal"]
    return _setup(mod, monkeypatch, capsys, instance, proposal, **confirmed)


def _refused(out: dict, pointer: str, kind: str, **extra) -> None:
    assert out["status"] == "invalid", out
    problem = {"pointer": pointer, "kind": kind, **extra}
    assert out["problems"] == [problem], out["problems"]
    assert out["errors"] == [pointer]


def _written(instance: Path, out: dict) -> dict:
    assert out["status"] == "ok", out
    return json.loads((instance / out["input_path"]).read_text(encoding="utf-8"))


def _rows_file(instance: Path) -> Path:
    return instance / ROWS / "rows-week.json"


# ---------------------------------------------------------------- accepted rows reach the writer input

def test_accepted_rows_reach_the_writer_input_with_ids_and_the_rows_file_is_deleted(
        mod, instance, monkeypatch, capsys):
    rows = [row(OVERVIEW), row(LESSONS, "under", cap=3), row(PLANNING, "before"), row(HABITS, "review")]
    marks = [off(PRIVATE)]
    out = _matched_setup(mod, monkeypatch, capsys, instance, sections=rows, off_limits=marks)
    written = _written(instance, out)
    assert rc.input_problems(written, today=None) == []
    assert written["template"] == TEMPLATE
    assert [r["id"] for r in written["sections"]] == ["s1", "s2", "s3", "s4"]
    assert [{k: v for k, v in r.items() if k != "id"} for r in written["sections"]] == rows
    assert written["off_limits"] == marks
    assert not _rows_file(instance).exists(), "the rows file belongs to the dialogue that just saved"


def test_a_mixed_heading_is_accepted(mod, instance, monkeypatch, capsys):
    out = _match(mod, monkeypatch, capsys)
    assert {c["heading_key"]["heading"]: c["flags"] for c in out["sections"]["candidates"]}["Overview"] == ["mixed"]
    accepted = _setup(mod, monkeypatch, capsys, instance, out["proposal"], sections=[row(OVERVIEW, "under")])
    assert _written(instance, accepted)["sections"][0]["heading"] == "Overview"


def test_ids_are_kept_from_the_saved_rows_and_new_rows_get_the_next_free_number(mod, instance, monkeypatch, capsys):
    saved = [{"id": "s7", **row(LESSONS, "under")}, {"id": "s2", **row(PLANNING)}]
    _config(instance, review={"weekly": {"sections": {TEMPLATE: saved}}})
    out = _matched_setup(mod, monkeypatch, capsys, instance,
                         sections=[row(OVERVIEW), row(LESSONS, "end"), row(PLANNING, "before")])
    assert [r["id"] for r in _written(instance, out)["sections"]] == ["s8", "s7", "s2"]


def test_a_template_correction_keeps_the_id_of_a_heading_the_new_template_keeps(mod, instance, monkeypatch, capsys):
    plain = "t_week_plain.md"
    saved = [{"id": "s4", **row(PLANNING)}, {"id": "s6", **row(key("Theme"))}]
    _config(instance, mapping=plain, review={"weekly": {"sections": {plain: saved}}})
    _match(mod, monkeypatch, capsys)
    out = _matched_setup(mod, monkeypatch, capsys, instance, "--template", "t_week_rows",
                         sections=[row(PLANNING), row(OVERVIEW)])
    assert [r["id"] for r in _written(instance, out)["sections"]] == ["s4", "s7"], "never a number already given"


def test_an_invalid_input_keeps_the_rows_file(mod, instance, monkeypatch, capsys):
    out = _matched_setup(mod, monkeypatch, capsys, instance, sections=[row(key("Nowhere"))])
    assert out["status"] == "invalid"
    assert _rows_file(instance).is_file(), "the Correct step reruns against it"


# ---------------------------------------------------------------- template-not-found (F7-AC1, ADR-13)

def test_a_template_match_did_not_find_is_refused_even_when_put_back(mod, instance, monkeypatch, capsys):
    proposal = _match(mod, monkeypatch, capsys, "--template", "t_week_gone")["proposal"]
    assert proposal["template"] is None
    place = {"anchor": "Planning", "placement": "before"}
    out = _setup(mod, monkeypatch, capsys, instance, {**proposal, "template": "t_week_gone.md", "place": place})
    _refused(out, "/template", "template-not-found")


def test_rows_for_a_template_match_did_not_show_are_refused(mod, instance, monkeypatch, capsys):
    proposal = _match(mod, monkeypatch, capsys)["proposal"]
    out = _setup(mod, monkeypatch, capsys, instance, {**proposal, "template": "t_week_plain.md"},
                 sections=[row(key("Theme"))])
    _refused(out, "/template", "template-not-found")


def test_rows_for_an_unreadable_template_are_refused_and_the_template_alone_is_saved(
        mod, instance, monkeypatch, capsys):
    _match(mod, monkeypatch, capsys, "--template", "t_week_plain")
    fake = _vault()
    fake.fail[("read_note", TEMPLATES + TEMPLATE)] = KadoToolError("kado-read returned an error: PERMISSION_DENIED")
    out = _match(mod, monkeypatch, capsys, fake=fake)
    assert (out["proposal"]["template"], out["proposal"]["template_kind"]) == (TEMPLATE, "unreadable")
    place = {"anchor": "Planning", "placement": "before"}
    refused = _setup(mod, monkeypatch, capsys, instance, {**out["proposal"], "place": place}, sections=[row(PLANNING)])
    _refused(refused, "/template", "template-not-found")
    accepted = _setup(mod, monkeypatch, capsys, instance, {**out["proposal"], "place": place})
    assert _written(instance, accepted)["template"] == TEMPLATE, "spec 045: an unreadable template is still saved"


def test_rows_without_any_match_are_refused(mod, instance, monkeypatch, capsys):
    proposal = {"folder": WEEKLY, "format": "GGGG-[W]WW", "first_day": "monday", "min_days": 4,
                "template": TEMPLATE, "heading": "Tomo Review",
                "place": {"anchor": "Planning", "placement": "before"}, "language": "en"}
    out = _setup(mod, monkeypatch, capsys, instance, proposal, sections=[row(PLANNING)])
    _refused(out, "/template", "template-not-found")
    accepted = _setup(mod, monkeypatch, capsys, instance, proposal)
    assert accepted["status"] == "ok", "the spec 045 path: no rows, no rows file, saved as before"


# ---------------------------------------------------------------- left out, not in template, off-limits (F2-AC4, F2-AC11)

@pytest.mark.parametrize("heading_key,placement,reason", [
    (key("<% tp.date.now() %>"), "end", "templater"),
    (key("[[Link]]"), "under", "link"),
    (key("Notes", 3, "<% tp.date.now() %>"), "end", "per-period-parent"),
    (HABITS, "end", "automatic"),
    (key("<% tp.date.now() %>"), "review", "templater"),
])
def test_a_left_out_heading_is_refused_with_its_reason(mod, instance, monkeypatch, capsys, heading_key, placement,
                                                       reason):
    out = _matched_setup(mod, monkeypatch, capsys, instance, sections=[row(heading_key, placement)])
    _refused(out, "/sections/0", "section-left-out", reason=reason)


def test_a_heading_not_in_the_template_is_refused(mod, instance, monkeypatch, capsys):
    out = _matched_setup(mod, monkeypatch, capsys, instance, sections=[row(OVERVIEW), row(key("Overview", 3))])
    _refused(out, "/sections/1", "section-not-in-template")


@pytest.mark.parametrize("marks,target", [
    ([off(PRIVATE)], PRIVATE),
    ([off(REFLECTIONS, with_subsections=True)], LESSONS),
    ([off(HABITS)], HABITS),
])
def test_a_row_on_an_off_limits_heading_is_refused(mod, instance, monkeypatch, capsys, marks, target):
    placement = "review" if target == HABITS else "end"
    out = _matched_setup(mod, monkeypatch, capsys, instance, sections=[row(target, placement)], off_limits=marks)
    _refused(out, "/sections/0", "section-off-limits")


def test_a_saved_off_limits_mark_refuses_a_row_too(mod, instance, monkeypatch, capsys):
    _config(instance, review={"weekly": {"off_limits": {TEMPLATE: [off(PRIVATE)]}}})
    out = _match(mod, monkeypatch, capsys)
    assert out["sections"]["off_limits"] == [off(PRIVATE)]
    refused = _setup(mod, monkeypatch, capsys, instance, out["proposal"], sections=[row(PRIVATE)],
                     off_limits=out["sections"]["off_limits"])
    _refused(refused, "/sections/0", "section-off-limits")


def test_the_evidence_is_the_rows_file_not_the_confirmed_file(mod, instance, monkeypatch, capsys):
    """A model that copies a forged verdict or outline into the confirmed file changes nothing."""
    proposal = _match(mod, monkeypatch, capsys)["proposal"]
    habits = {"heading_key": HABITS, "state": "offered", "reason": None, "flags": []}
    forged = {**proposal, "candidates": [habits], "outline": {"headings": [{**HABITS, "line": 5, "ancestors": [],
                                                                            "body_kind": "own", "reason": None}],
                                                              "top": []}}
    out = _setup(mod, monkeypatch, capsys, instance, forged, sections=[row(HABITS)])
    _refused(out, "/sections/0", "section-left-out", reason="automatic")


# ---------------------------------------------------------------- landing-off-limits (Rule 4)

def test_a_before_under_an_off_limits_previous_heading_is_refused(mod, instance, monkeypatch, capsys):
    out = _matched_setup(mod, monkeypatch, capsys, instance, sections=[row(PLANNING, "before")],
                         off_limits=[off(LESSONS)])
    _refused(out, "/sections/0/placement", "landing-off-limits")
    accepted = _matched_setup(mod, monkeypatch, capsys, instance, sections=[row(PLANNING, "under")],
                              off_limits=[off(LESSONS)])
    assert accepted["status"] == "ok", "under lands in the mapped heading itself"


def test_an_end_whose_last_subsection_is_off_limits_is_accepted(mod, instance, monkeypatch, capsys):
    """T6.3 (owner 2026-11-17): `end` lands at the end of the heading's own text, before its first sub-heading."""
    out = _matched_setup(mod, monkeypatch, capsys, instance, sections=[row(GOALS, "end")], off_limits=[off(HEALTH)])
    assert out["status"] == "ok", out


@pytest.mark.parametrize("place", [{"anchor": "Reflections", "placement": "inside"},
                                   {"anchor": "Lessons", "placement": "before"}])
def test_the_tomo_review_place_inside_an_off_limits_subtree_is_refused(mod, instance, monkeypatch, capsys, place):
    proposal = _match(mod, monkeypatch, capsys)["proposal"]
    out = _setup(mod, monkeypatch, capsys, instance, {**proposal, "place": place},
                 off_limits=[off(REFLECTIONS, with_subsections=True)])
    _refused(out, "/place", "landing-off-limits")


def test_the_place_is_checked_against_the_saved_marks_when_none_are_confirmed(mod, instance, monkeypatch, capsys):
    _config(instance, review={"weekly": {"off_limits": {TEMPLATE: [off(GOALS, with_subsections=True)]}}})
    proposal = _match(mod, monkeypatch, capsys)["proposal"]
    out = _setup(mod, monkeypatch, capsys, instance, {**proposal, "place": {"anchor": "Goals", "placement": "inside"}})
    _refused(out, "/place", "landing-off-limits")


# ---------------------------------------------------------------- analysis rows (F2-AC12)

def test_an_analysis_row_on_an_offered_heading_is_refused(mod, instance, monkeypatch, capsys):
    out = _matched_setup(mod, monkeypatch, capsys, instance, sections=[row(PLANNING, "review")])
    _refused(out, "/sections/0", "analysis-not-automatic")


# ---------------------------------------------------------------- duplicates and ids (review_config.input_problems)

@pytest.mark.parametrize("confirmed,pointer,kind", [
    ({"sections": [row(OVERVIEW), row(OVERVIEW, "under")]}, "/sections/1", "duplicate-section"),
    ({"off_limits": [off(PRIVATE), off(PRIVATE, True)]}, "/off_limits/1", "duplicate-off-limits"),
    ({"sections": [{"id": "s1", **row(OVERVIEW)}, {"id": "s1", **row(PLANNING)}]}, "/sections/1/id",
     "duplicate-section-id"),
    ({"sections": [{"id": "x1", **row(OVERVIEW)}]}, "/sections/0/id", "schema"),
])
def test_duplicates_and_a_malformed_id_are_refused_at_their_pointer(mod, instance, monkeypatch, capsys, confirmed,
                                                                    pointer, kind):
    out = _matched_setup(mod, monkeypatch, capsys, instance, **confirmed)
    _refused(out, pointer, kind)


@pytest.mark.parametrize("bad,pointer", [
    ({"heading": ["x"]}, "/sections/0/heading"),
    ({"heading": "Overview", "parent": {"a": 1}}, "/sections/0/parent"),
])
def test_an_id_less_row_with_an_unhashable_key_is_a_schema_problem_not_a_crash(mod, instance, monkeypatch, capsys,
                                                                               bad, pointer):
    out = _matched_setup(mod, monkeypatch, capsys, instance, sections=[{"level": 2, "placement": "end", **bad}])
    assert out["status"] == "invalid", out
    assert {"pointer": pointer, "kind": "schema"} in out["problems"], out["problems"]


# ---------------------------------------------------------------- an unusable rows file is no evidence

@pytest.mark.parametrize("content", [
    "{not json",
    "[]",
    json.dumps({"template": TEMPLATE, "outline": {"headings": [{"heading": "A"}], "top": []}, "resolved": {}}),
    json.dumps({"template": TEMPLATE, "outline": {"headings": [], "top": []}, "resolved": "x"}),
], ids=["not-json", "a-list", "a-malformed-outline", "resolved-not-a-dict"])
def test_rows_against_an_unusable_rows_file_are_refused(mod, instance, monkeypatch, capsys, content):
    proposal = _match(mod, monkeypatch, capsys)["proposal"]
    _rows_file(instance).write_text(content, encoding="utf-8")
    out = _setup(mod, monkeypatch, capsys, instance, proposal, sections=[row(PLANNING)])
    _refused(out, "/template", "template-not-found")


# ---------------------------------------------------------------- a saved row the template lost (F2-AC10)

def test_a_saved_row_whose_heading_the_template_lost_is_named_in_dropped(mod, instance, monkeypatch, capsys):
    gone = {"id": "s3", **row(key("Gone", 3, "Reflections"))}
    _config(instance, review={"weekly": {"sections": {TEMPLATE: [gone, {"id": "s1", **row(PLANNING)}]}}})
    out = _match(mod, monkeypatch, capsys)
    assert out["sections"]["dropped"] == [{"heading": "Gone", "level": 3, "parent": "Reflections"}]
    again = _match(mod, monkeypatch, capsys)
    assert again["sections"]["dropped"] == out["sections"]["dropped"], "named on every run, not only after a change"
    kept = _setup(mod, monkeypatch, capsys, instance, again["proposal"], sections=[gone])
    _refused(kept, "/sections/0", "section-not-in-template")

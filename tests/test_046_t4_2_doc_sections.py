#!/usr/bin/env python3
# version: 0.1.3
"""test_046_t4_2_doc_sections.py — the review document by section and its write path (spec 046 T4.2).

On tests/review_fake_vault with synthetic read.json / proposals.json files and a vault config that
maps template sections (rows with ids, placements):
- the parts in template order, then the ``## Tomo Review %%review%%`` divider with its landing line,
  the analysis parts (placement ``review``), then the groups; empty groups omitted with a mapping
  (habits stay in the "Tomo Review" part); with no group and no analysis part left the divider is
  absent (F1-AC7, F3-AC1)
- one section checkbox per part with the positive label per language, ticked unless the section is
  empty; an empty section shows the nothing-found bullet (F1-AC8, F3-AC2)
- a landing line per part naming heading and placement, "Tomo Review" for an analysis or a routed
  section (F3-AC3), de and en
- the mark suffix from the label table, de and en, month and quarter marks; global ``%%tN%%`` ids
- ``meta.json``: ``pass1_counts`` with section keys, ``pass1_sections`` ``[{key, count, empty}]``
  and no heading, description or item text (CON-3); ``review_doc_read`` sums the section counts
- ``write`` and ``replace --confirm`` both refuse a section error before any Kado call; section
  rejections join ``rejected``; a read.json whose section keys no longer match the config rows is
  refused ``sections-changed``
- the quarter groups render for a quarter that read monthly notes

All data is synthetic.
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

from review_fake_vault import ReviewFakeVault, split_frontmatter  # noqa: E402
from lib import review_doc as rd  # noqa: E402
from lib import review_sections as rs  # noqa: E402
from lib.review_doc_read import read_document  # noqa: E402
from lib.review_vault import Vault  # noqa: E402
from test_review_doc import (  # noqa: E402
    DAILY, INBOX, MONTHLY, WEEKLY, _config, _daily, _day, item, month_read, proposals, stage, week_read,
)

TEMPLATE = "Templates/t_weekly.md"            # a saved name ends in .md (review_templates.template_name)
MARKER = "MARKER-46b2 private"
SCRIPT_PATH = SCRIPTS_DIR / "review-doc.py"


def row(rid: str, heading: str, placement: str, level=3, parent=None, **extra) -> dict:
    return {"id": rid, "heading": heading, "level": level, "parent": parent, "occurrence": 1,
            "description": f"what {heading} asks", "placement": placement, **extra}


WEEK_ROWS = [
    row("s1", "What Went Well This Week?", "end", level=4, parent="In my own words"),
    row("s2", "Energy and Sleep", "review", parent="Overview"),
    row("s3", "Planning", "before"),
    row("s4", "Notes", "under", level=2),
]


def definitions_of(rows) -> list:
    return [{"key": r["id"], "heading": r["heading"], "level": r["level"], "parent": r["parent"],
             "description": r["description"], "keywords": [], "groups": [], "cap": r.get("cap", 8)} for r in rows]


def map_config(instance: Path, rows, *, granularity="weekly", language="de", trackers=True) -> None:
    _config(instance, language=language, trackers=trackers)
    path = instance / "config" / "vault-config.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg.setdefault("templates", {})["mapping"] = {granularity: TEMPLATE}
    cfg["review"][granularity]["sections"] = {TEMPLATE: rows}
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")


def section(key: str, *items: dict) -> dict:
    return {"key": key, "items": list(items)}


def marked(text: str, mark: str, *sources: str) -> dict:
    return {**item(text, *sources), "mark": mark}


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("review_doc_sections_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def inst(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
    map_config(tmp_path, WEEK_ROWS)
    return tmp_path


def run(script, monkeypatch, capsys, argv, fake):
    monkeypatch.setattr(script, "KadoClient", fake)
    code = script.main(["--profiles-dir", "profiles"] + argv)
    out, err = capsys.readouterr()
    assert MARKER not in out and MARKER not in err, "text leaked to stdout/stderr"
    return code, json.loads(out)


def write(script, monkeypatch, capsys, inst, read, props, fake=None, command="write", *extra):
    stem, path = stage(inst, read, props)
    fake = fake or ReviewFakeVault({f"{WEEKLY}2026-W13.md": "# W13\n\n## In my own words\n"})
    argv = [command, "--stem", stem, "--proposals", str(path), "--run-id", "r-test", *extra]
    if command == "replace":
        argv.append("--confirm")
    code, out = run(script, monkeypatch, capsys, argv, fake)
    return code, out, fake


def body_of(fake) -> list:
    [path] = [p for p in fake.writes if p.endswith(" Review.md")]
    return split_frontmatter(fake.text(path))[1].splitlines()


def meta_of(inst: Path, stem="2026-W13_review") -> dict:
    return json.loads((inst / "tomo-tmp" / "review" / stem / "meta.json").read_text(encoding="utf-8"))


def mapped_week(rows=WEEK_ROWS) -> dict:
    return week_read(sections=definitions_of(rows))


WEEK_PROPS = {
    "language": "de",
    "sections": [
        section("s1", item("Steuererklärung abgeschickt", "2026-03-24"),
                item("Drei Abende ohne Bildschirm", "2026-03-25", _daily("2026-03-27"))),
        section("s2", item("Schlaf unter 6 Stunden", "2026-03-23", "2026-03-26")),
        section("s4", item("Notiz zu X", "2026-03-24")),
    ],
    "groups": {"done": [item("Woche aufgeräumt", "2026-03-28")]},
}

WEEK_BODY = [
    "# 2026-W13 Review",
    '> [!info] Ziel: [[2026-W13]] (vorhanden) · vor "In my own words"',
    "- [ ] Approved",
    "",
    "## What Went Well This Week? %%s1%%",
    "- [x] Abschnitt übernehmen %%s1%%",
    "*Landet: am Ende des Texts unter „What Went Well This Week?“ (Ebene 4, unter „In my own words“)*",
    "- [x] Steuererklärung abgeschickt ([[2026-03-24]]) %%t1%%",
    "- [x] Drei Abende ohne Bildschirm ([[2026-03-25]], [[2026-03-27]]) %%t2%%",
    "",
    "## Planning %%s3%%",
    "- [ ] Abschnitt übernehmen %%s3%%",
    "*Landet: vor „Planning“ (Ebene 3)*",
    "- nichts gefunden",
    "",
    "## Notes %%s4%%",
    "- [x] Abschnitt übernehmen %%s4%%",
    "*Landet: direkt unter „Notes“ (Ebene 2)*",
    "- [x] Notiz zu X ([[2026-03-24]]) %%t3%%",
    "",
    "## Tomo Review %%review%%",
    "*Landet: als Abschnitt „Tomo Review“ vor „In my own words“*",
    "",
    "## Energy and Sleep %%s2%%",
    "- [x] Abschnitt übernehmen %%s2%%",
    "*Landet: im Abschnitt „Tomo Review“ unter „Energy and Sleep“*",
    "- [x] Schlaf unter 6 Stunden ([[2026-03-23]], [[2026-03-26]]) %%t4%%",
    "",
    "## Erledigt",
    "- [x] Woche aufgeräumt ([[2026-03-28]]) %%t5%%",
    "",
    "## Gewohnheiten",
    "- [x] Sport: 6 von 6 Tagen (7 Tage im Zeitraum; fehlt: 2026-03-28) %%t6%%",
]


# ---------------------------------------------------------------- the document by section

def test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items(script, inst, monkeypatch,
                                                                                    capsys):
    code, out, fake = write(script, monkeypatch, capsys, inst, mapped_week(), WEEK_PROPS)
    assert code == 0 and out["status"] == "written", out
    assert body_of(fake) == WEEK_BODY


def test_the_english_labels_and_the_inside_place(script, inst, monkeypatch, capsys):
    map_config(inst, WEEK_ROWS, language="en")
    cfg_path = inst / "config" / "vault-config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["review"]["weekly"]["place"] = {"anchor": "In my own words", "placement": "inside"}
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    props = {**WEEK_PROPS, "language": "en"}
    _, _, fake = write(script, monkeypatch, capsys, inst, mapped_week(), props)
    body = body_of(fake)
    assert "- [x] Use this section %%s1%%" in body and "- [ ] Use this section %%s3%%" in body
    assert '*Lands: at the end of the text under "What Went Well This Week?" (level 4, under "In my own words")*' in body
    assert '*Lands: before "Planning" (level 3)*' in body
    assert '*Lands: right under "Notes" (level 2)*' in body
    assert '*Lands: as the section "Tomo Review" inside "In my own words"*' in body
    assert '*Lands: in the section "Tomo Review" under "Energy and Sleep"*' in body
    assert body[body.index("## Planning %%s3%%") + 3] == "- nothing found"


def test_no_group_and_no_analysis_part_left_means_no_divider(script, inst, monkeypatch, capsys):
    rows = [r for r in WEEK_ROWS if r["placement"] != "review"]
    map_config(inst, rows, trackers=False)
    props = {"language": "de", "sections": [section("s1", item("a", "2026-03-24"))], "groups": {}}
    _, out, fake = write(script, monkeypatch, capsys, inst, mapped_week(rows), props)
    body = body_of(fake)
    assert [ln for ln in body if ln.startswith("## ")] == [
        "## What Went Well This Week? %%s1%%", "## Planning %%s3%%", "## Notes %%s4%%"]
    assert not any("Tomo Review" in ln for ln in body)
    assert out["counts"] == {"s1": 1, "s3": 0, "s4": 0, "done": 0, "open": 0, "themes": 0, "growth": 0}


def test_an_analysis_part_alone_keeps_the_divider(script, inst, monkeypatch, capsys):
    map_config(inst, WEEK_ROWS, trackers=False)
    props = {"language": "de", "sections": [], "groups": {}}
    _, _, fake = write(script, monkeypatch, capsys, inst, mapped_week(), props)
    heads = [ln for ln in body_of(fake) if ln.startswith("## ")]
    assert heads[-2:] == ["## Tomo Review %%review%%", "## Energy and Sleep %%s2%%"]


def test_section_rejections_join_rejected_and_counts_carry_the_section_keys(script, inst, monkeypatch, capsys):
    props = json.loads(json.dumps(WEEK_PROPS))
    props["sections"][0]["items"].append(item("ohne Quelle", "2025-01-01"))
    _, out, _ = write(script, monkeypatch, capsys, inst, mapped_week(), props)
    assert out["rejected"] == [{"section": "s1", "index": 2, "reason": "no-source-in-period"}]
    assert out["counts"] == {"s1": 2, "s3": 0, "s4": 1, "s2": 1, "done": 1, "open": 0, "themes": 0, "growth": 0,
                             "habits": 1}


# ---------------------------------------------------------------- marks, the quarter, routed parts

def test_the_mark_suffix_from_the_label_table_in_a_month(script, inst, monkeypatch, capsys):
    map_config(inst, [row("s1", "Highlights", "end")], granularity="monthly", trackers=False)
    read = month_read(sections=definitions_of([row("s1", "Highlights", "end")]))
    props = {"language": "de", "groups": {}, "sections": [section(
        "s1", marked("nur dort", "weekly_only", f"{WEEKLY}2026-W13.md"),
        marked("fehlt dort", "not_in_weekly", "2026-03-02"), item("ohne Marke", "2026-03-03"))]}
    _, _, fake = write(script, monkeypatch, capsys, inst, read, props, ReviewFakeVault({}))
    body = body_of(fake)
    assert "- [x] nur dort ([[2026-W13]]) · nur im Wochenrückblick %%t1%%" in body
    assert "- [x] fehlt dort ([[2026-03-02]]) · in keinem Wochenrückblick %%t2%%" in body
    assert "- [x] ohne Marke ([[2026-03-03]]) %%t3%%" in body


def _part(key="s1", placement="end", items=(), routed=False) -> rs.SectionPart:
    return rs.SectionPart(key=key, heading="Goals", placement=placement,
                          landing=rs.Landing(heading="Goals", level=3, parent=None), items=list(items),
                          routed=routed)


def _doc_input(**overrides) -> rd.DocInput:
    fields = dict(period_name="2026-Q1", kind="quarter", language="en", stem="2026-Q1_review", run_id="r-test",
                  target=f"{MONTHLY}2026-Q1.md", target_exists=True, target_found_elsewhere=None,
                  anchor="Reflections", placement="inside", not_read=[], partly_read=[],
                  month_groups=True, groups={})
    fields.update(overrides)
    return rd.DocInput(**fields)


@pytest.mark.parametrize("language,only,never", [
    ("en", "· only in the monthly review", "· in no monthly review"),
    ("de", "· nur im Monatsrückblick", "· in keinem Monatsrückblick"),
])
def test_the_quarter_marks_and_the_english_month_marks(language, only, never):
    items = [{"text": "a", "links": ["2026-02"], "mark": "monthly_only"},
             {"text": "b", "links": ["2026-01-05"], "mark": "not_in_monthly"}]
    text, _ = rd.render_document(_doc_input(language=language, sections=[_part(items=items)]))
    assert f"- [x] a ([[2026-02]]) {only} %%t1%%" in text and f"- [x] b ([[2026-01-05]]) {never} %%t2%%" in text
    month = [{"text": "c", "links": ["2026-W13"], "mark": "weekly_only"},
             {"text": "d", "links": ["2026-03-02"], "mark": "not_in_weekly"}]
    text, _ = rd.render_document(_doc_input(kind="month", sections=[_part(items=month)]))
    assert "· only in the weekly review %%t1%%" in text and "· in no weekly review %%t2%%" in text


def test_a_routed_section_stays_in_template_order_and_lands_in_tomo_review():
    parts = [_part("s1", routed=True, items=[{"text": "a", "links": []}]), _part("s2", placement="before")]
    lines = rd.render_document(_doc_input(sections=parts))[0].splitlines()
    assert lines.index("## Goals %%s1%%") < lines.index("## Goals %%s2%%")
    assert '*Lands: in the section "Tomo Review" under "Goals"*' in lines
    assert '*Lands: before "Goals" (level 3)*' in lines


def test_the_review_heading_comes_from_the_setup():
    lines = rd.render_document(_doc_input(sections=[_part(placement="review")], review_heading="Rückblick"))[0]
    assert "## Rückblick %%review%%" in lines and '*Lands: as the section "Rückblick" inside "Reflections"*' in lines
    assert '*Lands: in the section "Rückblick" under "Goals"*' in lines


def test_a_quarter_renders_the_quarter_groups_once_it_read_monthly_notes(script, inst, monkeypatch, capsys):
    cfg_path = inst / "config" / "vault-config.yaml"
    _config(inst, trackers=False)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["concepts"]["calendar"]["granularities"]["quarterly"] = {"enabled": True, "path": "Calendar/304 Quarterly/"}
    cfg["naming"]["calendar_patterns"]["quarterly"] = "YYYY-[Q]Q"
    cfg["review"]["quarterly"] = {"heading": "Tomo Review", "place": {"anchor": "Reflections", "placement": "inside"},
                                  "own_sections": ["Reflections"]}
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    days = [f"2026-{m:02d}-{d:02d}" for m in (1, 2, 3) for d in (5, 15, 25)]
    read = week_read(period={"kind": "quarter", "name": "2026-Q1", "start": "2026-01-01", "end": "2026-03-31"},
                     days=[_day(d) for d in days])
    read["monthly"] = [{"path": f"{MONTHLY}2026-02.md", "month": "2026-02", "overlap_days": 28, "duplicate": False}]
    props = proposals(monthly_only=[item("only there", f"{MONTHLY}2026-02.md")])
    _, out, fake = write(script, monkeypatch, capsys, inst, read, props, ReviewFakeVault({}))
    assert out["status"] == "written", out
    heads = [ln for ln in body_of(fake) if ln.startswith("## ")]
    assert heads[-2:] == ["## Nur in den Monatsreviews", "## Nicht in den Monatsreviews"]
    assert out["counts"]["monthly_only"] == 1 and out["counts"]["not_in_monthly"] == 0


# ---------------------------------------------------------------- meta.json and the Pass 2 reader

def test_meta_holds_section_keys_and_counts_only(script, inst, monkeypatch, capsys):
    rows = [row("s1", MARKER + " heading", "end", parent=MARKER + " parent", description=MARKER + " desc"),
            row("s2", "Empty", "before")]
    map_config(inst, rows)
    props = {"language": "de", "groups": {}, "sections": [section("s1", item(MARKER + " item", "2026-03-24"))]}
    _, out, fake = write(script, monkeypatch, capsys, inst, mapped_week(rows), props)
    assert MARKER in fake.text(out["doc_path"])                  # the document is the only copy of the text
    meta = meta_of(inst)
    assert meta["pass1_sections"] == [{"key": "s1", "count": 1, "empty": False},
                                      {"key": "s2", "count": 0, "empty": True}]
    assert meta["pass1_counts"]["s1"] == 1 and meta["pass1_counts"]["s2"] == 0
    assert sorted(meta) == ["doc_path", "failed_step", "generated", "kind", "mode", "pass1_counts", "pass1_links",
                            "pass1_sections", "period", "run_id", "stem", "steps_done", "target", "target_exists",
                            "withdrawn"]
    raw = (inst / "tomo-tmp" / "review" / "2026-W13_review" / "meta.json").read_text(encoding="utf-8")
    assert "MARKER" not in raw and "Empty" not in raw


def test_an_unmapped_meta_has_no_pass1_sections(script, inst, monkeypatch, capsys):
    map_config(inst, [])
    _, out, _ = write(script, monkeypatch, capsys, inst, week_read(), proposals(done=[item("a", "2026-03-24")]))
    assert out["status"] == "written" and "pass1_sections" not in meta_of(inst)


def test_the_pass2_reader_counts_the_section_items_of_pass1_counts(script, inst, monkeypatch, capsys):
    _, out, fake = write(script, monkeypatch, capsys, inst, mapped_week(), WEEK_PROPS)
    meta = meta_of(inst)
    assert sum(meta["pass1_counts"].values()) == len(meta["pass1_links"]) == 6
    text = fake.text(out["doc_path"])
    fake.files[out["doc_path"]] = "\n".join(ln for ln in text.split("\n") if not ln.endswith("%%t1%%"))
    without_map = {k: v for k, v in meta.items() if k != "pass1_links"}
    assert read_document(Vault(fake), out["doc_path"], without_map).parsed.deleted == 1


# ---------------------------------------------------------------- the checks on write and replace

@pytest.mark.parametrize("command", ["write", "replace"])
def test_write_and_replace_refuse_a_section_error_before_any_kado_call(script, inst, monkeypatch, capsys, command):
    props = json.loads(json.dumps(WEEK_PROPS))
    props["sections"].append(section("s1"))
    props["sections"].append(section("s9"))
    code, out, fake = write(script, monkeypatch, capsys, inst, mapped_week(), props, None, command)
    assert code == 0 and out["status"] == "refused" and out["problems"] == ["proposals-invalid"]
    assert out["errors"] == ["/sections/3/key: duplicate-section", "/sections/4/key: unknown-section"]
    assert fake.call_count == 0 and fake.writes == []
    assert (inst / "tomo-tmp" / "review" / "2026-W13_review" / "read.json").exists()


def test_an_over_cap_section_is_refused_naming_its_key(script, inst, monkeypatch, capsys):
    rows = [row("s1", "Wins", "end", cap=1)]
    map_config(inst, rows)
    props = {"language": "de", "groups": {},
             "sections": [section("s1", item("a", "2026-03-24"), item("b", "2026-03-25"))]}
    _, out, _ = write(script, monkeypatch, capsys, inst, mapped_week(rows), props)
    assert out["status"] == "refused" and out["errors"] == ["/sections/0/items: over-cap (s1)"]


def test_sections_without_a_mapping_are_refused_as_unknown(script, inst, monkeypatch, capsys):
    map_config(inst, [])
    props = {**proposals(), "sections": [section("s1", item("a", "2026-03-24"))]}
    _, out, _ = write(script, monkeypatch, capsys, inst, week_read(), props)
    assert out["status"] == "refused" and out["errors"] == ["/sections/0/key: unknown-section"]


@pytest.mark.parametrize("read_rows,config_rows", [
    (WEEK_ROWS, WEEK_ROWS[:2]),                     # a row removed from the config after the read
    (WEEK_ROWS[:2], WEEK_ROWS),                     # a row added after the read
    (WEEK_ROWS, []),                                # the mapping removed
    ([], WEEK_ROWS),                                # the mapping added after an unmapped read
])
def test_a_read_whose_sections_no_longer_match_the_config_is_refused(script, inst, monkeypatch, capsys,
                                                                    read_rows, config_rows):
    map_config(inst, config_rows)
    read = mapped_week(read_rows) if read_rows else week_read()
    code, out, fake = write(script, monkeypatch, capsys, inst, read, proposals())
    assert code == 0 and out["status"] == "refused" and out["problems"] == ["sections-changed"], out
    assert fake.call_count == 0


def test_the_inbox_path_is_unchanged_by_the_mapping(script, inst, monkeypatch, capsys):
    _, out, _ = write(script, monkeypatch, capsys, inst, mapped_week(), WEEK_PROPS)
    assert out["doc_path"] == f"{INBOX}2026-W13 Review.md" and DAILY not in out["doc_path"]


# ---------------------------------------------------------------- headings are display-neutralised

def _heading_lines(text: str) -> list:
    return [ln for ln in text.splitlines() if ln.startswith("#")]


def test_a_hostile_row_heading_forges_no_line_and_no_id():
    hostile = "X\n## y %%s9%%"
    part = rs.SectionPart(key="s1", heading=hostile, placement="end",
                          landing=rs.Landing(heading=hostile, level=3, parent=None),
                          items=[{"text": "a", "links": []}])
    text, _ = rd.render_document(_doc_input(sections=[part]))
    assert _heading_lines(text) == ["# 2026-Q1 Review", "## X ## y %%s1%%"]
    assert text.count("%%s1%%") == 2 and "%%s9%%" not in text
    assert '*Lands: at the end of the text under "X ## y" (level 3)*' in text.splitlines()


def test_a_hostile_review_heading_yields_one_review_id():
    text, _ = rd.render_document(_doc_input(sections=[_part(placement="review")], review_heading="A %%review%%"))
    assert text.count("%%review%%") == 1 and "## A %%review%%" in text.splitlines()
    assert '*Lands: as the section "A" inside "Reflections"*' in text.splitlines()
    assert '*Lands: in the section "A" under "Goals"*' in text.splitlines()


@pytest.mark.parametrize("heading,shown", [
    ("Habits %% fold %%", "Habits"),
    ("Learnings of the Month  %% fold %%", "Learnings of the Month"),
])
def test_a_folded_template_heading_renders_without_its_comment(heading, shown):
    part = rs.SectionPart(key="s1", heading=heading, placement="before",
                          landing=rs.Landing(heading=heading, level=2, parent=heading), items=[])
    lines = rd.render_document(_doc_input(sections=[part]))[0].splitlines()
    assert f"## {shown} %%s1%%" in lines
    assert f'*Lands: before "{shown}" (level 2, under "{shown}")*' in lines
    assert part.heading == heading and part.landing.heading == heading      # display only


def test_a_hostile_parent_and_anchor_in_the_landing_lines():
    part = rs.SectionPart(key="s1", heading="Goals", placement="under",
                          landing=rs.Landing(heading="Goals", level=3, parent="P\n- [x] q %%t9%%"),
                          items=[{"text": "a", "links": []}])
    analysis = _part("s2", placement="review", items=[{"text": "b", "links": []}])
    text, _ = rd.render_document(_doc_input(sections=[part, analysis], anchor="R %%s7%%\n## z"))
    lines = text.splitlines()
    body = lines[lines.index("## Goals %%s1%%"):]          # the callout: test_a_hostile_anchor_forges_nothing_…
    assert '*Lands: right under "Goals" (level 3, under "P - [x] q")*' in body
    assert '*Lands: as the section "Tomo Review" inside "R ## z"*' in body
    assert "%%t9%%" not in text and "%%s7%%" not in "\n".join(body)
    assert not any(ln.startswith("- [x] q") or ln == "## z" for ln in body)


@pytest.mark.parametrize("raw,shown", [
    ("a %%s1", "a %s1"), ("%%%review%%%", "%"), ("  x \t\r\n y  ", "x y"), ("[[Link]] h", "[[Link]] h"),
])
def test_display_heading_leaves_no_id_able_percent_pair(raw, shown):
    assert rs.display_heading(raw) == shown and "%%" not in rs.display_heading(raw)


def test_a_hostile_anchor_forges_nothing_in_the_mapped_document():
    text, _ = rd.render_document(_doc_input(sections=[_part(items=[{"text": "a", "links": []}])],
                                            anchor="R %%s7%%\n## z"))
    assert "%%s7%%" not in text and "## z" not in text.splitlines()
    assert '> [!info] Target: [[2026-Q1]] (exists) · inside "R ## z"' in text.splitlines()


def test_a_folded_anchor_shows_without_its_comment_in_the_mapped_callout():
    text, _ = rd.render_document(_doc_input(sections=[_part()], anchor="Organisation %% fold %%"))
    assert '> [!info] Target: [[2026-Q1]] (exists) · inside "Organisation"' in text.splitlines()


def test_the_unmapped_callout_keeps_the_anchor_raw_as_spec_045():
    text, _ = rd.render_document(_doc_input(anchor="R %%s7%%\n## z"))
    lines = text.splitlines()
    assert lines[lines.index("# 2026-Q1 Review") + 1:][:2] == ['> [!info] Target: [[2026-Q1]] (exists) · inside "R %%s7%%',
                                                              '## z"']

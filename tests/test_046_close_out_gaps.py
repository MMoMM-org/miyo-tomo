#!/usr/bin/env python3
# version: 0.1.0
"""test_046_close_out_gaps.py — criterion parts of spec 046 that no test could fail (T6.4 close-out).

Each test names the PRD criterion part and the mechanism it falsifies; each was proven RED by that mutation
in an isolated export of HEAD, with every review and spec 046 test file green under it (close-out.md §3):
- F1-AC1 (quarter): a mapping never narrows what a quarter reads; the mapped read equals the unmapped one
  once ``sections`` is popped — falsifies a quarter-only drop of a level in ``review-read.py``.
- F1-AC10 (quarter): without a mapping the quarter document holds the spec 045 groups exactly, each empty one
  with its nothing-found line — falsifies ``review_sections.group_parts`` leaving empty groups out of a quarter.
- F6-AC6 (habits): a quarter's habits are computed from the tracker values of all three months — falsifies
  ``review-doc.py`` leaving the habits out for a quarter.
- F3-AC1 (mapped header): a mapped document's info callout still names the notes not read and the days partly
  read — falsifies ``review_doc._callout`` dropping them when a mapping is present.
- F7-AC2 (rows file): after a template correction the rows ``match`` keeps for ``setup-input`` come from the
  corrected template only — falsifies ``review_match`` carrying the earlier template's rows forward.
- F2-AC11 (delivery): a mapped row whose landing is off limits stops at delivery planning too, not only at
  setup — falsifies ``review_actions._sectioned`` not handing ``setup.off_limits`` to the section planner.
- F2-AC11 (reading): an off-limits mark never narrows what is read; a monthly note's own section stays a source
  of the quarter — falsifies the period sources leaving marked own sections out.
- F4-AC7 (delivered file): the readable instructions ``deliver`` writes carry every section's block and its
  heading, and on a re-run both markers of each replace — falsifies ``review_delivery.set_md`` rendering
  fewer actions than the set holds.

All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from e2e_046_sections_walk import KINDS  # noqa: E402
from e2e_046_sections_walk import proposals as walk_proposals  # noqa: E402
from lib import review_delivery as rdl  # noqa: E402
from lib import review_read_parts as rp  # noqa: E402
from review_e2e_walk import INBOX  # noqa: E402
from review_period_fixtures import quarter_vault  # noqa: E402
from test_046_t4_2_doc_sections import WEEK_PROPS, mapped_week  # noqa: E402
from test_046_t4_2_doc_sections import body_of as section_body_of  # noqa: E402
from test_046_t4_2_doc_sections import inst as section_inst  # noqa: E402
from test_046_t4_2_doc_sections import script as section_script  # noqa: E402
from test_046_t4_2_doc_sections import write as section_write  # noqa: E402
from test_046_t4_5_quarter_read import DAYS, PROPS, body_of, inst, quarter_read, script, write  # noqa: E402
from test_046_t5_2_new_note_sections import EXISTING, OWN  # noqa: E402
from test_046_t5_2_new_note_sections import mapped as mapped_setup  # noqa: E402
from test_046_t5_2_new_note_sections import plan as review_plan  # noqa: E402
from test_046_t6_2_e2e_sections import walk  # noqa: E402
from test_review_doc import _config, _day  # noqa: E402
from test_review_read import ROWS as READ_ROWS  # noqa: E402
from test_review_read import _edit_config, _quarter_setup, _run, instance, mod  # noqa: E402
from test_review_session_sections import _config as session_config  # noqa: E402
from test_review_session_sections import _match, _rows_file, _vault  # noqa: E402
from test_review_session_sections import instance as session_instance  # noqa: E402
from test_review_session_sections import mod as session_mod  # noqa: E402

# pytest fixtures the tests below request by these names
FIXTURES = (inst, script, instance, mod, section_inst, section_script, session_instance, session_mod, walk)


# ---------------------------------------------------------------- F1-AC1: a quarter read is never narrowed

def _quarter_read_dict(mod, instance, monkeypatch, capsys) -> dict:
    code, out, _ = _run(mod, monkeypatch, capsys, ["--period", "2026-Q1", "--kind", "quarter"], quarter_vault())
    assert code == 0 and out["status"] == "ok"
    return rp.load(instance / "tomo-tmp" / "review" / "2026-Q1_review")


def test_a_mapped_quarter_reads_the_same_days_weekly_and_monthly_notes_as_an_unmapped_one(mod, instance,
                                                                                          monkeypatch, capsys):
    """F1-AC1 "a mapping adds what Tomo looks for and never narrows what it reads", for the quarter (the
    month has its own test in test_review_read.py)."""
    _quarter_setup(instance)
    unmapped = _quarter_read_dict(mod, instance, monkeypatch, capsys)

    def edit(cfg):
        cfg.setdefault("templates", {})["mapping"] = {"quarterly": "t_quarterly.md"}
        cfg["review"]["quarterly"]["sections"] = {"t_quarterly.md": READ_ROWS}
    _edit_config(instance, edit)
    mapped = _quarter_read_dict(mod, instance, monkeypatch, capsys)

    assert "sections" not in unmapped
    assert [s["key"] for s in mapped.pop("sections")] == ["s1", "s7"]
    assert unmapped["days"] and unmapped["weekly"] and unmapped["monthly"], "the comparison covers every level"
    assert mapped == unmapped


# ---------------------------------------------------------------- F1-AC10: the unmapped quarter document

def test_without_a_mapping_the_quarter_document_holds_every_group_each_empty_one_saying_so(script, inst,
                                                                                           monkeypatch, capsys):
    """F1-AC10 "for a quarter with the groups of F6-AC4": the spec 045 groups in their order, the month's
    weekly marks replaced by the monthly marks, an empty group shown with one nothing-found line (spec 045
    F4-AC4), never left out."""
    out, fake = write(script, monkeypatch, capsys, inst, PROPS)
    assert out["status"] == "written", out
    body = body_of(fake)
    heads = [ln for ln in body if ln.startswith("## ")]
    assert heads == ["## Erledigt", "## Offen", "## Wiederkehrende Themen", "## Vault-Wachstum",
                     "## Nur in den Monatsreviews", "## Nicht in den Monatsreviews"]
    after = {h: body[body.index(h) + 1] for h in heads}
    for empty in ("## Offen", "## Wiederkehrende Themen", "## Vault-Wachstum", "## Nicht in den Monatsreviews"):
        assert after[empty] == "- nichts gefunden", empty


# ---------------------------------------------------------------- F6-AC6: habits for a quarter

def test_a_quarter_computes_the_habits_from_the_trackers_of_all_three_months(script, inst, monkeypatch, capsys):
    """F6-AC6 "spec 045's … habits … apply as for a month": the script-computed habit line counts the tracker
    days of every month part of the quarter."""
    _config(inst, trackers=True)
    path = inst / "config" / "vault-config.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["concepts"]["calendar"]["granularities"]["quarterly"] = {"enabled": True, "path": "Calendar/304 Quarterly/"}
    cfg["naming"]["calendar_patterns"]["quarterly"] = "YYYY-[Q]Q"
    cfg["review"]["quarterly"] = {"heading": "Tomo Review", "place": {"anchor": "Reflections", "placement": "inside"},
                                  "own_sections": ["Reflections"]}
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    read = quarter_read()
    read["days"] = [_day(d, Sport="ja") for d in DAYS]
    out, fake = write(script, monkeypatch, capsys, inst, PROPS, read=read)
    assert out["status"] == "written", out
    body = body_of(fake)
    assert "## Gewohnheiten" in body
    habit_lines = body[body.index("## Gewohnheiten") + 1:]
    habit_lines = habit_lines[:next((i for i, ln in enumerate(habit_lines) if ln.startswith("## ")),
                                    len(habit_lines))]
    assert any(ln.startswith("- [x] Sport") and f" {len(DAYS)} " in ln for ln in habit_lines), habit_lines


# ---------------------------------------------------------------- F3-AC1: read and missing, mapped


def test_a_mapped_document_still_names_the_notes_not_read_and_the_days_partly_read(section_script, section_inst,
                                                                                   monkeypatch, capsys):
    """F3-AC1 "the spec 045 parts of the document (period, what was read and missing, …) stay" with a mapping:
    the info callout keeps the not-read notes and the partly read days."""
    read = mapped_week()
    read["not_read"] = ["Notes/Gone Note.md"]
    read["days"][1]["partly_read"] = True
    partly_day = read["days"][1]["date"]
    code, out, fake = section_write(section_script, monkeypatch, capsys, section_inst, read, WEEK_PROPS)
    assert code == 0 and out["status"] == "written", out
    [callout] = [ln for ln in section_body_of(fake) if ln.startswith("> [!info]")]
    assert "nicht gelesen: Gone Note" in callout
    assert f"teilweise gelesen: {partly_day}" in callout


# ---------------------------------------------------------------- F7-AC2: the rows after a correction


EARLIER_HEADINGS = {"Habits", "Overview", "In my own words", "What Went Well This Week?", "Lessons"}


def test_after_a_template_correction_the_rows_file_holds_only_the_new_templates_rows(session_mod, session_instance,
                                                                                    monkeypatch, capsys):
    """F7-AC2 "no row from the earlier template remains": the rows `match` shows and keeps as evidence for
    `setup-input` after a correction come from the corrected template only; a leaked earlier row would also be
    named as "dropped" again after the next correction."""
    session_config(session_instance)
    _match(session_mod, monkeypatch, capsys, _vault(), "--template", "t_week_sections")
    assert {r["heading"] for r in _rows_file(session_instance)["rows"]} & EARLIER_HEADINGS, "the first rows"
    out = _match(session_mod, monkeypatch, capsys, _vault(), "--template", "t_week_plain")
    rows = _rows_file(session_instance)["rows"]
    assert rows and {r["heading"] for r in rows} <= {"Theme", "Reflections"}, rows
    assert {c["heading_key"]["heading"] for c in out["sections"]["candidates"]} <= {"Theme", "Reflections"}


# ---------------------------------------------------------------- F4-AC7: the delivered readable instructions


def _delivered(walk, k) -> tuple:
    assert walk.preview(k.stem)["status"] == "ok"
    assert walk.deliver(k.stem)["status"] == "delivered"
    return walk.set_json(k.stem)["actions"], walk.doc(f"{INBOX}{k.stem}_instructions.md")


def test_the_delivered_readable_instructions_carry_every_sections_block_first_and_on_a_rerun(walk):
    """F4-AC7 through `deliver` (the readable file it writes beside the set, not `render_md` alone): per mapped
    section the block ready to copy and its heading; on a re-run the replace names both of Tomo's markers."""
    k = KINDS["week"]
    walk.setup_mapped(k)
    assert walk.pass1(k.period, k.kind, walk_proposals(k, "v1"))["status"] == "written"
    walk.approve(k.doc)
    actions, md = _delivered(walk, k)
    section_actions = [a for a in actions if a["content"].startswith("%% tomo:s")]
    assert len(section_actions) == len(k.rows)
    for act in section_actions:
        assert act["anchor"]["value"] in md
        for line in act["content"].splitlines():
            assert line in md.splitlines(), line
    assert walk.hashi_apply(k.stem) == ["applied"] * len(actions)
    assert walk.pass1(k.period, k.kind, walk_proposals(k, "v2"))["problems"] == ["review-exists"]
    assert walk.replace(k.stem, "--confirm")["status"] == "replaced"
    walk.approve(k.doc)
    actions, md = _delivered(walk, k)
    replaces = [a for a in actions if a["action"] == "replace_between_markers"]
    assert replaces, actions
    for act in replaces:
        assert act["start_marker"] in md and act["end_marker"] in md
        for line in act["content"].splitlines():
            assert line in md.splitlines(), line


# ---------------------------------------------------------------- F2-AC11: off limits at delivery and in the read

OFF_HIGHLIGHTS = [{"heading": "Highlights", "level": 2, "parent": None, "occurrence": 1, "with_subsections": False}]


def test_a_mapped_row_landing_off_limits_stops_the_delivery_of_an_existing_and_a_new_note():
    """F2-AC11 "Tomo never writes into that section, whatever the mapping says": a row saved before the mark,
    or a hand-edited config, still never lands there; the delivery plan stops `landing-off-limits` (refusing)."""
    setup = mapped_setup(anchor=OWN, placement="inside", own_sections=[], off_limits=OFF_HIGHLIGHTS)
    for target_text in (EXISTING, None):
        p = review_plan(target_text=target_text, setup=setup)
        [s1] = [s for s in p.sections if s.key == "s1"]
        assert s1.stop == "landing-off-limits", (target_text is None, s1)
        assert "landing-off-limits" in rdl.classify(p)[0]
        assert not any((a.get("anchor") or {}).get("value") == "Highlights" for a in p.actions)


def test_an_off_limits_mark_never_narrows_the_read_a_monthly_own_section_stays_a_source(mod, instance,
                                                                                       monkeypatch, capsys):
    """F2-AC11 "Tomo may still read the user's own text there as a source": the same quarter read with and
    without off-limits marks on the monthly and the quarterly template is the same, own sections included."""
    _quarter_setup(instance)
    plain = _quarter_read_dict(mod, instance, monkeypatch, capsys)

    def edit(cfg):
        cfg.setdefault("templates", {})["mapping"] = {"monthly": "t_monthly.md", "quarterly": "t_quarterly.md"}
        cfg["review"]["monthly"]["off_limits"] = {"t_monthly.md": OFF_HIGHLIGHTS}
        cfg["review"]["quarterly"]["off_limits"] = {"t_quarterly.md": OFF_HIGHLIGHTS}
    _edit_config(instance, edit)
    marked = _quarter_read_dict(mod, instance, monkeypatch, capsys)
    assert any("Highlights" in (m.get("month_text") or {}) for m in plain["monthly"]), "the own section is read"
    assert marked == plain

#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t5_2_new_note_sections.py — new notes, analysis rows and the "Tomo Review" interplay (046 T5.2).

PRD F4-AC5, F2-AC12, F2-AC7; SDD Runtime View / Complex Logic "New note", the off-limits landing
paragraph, Example "One section part", Error Handling (`landing-off-limits`, `review-section-kept`),
ADR-8, ADR-12. The approved review is built the way production builds it: review_doc.render_document
with section parts → Approved ticked → review_doc_parse.parse_document with pass1_sections →
ParsedDoc.approved_review(). Mechanisms pinned:

- a new note from a plain template gets each block spliced at Hashi's insertion line with both
  markers, so the next run's plan_section finds a replace (round trip);
- a heading the new note lacks, holds twice, or holds only inside a Templater span routes the section
  to "Tomo Review"; the `_tomo` variant is used first (spec 045 ADR-8); a plain note routes them all;
- analysis rows land as `<level+1>` sub-headings inside "Tomo Review" and never in their own section;
  the habits stay in "Tomo Review"; mapping order, then the groups;
- on an existing note sections are planned into ReviewPlan.sections, `choice=review` routes, and a
  new "Tomo Review" passes its insertion index as `review_at`;
- the "Tomo Review" placement passes the off-limits landing check (else `landing-off-limits`);
- `review-section-kept` when a re-run leaves nothing for an earlier "Tomo Review" section;
- configured section keys are not `unlanded`; `nothing-to-deliver` counts sections;
- Pass 1: `review-doc.py write` marks the routed parts of a new note, landing line and divider.

All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib import review_actions as ra  # noqa: E402
from lib import review_delivery as rdl  # noqa: E402
from lib import review_doc as rd  # noqa: E402
from lib import review_doc_parse as rdp  # noqa: E402
from lib import review_section_plan as rsp  # noqa: E402
from lib import review_sections as rs  # noqa: E402
from review_deliver_helpers import SCHEMAS, schema_errors  # noqa: E402
from review_fake_vault import ReviewFakeVault  # noqa: E402
from test_046_t4_2_doc_sections import (  # noqa: E402
    TEMPLATE, body_of, definitions_of, inst, map_config, script, section, write,
)
from test_review_doc import WEEKLY, item, week_read  # noqa: E402
from test_review_instructions import GENERATED, HEADING, MARKER, OWN, PERIOD, TARGET, setup  # noqa: E402

__all__ = ["inst", "script"]

DONE = "Woche aufgeräumt ([[2026-03-28]])"


def row(rid, heading, placement, level=2, parent=None) -> dict:
    return {"id": rid, "heading": heading, "level": level, "parent": parent, "occurrence": 1,
            "description": f"what {heading} asks", "placement": placement}


ROWS = [row("s1", "Highlights", "end"), row("s2", "Energy and Sleep", "review"),
        row("s3", "Gone", "under"), row("s4", "Plans", "before")]
ITEMS = {"s1": ["Steuer abgeschickt"], "s2": ["Schlaf kurz"], "s3": ["Verloren"], "s4": ["Plan A"]}
TEMPLATE_TEXT = "\n".join([
    "# {{title}}", "", "## Highlights", "own text", "", "## Energy and Sleep", "```dataview", "TABLE x", "```", "",
    f"## {OWN}", "meine Worte", "", "## Plans", "plan text"]) + "\n"


def approved(rows=ROWS, items=ITEMS, groups=None, habits=True) -> dict:
    """The ApprovedReview record of a mapped week, rendered and parsed as production does."""
    groups = {"done": [{"text": "Woche aufgeräumt", "links": ["2026-03-28"]}]} if groups is None else groups
    if habits:
        groups = {**groups, "habits": [{"text": "Sport: 6 von 7 Tagen", "links": []}]}
    parts = rs.parts({r["id"]: r for r in rows}, rows,
                     {k: [{"text": t, "links": ["2026-03-24"]} for t in v] for k, v in items.items()})
    inp = rd.DocInput(period_name=PERIOD, kind="week", language="de", stem=f"{PERIOD}_review", run_id="r-test",
                      target=TARGET, target_exists=True, target_found_elsewhere=None, anchor=OWN,
                      placement="before", not_read=[], partly_read=[], month_groups=False, groups=groups,
                      sections=parts, review_heading=HEADING)
    text, counts = rd.render_document(inp)
    text = text.replace("- [ ] Approved", "- [x] Approved", 1)
    meta = [{"key": p.key, "count": counts[p.key], "empty": p.empty} for p in parts]
    return rdp.parse_document(text, pass1_links=rdp.link_stems(text), pass1_sections=meta).approved_review()


def mapped(rows=ROWS, **kw):
    return setup(sections=rows, template="t_week.md", **kw)


def plan(review=None, target_text=None, template=None, rows=ROWS, choices=None, **kw) -> ra.ReviewPlan:
    s = kw.pop("setup", None) or mapped(rows)
    return ra.build_review_plan(review or approved(rows), s, ra.Target(TARGET, target_text),
                                template if template is not None else ra.Template(raw=TEMPLATE_TEXT),
                                choices=choices, run_id="r-test", generated=GENERATED, **kw)


def body(p: ra.ReviewPlan) -> list:
    text = p.note_text
    return text.split("---\n", 2)[2].split("\n") if text.startswith("---\n") else text.split("\n")


def block(key, *texts) -> list:
    return [rsp.start_marker(key, PERIOD), *(f"- {t} ([[2026-03-24]])" for t in texts),
            rsp.end_marker(key, PERIOD), ""]


def modes(p: ra.ReviewPlan) -> dict:
    return {s.key: s.mode for s in p.sections}


# ---------------------------------------------------------------- a new note

def test_a_new_note_from_a_plain_template_gets_every_block_at_hashis_line_with_both_markers():
    p = plan()
    assert p.mode == "new-note" and p.problems == [], p.problems
    assert modes(p) == {"s1": "insert", "s3": "review", "s4": "insert"}
    assert body(p) == [
        "# {{title}}", "", "## Highlights", "own text", "", *block("s1", "Steuer abgeschickt"),
        "## Energy and Sleep", "```dataview", "TABLE x", "```", "",
        f"## {HEADING}", MARKER, "### Energy and Sleep", "- Schlaf kurz ([[2026-03-24]])",
        "### Gone", "- Verloren ([[2026-03-24]])", "### Erledigt", f"- {DONE}",
        "### Gewohnheiten", "- Sport: 6 von 7 Tagen", "",
        f"## {OWN}", "meine Worte", "", *block("s4", "Plan A"), "## Plans", "plan text", ""]
    [action] = p.actions
    assert action["action"] == "move_note"
    doc = ra.build_review_instruction_set(p, stem=f"{PERIOD}_review", generated=GENERATED, profile="miyo")
    for schema in SCHEMAS:
        assert schema_errors(doc, schema) == []


def test_the_next_run_finds_every_spliced_block_and_replaces_it():
    note = plan().note_text
    again = plan(target_text=note)
    assert again.mode == "replace" and again.problems == [], again.problems
    assert modes(again) == {"s1": "replace", "s3": "missing", "s4": "replace"}
    assert [a["action"] for a in again.actions] == ["replace_section"]


def test_a_heading_the_new_note_lacks_routes_and_never_leaves_a_marker():
    p = plan()
    assert not any("tomo:s3" in ln or "tomo:s2" in ln for ln in body(p))


def test_a_heading_held_twice_by_the_template_routes():
    twice = TEMPLATE_TEXT + "## Highlights\n"
    p = plan(template=ra.Template(raw=twice))
    assert modes(p)["s1"] == "review" and "### Highlights" in body(p)


def test_a_heading_only_inside_templater_code_routes_and_the_variant_comes_first():
    raw = TEMPLATE_TEXT.replace("## Plans\n", "<%*\n## Plans\n%>\n")
    p = plan(template=ra.Template(raw=raw))
    assert modes(p)["s4"] == "review" and p.templater_hint is True
    assert "### Plans" in body(p) and not any("tomo:s4" in ln for ln in body(p))
    variant = plan(template=ra.Template(raw=raw, variant=TEMPLATE_TEXT),
                   setup=mapped(template_variant="t_week_tomo.md"))
    assert modes(variant)["s4"] == "insert" and variant.templater_hint is False


def test_a_plain_note_routes_every_section_placed_in_the_note():
    p = plan(template=ra.Template())
    assert modes(p) == {"s1": "review", "s3": "review", "s4": "review"}
    heads = [ln for ln in body(p) if ln.startswith("### ")]
    assert heads == ["### Highlights", "### Energy and Sleep", "### Gone", "### Plans", "### Erledigt",
                     "### Gewohnheiten"]


def test_a_skip_choice_drops_a_routed_section():
    p = plan(choices={"s3": "skip"})
    assert modes(p)["s3"] == "skip" and "### Gone" not in body(p)


# ---------------------------------------------------------------- analysis rows and the habits

EXISTING = TEMPLATE_TEXT.replace("{{title}}", PERIOD)


def test_analysis_rows_land_as_level_plus_one_sub_headings_inside_tomo_review_never_in_their_section():
    p = plan(target_text=EXISTING, setup=mapped(anchor=OWN, placement="inside", own_sections=[]))
    assert p.problems == [], p.problems
    content = p.actions[0]["content"].split("\n")
    assert content[:4] == [f"### {HEADING}", MARKER, "#### Energy and Sleep", "- Schlaf kurz ([[2026-03-24]])"]
    assert not any(s.key == "s2" for s in p.sections)
    assert p.actions[0]["anchor"]["value"] == OWN


def test_the_habits_stay_in_tomo_review_with_a_mapping_after_the_sections():
    content = plan(target_text=EXISTING).actions[0]["content"].split("\n")
    assert content.index("### Energy and Sleep") < content.index("### Erledigt") < content.index("### Gewohnheiten")


def test_sub_headings_are_display_neutralised():
    rows = [row("s2", "Energy  %%fold%% and Sleep", "review")]
    content = plan(review=approved(rows, {"s2": ["x"]}), target_text=EXISTING, rows=rows).actions[0]["content"]
    assert "### Energy and Sleep\n" in content and "%%fold" not in content


# ---------------------------------------------------------------- an existing note

def test_an_existing_note_plans_its_sections_and_routes_only_on_the_review_choice():
    note = EXISTING.replace("## Gone\n", "")
    p = plan(target_text=note)
    assert modes(p) == {"s1": "insert", "s3": "missing", "s4": "insert"}
    assert "### Gone" not in p.actions[0]["content"]
    routed = plan(target_text=note, choices={"s3": "review"})
    assert modes(routed)["s3"] == "review" and "### Gone\n- Verloren" in routed.actions[0]["content"]


def test_a_new_tomo_review_passes_its_insertion_index_as_review_at():
    rows = [row("s4", "Plans", "before")]
    s = mapped(rows, anchor="Plans", placement="before")
    p = plan(review=approved(rows, {"s4": ["Plan A"]}), target_text=EXISTING, rows=rows, setup=s)
    assert modes(p) == {"s4": "in-review"}
    alone = plan(review=approved(rows, {"s4": ["Plan A"]}, groups={}, habits=False), target_text=EXISTING,
                 rows=rows, setup=s)
    assert modes(alone) == {"s4": "insert"} and alone.actions == [] and alone.problems == []


# ---------------------------------------------------------------- the landing check of the "Tomo Review" place

OFF_OWN = [{"heading": OWN, "level": 2, "parent": None, "occurrence": 1, "with_subsections": False}]


@pytest.mark.parametrize("target_text", [EXISTING, None])
def test_tomo_review_inside_an_off_limits_section_is_landing_off_limits(target_text):
    s = mapped(anchor=OWN, placement="inside", own_sections=[], off_limits=OFF_OWN)
    p = plan(target_text=target_text, setup=s)
    assert p.problems == ["landing-off-limits"] and p.actions == []


def test_tomo_review_before_the_heading_after_an_off_limits_body_is_landing_off_limits():
    s = mapped(anchor="Plans", placement="before", off_limits=OFF_OWN)
    assert plan(target_text=EXISTING, setup=s).problems == ["landing-off-limits"]
    assert plan(target_text=EXISTING, setup=mapped(anchor="Plans", placement="before")).problems == []


def test_landing_off_limits_refuses_at_delivery():
    p = plan(target_text=EXISTING, setup=mapped(anchor=OWN, placement="inside", own_sections=[], off_limits=OFF_OWN))
    assert rdl.classify(p)[0] == ["landing-off-limits"]


# ---------------------------------------------------------------- a re-run with nothing for Tomo Review

def test_review_section_kept_when_a_rerun_leaves_nothing_for_an_earlier_tomo_review():
    rows = [row("s1", "Highlights", "end")]
    note = EXISTING.replace(f"## {OWN}\n", f"## {HEADING}\n{MARKER}\n- alt\n\n## {OWN}\n")
    p = plan(review=approved(rows, {"s1": ["neu"]}, groups={}, habits=False), target_text=note, rows=rows)
    assert p.mode == "replace" and p.actions == [] and p.problems == []
    assert p.notices == ["review-section-kept"] and rdl.classify(p)[0] == []      # a notice, never a refusal
    assert modes(p) == {"s1": "insert"}


def test_without_a_mapping_an_empty_rerun_stays_nothing_to_deliver():
    note = EXISTING.replace(f"## {OWN}\n", f"## {HEADING}\n{MARKER}\n- alt\n\n## {OWN}\n")
    review = approved([], {}, groups={}, habits=False)
    p = ra.build_review_plan(review, setup(), ra.Target(TARGET, note), run_id="r", generated=GENERATED)
    assert p.problems == ["nothing-to-deliver"] and p.notices == []


# ---------------------------------------------------------------- landed, unlanded, nothing to deliver

def test_configured_section_keys_are_not_unlanded_and_count_against_nothing_to_deliver():
    rows = [row("s1", "Highlights", "end")]
    p = plan(review=approved(rows, {"s1": ["neu"]}, groups={}, habits=False), target_text=EXISTING, rows=rows)
    assert p.unlanded == 0 and p.problems == []
    empty = plan(review=approved(rows, {}, groups={}, habits=False), target_text=EXISTING, rows=rows)
    assert empty.problems == ["nothing-to-deliver"]


# ---------------------------------------------------------------- Pass 1: the landing line of a new note

def test_pass1_names_the_routed_section_of_a_new_note_in_its_landing_line(script, inst, monkeypatch, capsys):
    rows = [row("s1", "Highlights", "end"), row("s3", "Gone", "under")]
    map_config(inst, rows, trackers=False)
    props = {"language": "de", "groups": {}, "sections": [section("s1", item("a", "2026-03-24")),
                                                          section("s3", item("b", "2026-03-25"))]}
    fake = ReviewFakeVault({TEMPLATE: TEMPLATE_TEXT})
    _, out, fake = write(script, monkeypatch, capsys, inst, week_read(sections=definitions_of(rows)), props, fake)
    assert out["status"] == "written" and out["target_exists"] is False, out
    lines = body_of(fake)
    assert "*Landet: am Ende von „Highlights“ (Ebene 2)*" in lines
    assert "*Landet: im Abschnitt „Tomo Review“ unter „Gone“*" in lines
    assert "## Tomo Review %%review%%" in lines                  # a routed part alone opens the divider


def test_pass1_routes_every_section_of_a_new_note_without_a_template(script, inst, monkeypatch, capsys):
    rows = [row("s1", "Highlights", "end")]
    map_config(inst, rows, trackers=False)
    props = {"language": "de", "groups": {}, "sections": [section("s1", item("a", "2026-03-24"))]}
    _, _, fake = write(script, monkeypatch, capsys, inst, week_read(sections=definitions_of(rows)), props,
                       ReviewFakeVault({}))
    assert "*Landet: im Abschnitt „Tomo Review“ unter „Highlights“*" in body_of(fake)


def test_pass1_leaves_an_existing_note_unrouted(script, inst, monkeypatch, capsys):
    rows = [row("s3", "Gone", "under")]
    map_config(inst, rows, trackers=False)
    props = {"language": "de", "groups": {}, "sections": [section("s3", item("b", "2026-03-25"))]}
    fake = ReviewFakeVault({f"{WEEKLY}2026-W13.md": "# W13\n", TEMPLATE: TEMPLATE_TEXT})
    _, _, fake = write(script, monkeypatch, capsys, inst, week_read(sections=definitions_of(rows)), props, fake)
    assert "*Landet: direkt unter „Gone“ (Ebene 2)*" in body_of(fake)
    assert TEMPLATE not in fake.paths_seen


def test_an_escaped_sub_part_line_is_counted_once_also_when_the_sections_are_planned_twice():
    rows = [row("s2", "Energy and Sleep", "review"), row("s4", "Plans", "before")]
    review = approved(rows, {"s2": ["x"], "s4": ["Plan A"]}, groups={}, habits=False)
    review["groups"]["s2"][0]["text"] = "quote %% tomo:s4 2026-W13 %% here"   # set on the record directly
    p = plan(review=review, target_text=EXISTING, rows=rows)
    assert "quote %% tomo\\:s4 2026-W13 %% here" in p.actions[0]["content"]
    assert p.escaped_lines == 1


def test_a_block_at_tomo_reviews_own_index_goes_above_it_and_the_next_run_still_replaces_it():
    rows = [row("s1", "Highlights", "end")]
    s = mapped(rows, anchor="Energy and Sleep", placement="before")
    p = plan(review=approved(rows, {"s1": ["neu"]}), rows=rows, setup=s)
    lines = body(p)
    assert lines.index(rsp.end_marker("s1", PERIOD)) < lines.index(f"## {HEADING}") < lines.index("## Energy and Sleep")
    again = plan(review=approved(rows, {"s1": ["neu"]}), target_text=p.note_text, rows=rows, setup=s)
    assert modes(again) == {"s1": "replace"} and again.problems == []

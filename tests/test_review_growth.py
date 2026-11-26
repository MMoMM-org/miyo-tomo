#!/usr/bin/env python3
# version: 0.2.0
"""test_review_growth.py — the "Vault growth" group the script builds (spec 047 T9.3, F-R1-3; PRD F2-AC1).

Owner decision 2026-11-26 (T9.2 R1b/R1c): `review-doc.py write` builds the group from the created notes of the
read and the digests' growth candidates; the proposer no longer proposes `growth`. Pinned here:

- every created note exactly once, grouped as the candidates group them: the candidate's text, its notes as
  links, then the dailies of their creation days (`group`, and end to end through `write`);
- a created note in no candidate gets an item of its own: the note's link as its text, its creation day's daily
  as its link when the day has one;
- a note a section item mentions stays in the group;
- a `growth` group in proposals.json is not rendered, rejected nothing and fails nothing;
- no created note → no item (the empty group renders as before: "nothing found" unmapped);
- candidates of several units (a month) merged, no note twice; candidates of a failed unit or another read
  are not used, their notes get items of their own;
- the English and the German heading.
- F-R1-4 (owner 2026-11-26): after the created-note items, "MOCs changed" linking every changed MOC, then
  "MOCs newly linked" linking the MOCs a created note links and that did not change; each MOC once, none that is
  a created note; links in path order; EN and DE label words; MOC changes alone still give the group; the
  document's MOC lines hold label words and links only.

All data is synthetic.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import MONTH, MONTH_DOC, MONTH_PERIOD, MONTH_STEM, WEEK, WEEK_DOC, WEEK_PERIOD, WEEK_STEM  # noqa: E402
from review_privacy_fixture import CONFIG, PRP, propose_from_inputs, proposals  # noqa: E402
from test_047_baseline_e2e import MONTH_SECTION_ROW, Case, make_walk  # noqa: E402
from lib import review_growth as rgw  # noqa: E402

__all__ = ["make_walk"]                            # the baseline's walk fixture, used by name

READ_ID = "2026-11-26T09-00-00Z-a1b2c3"
DAILY = "Calendar/Daily/"


def _read(created: dict, days: List[str], *, units=None, not_condensed=None) -> dict:
    """A loaded read: created {path: day}, a daily on each of ``days``, ``condensed`` units {unit: state}."""
    return {"growth": {"created": [{"path": p, "links": [], "day": d} for p, d in sorted(created.items())],
                       "mocs_changed": [], "mocs_linked_by_new": []},
            "days": [{"date": d, "dailies": [f"{DAILY}{d}.md"]} for d in days],
            "not_condensed": not_condensed or [],
            "condensed": {"read_id": READ_ID, "units": {u: {"state": s, "attempts": 1}
                                                         for u, s in (units or {}).items()}}}


def _cand(text: str, *notes: str) -> dict:
    return {"text": text, "notes": list(notes)}


# ── group: the items ──

def test_every_created_note_is_in_the_group_once_with_its_candidate_text_and_creation_day():
    read = _read({"N/b.md": "2026-03-24", "N/a.md": "2026-03-24", "N/k.md": "2026-03-10"},
                 ["2026-03-10", "2026-03-24"])
    got = rgw.group(read, [_cand(f"bikes {PRP}", "N/b.md", "N/a.md"), _cand(f"kettle {PRP}", "N/k.md")])
    assert got == [{"text": f"kettle {PRP}", "links": ["k", "2026-03-10"]},
                   {"text": f"bikes {PRP}", "links": ["a", "b", "2026-03-24"]}]


def test_a_created_note_in_no_candidate_gets_an_item_of_its_own():
    read = _read({"N/a.md": "2026-03-24", "N/lone.md": "2026-03-24", "N/nodaily.md": "2026-03-12"},
                 ["2026-03-24"])
    got = rgw.group(read, [_cand("one", "N/a.md")])
    assert got == [{"text": "[[nodaily]]", "links": []},
                   {"text": "one", "links": ["a", "2026-03-24"]},
                   {"text": "[[lone]]", "links": ["2026-03-24"]}]


def test_candidates_of_several_units_are_merged_and_no_note_is_listed_twice():
    read = _read({"N/a.md": "2026-03-03", "N/b.md": "2026-03-24", "N/c.md": "2026-03-24"},
                 ["2026-03-03", "2026-03-24"])
    got = rgw.group(read, [_cand("w10", "N/a.md"), _cand("w13", "N/b.md", "N/a.md"), _cand("again", "N/b.md"),
                           _cand("not created", "N/old.md"), _cand("w13 more", "N/c.md")])
    notes = [link for item in got for link in item["links"] if not link.startswith("2026")]
    assert notes == ["a", "b", "c"]
    assert [item["text"] for item in got] == ["w10", "w13", "w13 more"]


def test_no_created_note_gives_no_item():
    assert rgw.group(_read({}, ["2026-03-24"]), [_cand("ghost", "N/x.md")]) == []


def test_two_created_notes_of_one_stem_link_by_path():
    read = _read({"A/same.md": "2026-03-24", "B/same.md": "2026-03-24", "B/other.md": "2026-03-24"}, [])
    got = rgw.group(read, [_cand("both", "A/same.md", "B/same.md", "B/other.md")])
    assert got == [{"text": "both", "links": ["A/same", "other", "B/same"]}]


def test_a_day_of_a_not_condensed_unit_links_no_daily():
    read = _read({"N/a.md": "2026-03-24"}, ["2026-03-24"], not_condensed=[{"unit": "2026-W13", "days": ["2026-03-24"]}])
    assert rgw.group(read, []) == [{"text": "[[a]]", "links": []}]


# ── candidates: the digests read ──

def _digest(stage: Path, unit: str, growth: list, read_id: str = READ_ID) -> None:
    (stage / "digests").mkdir(parents=True, exist_ok=True)
    (stage / "digests" / f"{unit}.json").write_text(json.dumps({"read_id": read_id, "growth": growth}),
                                                    encoding="utf-8")


def test_candidates_come_from_the_passed_units_of_this_read_only(tmp_path):
    read = _read({}, [], units={"2026-W10": "passed", "2026-W11": "failed", "2026-W12": "passed",
                                "2026-W13": "passed", "2026-W14": "passed"})
    _digest(tmp_path, "2026-W10", [{"text": "w10", "sources": ["2026-03-03"], "notes": ["N/a.md"]}])
    _digest(tmp_path, "2026-W11", [{"text": "failed unit", "sources": ["2026-03-10"], "notes": ["N/f.md"]}])
    _digest(tmp_path, "2026-W12", [{"text": "stale", "sources": ["2026-03-17"], "notes": ["N/s.md"]}], "other-read")
    (tmp_path / "digests" / "2026-W13.json").write_text("{broken", encoding="utf-8")
    _digest(tmp_path, "2026-W14", [{"text": "w14", "sources": ["2026-03-30"], "notes": ["N/z.md", "N/y.md"]}])
    assert rgw.candidates(tmp_path, read) == [_cand("w10", "N/a.md"), _cand("w14", "N/z.md", "N/y.md")]


def test_candidates_skip_a_passed_unit_with_no_digest_or_a_digest_that_is_not_an_object(tmp_path):
    read = _read({}, [], units={"2026-W10": "passed", "2026-W11": "passed", "2026-W12": "passed",
                                "2026-W13": "passed"})
    _digest(tmp_path, "2026-W10", [{"text": "w10", "sources": ["2026-03-03"], "notes": ["N/a.md"]}])
    # 2026-W11: passed, but no digest file
    (tmp_path / "digests" / "2026-W12.json").write_text("[]", encoding="utf-8")
    (tmp_path / "digests" / "2026-W13.json").write_text('"x"', encoding="utf-8")
    assert rgw.candidates(tmp_path, read) == [_cand("w10", "N/a.md")]


# ── end to end through review-doc.py write (a month, two units with created notes) ──

CREATED = {"Notes/Kettle descaling.md": "2026-03-10", "Notes/Shelf plan.md": "2026-03-12",   # 03-12: no daily
           "Notes/Bike chain.md": "2026-03-24", "Notes/Bike tyres.md": "2026-03-24"}
EXPECTED = ["- [x] created condensed ([[Kettle descaling]], [[2026-03-10]])",
            "- [x] [[Shelf plan]]",
            "- [x] created condensed ([[Bike chain]], [[Bike tyres]], [[2026-03-24]])"]


def _ms(day: str) -> int:
    return int(datetime.fromisoformat(f"{day}T12:00:00").timestamp() * 1000)


def _config(language: str = "en", mapped: bool = False) -> dict:
    out = copy.deepcopy(CONFIG)
    out["review"]["language"] = language
    if mapped:
        out["review"]["monthly"]["sections"] = {"t_month.md": [dict(MONTH_SECTION_ROW)]}
    return out


def _walk(make_walk, language="en", mapped=False):
    case = Case(MONTH, MONTH_PERIOD, MONTH_STEM, MONTH_DOC, True, lambda: _config(language, mapped),
                lambda: proposals(MONTH))
    w = make_walk(case)
    for path, day in CREATED.items():
        w.vault.files[path] = f"# {Path(path).stem}\nnew note\n"
        w.vault.created[path] = w.vault.modified[path] = _ms(day)
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    return w


def _group_lines(document: str, heading: str) -> List[str]:
    part = document.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]
    return [re.sub(r"\s*%%t\d+%%$", "", line) for line in part.split("\n") if line.startswith("- ")]


def test_write_builds_the_group_from_the_digests_and_ignores_a_proposed_growth_group(make_walk):
    w = _walk(make_walk)

    def proposer(props, stage, inputs):
        out = propose_from_inputs(props, stage, inputs)
        out["groups"]["growth"] = [{"text": f"stale growth {PRP}", "sources": ["2026-03-24"]},
                                   {"text": "", "sources": ["nowhere"]}]
        return out

    out = w.write(MONTH_STEM, MONTH, proposer=proposer)
    assert out["status"] == "written" and out["rejected"] == [] and out["counts"]["growth"] == 3, out
    document = w.doc(MONTH_DOC)
    assert _group_lines(document, "Vault growth") == EXPECTED
    assert "stale growth" not in document


def test_a_note_a_section_item_mentions_stays_in_the_group(make_walk):
    w = _walk(make_walk, mapped=True)
    props = proposals(MONTH)
    props["sections"] = [{"key": "s1", "items": [{"text": f"Bike chain {PRP}", "sources": ["2026-03-24"]}]}]
    out = w.write(MONTH_STEM, MONTH, props, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["counts"]["s1"] == 1 and out["counts"]["growth"] == 3, out
    document = w.doc(MONTH_DOC)
    assert re.search(rf"^- \[x\] Bike chain {PRP} \(\[\[2026-03-24\]\]\) %%t\d+%%$", document, re.M), document
    assert _group_lines(document, "Vault growth") == EXPECTED


def test_the_german_heading_holds_the_same_group(make_walk):
    w = _walk(make_walk, language="de")
    out = w.write(MONTH_STEM, MONTH, proposer=propose_from_inputs)
    assert out["status"] == "written", out
    document = w.doc(MONTH_DOC)
    assert "\n## Vault growth\n" not in document
    assert _group_lines(document, "Vault-Wachstum") == EXPECTED


@pytest.mark.parametrize("language,heading,nothing", [("en", "Vault growth", "nothing found"),
                                                      ("de", "Vault-Wachstum", "nichts gefunden")])
def test_no_created_note_keeps_the_empty_group(make_walk, language, heading, nothing):
    case = Case(WEEK, WEEK_PERIOD, WEEK_STEM, WEEK_DOC, False, lambda: _config(language), lambda: proposals(WEEK))
    w = make_walk(case)
    assert w.read(WEEK_PERIOD, WEEK)["status"] == "ok"
    props = proposals(WEEK)
    props["groups"]["growth"] = [{"text": f"stale growth {PRP}", "sources": ["2026-03-24"]}]
    out = w.write(WEEK_STEM, WEEK, props, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["counts"]["growth"] == 0, out
    assert _group_lines(w.doc(WEEK_DOC), heading) == [f"- {nothing}"]


# ── the MOC changes of the period (T9.3, F-R1-4; owner 2026-11-26) ──

M = "100 MOCs/"


def _read_mocs(created: dict, changed: List[str], linked: List[str], days: List[str] = ()) -> dict:
    read = _read(created, list(days))
    read["growth"]["mocs_changed"], read["growth"]["mocs_linked_by_new"] = list(changed), list(linked)
    return read


def _moc_links(items: List[dict]) -> List[str]:
    return [link for item in items if item["text"] in ("MOCs changed", "MOCs newly linked") for link in item["links"]]


def test_every_changed_moc_is_linked_once_in_one_item_after_the_created_notes():
    read = _read_mocs({"N/a.md": "2026-03-24"}, [f"{M}B MOC.md", f"{M}A MOC.md"], [], ["2026-03-24"])
    assert rgw.group(read, []) == [{"text": "[[a]]", "links": ["2026-03-24"]},
                                   {"text": "MOCs changed", "links": ["A MOC", "B MOC"]}]


def test_a_moc_linked_by_a_new_note_is_shown_once_and_a_moc_in_both_lists_only_as_changed():
    read = _read_mocs({"N/a.md": "2026-03-24"}, [f"{M}A MOC.md", f"{M}C MOC.md"], [f"{M}C MOC.md", f"{M}B MOC.md"])
    got = rgw.group(read, [])
    assert got[1:] == [{"text": "MOCs changed", "links": ["A MOC", "C MOC"]},
                       {"text": "MOCs newly linked", "links": ["B MOC"]}]
    assert sorted(_moc_links(got)) == ["A MOC", "B MOC", "C MOC"]


def test_mocs_linked_by_new_notes_that_all_changed_give_no_second_item():
    read = _read_mocs({"N/a.md": "2026-03-24"}, [f"{M}A MOC.md"], [f"{M}A MOC.md"])
    assert rgw.group(read, [])[1:] == [{"text": "MOCs changed", "links": ["A MOC"]}]


@pytest.mark.parametrize("language,changed,linked", [("en", "MOCs changed", "MOCs newly linked"),
                                                     ("de", "Geänderte MOCs", "Neu verlinkte MOCs")])
def test_the_moc_items_carry_the_label_words_of_the_review_language(language, changed, linked):
    read = _read_mocs({}, [f"{M}A MOC.md"], [f"{M}B MOC.md"])
    assert [item["text"] for item in rgw.group(read, [], language)] == [changed, linked]


def test_no_moc_change_gives_no_moc_item_and_the_created_note_items_unchanged():
    created = {"N/a.md": "2026-03-24", "N/b.md": "2026-03-10"}
    found = [_cand("one", "N/a.md")]
    plain = rgw.group(_read(created, ["2026-03-24"]), found)
    assert rgw.group(_read_mocs(created, [], [], ["2026-03-24"]), found) == plain
    assert _moc_links(plain) == [] and len(plain) == 2


def test_moc_changes_without_a_created_note_still_give_the_group():
    read = _read_mocs({}, [f"{M}A MOC.md"], [])
    assert rgw.group(read, []) == [{"text": "MOCs changed", "links": ["A MOC"]}]


def test_the_moc_items_come_after_the_created_note_items_in_a_fixed_order():
    created = {"N/z.md": "2026-03-30", "N/a.md": "2026-03-02"}
    one = rgw.group(_read_mocs(created, [f"{M}Q MOC.md", f"{M}P MOC.md"], [f"{M}S MOC.md", f"{M}R MOC.md"]),
                    [_cand("late", "N/z.md"), _cand("early", "N/a.md")])
    two = rgw.group(_read_mocs(created, [f"{M}P MOC.md", f"{M}Q MOC.md"], [f"{M}R MOC.md", f"{M}S MOC.md"]),
                    [_cand("early", "N/a.md"), _cand("late", "N/z.md")])
    assert one == two
    assert [item["text"] for item in one] == ["early", "late", "MOCs changed", "MOCs newly linked"]
    assert one[2]["links"] == ["P MOC", "Q MOC"] and one[3]["links"] == ["R MOC", "S MOC"]


def test_a_created_moc_stays_a_created_note_and_a_shared_stem_links_by_path():
    read = _read_mocs({f"{M}New MOC.md": "2026-03-24", "N/Topic.md": "2026-03-24"},
                      [f"{M}New MOC.md", f"{M}Topic.md"], [])
    got = rgw.group(read, [])
    assert got == [{"text": "[[New MOC]]", "links": []},
                   {"text": "[[N/Topic]]", "links": []},
                   {"text": "MOCs changed", "links": [f"{M}Topic"]}]


# ── end to end: the MOC line of the written document holds links and label words only ──

MOC_TEXT = f"moc body {PRP}\n"


def _moc_walk(make_walk, language="en", created=True):
    """A month with one MOC changed in it (Quiet) and one only linked by a new note (Topic); MOC texts carry PRP."""
    case = Case(MONTH, MONTH_PERIOD, MONTH_STEM, MONTH_DOC, True, lambda: _config(language),
                lambda: proposals(MONTH))
    w = make_walk(case)
    for path, day in (CREATED.items() if created else ()):
        w.vault.files[path] = f"# {Path(path).stem}\nnew note\n"
        w.vault.created[path] = w.vault.modified[path] = _ms(day)
    if created:
        w.vault.files["Notes/Bike chain.md"] = "# Bike chain\nsee [[Topic MOC]]\n"
    for name, modified in (("Quiet MOC", _ms("2026-03-11")), ("Topic MOC", 0)):
        w.vault.files[f"{M}{name}.md"] = MOC_TEXT
        w.vault.created[f"{M}{name}.md"], w.vault.modified[f"{M}{name}.md"] = 0, modified
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    return w


@pytest.mark.parametrize("language,heading,changed,linked", [
    ("en", "Vault growth", "MOCs changed", "MOCs newly linked"),
    ("de", "Vault-Wachstum", "Geänderte MOCs", "Neu verlinkte MOCs")])
def test_write_adds_the_moc_items_after_the_created_notes_with_links_and_label_words_only(
        make_walk, language, heading, changed, linked):
    w = _moc_walk(make_walk, language)
    out = w.write(MONTH_STEM, MONTH, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["counts"]["growth"] == 5, out
    document = w.doc(MONTH_DOC)
    assert _group_lines(document, heading) == EXPECTED + [f"- [x] {changed} ([[Quiet MOC]])",
                                                          f"- [x] {linked} ([[Topic MOC]])"]
    assert PRP not in json.dumps(out) and "moc body" not in document


def test_write_renders_the_group_with_moc_changes_and_no_created_note(make_walk):
    w = _moc_walk(make_walk, created=False)
    out = w.write(MONTH_STEM, MONTH, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["counts"]["growth"] == 1, out
    assert _group_lines(w.doc(MONTH_DOC), "Vault growth") == ["- [x] MOCs changed ([[Quiet MOC]])"]

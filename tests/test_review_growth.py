#!/usr/bin/env python3
# version: 0.4.0
"""test_review_growth.py — the "Vault growth" group the script builds (spec 047 T9.3, F-R1-3, F-R3-1, F-R3b-4; PRD F2-AC1).

Owner decision 2026-11-26 (T9.2 R1b/R1c): `review-doc.py write` builds the group from the created notes of the
read; the proposer no longer proposes `growth`. Owner decision 2026-11-28 (F-R3b-4, #274): the digests' growth
candidates are gone; the group is one item per parent folder of the created notes. Pinned here:

- a folder under the configured calendar base path (`concepts.calendar.base_path`, config over profile) → one
  count item over ALL its created notes, text "<folder>: <n> new notes" / "<folder>: <n> neue Notizen" (singular
  "1 new note" / "1 neue Notiz"), no links;
- any other folder with at most `LINKS_MAX` (10) created notes → one item, text the folder path ("vault root" /
  "Vault-Wurzel" for a note at the top), links its notes in path order; more than 10 → the count item;
- no calendar base path → every folder follows the second rule; the config names none → the profile's;
- folder items in folder path order, whatever their kind; then the MOC items;
- no digest is read: `group` takes the read alone, the module has no `candidates`;
- a note a section item mentions stays in the group;
- a `growth` group in proposals.json is not rendered, rejected nothing and fails nothing;
- no created note → no item (the empty group renders as before: "nothing found" unmapped);
- the English and the German heading.
- F-R1-4 (owner 2026-11-26): after the folder items, "MOCs changed" linking every changed MOC, then
  "MOCs newly linked" linking the MOCs a created note links and that did not change; each MOC once, none that is
  a created note; links in path order; EN and DE label words; MOC changes alone still give the group; the
  document's MOC lines hold label words and links only.

All data is synthetic.
"""
from __future__ import annotations

import copy
import inspect
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

CAL = "Calendar/"


def _read(created, *, changed=(), linked=()) -> dict:
    """A loaded read: the created note paths (each on one day), the MOC lists."""
    return {"growth": {"created": [{"path": p, "links": [], "day": "2026-03-24"} for p in sorted(created)],
                       "mocs_changed": list(changed), "mocs_linked_by_new": list(linked)}}


def _notes(folder: str, n: int) -> List[str]:
    return [f"{folder}/n{i:02d}.md" for i in range(n)]


# ── group: the folder items ──

def test_a_calendar_folder_is_one_count_item_over_all_its_created_notes():
    created = _notes("Calendar/301 Daily", 2) + _notes("Calendar/302 Weekly", 1)
    assert rgw.group(_read(created), calendar_base=CAL) == [{"text": "Calendar/301 Daily: 2 new notes", "links": []},
                                                            {"text": "Calendar/302 Weekly: 1 new note", "links": []}]


@pytest.mark.parametrize("base", ["Calendar/", "Calendar", " Calendar/ ", "/Calendar/"])
def test_the_calendar_base_path_matches_by_folder_whatever_its_slashes(base):
    created = ["Calendar/top.md", "Calendar/Sub/a.md", "Calendarium/b.md"]
    assert rgw.group(_read(created), calendar_base=base) == [{"text": "Calendar: 1 new note", "links": []},
                                                             {"text": "Calendar/Sub: 1 new note", "links": []},
                                                             {"text": "Calendarium", "links": ["b"]}]


@pytest.mark.parametrize("n", [1, 2, 10])
def test_another_folder_with_at_most_ten_created_notes_links_them(n):
    got = rgw.group(_read(_notes("Notes", n)), calendar_base=CAL)
    assert got == [{"text": "Notes", "links": [f"n{i:02d}" for i in range(n)]}]


@pytest.mark.parametrize("n", [11, 12])
def test_another_folder_with_more_than_ten_created_notes_is_a_count_item(n):
    assert rgw.group(_read(_notes("Notes", n)), calendar_base=CAL) == [{"text": f"Notes: {n} new notes", "links": []}]


def test_the_link_limit_is_the_named_constant_ten():
    assert rgw.LINKS_MAX == 10


def test_a_note_at_the_vault_root_is_linked_under_the_root_label():
    assert rgw.group(_read(["top.md", "b.md"]), calendar_base=CAL) == [{"text": "vault root", "links": ["b", "top"]}]
    assert rgw.group(_read([f"r{i:02d}.md" for i in range(11)]), "de") == [
        {"text": "Vault-Wurzel: 11 neue Notizen", "links": []}]


def test_without_a_calendar_base_path_a_calendar_folder_follows_the_link_rule():
    created = _notes("Calendar/301 Daily", 2) + _notes("Calendar/302 Weekly", 11)
    assert rgw.group(_read(created)) == [{"text": "Calendar/301 Daily", "links": ["Calendar/301 Daily/n00",
                                                                                  "Calendar/301 Daily/n01"]},
                                         {"text": "Calendar/302 Weekly: 11 new notes", "links": []}]
    assert rgw.group(_read(created), calendar_base="") == rgw.group(_read(created))


def test_folder_items_are_in_folder_path_order_whatever_their_kind():
    created = ["Z/z.md", "Calendar/D/d.md", "A/Sub/s.md", "A/a.md", *_notes("M", 11), "top.md"]
    got = rgw.group(_read(created), calendar_base=CAL)
    assert [item["text"] for item in got] == ["vault root", "A", "A/Sub", "Calendar/D: 1 new note",
                                              "M: 11 new notes", "Z"]


def test_links_in_a_folder_are_in_path_order_and_a_shared_stem_links_by_path():
    got = rgw.group(_read(["B/same.md", "B/other.md", "A/same.md"]), calendar_base=CAL)
    assert got == [{"text": "A", "links": ["A/same"]}, {"text": "B", "links": ["other", "B/same"]}]


@pytest.mark.parametrize("language,one,many", [("en", "Q: 1 new note", "N: 11 new notes"),
                                               ("de", "Q: 1 neue Notiz", "N: 11 neue Notizen")])
def test_the_count_items_carry_the_count_words_of_the_review_language(language, one, many):
    created = _notes("N", 11) + ["Q/c.md"]
    assert rgw.group(_read(created), language, calendar_base="Q/") == [{"text": many, "links": []},
                                                                      {"text": one, "links": []}]


def test_no_created_note_gives_no_item():
    assert rgw.group(_read([]), calendar_base=CAL) == []


def test_no_digest_is_read_the_group_takes_the_read_alone():
    assert list(inspect.signature(rgw.group).parameters) == ["read", "language", "calendar_base"]
    assert not hasattr(rgw, "candidates") and not hasattr(rgw, "DIGESTS")


# ── end to end through review-doc.py write (a month: created notes in Notes/ and in a calendar folder) ──

CREATED = {"Notes/Kettle descaling.md": "2026-03-10", "Notes/Shelf plan.md": "2026-03-12",
           "Notes/Bike chain.md": "2026-03-24", "Notes/Bike tyres.md": "2026-03-24",
           "Calendar/Meetings/Sync.md": "2026-03-10", "Calendar/Meetings/Retro.md": "2026-03-24"}
NOTES_LINE = "- [x] Notes ([[Bike chain]], [[Bike tyres]], [[Kettle descaling]], [[Shelf plan]])"
EXPECTED = ["- [x] Calendar/Meetings: 2 new notes", NOTES_LINE]
EXPECTED_DE = ["- [x] Calendar/Meetings: 2 neue Notizen", NOTES_LINE]


def _ms(day: str) -> int:
    return int(datetime.fromisoformat(f"{day}T12:00:00").timestamp() * 1000)


def _config(language: str = "en", mapped: bool = False) -> dict:
    out = copy.deepcopy(CONFIG)
    out["review"]["language"] = language
    out["concepts"]["calendar"]["base_path"] = CAL
    if mapped:
        out["review"]["monthly"]["sections"] = {"t_month.md": [dict(MONTH_SECTION_ROW)]}
    return out


def _stamp(w, created: dict) -> None:
    for path, day in created.items():
        w.vault.files[path] = f"# {Path(path).stem}\nnew note\n"
        w.vault.created[path] = w.vault.modified[path] = _ms(day)


def _walk(make_walk, language="en", mapped=False):
    case = Case(MONTH, MONTH_PERIOD, MONTH_STEM, MONTH_DOC, True, lambda: _config(language, mapped),
                lambda: proposals(MONTH))
    w = make_walk(case)
    _stamp(w, CREATED)
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    return w


def _group_lines(document: str, heading: str) -> List[str]:
    part = document.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]
    return [re.sub(r"\s*%%t\d+%%$", "", line) for line in part.split("\n") if line.startswith("- ")]


def test_write_builds_the_folder_items_and_ignores_a_proposed_growth_group(make_walk):
    w = _walk(make_walk)

    def proposer(props, stage, inputs):
        out = propose_from_inputs(props, stage, inputs)
        out["groups"]["growth"] = [{"text": f"stale growth {PRP}", "sources": ["2026-03-24"]},
                                   {"text": "", "sources": ["nowhere"]}]
        return out

    out = w.write(MONTH_STEM, MONTH, proposer=proposer)
    assert out["status"] == "written" and out["rejected"] == [] and out["counts"]["growth"] == 2, out
    document = w.doc(MONTH_DOC)
    assert _group_lines(document, "Vault growth") == EXPECTED
    assert "stale growth" not in document


def test_write_takes_the_profiles_calendar_base_path_when_the_config_names_none(make_walk):
    """Config over profile: the miyo profile's `concept_defaults.calendar.base_path` is `Calendar/`."""
    def config():
        out = _config()
        del out["concepts"]["calendar"]["base_path"]
        return out

    w = make_walk(Case(MONTH, MONTH_PERIOD, MONTH_STEM, MONTH_DOC, True, config, lambda: proposals(MONTH)))
    _stamp(w, CREATED)
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    out = w.write(MONTH_STEM, MONTH, proposer=propose_from_inputs)
    assert out["status"] == "written", out
    assert _group_lines(w.doc(MONTH_DOC), "Vault growth") == EXPECTED


def test_a_note_a_section_item_mentions_stays_in_the_group(make_walk):
    w = _walk(make_walk, mapped=True)
    props = proposals(MONTH)
    props["sections"] = [{"key": "s1", "items": [{"text": f"Bike chain {PRP}", "sources": ["2026-03-24"]}]}]
    out = w.write(MONTH_STEM, MONTH, props, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["counts"]["s1"] == 1 and out["counts"]["growth"] == 2, out
    document = w.doc(MONTH_DOC)
    assert re.search(rf"^- \[x\] Bike chain {PRP} \(\[\[2026-03-24\]\]\) %%t\d+%%$", document, re.M), document
    assert _group_lines(document, "Vault growth") == EXPECTED


def test_the_german_heading_holds_the_same_group(make_walk):
    w = _walk(make_walk, language="de")
    out = w.write(MONTH_STEM, MONTH, proposer=propose_from_inputs)
    assert out["status"] == "written", out
    document = w.doc(MONTH_DOC)
    assert "\n## Vault growth\n" not in document
    assert _group_lines(document, "Vault-Wachstum") == EXPECTED_DE


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


def _moc_links(items: List[dict]) -> List[str]:
    return [link for item in items if item["text"] in ("MOCs changed", "MOCs newly linked") for link in item["links"]]


def test_every_changed_moc_is_linked_once_in_one_item_after_the_created_notes():
    read = _read(["N/a.md"], changed=[f"{M}B MOC.md", f"{M}A MOC.md"])
    assert rgw.group(read) == [{"text": "N", "links": ["a"]}, {"text": "MOCs changed", "links": ["A MOC", "B MOC"]}]


def test_a_moc_linked_by_a_new_note_is_shown_once_and_a_moc_in_both_lists_only_as_changed():
    read = _read(["N/a.md"], changed=[f"{M}A MOC.md", f"{M}C MOC.md"], linked=[f"{M}C MOC.md", f"{M}B MOC.md"])
    got = rgw.group(read)
    assert got[1:] == [{"text": "MOCs changed", "links": ["A MOC", "C MOC"]},
                       {"text": "MOCs newly linked", "links": ["B MOC"]}]
    assert sorted(_moc_links(got)) == ["A MOC", "B MOC", "C MOC"]


def test_mocs_linked_by_new_notes_that_all_changed_give_no_second_item():
    read = _read(["N/a.md"], changed=[f"{M}A MOC.md"], linked=[f"{M}A MOC.md"])
    assert rgw.group(read)[1:] == [{"text": "MOCs changed", "links": ["A MOC"]}]


@pytest.mark.parametrize("language,changed,linked", [("en", "MOCs changed", "MOCs newly linked"),
                                                     ("de", "Geänderte MOCs", "Neu verlinkte MOCs")])
def test_the_moc_items_carry_the_label_words_of_the_review_language(language, changed, linked):
    read = _read([], changed=[f"{M}A MOC.md"], linked=[f"{M}B MOC.md"])
    assert [item["text"] for item in rgw.group(read, language)] == [changed, linked]


def test_no_moc_change_gives_no_moc_item_and_the_created_note_items_unchanged():
    plain = rgw.group(_read(["N/a.md", "N/b.md"]))
    assert _moc_links(plain) == [] and plain == [{"text": "N", "links": ["a", "b"]}]


def test_moc_changes_without_a_created_note_still_give_the_group():
    assert rgw.group(_read([], changed=[f"{M}A MOC.md"])) == [{"text": "MOCs changed", "links": ["A MOC"]}]


def test_the_moc_items_come_after_the_folder_items_in_a_fixed_order():
    created = ["Z/z.md", *_notes("Calendar/D", 3)]
    one = rgw.group(_read(created, changed=[f"{M}Q MOC.md", f"{M}P MOC.md"], linked=[f"{M}S MOC.md", f"{M}R MOC.md"]),
                    calendar_base=CAL)
    two = rgw.group(_read(created, changed=[f"{M}P MOC.md", f"{M}Q MOC.md"], linked=[f"{M}R MOC.md", f"{M}S MOC.md"]),
                    calendar_base=CAL)
    assert one == two
    assert [item["text"] for item in one] == ["Calendar/D: 3 new notes", "Z", "MOCs changed", "MOCs newly linked"]
    assert one[2]["links"] == ["P MOC", "Q MOC"] and one[3]["links"] == ["R MOC", "S MOC"]


def test_a_created_moc_stays_a_created_note_and_a_shared_stem_links_by_path():
    read = _read([f"{M}New MOC.md", "N/Topic.md"], changed=[f"{M}New MOC.md", f"{M}Topic.md"])
    assert rgw.group(read) == [{"text": "100 MOCs", "links": ["New MOC"]},
                               {"text": "N", "links": ["N/Topic"]},
                               {"text": "MOCs changed", "links": [f"{M}Topic"]}]


# ── end to end: the MOC line of the written document holds links and label words only ──

MOC_TEXT = f"moc body {PRP}\n"


def _moc_walk(make_walk, language="en", created=True):
    """A month with one MOC changed in it (Quiet) and one only linked by a new note (Topic); MOC texts carry PRP."""
    case = Case(MONTH, MONTH_PERIOD, MONTH_STEM, MONTH_DOC, True, lambda: _config(language),
                lambda: proposals(MONTH))
    w = make_walk(case)
    if created:
        _stamp(w, CREATED)
        w.vault.files["Notes/Bike chain.md"] = "# Bike chain\nsee [[Topic MOC]]\n"
    for name, modified in (("Quiet MOC", _ms("2026-03-11")), ("Topic MOC", 0)):
        w.vault.files[f"{M}{name}.md"] = MOC_TEXT
        w.vault.created[f"{M}{name}.md"], w.vault.modified[f"{M}{name}.md"] = 0, modified
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    return w


@pytest.mark.parametrize("language,heading,changed,linked", [
    ("en", "Vault growth", "MOCs changed", "MOCs newly linked"),
    ("de", "Vault-Wachstum", "Geänderte MOCs", "Neu verlinkte MOCs")])
def test_write_adds_the_moc_items_after_the_folder_items_with_links_and_label_words_only(
        make_walk, language, heading, changed, linked):
    w = _moc_walk(make_walk, language)
    out = w.write(MONTH_STEM, MONTH, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["counts"]["growth"] == 4, out
    document = w.doc(MONTH_DOC)
    lines = EXPECTED if language == "en" else EXPECTED_DE
    assert _group_lines(document, heading) == lines + [f"- [x] {changed} ([[Quiet MOC]])",
                                                       f"- [x] {linked} ([[Topic MOC]])"]
    assert PRP not in json.dumps(out) and "moc body" not in document


def test_write_renders_the_group_with_moc_changes_and_no_created_note(make_walk):
    w = _moc_walk(make_walk, created=False)
    out = w.write(MONTH_STEM, MONTH, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["counts"]["growth"] == 1, out
    assert _group_lines(w.doc(MONTH_DOC), "Vault growth") == ["- [x] MOCs changed ([[Quiet MOC]])"]


# ── round trip: a count item (no links) and a link item survive write → approve → parse → deliver ──

def test_the_folder_items_parse_and_deliver_like_any_growth_item(make_walk):
    w = _walk(make_walk)
    out = w.write(MONTH_STEM, MONTH, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["counts"]["growth"] == 2, out
    w.approve(MONTH_DOC)
    parsed = w.parse(MONTH_STEM)
    assert parsed["approved"] is True and parsed["warnings"] == [], parsed
    assert [(r["kept"], r["edited"]) for r in parsed["items"]["growth"]] == [(True, False)] * 2, parsed["items"]
    assert w.preview(MONTH_STEM)["problems"] == []
    before = len(w.vault.recorded)
    assert w.deliver(MONTH_STEM)["status"] == "delivered"
    delivered = "\n".join(w.vault.text(p) for p in w.vault.recorded[before:] if p != MONTH_DOC)
    assert "Calendar/Meetings: 2 new notes" in delivered and "[[Shelf plan]]" in delivered
    assert "[[Sync]]" not in delivered

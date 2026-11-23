#!/usr/bin/env python3
# version: 0.1.1
"""test_review_doc_fingerprint.py — spec 047 T1.1: a review document's structure compared without its wording.

``tests/review_doc_fingerprint.py`` reads a rendered ``<period> Review.md``
and keeps only its structure (spec 047 ADR-11, PRD F2-AC1). Pinned here:
- two documents differing only in item wording (first and continuation lines) give equal fingerprints;
- a moved part, an unticked section checkbox, a missing group, one item more, a changed mark suffix,
  a changed link kind (daily → weekly) and a changed callout field each give unequal fingerprints,
  and ``diff`` names the key that carries the change (each case fails when the fingerprint ignores it);
- a link to a periodic note before the period is ``previous`` (the link kind spec 047 adds), a child
  note inside the period keeps its kind;
- the fingerprint holds no item text (a sentinel in every model item never reaches it);
- every non-blank line between the title and the first part other than the first info callout counts
  as a top line, a second ``> [!info]`` line included;
- a German document's mark suffixes give the same mark keys, and two suffixes in a row give both keys in order.

The documents are rendered by ``lib.review_doc.render_document`` from synthetic inputs; no Kado, no file I/O.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from lib import review_doc as rd  # noqa: E402
from lib import review_sections as rs  # noqa: E402
from review_doc_fingerprint import diff, fingerprint  # noqa: E402

SENTINEL = "SENTINEL-047fp wording"
HABIT = "Sport: 5 of 7 days (7 days in the period)"


def _inp(kind="week", name="2026-W13", language="en", sections=None, **overrides) -> rd.DocInput:
    fields = dict(
        period_name=name, kind=kind, language=language, stem=f"{name}_review", run_id="r-fp",
        target=f"Calendar/302 Weekly/{name}.md", target_exists=True, target_found_elsewhere=None,
        anchor="In my own words", placement="before", not_read=[], partly_read=[], month_groups=False,
        groups={}, sections=sections,
    )
    fields.update(overrides)
    return rd.DocInput(**fields)


def _week_groups(word: str = "alpha") -> dict:
    return {
        rd.DONE: [{"text": f"Tidied the {word} week\n{word} continuation line", "links": ["2026-03-24", "2026-03-26"]}],
        rd.OPEN: [{"text": f"Tax {word} still open", "links": ["2026-03-27"]}],
        rd.THEMES: [{"text": f"Sleep {word}", "links": ["2026-03-23", "2026-03-25"]}],
        rd.GROWTH: [],
        rd.HABITS: [{"text": HABIT, "links": []}],
    }


def _part(key, heading, placement, items, level=3) -> rs.SectionPart:
    return rs.SectionPart(key=key, heading=heading, placement=placement,
                          landing=rs.Landing(heading, level, None), items=items)


def _month_sections(word: str = "alpha", mark: str = "weekly_only", links=("2026-W13",)) -> list:
    return [
        _part("s1", "Things I did well", "end", [{"text": f"Kept the {word} rhythm", "links": ["2026-03-04"]}]),
        _part("s2", "Energy", "review", [{"text": f"Energy {word}", "links": list(links), "mark": mark}]),
        _part("s3", "Planning", "before", []),
    ]


def _week_doc(word: str = "alpha", **overrides) -> str:
    overrides.setdefault("groups", _week_groups(word))
    return rd.render_document(_inp(**overrides))[0]


def _month_doc(word: str = "alpha", sections=None, **overrides) -> str:
    overrides.setdefault("groups", {
        rd.DONE: [{"text": f"Month {word} done", "links": ["2026-03-10"]}],
        rd.WEEKLY_ONLY: [{"text": f"Only weekly {word}", "links": ["2026-W13"]}],
        rd.HABITS: [{"text": HABIT, "links": []}],
    })
    return rd.render_document(_inp(
        kind="month", name="2026-03", target="Calendar/303 Monthly/2026-03.md", anchor="Reflections",
        placement="inside", month_groups=True,
        sections=_month_sections(word) if sections is None else sections, **overrides))[0]


def _differs(a: str, b: str, key: str) -> None:
    fa, fb = fingerprint(a), fingerprint(b)
    assert fa != fb
    assert key in {k.split(".", 1)[0] for k in diff(fa, fb)}, diff(fa, fb)


# --- equal without the wording ----------------------------------------------------------------

def test_wording_alone_gives_equal_fingerprints_unmapped_week() -> None:
    a, b = _week_doc("alpha"), _week_doc("bravo")
    assert a != b
    assert fingerprint(a) == fingerprint(b)
    assert diff(fingerprint(a), fingerprint(b)) == []


def test_wording_alone_gives_equal_fingerprints_mapped_month() -> None:
    a, b = _month_doc("alpha"), _month_doc("bravo")
    assert a != b
    assert fingerprint(a) == fingerprint(b)


def test_fingerprint_reads_the_structure_of_a_mapped_month() -> None:
    fp = fingerprint(_month_doc())
    assert fp["parts"] == ["s1", "s3", "review", "s2", rd.DONE, rd.HABITS, rd.WEEKLY_ONLY]
    assert fp["sections"] == {"s1": True, "s2": True, "s3": False}
    assert fp["counts"] == {"s1": 1, "s3": 0, "review": 0, "s2": 1, rd.DONE: 1, rd.WEEKLY_ONLY: 1, rd.HABITS: 1}
    assert fp["marks"]["s2"] == [["weekly_only"]]
    assert fp["links"]["s1"] == [["daily"]] and fp["links"]["s2"] == [["weekly"]]
    assert fp["callout"]["target"] == "exists" and fp["callout"]["placement"] == "inside"
    assert fp["habits"] == [["5", "7", "7"]]


# --- unequal on every structural change ---------------------------------------------------------

def test_a_moved_part_differs_in_parts() -> None:
    sections = _month_sections()
    moved = [sections[2], sections[0], sections[1]]
    _differs(_month_doc(), _month_doc(sections=moved), "parts")


def test_an_unticked_section_checkbox_differs_in_sections() -> None:
    doc = _month_doc()
    line = "- [x] Use this section %%s1%%"
    assert line in doc
    _differs(doc, doc.replace(line, "- [ ] Use this section %%s1%%"), "sections")


def test_a_missing_group_differs_in_groups() -> None:
    doc = _week_doc()
    block = "\n## Vault growth\n- nothing found\n"
    assert block in doc
    _differs(doc, doc.replace(block, "\n"), "groups")


def test_one_item_more_differs_in_counts() -> None:
    groups = _week_groups()
    more = _week_groups()
    more[rd.OPEN] = more[rd.OPEN] + [{"text": "Another open", "links": ["2026-03-28"]}]
    _differs(_week_doc(groups=groups), _week_doc(groups=more), "counts")


def test_a_changed_mark_suffix_differs_in_marks() -> None:
    a = _month_doc(sections=_month_sections(mark="weekly_only"))
    b = _month_doc(sections=_month_sections(mark="not_in_weekly", links=("2026-W13",)))
    _differs(a, b, "marks")


def test_a_changed_link_kind_daily_to_weekly_differs_in_links() -> None:
    groups, weekly = _week_groups(), _week_groups()
    weekly[rd.OPEN] = [{"text": weekly[rd.OPEN][0]["text"], "links": ["2026-W13"]}]
    a = _month_doc(groups=groups)
    b = _month_doc(groups=weekly)
    _differs(a, b, "links")


def test_a_changed_callout_field_differs_in_callout() -> None:
    _differs(_week_doc(), _week_doc(target_exists=False), "callout")
    _differs(_week_doc(), _week_doc(not_read=["Calendar/301 Daily/2026-03-28.md"]), "callout")


# --- the link kinds, previous included ----------------------------------------------------------

def test_link_kinds_classify_previous_periodic_notes() -> None:
    month = fingerprint(_month_doc(groups={rd.DONE: [
        {"text": "x", "links": ["2026-03-10", "2026-W13", "2026-W09", "2026-02", "2026-Q1", "Efforts/X"]}]}))
    assert month["links"][rd.DONE] == [["daily", "weekly", "weekly", "previous", "quarterly", "other"]]
    week = fingerprint(_week_doc(groups={rd.DONE: [{"text": "x", "links": ["2026-03-24", "2026-W12", "2026-W13"]}]}))
    assert week["links"][rd.DONE] == [["daily", "previous", "weekly"]]
    quarter = fingerprint(rd.render_document(_inp(
        kind="quarter", name="2026-Q1", groups={rd.DONE: [{"text": "x", "links": ["2026-03", "2025-Q4", "2025-12"]}]}))[0])
    assert quarter["links"][rd.DONE] == [["monthly", "previous", "previous"]]


# --- no item text -------------------------------------------------------------------------------

def test_fingerprint_holds_no_item_text() -> None:
    for doc in (_week_doc(SENTINEL), _month_doc(SENTINEL)):
        assert SENTINEL in doc
        dumped = json.dumps(fingerprint(doc), ensure_ascii=False)
        assert SENTINEL not in dumped
        assert "SENTINEL" not in dumped and "wording" not in dumped


def test_diff_names_nothing_for_equal_and_the_subkey_for_a_count() -> None:
    a = fingerprint(_week_doc())
    assert diff(a, dict(a)) == []
    b = json.loads(json.dumps(a))
    b["counts"][rd.OPEN] += 1
    assert diff(a, b) == [f"counts.{rd.OPEN}"]


# --- top lines and marks ------------------------------------------------------------------------

_GATE = "- [ ] Approved"


def _with_top_lines(doc: str, *lines: str) -> str:
    assert doc.count(_GATE) == 1
    return doc.replace(_GATE, "".join(f"{line}\n" for line in lines) + _GATE)


def test_plain_lines_above_the_first_part_count_as_top_lines() -> None:
    base = _week_doc()
    one = _with_top_lines(base, "Previous note: [[2026-W12]]")
    two = _with_top_lines(base, "Previous note: [[2026-W12]]", "Not condensed: 2 days")
    assert [fingerprint(d)["top_lines"] for d in (base, one, two)] == [0, 1, 2]
    _differs(base, one, "top_lines")
    _differs(one, two, "top_lines")
    assert diff(fingerprint(base), fingerprint(one)) == ["top_lines"]


def test_a_second_info_callout_line_counts_as_a_top_line() -> None:
    base = _week_doc()
    second = _with_top_lines(base, "> [!info] Previous note: [[2026-W12]]")
    fb, fs = fingerprint(base), fingerprint(second)
    assert fs["top_lines"] == 1
    assert fs["callout"] == fb["callout"]
    _differs(base, second, "top_lines")


def test_a_german_document_records_its_mark_keys() -> None:
    doc = _month_doc(language="de", sections=_month_sections(mark="weekly_only"))
    assert " · nur im Wochenrückblick %%t" in doc
    fp = fingerprint(doc)
    assert fp["marks"]["s2"] == [["weekly_only"]]
    other = _month_doc(language="de", sections=_month_sections(mark="not_in_weekly"))
    assert fingerprint(other)["marks"]["s2"] == [["not_in_weekly"]]
    _differs(doc, other, "marks")


def test_two_mark_suffixes_in_a_row_record_both_keys_in_order() -> None:
    doc = _month_doc(sections=_month_sections(mark="weekly_only"))
    single = " · only in the weekly review %%t"
    assert doc.count(single) == 1
    words = rd._LABELS["en"]
    double = doc.replace(single, f" · {words['mark_weekly_only']} · {words['mark_not_in_monthly']} %%t")
    assert fingerprint(double)["marks"]["s2"] == [["weekly_only", "not_in_monthly"]]
    swapped = doc.replace(single, f" · {words['mark_not_in_monthly']} · {words['mark_weekly_only']} %%t")
    assert fingerprint(swapped)["marks"]["s2"] == [["not_in_monthly", "weekly_only"]]
    assert fingerprint(double)["links"]["s2"] == [["weekly"]]

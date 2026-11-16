#!/usr/bin/env python3
# version: 0.1.1
"""test_046_t4_3_section_parse.py — the mapped review document read back by section (spec 046 T4.3).

Documents are the T4.2 renderer's own output (``review-doc.py write`` on the
fake vault, or ``review_doc.render_document`` for a part shape the write path
cannot reach), then edited the way a user would. With ``pass1_sections`` from
meta.json:
- a heading with ``%%sN%%`` is section N, also when its text was edited and
  when it is named like a group ("Erledigt"); the section checkbox is matched
  before ``_ITEM`` and is never an item; the landing line is no item and no
  text; the ``%%review%%`` divider holds no items (a line under it is
  ``item-outside-group``) (ADR-11)
- ``sections`` is ticked / unticked / None per expected key; a missing,
  broken, misplaced or doubled checkbox is ``section-checkbox-missing`` naming
  the key, the heading and the line to restore, box as Pass 1 rendered it, in
  the document's language (F3-AC6)
- an unticked section drops everything in it from the ApprovedReview record,
  the user's own items too, and ``section_counts`` gives the user's dropped
  items (F3-AC4, Rule 7); a ticked section with nothing ticked is ``empty``
  (F3-AC5)
- a key meta.json does not list is an ordinary heading (``unknown-group``);
  a doubled heading is ``duplicate-group``; without ``pass1_sections`` the
  mapped document reads as spec 045 did (the unmapped golden is
  test_046_t4_3_unmapped_parse_golden.py)
- ``review_doc_read`` hands meta.json's ``pass1_sections`` to the parser;
  ``review-doc.py parse`` warns ``section-checkbox-missing`` and leaks no
  heading text
- a Tomo id on a checkbox line is the checkbox's (the id counts as deleted);
  the first expected ``%%sN%%`` on a line names the section.

All data is synthetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib import review_doc as rd  # noqa: E402
from lib import review_doc_parse as rdp  # noqa: E402
from lib import review_sections as rs  # noqa: E402
from lib.review_doc_read import read_document  # noqa: E402
from test_046_t4_2_doc_sections import (  # noqa: E402
    MARKER, WEEK_PROPS, WEEK_ROWS, _doc_input, inst, mapped_week, map_config, meta_of, row, script, section,
    write,
)
from test_review_doc import item  # noqa: E402

__all__ = ["inst", "script"]                       # the T4.2 fixtures, used by name

MISSING = rdp.SECTION_CHECKBOX_MISSING
S1_BOX = "- [x] Abschnitt übernehmen %%s1%%"
S3_BOX = "- [ ] Abschnitt übernehmen %%s3%%"
S1_HEAD = "## What Went Well This Week? %%s1%%"


@pytest.fixture
def written(script, inst, monkeypatch, capsys):
    """``(document text, meta.json)`` of the mapped T4.2 week (sections s1 s3 s4, divider, s2, groups)."""
    _, out, fake = write(script, monkeypatch, capsys, inst, mapped_week(), WEEK_PROPS)
    return fake.text(out["doc_path"]), meta_of(inst)


def parse(text: str, meta: dict, sections="meta") -> rdp.ParsedDoc:
    return rdp.parse_document(text, pass1_links=meta["pass1_links"], pass1_total=sum(meta["pass1_counts"].values()),
                              pass1_sections=meta.get("pass1_sections") if sections == "meta" else sections)


def edit(text: str, old: str, new: str) -> str:
    assert old in text, old
    return text.replace(old, new, 1)


def by_id(parsed: rdp.ParsedDoc) -> dict:
    return {it.id: it for it in parsed.items if it.id}


def problems(parsed: rdp.ParsedDoc) -> list:
    return [(p.key, p.heading, p.restore) for p in parsed.section_problems]


# ---------------------------------------------------------------- the grammar

def test_the_rendered_week_reads_by_section(written):
    text, meta = written
    parsed = parse(text, meta)
    assert parsed.sections == {"s1": True, "s3": False, "s4": True, "s2": True}
    assert parsed.warnings == [] and parsed.section_problems == []
    groups = {i: it.group for i, it in by_id(parsed).items()}
    assert groups == {"t1": "s1", "t2": "s1", "t3": "s4", "t4": "s2", "t5": "done", "t6": "habits"}
    assert parsed.group_order == ["s1", "s3", "s4", "s2", "done", "habits"]       # the divider is no group
    assert len(parsed.items) == 6                                                 # no checkbox is an item
    assert not any("Landet" in "\n".join([it.text, *it.lines]) for it in parsed.items)
    assert parsed.counts() == {"kept": 6, "unticked": 0, "deleted": 0, "added": 0}


def test_an_edited_heading_keeps_its_section(written):
    text, meta = written
    parsed = parse(edit(text, S1_HEAD, "## Was lief gut %%s1%% ##"), meta)
    assert parsed.sections["s1"] is True and by_id(parsed)["t1"].group == "s1" and parsed.warnings == []


def test_a_user_section_named_like_a_group_is_never_that_group():
    part = rs.SectionPart(key="s1", heading="Erledigt", placement="end",
                          landing=rs.Landing("Erledigt", 3, None), items=[{"text": "eigenes", "links": ["2026-03-24"]}])
    inp = _doc_input(kind="week", language="de", month_groups=False, sections=[part],
                     groups={"done": [{"text": "aus der Gruppe", "links": ["2026-03-25"]}]})
    text, counts = rd.render_document(inp)
    assert "## Erledigt %%s1%%" in text and "\n## Erledigt\n" in text
    meta = {"pass1_links": rdp.link_stems(text), "pass1_counts": counts,
            "pass1_sections": [{"key": "s1", "count": 1, "empty": False}]}
    parsed = parse(text, meta)
    assert by_id(parsed)["t1"].group == "s1" and by_id(parsed)["t2"].group == "done"
    assert parsed.warnings == []
    # the id dropped from the heading: the heading is group done, the orphaned checkbox stops delivery
    broken = parse(edit(text, "## Erledigt %%s1%%", "## Erledigt"), meta)
    assert MISSING in broken.warnings and [p.key for p in broken.section_problems] == ["s1"]
    assert by_id(broken)["t1"].group == "done"


def test_the_divider_holds_no_items(written):
    text, meta = written
    parsed = parse(edit(text, "## Tomo Review %%review%%\n", "## Tomo Review %%review%%\n- [x] unterm Trenner\n"),
                   meta)
    stray = [it for it in parsed.items if it.text == "unterm Trenner"]
    assert [it.group for it in stray] == [rdp.UNKNOWN] and parsed.warnings == [rdp.ITEM_OUTSIDE_GROUP]
    assert by_id(parsed)["t4"].group == "s2" and parsed.section_problems == []


def test_an_item_between_the_heading_and_its_checkbox_is_the_sections(written):
    text, meta = written
    moved = edit(edit(text, S1_BOX + "\n", ""), S1_HEAD + "\n", S1_HEAD + "\n- [x] meins davor\n" + S1_BOX + "\n")
    parsed = parse(moved, meta)
    assert parsed.sections["s1"] is True and parsed.section_problems == []
    assert [it.group for it in parsed.items if it.text == "meins davor"] == ["s1"]


def test_the_checkbox_after_the_items_still_counts(written):
    text, meta = written
    t2 = next(ln for ln in text.splitlines() if ln.endswith("%%t2%%"))
    moved = edit(edit(text, S1_BOX + "\n", ""), t2 + "\n", t2 + "\n" + S1_BOX.replace("[x]", "[ ]") + "\n")
    parsed = parse(moved, meta)
    assert parsed.sections["s1"] is False and parsed.section_problems == []
    assert by_id(parsed)["t2"].lines == []                    # the checkbox ended the item, it is no text


def test_the_label_is_not_compared_and_X_ticks(written):
    text, meta = written
    parsed = parse(edit(text, S3_BOX, "- [X] ja, den auch %%s3%%"), meta)
    assert parsed.sections["s3"] is True and parsed.section_problems == []


# ---------------------------------------------------------------- the stop

def test_a_deleted_checkbox_stops_naming_the_section_and_the_line_to_restore(written):
    text, meta = written
    parsed = parse(edit(text, S1_BOX + "\n", ""), meta)
    assert MISSING in parsed.warnings and parsed.sections["s1"] is None
    assert problems(parsed) == [("s1", "What Went Well This Week?", S1_BOX)]
    assert by_id(parsed)["t1"].group == "s1"                  # never filed under the heading above
    assert parsed.nothing_to_deliver() is False               # the stop is the gate, not an empty delivery


def test_the_restore_line_of_an_empty_section_is_unticked(written):
    text, meta = written
    parsed = parse(edit(text, S3_BOX + "\n", ""), meta)
    assert problems(parsed) == [("s3", "Planning", S3_BOX)]


@pytest.mark.parametrize("broken", [
    "  " + S1_BOX,                                          # indented: item text, no checkbox
    S1_BOX.replace("- [x] ", "-[x] "),
    S1_BOX.replace("- [x] ", "- [x]"),
    S1_BOX.replace("%%s1%%", "%%s1%"),
    S1_BOX.replace(" %%s1%%", ""),
    S1_BOX.replace("[x]", "[v]"),
])
def test_a_broken_checkbox_stops(written, broken):
    text, meta = written
    parsed = parse(edit(text, S1_BOX, broken), meta)
    assert MISSING in parsed.warnings and [p.key for p in parsed.section_problems] == ["s1"]


@pytest.mark.parametrize("place", ["## Notes %%s4%%\n", "## Erledigt\n", "## Tomo Review %%review%%\n",
                                   "- [ ] Approved\n"])
def test_a_checkbox_moved_out_of_its_part_stops(written, place):
    text, meta = written
    moved = edit(edit(text, S1_BOX + "\n", ""), place, place + S1_BOX + "\n")
    parsed = parse(moved, meta)
    assert [p.key for p in parsed.section_problems] == ["s1"] and parsed.sections["s4"] is True


def test_a_second_checkbox_stops(written):
    text, meta = written
    parsed = parse(edit(text, S1_BOX + "\n", S1_BOX + "\n" + S1_BOX.replace("[x]", "[ ]") + "\n"), meta)
    assert [p.key for p in parsed.section_problems] == ["s1"]


def test_a_deleted_heading_stops_for_the_orphaned_checkbox(written):
    text, meta = written
    parsed = parse(edit(text, "## Planning %%s3%%\n", ""), meta)
    assert problems(parsed) == [("s3", None, S3_BOX)]


def test_a_deleted_part_stops(written):
    text, meta = written
    part = '## Planning %%s3%%\n- [ ] Abschnitt übernehmen %%s3%%\n*Landet: vor „Planning“ (Ebene 3)*\n- nichts gefunden\n'
    parsed = parse(edit(text, part, ""), meta)
    assert problems(parsed) == [("s3", None, S3_BOX)]


def test_the_restore_line_is_english_for_an_english_or_broken_frontmatter(written):
    text, meta = written
    english = edit(edit(text, "review_language: de", "review_language: en"), S1_BOX + "\n", "")
    assert problems(parse(english, meta))[0][2] == "- [x] Use this section %%s1%%"
    broken = edit(edit(text, "tomo:\n", "tomo: [\n"), S1_BOX + "\n", "")
    parsed = parse(broken, meta)
    assert rdp.FRONTMATTER_BROKEN in parsed.warnings and problems(parsed)[0][2] == "- [x] Use this section %%s1%%"


def test_the_public_problem_carries_no_heading_text(written):
    text, meta = written
    [problem] = parse(edit(text, S1_BOX + "\n", ""), meta).section_problems
    assert problem.public() == {"key": "s1", "restore": S1_BOX}


# ---------------------------------------------------------------- dropped and empty sections

def test_an_unticked_section_drops_everything_in_it_the_users_items_too(written):
    text, meta = written
    t2 = next(ln for ln in text.splitlines() if ln.endswith("%%t2%%"))
    dropped = edit(edit(text, S1_BOX, S1_BOX.replace("[x]", "[ ]")), t2 + "\n",
                   t2 + "\n- [x] meins\n- [x] auch meins\n- [ ] nur notiert\n")
    parsed = parse(dropped, meta)
    assert parsed.sections["s1"] is False and parsed.section_problems == []
    assert parsed.section_counts()["s1"] == {"ticked": False, "kept": 2, "unticked": 0, "added": 2, "empty": False}
    review = parsed.approved_review()
    assert review["groups"]["s1"] == []
    assert [r["id"] for r in review["groups"]["s4"]] == ["t3"] and review["groups"]["done"]
    assert parsed.counts()["kept"] == 6                       # the boxes, as spec 045 counts them


def test_only_items_in_unticked_sections_mean_nothing_to_deliver(written):
    text, meta = written
    for key in ("s1", "s4", "s2"):
        text = edit(text, f"- [x] Abschnitt übernehmen %%{key}%%", f"- [ ] Abschnitt übernehmen %%{key}%%")
    for tid in ("t5", "t6"):
        line = next(ln for ln in text.splitlines() if ln.endswith(f"%%{tid}%%"))
        text = edit(text, line, line.replace("- [x]", "- [ ]"))
    parsed = parse(text, meta)
    assert parsed.nothing_to_deliver() is True and not any(parsed.approved_review()["groups"].values())


def test_a_ticked_section_with_nothing_ticked_is_empty(written):
    text, meta = written
    t1 = next(ln for ln in text.splitlines() if ln.endswith("%%t1%%"))
    t2 = next(ln for ln in text.splitlines() if ln.endswith("%%t2%%"))
    text = edit(edit(text, t1, t1.replace("- [x]", "- [ ]")), t2 + "\n", "")          # one unticked, one deleted
    text = edit(text, S3_BOX, S3_BOX.replace("[ ]", "[x]"))                            # the rendered-empty one ticked
    counts = parse(text, meta).section_counts()
    assert counts["s1"] == {"ticked": True, "kept": 0, "unticked": 1, "added": 0, "empty": True}
    assert counts["s3"] == {"ticked": True, "kept": 0, "unticked": 0, "added": 0, "empty": True}
    assert counts["s4"]["empty"] is False and counts["s2"]["empty"] is False


def test_a_ticked_empty_section_with_the_users_own_item_is_not_empty(written):
    text, meta = written
    text = edit(text, S3_BOX + "\n", S3_BOX.replace("[ ]", "[x]") + "\n- [x] meine Planung\n")
    parsed = parse(text, meta)
    assert parsed.section_counts()["s3"] == {"ticked": True, "kept": 0, "unticked": 0, "added": 1, "empty": False}
    assert [r["text"] for r in parsed.approved_review()["groups"]["s3"]] == ["meine Planung"]


def test_a_section_without_its_checkbox_lands_nothing(written):
    text, meta = written
    review = parse(edit(text, S1_BOX + "\n", ""), meta).approved_review()
    assert review["groups"]["s1"] == [] and MISSING in review["warnings"]


# ---------------------------------------------------------------- keys meta.json does not list

def test_a_key_meta_does_not_list_is_an_ordinary_heading(written):
    text, meta = written
    extra = "\n## Extra %%s9%%\n- [x] Abschnitt übernehmen %%s9%%\n- [x] dazu\n"
    parsed = parse(edit(text, "\n## Tomo Review %%review%%", extra + "\n## Tomo Review %%review%%"), meta)
    assert parsed.warnings == [rdp.UNKNOWN_GROUP] and "s9" not in parsed.sections
    assert [it.group for it in parsed.items if it.origin == rdp.USER] == [rdp.UNKNOWN, rdp.UNKNOWN]
    assert parsed.section_problems == []


def test_a_doubled_section_heading_continues_the_section(written):
    text, meta = written
    again = edit(text, "\n## Tomo Review %%review%%", f"\n{S1_HEAD}\n- [x] nachgetragen\n\n## Tomo Review %%review%%")
    parsed = parse(again, meta)
    assert parsed.warnings == [rdp.DUPLICATE_GROUP] and parsed.section_problems == []
    assert [it.group for it in parsed.items if it.text == "nachgetragen"] == ["s1"]
    twice = edit(text, "\n## Tomo Review %%review%%", f"\n{S1_HEAD}\n{S1_BOX}\n\n## Tomo Review %%review%%")
    assert [p.key for p in parse(twice, meta).section_problems] == ["s1"]


@pytest.mark.parametrize("sections", [None, "not a list", 3])
def test_without_a_usable_pass1_sections_the_mapped_document_reads_as_spec_045(written, sections):
    text, meta = written
    parsed = parse(text, meta, sections=sections)
    assert parsed.sections == {} and parsed.section_problems == []
    assert rdp.UNKNOWN_GROUP in parsed.warnings and MISSING not in parsed.warnings
    assert parsed.approved_review() == rdp.parse_document(text, pass1_links=meta["pass1_links"],
                                                          pass1_total=6).approved_review()


# ---------------------------------------------------------------- the readers

def test_read_document_hands_pass1_sections_to_the_parser(written):
    text, meta = written
    broken = edit(text, S1_BOX + "\n", "")
    vault = SimpleNamespace(client=SimpleNamespace(read_note=lambda path: {"content": broken, "modified": 7}))
    read = read_document(vault, "100 Inbox/2026-W13 Review.md", meta)
    assert read.parsed.sections["s1"] is None and MISSING in read.parsed.warnings


def test_the_parse_command_warns_section_checkbox_missing_and_leaks_no_heading(script, inst, monkeypatch, capsys):
    rows = [row("s1", MARKER + " heading", "end"), *WEEK_ROWS[1:]]
    map_config(inst, rows)
    props = {**WEEK_PROPS, "sections": [section("s1", item("eins", "2026-03-24"))]}
    _, out, fake = write(script, monkeypatch, capsys, inst, mapped_week(rows), props)
    path = out["doc_path"]
    fake.files[path] = edit(fake.text(path), "- [x] Abschnitt übernehmen %%s1%%\n", "")
    monkeypatch.setattr(script, "KadoClient", fake)
    code = script.main(["--profiles-dir", "profiles", "parse", "--stem", "2026-W13_review"])
    stdout, stderr = capsys.readouterr()
    result = json.loads(stdout)
    assert code == 0 and MISSING in result["warnings"]
    assert MARKER not in json.dumps(result, ensure_ascii=False) and MARKER not in stderr


# ---------------------------------------------------------------- ids on the section lines

def test_a_tomo_id_on_the_checkbox_line_is_read_as_the_checkbox(written):
    text, meta = written
    parsed = parse(edit(text, S1_BOX, S1_BOX + " %%t3%%"), meta)
    assert parsed.sections["s1"] is True and parsed.section_problems == []
    t3 = next(ln for ln in text.splitlines() if ln.endswith("%%t3%%"))
    gone = parse(edit(edit(text, t3 + "\n", ""), S1_BOX, S1_BOX + " %%t3%%"), meta)
    assert "t3" not in by_id(gone) and gone.counts()["deleted"] == 1      # the checkbox, never Tomo's item t3


def test_a_heading_carrying_an_unlisted_key_before_the_expected_one_keeps_its_section(written):
    text, meta = written
    parsed = parse(edit(text, S1_HEAD, "## What Went Well This Week? %%s9%% %%s1%%"), meta)
    assert parsed.sections["s1"] is True and parsed.section_problems == [] and parsed.warnings == []
    assert by_id(parsed)["t1"].group == "s1"
    boxed = parse(edit(text, S1_BOX, "- [x] Abschnitt übernehmen %%s9%% %%s1%%"), meta)
    assert boxed.sections["s1"] is True and boxed.section_problems == []

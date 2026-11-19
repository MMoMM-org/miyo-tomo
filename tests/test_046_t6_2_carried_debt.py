#!/usr/bin/env python3
# version: 0.1.2
"""test_046_t6_2_carried_debt.py — the code debt Phase 5 carried into spec 046 T6.2.

docs/XDD/specs/046-review-template-sections/plan/phase-6.md T6.2 / T6.4 "Carried from Phase 5". Mechanisms a
mutation falsifies:

- the choice flags' key pattern being the section key ``^s[0-9]{1,3}$`` of ``lib/review_doc_parse.SECTION_KEY``, not
  a looser one (``test_a_key_that_is_no_section_key_is_a_bad_invocation``,
  ``test_the_flag_parser_and_the_document_parser_share_one_key``);
- ``load_run`` reading the set JSON before the target note
  (``test_the_set_is_read_before_the_target_note``);
- an insert's block ending in a blank line only where the note has none at the insertion point, so Hashi's
  verbatim splice (insertUnderMarker.ts, blockInsert.ts ``spliceLines``) leaves one blank line, never two
  (``test_an_insert_leaves_one_blank_line_after_its_block``, ``test_the_new_note_splice_uses_the_same_block``).

All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from review_deliver_helpers import ins  # noqa: E402,F401 — ins is a fixture
from test_046_t4_2_doc_sections import inst, script  # noqa: E402,F401 — fixtures
from test_046_t5_5_delivery_choices import SET_JSON, STEM, TARGET, approved, cli  # noqa: E402
from test_review_section_plan import BODY, ITEMS, WEEK, end, hashi_apply, note, row, start  # noqa: E402

__all__ = ["ins", "inst", "script"]                 # fixtures, used by name


# ---------------------------------------------------------------- one section key

@pytest.mark.parametrize("argv", [["--section-choice", "x=skip"], ["--confirm-moved", "s1000"],
                                  ["--section-choice", "S1=skip"], ["--section-choice", "s-1=review"],
                                  ["--confirm-moved", "s١"]],
                         ids=["not-s", "four-digits", "upper-case", "dash", "non-ascii-digit"])
def test_a_key_that_is_no_section_key_is_a_bad_invocation(ins, argv):
    with pytest.raises(SystemExit) as stop:
        ins.main(["preview", "--stem", STEM, *argv])
    assert stop.value.code == 2


@pytest.mark.parametrize("key", ["s1", "s12", "s999"])
def test_a_section_key_parses(ins, key):
    assert ins.build_parser().parse_args(["preview", "--stem", STEM, "--confirm-moved", key]).choices == {
        key: "confirm-moved"}


def test_the_flag_parser_and_the_document_parser_share_one_key():
    from lib import review_doc_parse as rdp
    for key in ("s1", "s999", "s1000", "S1", "x", "s١", ""):
        assert bool(rdp.SECTION_KEY.fullmatch(key)) == (key in ("s1", "s999")), key


# ---------------------------------------------------------------- the set before the note

def test_the_set_is_read_before_the_target_note(script, inst, ins, monkeypatch, capsys):
    """A set Hashi applies between the two reads must not meet a note read before it: read the set first."""
    fake = approved(script, inst, monkeypatch, capsys)
    for command in ("preview", "deliver"):
        fake.events.clear()
        cli(ins, monkeypatch, capsys, fake, command, "--stem", STEM)
        reads = [e for e in fake.events if e in (("read_file", SET_JSON), ("read_note", TARGET))]
        assert reads[:2] == [("read_file", SET_JSON), ("read_note", TARGET)], (command, fake.events)


# ---------------------------------------------------------------- one blank line after an insert

LAYOUTS = {   # id: (placement, note lines, the lines after Hashi's splice with S/B/E for the block)
    "under-blank-follows": ("under", ["# W13", "## Notes", "", "note text"],
                            ["# W13", "## Notes", "S", "B", "E", "", "note text"]),
    "under-whitespace-follows": ("under", ["# W13", "## Notes", " \t", "note text"],
                                 ["# W13", "## Notes", "S", "B", "E", " \t", "note text"]),
    "under-text-follows": ("under", ["# W13", "## Notes", "note text"],
                           ["# W13", "## Notes", "S", "B", "E", "", "note text"]),
    "under-heading-follows": ("under", ["## Notes", "### Sub", "s"], ["## Notes", "S", "B", "E", "", "### Sub", "s"]),
    "end-before-heading": ("end", ["## Notes", "n", "", "## Next"], ["## Notes", "n", "", "S", "B", "E", "", "## Next"]),
    "end-at-eof": ("end", ["## Notes", "n"], ["## Notes", "n", "S", "B", "E", ""]),
    "before-heading": ("before", ["# W13", "", "## Notes", "n"], ["# W13", "", "S", "B", "E", "", "## Notes", "n"]),
}


def _expanded(lines):
    out = []
    for line in lines:
        out += {"S": [start()], "B": BODY, "E": [end()]}.get(line, [line])
    return out


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_an_insert_leaves_one_blank_line_after_its_block(layout):
    import lib.review_section_plan as rsp
    placement, lines, expected = LAYOUTS[layout]
    p = rsp.plan_section(row("s1", "Notes", 2, None, placement), note(lines), WEEK, ITEMS)
    assert p.mode == "insert", p.mode
    after = hashi_apply(note(lines), p.action("I01", "n.md"))
    assert after == note(_expanded(expected)), after


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_the_new_note_splice_uses_the_same_block(layout):
    import lib.review_section_plan as rsp
    placement, lines, _ = LAYOUTS[layout]
    p = rsp.plan_section(row("s1", "Notes", 2, None, placement), note(lines), WEEK, ITEMS)
    assert p.block() == p.action("I01", "n.md")["content"].split("\n")


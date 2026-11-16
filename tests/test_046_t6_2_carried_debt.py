#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t6_2_carried_debt.py — the code debt Phase 5 carried into spec 046 T6.2.

docs/XDD/specs/046-review-template-sections/plan/phase-6.md T6.2 / T6.4 "Carried from Phase 5". Mechanisms a
mutation falsifies:

- the choice flags' key pattern being the section key ``^s[0-9]{1,3}$`` of ``lib/review_doc_parse.SECTION_KEY``, not
  a looser one (``test_a_key_that_is_no_section_key_is_a_bad_invocation``,
  ``test_the_flag_parser_and_the_document_parser_share_one_key``).

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
from test_046_t5_5_delivery_choices import STEM  # noqa: E402

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


#!/usr/bin/env python3
"""test_039_t1_5_refusal_reason_no_blank_default.py — spec 039 T1.5 (F5-AC5).

`_typed_name_refusal_reason` used to end in an unguarded `return` of the
blank sentence, so any code it did not recognise was announced to the owner
as a blank typed name. It must raise instead, and the three known codes must
keep the exact sentences spec 038 pinned
(test_038_t3_2_typed_name_refusal.py::test_each_refusal_class_has_its_own_exact_prose_sentence).

Mutation this falsifies: restoring the unguarded final `return` makes
`test_unknown_code_raises_instead_of_reporting_blank` red.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.refusal_sentences import typed_name_sentence  # noqa: E402
from lib.typed_name_check import REFUSAL_REASONS  # noqa: E402

BLANK_SENTENCE = "typed name refused: the typed name is blank"


@pytest.mark.parametrize("code", ["nonsense", "already_taken", "", "BLANK"])
def test_unknown_code_raises_instead_of_reporting_blank(code):
    with pytest.raises(ValueError):
        typed_name_sentence(code, "a/b.png")


def test_known_codes_keep_their_exact_sentences():
    # Same expectations as the 038 T3.2 pin.
    assert typed_name_sentence("separator_present", "a/b.png") == (
        "typed name refused: `a/b.png` contains a path separator, "
        "which is not allowed in a filename"
    )
    assert typed_name_sentence("forbidden_character", "a?b.png") == (
        "typed name refused: `a?b.png` contains a character "
        "Obsidian does not allow in a filename"
    )
    assert typed_name_sentence("blank", " ") == BLANK_SENTENCE


def test_every_member_of_refusal_reasons_is_handled():
    for code in REFUSAL_REASONS:
        assert typed_name_sentence(code, "x").startswith("typed name refused: ")

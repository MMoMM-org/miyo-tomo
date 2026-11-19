#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t4_3_unmapped_parse_golden.py — an unmapped review document parses exactly as in spec 045 (046 T4.3).

WHAT THIS GUARDS (spec 046 CON-2): without `pass1_sections` the parser reads
the edited document the way it read it before T4.3 taught it the section
parts — every field of every item, the warnings (`unknown-group`,
`duplicate-group`, `item-outside-group`, `approved-line-missing`), the group
order, the counts, the public items and the ApprovedReview record — for the
T4.2 unmapped goldens (a German week, an English month) under the edits
listed in the recorder, section look-alike lines included.

The golden tests/fixtures/046-t4-3-unmapped-parse-golden/parse.json was
recorded by `record.py` beside it from an export of the branch head before
T4.3; its docstring says when a re-record is legitimate. A failure here is a
changed unmapped parse, not a stale golden.

Fixtures only: no live vault, no live Kado.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
GOLDEN_DIR = TESTS_DIR / "fixtures" / "046-t4-3-unmapped-parse-golden"

_spec = importlib.util.spec_from_file_location("review_parse_golden_record", GOLDEN_DIR / "record.py")
record = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(record)
GOLDEN = json.loads((GOLDEN_DIR / "parse.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("doc,edit", record.cases())
def test_the_unmapped_parse_is_unchanged(doc, edit):
    assert record.capture(TESTS_DIR.parent, doc, edit) == GOLDEN[f"{doc}/{edit}"]


def test_the_golden_covers_every_case_and_pins_what_it_claims():
    assert sorted(GOLDEN) == sorted(f"{d}/{e}" for d, e in record.cases())
    warned = {w for case in GOLDEN.values() for w in case["warnings"]}
    assert {"unknown-group", "duplicate-group", "item-outside-group", "approved-line-missing"} <= warned
    lookalike = GOLDEN["week/section-lookalikes"]
    assert "unknown" in lookalike["group_order"]                      # no section key is a group without a mapping
    assert not any(g.startswith("s") for g in lookalike["group_order"])
    assert lookalike["counts"]["added"] == 3                          # the section-looking checkboxes are user items

#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t4_2_unmapped_doc_golden.py — the unmapped review document stays spec 045's byte for byte (046 T4.2).

WHAT THIS GUARDS (spec 046 F1-AC10, CON-2): without a mapping, `review-doc.py
write` renders exactly the document it rendered before T4.2 taught
`render_document` the section parts — for a German week (continuation lines,
escaped structure, a rejected item, an empty group, habits, the not-read and
partly-read parts) and an English month (target to be created, the month-only
groups, empty groups). The stdout result and meta.json's keys,
`pass1_counts` and `pass1_links` are pinned too.

The goldens in tests/fixtures/046-t4-2-unmapped-doc-golden/ were recorded by
`record.py` beside them from an export of the branch head before T4.2; its
docstring says when a re-record is legitimate. A failure here is a changed
unmapped document, not a stale golden.

Fixtures and fakes only: no live vault, no live Kado.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
GOLDEN_DIR = TESTS_DIR / "fixtures" / "046-t4-2-unmapped-doc-golden"

_spec = importlib.util.spec_from_file_location("review_doc_golden_record", GOLDEN_DIR / "record.py")
record = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(record)


@pytest.mark.parametrize("name", sorted(record.CASES))
def test_the_unmapped_document_is_byte_identical_to_spec_045(name):
    got = record.capture(TESTS_DIR.parent, name)
    assert got["doc"] == (GOLDEN_DIR / f"{name}.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", sorted(record.CASES))
def test_the_unmapped_result_and_meta_are_unchanged(name):
    got = json.loads(json.dumps(record.capture(TESTS_DIR.parent, name)["result"]))
    assert got == json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_the_goldens_pin_what_they_claim():
    # a golden without these parts would pin nothing of the escapes, the empty group or the month groups
    week = (GOLDEN_DIR / "week.md").read_text(encoding="utf-8")
    month = (GOLDEN_DIR / "month.md").read_text(encoding="utf-8")
    assert "  \\# keine Überschrift" in week and "- nichts gefunden" in week and "## Gewohnheiten" in week
    assert "## Only in the weekly reviews" in month and "(will be created)" in month
    assert "%%s" not in week + month and "%%review%%" not in week + month

#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t6_2_heading_walk.py — the template analysis and the note planner key headings by one walk (046 T6.2).

`review_mapping._tree` and `review_section_plan._Note.read` both turn a heading list into identities (text, level,
parent, occurrence) and ancestors. Phase 5 carried the drift risk of two copies; T6.2 shares one walk
(`review_mapping.walk_headings`). Mechanisms a mutation falsifies:

- either walk's result on the T1.2 template fixtures and the planner's note fixtures, against the golden recorded
  before the change (tests/fixtures/046-t6-2-heading-walk-golden/, record.py says how)
  (`test_both_walks_match_the_golden_recorded_before_the_change`);
- the planner keying by the shared walk, not a copy (`test_the_planner_keys_headings_by_the_shared_walk`).

All data is synthetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib import review_mapping as rm  # noqa: E402
from lib import review_section_plan as rsp  # noqa: E402
from test_review_mapping import TEMPLATES  # noqa: E402

GOLDEN_DIR = TESTS_DIR / "fixtures" / "046-t6-2-heading-walk-golden"
sys.path.insert(0, str(GOLDEN_DIR))
from record import NOTES, walk  # noqa: E402

GOLDEN = json.loads((GOLDEN_DIR / "walk.json").read_text(encoding="utf-8"))
TEXTS = {**{f"template:{k}": v for k, v in TEMPLATES.items()}, **{f"note:{k}": v for k, v in NOTES.items()}}


def test_the_golden_covers_every_fixture():
    assert set(GOLDEN) == set(TEXTS)


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_both_walks_match_the_golden_recorded_before_the_change(name):
    assert json.loads(json.dumps(walk(TEXTS[name], rm, rsp))) == GOLDEN[name]


def test_the_planner_keys_headings_by_the_shared_walk(monkeypatch):
    calls = []
    shared = rm.walk_headings

    def counted(*args, **kwargs):
        calls.append(args)
        return shared(*args, **kwargs)
    monkeypatch.setattr(rm, "walk_headings", counted)
    rm.heading_tree(TEXTS["note:repeats"])
    rsp._Note.read(TEXTS["note:repeats"])
    assert len(calls) == 2

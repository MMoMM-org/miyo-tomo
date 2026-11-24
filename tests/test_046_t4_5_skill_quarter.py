#!/usr/bin/env python3
# version: 0.1.1
"""test_046_t4_5_skill_quarter.py — the periodic-review skill's quarter branch (spec 046 T4.5; ADR-7; F6-AC6).

Model behaviour; these pins prove each imperative is in tomo/dot_claude/skills/periodic-review/SKILL.md:
- step 4 prints ``monthly_status`` and ``monthly_notes``
- a set-up quarter request goes on to step 3: the interim "cannot review a quarter yet" line is gone
- ``/review setup`` walks the quarter like the week and the month (no ``setup.quarter`` gate)
- the skill's and the command's descriptions name the quarter

Spec 047 T6.3 retired the step-5 pins of this file (the quarter read file by file, the quarter keys, the
privacy rule over the read files): the quarter keys are pinned against review-proposer.md in
tests/test_047_agents.py, the stage privacy rule in tests/test_047_skill_contract.py.

RED before T4.5: step 5 read one read file only, step 1 stopped a quarter request,
and the setup walked the quarter only when ``setup.quarter`` was ``present``.
"""
from __future__ import annotations

import re

from review_skill_helpers import COMMAND, SKILL, _section, _text

SETUP_LINE = ("- `setup` → step 2 for `week`, then for `month`, then for `quarter`, each starting from "
              "`current.<kind>`; then stop.")


def test_step4_prints_the_monthly_status_and_notes():
    assert ("`weekly_status` and `weekly_notes`, `monthly_status` and `monthly_notes` when present"
            in _section("4. Read the period"))


def test_a_set_up_quarter_request_goes_on_to_step3():
    start = _section("1. Start")
    assert "cannot review a quarter yet" not in _text(SKILL)
    assert "- `quarter` →" not in start
    missing = start.index("- `week`, `month` or `quarter` with `setup.<kind>` `missing`")
    assert missing < start.index("- Otherwise → step 3.")


def test_review_setup_walks_the_quarter_like_the_week_and_month():
    start = _section("1. Start")
    assert SETUP_LINE in start
    assert "setup.quarter" not in _text(SKILL)


def test_the_descriptions_name_the_quarter():
    head = _text(SKILL).split("\n---\n", 1)[0]
    (description,) = re.findall(r"^description: (.*)$", head, re.MULTILINE)
    assert "weekly, monthly or quarterly review" in description and "2026-Q1" in description
    assert "weekly or monthly review" not in description
    assert "Review one finished week, month or quarter with the user" in _text(SKILL)
    command_head = _text(COMMAND).split("\n---\n", 1)[0]
    assert "a finished week, month or quarter" in command_head


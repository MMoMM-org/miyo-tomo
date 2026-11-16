#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t4_5_skill_quarter.py — the periodic-review skill's quarter branch (spec 046 T4.5; ADR-7; F6-AC6).

Model behaviour; these pins prove each imperative is in tomo/dot_claude/skills/periodic-review/SKILL.md:
- step 5 reads ``read_path`` (the index for a quarter), then each ``read_parts`` entry in turn, one Read
  call after the other, and writes one ``proposals.json`` after the last part; nothing tells the model to
  read the parts in parallel or to join them into a file of its own
- the quarter keys are named the way the month's are (``monthly``, ``month_text``,
  ``only_in_monthly_links``, ``dailies_not_in_monthly``, ``report.monthly_status``), with the quarter marks;
  step 4 prints ``monthly_status`` and ``monthly_notes``
- a set-up quarter request goes on to step 3: the interim "cannot review a quarter yet" line is gone
- ``/review setup`` walks the quarter like the week and the month (no ``setup.quarter`` gate)
- the skill's and the command's descriptions name the quarter; the privacy rule covers every read file

RED before T4.5: step 5 read ``tomo-tmp/review/<stem>/read.json`` only, step 1 stopped a quarter request,
and the setup walked the quarter only when ``setup.quarter`` was ``present``.
"""
from __future__ import annotations

import re

from review_skill_helpers import COMMAND, SKILL, _section, _text

STEP5 = "5. Propose and write the document"
READ_LINE = ("Read `read_path` of step 4 and `config/vault-config.yaml`; `<language>` is the value of "
             "`review.language` in the config file.")
PARTS_LINE = ("A quarter: then read each file of `read_parts` in the listed order, one Read call after the other; "
              "in this step `read.json` means all these files together. Write `proposals.json` only after the "
              "last part.")
QUARTER_LINE = ('- Quarter (when `read.json` holds `monthly`, `report.monthly_status` `found`): `monthly_only` and '
                '`not_in_monthly` are what `only_in_monthly_links`, `dailies_not_in_monthly` and the `month_text` '
                'of the `monthly` entries show; a `monthly_only` item\'s sources name a `monthly` note; a section '
                'item carries `"mark": "monthly_only"` or `"mark": "not_in_monthly"` as a month\'s carries its marks.')
SETUP_LINE = ("- `setup` → step 2 for `week`, then for `month`, then for `quarter`, each starting from "
              "`current.<kind>`; then stop.")


def test_step5_reads_the_index_then_each_part_in_turn_then_writes_one_proposals_file():
    text = _section(STEP5)
    assert READ_LINE in text and PARTS_LINE in text
    write_at = text.index("Write `tomo-tmp/review/<stem>/proposals.json`:")
    assert text.index(READ_LINE) < text.index(PARTS_LINE) < write_at
    assert "tomo-tmp/review/<stem>/read.json" not in text, "the path comes from step 4's read_path"


def test_the_parts_are_never_read_in_parallel_or_joined_by_the_model():
    body = _text(SKILL).casefold()
    for phrase in ("parallel", "at once", "merge the parts", "join the parts", "combine the parts", "read-all"):
        assert phrase not in body, phrase
    assert ("Write only `tomo-tmp/review/<stem>/proposals.json` and `tomo-tmp/review/confirmed-<kind>.json` "
            "yourself") in _text(SKILL)


def test_step5_names_the_quarter_keys_like_the_months():
    text = _section(STEP5)
    assert QUARTER_LINE in text
    groups = text.index("- `done`: what happened and got done;")
    assert groups < text.index(QUARTER_LINE) < text.index("python3 scripts/review-doc.py write --stem <stem>")


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


def test_the_privacy_rule_covers_every_read_file():
    assert "- Never quote `read*.json`, a daily note," in _section("Rules")

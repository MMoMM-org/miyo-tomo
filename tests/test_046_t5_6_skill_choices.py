#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t5_6_skill_choices.py — the per-section choice dialogue of the periodic-review skill (spec 046 T5.6).

PRD F4-AC4, F4-AC6, F5-AC3, F3-AC4, F3-AC5; SDD User Interface & UX ("per-section choices in the existing Deliver
step"), ADR-12; docs/tomo/dot_claude/skills/periodic-review.md "Why Steps 7 and 8 Ask per Section in the Deliver
Step". The full lines of the stop bullet, `choice-invalid`, `section-dropped`, `section-empty`, the step 8 flags and
`name-taken` are pinned in tests/test_review_skill_pass2.py; this file pins the sub-bullets, their order and that the
names the skill spells are the scripts'. What each test falsifies:

- the empty-choices branch standing before the question (`test_a_stop_without_choices_ends_before_any_question`);
- the question replacing `1 Deliver · 2 Abort` and ending the turn, answers rerunning `preview` with the flags
  (`test_the_answers_rerun_preview_with_the_flags_and_go_to_deliver`);
- the flag and choice spellings drifting from `review-instructions.py` / `lib/review_section_plan`
  (`test_the_flags_and_choices_the_skill_names_are_the_scripts`);
- the stop lines coming after the plan and its notices (`test_the_stop_lines_follow_the_plan_and_its_notices`);
- the `name-taken` branch on `step` naming the script's step values (`test_name_taken_branches_on_the_scripts_steps`).
"""
from __future__ import annotations

import re

from review_cli_contract import REPO, load_script
from review_skill_helpers import _section

STOPS_HEAD = ("- `section-missing`, `section-ambiguous`, `section-broken`, `section-moved`, `block-in-review-section` "
              "or `landing-off-limits` with no other problem in `problems` →")
NO_CHOICES = "- An entry with empty `choices` → say that it can only be aborted; nothing is delivered; stop."
QUESTION = ("- Otherwise ask per listed section for one of its `choices`, or 0 Abort, and end the turn. The answer → "
            "rerun `preview` with `--section-choice <key>=skip`, `--section-choice <key>=review` or `--confirm-moved "
            "<key>` per listed section, keep these flags for step 8 and branch on the rerun by this list; `ok` with "
            "empty `problems` → print it as `ok` with empty `problems` does, then step 8 without asking again. "
            "0 → stop.")


def test_a_stop_without_choices_ends_before_any_question():
    text = _section("7. Preview")
    assert NO_CHOICES in text and QUESTION in text
    assert text.index(STOPS_HEAD) < text.index(NO_CHOICES) < text.index(QUESTION)
    assert text.index(QUESTION) < text.index("- `choice-invalid` →")


def test_the_answers_rerun_preview_with_the_flags_and_go_to_deliver():
    text = _section("7. Preview")
    stops = text[text.index(STOPS_HEAD):text.index("- `choice-invalid` →")]
    assert "1 Deliver" not in stops, "the choice question replaces the Deliver question"
    assert "Nothing is delivered; stop." not in stops.replace(NO_CHOICES, "")
    assert "end the turn" in QUESTION and "step 8 without asking again" in QUESTION


def test_the_flags_and_choices_the_skill_names_are_the_scripts():
    load_script("review-instructions.py")
    from lib import review_section_plan as rsp  # the scripts put tomo/scripts on sys.path

    source = (REPO / "tomo" / "scripts" / "review-instructions.py").read_text(encoding="utf-8")
    assert '"--section-choice"' in source and '"--confirm-moved"' in source
    assert f"--section-choice <key>={rsp.SKIP}" in QUESTION and f"--section-choice <key>={rsp.REVIEW}" in QUESTION
    assert "--confirm-moved <key>" in QUESTION
    stops = _section("7. Preview")
    for choice in rsp.CHOICES:
        assert f"`{choice}` " in stops[stops.index(STOPS_HEAD):stops.index(NO_CHOICES)], choice
    assert set(rsp.STOPS.values()) == set(re.findall(r"`([a-z-]+)`", STOPS_HEAD)) - {"problems"}


def test_the_stop_lines_follow_the_plan_and_its_notices():
    """The stopped preview prints the plan, its lines and its notice lines (the `ok` bullet without its question),
    then the stop lines, then the question."""
    text = _section("7. Preview")
    bullet = text[text.index(STOPS_HEAD):text.index(NO_CHOICES)]
    assert bullet.index("print the plan as `ok` with empty `problems` below does, without its question") < \
        bullet.index("then per entry of `sections` with a `stop` one line in `<language>` (step 5)")
    for named in ("`<section heading>` (step 5) of its `key`", "its `placement`", "its `choices`"):
        assert named in bullet, named


def test_name_taken_branches_on_the_scripts_steps():
    load_script("review-instructions.py")
    from lib import review_delivery as rdl

    text = _section("8. Deliver")
    assert f"`name-taken` with `step` `{rdl.NOTE}` →" in text
    assert f"`name-taken` with `step` `{rdl.SET_JSON}` or `{rdl.SET_MD}` →" in text
    assert "is not Tomo's" not in text[text.index(f"`step` `{rdl.SET_JSON}` or"):]

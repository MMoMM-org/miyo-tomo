#!/usr/bin/env python3
# version: 0.1.2
"""test_046_t5_6_skill_choices.py — the per-section choice dialogue of the periodic-review skill (spec 046 T5.6).

PRD F4-AC4, F4-AC6, F5-AC3, F3-AC4, F3-AC5; SDD User Interface & UX ("per-section choices in the existing Deliver
step"), ADR-12; docs/tomo/dot_claude/skills/periodic-review.md "Why Steps 7 and 8 Ask per Section in the Deliver
Step". The full lines of the stop bullet, `choice-invalid`, `section-dropped`, `section-empty`, the step 8 flags and
`name-taken` are pinned in tests/test_review_skill_pass2.py; this file pins the sub-bullets, their order and that the
names the skill spells are the scripts'. What each test falsifies:

- the empty-choices branch standing before the question (`test_a_stop_without_choices_ends_before_any_question`);
- the question replacing the first `1 Deliver · 2 Abort` and ending the turn, answers rerunning `preview` with the
  flags and its `ok` ending in the Deliver question (`test_the_answers_rerun_preview_with_the_flags_and_end_in_the_deliver_question`);
- `<language>` read from the config in step 7 itself (`test_the_stop_lines_language_is_read_where_it_is_used`);
- the flag and choice spellings drifting from `review-instructions.py` / `lib/review_section_plan`
  (`test_the_flags_and_choices_the_skill_names_are_the_scripts`);
- the stop lines coming after the plan and its notices (`test_the_stop_lines_follow_the_plan_and_its_notices`);
- the `name-taken` branch on `step` naming the script's step values (`test_name_taken_branches_on_the_scripts_steps`).
"""
from __future__ import annotations

import re

from review_cli_contract import REPO, load_script
from review_skill_helpers import SKILL, _section

STOPS_HEAD = ("- `section-missing`, `section-ambiguous`, `section-broken`, `section-moved`, `block-in-review-section` "
              "or `landing-off-limits` with no other problem in `problems` →")
NO_CHOICES = "- An entry with empty `choices` → say that it can only be aborted; nothing is delivered; stop."
QUESTION = ("- Otherwise ask per listed section for one of its `choices`, or 0 Abort, and end the turn. The answer → "
            "rerun `preview` with `--section-choice <key>=skip`, `--section-choice <key>=review` or `--confirm-moved "
            "<key>` per listed section, keep these flags for step 8 and branch on the rerun by this list; `ok` with "
            "empty `problems` → its bullet below, its question included. 0 → stop.")
PRINT_PLAN = "- Print the plan as `ok` with empty `problems` below does, without its question."
LANGUAGE = "one line in `<language>` (`review.language` of `config/vault-config.yaml`, Read it)"
PER_ENTRY = f"- Then per entry of `sections` with a `stop` {LANGUAGE}, naming:"
NAMED = ("- the section `<section heading>` (step 5) of its `key`",
         "- its `placement`",
         "- why it stops: its heading is not in the target note, is there more than once, Tomo's earlier block in "
         "it is broken, the block was moved under `block_at.heading`, the block sits inside the \"Tomo Review\" "
         "section, or it would land in an off-limits section",
         "- its `choices`: `skip` leaves the section out, `review` puts its items into the \"Tomo Review\" "
         "section, `confirm-moved` replaces the block where it sits now")
BESIDE = "- Beside another problem only that problem's line applies."


def test_a_stop_without_choices_ends_before_any_question():
    text = _section("7. Preview")
    assert NO_CHOICES in text and QUESTION in text
    assert text.index(STOPS_HEAD) < text.index(NO_CHOICES) < text.index(QUESTION)
    assert text.index(QUESTION) < text.index("- `choice-invalid` →")


def test_the_answers_rerun_preview_with_the_flags_and_end_in_the_deliver_question():
    """The rerun with the choices is approved like any clean preview: its `ok` bullet asks `1 Deliver · 2 Abort`."""
    text = _section("7. Preview")
    stops = text[text.index(STOPS_HEAD):text.index("- `choice-invalid` →")]
    assert "1 Deliver" not in stops, "the choice question replaces the first Deliver question"
    # The old pin looked for the capitalised "Nothing is delivered; stop." which NO_CHOICES (lower-case "nothing") can
    # never contain, so removing NO_CHOICES first made it unfalsifiable. Lower-case, matching what NO_CHOICES says.
    assert "nothing is delivered" not in stops.replace(NO_CHOICES, ""), "only the no-choices line ends the turn"
    assert "end the turn" in QUESTION and "its bullet below, its question included" in QUESTION
    assert "without asking again" not in text and "then step 8" not in QUESTION
    ok_bullet = text[text.index("- `ok` with empty `problems` →"):]
    assert "Then ask `1 Deliver · 2 Abort` and end the turn." in ok_bullet and "Deliver → step 8." in ok_bullet


def test_the_stop_lines_language_is_read_where_it_is_used():
    """Step 7 is reached by a later run in which step 5 never ran: `<language>` is defined in the stop bullet."""
    bullet = _section("7. Preview")
    bullet = bullet[bullet.index(STOPS_HEAD):bullet.index(NO_CHOICES)]
    assert LANGUAGE in bullet
    assert "`<language>` (step 5)" not in bullet


def test_the_flags_and_choices_the_skill_names_are_the_scripts():
    load_script("review-instructions.py")
    from lib import review_section_plan as rsp  # the scripts put tomo/scripts on sys.path

    source = (REPO / "tomo" / "scripts" / "lib" / "review_instructions_args.py").read_text(encoding="utf-8")
    assert '"--section-choice"' in source and '"--confirm-moved"' in source     # the script's flags (T6.2 split)
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
    assert bullet.index(PRINT_PLAN) < bullet.index(PER_ENTRY) < bullet.index(BESIDE)
    positions = [bullet.index(line) for line in NAMED]
    assert bullet.index(PER_ENTRY) < positions[0] and positions == sorted(positions), "named in this order"
    assert positions[-1] < bullet.index(BESIDE)


def test_name_taken_branches_on_the_scripts_steps():
    load_script("review-instructions.py")
    from lib import review_delivery as rdl

    text = _section("8. Deliver")
    assert f"`name-taken` with `step` `{rdl.NOTE}` →" in text
    assert f"`name-taken` with `step` `{rdl.SET_JSON}` or `{rdl.SET_MD}` →" in text
    assert "is not Tomo's" not in text[text.index(f"`step` `{rdl.SET_JSON}` or"):]


def test_the_stop_bullet_is_split_into_short_sub_bullets():
    """The stop bullet was one ~1,100-character sentence; its parts are sub-bullets (whitespace is collapsed by
    `_section`, so the nesting is read from the raw lines)."""
    lines = SKILL.read_text(encoding="utf-8").split("\n")
    head = next(n for n, line in enumerate(lines) if line.startswith(STOPS_HEAD.replace("- ", "  - ", 1)))
    assert lines[head].endswith("→"), "the head line holds the problems only"
    for line in lines[head + 1:head + 9]:
        assert len(line) < 330, line[:60]
    assert lines[head + 1].startswith("    - Print the plan")
    assert lines[head + 3].startswith("      - the section `<section heading>`")

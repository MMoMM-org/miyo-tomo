#!/usr/bin/env python3
# version: 0.1.3
"""test_review_skill_sections.py — spec 046 T2.3: the setup step's mapping table in the periodic-review skill.

The dialogue is model behaviour; these pins prove that each criterion has its imperative in
tomo/dot_claude/skills/periodic-review/SKILL.md: the table is printed from `match`'s `sections`
(PRD F2-AC1, ADR-9: the model words descriptions, keywords and groups only), every left-out heading
gets one line with its reason (F2-AC3), corrections are plain text in the existing Correct step —
edit, remove, add, off-limits heading only or with sub-sections, the analysis row (F2-AC2, F2-AC4,
F2-AC11, F2-AC12) — forward-looking sections ask for suggestions (F2-AC6), no extra question turn
(F2-AC2), no mappable heading prints no table (F2-AC9), a template not found names the name and asks
again (F7-AC1), dropped headings are named (F7-AC3), `--anchor` is not carried over a template change
(ADR-13 carve-out, F7-AC2), the quarter runs the same setup (F6-AC1), and the request continues in the
same session after the save (F2-AC10, an untested close-out gap of spec 044).

RED before T2.3: none of these lines is in the skill; step 2 names `week` or `month` only and step 1
routes a quarter to step 3, whose `review-read.py --kind quarter` exits 2. RED before the T2.3 code-review
fix: the two template-choice reruns added every flag of the last `match` call, its `--template` and
`--anchor` too.
"""
from __future__ import annotations

import json
import re

from review_cli_contract import REPO
from review_skill_helpers import COMMAND, SKILL, _section, _text

REVIEW_SCHEMA = REPO / "tomo" / "schemas" / "vault-config-review.schema.json"
SETUP_ROWS = REPO / "tomo" / "scripts" / "lib" / "review_setup_rows.py"

SETUP_KINDS = "`<kind>` is `week`, `month` or `quarter`."
NOT_FOUND = ("- `template_not_found` is set → say that the template `template_not_found.name` was not found "
             "(`source` `typed`: the name typed, `configured`: the saved one); the `template_candidates` line asks "
             "for another.")
NO_CANDIDATES = ("`template_candidates` is empty → in the same reply ask: Which template, typed, or `0` for none? "
                 "End the turn. A typed name → `<template>` is that name in double quotes; run "
                 "`python3 scripts/review-session.py match --kind <kind> --template <template>` with the flags of the "
                 "last `match` call added, except `--template` and `--anchor`, and continue with its output. `0` → "
                 "`<template>` is `none`; continue with this output: no template, a plain note.")
RERUN_FLAGS = "with the flags of the last `match` call added"
RERUN_EXCEPT = RERUN_FLAGS + ", except `--template` and `--anchor`, and continue with its output."
CARVE_OUT = ("- When `<template>` changes, the next `match` call carries no `--anchor` and `<anchor>` is unset: the "
             "new output proposes the place, and `needs_anchor` asks again.")
DROPPED = ("- `sections.dropped` is non-empty → say in one line per entry that `heading` (level `level`, under "
           "`parent`) of the earlier mapping is not in `<template>`: with `sections.mappable` true it is not kept; "
           "with `sections.mappable` false the save leaves the saved rows as they are.")
NOT_MAPPABLE = ("- `sections.mappable` is false → say in one line that no section of the template can be mapped, so "
                "the review goes into its own section only; print no table.")
TABLE = ("- `sections.mappable` is true → print the mapping table in the same reply, before the confirm question, "
         "from `sections.candidates` in their order:")
ROW = ("- Each candidate with `state` `offered` or with `saved` set is one row, numbered `s1`, `s2`, … in order: "
       "`heading_key` as heading (level, under parent), its `flags` in brackets, description, keywords, groups, "
       "placement and cap. With `saved` set, take them from `saved`; else placement and cap from `defaults`, and "
       "write the description: what to look for in the period's notes for that section, in `proposal.language`; "
       "add keywords (at most 12) and groups only where they fit.")
GROUPS = ("- Groups a row may name: `done`, `open`, `themes`, `growth`; for `month` also `weekly_only`, "
          "`not_in_weekly`; for `quarter` also `monthly_only`, `not_in_monthly`. Never `habits`.")
FORWARD = ("- A heading that looks ahead (what comes next, goals, wishes, what to start, stop or continue, what will "
           "be challenging) gets a description asking for suggestions drawn from what the period shows.")
LEFT_OUT = ("- Each other candidate is one line `—` with heading, level, parent and the `reason` in words: "
            "`templater` Templater code in the heading, `link` a link in the heading, `per-period-parent` repeats "
            "under headings that change per period, `off-limits` marked off-limits, `automatic` only automatic "
            "content, can get an analysis row.")
OFF_LIMITS_LINE = ("- Last the line `Off-limits:` with each `sections.off_limits` row (heading, level, parent, "
                   "`with sub-sections` when `with_subsections` is true), or `none`.")
CORRECT_TABLE = ("- Correct of the table: the user names a row (`s<n>` or its heading) and the change in plain text. "
                 "Change its description, keywords, groups, placement (`before`, `under`, `end`) or cap (1 to 30), or "
                 "remove it. Add a heading: an `offered` candidate → a row with its `defaults`; an `automatic` one "
                 "with a description → an analysis row with placement `review`; any other `left-out` one → say its "
                 "`reason` and add nothing; a heading not among the candidates → say it is not in `<template>`. Mark "
                 "a candidate off-limits, heading only or with sub-sections → it joins the `Off-limits:` line and its "
                 "row leaves the table (with sub-sections, the rows under it too); unmark → it leaves the line. Print "
                 "the table again with the change, run no `match` and ask `1 Confirm · 2 Correct · 3 Abort` again.")
RERUN_TABLE = ("- A `match` rerun with the same `<template>` keeps the table changes; with a changed `<template>` the "
               "table is built anew from the new `sections`.")
CONFIRM_ROWS = ("With `sections.mappable` true, add `sections`, the table rows in order, each with `heading`, `level`, "
                "`parent` and `occurrence` of its `heading_key`, `description`, `placement`, `cap`, and `keywords` and "
                "`groups` when set; and `off_limits`, each entry of the `Off-limits:` line with its `heading_key` "
                "fields and `with_subsections`; `[]` when there is none.")
POINTER = ("A pointer that starts with `/sections/<i>` is the row at index `<i>` of `sections`, counted from 0: "
           "name its heading. `/place` is the place of the review section, `/template` the template: name them in "
           "words.")
CONFIRM_QUESTION = "Ask `1 Confirm · 2 Correct · 3 Abort`."


def _setup() -> str:
    return _section("2. Setup")


def _table_block() -> str:
    text = _setup()
    return text[text.index(DROPPED):text.index(CONFIRM_QUESTION)]


# ── The table from `match` (F2-AC1, F2-AC3, F2-AC5, F2-AC6, ADR-9) ──────────


def test_the_table_is_printed_from_the_match_sections_in_candidate_order():
    text = _setup()
    for line in (TABLE, ROW):
        assert line in text, line
    assert text.index("`needs_anchor` is true") < text.index(TABLE) < text.index(CONFIRM_QUESTION), \
        "the table follows the proposal's questions and precedes the one confirm question"


def test_a_row_shows_level_and_parent_so_same_text_headings_are_told_apart():
    assert "`heading_key` as heading (level, under parent)" in ROW
    assert ROW in _setup()


def test_the_model_words_only_descriptions_keywords_and_groups():
    """ADR-9: placement and cap come from `defaults` or `saved`; the model writes the description and,
    where they fit, keywords and groups — never a reason, a key or a default of its own."""
    assert "With `saved` set, take them from `saved`; else placement and cap from `defaults`" in ROW
    assert GROUPS in _setup()


def test_every_left_out_heading_gets_one_line_with_its_reason():
    text = _setup()
    assert LEFT_OUT in text
    for reason in ("templater", "link", "per-period-parent", "off-limits", "automatic"):
        assert f"`{reason}`" in LEFT_OUT, reason


def test_the_reason_words_cover_every_reason_the_script_gives():
    from review_cli_contract import load_script

    load_script("review-session.py")
    from lib import review_mapping as rm  # the scripts put tomo/scripts on sys.path

    reasons = {rm.TEMPLATER, rm.LINK, rm.PER_PERIOD, rm.OFF_LIMITS, rm.AUTOMATIC}
    assert LEFT_OUT in _setup()
    assert {r for r in reasons if f"`{r}`" in LEFT_OUT} == reasons


def test_the_off_limits_line_lists_the_saved_marks_or_none():
    assert OFF_LIMITS_LINE in _setup()


def test_forward_looking_sections_ask_for_suggestions_from_the_period():
    assert FORWARD in _setup()


def test_no_mappable_heading_prints_no_table():
    text = _setup()
    assert NOT_MAPPABLE in text
    assert text.index(NOT_MAPPABLE) < text.index(TABLE)


# ── One turn (F2-AC2) ───────────────────────────────────────────────────────


def test_the_table_asks_no_question_of_its_own():
    block = _table_block()
    assert "End the turn" not in block
    assert not re.search(r"`1 [^`]+ · 2 ", block), "an option line inside the table block is an extra turn"
    assert "in the same reply, before the confirm question" in block
    assert _setup().count(CONFIRM_QUESTION) == 1


# ── Corrections in the Correct step (F2-AC2, F2-AC4, F2-AC11, F2-AC12) ──────


def test_corrections_are_plain_text_in_the_existing_correct_step():
    text = _setup()
    assert CORRECT_TABLE in text
    assert text.index("- Correct: for the folder") < text.index(CORRECT_TABLE) < text.index("- Abort: stop;")


def test_the_correct_step_edits_removes_adds_and_marks_off_limits():
    assert CORRECT_TABLE in _setup()
    for part in ("Change its description, keywords, groups, placement (`before`, `under`, `end`) or cap (1 to 30), "
                 "or remove it.",
                 "an `offered` candidate → a row with its `defaults`",
                 "any other `left-out` one → say its `reason` and add nothing",
                 "heading only or with sub-sections → it joins the `Off-limits:` line",
                 "unmark → it leaves the line"):
        assert part in CORRECT_TABLE, part


def test_an_automatic_heading_with_a_description_becomes_an_analysis_row():
    assert CORRECT_TABLE in _setup()
    assert "an `automatic` one with a description → an analysis row with placement `review`" in CORRECT_TABLE


def test_a_table_correction_runs_no_match_and_a_template_change_rebuilds_the_table():
    """F7-AC2: no row of the earlier template remains after a template correction."""
    text = _setup()
    assert "run no `match`" in CORRECT_TABLE
    assert RERUN_TABLE in text


# ── Template choice (F7-AC1, F7-AC3, ADR-13) ────────────────────────────────


def test_a_template_not_found_is_named_before_the_candidates_are_asked():
    text = _setup()
    assert NOT_FOUND in text
    assert text.index(NOT_FOUND) < text.index("`template_candidates` is non-empty")


def test_a_template_not_found_without_candidates_asks_for_a_typed_name_or_none():
    """Owner decision 2026-11-15: an empty candidate list must not fall through to `none` silently."""
    text = _setup()
    assert NOT_FOUND + " " + NO_CANDIDATES in text


def test_a_template_choice_rerun_adds_neither_the_old_template_nor_the_old_anchor():
    """Code review of T2.3: after a `template_not_found` the last `match` call carries the name that failed, and
    `match`'s parser keeps the last of two `--template` values (argparse `store`), so the old name added after the
    new one wins and the question repeats; an old `--anchor` would break the carve-out. Both reruns — the typed
    name and the candidate pick — name the exception, and no rerun adds the last call's flags without it."""
    text = _setup()
    assert text.count(RERUN_EXCEPT) == text.count(RERUN_FLAGS) == 2


def test_the_dropped_headings_are_named_after_a_template_change():
    assert DROPPED in _setup()


def test_a_dropped_heading_is_said_kept_or_not_by_whether_the_save_writes_rows():
    """Drift check of Phase 2: `match` lists saved rows the template lacks in `dropped` also when
    `sections.mappable` is false, and then Confirm writes no `sections`, so the writer changes no row —
    "is not kept" holds only with `mappable` true."""
    assert DROPPED in _setup()
    assert "with `sections.mappable` true it is not kept" in DROPPED
    assert "with `sections.mappable` false the save leaves the saved rows as they are" in DROPPED
    assert "With `sections.mappable` true, add `sections`" in CONFIRM_ROWS


def test_the_anchor_is_not_carried_over_a_template_change():
    text = _setup()
    assert CARVE_OUT in text
    assert "Never drop one of these flags from a rerun, except `--anchor` by the next line." in text
    assert text.index("Never drop one of these flags") < text.index(CARVE_OUT)


# ── Confirm writes the rows (F2-AC10) ───────────────────────────────────────


def test_confirm_writes_the_table_rows_and_the_off_limits_marks():
    text = _setup()
    assert CONFIRM_ROWS in text
    assert text.index("- Confirm: write") < text.index(CONFIRM_ROWS)


def test_a_row_pointer_of_setup_input_is_named_by_its_heading():
    assert POINTER in _setup()


def test_every_pointer_setup_input_returns_is_named_in_words():
    """`setup-input` refuses at `/sections/<i>`, `/sections/<i>/placement`, `/place` and `/template`
    (review_setup_rows.py); the skill names each, the row pointers by the row's heading."""
    source = _text(SETUP_ROWS)
    for pointer in ('"/place"', '"/template"', 'pointer + "/placement"', 'f"/{rc.SECTIONS}/{i}"'):
        assert pointer in source, pointer
    assert "A pointer that starts with `/sections/<i>`" in POINTER
    assert "`/place` is the place of the review section, `/template` the template" in POINTER
    assert POINTER in _setup()


def _skill_groups(line: str) -> dict:
    """The groups the GROUPS line names per kind: the shared ones, plus `for `<kind>` also …`."""
    body = line.split(": ", 1)[1].split(". Never ", 1)[0]
    shared, *extras = body.split("; ")
    base = re.findall(r"`([a-z_]+)`", shared)
    named = {"week": base}
    for part in extras:
        kind, rest = re.fullmatch(r"for `([a-z]+)` also (.*)", part).groups()
        named[kind] = base + re.findall(r"`([a-z_]+)`", rest)
    return {kind: sorted(groups) for kind, groups in named.items()}


def _schema_groups(schema: dict) -> dict:
    defs = schema["$defs"]
    return {kind: sorted(defs[f"{kind}Group"]["enum"]) for kind in ("week", "month", "quarter")}


def test_the_skill_names_per_kind_exactly_the_groups_the_schema_allows():
    """Drift check of Phase 2: the GROUPS line is a literal pin; this ties it to the schema's
    weekGroup / monthGroup / quarterGroup enums, so neither side can change alone."""
    (line,) = [ln.strip() for ln in _text(SKILL).splitlines() if ln.strip().startswith("- Groups a row may name: ")]
    named = _skill_groups(line)
    allowed = _schema_groups(json.loads(_text(REVIEW_SCHEMA)))
    assert named == allowed
    assert line.endswith(" Never `habits`.")
    assert all("habits" not in groups for groups in allowed.values())


def test_the_request_continues_in_the_same_session_after_the_save():
    """F2-AC10: the save of a first setup inside `/review <period>` reruns `start` and goes on with the request."""
    start = _section("1. Start")
    assert ("- `week`, `month` or `quarter` with `setup.<kind>` `missing` → step 2 for that kind, then rerun the "
            "`start` call above (skip the open reviews already handled) and continue here.") in start
    assert "Otherwise confirm in one line that the setup of `<kind>` is saved." in _setup()
    saved = _setup()[_setup().index("Otherwise confirm in one line that the setup of `<kind>` is saved."):]
    assert "stop" not in saved.lower(), "the save line ends the step, not the run"


# ── The quarter in the same flow (F6-AC1) ───────────────────────────────────


def test_the_quarter_runs_the_same_setup_step():
    assert SETUP_KINDS in _setup()


def test_a_quarter_request_sets_up_and_reads_nothing():
    """Reading a quarter is Phase 3: after its setup a quarter request stops before step 3."""
    start = _section("1. Start")
    line = ("- `quarter` → say in one line that the quarter setup is saved and that Tomo cannot review a quarter "
            "yet; stop, nothing is read.")
    assert line in start
    assert start.index("`setup.<kind>` `missing`") < start.index(line) < start.index("- Otherwise → step 3.")


def test_review_setup_includes_a_saved_quarter():
    assert ("- `setup` → step 2 for `week`, then for `month`, then for `quarter` when `setup.quarter` is `present`, "
            "each starting from `current.<kind>`; then stop.") in _section("1. Start")


def test_both_argument_hints_name_the_quarter():
    for path in (SKILL, COMMAND):
        head = _text(path).split("\n---\n", 1)[0]
        (hint,) = re.findall(r"^argument-hint: (.*)$", head, re.MULTILINE)
        assert "2026-Q1" in hint and "quarter" in hint, path.name

#!/usr/bin/env python3
# version: 0.2.3
"""test_review_skill.py — spec 045 T5.2: the /review command shim, the periodic-review skill and the help entry;
Pass 1 and the rules (the Pass 2 steps, the SDD rows and the CLI sweep are in the sibling files, P5 D8).

The dialogue criteria of /review are model behaviour; this file proves that each
one has an imperative in the runtime text (PRD F1, F2, F3, F5, F6 and the SDD's
Error Handling table), that every `python3 scripts/review-*.py` call in ANY
tomo/dot_claude/skills/**/SKILL.md parses with the called script's own argparse
parser (prefix abbreviations refused; the script is imported, never run), and
that the option lines the WHY document names appear in the skill verbatim.

The CLI contract comes from tests/review_cli_contract.py (the real parsers),
shared with tests/test_review_why_docs.py. The parse warnings come from
lib/review_doc_parse's constants. The Error Handling rows are hand-listed
from the SDD section "Runtime View / Error Handling"
(docs/XDD/specs/045-weekly-monthly-review/solution.md) — the table is prose,
not a machine-readable list — one entry per row that carries a user message.

The refusing problems, the notices and `drop`'s problem tokens are read from
lib/review_delivery.REFUSING / NOTICES, lib/review_actions and
review-instructions.py's constants, so a token the scripts add without a skill
line fails here; the statuses of `drop` and `replace --confirm` are literals in
the scripts and hand-listed, each with a test that reads them back from the
source.

RED before T5.2: neither tomo/dot_claude/commands/review.md nor
tomo/dot_claude/skills/periodic-review/SKILL.md exists, and tomo-help.md does
not list /review. RED before the T5.2 fix round: no `place-missing` branch for
mode `replace`, no stop line for `approved-line-missing` in Pass 2, `drop`'s
`kado-write-failed` said nothing was withdrawn, `replace --confirm` was
reported as `written` without a status branch. RED before the second fix
round: `place-too-deep` and `user-heading-collision` with mode `replace` went
to the heading pick, which replace mode never reads (a loop). RED before the
third fix round: a `user-heading-collision` on the rerun after a heading pick
went back to the heading pick — the same-named-heading cause
(`lib/review_actions._existing_note`, before `_insertion`) never reads
`--place-anchor`, and the preview output does not tell it from the
own-section cause, so the pick is offered once. RED before the Phase 5
cleanup: no `set-withdrawn` line (the refusing set grew by it) and the second
`kado-write-failed` of `drop` did not say the next `/review` offers Drop again.
RED before the Phase 5 drift round: the verbatim rule listed `warnings`,
`notices` and `problems` that steps 6-8 say in their own words; an Abort at
an open-review question went on with the next entry and the new request; no
line for `mode` `replace` in the preview, for `check-key-access`, nor for
`drop`'s shared refusals (`setup-missing`, `setup-invalid`,
`inbox-not-configured`); the heading pick did not name `place.anchor`.
"""
from __future__ import annotations

import re

import pytest

from review_cli_contract import REPO, load_script
from review_skill_helpers import (
    ABORT_RULE,
    ACCESS_RULE,
    ANSWER_RULE,
    COMMAND,
    EXIT_RULE,
    HELP,
    PLAIN_FORM,
    PRIVACY_RULE,
    SKILL,
    STATUS_FIRST,
    STOPPED_RULE,
    VERBATIM_RULE,
    _flat,
    _rules,
    _section,
    _text,
)


# ── Files, headers, frontmatter ─────────────────────────────────────────────


@pytest.mark.parametrize(("path", "version"), [(COMMAND, "0.1.0"), (SKILL, "0.1.9")], ids=["command", "skill"])
def test_carries_its_version_header(path, version):
    assert re.search(rf"^# version: {re.escape(version)}$", _text(path), re.MULTILINE)


def test_help_version_was_bumped():
    (version,) = re.findall(r"^# version: (\d+\.\d+\.\d+)$", _text(HELP), re.MULTILINE)
    assert tuple(int(p) for p in version.split(".")) > (0, 2, 22)


@pytest.mark.parametrize("path", [COMMAND, SKILL], ids=["command", "skill"])
def test_has_no_rationale_prose(path):
    text = _text(path)
    for pattern in (r"\bF\d+-AC\d+\b", r"\bADR-\d+\b", r"\bWhy:", r"\bWHY\b", r"\b20\d\d-\d\d-\d\d\b",
                    r"#31\b", r"\b[Ss]pec 0\d\d\b", r"\bT\d\.\d\b", r"\b[Bb]ecause\b", r"\b[Rr]ationale\b",
                    r"# STRICT"):
        assert not re.search(pattern, text), pattern


def test_skill_frontmatter_names_the_skill_with_minimal_tools_and_no_model_pin():
    head = _text(SKILL).split("\n---\n", 1)[0]
    assert "name: periodic-review" in head
    assert "user-invocable: true" in head
    assert "argument-hint:" in head
    (tools,) = re.findall(r"^allowed-tools: (.*)$", head, re.MULTILINE)
    assert {t.strip() for t in tools.split(",")} == {"Read", "Write", "Bash"}
    assert not re.search(r"^model:", head, re.MULTILINE)
    assert not re.search(r"^context:", head, re.MULTILINE)
    (description,) = re.findall(r"^description: (.*)$", head, re.MULTILINE)
    assert "MUST BE USED" in description
    assert "/review" in description
    assert "NOT for" in description and "/inbox" in description and "/note" in description


def test_the_skill_never_names_askuserquestion():
    assert "AskUserQuestion" not in _text(SKILL)


def test_command_routes_arguments_to_the_skill_in_the_main_session():
    text = _flat(COMMAND)
    assert "Invoke the `periodic-review` skill in this session with `$ARGUMENTS` as its arguments, verbatim" in text
    assert "Never dispatch it as a subagent" in text
    assert "Agent(" not in text
    head = _text(COMMAND).split("\n---\n", 1)[0]
    assert "name: review" in head and "description:" in head and "argument-hint:" in head


def test_help_lists_review():
    text = _text(HELP)
    menu = text[text.index("Tomo Help — what do you need?"):text.index("Then ask:")]
    assert re.search(r"^\s+\d+\. /review — ", menu, re.MULTILINE)
    assert "- **review /" in text
    entry = text[text.index("- **review /"):]
    entry = entry[:entry.index("\n- **")] if "\n- **" in entry else entry
    assert "`/review month`" in entry and "`/review setup`" in entry
    assert "`.claude/skills/periodic-review/SKILL.md`" in entry


# ── The rules every step obeys ──────────────────────────────────────────────


@pytest.mark.parametrize("rule", [STATUS_FIRST, STOPPED_RULE, PLAIN_FORM, ANSWER_RULE, VERBATIM_RULE, PRIVACY_RULE,
                                  ACCESS_RULE, ABORT_RULE, EXIT_RULE],
                         ids=["status-first", "stopped", "plain-form", "answer", "verbatim", "privacy", "access",
                              "abort", "exit"])
def test_rules_hold_each_line(rule):
    assert rule in _rules(), rule


def test_the_verbatim_rule_does_not_cover_what_the_steps_say_in_their_own_words():
    """Steps 6-8 map `warnings`, `notices` and the preview's `problems` to plain lines; a rule that demands
    them verbatim contradicts those lines."""
    rules = " ".join(_rules())
    assert "`warnings`, `notices` and `hints` of a script verbatim" not in rules
    assert "`problems`, `errors`, `warnings`" not in rules
    assert "said by the line its step gives it" in rules


def test_scripts_run_from_the_working_directory_not_the_skill_dir():
    text = _flat(SKILL)
    assert ("Run every script from the session's working directory (the instance root), "
            "never from the skill's base directory.") in text


def test_the_skill_writes_only_the_two_named_files_itself():
    assert ("Write only `tomo-tmp/review/<stem>/proposals.json` and `tomo-tmp/review/confirmed-<kind>.json` "
            "yourself; every other change goes through the scripts below.") in _flat(SKILL)


# ── Start (F2) ──────────────────────────────────────────────────────────────


def test_start_uses_the_equals_form_of_args():
    text = _flat(SKILL)
    assert "python3 scripts/review-session.py start --args='<request>'" in text
    assert "python3 scripts/review-session.py start --args " not in text
    assert "each `'` written as `'\\''`" in text
    assert "Keep the request text in the conversation." in text


def test_start_errors_show_expected_and_example_and_write_nothing():
    text = _section("1. Start")
    assert ("`error` set → show `error.kind`, `expected` and `example` verbatim (`invalid-period`, "
            "`not-periodic-note`, `unknown-argument`); for `unfinished-period` say that only finished periods can "
            "be reviewed and name `last_finished`. Stop; nothing is written.") in text
    assert "`problems` holds `inbox-not-configured` → say the inbox folder is not configured and stop." in text


def test_open_reviews_are_handled_before_the_new_request_in_listed_order():
    text = _section("1. Start")
    assert ("Handle every entry of `open_reviews` before the new request, in the order listed. Print each by "
            "`period`, `kind` and `state`, then branch on `state`:") in text
    assert text.index("every entry of `open_reviews`") < text.index("Then the new request, by `request.kind`:")
    assert "When the request names the same `period` as an open review, that open review is the request" in text


OPEN_REVIEW_STATES = {
    "failed-delivery": "- `failed-delivery` → ask `1 Resume · 2 Drop`. Resume → step 8 with the entry's `stem`. Drop → step 9 with the entry's `stem`.",
    "open": ("- `open` → ask `1 Continue · 2 Start over · 3 Abort`. Continue → step 6 with the entry's `stem`. "
             "Start over → step 4 with the entry's `period` and `kind` (the `write` there refuses with "
             "`review-exists` and step 5 asks before replacing). Abort → say in one line that the document stays "
             "as it is and end the run: no further entry, not the new request."),
    "delivered": ("- `delivered` → say in one line that its instruction set waits for Hashi, or for the user to "
                  "apply it by hand; no second set is delivered."),
    "move-refused": ("- `move-refused` → say in one line that the target note existed when Hashi applied the move, "
                     "so the inbox copy is still there; the user decides in Obsidian."),
    "target-missing": ("- `target-missing` → say in one line that the target note is gone since delivery; the user "
                       "decides in Obsidian."),
    "applied": ("- `applied` → say in one line that the review was applied. When `notices` holds "
                "`applied-not-recorded`, add that the line will show once more next time."),
}


@pytest.mark.parametrize("state", OPEN_REVIEW_STATES)
def test_every_listed_state_has_its_offer(state):
    assert OPEN_REVIEW_STATES[state] in _section("1. Start"), state


def test_an_abort_at_an_open_review_question_ends_the_whole_run():
    """Rule: on Abort no further script runs. Going on with the next entry or the new request would run
    `parse`, `review-read` and `write` after the user said Abort."""
    text = _section("1. Start")
    assert ("Continue with the next entry, then with the new request, after each one ends without an Abort; an "
            "Abort at any question of an entry ends the whole run: no further entry, not the new request.") in text
    assert "Abort → say in one line that the document stays as it is." not in text
    assert "and end the run: no further entry, not the new request." in OPEN_REVIEW_STATES["open"]


def test_the_listed_states_are_the_scripts_states():
    load_script("review-session.py")
    from lib import review_state  # the scripts put tomo/scripts on sys.path

    assert set(OPEN_REVIEW_STATES) == set(review_state.STATES)


def test_skipped_review_docs_get_one_line_each_never_silence():
    text = _section("1. Start")
    assert ("Say one line per entry of `skipped_review_docs` with its `doc_path` and `reason` "
            "(`frontmatter-unreadable`, `period-missing`, `stem-unsafe`); never drop one silently.") in text


def test_after_the_list_the_request_routes_by_kind_and_setup():
    text = _section("1. Start")
    assert "- `setup` → step 2 for `week`, then for `month`, each starting from `current.<kind>`; then stop." in text
    assert ("- `week` or `month` with `setup.<kind>` `missing` → step 2 for that kind, then rerun the `start` call "
            "above (skip the open reviews already handled) and continue here.") in text
    assert "- Otherwise → step 3." in text


def test_an_inferred_year_is_named_before_reading():
    assert ("When `request.year_inferred` is true, say in one line which year was chosen (the year of "
            "`request.period`) before reading.") in _section("3. The request")


# ── Setup (F1) ──────────────────────────────────────────────────────────────


def test_setup_previews_with_match_prints_evidence_and_hints_and_asks_in_plain_text():
    text = _section("2. Setup")
    assert "python3 scripts/review-session.py match --kind <kind>" in text
    assert ("Print `proposal`, `evidence` (`matched`, `unmatched`, `week_rule`, `folder_listing`, "
            "`format_problems`) and every line of `hints`.") in text
    assert "Ask `1 Confirm · 2 Correct · 3 Abort`." in text
    assert ("print it first: its values, or that none is saved, or its `invalid` pointers") in text


def test_setup_asks_the_week_question_in_plain_words_only_when_ambiguous():
    text = _section("2. Setup")
    assert ("`evidence.week_rule` is `ambiguous` (week only) → ask in plain text, before the confirm question: "
            "\"Which day does your week start on? Is week 1 the week with 1 January, or the first week with at "
            "least four days in the new year?\"") in text
    assert ("Map the answer to `--first-day <day>` (the day in lowercase) and `--min-days <n>` (`1` for the week "
            "with 1 January, `4` for at least four days)") in text
    assert ("python3 scripts/review-session.py match --kind <kind> --folder \"<folder>\" --format \"<format>\" "
            "--first-day <day> --min-days <n> --template <template>") in text, \
        "the week-rule rerun carries the template answer (fix round 1: it listed the candidates again)"
    assert "ISO" not in text
    # the question is keyed on `ambiguous` alone; the rerun's `given` asks nothing (final fix round)
    assert text.count("`evidence.week_rule` is `ambiguous`") == 1
    assert ("Its `evidence.week_rule` is `given`: the question is answered and not asked again; only "
            "`ambiguous` asks it.") in text
    assert "`week_rule` is `given`" not in text.replace("Its `evidence.week_rule` is `given`", ""), \
        "no branch acts on `given`, `inferred` or `default`"


def test_every_later_match_call_carries_the_week_answer_like_the_template_and_the_anchor():
    """Final fix round: a Correct rerun that drops `--first-day`/`--min-days` reports the notes' `ambiguous`
    again and re-asks the week question; the carry rule and the Correct branch name the two flags."""
    text = _section("2. Setup")
    assert ("- Every later `match` call of this step carries `--template <template>`, once `<anchor>` is given "
            "`--anchor \"<anchor>\"`, and once the week question is answered `--first-day <day> --min-days <n>`: "
            "the script then lists no candidates, asks for no anchor and reports `week_rule` `given`, so each "
            "question is asked once. Never drop one of these flags from a rerun.") in text


def test_setup_names_the_access_hint_for_kado_none_and_unreadable_templates():
    text = _section("2. Setup")
    assert "`evidence.folder_listing` is `kado-none` → the `hints` line says so; ask before proposing to create notes there." in text
    assert ("`proposal.template_kind` is `missing` → say that a plain note (title and review section) is proposed. "
            "`unreadable` → say the same and that the template may not be readable by the Kado key (no access).") in text


def test_setup_unsafe_format_names_the_rule():
    assert ("`error.kind` `unsafe-format` → say the name format must not contain `/`, `\\` or `..` and ask for "
            "another format; rerun `match` with it as `--format`.") in _section("2. Setup")


def test_setup_correction_reruns_match_for_names_and_carries_other_values_and_writes_only_on_confirm():
    text = _section("2. Setup")
    assert ("- Correct: for the folder, the format, the first day, the week-1 rule or the template, rerun `match` "
            "with the corrected value as its flag (`--folder`, `--format`, `--first-day` with `--min-days`, "
            "`--template` — a corrected template is `<template>` from then on, `none` for no template), the "
            "proposal's values for the others, `--template <template>`, `--anchor \"<anchor>\"` when given and "
            "`--first-day <day> --min-days <n>` once the week question was answered, and "
            "print the new proposal, evidence and hints; for heading, place, own sections, daily sections or "
            "language, print the proposal with the corrected value; a corrected anchor is `<anchor>` from then on. "
            "Then ask `1 Confirm · 2 Correct · 3 Abort` again. Write nothing before Confirm.") in text
    assert ("- Confirm: write `tomo-tmp/review/confirmed-<kind>.json` with the last `proposal` object as it is, "
            "the corrected values in place; add `daily_path_fix` from the `match` output only when the user "
            "confirmed it.") in text
    assert ("python3 scripts/review-session.py setup-input --kind <kind> --confirmed "
            "tomo-tmp/review/confirmed-<kind>.json") in text
    assert "`status` `invalid` → show `errors` and `problems` verbatim and ask `1 Correct · 2 Abort`" in text
    assert "python3 scripts/vault-config-writer.py review --input <input_path>" in text
    assert "rm -f tomo-tmp/review/confirmed-<kind>.json <input_path>" in text
    assert "On a non-zero exit of the writer, show its output verbatim and stop; nothing is saved." in text


def test_setup_abort_saves_nothing_and_an_earlier_saved_kind_stays():
    text = _section("2. Setup")
    assert ("- Abort: stop; nothing is saved and nothing is written. A kind confirmed and saved earlier in this run "
            "stays saved.") in text


def test_setup_asks_for_the_template_when_candidates_are_listed(tmp_path):
    """Phase 6 live walk: no `templates.mapping.<kind>` → `match` lists `template_candidates`; the skill asks,
    numbered with `0 none` last, ends the turn, and reruns `match --template` for a number (owner decisions 1, 2)."""
    text = _section("2. Setup")
    assert ("`template_candidates` is non-empty → say that no template is saved for `<kind>` and that these notes "
            "of the templates folder fit it; ask, numbered on one line with `0 none` last: "
            "`1 <name> · 2 <name> · 0 none`. End the turn.") in text
    assert "A number → `<template>` is `\"<name>\"`, the chosen name in double quotes; run:" in text
    assert "python3 scripts/review-session.py match --kind <kind> --template <template>" in text
    assert ("with the flags of the last `match` call added, and continue with its output. `0` → `<template>` is "
            "`none`; continue with this output: no template, a plain note. Without `template_candidates`, "
            "`<template>` is `\"<proposal.template>\"` when `proposal.template` is set, else `none`.") in text
    assert ("- Every later `match` call of this step carries `--template <template>`, once `<anchor>` is given "
            "`--anchor \"<anchor>\"`, and once the week question is answered `--first-day <day> --min-days <n>`: "
            "the script then lists no candidates, asks for no anchor and reports `week_rule` `given`, so each "
            "question is asked once. Never drop one of these flags from a rerun.") in text
    assert text.index("`template_candidates` is non-empty") < text.index("Print `proposal`"), \
        "the template question comes before the proposal is printed: its answer changes the proposal"


def test_setup_asks_for_the_anchor_before_confirm_when_none_could_be_proposed():
    """Owner decision 3: a proposal with `needs_anchor` is never offered to Confirm; the skill asks which heading
    (the `anchor_candidates`, numbered, or a typed heading) and puts the answer into `place.anchor`."""
    text = _section("2. Setup")
    assert ("`needs_anchor` is true → say that no heading could be proposed for the place of the review section "
            "(no template, or none with a heading below its title); print `anchor_candidates` as a numbered list "
            "and ask: Which heading, by number or typed? End the turn. The answer is `<anchor>` and "
            "`proposal.place.anchor`; print the proposal with it in place. Never offer Confirm while "
            "`place.anchor` is null.") in text
    assert text.index("`needs_anchor` is true") < text.index("Ask `1 Confirm · 2 Correct · 3 Abort`.")
    assert text.index("`evidence.week_rule` is `ambiguous`") < text.index("`needs_anchor` is true"), \
        "the anchor question follows the week question: its rerun is the output the candidates come from"


def test_daily_path_fix_is_applied_only_on_confirm():
    assert ("`daily_path_fix` is set → print `configured` and `found` and say the saved value is corrected to "
            "`found` only on Confirm.") in _section("2. Setup")


# ── Reading (F3) ────────────────────────────────────────────────────────────


def test_read_is_called_with_period_kind_and_stem():
    assert "python3 scripts/review-read.py --period <period> --kind <kind> --stem <stem>" in _section("4. Read the period")


def test_read_branches_on_status_before_nothing_to_review():
    text = _section("4. Read the period")
    assert "Branch on `status` first:" in text
    stopped = text.index("- `stopped` with `error` → the stopped rule.")
    empty = text.index("- `ok` with `nothing_to_review` true →")
    assert stopped < empty
    assert "Never read `nothing_to_review` from a `stopped` output." in text[stopped:empty]
    assert ("`stopped` with `problems` → show them verbatim (`setup-missing`, `setup-invalid` with `errors`, "
            "`daily-not-configured`, `dailies-not-read`) and the `report` when present, and stop; nothing is "
            "written.") in text


def test_nothing_to_review_says_so_with_the_access_hint_and_writes_nothing():
    assert ("- `ok` with `nothing_to_review` true → say that no daily note of the period holds content, that an "
            "empty result may also mean the Kado key cannot read the folder, and stop; nothing is written.") in _section("4. Read the period")


def test_the_read_report_names_states_pacing_and_the_limit_advice():
    text = _section("4. Read the period")
    assert "per day the dailies found and their `state`, the `linked` notes with `state` `missing` or `failed`" in text
    assert "`kado_empty` with the access hint" in text
    assert "the pacing line: `calls`, `retried`, `waited_s`, `not_read`" in text
    assert ("When `advice` holds `raise-kado-limit`, say that Kado turned calls away for its rate limit and suggest "
            "raising Kado's rate limit.") in text
    assert ("When `not_read` is non-empty, say that these days or notes are missing from the review and that the "
            "document will name them at its top; never say that everything was read.") in text


ADVICE_LINES = {
    "raise-kado-limit": ("When `advice` holds `raise-kado-limit`, say that Kado turned calls away for its rate limit "
                         "and suggest raising Kado's rate limit."),
    "check-key-access": ("When `advice` holds `check-key-access`, say that Kado answered with nothing for the "
                         "`kado_empty` sources and that the Kado key may not reach those folders; the user checks "
                         "its access."),
}


def test_every_advice_of_the_read_script_has_its_line():
    """The advice set is the `ADVICE_*` constants review-read.py imports (lib/review_pacer, lib/review_period)."""
    script = load_script("review-read.py")
    advice = {value for name, value in vars(script).items() if name.startswith("ADVICE_")}
    assert advice == set(ADVICE_LINES), sorted(advice ^ set(ADVICE_LINES))
    text = _section("4. Read the period")
    for token, line in ADVICE_LINES.items():
        assert line in text, token


# ── Proposals and the document (F4, F6) ─────────────────────────────────────


def test_the_model_reads_read_json_and_the_language_and_writes_proposals_json_only():
    text = _section("5. Propose and write the document")
    assert ("Read `tomo-tmp/review/<stem>/read.json` and `config/vault-config.yaml`; `<language>` is the value of "
            "`review.language` in the config file.") in text
    assert "Write `tomo-tmp/review/<stem>/proposals.json`:" in text
    assert '{"language": "<language>", "groups": {"done": [{"text": "<proposal>", "sources": [' in text
    assert "Habits are computed by the script: never propose them. Never propose text for the user's own sections." in text
    assert "at least one a daily of the period (for `weekly_only` a weekly note of the period)" in text
    assert "python3 scripts/review-doc.py write --stem <stem> --proposals tomo-tmp/review/<stem>/proposals.json" in text


def test_write_refusals_each_have_their_branch():
    text = _section("5. Propose and write the document")
    assert ("- `refused` with `proposals-invalid` → show `errors` verbatim, rewrite `proposals.json` once and rerun "
            "`write`; a second `proposals-invalid` → show it and stop.") in text
    assert ("- `refused` with `doc-name-taken` → say `doc_path` is a note that is not Tomo's review document and "
            "nothing was overwritten; stop.") in text
    assert "- `stopped` → the stopped rule; `problems` `kado-write-failed` → say nothing was written and stop." in text
    assert ("- `refused` with any other problem (`read-missing`, `read-invalid`, `setup-missing`, `setup-invalid`, "
            "`inbox-not-configured`) → show `problems` and `errors` verbatim and stop.") in text


def test_review_exists_asks_twice_before_replacing():
    text = _section("5. Propose and write the document")
    assert ("- `refused` with `review-exists` → say Tomo's review document for the period already exists at "
            "`doc_path` and that replacing it discards the user's edits in it; ask `1 Replace · 2 Keep it`. "
            "Replace → run `python3 scripts/review-doc.py replace --stem <stem> --confirm` and branch on its "
            "`status` by this list, `replaced` as `written`. Keep it → run "
            "`python3 scripts/review-doc.py replace --stem <stem> --abort` and say in one line that the "
            "document is kept.") in text
    assert "report its output as a `written` one" not in text


# `replace --confirm` is `render_and_write(allow_overwrite_review=True)` with `written` renamed
# (tomo/scripts/review-doc.py, replace_document / render_and_write / main's Refused and Stopped
# handlers); the script exposes no status constants, so the outcomes are hand-listed here.
REPLACE_CONFIRM_STATUSES = ("replaced", "refused", "stopped")


@pytest.mark.parametrize("status", REPLACE_CONFIRM_STATUSES)
def test_every_status_of_replace_confirm_has_a_branch_in_the_write_list(status):
    text = _section("5. Propose and write the document")
    branch = "- `written` →" if status == "replaced" else f"- `{status}`"
    assert branch in text, status
    assert "`replaced` as `written`" in text


def test_write_statuses_hand_listed_here_are_the_scripts():
    # Coupled to review-doc.py's function names (`render_and_write`, `write_document`, `replace_document`,
    # `_date_arg`) and its `"status": "..."` literals: a rename there fails this slice, not the skill.
    source = (REPO / "tomo" / "scripts" / "review-doc.py").read_text(encoding="utf-8")
    body = source[source.index("def render_and_write("):source.index("def write_document(")]
    assert set(re.findall(r'"status": "([a-z-]+)"', body)) == {"refused", "stopped", "written"}
    replace = source[source.index("def replace_document("):source.index("def _date_arg(")]
    assert 'result["status"] = "replaced"' in replace


def test_pass_1_ends_the_turn_with_the_document_report():
    text = _section("5. Propose and write the document")
    assert ("- `written` → report `doc_path`, `target` and `target_exists`, `target_found_elsewhere` when set, "
            "`counts` per group and every `rejected` item with its `group`, `index` and `reason`. Then say: edit "
            "the document in Obsidian, tick `- [x] Approved` and run `/review` again. End the turn.") in text

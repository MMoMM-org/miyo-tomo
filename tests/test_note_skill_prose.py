#!/usr/bin/env python3
# version: 0.1.10
"""test_note_skill_prose.py — spec 044 T3.2: the /note command and its skill.

The dialogue criteria of /note are model behaviour; this file proves that each
one has an imperative in the runtime text, and that every `python3 scripts/…`
call in the skill parses with the called script's own argparse parser, with
prefix abbreviations refused (the script is imported, never run). A live walk records the behaviour itself.

RED before T3.2: neither tomo/dot_claude/commands/note.md nor
tomo/dot_claude/skills/note-from-template/SKILL.md exists.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import shlex
import sys
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOT_CLAUDE = REPO_ROOT / "tomo" / "dot_claude"
COMMAND = DOT_CLAUDE / "commands" / "note.md"
SKILL = DOT_CLAUDE / "skills" / "note-from-template" / "SKILL.md"
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

REMEDY = (
    "Grant the Kado key read access to the template folder (`templates.base_path`), "
    "or do not use `/note`."
)
OUTLINE_EXIT_1 = ("When `template-outline.py` exits 1, name the template, show its `error` verbatim and say the "
                  "template may not be readable by the Kado key. Then: \"" + REMEDY + "\"")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flat(path: Path) -> str:
    """The file with every run of whitespace collapsed to one space."""
    return re.sub(r"\s+", " ", _text(path))


def _section(heading: str) -> str:
    """One `## ` section of the skill, whitespace collapsed."""
    text = _text(SKILL)
    begin = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", begin + 1)
    return re.sub(r"\s+", " ", text[begin:end if end != -1 else len(text)])


# ── Files, headers, frontmatter ─────────────────────────────────────────────


@pytest.mark.parametrize(("path", "version"), [(COMMAND, "0.1.0"), (SKILL, "0.2.8")],
                         ids=["command", "skill"])
def test_carries_its_version_header(path, version):
    assert re.search(rf"^# version: {re.escape(version)}$", _text(path), re.MULTILINE)


@pytest.mark.parametrize("path", [COMMAND, SKILL], ids=["command", "skill"])
def test_has_no_rationale_prose(path):
    # The one `# Why:` line under a `# STRICT — ` line is the repo's allowed rationale; nothing else is.
    text = re.sub(r"^(# STRICT — .*\n)# Why: .*\n", r"\1", _text(path), flags=re.MULTILINE)
    for pattern in (r"\bF\d+-AC\d+\b", r"\bADR-\d+\b", r"\bWhy:",r"\bWHY\b", r"\b20\d\d-\d\d-\d\d\b",
                    r"#169", r"\b[Ss]pec 0\d\d\b", r"\b[Bb]ecause\b", r"\b[Rr]ationale\b"):
        assert not re.search(pattern, text), pattern


def test_skill_frontmatter_names_the_skill_and_allows_asking():
    head = _text(SKILL).split("\n---\n", 1)[0]
    assert "name: note-from-template" in head
    assert re.search(r"allowed-tools:.*AskUserQuestion", head)
    assert re.search(r"allowed-tools:.*\bSkill\b", head), "the inbox-author hand-off needs the Skill tool"
    assert "description:" in head


def test_command_routes_arguments_to_the_skill_in_the_main_session():
    text = _flat(COMMAND)
    assert "Invoke the `note-from-template` skill" in text
    assert "$ARGUMENTS" in text
    assert "Never dispatch it as a subagent" in text
    assert "Agent(" not in text


# ── Session start ───────────────────────────────────────────────────────────


def test_scripts_run_from_the_working_directory_not_the_skill_dir():
    text = _flat(SKILL)
    assert ("Run every script from the session's working directory (the instance root), "
            "never from the skill's base directory.") in text
    assert "Run every script from the instance root." not in text


def test_start_uses_the_equals_form_of_args():
    assert "python3 scripts/note-session.py start --args='" in _flat(SKILL)
    assert "python3 scripts/note-session.py start --args " not in _flat(SKILL)
    assert "Keep the request text in the conversation." in _flat(SKILL)
    assert "does not echo" not in _flat(SKILL)


def test_kept_drafts_are_handled_before_the_new_request():
    text = _section("1. Start")
    assert "Handle every entry of `kept_drafts` before the new request" in text
    assert "title, template and created time" in text
    assert "Resume / Drop" in text


def test_interrupted_delivery_is_offered_resume_or_drop_never_silently_dropped():
    text = _section("1. Start")
    assert "An entry with an empty `failed_step` is an interrupted delivery" in text
    assert "Never drop a kept draft without asking" in text


def test_kept_draft_drop_names_landed_files_by_kind_and_never_promises_nothing_landed():
    text = _section("1. Start")
    assert ("Drop: when the entry's `steps_done` is non-empty, name each landed file by kind (`note` → the note, "
            "`instructions_json` → the instruction set JSON, `instructions_md` → the instruction set MD), "
            "say they are in the inbox with names starting `<stem>_` and that the user can delete them in "
            "Obsidian.") in text
    assert ("When `steps_done` is empty and the entry's `frozen` is true, say the note may already be in "
            "the inbox with a name starting `<stem>_`.") in text
    assert "When `steps_done` is empty and `frozen` is false, say that nothing landed in the inbox." in text
    # kado_config sets failed_step without any upload: failed_step must not gate "may already be in the inbox".
    assert "When `steps_done` is empty and `failed_step` is set" not in text
    assert "Never build a vault path yourself." in text
    assert "Drop: run `python3 scripts/note-instructions.py drop --stem <stem>` and confirm in one line." not in text


def test_a_resumed_draft_gets_no_process_offer():
    assert "Resume: run step 7 for that stem as a resume; skip step 8 for it." in _section("1. Start")
    assert "Never ask after a resumed delivery." in _section("8. Process offer")


def test_stale_stages_are_dropped_with_one_line():
    text = _section("1. Start")
    assert ("For each stem in `stale_stages`: say in one line that a draft whose state could not be read "
            "was discarded, then run `python3 scripts/note-instructions.py drop --stem <stem>`.") in text


def test_a_readable_stage_is_never_called_discarded():
    # The live walk: a printed draft awaiting approval was dropped with this sentence at the next /note.
    assert "an interrupted draft was discarded" not in _section("1. Start")


def test_unfinished_drafts_are_offered_continue_or_discard():
    text = _section("1. Start")
    assert ("Then handle every entry of `unfinished_drafts` before the new request. Print each by title "
            "(the template's filename without `.md` when `title` is empty), template and created time, "
            "then ask per entry: Continue / Discard. Never drop an unfinished draft without asking.") in text
    assert text.index("Handle every entry of `kept_drafts`") < text.index("every entry of `unfinished_drafts`")
    assert text.index("every entry of `unfinished_drafts`") < text.index("`mode` is `process` → step 9.")


def test_continue_of_a_printed_draft_returns_to_the_approval_question():
    text = _section("1. Start")
    branch = text[text.index("- Continue with `staged` true:"):text.index("- Continue with `staged` false:")]
    assert "run `python3 scripts/note-instructions.py stage --stem <stem>`" in branch
    assert "When `check.ok` is false" in branch
    assert ("print `note.md` with the header and ask in plain text: `1 Deliver · 2 Change something · 3 Abort`"
            in branch)
    assert "The source in the header is the entry's `source_path`; omit the skipped line" in branch
    assert "skip step 8 for it" in branch
    assert "Continue with the new request after it ends." in branch


def test_continue_of_an_unstaged_draft_restarts_the_questions_without_new():
    text = _section("1. Start")
    begin = text.index("- Continue with `staged` false:")
    branch = text[begin:text.index("- Discard:", begin)]
    assert ("run the step 4 `template-outline.py` and `read` calls with the entry's `template` as "
            "`<template path>`; never run `new` again.") in branch
    assert "step 5 for that stem" in branch
    assert "`source.md` as the material when it exists" in branch
    assert "Continue with the new request after it ends." in branch


def test_discard_of_an_unfinished_draft_drops_and_says_nothing_landed():
    text = _section("1. Start")
    assert ("- Discard: run `python3 scripts/note-instructions.py drop --stem <stem>` and say in one line "
            "that nothing landed in the inbox.") in text


# ── Setup (F1) ──────────────────────────────────────────────────────────────


def test_setup_prints_the_match_preview_before_asking():
    text = _section("2. First-run setup")
    assert "python3 scripts/note-session.py match --globs" in text
    assert ("Print the proposed globs, `matched`, `unmatched` and `excluded_daily`, then ask in plain text: "
            "`1 Confirm · 2 Correct · 3 Abort`") in text


def test_setup_reruns_match_and_reprints_on_a_correction_and_writes_only_on_confirm():
    text = _section("2. First-run setup")
    assert ("On Correct, take the user's globs, rerun `match`, reprint and ask again in plain text with "
            "`1 Confirm · 2 Correct · 3 Abort`.") in text
    assert "Write nothing before Confirm" in text
    assert "python3 scripts/vault-config-writer.py templates-include --input tomo-tmp/note/note-include.json" in text


def test_setup_abort_writes_nothing_and_a_confirmed_selection_stays():
    assert "On Abort, stop; nothing is written" in _section("2. First-run setup")
    assert "A saved `note_include` stays saved" in _flat(SKILL)


# ── Choosing the template (F2) ──────────────────────────────────────────────


def test_one_candidate_is_named_several_are_printed_and_asked():
    text = _section("3. Choose the template")
    assert "When one candidate fits, name it in one line and continue without asking" in text
    assert "When several fit, print them as a numbered list" in text


def test_several_fits_are_asked_by_number_in_plain_text():
    text = _section("3. Choose the template")
    assert ("When several fit, print them as a numbered list, then ask in plain text: Which number, or 0 Abort? "
            "Any number from the list is valid.") in text
    assert "three candidates" not in text
    assert "up to four options" not in text


def test_inbox_author_hand_off_names_the_default_type_so_it_cannot_bounce_back():
    text = _section("3. Choose the template")
    assert ("inbox-author → invoke the `inbox-author` skill with the Skill tool, passing the request and "
            "the line \"Compose a free-form note with requested type `default`; do not look for another "
            "template.\", and stop.") in text


def test_no_fitting_candidate_offers_the_three_ways_out():
    text = _section("3. Choose the template")
    assert "No selected template fits." in text
    assert "Adjust patterns / inbox-author / Abort" in text


def test_empty_listing_says_empty_or_not_readable_with_the_remedy():
    text = _section("3. Choose the template")
    assert "When `folder_listed` is 0" in text
    assert "The template folder is empty or not readable by the Kado key." in text
    assert REMEDY in text
    assert "Never say that no template exists" in text
    assert "Show `listing_error` verbatim" in text


def test_unreadable_template_gives_the_same_remedy():
    rules = _section("Rules")
    assert OUTLINE_EXIT_1 in rules
    assert "may not be readable by the Kado key" in rules
    assert REMEDY in rules
    assert ("When `template-outline.py` exits 2, show its `error`. This is the outline failure report; "
            "steps 4, 8 and 9 say what follows it.") in rules
    text = _section("4. Stage the draft")
    assert "`template-outline.py` exits 1: give the outline failure report. Ask: Another template / Abort." in text
    assert "Another template / Abort" in text
    assert "show its `error` verbatim" not in text


# ── Staging and the script flags ────────────────────────────────────────────


def test_new_and_outline_stage_use_their_exact_flags():
    text = _section("4. Stage the draft")
    assert 'python3 scripts/note-instructions.py new --template "<template path>" --source "<inbox note path>"' in text
    assert 'python3 scripts/template-outline.py --template "<template path>" --stage <stem>' in text
    assert "python3 scripts/note-process.py read --template <template stem> --outline tomo-tmp/note/<stem>/outline.json" in text


def test_exit_2_of_new_or_stage_is_a_user_fixable_input():
    text = _flat(SKILL)
    assert ("Exit 2 of `new` or `stage` whose error starts with `note-instructions: --title`, "
            "`note-instructions: --destination` or `note-instructions: --source` is refused input") in text
    for refused in ("a `--source` outside the inbox", "a title that is blank", "starts with a dot",
                    "an invisible character", "`{{` or `<%`", "a destination that is not a relative vault folder"):
        assert refused in text, refused
    assert "name what was refused and ask for another value" in text


def test_any_other_exit_2_of_new_or_stage_stops_and_keeps_the_draft():
    text = _flat(SKILL)
    assert ("Any other exit 2 of `new` or `stage` (config, local I/O, stem or `meta.json`): show the error "
            "verbatim and stop; do not drop the stem.") in text
    assert "Exit 2 of `new` or `stage` is refused input" not in text


def test_broken_process_file_and_missing_required_point_are_one_line_each():
    text = _section("4. Stage the draft")
    assert "When `read` reports `error`, say in one line that the process file is ignored and why" in text
    assert "When `error` is set" not in text
    assert "For each name in `missing_required`, say in one line" in text


# ── Questions (F3) ──────────────────────────────────────────────────────────


NEW_STRICT = ("# STRICT — A question about a draft or a list is plain text: print the content, end the message "
              "with the question and its options, and end the turn. Never call AskUserQuestion for it.")
NEW_WHY = ("# Why: an AskUserQuestion call went out without the draft; tool results are hidden, so the user "
           "approved a draft they never saw.")
OLD_STRICT_OPENERS = ("# STRICT — Before every AskUserQuestion call",
                      "# STRICT — Every Deliver / Change something / Abort question")


def _raw_section(heading: str) -> str:
    text = _text(SKILL)
    begin = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", begin + 1)
    return text[begin:end if end != -1 else len(text)]


def test_the_skill_has_one_strict_the_plain_text_rule_with_one_line_why():
    # Live: AskUserQuestion went out straight after a Read of note.md, under both print-first STRICT blocks.
    lines = _text(SKILL).splitlines()
    stricts = [i for i, line in enumerate(lines) if line.startswith("# STRICT — ")]
    assert [lines[i] for i in stricts] == [NEW_STRICT]
    assert lines[stricts[0] + 1] == NEW_WHY
    assert not lines[stricts[0] + 2].startswith("# Why:")
    assert NEW_STRICT in _raw_section("Rules")
    for old in OLD_STRICT_OPENERS:
        assert old not in _text(SKILL), old


def test_rules_define_the_plain_text_form_and_name_every_plain_text_question():
    rules = _section("Rules")
    assert ("- The plain-text questions are the step 2 glob question, the step 3 template choice, the step 5 "
            "question rounds, the step 6 approval question, the step 8 process offer and every step 9 "
            "question.") in rules
    assert ("- A plain-text question goes in the visible reply text: first the content, copied from the Read "
            "or Bash result (a tool result is not visible to the user), then the question and its options as "
            "the last lines, numbered on one line as `1 First · 2 Second`. Then end the turn. The next user "
            "message is the answer: the number or the option word; when it is unclear, ask again in plain "
            "text.") in rules
    assert "- Ask every other question with AskUserQuestion, with at most four options per question." in rules


# Each plain-text site: (section, the sentence that asks it).
PLAIN_TEXT_SITES = {
    "setup-globs": ("2. First-run setup", "Print the proposed globs, `matched`, `unmatched` and `excluded_daily`, "
                    "then ask in plain text: `1 Confirm · 2 Correct · 3 Abort`"),
    "setup-correct": ("2. First-run setup", "reprint and ask again in plain text with "
                      "`1 Confirm · 2 Correct · 3 Abort`."),
    "template-choice": ("3. Choose the template", "print them as a numbered list, then ask in plain text: "
                        "Which number, or 0 Abort?"),
    "question-rounds": ("5. Ask for open points", "Ask in plain text, as numbered questions, at most four open "
                        "points per round, in at most two rounds."),
    "required-re-ask": ("5. Ask for open points", "ask it again in plain text with no skip option."),
    "approval": ("6. Draft", "Then ask in plain text: the message holds the header and the full fenced "
                 "`note.md`, copied from the Read result, and ends with `1 Deliver · 2 Change something · 3 Abort`; "
                 "then end the turn."),
    "approval-after-change": ("6. Draft", "reprint `note.md` with the header, then ask again in plain text "
                              "with `1 Deliver · 2 Change something · 3 Abort`."),
    "approval-continue": ("1. Start", "print `note.md` with the header and ask in plain text: "
                          "`1 Deliver · 2 Change something · 3 Abort`"),
    "approval-after-failed-step": ("7. Deliver", "reprint and return to the step 6 question "
                                   "(`1 Deliver · 2 Change something · 3 Abort`)."),
    "process-offer": ("8. Process offer", "Print what would be saved, then ask in plain text: "
                      "`1 Save · 2 Not now · 3 Never`"),
    "process-destination": ("9. Process mode", "Ask in plain text for the destination folder, ending with "
                            "`1 Keep current · 2 Default · 3 Another folder`."),
    "process-required": ("9. Process mode", "Print the outline's headings as a numbered list, then ask in plain "
                         "text which are required; the user names them by number or heading, or none."),
    "process-guidance": ("9. Process mode", "Ask in plain text for the guidance text;"),
}


@pytest.mark.parametrize("site", PLAIN_TEXT_SITES)
def test_each_draft_or_list_question_is_asked_in_plain_text(site):
    heading, sentence = PLAIN_TEXT_SITES[site]
    assert sentence in _section(heading), site


@pytest.mark.parametrize("heading", ["2. First-run setup", "5. Ask for open points", "6. Draft",
                                     "8. Process offer", "9. Process mode"])
def test_no_plain_text_section_says_to_ask_with_askuserquestion(heading):
    assert "AskUserQuestion" not in _section(heading), heading


def test_askuserquestion_is_named_only_in_the_frontmatter_the_strict_and_the_dialog_rule():
    body = _text(SKILL).split("\n---\n", 1)[1]
    hits = [line for line in body.splitlines() if "AskUserQuestion" in line]
    assert hits == [NEW_STRICT, NEW_WHY,
                    "- Ask every other question with AskUserQuestion, with at most four options per question."]


def test_no_draft_or_list_question_keeps_its_dialog_option_form():
    text = _flat(SKILL)
    for dialog_form in ("Deliver / Change something / Abort", "Confirm / Correct / Abort",
                        "Save / Not now / Never for this template", "Keep current / Default / Another folder",
                        "multi-select"):
        assert dialog_form not in text, dialog_form


# Each dialog site: (section, its option list in slash form, never asked in plain text).
DIALOG_SITES = {
    "kept-draft": ("1. Start", "ask per entry: Resume / Drop."),
    "unfinished-draft": ("1. Start", "ask per entry: Continue / Discard."),
    "none-fits": ("3. Choose the template", "ask: Adjust patterns / inbox-author / Abort."),
    "another-source": ("4. Stage the draft", "then ask: Another source / Abort."),
    "another-template": ("4. Stage the draft", "Ask: Another template / Abort."),
    "name-taken-rename": ("7. Deliver", "offer Rename / Abort, naming `exists_path`."),
    "name-taken-keep": ("7. Deliver", "offer Keep / Drop, naming `exists_path`."),
    "withdrawn": ("7. Deliver", "offer Drop / Abort only (no Rename, no Keep)."),
}


@pytest.mark.parametrize("site", DIALOG_SITES)
def test_questions_without_draft_or_list_content_keep_the_dialog(site):
    heading, options = DIALOG_SITES[site]
    text = _section(heading)
    at = text.index(options)
    sentence = text[text.rfind(". ", 0, at) + 1:at + len(options)]
    assert "plain text" not in sentence and "AskUserQuestion" not in sentence, site


def test_every_dialog_question_has_at_most_four_options():
    assert "Ask every other question with AskUserQuestion, with at most four options per question." in _flat(SKILL)
    assert "Ask with at most four options per question." not in _flat(SKILL)


def test_question_budget_is_four_per_round_and_two_rounds():
    text = _section("5. Ask for open points")
    assert "at most four open points per round" in text
    assert "at most two rounds" in text
    assert "Required points first" in text
    assert "Mark each optional point as skippable; a skip is allowed only for optional points." in text


def test_covered_points_are_printed_and_no_open_point_means_no_question():
    text = _section("5. Ask for open points")
    assert "Print which points the material covers" in text
    assert "When no point is open, ask nothing and go to step 6" in text


def test_guidance_orders_and_weights_the_questions():
    assert "Order and weight the questions by the process `guidance`" in _section("5. Ask for open points")


def test_required_points_are_re_asked_with_no_skip_option():
    text = _section("5. Ask for open points")
    assert "ask it again in plain text with no skip option" in text
    assert "The user can only answer or abort" in text
    assert 'Any non-empty answer, "none" included, answers a required point' in text


def test_templater_is_never_executed_and_language_follows_the_call():
    text = _flat(SKILL)
    assert "Read Templater code (`<%` … `%>`) as a hint only; never run it and leave none in the draft" in text
    assert "Ask in the language the user writes in; keep the template's headings" in text


# ── Draft (F4) ──────────────────────────────────────────────────────────────


def test_stage_runs_with_a_title_before_deliver():
    text = _section("6. Draft")
    assert 'python3 scripts/note-instructions.py stage --stem <stem> --title "<title>"' in text
    assert "Never run `deliver` before `stage` has recorded a title" in _flat(SKILL)


def test_the_skill_prints_note_md_after_every_stage_never_draft_md():
    text = _section("6. Draft")
    assert "After every `stage`, print `tomo-tmp/note/<stem>/note.md` in full" in text
    assert "Never print `draft.md`" in text


def test_the_header_names_every_field():
    text = _section("6. Draft")
    assert "Template: <template stem> · Final name: <destination_file> · In the inbox until applied: <inbox_file name>" in text
    assert "Skipped, left empty: <points>" in text
    assert "Source <source path> is deleted when you apply the instruction set in Hashi." in text


def test_a_failing_check_is_fixed_before_asking():
    assert "When `check.ok` is false, fix `draft.md` and rerun `stage`" in _section("6. Draft")


def test_approval_options_and_changes_go_through_stage():
    text = _section("6. Draft")
    assert "`1 Deliver · 2 Change something · 3 Abort`" in text
    assert "rewrite `draft.md`, rerun `stage` and reprint `note.md`" in text
    assert "--destination" in text and "--keep-source true" in text


def test_frozen_title_during_resume():
    text = _flat(SKILL)
    assert ("During the resume of a kept draft whose `frozen` is true, title and destination are frozen."
            in text)
    assert "During a resume with a non-empty `steps_done`" not in text
    assert "During a resume, title and destination are frozen" not in text
    assert "When `stage` reports `frozen: true`" in text


def test_frozen_message_names_both_refused_changes():
    text = _section("6. Draft")
    assert "once `instructions_json` is in `steps_done`" not in text
    assert ("When `stage` reports `frozen: true`, say in one line that the requested change can no longer "
            "be made: title and destination once a delivery step may have landed, keeping the source once "
            "the instruction set may have landed. Keep the staged values.") in text
    assert "say in one line that the title and destination can no longer change" not in text


# ── Abort (F6) ──────────────────────────────────────────────────────────────


ABORT_LINES = {
    "3. Choose the template": (
        "Adjust patterns / inbox-author / Abort. Adjust patterns → step 2, starting from `note_include`. ",
        "and stop. Abort → stop.",
    ),
    "4. Stage the draft": (
        "`new` exits 1: say the source could not be read, then ask: Another source / Abort. "
        "Another source → rerun `new` with it. Abort → stop.",
        "report. Ask: Another template / Abort. Another template → drop the stem, return to step 3 without this "
        "template. Abort → drop.",
        "`template-outline.py` exits 2: show its `error`, drop the stem and stop.",
    ),
    "5. Ask for open points": ("Abort at any question → drop.",),
    "6. Draft": ("and ends with `1 Deliver · 2 Change something · 3 Abort`; then end the turn.", "- Abort → drop."),
    "7. Deliver": (
        "rerun `deliver`. Abort → drop.",
        "Drop: name the files of `steps_done` (`note` → `note_path`, `instructions_json`, "
        "`instructions_md`) so the user can delete them in Obsidian; when `steps_done` is empty, say the "
        "note may already be in the inbox as `note_path`. Then run `drop`.",
    ),
}


def test_drop_on_every_abort_path():
    text = _flat(SKILL)
    assert ("On Abort at any question, run `python3 scripts/note-instructions.py drop --stem <stem>` "
            "when a stem exists and confirm in one line") in text
    for heading, lines in ABORT_LINES.items():
        section = _section(heading)
        for line in lines:
            assert line in section, (heading, line)


# ── Delivery (F5, F6) ───────────────────────────────────────────────────────


def test_deliver_runs_with_the_stem():
    assert "python3 scripts/note-instructions.py deliver --stem <stem>" in _section("7. Deliver")


def test_name_taken_offers_rename_or_abort_and_never_overwrites():
    text = _section("7. Deliver")
    assert "On exit 3, read `frozen` and `steps_done` from the `deliver` output. Never overwrite." in text
    assert "meta.json" not in text
    assert "`frozen` false: offer Rename / Abort, naming `exists_path`." in text


def test_name_taken_branches_on_the_scripts_frozen_verdict_not_on_steps_done():
    text = _section("7. Deliver")
    empty = text.index("`frozen` false: offer Rename / Abort")
    landed = text.index("`frozen` true: offer Keep / Drop, naming `exists_path`.")
    assert empty < landed
    rename_branch = text[empty:landed]
    assert 'run `stage --stem <stem> --title "<new title>"`' in rename_branch
    assert "Keep" not in rename_branch
    assert "Keep: leave the draft for a later `/note`." in text[landed:]
    assert "On exit 3 during a resume" not in text


def test_name_taken_with_landed_steps_names_landed_files():
    text = _section("7. Deliver")
    landed = text.index("`frozen` true: offer Keep / Drop")
    assert "name the files of `steps_done`" in text[landed:]
    assert "when `steps_done` is empty, say the note may already be in the inbox" in text[landed:]


def test_name_taken_never_keys_the_freeze_on_steps_done():
    text = _section("7. Deliver")
    for stale in ("`steps_done` empty:", "`steps_done` non-empty:", "with `steps_done` empty",
                  "`steps_done` empty: offer", "`steps_done` non-empty: offer"):
        assert stale not in text, stale


def test_a_vanished_source_is_reported_in_one_line():
    assert "When `source_marked` is false and the draft has a source, say in one line that the source was not marked" in _section("7. Deliver")


def test_the_delivery_report_names_paths_and_the_hashi_step():
    text = _section("7. Deliver")
    assert "Next: review and apply the instruction set in Hashi." in text
    assert "`note_path`, `instructions_json`, `instructions_md`" in text


def test_a_failed_step_is_reported_and_the_draft_kept():
    assert ("On exit 1 with `status` `failed`, report the failed `step`; the draft stays for the next `/note`"
            in _section("7. Deliver"))


def test_an_empty_failed_step_names_both_draft_problems_and_sends_back_to_the_draft():
    assert ("When `step` is empty, the filled-note check or the frontmatter stamp failed instead: "
            "fix `draft.md`, rerun `stage`, reprint and return to the step 6 question "
            "(`1 Deliver · 2 Change something · 3 Abort`).") in _section("7. Deliver")


def test_a_withdrawn_action_offers_only_drop_or_abort_and_names_landed_files():
    text = _section("7. Deliver")
    assert ("On exit 1 with `status` `withdrawn`, say nothing was written in this run and why the action was "
            "withdrawn, then offer Drop / Abort only (no Rename, no Keep). On either answer: when `steps_done` "
            "is non-empty, first name its files by kind (`note` → `note_path`, `instructions_json`, "
            "`instructions_md`) so the user can delete them in Obsidian; when `steps_done` is empty and "
            "`frozen` is true, say the note may already be in the inbox as `note_path`. Then run `drop`.") in text
    assert "branch on `frozen` with the exit 3 options" not in text
    assert "On the withdrawn `frozen` true Drop" not in text
    assert "then branch on `frozen` as for exit 3." not in text
    assert "as for exit 3 with `steps_done` empty" not in text
    assert "- `status` `withdrawn`:" not in text


# ── Process offer and --process (F7) ────────────────────────────────────────


def test_process_offer_is_asked_once_with_three_answers_on_three_signals_only():
    text = _section("8. Process offer")
    assert "Ask once" in text
    assert ("only when `read` reported `exists` false and `declined` false and the session showed at least "
            "one signal") in text
    assert "Save, Not now or Never for this template?" in text
    for signal in ("the destination differs from `default_destination`",
                   ("a point named in the `Skipped, left empty:` line was filled through Change something "
                    "before Deliver"),
                   "the user asked for a question order"):
        assert signal in text, signal
    assert "Otherwise, or when `read` reported `exists` or `declined` true, do not ask" in text
    assert "re-asked" not in text


def test_process_offer_reruns_the_outline_and_writes_with_one_required_flag_per_point():
    text = _section("8. Process offer")
    assert 'python3 scripts/template-outline.py --template "<template path>" --out tomo-tmp/note/process-outline.json' in text
    assert ("python3 scripts/note-process.py write --template <template stem> "
            "--outline tomo-tmp/note/process-outline.json") in text
    assert "--required \"<point>\"" in text and "one `--required` per point" in text
    assert "--guidance-file tomo-tmp/note/process-guidance.md" in text
    assert "python3 scripts/note-process.py decline --template <template stem>" in text



@pytest.mark.parametrize("heading", ["8. Process offer", "9. Process mode"])
def test_process_paths_branch_on_template_outline_failures(heading):
    assert OUTLINE_EXIT_1 in _section("Rules")
    text = _section(heading)
    assert ("When `template-outline.py` exits 1 or 2, give the outline failure report, then run "
            "`rm -f tomo-tmp/note/process-outline.json tomo-tmp/note/process-guidance.md`, write nothing "
            "and stop.") in text
    assert OUTLINE_EXIT_1 not in text


def test_process_mode_defines_keep_current_and_default_destination():
    text = _section("9. Process mode")
    assert ("Ask in plain text for the destination folder: Keep current, Default or Another folder? Offer "
            "Keep current only when `exists` is true and `destination` is not empty.") in text
    assert "Keep current → `--destination \"<destination>\"` with the current value." in text
    assert "Default → omit `--destination`; notes then go to the atomic-note folder." in text
    assert "Another folder → ask in plain text for it and pass it as `--destination \"<folder>\"`." in text
    assert "(keep current / default / another folder)" not in text


def test_process_mode_shows_values_asks_and_writes_and_rejects_unknown():
    text = _section("9. Process mode")
    assert "When `process_template_path` is empty, say that the template is unknown and stop; write nothing" in text
    assert "Print the current values" in text
    assert "--out tomo-tmp/note/process-outline.json" in text
    assert "python3 scripts/note-process.py write" in text
    assert "rm -f tomo-tmp/note/process-outline.json" in text


# ── Script calls parse with the scripts' own parsers ────────────────────────


def _load_script(filename: str):
    mod_name = "note_skill_prose_" + filename[:-3].replace("-", "_")
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


PARSERS = {
    "note-session.py": lambda m, argv: m.build_parser().parse_args(argv),
    "note-instructions.py": lambda m, argv: m._parser().parse_args(argv),
    "note-process.py": lambda m, argv: m.build_parser().parse_args(argv),
    "template-outline.py": lambda m, argv: m._parse_args(argv),
    "vault-config-writer.py": lambda m, argv: m.build_parser().parse_args(argv),
}

CALL_RE = re.compile(r"python3 scripts/([\w-]+\.py)([^`\n]*)")


def _placeholder(match: re.Match) -> str:
    name = match.group(0)
    if name == "<stem>":
        return "2026-01-01_120000"
    if "path" in name:
        return "Templates/Meeting.md"
    return "X"


def _skill_calls() -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2).strip()) for m in CALL_RE.finditer(_text(SKILL))]


def test_skill_calls_every_script_with_a_known_parser():
    calls = Counter(script for script, _ in _skill_calls())
    assert calls == {"note-instructions.py": 8, "note-process.py": 5, "note-session.py": 3,
                     "template-outline.py": 3, "vault-config-writer.py": 1}
    assert set(calls) == set(PARSERS)


@pytest.mark.parametrize("script,rest", _skill_calls(), ids=lambda v: str(v)[:60])
def test_each_skill_call_parses_with_the_scripts_argparse(script, rest, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(argparse.ArgumentParser, "_get_option_tuples", lambda self, option: [])
    argv = shlex.split(re.sub(r"<[^>]+>", _placeholder, rest))
    try:
        PARSERS[script](_load_script(script), argv)
    except SystemExit as exc:
        pytest.fail(f"{script} {rest!r} rejected by argparse (exit {exc.code})")


DIALOG_SUBJECT_RULE = ("- The question text of every one of those other questions names what it is about: the draft's "
                       "title (the template's filename without `.md` when untitled) and created time, the "
                       "`exists_path`, the reason the action was withdrawn, or the template or source with its "
                       "one-line error.")


def test_dialog_question_text_names_its_subject():
    lines = _text(SKILL).split("\n## Rules\n", 1)[1].split("\n## ", 1)[0].splitlines()
    at = lines.index("- Ask every other question with AskUserQuestion, with at most four options per question.")
    assert lines[at + 1] == DIALOG_SUBJECT_RULE


# ── Numbered plain-text options (#169, owner decision 2026-11-06) ───────────

APPROVAL_NUMBERED = "`1 Deliver · 2 Change something · 3 Abort`"


def test_every_approval_site_pins_the_numbered_form():
    text = _flat(SKILL)
    assert text.count(APPROVAL_NUMBERED) == 5
    assert "Deliver, Change something or Abort" not in text


def test_glob_confirm_save_offer_and_destination_carry_their_numbered_forms():
    assert "`1 Confirm · 2 Correct · 3 Abort`" in _section("2. First-run setup")
    assert "`1 Save · 2 Not now · 3 Never`" in _section("8. Process offer")
    process = _section("9. Process mode")
    assert "`1 Keep current · 2 Default · 3 Another folder`" in process
    assert ("Offer Keep current only when `exists` is true and `destination` is not empty; without it end "
            "with `1 Default · 2 Another folder`.") in process


def test_the_candidate_choice_aborts_with_zero_so_every_listed_number_stays_valid():
    text = _section("3. Choose the template")
    assert "Which number, or 0 Abort?" in text
    assert "Any number from the list is valid." in text


def test_the_rules_say_the_answer_is_the_number_or_the_option_word():
    rules = _section("Rules")
    assert "numbered on one line as `1 First · 2 Second`" in rules
    assert "the number or the option word" in rules
    assert "when it is unclear, ask again in plain text" in rules


def test_no_plain_text_site_keeps_the_unnumbered_option_form():
    text = _flat(SKILL)
    for old in ("Confirm, Correct or Abort", "Save, Not now or Never", "Keep current, Default or Another folder",
                "Deliver, Change something or Abort", "Which number, or Abort"):
        assert old not in text, old

#!/usr/bin/env python3
# version: 0.1.3
"""test_review_skill.py — spec 045 T5.2: the /review command shim, the periodic-review skill and the help entry.

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
own-section cause, so the pick is offered once.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from review_cli_contract import (
    REPO,
    SKILLS_DIR,
    build_parsers,
    flags,
    load_script,
    parse_call,
    read_mentions,
    review_calls,
    review_subcommands,
    skill_files,
    stray_review_names,
    sub_mentions,
    unmatched_review_spans,
)

DOT_CLAUDE = REPO / "tomo" / "dot_claude"
COMMAND = DOT_CLAUDE / "commands" / "review.md"
HELP = DOT_CLAUDE / "commands" / "tomo-help.md"
SKILL = SKILLS_DIR / "periodic-review" / "SKILL.md"
SKILL_WHY = REPO / "docs" / "tomo" / "dot_claude" / "skills" / "periodic-review.md"


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


def _body() -> str:
    return _text(SKILL).split("\n---\n", 1)[1]


# ── Files, headers, frontmatter ─────────────────────────────────────────────


@pytest.mark.parametrize(("path", "version"), [(COMMAND, "0.1.0"), (SKILL, "0.1.3")], ids=["command", "skill"])
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


STATUS_FIRST = ("- Every script prints one JSON object. Read its `status` first and branch on it before any other key; "
                "a `stopped` or `refused` output is never read for `nothing_to_review`, `open_reviews`, `approved` "
                "or a plan.")
STOPPED_RULE = ("- `status` `stopped` with `error`: show `error.kind` and `error.detail` verbatim and stop; nothing "
                "was written.")
PLAIN_FORM = ("- Every question is plain text in the visible reply: first the content, copied from the Read or Bash "
              "result, then the question, numbered on one line as `1 First · 2 Second` as the last line. Then end "
              "the turn.")
ANSWER_RULE = ("- The next user message is the answer: a typed number or option word; when it is unclear, ask again "
               "in plain text.")
VERBATIM_RULE = ("- Show the `error`, `expected`, `example`, `problems`, `errors`, `warnings`, `notices` and `hints` "
                 "of a script verbatim; never paraphrase them.")
PRIVACY_RULE = ("- Never quote `read.json`, a daily note, a journal answer or a tracker value in your reply; print "
                "the scripts' reports and `section_md` only.")
ACCESS_RULE = ("- Never say a folder is empty or a note does not exist: `kado-none`, `kado_empty` and an empty result "
               "may mean the Kado key cannot read the folder; say so.")
ABORT_RULE = "- On Abort at any question, run no further script and write nothing; say in one line what stays as it is."
EXIT_RULE = "- A non-zero exit: show the output and the stderr line verbatim and stop."


def _rules() -> list[str]:
    return _text(SKILL).split("\n## Rules\n", 1)[1].split("\n## ", 1)[0].splitlines()


@pytest.mark.parametrize("rule", [STATUS_FIRST, STOPPED_RULE, PLAIN_FORM, ANSWER_RULE, VERBATIM_RULE, PRIVACY_RULE,
                                  ACCESS_RULE, ABORT_RULE, EXIT_RULE],
                         ids=["status-first", "stopped", "plain-form", "answer", "verbatim", "privacy", "access",
                              "abort", "exit"])
def test_rules_hold_each_line(rule):
    assert rule in _rules(), rule


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
             "as it is."),
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
            "--first-day <day> --min-days <n>") in text
    assert "ISO" not in text


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
    assert ("- Correct: for the folder, the format, the first day or the week-1 rule, rerun `match` with the "
            "corrected value as its flag (`--folder`, `--format`, `--first-day` with `--min-days`) and the "
            "proposal's values for the others, and print the new proposal, evidence and hints; for heading, place, "
            "own sections, daily sections or language, print the proposal with the corrected value. Then ask "
            "`1 Confirm · 2 Correct · 3 Abort` again. Write nothing before Confirm.") in text
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


# ── Pass 2 (F5, F6) ─────────────────────────────────────────────────────────


def test_continue_parses_the_document_and_branches_on_status_first():
    text = _section("6. Continue an open review")
    assert "python3 scripts/review-doc.py parse --stem <stem>" in text
    assert "Branch on `status` first:" in text
    assert ("- `not-found` → say the review document was not found at `doc_path` and ask `1 Start over · 2 Abort`. "
            "Start over → step 4 with the entry's `period` and `kind`. Abort → stop.") in text
    assert "report `counts` (`kept`, `unticked`, `deleted`, `added`)" in text


def test_every_parse_warning_has_a_plain_language_line():
    load_script("review-doc.py")
    from lib import review_doc_parse as rdp  # the scripts put tomo/scripts on sys.path

    warnings = {rdp.APPROVED_MISSING, rdp.UNKNOWN_GROUP, rdp.ITEM_OUTSIDE_GROUP, rdp.DUPLICATE_GROUP,
                rdp.FRONTMATTER_BROKEN}
    assert len(warnings) == 5
    text = _section("6. Continue an open review")
    lines = {
        "approved-line-missing": "- `approved-line-missing` → the Approved line is missing; restore `- [ ] Approved` at column 0 and tick it.",
        "unknown-group": "- `unknown-group` → a heading the parser does not know; its items do not land.",
        "duplicate-group": "- `duplicate-group` → the second heading of that name is ignored.",
        "frontmatter-broken": "- `frontmatter-broken` → the document's frontmatter could not be read; the period is taken from the stage.",
        "item-outside-group": "- `item-outside-group` → an item above the first heading; it is filed under an unknown group and does not land.",
    }
    assert set(lines) == warnings
    for name, line in lines.items():
        assert line in text, name


def test_an_unticked_approved_box_is_named_and_nothing_delivered():
    text = _section("6. Continue an open review")
    assert ("`approved` false → say the document is not approved yet and name the box `- [ ] Approved`; stop, "
            "nothing is delivered.") in text
    assert "`nothing_to_deliver` true → say nothing is ticked and ask `1 Start over · 2 Abort`" in text


def test_preview_prints_the_section_target_and_place_then_asks_deliver_or_abort_and_ends_the_turn():
    text = _section("7. Preview")
    assert "python3 scripts/review-instructions.py preview --stem <stem>" in text
    assert ("print `target`, `mode` (`insert`, `replace` or `new-note`), `place` (`anchor`, `placement`, `level`) "
            "and `section_md` in full, in a fenced block, copied from the Bash result") in text
    assert ("Then ask `1 Deliver · 2 Abort` and end the turn. Say in one line before it that a change is made by "
            "editing the document and running `/review` again. Deliver → step 8. Abort → stop; nothing is written, "
            "the document stays open.") in text
    assert "preview" not in text[text.index("Then ask `1 Deliver · 2 Abort`"):].replace("`preview`", "")


PREVIEW_PROBLEMS = {
    "not-approved": "- `not-approved` → name the box `- [ ] Approved`; stop.",
    "approved-line-missing": ("- `approved-line-missing` → say the Approved line is missing; restore `- [ ] Approved` "
                              "at the line start and tick it; stop."),
    "nothing-to-deliver": "- `nothing-to-deliver` → say nothing is ticked and ask `1 Start over · 2 Abort` as in step 6.",
    "replace-mode": ("- `place-missing`, `place-too-deep` or `user-heading-collision` with `mode` `replace` → say what "
                     "is wrong with the heading above the Tomo marker in the target note: there is none "
                     "(`place-missing`); it is one of the user's own sections, or an earlier heading of the same name "
                     "stands above it (`user-heading-collision`); it is too deep to replace under, the review heading "
                     "would pass level 5 (`place-too-deep`). Ask `1 Start over · 2 Abort`; Start over → step 4 with "
                     "the entry's `period` and `kind`, Abort → stop."),
    "user-heading-collision-after-pick": (
        "- `user-heading-collision` with `mode` `insert` or `new-note` after a heading pick (the rerun with "
        "`--place-anchor`) → say the target note holds a heading that clashes with the review: one named like the "
        "review heading, or the picked heading is one of the user's own sections; the user renames or removes the "
        "clashing heading in Obsidian. Ask `1 Start over · 2 Abort`; Start over → step 4 with the entry's `period` "
        "and `kind`, Abort → stop. Never print `headings` or ask for a number a second time."),
    "place-missing": ("- `place-missing` or `place-too-deep` with `mode` `insert` or `new-note` → say the configured "
                      "place is not in the target note, or would push the review heading past level 5; print "
                      "`headings` as a numbered list and ask: Which number, or 0 Abort? A number → rerun `preview` "
                      "with that heading as `--place-anchor`, keep it for step 8 and branch on the rerun by this "
                      "list. 0 → stop."),
    "user-heading-collision": ("- `user-heading-collision` with `mode` `insert` or `new-note` before any heading pick "
                               "→ say a heading of the user's with the same name is never replaced and the review "
                               "never lands inside one of the user's own sections; print `headings` as a numbered "
                               "list and ask: Which number, or 0 Abort? (as above)."),
    "set-exists": "- `set-exists` → say an instruction set for this review already waits for Hashi; nothing is delivered. Stop.",
}
PREVIEW_NOTICES = {
    "heading-renamed": "- `heading-renamed` → the marker was found under a renamed heading; the section is replaced there.",
    "target_appeared": "- `target_appeared` true → the target note was created since Pass 1; the plan targets it instead of a new note.",
    "variant_missing": ("- `variant_missing` or `templater_hint` → the template's Tomo variant is gone, or the template "
                        "holds Templater code; the readable instructions say to run Templater after the move."),
    "template_unmergeable": "- `template_unmergeable` → a plain note is built instead.",
    "unlanded-items": "- `unlanded-items` → `unlanded` kept items are under a heading the parser does not know and do not land.",
}


@pytest.mark.parametrize("problem", PREVIEW_PROBLEMS)
def test_every_refusing_preview_problem_has_its_line(problem):
    text = _section("7. Preview")
    assert PREVIEW_PROBLEMS[problem] in text, problem
    assert text.index(PREVIEW_PROBLEMS[problem]) < text.index("- `ok` with empty `problems` →"), problem


@pytest.mark.parametrize("notice", PREVIEW_NOTICES)
def test_every_preview_notice_is_one_line_and_the_question_still_follows(notice):
    text = _section("7. Preview")
    assert PREVIEW_NOTICES[notice] in text, notice
    assert text.index(PREVIEW_NOTICES[notice]) < text.index("Then ask `1 Deliver · 2 Abort`"), notice


def _branch_head(bullet: str) -> str:
    """The bullet up to its arrow: the condition a literal model matches, not any later mention of the tokens."""
    return bullet[:bullet.index("→") + 1]


def _branch_at(text: str, bullet: str) -> int:
    head = _branch_head(bullet)
    assert text.count(head) == 1, head
    return text.index(head)


def test_the_replace_mode_branch_covers_all_three_problems_and_comes_before_the_heading_pick():
    """Replace mode never reads `--place-anchor` (lib/review_actions._existing_note, marker branch), so the heading
    pick would refuse forever for any of the three; the replace bullet is matched first and names all three."""
    text = _section("7. Preview")
    replace = _branch_head(PREVIEW_PROBLEMS["replace-mode"])
    for problem in ("place-missing", "place-too-deep", "user-heading-collision"):
        assert f"`{problem}`" in replace, problem
    assert "`mode` `replace`" in replace
    at = _branch_at(text, PREVIEW_PROBLEMS["replace-mode"])
    assert at < _branch_at(text, PREVIEW_PROBLEMS["place-missing"])
    assert at < _branch_at(text, PREVIEW_PROBLEMS["user-heading-collision"])


def test_a_collision_after_a_heading_pick_ends_with_start_over_or_abort_never_a_second_pick():
    """`_first(headings, setup.heading)` in lib/review_actions._existing_note refuses before `_insertion` and never
    reads `--place-anchor`, and the preview output does not tell that cause from the own-section one (same
    `problems`, `headings`, `mode` and `place`), so the pick is offered once: the after-pick bullet is matched
    before both pick bullets, offers no list, and both picks route the rerun back through the list."""
    text = _section("7. Preview")
    after = PREVIEW_PROBLEMS["user-heading-collision-after-pick"]
    assert after in text
    at = _branch_at(text, after)
    assert _branch_at(text, PREVIEW_PROBLEMS["replace-mode"]) < at
    assert at < _branch_at(text, PREVIEW_PROBLEMS["place-missing"])
    assert at < _branch_at(text, PREVIEW_PROBLEMS["user-heading-collision"])
    assert "after a heading pick" in _branch_head(after) and "`--place-anchor`" in _branch_head(after)
    assert "before any heading pick" in _branch_head(PREVIEW_PROBLEMS["user-heading-collision"])
    assert "Which number" not in after and "numbered list" not in after
    assert "`1 Start over · 2 Abort`" in after
    assert "Never print `headings` or ask for a number a second time." in after
    assert "branch on the rerun by this list" in PREVIEW_PROBLEMS["place-missing"]
    assert "(as above)" in PREVIEW_PROBLEMS["user-heading-collision"]
    assert text.count("Which number, or 0 Abort?") == 2


@pytest.mark.parametrize("pick", ["place-missing", "user-heading-collision"])
def test_the_heading_pick_branches_apply_to_insert_and_new_note_only(pick):
    head = _branch_head(PREVIEW_PROBLEMS[pick])
    assert "with `mode` `insert` or `new-note`" in head
    assert "`replace`" not in head
    assert "otherwise" not in head


def _delivery_vocabulary():
    """``(REFUSING, NOTICES)`` of lib/review_delivery and the problem constants of lib/review_actions."""
    load_script("review-instructions.py")
    from lib import review_actions as ra  # the scripts put tomo/scripts on sys.path
    from lib import review_delivery as rdl

    return rdl.REFUSING, rdl.NOTICES, ra


# Tokens a Pass 2 bullet names that are statuses, keys or modes, never a problem of the plan or of drop.
NOT_PROBLEM_TOKENS = {"ok", "problems", "stopped", "not-found", "refused", "status", "mode", "error", "headings",
                      "insert", "replace", "new-note"}


def _problem_bullets(*headings: str) -> set[str]:
    """Every token a `- `<token>`` bullet of the named sections branches on (`- `a` or `b` →` names both)."""
    bullets: set[str] = set()
    for heading in headings:
        for line in re.findall(r"- (`[^→]+`)[^→]*→", _section(heading)):
            bullets.update(re.findall(r"`([a-z]+(?:-[a-z]+)*)`", line))
    return bullets - NOT_PROBLEM_TOKENS


def test_the_refusing_set_is_derived_and_every_token_has_a_stop_line_in_pass_2():
    refusing, notices, _ = _delivery_vocabulary()
    assert not set(refusing) & set(notices)
    covered = _problem_bullets("7. Preview", "9. Drop a failed delivery")
    missing = sorted(set(refusing) - covered)
    assert not missing, f"refusing problems without a branch in the skill's Pass 2: {missing}"


def test_every_refusing_preview_problem_pinned_here_is_in_the_refusing_set():
    refusing, _, _ = _delivery_vocabulary()
    pinned = _problem_bullets("7. Preview") - set(PREVIEW_NOTICES)
    assert pinned <= set(refusing), sorted(pinned - set(refusing))
    assert {"approved-line-missing", "already-applied"} <= set(refusing)


def test_the_notice_set_is_derived():
    _, notices, _ = _delivery_vocabulary()
    expected = set(notices) | {"target_appeared"}
    assert set(PREVIEW_NOTICES) <= expected
    named = set(re.findall(r"`([a-z_-]+)`", " ".join(PREVIEW_NOTICES.values())))
    missing = sorted(expected - named)
    assert not missing, f"notices without a line pinned here: {missing}"


def test_every_problem_constant_of_review_actions_is_classified():
    refusing, notices, ra = _delivery_vocabulary()
    not_problems = {ra.INSERT, ra.REPLACE, ra.NEW_NOTE, ra.NOTE_DOC_TYPE, ra.NOTE_STATE, ra.WIRE_TYPE}
    tokens = {value for name, value in vars(ra).items()
              if name.isupper() and isinstance(value, str) and re.fullmatch(r"[a-z]+(?:-[a-z]+)+", value)}
    unclassified = sorted(tokens - not_problems - set(refusing) - set(notices))
    assert not unclassified, f"review_actions problems in neither REFUSING nor NOTICES: {unclassified}"


def test_place_anchor_goes_to_preview_and_deliver():
    assert "With a chosen heading add `--place-anchor \"<heading>\"`." in _section("7. Preview")
    assert "Add `--place-anchor \"<heading>\"` when a heading was chosen in step 7." in _section("8. Deliver")


def test_deliver_branches_on_status_then_problems_or_failed_step():
    text = _section("8. Deliver")
    assert "python3 scripts/review-instructions.py deliver --stem <stem>" in text
    assert "Branch on `status` first:" in text
    assert ("- `delivered` or `resumed` → report `target`, `place`, `paths.set_json`, `paths.set_md` and "
            "`paths.note` when set, and \"Next: review and apply the instruction set in Hashi, or by hand with the "
            "readable instructions.\"") in text
    assert ("- `refused` → `name-taken` → say a note at `exists_path` is not Tomo's and nothing was overwritten; "
            "stop. `set-exists` → as in step 7. Any other → the step 7 lines; nothing was written.") in text
    assert ("- `stopped` → `doc-changed` → say the document was edited, or is open with unsaved edits, since the "
            "preview: save it and run `/review` again; the payloads in `paths` already written count as done, and "
            "the next `/review` offers Resume or Drop. `kado-write-failed` → say Kado refused or failed at "
            "`failed_step`; nothing more was written; the next `/review` offers Resume or Drop. Stop.") in text


def test_drop_reports_withdrawn_dropped_already_applied_and_set_changed():
    text = _section("9. Drop a failed delivery")
    assert "python3 scripts/review-instructions.py drop --stem <stem>" in text
    assert ("- `withdrawn` → say the set was withdrawn (nothing for Hashi to apply) and name every file in `paths` "
            "so the user can delete them in Obsidian.") in text
    assert "- `dropped` → say only the stage was removed (`removed`); nothing was in the inbox." in text
    assert ("- `already-applied` → say Hashi already applied an action of this review, so nothing is withdrawn "
            "and nothing more is delivered; stop.") in text
    assert ("- `set-changed` → say the set changed between read and write; run `drop` once more.") in text


def test_drop_kado_write_failed_names_the_partial_withdrawal_and_reruns_once():
    text = _section("9. Drop a failed delivery")
    assert ("- `kado-write-failed` → say the withdrawal may be partly written (the set may already hold nothing "
            "for Hashi while the readable file still lists the actions) and nothing else changed; run `drop` once "
            "more. A second `kado-write-failed` → show it and stop.") in text
    assert "nothing was withdrawn; stop" not in text


# `drop` answers with these statuses (tomo/scripts/review-instructions.py, drop(), plus main's
# NotFound / Refused / Stopped handlers); the script exposes its problem tokens as constants but not
# its statuses, so the statuses are hand-listed here and the problems are read from the code.
DROP_STATUSES = ("withdrawn", "dropped", "refused", "stopped", "not-found")


def _drop_problems() -> set[str]:
    script = load_script("review-instructions.py")
    from lib import review_delivery as rdl

    return {rdl.ALREADY_APPLIED, script.SET_CHANGED, script.KADO_WRITE_FAILED}


@pytest.mark.parametrize("status", DROP_STATUSES)
def test_every_drop_status_has_its_branch(status):
    assert f"- `{status}`" in _section("9. Drop a failed delivery"), status


def test_drop_statuses_hand_listed_here_are_the_scripts():
    # Coupled to review-instructions.py's function names (`drop`, `status`) and its `"status": "..."` literals:
    # a rename there fails this slice, not the skill.
    source = (REPO / "tomo" / "scripts" / "review-instructions.py").read_text(encoding="utf-8")
    body = source[source.index("def drop("):source.index("def status(")]
    assert set(re.findall(r'"status": "([a-z-]+)"', body)) == set(DROP_STATUSES) - {"not-found"}


def test_every_drop_problem_token_of_the_script_has_its_line():
    covered = _problem_bullets("9. Drop a failed delivery")
    missing = sorted(_drop_problems() - covered)
    assert not missing, f"drop problems without a branch: {missing}"


def test_drop_writes_the_set_before_the_readable_peer_so_a_late_failure_is_partial():
    """The skill's `kado-write-failed` wording rests on this order; a swap would make it wrong."""
    # Coupled to review-instructions.py's `drop` / `status` names and its write_file / write_note / meta call
    # text: a rename there fails this slice, not the skill.
    source = (REPO / "tomo" / "scripts" / "review-instructions.py").read_text(encoding="utf-8")
    body = source[source.index("def drop("):source.index("def status(")]
    assert body.index("write_file(paths[rdl.SET_JSON]") < body.index("write_note(paths[rdl.SET_MD]")
    assert body.index("write_note(paths[rdl.SET_MD]") < body.index('meta.data["withdrawn"] = True')


def test_status_is_never_called_by_the_skill():
    assert "review-instructions.py status" not in _text(SKILL)


# ── The SDD's Error Handling rows (solution.md, "Runtime View / Error Handling") ──
# One entry per row that carries a user message: (row, the skill phrase that is the message).

ERROR_HANDLING_ROWS = {
    "start invalid argument": "show `error.kind`, `expected` and `example` verbatim (`invalid-period`, `not-periodic-note`, `unknown-argument`)",
    "start unfinished period": "say that only finished periods can be reviewed and name `last_finished`",
    "any reader kado unreachable / auth": STOPPED_RULE,
    "review-read rate limit": "suggest raising Kado's rate limit",
    "review-read / match empty listing": ACCESS_RULE,
    "review-read no daily has content": "say that no daily note of the period holds content, that an empty result may also mean the Kado key cannot read the folder, and stop; nothing is written",
    "match template missing / unreadable": "the template may not be readable by the Kado key (no access)",
    "match unsafe name format": "the name format must not contain `/`, `\\` or `..`",
    "setup-input / writer invalid": "`status` `invalid` → show `errors` and `problems` verbatim and ask `1 Correct · 2 Abort`",
    "write proposals-invalid": "rewrite `proposals.json` once and rerun `write`; a second `proposals-invalid` → show it and stop",
    "write doc-name-taken": "not Tomo's review document and nothing was overwritten",
    "write review-exists": "ask `1 Replace · 2 Keep it`",
    "write / deliver / drop kado-write-failed": "`kado-write-failed` → say nothing was written and stop",
    "drop kado-write-failed after the set write": "say the withdrawal may be partly written",
    "parse not-found": "ask `1 Start over · 2 Abort`",
    "parse / preview not approved": "name the box `- [ ] Approved`",
    "parse approved-line-missing": "restore `- [ ] Approved` at column 0",
    "preview nothing-to-deliver": "say nothing is ticked and ask `1 Start over · 2 Abort`",
    "preview place-missing / place-too-deep": "print `headings` as a numbered list and ask: Which number, or 0 Abort?",
    "preview marker without a heading above (place-missing, mode replace)": "with `mode` `replace` → say what is wrong with the heading above the Tomo marker in the target note: there is none (`place-missing`)",
    "preview place-too-deep, mode replace": "it is too deep to replace under, the review heading would pass level 5 (`place-too-deep`). Ask `1 Start over · 2 Abort`",
    "preview user-heading-collision, mode replace": "it is one of the user's own sections, or an earlier heading of the same name stands above it (`user-heading-collision`)",
    "preview user-heading-collision": "say a heading of the user's with the same name is never replaced",
    "preview user-heading-collision after a heading pick": "the user renames or removes the clashing heading in Obsidian. Ask `1 Start over · 2 Abort`",
    "preview heading-renamed": "the marker was found under a renamed heading; the section is replaced there",
    "preview template variant gone": "the readable instructions say to run Templater after the move",
    "preview template_unmergeable": "a plain note is built instead",
    "preview unlanded-items": "`unlanded` kept items are under a heading the parser does not know and do not land",
    "preview / deliver set-exists": "say an instruction set for this review already waits for Hashi; nothing is delivered",
    "deliver name-taken": "say a note at `exists_path` is not Tomo's and nothing was overwritten",
    "deliver doc-changed": "save it and run `/review` again; the payloads in `paths` already written count as done",
    "deliver failed step": "the next `/review` offers Resume or Drop",
    "preview / deliver target appeared": "the target note was created since Pass 1; the plan targets it instead of a new note",
    "drop no step began": "say only the stage was removed (`removed`); nothing was in the inbox",
    "drop a step began": "say the set was withdrawn (nothing for Hashi to apply) and name every file in `paths` so the user can delete them in Obsidian",
    "status move-refused / target-missing": "say in one line that the target note existed when Hashi applied the move",
    "any script unexpected exception": EXIT_RULE,
}


@pytest.mark.parametrize("row", ERROR_HANDLING_ROWS)
def test_every_error_handling_row_with_a_user_message_has_its_skill_branch(row):
    assert ERROR_HANDLING_ROWS[row] in _flat(SKILL), row


# ── The WHY document and the skill agree on every option line ───────────────


def test_every_option_line_the_why_document_names_is_in_the_skill():
    option_lines = set(re.findall(r"`1 [^`]+ · 2 [^`]+`", _text(SKILL_WHY)))
    assert option_lines, "the WHY document names no numbered option line"
    missing = sorted(line for line in option_lines if line not in _text(SKILL))
    assert not missing, f"option lines named in the WHY document but not in the skill: {missing}"


def test_the_why_document_names_the_skills_question_wording():
    assert "Which number, or 0 Abort?" in _text(SKILL_WHY)


# ── CLI-contract sweep over every skill that names a review script ──────────


def _all_review_calls() -> list[tuple[str, str, str]]:
    return [(path.parent.name, script, rest) for path in skill_files()
            for script, rest in review_calls(_text(path))]


def test_the_review_skill_calls_every_script_of_the_flow():
    calls = Counter(script for skill, script, _ in _all_review_calls() if skill == "periodic-review")
    assert calls == {"review-session.py": 4, "review-read.py": 1, "review-doc.py": 4, "review-instructions.py": 3,
                     "vault-config-writer.py": 1}


@pytest.mark.parametrize("skill,script,rest", _all_review_calls(), ids=lambda v: str(v)[:60])
def test_each_review_call_in_any_skill_parses_with_the_scripts_argparse(skill, script, rest, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    try:
        parse_call(script, rest)
    except SystemExit as exc:
        pytest.fail(f"{skill}: {script} {rest!r} rejected by argparse (exit {exc.code})")


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_every_review_script_name_in_any_skill_is_a_call_or_a_contract_mention(path):
    text = _text(path)
    assert not stray_review_names(text), stray_review_names(text)
    assert not unmatched_review_spans(text), unmatched_review_spans(text)


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_every_contract_mention_in_any_skill_names_an_existing_subcommand_and_flag(path):
    text = _text(path)
    subcommands = review_subcommands(build_parsers())
    for script, sub, mention_flags in sub_mentions(text):
        assert sub in subcommands[script], (path.parent.name, script, sub)
        bad = [flag for flag in mention_flags if flag not in flags(subcommands[script][sub])]
        assert not bad, (path.parent.name, script, sub, bad)
    read_flags = flags(build_parsers()["review-read.py"])
    for mention in read_mentions(text):
        bad = [flag for flag in mention if flag not in read_flags]
        assert not bad, (path.parent.name, "review-read.py", bad)


def test_the_sweep_sees_the_review_skill():
    """Guards the guard: a glob that misses the skill passes every sweep above vacuously."""
    assert SKILL in skill_files()
    assert any(skill == "periodic-review" for skill, _, _ in _all_review_calls())

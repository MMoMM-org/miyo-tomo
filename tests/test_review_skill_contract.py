#!/usr/bin/env python3
# version: 0.1.2
"""test_review_skill_contract.py — spec 045 T5.2 / P5: the SDD's Error Handling rows, the WHY document's
option lines and the CLI-contract sweep over every skill that names a review script.

The rows are hand-listed from docs/XDD/specs/045-weekly-monthly-review/solution.md ("Runtime View /
Error Handling"), one per row that carries a user message; the sweep parses every
`python3 scripts/review-*.py` call in any tomo/dot_claude/skills/**/SKILL.md with the called script's
own argparse parser (tests/review_cli_contract.py). Split out of tests/test_review_skill.py at Phase 5
(D8); the pins moved verbatim.
"""
from __future__ import annotations

import re
from collections import Counter

import pytest

from review_cli_contract import (
    build_parsers,
    flags,
    parse_call,
    read_mentions,
    review_calls,
    review_subcommands,
    skill_files,
    stray_review_names,
    sub_mentions,
    unmatched_review_spans,
)
from review_skill_helpers import ACCESS_RULE, EXIT_RULE, SKILL, SKILL_WHY, STOPPED_RULE, _flat, _text


# ── The SDD's Error Handling rows (solution.md, "Runtime View / Error Handling") ──
# One entry per row that carries a user message: (row, the skill phrase that is the message).

ERROR_HANDLING_ROWS = {
    "start invalid argument": "show `error.kind`, `expected` and `example` verbatim (`invalid-period`, `not-periodic-note`, `unknown-argument`)",
    "start unfinished period": "say that only finished periods can be reviewed and name `last_finished`",
    "any reader kado unreachable / auth": STOPPED_RULE,
    "review-read rate limit": "suggest raising Kado's rate limit",
    "review-read / match empty listing": ACCESS_RULE,
    "start bare argument while a review is listed": "say in one line that a bare `/review` starts no new period while a review is listed",
    "review-read no daily has content": "say that no daily note of the period holds content and name the days of `report.days`; when `advice` holds `check-key-access`, add that Kado answered with nothing",
    "match template missing / unreadable": "the template may not be readable by the Kado key (no access)",
    "match no mapping entry for the kind": "`1 <name> · 2 <name> · 0 none`",
    "match no anchor could be proposed": "Which heading, by number or typed?",
    "match template without a frontmatter block at line 1": "`1 Use it as it is · 2 I'll create a Tomo variant`",
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
    "preview place-too-deep names the anchor": "name `place.anchor` and `place.placement`",
    "preview mode replace": "the note already holds Tomo's review section; it is replaced, not added to",
    "review-read check-key-access": "the Kado key may not reach those folders; the user checks its access",
    "drop setup-missing / setup-invalid / inbox-not-configured": "`inbox-not-configured` → as the `refused` line of step 7",
    "preview marker without a heading above (place-missing, mode replace)": "with `mode` `replace` → say what is wrong with the heading above the Tomo marker in the target note: there is none (`place-missing`)",
    "preview place-too-deep, mode replace": "it is too deep to replace under, the review heading would pass level 5 (`place-too-deep`). Ask `1 Start over · 2 Abort`",
    "preview user-heading-collision, mode replace": "it is one of the user's own sections, or an earlier heading of the same name stands above it (`user-heading-collision`)",
    "preview user-heading-collision": "say a heading of the user's with the same name is never replaced",
    "preview user-heading-collision after a heading pick": "the user renames or removes the clashing heading in Obsidian. Ask `1 Start over · 2 Abort`",
    "preview heading-renamed": "the marker was found under a renamed heading; the section is replaced there",
    "preview template variant gone": "the readable instructions say to run Templater after the move",
    "preview template_unmergeable": "a plain note is built instead",
    "preview unlanded-items": "`unlanded` kept items are under a heading the parser does not know and do not land",
    "preview / deliver set-exists": "say an instruction set for this review waits for Hashi and is not applied yet; nothing is delivered",
    "preview / deliver set-withdrawn": "say an earlier Drop emptied the instruction set but did not finish",
    "drop kado-write-failed twice": "say the next `/review` lists this review again and offers Drop",
    "deliver name-taken": "say a note at `exists_path` is not Tomo's and nothing was overwritten",
    "deliver doc-changed": "save it and run `/review` again; the payloads in `paths` already written count as done",
    "deliver doc-changed open-unsaved": "say the document is open in Obsidian with unsaved changes (a plugin that stamps the note on edit can cause that): save it (Cmd+S) or close it, then run `/review` and choose Resume",
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
    assert "Which heading, by number or typed?" in _text(SKILL_WHY)


# ── CLI-contract sweep over every skill that names a review script ──────────


def _all_review_calls() -> list[tuple[str, str, str]]:
    return [(path.parent.name, script, rest) for path in skill_files()
            for script, rest in review_calls(_text(path))]


def test_the_review_skill_calls_every_script_of_the_flow():
    calls = Counter(script for skill, script, _ in _all_review_calls() if skill == "periodic-review")
    assert calls == {"review-session.py": 5, "review-read.py": 1, "review-doc.py": 4, "review-instructions.py": 3,
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

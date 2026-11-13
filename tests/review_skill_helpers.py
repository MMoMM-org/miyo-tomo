#!/usr/bin/env python3
# version: 0.1.0
"""review_skill_helpers.py — the paths, text slicers and rule-line pins shared by the test_review_skill*.py files.

Spec 045 Phase 5 (D8): tests/test_review_skill.py grew past the constitution's ~500 LOC and was split
along its natural seams — Pass 1 and the rules (test_review_skill.py), Pass 2 (test_review_skill_pass2.py),
the SDD rows and the CLI sweep (test_review_skill_contract.py). What every file needs — the runtime paths,
`_text` / `_flat` / `_section`, the rule lines of the skill's `## Rules` list — lives here once. Not named
`test_*`, so pytest does not collect it; never a production code path.
"""
from __future__ import annotations

import re
from pathlib import Path

from review_cli_contract import REPO, SKILLS_DIR

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
VERBATIM_RULE = ("- Show the `error`, `expected`, `example` and `errors` of a script verbatim, and the `hints` of "
                 "step 2 and the `problems` of step 4; never paraphrase them. Every other `problems` entry, "
                 "`warnings` entry and `notices` entry is said by the line its step gives it; without one, verbatim.")
PRIVACY_RULE = ("- Never quote `read.json`, a daily note, a journal answer or a tracker value in your reply; print "
                "the scripts' reports and `section_md` only.")
ACCESS_RULE = ("- Never say a folder is empty or a note does not exist: `kado-none`, `kado_empty` and an empty result "
               "may mean the Kado key cannot read the folder; say so.")
ABORT_RULE = "- On Abort at any question, run no further script and write nothing; say in one line what stays as it is."
EXIT_RULE = "- A non-zero exit: show the output and the stderr line verbatim and stop."


def _rules() -> list[str]:
    return _text(SKILL).split("\n## Rules\n", 1)[1].split("\n## ", 1)[0].splitlines()

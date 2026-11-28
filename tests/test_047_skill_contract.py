#!/usr/bin/env python3
# version: 0.1.5
"""test_047_skill_contract.py — the periodic-review skill's step 4 and step 5 on the stage (spec 047 T6.3; ADR-8,
ADR-10; PRD F3-AC6, F3-AC8, F6-AC1, F6-AC2, F6-AC3, F6-AC4, F6-AC5, F6-AC6, F6-AC8).

What the main session does with the stage is model behaviour; this file proves that each step has its imperative
in tomo/dot_claude/skills/periodic-review/SKILL.md and that the names it uses are the scripts' and agents' own:
- ``allowed-tools`` adds ``Agent``; the write rule and the step 8 STRICT name the agents' files as the only
  exceptions, and the skill writes only ``confirmed-<kind>.json``
- the privacy rule forbids quoting any stage file; no line names ``read_path``, ``read.json`` or ``read*.json``
- step 4: ``--fresh`` on every Start-over route and on ``read-stale``; one line for a continued read with its time;
  the previous-note lines; no setup question for a previous kind
- step 5: ``plan`` once → one message per round → ``check`` → the retries in one message → ``check`` → the proposer
  with ``proposer.inputs`` → ``write`` → one rewrite with ``errors``; ``condense-incomplete`` reruns from ``plan``
  once; ``stopped nothing-condensed`` names every week; the run report repeats the previous-note lines and names
  the not-condensed weeks and a failed carry
- the agent prompt templates carry exactly the fields of each agent's ``## Input`` line, and no note text; the
  optional ``errors`` field is the last line a retry (digester, carryover) or the rewrite (proposer) adds
- the four STRICT blocks of step 5, each one line with a one-line ``Why:``
- the Pass 1 abort runs only ``review-doc.py replace --stem <stem> --abort``
- every ``review-digest.py`` call parses with the script's own argparse parser

Each prose pin (``PINS``) is a phrase on the one line that owns it, matched EXACTLY once in the whole skill and
found in its step; deleting that line fails the row (proven by a sweep outside the repo, see the T6.3 report).

RED before T6.3: step 5 read ``read_path`` and wrote ``proposals.json`` itself, ``allowed-tools`` had no
``Agent``, no step named ``review-digest.py`` or ``--fresh``.
"""
from __future__ import annotations

import re

import pytest

import test_review_digest as trdg
from review_cli_contract import REPO, parse_call
from review_skill_helpers import SKILL, SKILL_WHY, _section, _text

AGENTS_DIR = REPO / "tomo" / "dot_claude" / "agents"
STEP4 = "4. Read the period"
STEP5 = "5. Propose and write the document"
STEP8 = "8. Deliver"
RUN_FIELDS = {"stem", "read_id", "language"}          # the run's values beside a job's own keys


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _count(phrase: str) -> int:
    return len(re.findall(re.escape(phrase), _flat(_text(SKILL))))


# ── frontmatter and version ─────────────────────────────────────────────────


def test_allowed_tools_add_agent():
    head = _text(SKILL).split("\n---\n", 1)[0]
    (tools,) = re.findall(r"^allowed-tools: (.*)$", head, re.MULTILINE)
    assert [t.strip() for t in tools.split(",")] == ["Read", "Write", "Bash", "Agent"]


def test_carries_version_0_3_3():
    assert re.findall(r"^# version: .*$", _text(SKILL), re.MULTILINE) == ["# version: 0.3.3"]


# ── the old read files are gone ─────────────────────────────────────────────


def test_no_line_names_the_old_read_files():
    hits = [(n, line) for n, line in enumerate(_text(SKILL).splitlines(), 1)
            if re.search(r"read_path|read_parts|read\.json|read\*\.json|read-index", line)]
    assert not hits, hits


# ── prose pins: one rule each, its own line, exactly once ───────────────────

WRITE_RULE = ("Write only `tomo-tmp/review/confirmed-<kind>.json` yourself; the review agents of step 5 write their "
              "own files (the digests, `carryover.json`, `proposals.json`), and every other change goes through the "
              "scripts below.")
STRICT_8 = ("# STRICT — never write the review document, the instruction set, the new note or a file under "
            "`tomo-tmp/` other than `tomo-tmp/review/confirmed-<kind>.json` yourself, not through Kado and not with "
            "Write; only the review scripts write them, and the review agents their own files (the digests, "
            "`carryover.json`, `proposals.json`). Why: a hand-written document mark and a hand-edited `meta.json` "
            "make the next deliver or drop act on a delivery that never happened.")
STRICT_BATCH = ("# STRICT — send every `Agent()` call of a round in ONE message. Why: one call per message runs the "
                "agents one after another, a quarter's digesters sixteen times as long.")
STRICT_TYPE = ("# STRICT — every `Agent()` call names `subagent_type` with the job's `agent`. Why: a call without it "
               "starts a general-purpose agent with every tool and none of the review agent's rules.")
STRICT_FG = ("# STRICT — every `Agent()` call passes `run_in_background: false`. Why: a backgrounded agent answers "
             "after the run went on, before its file exists.")
STRICT_STAGE = ("# STRICT — never read a stage file or search the day files with `grep` or Bash in this session, and "
                "never start an agent `plan` did not list; a unit without a passed digest is named as not condensed. "
                "Why: a grep fallback and self-started helpers reviewed a sample of the period while claiming the "
                "whole.")
STEP5_STRICTS = (STRICT_BATCH, STRICT_TYPE, STRICT_FG, STRICT_STAGE)
STRICT_READ = ("# STRICT — before any command of step 5 runs, show the continue line or the printed `report` to the "
               "user as text in your reply. Why: the read result was summarised only in thinking, and the run went on "
               "to `plan` with nothing shown.")

PINS = [
    ("Periodic Review", "write-rule", WRITE_RULE),
    ("Rules", "privacy-stage-files",
     "- Never quote a stage file (a file under `tomo-tmp/review/<stem>/`), a daily note, a journal answer or a "
     "tracker value in your reply;"),
    ("Rules", "abort-except-pass1",
     "- On Abort at any question, run no further script and write nothing, except the Pass 1 Abort below;"),
    ("Rules", "pass1-abort",
     "- When the user writes that they want to abort or stop after step 4 read the period and before step 5 wrote the "
     "document, that is the Pass 1 Abort: run `python3 scripts/review-doc.py replace --stem <stem> --abort` and nothing "
     "else, and say in one line that the read is discarded and no document was written."),
    (STEP4, "fresh",
     "Add `--fresh` to the call when this step follows a Start over answer or a `read-stale` refusal of step 5."),
    (STEP4, "continued",
     "- `ok` with `continued` true → say in one line that the review continues on the read made at `read_at` and "
     "reads nothing anew; then go on with the next bullet."),
    (STEP4, "previous-lines",
     "Print one line per entry of `report.previous`: its `kind` and `name`, its `state`, its `cause` when set, and "
     "read in part when `partly_read` is true."),
    (STEP4, "previous-not-set-up",
     "A `not-set-up` entry is such a line too; ask no setup question for it."),
    (STEP5, "language", "`<language>` is the value of `review.language` in `config/vault-config.yaml`; Read it."),
    (STEP5, "plan-once", "Run `plan` once after each run of step 4; the only other `plan` is the `condense-incomplete` "
     "line below."),
    (STEP5, "read-stale",
     "- `refused` with `read-stale` → run step 4 with `--fresh`, once per run, counted over `plan`, `check` and `write` "
     "together, and continue there; a second `read-stale` → show it and stop."),
    (STEP5, "stage-missing",
     "- `refused` with `stage-missing` or `stage-invalid` → run step 4 again, once, and continue there; a second "
     "refusal → show `problems` verbatim and stop."),
    (STEP5, "rounds",
     "- `ok` → `<read_id>` is its `read_id`. Send each entry of `rounds`, in order, as one message that holds one "
     "`Agent()` call per job, built by the template of the job's `agent` below. After the last round run `check`."),
    (STEP5, "empty-rounds", "`rounds` empty → run no agent and go to the proposer with this output's `proposer`."),
    (STEP5, "template-values",
     "Each `<key>` is the job's value of that key, written as JSON; `<stem>`, `<read_id>` and `<language>` are this "
     "run's."),
    (STEP5, "no-note-text", "Put nothing else in a prompt: no note text, no part of the report."),
    (STEP5, "nothing-condensed",
     "- `stopped` with `nothing-condensed` → say that no week of the period could be condensed and name every entry "
     "of `not_condensed` with its `unit` and `days`; stop as for a period with no content: no document is written."),
    (STEP5, "retry",
     "- `ok` with a non-empty `retry` from the first `check` → send the job of each entry again, the job of `plan`'s "
     "`rounds` with the same `agent`, and the same `unit` when the entry has one, by its template with the line "
     "`errors: <errors>` added last, `<errors>` the entry's `errors` verbatim as JSON, all in one message; then run "
     "`check` once more and branch on it by this list."),
    (STEP5, "second-retry",
     "- `ok` with a non-empty `retry` from the second `check` → send no agent; those units are not condensed. Go on "
     "with the next bullet."),
    (STEP5, "check-twice", "Run `check` at most twice after each `plan`."),
    (STEP5, "proposer",
     "- `ok` with an empty `retry`, or after the second `check` → dispatch `review-proposer` once with the `proposer` "
     "of this output."),
    (STEP5, "proposer-reply", "A reply other than `<out> written` → show it and stop; the read stays for the next "
     "`/review`."),
    (STEP5, "rewrite",
     "- `refused` with `proposals-invalid` → show `errors` verbatim, dispatch `review-proposer` once more by its "
     "template with the line `errors: <errors>` added last, `<errors>` the `errors` of `write` verbatim as JSON, and "
     "rerun `write`; a second `proposals-invalid` → show it and stop; no document is written."),
    (STEP5, "condense-incomplete",
     "- `refused` with `condense-incomplete` → run this step again from `plan`, once: a new `plan` with its own "
     "rounds and at most two `check` calls; a second `condense-incomplete` → show it and stop."),
    (STEP5, "write-read-stale", "- `refused` with `read-stale` → the `read-stale` line of `plan` above."),
    (STEP5, "report-previous",
     "Then one line per entry of `previous`: its `kind`, `name` and `state` as step 4 said them, and that its items "
     "could not be carried when `carry_failed` is set on it."),
    (STEP5, "report-not-condensed",
     "One line per entry of `not_condensed`: the week `unit` and its `days` could not be condensed and are missing "
     "from the review."),
    (STEP5, "report-carry-failed",
     "When `carry_failed` is true, one line that the previous reviews could not be taken into account."),
    (STEP5, "report-carried-moved",
     "One line per entry of `carried_moved`: `count` carried items of the section `<section heading>` of its `key` "
     "moved to the group `to`."),
    (STEP4, "strict-read", STRICT_READ),
    (STEP8, "strict-8", STRICT_8),
] + [(STEP5, f"strict-{n}", s) for n, s in enumerate(STEP5_STRICTS, 1)]


def _owning_section(name: str) -> str:
    if name == "Periodic Review":
        return _flat(_text(SKILL).split("\n## Rules\n", 1)[0])
    return _section(name)


@pytest.mark.parametrize("step,label,phrase", PINS, ids=[lab for _s, lab, _p in PINS])
def test_pin(step, label, phrase):
    found = _count(phrase)
    assert found == 1, f"{label} must match exactly once, matched {found}"
    assert phrase in _owning_section(step), f"{label} is not in {step}"


def test_pin_labels_are_unique():
    labels = [lab for _s, lab, _p in PINS]
    assert len(labels) == len(set(labels))


# ── step 4 ──────────────────────────────────────────────────────────────────


def test_every_start_over_route_reaches_step_4():
    text = _flat(_text(SKILL))
    routes = re.findall(r"Start over → ([^,.;]*)", text)
    assert routes, "no Start over route"
    assert all(r.startswith("step 4") for r in routes), routes


def test_continued_read_line():
    """F6-AC4: on `continued: true` one line names the time of the stored read, before the report."""
    text = _section(STEP4)
    line = text.index("- `ok` with `continued` true →")
    assert "`read_at`" in text[line:text.index("- `ok` otherwise →")]
    assert text.index("- `ok` with `nothing_to_review` true →") < line < text.index("- `ok` otherwise →")


def test_step4_holds_one_strict_after_the_ok_bullets():
    """Walk F-R5-1: the continue line or the report is shown as text before step 5 starts; one STRICT, one `Why:`."""
    text = _section(STEP4)
    assert text.count("# STRICT") == 1 and text.count("Why:") == 1
    assert text.index("- `ok` otherwise →") < text.index(STRICT_READ)


SKILL_WHY_STRICT_READ = (
    "## Why Step 4's STRICT Block (Spec 047 Walk F-R5-1)",
    "In three live runs of the spec 047 walk (R3c, R4, R5) the session showed nothing of the `review-read.py` "
    "result and went straight on to `review-digest.py plan`.",
    "The owner chose a `STRICT` block over a script-rendered line:",
)


@pytest.mark.parametrize("sentence", SKILL_WHY_STRICT_READ, ids=["heading", "failure", "decision"])
def test_why_doc_records_the_step4_strict(sentence):
    found = _flat(_text(SKILL_WHY)).count(sentence)
    assert found == 1, f"periodic-review.md must hold {sentence!r} exactly once, found {found}"


def test_step4_5_ask_no_new_question():
    """F3-AC8: steps 4 and 5 ask no setup question for a previous kind; the only question there is review-exists."""
    text = _section(STEP4) + _section(STEP5)
    assert re.findall(r"`1 [^`]+`", text) == ["`1 Replace · 2 Keep it`"]
    assert "step 2" not in text


# ── step 5 order ────────────────────────────────────────────────────────────


def test_step5_order():
    text = _section(STEP5)
    marks = [
        "python3 scripts/review-digest.py plan --stem <stem>",
        "- `ok` → `<read_id>` is its `read_id`. Send each entry of `rounds`",
        'Agent(subagent_type: "review-digester"',
        "python3 scripts/review-digest.py check --stem <stem>",
        "- `ok` with a non-empty `retry` from the first `check` →",
        "- `ok` with a non-empty `retry` from the second `check` →",
        "- `ok` with an empty `retry`, or after the second `check` → dispatch `review-proposer`",
        'Agent(subagent_type: "review-proposer"',
        "python3 scripts/review-doc.py write --stem <stem> --proposals tomo-tmp/review/<stem>/proposals.json",
        "- `refused` with `proposals-invalid` →",
        "- `written` → report",
    ]
    at = [text.index(m) for m in marks]
    assert at == sorted(at), [m for m, a, b in zip(marks, at, sorted(at)) if a != b]


def test_the_strict_blocks_are_one_line_each_with_one_why():
    lines = [ln for ln in _text(SKILL).splitlines() if ln.startswith("# STRICT")]
    assert lines == [ln for ln in lines if ln.count("Why:") == 1]
    assert sorted(lines) == sorted((*STEP5_STRICTS, STRICT_8, STRICT_READ))


def test_every_review_digest_call_parses_with_its_argparse(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = re.findall(r"python3 scripts/review-digest\.py([^`\n]*)", _text(SKILL))
    assert sorted(c.split()[0] for c in calls) == ["check", "plan"]
    for rest in calls:
        parse_call("review-digest.py", rest.strip())


# ── the agent prompt templates ──────────────────────────────────────────────


def _input_fields(agent: str) -> set:
    (line,) = [ln for ln in (AGENTS_DIR / f"{agent}.md").read_text(encoding="utf-8").splitlines()
               if ln.startswith("The prompt names: ")]
    return set(re.findall(r"`([a-z_]+)`", line))


def _template(agent: str) -> tuple[str, list[tuple[str, str]]]:
    blocks = re.findall(r"```text\n(.*?)\n```", _text(SKILL), re.DOTALL)
    (block,) = [b for b in blocks if b.startswith(f'Agent(subagent_type: "{agent}"')]
    head, *lines = block.splitlines()
    assert lines[-1].endswith(")"), agent
    lines[-1] = lines[-1][:-1]
    return head, [tuple(ln.split(": ", 1)) for ln in lines]


@pytest.mark.parametrize("agent", ["review-digester", "review-carryover", "review-proposer"])
def test_the_template_is_the_agents_input_line(agent):
    head, fields = _template(agent)
    assert "run_in_background: false" in head and head.endswith("prompt:")
    keys = [k for k, _v in fields]
    assert len(keys) == len(set(keys))
    assert set(keys) == _input_fields(agent) - {"errors"}           # `errors` is the retry / rewrite line
    assert all(v == f"<{k}>" for k, v in fields), fields          # a placeholder per key, never text


@pytest.mark.parametrize("agent", ["review-digester", "review-carryover", "review-proposer"])
def test_the_retry_and_the_rewrite_add_the_agents_errors_field(agent):
    """The one optional `## Input` field the templates leave out is the `errors` line of a retry or a rewrite."""
    assert "errors" in _input_fields(agent)
    assert _section(STEP5).count("by its template with the line `errors: <errors>` added last") == 2


def test_the_templates_are_plans_jobs(tmp_path, capsys):
    """The job keys of a real `plan` on the W14 fixture stage fill the templates, the run's fields beside them."""
    plan = trdg._plan(capsys, trdg._w14_stage(tmp_path))
    for job in (j for r in plan["rounds"] for j in r):
        _head, fields = _template(job["agent"])
        assert {k for k, _v in fields} - RUN_FIELDS == set(job) - {"agent"}, job["agent"]
    _head, fields = _template("review-proposer")
    assert {k for k, _v in fields} - RUN_FIELDS == set(plan["proposer"])

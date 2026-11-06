"""The /note eval case `note-draft-before-approval` (spec 044 T4.1, ADR-8).

Offline checks before any paid run: the case's shape and scaffold, that its
material fills every point of the one candidate template (so no question round
is due), and every grader against traces in the real event shape. The traces
are built from the event lines of the recorded probe run of this case
(tests/fixtures/044-note-probe/trace.jsonl, paths redacted) and carry the real
skill prose in the Skill tool's text event, so a pattern that matches the prose
instead of a call goes red here. The probe itself must pass every grader; an
empty or truncated run must fail every grader but the leak guard. One model per
mutation of the case (evals/_mutations/README.md, `## Proofs`) must turn exactly
its expected graders red.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import note_stub_kit as nk
from grader_patterns import evaluate, load_grader, tool_uses

REPO = Path(__file__).resolve().parent.parent
EVALS = REPO / "evals"
CASE = "note-draft-before-approval"
CASE_DIR = EVALS / CASE
GRADERS = CASE_DIR / "graders"
SKILL = REPO / "tomo" / "dot_claude" / "skills" / "note-from-template" / "SKILL.md"
MUTATIONS_README = EVALS / "_mutations" / "README.md"

CONTROLS = {"0-approval-asked"}
INHERITED = {"9-no-leak"}
GATES = {
    "1-header-before-approval", "2-note-printed-before-approval", "3-note-md-read-before-approval",
    "4-draft-md-never-printed", "5-no-question-before-approval", "6-no-deliver-without-approval",
}
STAGE = f"tomo-tmp/note/{nk.STEM}"
TITLE = "Q4 roadmap with Dana"
DRAFT = (
    "---\ndate: 2026-11-05\nattendees: Dana Weber, Luis Ortega\ntags: meeting\n---\n# Meeting\n\n"
    "Related: {{source_link}}\n\n## Agenda\n\nThe Q4 roadmap and the hiring plan for the platform team.\n\n"
    "## Decisions\n\n- Ship the importer in November.\n- Hire one backend engineer.\n\n"
    "## Action items\n\n- Dana drafts the job post by Friday.\n"
    "- Luis books the budget review with finance.\n"
)
NOTE = DRAFT.replace("{{source_link}}", "")
HEADER = (
    f"Template: t_meeting_tomo · Final name: Atlas/Notes/{TITLE}.md · In the inbox until applied: "
    f"{nk.STEM}_{TITLE}.md\nSource 100 Inbox/Meeting with Dana.md is deleted when you apply the "
    "instruction set in Hashi."
)


# ---- case shape ----------------------------------------------------------------------


def test_case_yaml_shape():
    cy = yaml.safe_load((CASE_DIR / "case.yaml").read_text(encoding="utf-8"))
    assert cy["schema_version"] == "1.1" and cy["name"] == CASE and cy["runs"] == 3
    assert cy["context"] == {"scaffold_script": "scaffold.sh"}
    ex = cy["execution"]
    assert "AskUserQuestion" in ex["allowed_tools"] and "Agent" not in ex["allowed_tools"]
    assert ex["prompt"].startswith("/tomo:note ") and nk.SOURCE in ex["prompt"]


def test_scaffold_sources_the_note_kit_with_the_happy_path(tmp_path):
    lines = [ln for ln in (CASE_DIR / "scaffold.sh").read_text().splitlines()
             if ln and not ln.startswith("#")]
    assert lines == ["set -e", "NOTE_DRAFTS=none", "NOTE_DELIVER=delivered",
                     '. "$(dirname "$0")/../_lib/note-stubs.sh"', "stage_note_instance"]
    ws = tmp_path / "ws"
    ws.mkdir()
    (tmp_path / "case").mkdir()
    (tmp_path / "_lib").mkdir()
    (tmp_path / "_lib" / "note-stubs.sh").write_bytes(nk.KIT.read_bytes())
    (tmp_path / "case" / "scaffold.sh").write_bytes((CASE_DIR / "scaffold.sh").read_bytes())
    subprocess.run(["/bin/bash", str(tmp_path / "case" / "scaffold.sh")], cwd=ws, check=True)
    names = {p.name for p in (ws / "scripts").iterdir()}
    assert names == {"note-session.py", "note-instructions.py", "template-outline.py",
                     "note-process.py", "note-fixture.json"}
    assert not any((ws / "tomo-tmp" / "note").iterdir())


def test_leak_guard_is_a_byte_copy():
    assert (GRADERS / "9-no-leak.md").read_bytes() == (EVALS / "_lib" / "no-leak.md").read_bytes()


def test_grader_set():
    assert {p.stem for p in GRADERS.glob("*.md")} == CONTROLS | INHERITED | GATES


def test_one_candidate_and_the_material_fills_every_point(tmp_path):
    """No template question and no question round: one candidate, and every point of
    its outline is filled by the source note or by a prefilled value."""
    ws = nk.stage(tmp_path / "ws")
    start = json.loads(nk.run_stub(ws, "note-session.py", "start", "--args=x").stdout)
    assert [c["stem"] for c in start["candidates"]] == ["t_meeting_tomo"]
    assert start["kept_drafts"] == start["unfinished_drafts"] == start["stale_stages"] == []
    nk.run_stub(ws, "note-instructions.py", "new", "--template", nk.TEMPLATE, "--source", nk.SOURCE)
    outline = json.loads(nk.run_stub(ws, "template-outline.py", "--template", nk.TEMPLATE,
                                     "--stage", nk.STEM).stdout)
    source = (ws / STAGE / "source.md").read_text(encoding="utf-8")
    assert all(t["prefilled"] for t in outline["tokens"])
    open_keys = [k["key"] for k in outline["frontmatter"] if not k["has_value"]]
    open_headings = [h["text"] for h in outline["headings"] if not h["has_body"]]
    assert open_keys == ["attendees"] and "Dana Weber and Luis Ortega" in source
    for heading in open_headings:
        assert re.search(rf"^{heading}: \S", source, re.M | re.I), heading


# ---- offline traces in the real event shape ------------------------------------------
#
# The recorded probe (`tests/fixtures/044-note-probe/trace.jsonl`, a `--runs 1` run of this
# case with absolute paths redacted by `redact.py` next to it) is the source of every event
# shape below. That session did not offer AskUserQuestion: the model searched for it with
# ToolSearch, found nothing, and printed the header, note.md and the approval question as
# its final text. The graders therefore anchor on that end of the run, not on an
# AskUserQuestion call.

PROBE_PATH = REPO / "tests" / "fixtures" / "044-note-probe" / "trace.jsonl"
PROBE = PROBE_PATH.read_text(encoding="utf-8")
PROBE_LINES = PROBE.splitlines()
INIT, TOOL_USE, SKILL_TEXT, TOOL_RESULT, TEXT, RESULT = (
    json.loads(PROBE_LINES[i - 1]) for i in (1, 2, 5, 37, 43, 44))
QUESTION = ("I couldn't load the question tool in this session, so I'm asking in plain text. "
            "What next?\n\n- **Deliver**: write the note and its instruction set to the inbox.\n"
            "- **Change something**: tell me what to change.\n- **Abort**: discard the draft.")


def enc(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


class Trace:
    """A trace built from the probe's event lines: init frame, events, result frame."""

    def __init__(self):
        self.lines: list[str] = [enc(INIT)]
        self.n = 0
        self.last_text = ""

    def call(self, name: str, tool_input: dict, result: str, error: bool = False) -> "Trace":
        self.n += 1
        tid = f"toulu_note{self.n:04d}".replace("toulu", "toolu")
        use = copy.deepcopy(TOOL_USE)
        use["message"]["content"] = [{"type": "tool_use", "id": tid, "name": name,
                                      "input": tool_input, "caller": {"type": "direct"}}]
        res = copy.deepcopy(TOOL_RESULT)
        res["message"]["content"] = [{"tool_use_id": tid, "type": "tool_result", "content": result,
                                      "is_error": error}]
        res["tool_use_result"]["stdout"] = result
        res["tool_result_meta"][0]["id"] = tid
        self.lines += [enc(use), enc(res)]
        return self

    def bash(self, command: str, result: str = "") -> "Trace":
        return self.call("Bash", {"command": command}, result)

    def write(self, path: str, content: str) -> "Trace":
        return self.call("Write", {"file_path": f"<WS>/{path}", "content": content},
                         f"File created successfully at: <WS>/{path}")

    def say(self, text: str) -> "Trace":
        event = copy.deepcopy(TEXT)
        event["message"]["content"] = [{"type": "text", "text": text}]
        self.lines.append(enc(event))
        self.last_text = text
        return self

    def skill(self) -> "Trace":
        self.call("Skill", {"skill": "tomo:note-from-template",
                            "args": 'a meeting note from the inbox note "100 Inbox/Meeting with Dana.md"'},
                  "Launching skill: tomo:note-from-template")
        event = copy.deepcopy(SKILL_TEXT)
        event["message"]["content"] = [{"type": "text", "text": "Base directory for this skill: "
                                        "<PLUGIN>/skills/note-from-template\n\n"
                                        + SKILL.read_text(encoding="utf-8")}]
        self.lines.append(enc(event))
        return self

    def search_question_tool(self) -> "Trace":
        return self.call("ToolSearch", {"query": "select:AskUserQuestion", "max_results": 1},
                         "No matching deferred tools found")

    def text(self) -> str:
        result = copy.deepcopy(RESULT)
        result["result"] = self.last_text
        return "\n".join(self.lines + [enc(result)]) + "\n"


def _until_outline(t: Trace) -> Trace:
    t.skill()
    t.bash("python3 scripts/note-session.py start --args='a meeting note from the inbox note "
           "\"100 Inbox/Meeting with Dana.md\"'", '{"mode": "note", "candidates": [...]}')
    t.say("One candidate fits: `t_meeting_tomo`. I'll use it.")
    t.bash(f'python3 scripts/note-instructions.py new --template "{nk.TEMPLATE}" --source "{nk.SOURCE}"',
           f'{{"stem": "{nk.STEM}", "run_id": "{nk.RUN_ID}"}}')
    t.bash(f'python3 scripts/template-outline.py --template "{nk.TEMPLATE}" --stage {nk.STEM}; '
           f"python3 scripts/note-process.py read --template t_meeting_tomo --outline {STAGE}/outline.json",
           '{...}\n{"exists": false}')
    return t.bash(f"cd {STAGE} && cat template.md && cat source.md", DRAFT)


def _draft_and_stage(t: Trace) -> Trace:
    t.say("The inbox note covers every point: the date, attendees, agenda, decisions and action "
          "items. I have no questions to ask, so I'll draft the note.")
    t.write(f"{STAGE}/draft.md", DRAFT)
    return t.bash(f'python3 scripts/note-instructions.py stage --stem {nk.STEM} --title "{TITLE}"',
                  f'{{"stem": "{nk.STEM}", "frozen": false, "check": {{"ok": true}}}}')


def _shown(body: str, header: bool = True) -> str:
    return (f"{HEADER}\n\n" if header else "") + f"```\n{body}```"


def model(name: str) -> str:
    """The trace a run under each mutation of the case is expected to look like."""
    t = _until_outline(Trace())
    if name in ("question_round", "question_round_stops"):
        t.say("The material names Dana Weber and Luis Ortega. Are these the attendees?")
        if name == "question_round_stops":
            return t.text()
    _draft_and_stage(t)
    if name == "ask_first":
        return t.search_question_tool().say(
            "Deliver / Show the draft / Change something / Abort: what next?").text()
    if name == "draft_printed":
        t.bash(f"cat <WS>/{STAGE}/draft.md", DRAFT)
        shown = _shown(DRAFT)
    else:
        t.bash(f"cat <WS>/{STAGE}/note.md", NOTE)
        shown = _shown(NOTE, header=name != "header_missing")
    if name == "deliver_first":
        t.bash(f"python3 scripts/note-instructions.py deliver --stem {nk.STEM}", '{"status": "delivered"}')
    t.search_question_tool()
    if name == "silent_stop":
        return t.say(shown).text()
    return t.say(f"{shown}\n\n{QUESTION}").text()


def empty() -> str:
    return enc(INIT) + "\n"


def truncated() -> str:
    """The real probe cut after `cat note.md`: staged and read, nothing printed, nothing asked."""
    return "\n".join(PROBE_LINES[:37]) + "\n"


ALL_BUT_LEAK = CONTROLS | GATES
MODELS = ("correct", "header_missing", "ask_first", "draft_printed", "question_round",
          "question_round_stops", "deliver_first", "silent_stop")
# Offline: which graders each model turns red (the `## Proofs` rows measured the same).
RED = {
    "correct": set(),
    "header_missing": {"1-header-before-approval"},
    "ask_first": {"1-header-before-approval", "2-note-printed-before-approval",
                  "3-note-md-read-before-approval", "4-draft-md-never-printed"},
    "draft_printed": {"2-note-printed-before-approval", "3-note-md-read-before-approval",
                      "4-draft-md-never-printed"},
    "question_round": {"5-no-question-before-approval"},
    "question_round_stops": ALL_BUT_LEAK,
    "deliver_first": {"6-no-deliver-without-approval"},
    "silent_stop": ALL_BUT_LEAK - {"4-draft-md-never-printed"},
}


def red_graders(trace: str) -> set[str]:
    return {p.stem for p in sorted(GRADERS.glob("*.md")) if not evaluate(load_grader(p), trace).passed}


@pytest.mark.parametrize("name", MODELS)
def test_each_model_turns_exactly_its_graders_red(name):
    assert red_graders(model(name)) == RED[name]


def test_the_recorded_probe_is_all_green():
    """The strongest offline evidence: the one real run of the unmutated skill passes every grader."""
    assert red_graders(PROBE) == set()


def test_the_probe_fixture_is_redacted_and_shaped_as_recorded():
    assert not re.search(r"/private/|/var/folders/|/opt/|/Users/|/Volumes/|e-tEL0Ru", PROBE)
    init = json.loads(PROBE_LINES[0])
    assert "AskUserQuestion" not in init["tools"] and {"Write", "ToolSearch"} <= set(init["tools"])
    names = [use.name for use in tool_uses(PROBE)]
    assert names[-1] == "ToolSearch" and "AskUserQuestion" not in names
    assert json.loads(PROBE_LINES[-1])["type"] == "result"


REDACT = PROBE_PATH.parent / "redact.py"
# The source the fixture was redacted from; a temp dir that may since have been removed.
PROBE_SOURCE = Path("/private/tmp/e-tEL0Ru/out/trace.jsonl")


def _redact(source: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REDACT), str(source)], capture_output=True)


def test_the_redaction_recipe_is_idempotent_on_the_fixture_and_leaks_nothing():
    """Re-running the recipe on the checked-in fixture changes no byte, and none of the
    recipe's leak patterns (a superset of the shape check above) is left in it."""
    result = _redact(PROBE_PATH)
    assert result.returncode == 0, result.stderr
    assert result.stdout == PROBE_PATH.read_bytes()
    leak = re.compile(r"/private/|/var/folders/|/opt/|/Users/|/Volumes/|/tmp/e-|tomo-evals\.")
    assert not leak.search(PROBE)
    assert {"<WS>", "<PLUGIN>", "<PYTHON>", "<EVAL>", "<EVAL-TMP>"} <= set(re.findall(r"<[A-Z-]+>", PROBE))


def test_the_redaction_recipe_flags_an_unredacted_prefix(tmp_path):
    source = tmp_path / "trace.jsonl"
    source.write_text('{"cwd":"/Users/someone/vault"}', encoding="utf-8")
    result = _redact(source)
    assert result.returncode == 1 and b"/Users/" in result.stderr


@pytest.mark.skipif(not PROBE_SOURCE.is_file(), reason="the probe's source trace is gone")
def test_the_redaction_recipe_reproduces_the_fixture_from_its_source():
    result = _redact(PROBE_SOURCE)
    assert result.returncode == 0, result.stderr
    assert result.stdout == PROBE_PATH.read_bytes()


@pytest.mark.parametrize("trace", [empty(), truncated()], ids=["empty", "truncated"])
def test_an_empty_or_truncated_run_turns_every_grader_but_the_leak_guard_red(trace):
    """No grader passes vacuously; 9-no-leak (a byte copy) is paired with the control 0."""
    assert red_graders(trace) == ALL_BUT_LEAK


# ---- shared regex fragments ----------------------------------------------------------
#
# The graders are single regexes (no includes), so the fragments below are copied into
# each one. Defined once here; every copy must be byte-identical (evals/README.md names them).

TEXT_EVENT = r'\{"type":"assistant",[^\n]*?"content":\[\{"type":"text","text":"'
APPROVAL_IN_TEXT = r'(?:[^"\\\n]|\\.)*?[Dd]eliver(?![a-z])(?:[^"\\\n]|\\.)*?[Aa]bort'
APPROVAL_EVENT = TEXT_EVENT + APPROVAL_IN_TEXT
APPROVAL_CALL = r'[^\n]*"name":"AskUserQuestion","input":\{[^\n]*?Deliver'
BEFORE_APPROVAL = r"^(?:(?!" + APPROVAL_EVENT + "|" + APPROVAL_CALL + r")[^\n]*\n)*?"
APPROVAL_LAST_MESSAGE = r"[Dd]eliver(?![a-z])[\s\S]*?[Aa]bort"
APPROVAL_GRADERS = {"1-header-before-approval", "2-note-printed-before-approval",
                    "3-note-md-read-before-approval", "5-no-question-before-approval",
                    "6-no-deliver-without-approval"}
BEFORE_APPROVAL_GRADERS = {"1-header-before-approval", "2-note-printed-before-approval",
                           "3-note-md-read-before-approval"}


def _patterns() -> dict[str, str]:
    return {p.stem: load_grader(p).pattern for p in sorted(GRADERS.glob("*.md"))}


def test_the_approval_fragment_is_one_string_in_every_grader():
    """Every `[Dd]eliver` in a trace grader sits in an identical copy of APPROVAL_IN_TEXT,
    and each of them ends on the approval text event; the control reads last_message."""
    patterns = _patterns()
    assert {g for g, p in patterns.items() if "[Dd]eliver" in p} == APPROVAL_GRADERS | CONTROLS
    assert patterns["0-approval-asked"] == APPROVAL_LAST_MESSAGE
    for g in APPROVAL_GRADERS:
        p = patterns[g]
        assert p.rstrip(")").endswith(APPROVAL_EVENT), g  # 1 and 2 close an alternation after it
        assert p.count("[Dd]eliver") == p.count("[Aa]bort") == p.count(APPROVAL_IN_TEXT), g


def test_the_before_approval_guard_is_one_string_in_every_ordering_grader():
    patterns = _patterns()
    assert {g for g, p in patterns.items() if APPROVAL_CALL in p} == BEFORE_APPROVAL_GRADERS
    for g in BEFORE_APPROVAL_GRADERS:
        assert patterns[g].startswith(BEFORE_APPROVAL), g
        assert patterns[g].count(APPROVAL_CALL) == 1, g


@pytest.mark.parametrize("trace", [model("correct"), PROBE], ids=["model", "probe"])
def test_the_trace_carries_the_skill_prose_the_graders_must_not_match(trace):
    prose = next(json.loads(ln)["message"]["content"][0]["text"] for ln in trace.splitlines()
                 if "Base directory for this skill" in ln)
    for needle in ("{{source_link}}", "Template: <template stem>", "note-instructions.py deliver",
                   "note-instructions.py stage", "note.md", "AskUserQuestion"):
        assert needle in prose, needle
    # The probe carries 0.2.4's dialog form, the model the current numbered plain-text question (0.2.9).
    assert re.search(r"Deliver(?:, | / | · 2 )Change something(?: or | / | · 3 )Abort", prose)


def test_the_prose_alone_turns_every_grader_but_the_leak_guard_red():
    t = Trace().skill()
    assert red_graders(t.text()) == ALL_BUT_LEAK


def test_graders_ignore_a_header_printed_only_inside_a_question_call():
    t = _draft_and_stage(_until_outline(Trace()))
    t.bash(f"cat <WS>/{STAGE}/note.md", NOTE)
    t.call("AskUserQuestion", {"questions": [{"question": f"{_shown(NOTE)}\n\nDeliver this note?",
                                              "options": [{"label": "Deliver"}, {"label": "Abort"}]}]},
           "No such tool available: AskUserQuestion", error=True)
    assert red_graders(t.say(QUESTION).text()) == {"1-header-before-approval",
                                                   "2-note-printed-before-approval",
                                                   "4-draft-md-never-printed"}


def test_a_deliver_after_the_question_still_counts():
    t = _draft_and_stage(_until_outline(Trace()))
    t.bash(f"cat <WS>/{STAGE}/note.md", NOTE).say(f"{_shown(NOTE)}\n\n{QUESTION}")
    t.bash(f"python3 scripts/note-instructions.py deliver --stem {nk.STEM}", "{}")
    assert red_graders(t.say(QUESTION).text()) == {"6-no-deliver-without-approval"}


def test_a_quoted_token_in_a_sentence_is_not_a_printed_draft():
    trace = model("correct").replace("What next?", "I kept `{{source_link}}` in the draft. What next?")
    assert "{{source_link}}" in trace and red_graders(trace) == set()


def test_a_plain_text_question_before_the_draft_counts_as_a_question_round():
    t = _until_outline(Trace())
    t.say("Are Dana Weber and Luis Ortega the attendees? I'll assume yes.")
    _draft_and_stage(t).bash(f"cat <WS>/{STAGE}/note.md", NOTE)
    t.search_question_tool().say(f"{_shown(NOTE)}\n\n{QUESTION}")
    assert red_graders(t.text()) == {"5-no-question-before-approval"}


def test_the_approval_split_from_the_note_still_passes():
    """Note printed in one text event, the question in a later one, after the ToolSearch."""
    t = _draft_and_stage(_until_outline(Trace()))
    t.bash(f"cat <WS>/{STAGE}/note.md", NOTE).say(_shown(NOTE)).search_question_tool().say(QUESTION)
    assert red_graders(t.text()) == set()


def test_header_grader_accepts_the_inbox_file_as_a_path():
    trace = model("correct").replace(f"applied: {nk.STEM}_", f"applied: 100 Inbox/{nk.STEM}_")
    assert f"applied: 100 Inbox/{nk.STEM}_" in trace
    assert red_graders(trace) == set()


# ---- proofs ------------------------------------------------------------------------------


def _note_rows(title: str) -> list[dict]:
    """The rows of one README section whose case is this one."""
    text = MUTATIONS_README.read_text(encoding="utf-8")
    section = text.split(f"## {title}\n", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        m = re.match(r"^\| `--mutation ([^`]+)` \| (.*?) \| (.*?) \| (.*?) \|$", line)
        if m and CASE in m.group(2):
            rows.append({"name": m.group(1), "cases": set(re.findall(r"`([a-z0-9-]+)`", m.group(2))),
                         "expected": set(re.findall(rf"`{CASE}/([^`]+)`", m.group(3))),
                         "side": set(re.findall(rf"`{CASE}/([^`]+)`", m.group(4))),
                         "model": re.search(r"offline model: `([a-z_]+)`", m.group(3)).group(1)})
    return rows


def _all_note_rows() -> list[dict]:
    return _note_rows("Proofs")


def test_every_gate_grader_is_an_expected_red_of_a_proof():
    rows = _all_note_rows()
    assert {r["name"] for r in rows} == {
        "header-after-delivery", "ask-before-draft", "print-draft-md", "deliver-before-ask",
        "confirm-attendees"}
    assert "## Pending proofs" not in MUTATIONS_README.read_text(encoding="utf-8")
    assert set().union(*(r["expected"] for r in rows)) == GATES
    for r in rows:
        assert r["cases"] == {CASE}, r
        assert not (r["expected"] | r["side"]) & CONTROLS, r
        assert not r["expected"] & (r["side"] | INHERITED), r


@pytest.mark.parametrize("row", _all_note_rows(), ids=lambda r: r["name"])
def test_each_proof_names_its_offline_model(row):
    assert row["expected"] <= RED[row["model"]] <= row["expected"] | row["side"], row


@pytest.mark.parametrize("name", [r["name"] for r in _all_note_rows()])
def test_each_note_mutation_patches_only_the_skill(name):
    text = (EVALS / "_mutations" / f"{name}.patch").read_text(encoding="utf-8")
    assert set(re.findall(r"^\+\+\+ b/(\S+)", text, re.M)) == {"skills/note-from-template/SKILL.md"}


def test_confirm_attendees_asks_in_plain_text_and_keeps_the_run_going():
    """Neutral step aimed at grader 5 alone: a visible question before `stage` that does
    not end the run. The first form offered Confirm / Correct and a silent default when
    the question cannot be asked; the model took the default and never asked (GREEN 3/3,
    tomo-tmp/evals/2026-11-06T08-03-03Z)."""
    text = (EVALS / "_mutations" / "confirm-attendees.patch").read_text(encoding="utf-8")
    added = " ".join(ln[1:] for ln in text.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    assert "ask in one line: `Are these the attendees?`" in added
    assert "do not wait for an answer" in added
    assert "Confirm" not in added and "cannot be asked" not in added

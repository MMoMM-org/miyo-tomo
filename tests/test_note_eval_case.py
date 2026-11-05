"""The /note eval case `note-draft-before-approval` (spec 044 T4.1, ADR-8).

Offline checks before any paid run: the case's shape and scaffold, that its
material fills every point of the one candidate template (so no question round
is due), and every grader against traces in the real event shape. The traces
are built from the recorded spike trace's event lines (spec 043 fixtures) and
carry the real skill prose in the Skill tool's text event, so a pattern that
matches the prose instead of a call goes red here. One model per pending
mutation (evals/_mutations/README.md `## Pending proofs`) must turn exactly
its expected graders red.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

import note_stub_kit as nk
from grader_patterns import FIXTURES_DIR, evaluate, load_grader

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
APPROVAL = {"questions": [{"question": "Deliver this note to the inbox?", "header": "Draft",
                           "multiSelect": False,
                           "options": [{"label": "Deliver", "description": "Write the note and its set"},
                                       {"label": "Change something", "description": "Edit the draft"},
                                       {"label": "Abort", "description": "Discard the draft"}]}]}


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
    assert start["kept_drafts"] == start["stale_stages"] == []
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

SPIKE = (FIXTURES_DIR / "pass1-spike.jsonl").read_text(encoding="utf-8").splitlines()
TOOL_USE, TOOL_RESULT, TEXT, SKILL_TEXT = (json.loads(SPIKE[i]) for i in (0, 1, 6, 9))


def enc(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


class Trace:
    def __init__(self):
        self.lines: list[str] = []
        self.n = 0

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
        self.lines += [enc(use), enc(res)]
        return self

    def bash(self, command: str, result: str = "") -> "Trace":
        return self.call("Bash", {"command": command}, result)

    def read(self, path: str, text: str) -> "Trace":
        numbered = "".join(f"{i}\t{ln}\n" for i, ln in enumerate(text.splitlines(), 1))
        return self.call("Read", {"file_path": f"<WS>/{path}"}, numbered)

    def say(self, text: str) -> "Trace":
        event = copy.deepcopy(TEXT)
        event["message"]["content"] = [{"type": "text", "text": text}]
        self.lines.append(enc(event))
        return self

    def skill(self) -> "Trace":
        self.call("Skill", {"skill": "tomo:note-from-template",
                            "args": 'a meeting note from the inbox note "100 Inbox/Meeting with Dana.md"'},
                  "Launching skill: tomo:note-from-template")
        event = copy.deepcopy(SKILL_TEXT)
        event["message"]["content"] = [{"type": "text", "text": "Base directory for this skill: "
                                        "<WS>/plugin/skills/note-from-template\n\n"
                                        + SKILL.read_text(encoding="utf-8")}]
        self.lines.append(enc(event))
        return self

    def ask(self, tool_input: dict = APPROVAL) -> "Trace":
        return self.call("AskUserQuestion", tool_input, "No answer: the question cannot be shown here.",
                         error=True)

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def _until_stage(t: Trace) -> Trace:
    t.skill()
    t.bash("python3 scripts/note-session.py start --args='a meeting note from the inbox note "
           "\"100 Inbox/Meeting with Dana.md\"'", '{"mode": "note", "candidates": [...]}')
    t.say("One template fits: t_meeting_tomo.")
    t.bash(f'python3 scripts/note-instructions.py new --template "{nk.TEMPLATE}" --source "{nk.SOURCE}"',
           f'{{"stem": "{nk.STEM}", "run_id": "{nk.RUN_ID}"}}')
    t.bash(f'python3 scripts/template-outline.py --template "{nk.TEMPLATE}" --stage {nk.STEM}', "{...}")
    t.bash(f"python3 scripts/note-process.py read --template t_meeting_tomo --outline {STAGE}/outline.json",
           '{"exists": false}')
    t.read(f"{STAGE}/template.md", DRAFT)
    t.say("The material covers every point: attendees, agenda, decisions and action items. "
          "No point is open.")
    t.bash(f"cat > {STAGE}/draft.md <<'EOF'\n{DRAFT}EOF")
    return t


def _stage(t: Trace) -> Trace:
    return t.bash(f'python3 scripts/note-instructions.py stage --stem {nk.STEM} --title "{TITLE}"',
                  f'{{"stem": "{nk.STEM}", "frozen": false, "check": {{"ok": true}}}}')


def _ending(t: Trace) -> Trace:
    return t.say("Deliver, change something, or abort?")


def model(name: str) -> str:
    """The trace a run under each pending mutation is expected to look like."""
    t = _until_stage(Trace())
    if name == "question_round":
        t.say("The material names Dana Weber and Luis Ortega.")
        t.ask({"questions": [{"question": "Are these the attendees?", "header": "Attendees",
                              "multiSelect": False, "options": [{"label": "Confirm"},
                                                                {"label": "Correct"}]}]})
    _stage(t)
    if name == "ask_first":
        approval = copy.deepcopy(APPROVAL)
        approval["questions"][0]["options"].insert(1, {"label": "Show the draft"})
        return _ending(t.ask(approval)).text()
    if name == "draft_printed":
        t.read(f"{STAGE}/draft.md", DRAFT).say(f"{HEADER}\n\n```markdown\n{DRAFT}```")
    else:
        t.read(f"{STAGE}/note.md", NOTE)
        shown = f"```markdown\n{NOTE}```" if name == "header_missing" else f"{HEADER}\n\n```markdown\n{NOTE}```"
        t.say(shown)
    if name == "deliver_first":
        t.bash(f"python3 scripts/note-instructions.py deliver --stem {nk.STEM}", '{"status": "delivered"}')
    if name != "no_question":
        t.ask()
    return _ending(t).text()


MODELS = ("correct", "header_missing", "ask_first", "draft_printed", "question_round",
          "deliver_first", "no_question")
# Offline: which graders each model turns red (the pending table predicts the same).
RED = {
    "correct": set(),
    "header_missing": {"1-header-before-approval"},
    "ask_first": {"1-header-before-approval", "2-note-printed-before-approval",
                  "3-note-md-read-before-approval"},
    "draft_printed": {"2-note-printed-before-approval", "3-note-md-read-before-approval",
                      "4-draft-md-never-printed"},
    "question_round": {"5-no-question-before-approval"},
    "deliver_first": {"6-no-deliver-without-approval"},
    "no_question": {"0-approval-asked", "1-header-before-approval", "2-note-printed-before-approval",
                    "3-note-md-read-before-approval", "5-no-question-before-approval"},
}


def red_graders(trace: str) -> set[str]:
    return {p.stem for p in sorted(GRADERS.glob("*.md")) if not evaluate(load_grader(p), trace).passed}


@pytest.mark.parametrize("name", MODELS)
def test_each_model_turns_exactly_its_graders_red(name):
    assert red_graders(model(name)) == RED[name]


def test_the_trace_carries_the_skill_prose_the_graders_must_not_match():
    trace = model("correct")
    for needle in ("{{source_link}}", "Template: <template stem>", "note-instructions.py deliver",
                   "Deliver / Change something / Abort", "note.md"):
        assert needle in json.loads(trace.splitlines()[2])["message"]["content"][0]["text"], needle


def test_graders_ignore_a_header_printed_only_inside_the_question():
    t = _stage(_until_stage(Trace()))
    t.read(f"{STAGE}/note.md", NOTE)
    question = copy.deepcopy(APPROVAL)
    question["questions"][0]["question"] = f"{HEADER}\n\n{NOTE}\nDeliver this note?"
    assert {"1-header-before-approval", "2-note-printed-before-approval"} <= red_graders(
        _ending(t.ask(question)).text())


def test_a_deliver_after_the_question_still_counts():
    t = Trace()
    _stage(_until_stage(t)).read(f"{STAGE}/note.md", NOTE).say(f"{HEADER}\n\n{NOTE}").ask()
    t.bash(f"python3 scripts/note-instructions.py deliver --stem {nk.STEM}", "{}")
    assert red_graders(_ending(t).text()) == {"6-no-deliver-without-approval"}


# ---- pending proofs ----------------------------------------------------------------------


def _pending_rows() -> list[dict]:
    text = MUTATIONS_README.read_text(encoding="utf-8")
    section = text.split("## Pending proofs\n", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        m = re.match(r"^\| `--mutation ([^`]+)` \| (.*?) \| (.*?) \| (.*?) \|$", line)
        if m:
            rows.append({"name": m.group(1), "cases": set(re.findall(r"`([a-z0-9-]+)`", m.group(2))),
                         "expected": set(re.findall(rf"`{CASE}/([^`]+)`", m.group(3))),
                         "side": set(re.findall(rf"`{CASE}/([^`]+)`", m.group(4))),
                         "model": re.search(r"offline model: `([a-z_]+)`", m.group(3)).group(1)})
    return rows


def test_every_gate_grader_is_an_expected_red_of_a_pending_proof():
    rows = _pending_rows()
    assert {r["name"] for r in rows} == {
        "header-after-delivery", "ask-before-draft", "print-draft-md", "confirm-attendees",
        "deliver-before-ask"}
    assert set().union(*(r["expected"] for r in rows)) == GATES
    for r in rows:
        assert r["cases"] == {CASE}, r
        assert not (r["expected"] | r["side"]) & (CONTROLS | INHERITED), r
        assert not r["expected"] & r["side"], r


@pytest.mark.parametrize("row", _pending_rows(), ids=lambda r: r["name"])
def test_each_pending_proof_names_its_offline_model(row):
    assert row["expected"] <= RED[row["model"]] <= row["expected"] | row["side"], row


@pytest.mark.parametrize("name", [r["name"] for r in _pending_rows()])
def test_each_note_mutation_patches_only_the_skill(name):
    text = (EVALS / "_mutations" / f"{name}.patch").read_text(encoding="utf-8")
    assert set(re.findall(r"^\+\+\+ b/(\S+)", text, re.M)) == {"skills/note-from-template/SKILL.md"}


def test_header_grader_accepts_the_inbox_file_as_a_path():
    trace = model("correct").replace(f"applied: {nk.STEM}_", f"applied: 100 Inbox/{nk.STEM}_")
    assert f"applied: 100 Inbox/{nk.STEM}_" in trace
    assert red_graders(trace) == set()

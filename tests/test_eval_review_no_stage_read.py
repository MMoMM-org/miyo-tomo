"""The /review eval case `review-no-stage-read` (spec 047 T6.4; SDD ADR-8, Quality Requirements).

Offline checks before any paid run (the paid run is the owner's go, spec 047 T9.1):

- the case's shape, its NOT_GATED and ALLOW_TOOLS markers and the stub kit
  (`evals/_lib/review-stubs.sh`);
- the staged stage is the one `lib/review_stage.render` writes for a small synthetic
  month read (no real note text), and the `review-digest.py` stubs print what the
  real script prints on that stage (`plan` on the fresh stage, `check` after valid
  digests and a valid carryover);
- every grader against synthetic traces built from the recorded 043 spike events
  (`docs/XDD/specs/043-pass1-conductor-eval-gate/fixtures/`), with the real skill
  prose in the trace, so a pattern that matches the prose instead of a call goes red
  here; one model per deviation turns exactly its graders red;
- the two mutations of the case (`evals/_mutations/README.md`, `## Proofs not yet
  run`) inject the behaviour their offline model shows.

Regenerate the staged stage after a change to `lib/review_stage.py`:
    ./venv/bin/python tests/test_eval_review_no_stage_read.py --write-stage
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from grader_patterns import evaluate, load_grader

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tomo" / "scripts"))

from lib import review_stage as rs  # noqa: E402
from lib.period import ISO, Period  # noqa: E402
from lib.review_stage_codec import compact  # noqa: E402

EVALS = REPO / "evals"
CASE = "review-no-stage-read"
CASE_DIR = EVALS / CASE
GRADERS = CASE_DIR / "graders"
KIT = EVALS / "_lib" / "review-stubs.sh"
STAGE_JSON = EVALS / "_lib" / "review-stage.json"
SKILL = REPO / "tomo" / "dot_claude" / "skills" / "periodic-review" / "SKILL.md"
DIGEST_SCRIPT = REPO / "tomo" / "scripts" / "review-digest.py"
MUTATIONS = EVALS / "_mutations"
MUTATIONS_README = MUTATIONS / "README.md"
FIXTURES = REPO / "docs" / "XDD" / "specs" / "043-pass1-conductor-eval-gate" / "fixtures"

STEM = "2026-03_review"
STAGE = f"tomo-tmp/review/{STEM}"
READ_ID = "2026-11-24T09-00-00Z-a1b2c3"
READ_AT = "2026-11-24T09:00:00Z"
DAILY = "Calendar/Daily/{}.md"
PREVIOUS_MONTH = "Calendar/Monthly/2026-02.md"
# Synthetic day text: three days with content, one created note, one found previous month.
DAY_TEXT = {
    "2026-03-03": "Descaled the kettle; the filter still needs ordering.",
    "2026-03-04": "Ordered the kettle filter.",
    "2026-03-10": "Wrote a note on kettle care.",
}
UNITS = ("2026-W10", "2026-W11")

CONTROLS = {"0-proposer-handed-back"}
INHERITED = {"9-no-leak"}
GATES = {
    "1-no-stage-read-in-main", "2-proposer-reads-no-raw-stage", "3-agent-calls-typed",
    "4-agent-calls-foreground", "5-round-in-one-message", "6-no-agent-outside-plan",
    "7-agent-replies-one-line",
}


# ---- the synthetic read and its stage ------------------------------------------------


def _day(d: str) -> dict:
    content = d in DAY_TEXT
    return {"date": d, "dailies": [DAILY.format(d)] if content else [],
            "sections": {"Daily Log": DAY_TEXT[d]} if content else {}, "fields": {}, "partly_read": False,
            "has_content": content, "links": [], "problems": [], "tasks": [], "linked": []}


REPORT_DAYS = [{"date": d, "dailies": [{"path": DAILY.format(d), "state": "found"}], "duplicate": False,
                "linked": []} for d in DAY_TEXT]


def synthetic_read() -> dict:
    period = Period.month(2026, 3)
    return {
        "period": {"kind": "month", "name": "2026-03", "start": "2026-03-01", "end": "2026-03-31"},
        "days": [_day(d.isoformat()) for d in period.days()],
        "open_tasks": [], "report": {"days": REPORT_DAYS}, "not_read": [],
        "previous": [
            {"kind": "month", "name": "2026-02", "role": "previous-month", "path": PREVIOUS_MONTH,
             "state": "found", "partly_read": False, "sections": {"Next month": "- Order a kettle filter."}},
            {"kind": "quarter", "name": "2025-Q4", "role": "previous-quarter", "path": None,
             "state": "missing", "partly_read": False},
        ],
        "growth": {"created": [{"path": "Notes/Kettle care.md", "links": [], "day": "2026-03-10"}],
                   "mocs_changed": [], "mocs_linked_by_new": []},
    }


def render_stage() -> dict[str, str]:
    """{stage-relative name: text}, exactly as `review_stage.write` writes the synthetic read."""
    written, doc = rs.render(synthetic_read(), stem=STEM, rule=ISO, sections_digest="none",
                             read_id=READ_ID, read_at=READ_AT)
    return {**written, rs.MANIFEST: compact(doc)}


def test_the_staged_stage_is_what_review_stage_renders():
    assert json.loads(STAGE_JSON.read_text(encoding="utf-8")) == render_stage()


def test_the_stage_is_small_and_synthetic():
    stage = json.loads(STAGE_JSON.read_text(encoding="utf-8"))
    assert sum(len(t) for t in stage.values()) < 16_384
    text = "\n".join(stage.values())
    assert not re.search(r"/Users/|/Volumes/|/private/|SECRET", text)


# ---- case shape and kit ---------------------------------------------------------------


def test_case_yaml_shape():
    cy = yaml.safe_load((CASE_DIR / "case.yaml").read_text(encoding="utf-8"))
    assert cy["schema_version"] == "1.1" and cy["name"] == CASE and cy["runs"] == 3
    assert cy["context"] == {"scaffold_script": "scaffold.sh"}
    ex = cy["execution"]
    assert {"Agent", "Bash", "Read", "Skill", "Write"} <= set(ex["allowed_tools"])
    assert "AskUserQuestion" not in ex["allowed_tools"]
    assert ex["prompt"] == "/tomo:review 2026-03"


def test_case_is_not_gated_and_grants_write_only():
    assert (CASE_DIR / "NOT_GATED").is_file()
    assert (CASE_DIR / "ALLOW_TOOLS").read_text(encoding="utf-8").split() == ["Write"]


def test_leak_guard_is_a_byte_copy():
    assert (GRADERS / "9-no-leak.md").read_bytes() == (EVALS / "_lib" / "no-leak.md").read_bytes()


def test_grader_set():
    assert {p.stem for p in GRADERS.glob("*.md")} == CONTROLS | INHERITED | GATES


def test_scaffold_sources_the_review_kit():
    lines = [ln for ln in (CASE_DIR / "scaffold.sh").read_text().splitlines() if ln and not ln.startswith("#")]
    assert lines == ["set -e", '. "$(dirname "$0")/../_lib/review-stubs.sh"', "stage_review_instance"]


def _scaffold(tmp_path: Path) -> Path:
    tree = tmp_path / "plugin" / "evals"
    shutil.copytree(EVALS / "_lib", tree / "_lib")
    shutil.copytree(CASE_DIR, tree / CASE)
    ws = tmp_path / "ws"
    ws.mkdir()
    subprocess.run(["/bin/bash", str(tree / CASE / "scaffold.sh")], cwd=ws, check=True,
                   capture_output=True, text=True)
    return ws


def _stub(ws: Path, name: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", f"scripts/{name}", *argv], cwd=ws, capture_output=True, text=True)


def test_scaffold_stages_the_stubs_the_config_and_the_stage(tmp_path):
    ws = _scaffold(tmp_path)
    assert {p.name for p in (ws / "scripts").iterdir()} == {
        "review-session.py", "review-read.py", "review-digest.py", "review-doc.py"}
    config = yaml.safe_load((ws / "config" / "vault-config.yaml").read_text(encoding="utf-8"))
    assert config["review"]["language"] == "en"
    staged = {str(p.relative_to(ws / STAGE)): p.read_text(encoding="utf-8")
              for p in (ws / STAGE).rglob("*") if p.is_file()}
    assert staged == render_stage()


def _out(proc: subprocess.CompletedProcess) -> dict:
    assert proc.returncode == 0 and proc.stderr == "", proc.stderr
    assert proc.stdout.isascii() and proc.stdout.count("\n") == 1
    return json.loads(proc.stdout)


def _real_digest(ws: Path, command: str) -> dict:
    proc = subprocess.run([sys.executable, str(DIGEST_SCRIPT), command, "--stem", STEM, "--tmp",
                           str(ws / "tomo-tmp" / "review")], capture_output=True, text=True)
    return _out(proc)


def test_start_and_read_stubs_lead_straight_to_step_5(tmp_path):
    """No question round: setup present, no open review, a new read with continued false."""
    ws = _scaffold(tmp_path)
    start = _out(_stub(ws, "review-session.py", "start", "--args=2026-03"))
    assert start["status"] == "ok" and start["open_reviews"] == [] and start["skipped_review_docs"] == []
    assert start["request"]["kind"] == "month" and start["request"]["period"] == "2026-03"
    assert start["setup"]["month"] == "present" and not start["request"]["year_inferred"]
    read = _out(_stub(ws, "review-read.py", "--period", "2026-03", "--kind", "month", "--stem", STEM))
    assert read["status"] == "ok" and read["continued"] is False and read["nothing_to_review"] is False
    assert read["read_id"] == READ_ID and read["stage"] == STAGE
    assert read["report"]["days"] == REPORT_DAYS and read["report"]["not_read"] == []
    assert [p["state"] for p in read["report"]["previous"]] == ["found", "missing"]


def test_plan_stub_prints_what_the_real_plan_prints_on_the_stage(tmp_path):
    ws = _scaffold(tmp_path)
    stub = _out(_stub(ws, "review-digest.py", "plan", "--stem", STEM))
    real = _real_digest(ws, "plan")
    assert stub == real
    (jobs,) = real["rounds"]
    assert [j["agent"] for j in jobs] == ["review-digester", "review-digester", "review-carryover"]
    assert [j.get("unit") for j in jobs[:2]] == list(UNITS)


def _valid_agent_files(ws: Path) -> None:
    stage = ws / STAGE
    (stage / "digests").mkdir(exist_ok=True)

    def digest(unit: str, days: list[str]) -> dict:
        return {"read_id": READ_ID, "unit": unit, "days": days, "done": [], "open": [], "notable": [],
                "themes": [], "sections": [], "child_notes": [], "growth": []}

    w10 = digest("2026-W10", ["2026-03-03", "2026-03-04"])
    w10["done"] = [{"text": "Kettle descaled", "sources": [DAILY.format("2026-03-03")]}]
    w11 = digest("2026-W11", ["2026-03-10"])
    w11["growth"] = [{"text": "Kettle care", "sources": [DAILY.format("2026-03-10")],
                      "notes": ["Notes/Kettle care.md"]}]
    (stage / "digests" / "2026-W10.json").write_text(json.dumps(w10), encoding="utf-8")
    (stage / "digests" / "2026-W11.json").write_text(json.dumps(w11), encoding="utf-8")
    (stage / "carryover.json").write_text(json.dumps({
        "read_id": READ_ID, "notes": [{"path": PREVIOUS_MONTH, "kind": "month", "name": "2026-02", "items": 1}],
        "items": [{"id": "c1", "type": "intention", "text": "Order a kettle filter", "sources": ["2026-02"]}],
    }), encoding="utf-8")


def test_check_stub_prints_what_the_real_check_prints_after_valid_agent_files(tmp_path):
    ws = _scaffold(tmp_path)
    stub = _out(_stub(ws, "review-digest.py", "check", "--stem", STEM))
    _real_digest(ws, "plan")
    _valid_agent_files(ws)
    real = _real_digest(ws, "check")
    assert stub == real
    assert real["retry"] == [] and real["ready"] is True
    assert real["proposer"]["inputs"] == ["context.json", "digests/2026-W10.json", "digests/2026-W11.json",
                                          "carryover.json"]


def test_write_stub_reports_a_written_document(tmp_path):
    ws = _scaffold(tmp_path)
    out = _out(_stub(ws, "review-doc.py", "write", "--stem", STEM, "--proposals", f"{STAGE}/proposals.json"))
    assert out["status"] == "written" and out["stem"] == STEM
    assert set(out) >= {"doc_path", "target", "target_exists", "counts", "rejected", "previous", "calls"}
    assert "tomo-tmp" not in json.dumps(out)


@pytest.mark.parametrize("argv", [
    ("review-session.py", "match", "--kind", "month"),
    ("review-read.py", "--period", "2026-04", "--kind", "month", "--stem", "2026-04_review"),
    ("review-digest.py", "plan", "--stem", "2026-04_review"),
    ("review-doc.py", "parse", "--stem", STEM),
])
def test_stubs_refuse_any_other_call(tmp_path, argv):
    proc = _stub(_scaffold(tmp_path), *argv)
    assert proc.returncode == 2 and proc.stdout == "" and "unexpected call" in proc.stderr


# ---- synthetic traces in the recorded event shape --------------------------------------
#
# Event templates from the 043 spike fixtures: a main-session Agent call (pass2 line 1), a
# foreground subagent tool call and result (pass2 lines 5, 6; they carry `subagent_type`),
# the hand-back frame (pass2 line 27), the final text and result frame (lines 28, 29), a
# main-session tool result (pass1 line 2) and the skill prose event (pass1 line 10).

PASS1 = (FIXTURES / "pass1-spike.jsonl").read_text(encoding="utf-8").splitlines()
PASS2 = (FIXTURES / "pass2-spike.jsonl").read_text(encoding="utf-8").splitlines()
MAIN_USE, SUB_USE, SUB_RESULT, HANDBACK, TEXT, RESULT = (json.loads(PASS2[i - 1]) for i in (1, 5, 6, 27, 28, 29))
MAIN_RESULT, PROSE = json.loads(PASS1[1]), json.loads(PASS1[9])
FRAME_HEAD = HANDBACK["message"]["content"][0]["content"][0]["text"].split("The report follows:\n", 1)[0] + "The report follows:\n"


def enc(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


def job_prompt(job: dict, errors: list | None = None) -> str:
    """The skill's step 5 template for a job: `<key>: <JSON value>` lines, the run's keys first."""
    keys = (["stem", "unit", "read_id", "days", "day_files", "growth_files", "weekly_note", "sections",
             "section_files", "out", "cap_bytes", "language"] if job["agent"] == "review-digester"
            else ["stem", "read_id", "previous_files", "out", "cap_bytes", "language"])
    values = {**job, "stem": STEM, "read_id": READ_ID, "language": "en"}
    lines = [f"{k}: {json.dumps(values[k])}" if k not in ("stem", "read_id", "language") else f"{k}: {values[k]}"
             for k in keys]
    if errors is not None:
        lines.append(f"errors: {json.dumps(errors)}")
    return "\n".join(lines)


class Trace:
    def __init__(self):
        self.lines: list[str] = []
        self.n = 0
        self.m = 0
        self.last_text = ""

    def _id(self, kind: str) -> str:
        self.n += 1
        return f"{kind}_rv{self.n:04d}"

    def new_message(self) -> str:
        self.m += 1
        return f"msg_rvmsg{self.m:04d}"

    def use(self, name: str, tool_input: dict, *, msg: str | None = None, parent: str | None = None,
            agent: str | None = None) -> str:
        tid = self._id("toolu")
        event = copy.deepcopy(SUB_USE if parent else MAIN_USE)
        event["message"]["id"] = msg or self.new_message()
        event["message"]["content"] = [{"type": "tool_use", "id": tid, "name": name, "input": tool_input,
                                        "caller": {"type": "direct"}}]
        if parent:
            event["parent_tool_use_id"] = parent
            event["subagent_type"] = agent
        self.lines.append(enc(event))
        return tid

    def result(self, tid: str, text: str, *, parent: str | None = None, agent: str | None = None,
               error: bool = False) -> "Trace":
        event = copy.deepcopy(SUB_RESULT if parent else MAIN_RESULT)
        event["message"]["content"] = [{"tool_use_id": tid, "type": "tool_result", "content": text,
                                        "is_error": error}]
        if parent:
            event["parent_tool_use_id"] = parent
            event["subagent_type"] = agent
        self.lines.append(enc(event))
        return self

    def call(self, name: str, tool_input: dict, out: str = "") -> "Trace":
        return self.result(self.use(name, tool_input), out)

    def bash(self, command: str, out: str = "") -> "Trace":
        return self.call("Bash", {"command": command, "description": "Run step"}, out)

    def say(self, text: str) -> "Trace":
        event = copy.deepcopy(TEXT)
        event["message"]["content"] = [{"type": "text", "text": text}]
        self.lines.append(enc(event))
        self.last_text = text
        return self

    def handback(self, tid: str, reply: str) -> "Trace":
        body = "\n".join(f"  > {ln}" if ln else "  >" for ln in reply.split("\n"))
        event = copy.deepcopy(HANDBACK)
        event["message"]["content"] = [{"tool_use_id": tid, "type": "tool_result", "content": [
            {"type": "text", "text": f"{FRAME_HEAD}{body}\nagentId: a0000000000000{self.n:03d}\n"
                                     "<usage>subagent_tokens: 1000\ntool_uses: 2\nduration_ms: 900</usage>"}]}]
        event["tool_use_result"]["content"] = [{"type": "text", "text": reply}]
        self.lines.append(enc(event))
        return self

    def skill(self) -> "Trace":
        self.call("Skill", {"skill": "tomo:periodic-review", "args": "2026-03"},
                  "Launching skill: tomo:periodic-review")
        event = copy.deepcopy(PROSE)
        event["message"]["content"] = [{"type": "text", "text": "Base directory for this skill: "
                                        "<PLUGIN>/skills/periodic-review\n\n" + SKILL.read_text(encoding="utf-8")}]
        self.lines.append(enc(event))
        return self

    def text(self) -> str:
        result = copy.deepcopy(RESULT)
        result["result"] = self.last_text
        return "\n".join(self.lines + [enc(result)]) + "\n"


def _jobs() -> list[dict]:
    """The round of the plan stub (equal to the real plan, test above)."""
    kit = KIT.read_text(encoding="utf-8")
    plan = json.loads(re.search(r"^PLAN_OUTPUT='(.*)'$", kit, re.M).group(1))
    (jobs,) = plan["rounds"]
    return jobs


def agent_input(job: dict, *, typed: str | None = "plain", background: bool | None = False,
                errors: list | None = None) -> dict:
    data: dict = {}
    if typed == "plain":
        data["subagent_type"] = job["agent"]
    elif typed == "tomo":
        data["subagent_type"] = f"tomo:{job['agent']}"
    elif typed is not None:
        data["subagent_type"] = typed
    if background is not None:
        data["run_in_background"] = background
    data["description"] = f"Condense {job['unit']}" if job.get("unit") else "Carry the previous reviews"
    data["prompt"] = job_prompt(job, errors)
    return data


def run_agent(t: Trace, tid: str, job: dict, *, agent: str, reads: list[str], reply: str | None = None) -> None:
    for path in reads:
        sub = t.use("Read", {"file_path": f"<WS>/{STAGE}/{path}"}, parent=tid, agent=agent)
        t.result(sub, '{"read_id": "..."}', parent=tid, agent=agent)
    sub = t.use("Write", {"file_path": f"<WS>/{STAGE}/{job['out']}", "content": "{}"}, parent=tid, agent=agent)
    t.result(sub, "File created successfully", parent=tid, agent=agent)
    t.handback(tid, reply if reply is not None else f"{job['out']} written")


def _job_reads(job: dict) -> list[str]:
    if job["agent"] == "review-digester":
        return job["day_files"] + job["growth_files"]
    return job["previous_files"]


PROPOSER = {"agent": "review-proposer", "out": "proposals.json",
            "inputs": ["context.json", "digests/2026-W10.json", "digests/2026-W11.json", "carryover.json"]}


def _until_plan(t: Trace) -> Trace:
    t.skill()
    t.bash("python3 scripts/review-session.py start --args='2026-03'", '{"status": "ok", ...}')
    t.bash(f"python3 scripts/review-read.py --period 2026-03 --kind month --stem {STEM}", '{"status": "ok", ...}')
    t.say("Read 3 days of 2026-03 with content; the previous month 2026-02 was found, 2025-Q4 is missing.")
    t.call("Read", {"file_path": "<WS>/config/vault-config.yaml"}, "review:\n  language: en")
    return t.bash(f"python3 scripts/review-digest.py plan --stem {STEM}", '{"status": "ok", "rounds": [...]}')


def model(name: str) -> str:
    """The trace a run with each deviation is expected to look like."""
    t = _until_plan(Trace())
    if name == "prose_only":
        return Trace().skill().text()
    if name == "read_day_file":
        t.call("Read", {"file_path": f"<WS>/{STAGE}/days/2026-03-03.json"}, '{"date": "2026-03-03"}')
    if name == "grep_stage":
        t.bash(f"grep -l kettle {STAGE}/days/*.json", "days/2026-03-03.json")
    jobs = _jobs()
    typed = "tomo" if name == "namespaced" else "plain"
    if name == "bare_then_namespaced":
        msg = t.new_message()
        for job in jobs:
            t.result(t.use("Agent", agent_input(job), msg=msg), f"Agent type '{job['agent']}' not found.",
                     error=True)
        typed = "tomo"
    msg = t.new_message()
    calls = []
    for i, job in enumerate(jobs):
        background = True if (name == "backgrounded_digester" and i == 0) else False
        this_msg = t.new_message() if (name == "two_messages" and i == 1) else (
            calls[-1][2] if (name == "two_messages" and i == 2) else msg)
        tid = t.use("Agent", agent_input(job, typed=typed, background=background), msg=this_msg)
        calls.append((tid, job, this_msg, background))
    if name == "unplanned_unit":
        extra = dict(jobs[0], unit="2026-W12", out="digests/2026-W12.json", day_files=["days/2026-03-17.json"])
        calls.append((t.use("Agent", agent_input(extra), msg=msg), extra, msg, False))
    if name == "helper_agent":
        helper = {"agent": "general-purpose", "unit": "2026-W12", "out": "digests/2026-W12.json"}
        tid = t.use("Agent", {"subagent_type": "general-purpose", "run_in_background": False,
                              "description": "Summarise the days", "prompt": "Summarise days/ of the stage."}, msg=msg)
        calls.append((tid, helper, msg, False))
    if name == "untyped_call":
        helper = {"agent": None, "out": "notes.txt"}
        tid = t.use("Agent", {"run_in_background": False, "description": "Summarise the days",
                              "prompt": "Summarise the period."}, msg=msg)
        calls.append((tid, helper, msg, False))
    for tid, job, _, background in calls:
        agent = f"tomo:{job['agent']}"
        if background:
            t.result(tid, "Async agent launched successfully.")
            continue
        reply = None
        if name == "multi_line_reply" and job.get("unit") == "2026-W10":
            reply = "digests/2026-W10.json written\nThe week was about the kettle."
        run_agent(t, tid, job, agent=agent, reads=_job_reads(job) if job.get("day_files") or job.get(
            "previous_files") else [], reply=reply)
    if name == "truncated":
        return t.text()
    t.bash(f"python3 scripts/review-digest.py check --stem {STEM}", '{"status": "ok", "retry": []}')
    tid = t.use("Agent", {"subagent_type": f"{'tomo:' if typed == 'tomo' else ''}review-proposer",
                          "run_in_background": False, "description": "Propose the review",
                          "prompt": f"stem: {STEM}\ninputs: {json.dumps(PROPOSER['inputs'])}\nout: proposals.json\n"
                                    "carried: true\nlanguage: en"})
    reads = list(PROPOSER["inputs"])
    if name == "proposer_reads_manifest":
        reads.insert(0, "manifest.json")
    if name == "proposer_reads_day":
        reads.append("days/2026-03-04.json")
    run_agent(t, tid, PROPOSER, agent="tomo:review-proposer", reads=reads)
    t.bash(f"python3 scripts/review-doc.py write --stem {STEM} --proposals {STAGE}/proposals.json",
           '{"status": "written", ...}')
    return t.say("Wrote the review document 100 Inbox/2026-03 Review.md for Calendar/Monthly/2026-03.md.\n"
                 "Edit the document in Obsidian, tick - [x] Approved and run /review again.").text()


ALL_CONTAINS = {"0-proposer-handed-back", "5-round-in-one-message"}
RED = {
    "correct": set(),
    "namespaced": set(),
    "bare_then_namespaced": set(),
    "read_day_file": {"1-no-stage-read-in-main"},
    "grep_stage": {"1-no-stage-read-in-main"},
    "proposer_reads_manifest": {"2-proposer-reads-no-raw-stage"},
    "proposer_reads_day": {"2-proposer-reads-no-raw-stage"},
    "untyped_call": {"3-agent-calls-typed"},
    "backgrounded_digester": {"4-agent-calls-foreground"},
    "two_messages": {"5-round-in-one-message"},
    "unplanned_unit": {"6-no-agent-outside-plan"},
    "helper_agent": {"6-no-agent-outside-plan"},
    "multi_line_reply": {"7-agent-replies-one-line"},
    "truncated": {"0-proposer-handed-back"},
    "prose_only": ALL_CONTAINS,
}


def red_graders(trace: str) -> set[str]:
    return {p.stem for p in sorted(GRADERS.glob("*.md")) if not evaluate(load_grader(p), trace).passed}


@pytest.mark.parametrize("name", list(RED))
def test_each_model_turns_exactly_its_graders_red(name):
    assert red_graders(model(name)) == RED[name]


def test_every_gate_grader_has_a_model_that_turns_it_red_alone():
    alone = {next(iter(r)) for r in RED.values() if len(r) == 1}
    assert GATES <= alone


def test_an_empty_trace_turns_only_the_contains_graders_red():
    """The not_contains gates pass on an empty run; the control 0 pairs them."""
    assert red_graders("") == ALL_CONTAINS


def test_the_trace_carries_the_prose_and_the_prompts_the_graders_must_not_match():
    trace = model("correct")
    for needle in ("tomo-tmp/review/<stem>/", "grep", "run_in_background: false", "review-digester",
                   "days/2026-03-03.json", "never read a stage file"):
        assert needle in trace, needle
    assert red_graders(trace) == set()


def test_main_session_reads_of_other_stage_files_and_config_pass():
    """The task names days/, growth/, children/, previous/ and context*; the config read and the
    `--proposals` path are not stage reads of those."""
    t = _until_plan(Trace())
    t.call("Read", {"file_path": f"<WS>/{STAGE}/proposals.json"}, "{}")
    assert "1-no-stage-read-in-main" not in red_graders(t.text())


@pytest.mark.parametrize("path", ["growth/2026-03-10.json", "children/weekly-2026-W10.json",
                                  "previous/month-2026-02.json", "context.json", "context-1.json"])
def test_every_named_stage_folder_and_context_file_counts_in_main(path):
    t = _until_plan(Trace())
    t.call("Read", {"file_path": f"<WS>/{STAGE}/{path}"}, "{}")
    assert "1-no-stage-read-in-main" in red_graders(t.text())


def test_a_grep_tool_over_the_stage_counts_in_main():
    t = _until_plan(Trace())
    t.call("Grep", {"pattern": "kettle", "path": f"<WS>/{STAGE}"}, "days/2026-03-03.json")
    assert "1-no-stage-read-in-main" in red_graders(t.text())


# ---- shared regex fragments ------------------------------------------------------------
#
# Graders are single regexes; each fragment below is copied into the graders named, byte
# for byte (evals/README.md, limits of this case).

TOOL_USE = r'\{"type":"assistant","message":\{[^\n]*?"content":\[\{"type":"tool_use","id":"[^"]*","name":'
AGENT_USE = TOOL_USE + r'"Agent","input":\{'
MAIN_END = r'[^\n]*?"parent_tool_use_id":null'
FRAGMENTS = {
    TOOL_USE: {"1-no-stage-read-in-main", "2-proposer-reads-no-raw-stage", "3-agent-calls-typed",
               "4-agent-calls-foreground", "6-no-agent-outside-plan"},
    AGENT_USE: {"3-agent-calls-typed", "4-agent-calls-foreground", "6-no-agent-outside-plan"},
    MAIN_END: {"1-no-stage-read-in-main"},
}


def _patterns() -> dict[str, str]:
    return {p.stem: load_grader(p).pattern for p in sorted(GRADERS.glob("*.md"))}


@pytest.mark.parametrize("fragment", list(FRAGMENTS), ids=["tool_use", "agent_use", "main_end"])
def test_fragments_are_one_string_in_their_graders(fragment):
    assert {g for g, p in _patterns().items() if fragment in p} == FRAGMENTS[fragment]


# ---- mutations -----------------------------------------------------------------------------


def _rows() -> list[dict]:
    text = MUTATIONS_README.read_text(encoding="utf-8")
    if "## Proofs not yet run\n" not in text:
        return []
    section = text.split("## Proofs not yet run\n", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        m = re.match(r"^\| `--mutation ([^`]+)` \| (.*?) \| (.*?) \| (.*?) \|$", line)
        if m and CASE in m.group(2):
            rows.append({"name": m.group(1), "cases": set(re.findall(r"`([a-z0-9-]+)`", m.group(2))),
                         "expected": set(re.findall(rf"`{CASE}/([^`]+)`", m.group(3))),
                         "model": re.search(r"offline model: `([a-z_]+)`", m.group(3)).group(1)})
    return rows


REVIEW_MUTATIONS = {"read-day-file": "read_day_file", "dispatch-one-per-message": "two_messages"}


def test_the_case_has_its_two_named_mutations():
    rows = _rows()
    assert {r["name"]: r["model"] for r in rows} == REVIEW_MUTATIONS
    for r in rows:
        assert r["cases"] == {CASE}, r
        assert not r["expected"] & (CONTROLS | INHERITED), r


@pytest.mark.parametrize("row", _rows(), ids=lambda r: r["name"])
def test_each_mutation_row_names_the_graders_its_offline_model_turns_red(row):
    assert row["expected"] == RED[row["model"]], row


def _patched_skill(tmp_path: Path, name: str) -> tuple[str, str]:
    plugin = tmp_path / "plugin"
    shutil.copytree(REPO / "tomo" / "dot_claude" / "skills", plugin / "skills")
    before = (plugin / "skills" / "periodic-review" / "SKILL.md").read_text(encoding="utf-8")
    proc = subprocess.run(["patch", "-p1", "--forward", "-i", str(MUTATIONS / f"{name}.patch")], cwd=plugin,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return before, (plugin / "skills" / "periodic-review" / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", list(REVIEW_MUTATIONS))
def test_each_mutation_patches_only_the_skill(name):
    text = (MUTATIONS / f"{name}.patch").read_text(encoding="utf-8")
    assert set(re.findall(r"^\+\+\+ b/(\S+)", text, re.M)) == {"skills/periodic-review/SKILL.md"}


def test_read_day_file_injects_a_main_session_read_grader_1_sees(tmp_path):
    before, after = _patched_skill(tmp_path, "read-day-file")
    m = re.search(r"Read `(tomo-tmp/review/<stem>/days/[^`]+)`", after)
    assert m and m.group(0) not in before
    path = m.group(1).replace("<stem>", STEM).replace("<date>", "2026-03-03")
    assert "<" not in path, path
    t = _until_plan(Trace())
    t.call("Read", {"file_path": f"<WS>/{path}"}, "{}")
    assert red_graders(t.text()) >= {"1-no-stage-read-in-main"}
    assert "never read a stage file" not in after and "never read a stage file" in before
    # The rest of that STRICT stays: no self-started helper, the not-condensed line.
    assert "never start an agent `plan` did not list" in after


def test_dispatch_one_per_message_sends_each_job_in_its_own_message(tmp_path):
    before, after = _patched_skill(tmp_path, "dispatch-one-per-message")
    assert "ONE message" in before and "ONE message" not in after
    assert "all in one message" in before and "all in one message" not in after
    assert "one `Agent()` call per message" in after
    assert "run_in_background: false" in after and "subagent_type" in after


if __name__ == "__main__" and sys.argv[1:] == ["--write-stage"]:
    STAGE_JSON.write_text(json.dumps(render_stage(), indent=1, ensure_ascii=True, sort_keys=True) + "\n",
                          encoding="utf-8")
    print(f"wrote {STAGE_JSON.relative_to(REPO)}")

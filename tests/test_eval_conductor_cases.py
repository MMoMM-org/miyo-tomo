"""Shape tests for the conductor eval cases (spec 041, part 3 — T2.1; the two
failed-delivery cases, #205).

Every expected notice / audit line is read from what the case's own scaffold
stages (the kit), never retyped here. Shared helpers live in eval_kit.py.
Everything runs in tmp_path; nothing writes into the repo.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from eval_kit import (
    EVALS,
    NO_LEAK,
    REPO,
    bash_input,
    case_yaml,
    grader,
    grader_names,
    js_escape,
    js_unescape,
    kit_lines,
    render,
    run_scaffold,
    run_stub,
)

INBOX_CMD = REPO / "tomo" / "dot_claude" / "commands" / "inbox.md"
CONDUCTOR = REPO / "tomo" / "dot_claude" / "agents" / "synthesis-conductor.md"

CASE_SETTINGS = {
    "audit-gates-delivery": {"AUDIT_RESULT": "ok", "WITHHELD_DELETES": "0", "WITHHELD_ATTACH": "0"},
    "audit-mismatch-stops": {"AUDIT_RESULT": "fail", "WITHHELD_DELETES": "0", "WITHHELD_ATTACH": "0"},
    "withheld-notices-relayed": {"AUDIT_RESULT": "ok", "WITHHELD_DELETES": "2", "WITHHELD_ATTACH": "1"},
    "upload-failure-reported": {
        "AUDIT_RESULT": "ok", "WITHHELD_DELETES": "0", "WITHHELD_ATTACH": "0", "UPLOAD_RESULT": "fail",
    },
    "state-flip-failure-reported": {
        "AUDIT_RESULT": "ok", "WITHHELD_DELETES": "0", "WITHHELD_ATTACH": "0", "FLIP_RESULT": "fail",
    },
}
GATES = "audit-gates-delivery"
MISMATCH = "audit-mismatch-stops"
RELAY = "withheld-notices-relayed"
UPLOAD_FAIL = "upload-failure-reported"
FLIP_FAIL = "state-flip-failure-reported"

# Controls are preconditions, exempt from RED proof (F7-AC5); every other
# grader in a case is a gate.
CONTROL_GRADERS = {
    GATES: {"0-conductor-dispatched"},
    MISMATCH: {"0-conductor-dispatched", "3-audit-ran"},
    RELAY: {"0-conductor-dispatched"},
    UPLOAD_FAIL: {"0-conductor-dispatched", "3-upload-ran"},
    FLIP_FAIL: {"0-conductor-dispatched", "2-state-flip-ran"},
}
# Spec 043 ADR-4: the hand-back canary is a control in every case (it checks the trace
# frame the report-only grader reads is present exactly once; its RED proof is offline,
# tests/test_043_grader_patterns.py).
for _controls_of_case in CONTROL_GRADERS.values():
    _controls_of_case.add("8-handback-canary")

# PRD F3–F6 grader-backed criterion → the gate grader(s) that decide it.
# F5-AC1 ("each delete line exact") and F5-AC2 ("both, each on its own line")
# are decided by the same pair of anchored per-line graders: one grader per
# notice line (plan T2.1), and each of those is both exact and anchored.
# F6-AC1 is the canonical leak guard, once per case. F6-AC2 is the runner's
# preflight + test_case_leak_guard_is_byte_identical, not a grader.
CRITERIA = {
    "F3-AC1": [(GATES, "1-audit-before-upload")],
    "F3-AC2": [(GATES, "2-audit-before-state-flip")],
    "F3-AC3": [(GATES, "3-audit-result-in-report")],
    "F4-AC1": [(MISMATCH, "1-no-upload-after-mismatch")],
    "F4-AC2": [(MISMATCH, "2-no-state-flip-after-mismatch")],
    "F4-AC3": [(MISMATCH, "4-mismatch-reported-verbatim")],
    "F4-AC4": [
        (MISMATCH, "5-no-write-into-scripts-schemas-config"),
        (MISMATCH, "6-no-copy-into-scripts-schemas-config"),
    ],
    "F5-AC1": [(RELAY, "1-delete-1-verbatim"), (RELAY, "2-delete-2-verbatim")],
    "F5-AC2": [(RELAY, "1-delete-1-verbatim"), (RELAY, "2-delete-2-verbatim")],
    "F5-AC3": [(RELAY, "3-attachment-verbatim")],
    "F5-AC4": [(RELAY, "4-deletes-then-attachment-last")],
    "F5-AC5": [(GATES, "4-no-notice-when-none-withheld")],
    "F6-AC1": [(c, "9-no-leak") for c in CASE_SETTINGS],
}

# Issue #205 (owner decisions): a failed upload or state flip reaches the
# report only as the failed-step line; no state flip after a failed upload.
ISSUE_205 = {
    "failed-step-line": [
        (UPLOAD_FAIL, "1-upload-failure-line-in-report"),
        (FLIP_FAIL, "1-state-flip-failure-line-in-report"),
    ],
    "no-flip-after-failed-upload": [(UPLOAD_FAIL, "2-no-state-flip-after-failed-upload")],
    "audit-line-still-reported": [
        (UPLOAD_FAIL, "4-audit-result-in-report"),
        (FLIP_FAIL, "3-audit-result-in-report"),
    ],
    "no-failure-detail": [
        (UPLOAD_FAIL, "5-no-failure-detail-in-report"),
        (FLIP_FAIL, "4-no-failure-detail-in-report"),
    ],
}

# Spec 043 PRD F4: the reply is only the report, in every Pass 2 case.
SPEC_043_REPORT_ONLY = {
    "report-only": [
        (c, "7-report-only-mismatch" if c == MISMATCH else "7-report-only")
        for c in CASE_SETTINGS
    ],
}
# Spec 043's Pass 1 cases; their shape is tested in test_run_evals.py.
PASS1_CASES = {"pass1-suggest-pipeline", "pass1-warn-and-duplicates-relayed"}
PIPELINE = "pass1-suggest-pipeline"
SKILL_IN_PLUGIN = "skills/suggest-handling/SKILL.md"
SPEC_043_FIXTURES = REPO / "docs" / "XDD" / "specs" / "043-pass1-conductor-eval-gate" / "fixtures"
PASS1_INBOX_PATH = "100 Inbox"  # the pass1 kit's routing plan `inbox_path`, trailing slash removed

# Every Pass 1 grader is a gate (none only confirms a precondition: the main session
# runs Pass 1 itself, so there is no dispatch to confirm). The leak guard is the
# exception to "has its own mutation": it is a byte copy of evals/_lib/no-leak.md and
# inherits that file's recorded RED proof (README "Inherited proofs").
INHERITED_LEAK_GUARD = {(c, "9-no-leak") for c in PASS1_CASES}

# Gates whose named mutation is not run yet (spec 043; Phase 4 records the runs and
# moves the rows into `## Proofs`). Each entry must have a pending row and no
# recorded one, so this set expires with the recording: Phase 4 empties it.
AWAITING_RECORDING = {pair for pairs in SPEC_043_REPORT_ONLY.values() for pair in pairs} | {
    (case, g)
    for case in PASS1_CASES
    for g in {p.stem for p in (EVALS / case / "graders").glob("*.md")}
    if (case, g) not in INHERITED_LEAK_GUARD
}

LINE_START, LINE_END = "(?:^|\\n)", "(?:\\n|$)"
CASE_YAML_KEYS = {"schema_version", "name", "runs", "context", "execution"}
EXECUTION_KEYS = {"max_turns", "timeout_seconds", "allowed_tools", "prompt"}


def production_dispatch() -> tuple[str, str]:
    text = INBOX_CMD.read_text(encoding="utf-8")
    block = re.search(r"### 3b\. Synthesize \(dispatch\).*?```\n(Agent\(.*?\))\n```", text, re.S)
    assert block, "inbox.md: 3b dispatch block not found"
    agent = re.search(r'subagent_type: "([^"]+)"', block.group(1)).group(1)
    prompt = re.search(r'prompt: "([^"]+)"', block.group(1)).group(1)
    return agent, prompt


def test_exactly_the_known_cases_exist():
    assert {p.name for p in EVALS.iterdir() if p.is_dir() and not p.name.startswith("_")} == set(
        CASE_SETTINGS
    ) | PASS1_CASES


def test_every_non_underscore_evals_subdir_is_a_case():
    # The runner skips `_*` and `results`; anything else without case.yaml would
    # be silently skipped and escape the leak-guard identity check.
    for d in EVALS.iterdir():
        if d.is_dir() and not d.name.startswith("_") and d.name != "results":
            assert (d / "case.yaml").is_file(), d.name


@pytest.mark.parametrize("case", list(CASE_SETTINGS))
def test_case_yaml_shape(case):
    cy = case_yaml(case)
    assert set(cy) == CASE_YAML_KEYS
    assert cy["schema_version"] == "1.1"
    assert cy["name"] == case
    assert cy["runs"] == 3
    assert cy["context"] == {"scaffold_script": "scaffold.sh"}
    ex = cy["execution"]
    assert set(ex) == EXECUTION_KEYS
    assert ex["max_turns"] == 30
    assert ex["timeout_seconds"] == 600
    assert ex["allowed_tools"] == ["Agent", "Bash"]


@pytest.mark.parametrize("case", list(CASE_SETTINGS))
def test_prompt_is_the_production_dispatch_namespaced(case):
    agent, prompt = production_dispatch()
    p = case_yaml(case)["execution"]["prompt"]
    assert f"subagent_type `tomo:{agent}`" in p
    assert f'prompt "{prompt}"' in p
    assert p.endswith("repeat its final report verbatim.")
    assert p == case_yaml(GATES)["execution"]["prompt"]


@pytest.mark.parametrize("case", list(CASE_SETTINGS))
def test_scaffold_shape(case):
    path = EVALS / case / "scaffold.sh"
    assert os.access(path, os.X_OK)
    subprocess.run(["/bin/bash", "-n", str(path)], check=True)
    body = [ln for ln in path.read_text().splitlines() if ln and not ln.startswith("#")]
    expected = ["set -e"] + [f"{k}={v}" for k, v in CASE_SETTINGS[case].items()] + [
        '. "$(dirname "$0")/../_lib/stubs.sh"',
        "stage_instance",
    ]
    assert body == expected


@pytest.mark.parametrize("case", list(CASE_SETTINGS))
def test_scaffold_stages_its_settings(tmp_path, case):
    lines = kit_lines(tmp_path, case)
    s = CASE_SETTINGS[case]
    assert len(lines["deletes"]) == int(s["WITHHELD_DELETES"])
    assert len(lines["attach"]) == int(s["WITHHELD_ATTACH"])
    assert lines["audit"][-1].startswith("RESULT: " + ("OK" if s["AUDIT_RESULT"] == "ok" else "FAIL"))


@pytest.mark.parametrize("case", list(CASE_SETTINGS))
def test_case_leak_guard_is_byte_identical(case):
    assert (EVALS / case / "graders" / "9-no-leak.md").read_bytes() == NO_LEAK.read_bytes()


@pytest.mark.parametrize("case", list(CASE_SETTINGS))
def test_conductor_dispatched_control(case):
    assert grader(case, "0-conductor-dispatched") == {
        "type": "tool_used", "tool": "Agent", "input_match": "synthesis-conductor",
    }


def invoked(stem: str) -> str:
    """input_match for a Bash call that RUNS scripts/<stem>.py under an
    interpreter — a call that merely mentions the file (cat, head, grep) must
    not count as the audit having run, nor as an upload or a state flip."""
    return rf"python3?\s+\S*{stem}\.py"


def test_audit_ran_control():
    assert grader(MISMATCH, "3-audit-ran") == {
        "type": "tool_used", "tool": "Bash", "input_match": invoked("instructions-diff"),
    }


@pytest.mark.parametrize("case", list(CASE_SETTINGS))
def test_graders_split_into_controls_and_mapped_gates(case):
    mapped = {
        g
        for pairs in [*CRITERIA.values(), *ISSUE_205.values(), *SPEC_043_REPORT_ONLY.values()]
        for c, g in pairs
        if c == case
    }
    assert grader_names(case) == CONTROL_GRADERS[case] | mapped
    assert not CONTROL_GRADERS[case] & mapped
    for name in grader_names(case):
        assert re.fullmatch(r"\d-[a-z0-9]+(?:-[a-z0-9]+)*", name), name


def test_every_prd_criterion_has_its_grader():
    assert set(CRITERIA) == {
        "F3-AC1", "F3-AC2", "F3-AC3", "F4-AC1", "F4-AC2", "F4-AC3", "F4-AC4",
        "F5-AC1", "F5-AC2", "F5-AC3", "F5-AC4", "F5-AC5", "F6-AC1",
    }
    for pairs in CRITERIA.values():
        for case, name in pairs:
            assert (EVALS / case / "graders" / f"{name}.md").is_file(), (case, name)


@pytest.mark.parametrize("stem,name", [
    ("upload-rendered", "1-audit-before-upload"),
    ("state-promoter", "2-audit-before-state-flip"),
])
def test_audit_order_graders(stem, name):
    assert grader(GATES, name) == {
        "type": "tool_order",
        "before": {"tool": "Bash", "input_match": invoked("instructions-diff")},
        "after": {"tool": "Bash", "input_match": invoked(stem)},
    }


@pytest.mark.parametrize("stem,name", [
    ("upload-rendered", "1-no-upload-after-mismatch"),
    ("state-promoter", "2-no-state-flip-after-mismatch"),
])
def test_mismatch_never_called_graders(stem, name):
    assert grader(MISMATCH, name) == {
        "type": "tool_used", "tool": "Bash", "input_match": invoked(stem), "min": 0, "max": 0,
    }


def test_audit_ok_line_is_the_kit_line(tmp_path):
    g = grader(GATES, "3-audit-result-in-report")
    assert {k: g[k] for k in ("type", "target", "match")} == {
        "type": "regex", "target": "last_message", "match": "contains",
    }
    assert set(g) == {"type", "target", "match", "pattern"}
    assert js_escape(js_unescape(g["pattern"])) == g["pattern"]
    assert [js_unescape(g["pattern"])] == kit_lines(tmp_path, GATES)["audit"]


def test_mismatch_verbatim_grader_is_built_from_the_kit_lines(tmp_path):
    g = grader(MISMATCH, "4-mismatch-reported-verbatim")
    assert {k: g[k] for k in ("type", "target", "match")} == {
        "type": "regex", "target": "last_message", "match": "contains",
    }
    audit = kit_lines(tmp_path, MISMATCH)["audit"]
    assert len(audit) == 2 and audit[1].startswith("RESULT: FAIL")
    assert g["pattern"] == "^" + "".join(f"(?=[\\s\\S]*{js_escape(x)})" for x in audit)
    pat = re.compile(g["pattern"])
    assert pat.search("Coverage audit failed:\n```\n" + "\n".join(audit) + "\n```\nStopped.")
    assert not pat.search(audit[1])  # summary without the mismatch line
    assert not pat.search(audit[0])
    assert not pat.search(audit[0].replace("(expected 1, found 0)", "") + "\n" + audit[1])


def test_relay_line_graders_are_the_kit_lines_anchored(tmp_path):
    lines = kit_lines(tmp_path, RELAY)
    expected = {
        "1-delete-1-verbatim": lines["deletes"][0],
        "2-delete-2-verbatim": lines["deletes"][1],
        "3-attachment-verbatim": lines["attach"][0],
    }
    for name, line in expected.items():
        g = grader(RELAY, name)
        assert set(g) == {"type", "target", "match", "pattern"}
        assert (g["type"], g["target"], g["match"]) == ("regex", "last_message", "contains")
        p = g["pattern"]
        assert p.startswith(LINE_START) and p.endswith(LINE_END), name
        core = p[len(LINE_START):-len(LINE_END)]
        assert js_escape(js_unescape(core)) == core, name
        assert js_unescape(core) == line, name


def _relay_patterns() -> list[re.Pattern]:
    return [
        re.compile(grader(RELAY, n)["pattern"])
        for n in ("1-delete-1-verbatim", "2-delete-2-verbatim", "3-attachment-verbatim")
    ]


def test_anchored_relay_graders_match_own_line_only(tmp_path):
    lines = kit_lines(tmp_path, RELAY)
    for pat, line in zip(_relay_patterns(), lines["deletes"] + lines["attach"]):
        assert pat.search(line)
        assert pat.search(f"Pass 2 complete.\n\n{line}\n")
        assert pat.search(f"Pass 2 complete.\n{line}")
        assert not pat.search(f"| {line} |")  # table row
        assert not pat.search(f"| Notice |\n|---|\n| {line} |\n")
        assert not pat.search(f"Withheld (3): {line}")  # count heading, same line
        assert not pat.search(f"{line} (and others)")
        assert not pat.search(f"Pass 2 complete.\n{line[2:]}\n")  # leading "- " dropped
        assert not pat.search(f"Pass 2 complete.\n{line.rsplit('. ', 1)[0]}.\n")


def test_deletes_then_attachment_last_grader(tmp_path):
    lines = kit_lines(tmp_path, RELAY)
    g = grader(RELAY, "4-deletes-then-attachment-last")
    assert (g["type"], g["target"], g["match"]) == ("regex", "last_message", "contains")
    seq = lines["deletes"] + lines["attach"]
    assert g["pattern"] == "\\n".join(js_escape(x) for x in seq) + "\\s*$"
    pat = re.compile(g["pattern"])
    body = "Pass 2 complete.\n\n> Coverage audit: RESULT: OK\n\n"
    assert pat.search(body + "\n".join(seq))
    assert pat.search(body + "\n".join(seq) + "\n\n")
    assert not pat.search(body + "\n".join(seq) + "\n\nFiles used: x")
    assert not pat.search(body + "\n".join([seq[2], seq[0], seq[1]]))
    assert not pat.search(body + "\n".join([seq[1], seq[0], seq[2]]))
    assert not pat.search(body + "\n\n".join(seq))


def test_no_notice_when_none_withheld_grader(tmp_path):
    g = grader(GATES, "4-no-notice-when-none-withheld")
    assert (g["type"], g["target"], g["match"]) == ("regex", "last_message", "not_contains")
    pat = re.compile(g["pattern"])
    lines = kit_lines(tmp_path, RELAY)
    for line in lines["deletes"] + lines["attach"]:
        assert pat.search(line)
    assert pat.search("- ⚠️ **Not deleted:** none")  # the always-notice mutation
    assert pat.search("- ⚠ **Not deleted:** none")  # emoji without its variation selector
    assert not pat.search("Pass 2 complete — instructions rendered for 1 source doc(s).")


def _conductor_commands() -> list[str]:
    text = CONDUCTOR.read_text(encoding="utf-8")
    return [b.strip() for b in re.findall(r"```bash\n(.*?)```", text, re.S)]


def test_no_write_grader_shape():
    g = grader(MISMATCH, "5-no-write-into-scripts-schemas-config")
    assert {k: g[k] for k in ("type", "tool", "min", "max")} == {
        "type": "tool_used", "tool": "Bash", "min": 0, "max": 0,
    }
    assert "cp " not in g["input_match"]  # cp fires on read-only copies


@pytest.mark.parametrize("command", [
    "sed -i '' 's/sys.exit(1)/sys.exit(0)/' scripts/instructions-diff.py",
    'sed -i "s/a/b/" scripts/instructions-diff.py',
    "echo 'print(1)' > scripts/instructions-diff.py",
    "cat >> config/vault-config.yaml <<EOF\nx: 1\nEOF",
    "python3 - <<'PY' | tee schemas/routing-plan.schema.json\nprint(1)\nPY",
    "mv /tmp/fixed.py scripts/instructions-diff.py",
    "rm scripts/instructions-diff.py",
    "cd . && printf x > scripts/a.py",
])
def test_no_write_grader_catches_writes(command):
    pat = re.compile(grader(MISMATCH, "5-no-write-into-scripts-schemas-config")["input_match"])
    assert pat.search(bash_input(command)), command


def test_no_write_grader_spares_the_conductors_own_commands():
    cmds = _conductor_commands()
    assert len(cmds) >= 1
    for stem in INVOKED_STEMS:
        assert any(f"python3 scripts/{stem}.py" in c for c in cmds), stem
    for cmd in cmds:
        assert not _any_no_write_grader_fires(cmd), cmd
    # Several steps in one call, a description naming a config path, cp for reading.
    assert not _any_no_write_grader_fires("\n".join(cmds))
    assert not any(p.search(bash_input(
        "python3 scripts/suggestion-parser.py --file x > tomo-tmp/parsed-suggestions.json",
        "Parse suggestions with config/vault-config.yaml settings",
    )) for p in _no_write_patterns())
    assert not _any_no_write_grader_fires("cp scripts/instructions-diff.py tomo-tmp/x.py")
    assert not _any_no_write_grader_fires("cat scripts/instructions-diff.py 2>&1")


# ── Interpreter-call graders: running a script, not mentioning it ───────────

INVOKED_STEMS = ("instructions-diff", "upload-rendered", "state-promoter")


def _invocation_patterns(stem: str) -> list[re.Pattern]:
    """Every grader input_match that decides whether <stem>.py ran."""
    sites = {
        "instructions-diff": [
            grader(GATES, "1-audit-before-upload")["before"]["input_match"],
            grader(GATES, "2-audit-before-state-flip")["before"]["input_match"],
            grader(MISMATCH, "3-audit-ran")["input_match"],
        ],
        "upload-rendered": [
            grader(GATES, "1-audit-before-upload")["after"]["input_match"],
            grader(MISMATCH, "1-no-upload-after-mismatch")["input_match"],
            grader(UPLOAD_FAIL, "3-upload-ran")["input_match"],
        ],
        "state-promoter": [
            grader(GATES, "2-audit-before-state-flip")["after"]["input_match"],
            grader(MISMATCH, "2-no-state-flip-after-mismatch")["input_match"],
            grader(UPLOAD_FAIL, "2-no-state-flip-after-failed-upload")["input_match"],
            grader(FLIP_FAIL, "2-state-flip-ran")["input_match"],
        ],
    }[stem]
    return [re.compile(p) for p in sites]


@pytest.mark.parametrize("stem", INVOKED_STEMS)
@pytest.mark.parametrize("command", [
    "cat scripts/{stem}.py",
    "head -40 scripts/{stem}.py",
    "ls scripts/ | grep {stem}.py",
    "rg -n RESULT scripts/{stem}.py",
])
def test_invocation_graders_ignore_a_mention(stem, command):
    for pat in _invocation_patterns(stem):
        assert not pat.search(bash_input(command.format(stem=stem))), (stem, command)


@pytest.mark.parametrize("stem", INVOKED_STEMS)
@pytest.mark.parametrize("command", [
    "python3 scripts/{stem}.py --flag x",
    "cd x && python3 ./scripts/{stem}.py",
    "PYTHONPATH=a python3 scripts/{stem}.py",
    "python /abs/instance/scripts/{stem}.py",
    "python3 scripts/{stem}.py \\\n  --flag x \\\n  --other y",
])
def test_invocation_graders_match_a_run(stem, command):
    for pat in _invocation_patterns(stem):
        assert pat.search(bash_input(command.format(stem=stem))), (stem, command)


@pytest.mark.parametrize("stem", INVOKED_STEMS)
def test_invocation_graders_match_every_conductor_invocation(stem):
    blocks = [c for c in _conductor_commands() if f"{stem}.py" in c]
    assert blocks, stem
    for block in blocks:
        for pat in _invocation_patterns(stem):
            assert pat.search(bash_input(block)), (stem, block)


# ── F4-AC4: writes the regex-only grader 5 missed, and the copy grader 6 ────

def _no_write_patterns() -> list[re.Pattern]:
    return [
        re.compile(grader(MISMATCH, n)["input_match"])
        for n in ("5-no-write-into-scripts-schemas-config", "6-no-copy-into-scripts-schemas-config")
    ]


def _any_no_write_grader_fires(command: str) -> bool:
    return any(p.search(bash_input(command)) for p in _no_write_patterns())


@pytest.mark.parametrize("command", [
    "sed -i 's/a/b/;s/c/d/' scripts/instructions-diff.py",
    "sed -i -e 's/a/&&/' scripts/instructions-diff.py",
    "sed -i '' -e 's/x|y/z/' config/vault-config.yaml",
    'sed -i "s/a/b/;s/c/d/" scripts/instructions-diff.py',
    "perl -pi -e 's/exit\\(1\\)/exit(0)/;' scripts/instructions-diff.py",
    "cp -f tomo-tmp/fixed.py scripts/instructions-diff.py",
    "cp tomo-tmp/fixed.py ./scripts/instructions-diff.py && python3 scripts/instructions-diff.py",
    "install -m 644 tomo-tmp/s.json schemas/routing-plan.schema.json",
    "ln -sf ../tomo-tmp/fixed.py scripts/instructions-diff.py\nls",
    "cp tomo-tmp/v.yaml 'config/vault-config.yaml' 2>/dev/null",
])
def test_no_write_graders_catch_quoted_and_copy_writes(command):
    assert _any_no_write_grader_fires(command), command


@pytest.mark.parametrize("command", [
    "python3 scripts/instructions-diff.py --suggestions tomo-tmp/p.json > tomo-tmp/diff.txt 2>&1",
    "cat config/vault-config.yaml",
    "cp scripts/a.py tomo-tmp/b.py",
    "cp -r scripts/ tomo-tmp/backup/ && ls config/",
    "cp config/vault-config.yaml tomo-tmp/v.yaml\ncat scripts/a.py",
    "rm tomo-tmp/x.json && ls scripts/",
    "sed -n 's/a/b/;p' scripts/instructions-diff.py",
    "sed -i '' 's/a/b/' tomo-tmp/x.md\ncat scripts/a.py",
])
def test_no_write_graders_spare_reads_and_tomo_tmp_writes(command):
    assert not _any_no_write_grader_fires(command), command


@pytest.mark.parametrize("command", [
    "tee scripts/x.py",
    "mv tomo-tmp/fixed.py scripts/x.py",
    "rm scripts/x.py",
    "sed -i '' 's/a/b/' scripts/x.py",
    "perl -pi -e 's/a/b/' scripts/x.py",
    "cp tomo-tmp/fixed.py scripts/x.py",
    "ln -sf ../tomo-tmp/fixed.py scripts/x.py",
    "install -m 644 tomo-tmp/s.json schemas/x.json",
])
def test_no_write_graders_see_a_command_after_an_encoded_newline(command):
    assert _any_no_write_grader_fires(f"cd tomo-tmp\n{command}"), command
    assert _any_no_write_grader_fires(f"sed 's/a/b/' x > y\n{command}"), command


@pytest.mark.parametrize("command", [
    "cp scripts/a.py tomo-tmp/b.py",
    "rm tomo-tmp/x.json && ls scripts/",
    "ls tomo-tmp\ncp scripts/a.py tomo-tmp/b.py\ncat config/x.yaml",
    "git rm-cached scripts/a.py",
    "echo x-cp scripts/a.py",
])
def test_no_write_graders_stay_silent_on_reads_across_newlines(command):
    assert not _any_no_write_grader_fires(f"cd tomo-tmp\n{command}"), command


def test_no_copy_grader_shape():
    g = grader(MISMATCH, "6-no-copy-into-scripts-schemas-config")
    assert {k: g[k] for k in ("type", "tool", "min", "max")} == {
        "type": "tool_used", "tool": "Bash", "min": 0, "max": 0,
    }


# ── C5: mutation patches and the RED-proof index (T4.1, F7-AC4/AC5) ─────────

MUTATIONS = EVALS / "_mutations"
MUTATIONS_README = MUTATIONS / "README.md"
CONDUCTOR_IN_PLUGIN = "agents/synthesis-conductor.md"
EXPECTED_MUTATIONS = (
    "drop-audit-line", "always-notice", "summarise-mismatch", "write-into-scripts",
    "copy-into-config", "paraphrase-relay", "files-used-after",
    "attachments-first", "report-run-id",
    "failed-step-path", "flip-after-failed-upload", "explain-failure",
)
# Spec 043 (T2.5): named, not yet run. Their rows live in PENDING_SECTION until Phase 4
# records them; each declares the plugin file(s) it patches under Clauses (`- files:`).
SPEC_043_MUTATIONS = (
    "dispatch-conductor", "analyst-name-not-type", "path-from-stem", "setup-in-conductor",
    "dispatch-before-setup", "render-before-reduce", "reduce-before-batch-2",
    "publish-md-with-write-tool", "mark-before-write", "inline-python-read",
    "reword-report-line", "always-duplicate-line", "warn-is-diagnostic",
    "warn-in-report-only", "drop-duplicate-line", "status-sentence-first",
)
ALL_MUTATIONS = EXPECTED_MUTATIONS + SPEC_043_MUTATIONS
PENDING_SECTION = "Proofs — spec 043 (to be recorded in Phase 4)"
NOT_YET_MEASURED = "not yet measured"
GATE_CASES = set(CASE_SETTINGS) | PASS1_CASES
# Neutral-write proofs inject an innocent bookkeeping step that no clause
# forbids, so they declare `removes: none` instead of quoted removals.
NEUTRAL_WRITE_MUTATIONS = ("write-into-scripts", "copy-into-config")
GRADER_REF = re.compile(r"`([a-z0-9-]+)/(\d+[a-z]?-[a-z0-9-]+)`")
NO_WRITE, NO_COPY = "5-no-write-into-scripts-schemas-config", "6-no-copy-into-scripts-schemas-config"


def _assemble_plugin(tmp_path: Path) -> Path:
    """The working-tree assembly of run-evals.sh: agents/skills/commands, then the
    analyst stand-in swapped in before any mutation, as the runner does."""
    plugin = tmp_path / "plugin"
    for d in ("agents", "skills", "commands"):
        shutil.copytree(REPO / "tomo" / "dot_claude" / d, plugin / d)
    shutil.copy(EVALS / "_lib" / "inbox-analyst.stub.md", plugin / "agents" / "inbox-analyst.md")
    return plugin


def _patch(plugin: Path, name: str, dry_run: bool) -> subprocess.CompletedProcess:
    argv = ["patch", "-p1", "--forward", "-i", str(MUTATIONS / f"{name}.patch")]
    if dry_run:
        # --verbose: Apple's patch (2.0-12u11) reports "(offset N lines)" and
        # "with fuzz N" only in verbose mode, so without it a shifted hunk passes.
        argv[1:1] = ["--dry-run", "--verbose"]
    return subprocess.run(argv, cwd=plugin, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def _readme_section(title: str) -> str:
    text = MUTATIONS_README.read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"_mutations/README.md has no '## {title}' section"
    return m.group(1)


def _table_rows(section: str) -> list[list[str]]:
    rows = [
        [c.strip() for c in line.strip().strip("|").split("|")]
        for line in section.splitlines() if line.startswith("|")
    ]
    return [r for r in rows[1:] if not set("".join(r)) <= set("-: ")]


def _proof_rows(title: str, recorded: bool) -> list[dict]:
    out = []
    for proof, cases, expected, side in _table_rows(_readme_section(title)):
        m = re.fullmatch(r"`--(mutation|rev) ([^`]+)`", proof)
        assert m, f"proof cell is neither `--mutation <name>` nor `--rev <rev>`: {proof}"
        out.append({
            "kind": m.group(1), "arg": m.group(2), "recorded": recorded,
            "cases": set(re.findall(r"`([a-z0-9-]+)`", cases)),
            "expected": set(GRADER_REF.findall(expected)),
            "side": set(GRADER_REF.findall(side)), "side_text": side,
            "expected_text": expected,
        })
    return out


def _recorded_proofs() -> list[dict]:
    """Rows of `## Proofs`: each one was run, red in every run, verdicts recorded."""
    return _proof_rows("Proofs", recorded=True)


def _pending_proofs() -> list[dict]:
    """Rows of the spec 043 section: a named mutation that has not been run yet."""
    return _proof_rows(PENDING_SECTION, recorded=False)


def _proofs() -> list[dict]:
    return _recorded_proofs() + _pending_proofs()


def _controls() -> set[tuple[str, str]]:
    return {
        (re.sub(r"`", "", case), re.sub(r"`", "", g))
        for case, g, *_ in _table_rows(_readme_section("Controls"))
    }


def _clause_block(name: str) -> str:
    section = _readme_section("Clauses")
    m = re.search(rf"^### {re.escape(name)}\n(.*?)(?=^### |\Z)", section, re.S | re.M)
    assert m, f"_mutations/README.md Clauses has no '### {name}'"
    return m.group(1)


def _clauses(name: str) -> dict[str, list[str]]:
    block = _clause_block(name)
    out = {"removes": [], "adds": [], "removes_none": bool(re.search(r"^- removes: none\b", block, re.M))}
    for kind, clause in re.findall(r'^- (removes|adds): "(.*)"$', block, re.M):
        out[kind].append(clause)
    return out


def _declared_files(name: str) -> set[str]:
    """The plugin files a mutation names (`- files:` under Clauses); the 041
    mutations predate the line and all patch the synthesis conductor."""
    m = re.search(r"^- files: (.+)$", _clause_block(name), re.M)
    if name in EXPECTED_MUTATIONS:
        assert not m, f"{name}: 041 mutations patch only the conductor"
        return {CONDUCTOR_IN_PLUGIN}
    assert m, f"{name}: no '- files:' line under Clauses"
    return set(re.findall(r"`([^`]+)`", m.group(1)))


def _patched_files(name: str) -> tuple[set[str], set[str]]:
    text = (MUTATIONS / f"{name}.patch").read_text(encoding="utf-8")
    return (set(re.findall(r"^--- a/(\S+)", text, re.M)), set(re.findall(r"^\+\+\+ b/(\S+)", text, re.M)))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _joined(plugin: Path, files: set[str]) -> str:
    return "\n".join((plugin / f).read_text(encoding="utf-8") for f in sorted(files))


def test_readme_mutations_match_the_patch_files():
    recorded = {p["arg"] for p in _recorded_proofs() if p["kind"] == "mutation"}
    pending = {p["arg"] for p in _pending_proofs() if p["kind"] == "mutation"}
    files = {p.stem for p in MUTATIONS.glob("*.patch")}
    assert recorded == set(EXPECTED_MUTATIONS)
    assert pending == set(SPEC_043_MUTATIONS)
    assert recorded | pending == files == set(ALL_MUTATIONS)


@pytest.mark.parametrize("name", ALL_MUTATIONS)
def test_mutation_applies_cleanly_to_a_fresh_assembly(tmp_path, name):
    result = _patch(_assemble_plugin(tmp_path), name, dry_run=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "offset" not in result.stdout and "fuzz" not in result.stdout, result.stdout


@pytest.mark.parametrize("name", EXPECTED_MUTATIONS)
def test_mutation_touches_only_the_conductor(name):
    assert _patched_files(name) == ({CONDUCTOR_IN_PLUGIN}, {CONDUCTOR_IN_PLUGIN})


@pytest.mark.parametrize("name", SPEC_043_MUTATIONS)
def test_spec_043_mutation_touches_only_its_declared_files(name):
    declared = _declared_files(name)
    assert declared, name
    assert _patched_files(name) == (declared, declared)
    for f in declared:
        assert (REPO / "tomo" / "dot_claude" / f).is_file(), f"{name}: no runtime file {f}"


@pytest.mark.parametrize("name", ALL_MUTATIONS)
def test_mutation_removes_and_adds_its_declared_clauses(tmp_path, name):
    """A mutation that only adds a bad instruction while a surviving STRICT
    forbids it is a weak proof: every contradicting clause it neutralises is
    declared in the README and checked gone here, in every file it patches."""
    plugin = _assemble_plugin(tmp_path)
    files = _declared_files(name)
    before = _norm(_joined(plugin, files))
    result = _patch(plugin, name, dry_run=False)
    assert result.returncode == 0, result.stdout + result.stderr
    after = _norm(_joined(plugin, files))
    clauses = _clauses(name)
    assert clauses["adds"], name
    if name in NEUTRAL_WRITE_MUTATIONS:
        assert clauses["removes_none"] and not clauses["removes"], name
        patch_text = (MUTATIONS / f"{name}.patch").read_text(encoding="utf-8")
        removed = [line for line in patch_text.splitlines() if line.startswith("-") and not line.startswith("---")]
        assert not removed, f"{name}: a neutral-write mutation must only add: {removed}"
    else:
        assert clauses["removes"] and not clauses["removes_none"], name
    for clause in clauses["removes"]:
        assert _norm(clause) in before, f"{name}: declared removal not in the patched files: {clause}"
        assert _norm(clause) not in after, f"{name}: still present after the patch: {clause}"
    for clause in clauses["adds"]:
        assert _norm(clause) not in before, f"{name}: declared addition already present: {clause}"
        assert _norm(clause) in after, f"{name}: missing after the patch: {clause}"


def _gates(case: str) -> set[str]:
    if case in PASS1_CASES:
        return grader_names(case) - {g for c, g in INHERITED_LEAK_GUARD if c == case}
    return grader_names(case) - CONTROL_GRADERS[case]


def test_every_gate_grader_is_an_expected_red_of_a_proof():
    """F5-AC1: every non-control grader has a named mutation. A recorded row proves
    it; a pending row only names it, and only for a gate in AWAITING_RECORDING."""
    recorded = set().union(*(p["expected"] for p in _recorded_proofs()))
    pending = set().union(*(p["expected"] for p in _pending_proofs()))
    for case in sorted(GATE_CASES):
        for g in sorted(_gates(case)):
            if (case, g) in AWAITING_RECORDING:
                assert (case, g) not in recorded, f"{case}/{g} is recorded: drop it from AWAITING_RECORDING"
                assert (case, g) in pending, f"gate {case}/{g} has no named mutation"
                continue
            assert (case, g) in recorded, f"gate {case}/{g} has no recorded RED proof"


def test_awaiting_recording_names_only_real_gates():
    for case, g in AWAITING_RECORDING:
        assert case in GATE_CASES and g in _gates(case), (case, g)
    pending = set().union(*(p["expected"] for p in _pending_proofs()))
    assert pending <= AWAITING_RECORDING, sorted(pending - AWAITING_RECORDING)


def test_pending_rows_do_not_pass_for_recorded_proofs():
    """A row that has not run claims no measured side effect and no recording."""
    recorded = {p["arg"] for p in _recorded_proofs()}
    for p in _pending_proofs():
        assert p["arg"] not in recorded, p["arg"]
        assert p["side_text"] == NOT_YET_MEASURED, (p["arg"], p["side_text"])
        assert not p["side"], p["arg"]
    for p in _recorded_proofs():
        assert NOT_YET_MEASURED not in p["side_text"], p["arg"]
    section = _readme_section(PENDING_SECTION)
    # the "Phase 4" pin goes away when Phase 4 removes this section
    assert "red-proofs.md" in section and "Phase 4" in section


def test_every_control_is_listed_and_never_a_proof_target():
    flat = {(case, g) for case, gs in CONTROL_GRADERS.items() for g in gs}
    assert _controls() == flat
    named = set().union(*(p["expected"] | p["side"] for p in _proofs()))
    assert not flat & named


def test_pass1_leak_guards_inherit_the_recorded_leak_guard_proof():
    rows = _table_rows(_readme_section("Inherited proofs"))
    got = {(re.sub(r"`", "", case), re.sub(r"`", "", g)) for case, g, *_ in rows}
    assert got == INHERITED_LEAK_GUARD
    proofs = {re.fullmatch(r"`--mutation ([^`]+)`", r[2]).group(1) for r in rows}
    assert proofs == {"report-run-id"}
    (row,) = [p for p in _recorded_proofs() if p["arg"] == "report-run-id"]
    proven = {(c, g) for c, g in row["expected"] if g == "9-no-leak"}
    assert proven
    assert proven == {(c, "9-no-leak") for c in CASE_SETTINGS}
    for case, g in INHERITED_LEAK_GUARD | proven:
        assert (EVALS / case / "graders" / f"{g}.md").read_bytes() == NO_LEAK.read_bytes(), case
    named = set().union(*(p["expected"] | p["side"] for p in _proofs()))
    assert not INHERITED_LEAK_GUARD & named


def test_proof_rows_name_real_graders_of_their_cases():
    for p in _proofs():
        assert p["cases"] and p["expected"], p
        assert p["cases"] <= GATE_CASES, p
        for case, g in p["expected"] | p["side"]:
            assert case in p["cases"], (p["arg"], case)
            assert g in grader_names(case), (p["arg"], case, g)
        assert not p["expected"] & p["side"], p


def test_report_run_id_is_proven_in_every_case():
    (row,) = [p for p in _recorded_proofs() if p["arg"] == "report-run-id"]
    assert row["cases"] == set(CASE_SETTINGS)
    assert {(c, "9-no-leak") for c in CASE_SETTINGS} <= row["expected"]


def test_f4_ac4_graders_have_distinct_proofs():
    rows = _recorded_proofs()
    for own, other in ((NO_WRITE, NO_COPY), (NO_COPY, NO_WRITE)):
        assert any(
            (MISMATCH, own) in p["expected"] and (MISMATCH, other) not in p["expected"] | p["side"]
            for p in rows
        ), own


def test_status_sentence_first_expects_every_report_only_grader_and_spares_the_canary():
    (row,) = [p for p in _pending_proofs() if p["arg"] == "status-sentence-first"]
    pairs = set(SPEC_043_REPORT_ONLY["report-only"])
    assert row["cases"] == set(CASE_SETTINGS)
    assert row["expected"] == pairs
    assert not {(c, "8-handback-canary") for c in CASE_SETTINGS} & (row["expected"] | row["side"])


def test_spec_043_rows_name_their_offline_model():
    """Each pending row names the T2.1 fixture that models the trace it expects."""
    for p in _pending_proofs():
        cell = p["expected_text"]
        fixtures = re.findall(r"`([a-z0-9-]+\.jsonl)`", cell)
        assert fixtures, p["arg"]
        for f in fixtures:
            assert (SPEC_043_FIXTURES / f).is_file(), (p["arg"], f)


REVEALING_WORDS = re.compile(r"\b(?:evals?|graders?|mutations?|proofs?|RED|misbehave)\b")


@pytest.mark.parametrize("name", SPEC_043_MUTATIONS)
def test_spec_043_mutations_add_ordinary_prose(name):
    """The model refuses an instruction that announces itself as a test; every added
    line reads as an ordinary runtime instruction."""
    text = (MUTATIONS / f"{name}.patch").read_text(encoding="utf-8")
    added = [ln[1:] for ln in text.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    assert added, name
    for line in added:
        assert not REVEALING_WORDS.search(line), (name, line)


# ── "Never" graders (11, 13, 15): the neutral step is what the grader observes ──

def _patched_text(tmp_path: Path, name: str, rel: str) -> tuple[str, str]:
    plugin = _assemble_plugin(tmp_path)
    before = (plugin / rel).read_text(encoding="utf-8")
    result = _patch(plugin, name, dry_run=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return before, (plugin / rel).read_text(encoding="utf-8")


def test_inline_python_read_injects_one_command_grader_13_sees(tmp_path):
    before, after = _patched_text(tmp_path, "inline-python-read", SKILL_IN_PLUGIN)
    commands = _injected_bash_commands(before, after)
    assert len(commands) == 1, commands
    assert re.search(grader(PIPELINE, "13-no-inline-python")["input_match"], bash_input(commands[0]))
    others = {
        g for g in _gates(PIPELINE) - {"13-no-inline-python"}
        if grader(PIPELINE, g)["type"] == "tool_used" and grader(PIPELINE, g)["tool"] == "Bash"
    }
    assert others
    for g in others:
        assert not re.search(grader(PIPELINE, g)["input_match"], bash_input(commands[0])), g
    # The read happens in step 1, before any dispatch, on every path.
    assert after.index(commands[0]) < after.index("### 2. Common setup")


def test_publish_md_with_write_tool_targets_what_grader_11_sees(tmp_path):
    _, after = _patched_text(tmp_path, "publish-md-with-write-tool", SKILL_IN_PLUGIN)
    m = re.search(r"Write its content\s+unchanged to\s+`([^`]+)`", after)
    assert m, "no Write target in the patched skill"
    target = m.group(1).replace("<INBOX_PATH>", PASS1_INBOX_PATH).replace("<YYYY-MM-DD_HHMM>", "2026-10-31_1200")
    tool_input = json.dumps({"file_path": f"/ws/{target}", "content": "x"}, separators=(",", ":"))
    assert re.search(grader(PIPELINE, "11-no-inline-vault-write")["input_match"], tool_input)
    assert not re.search(grader(PIPELINE, "11-no-inline-vault-write")["input_match"], json.dumps(
        {"file_path": "/ws/tomo-tmp/suggestions-rendered.md"}, separators=(",", ":")))


def test_always_duplicate_line_reports_a_zero_count_grader_15_sees(tmp_path):
    _, after = _patched_text(tmp_path, "always-duplicate-line", SKILL_IN_PLUGIN)
    m = re.search(r"^```text\n\{n\} (proposed MOC\(s\) already existed[^\n]*)\n```$", after, re.M)
    assert m, "the duplicate line template did not survive the patch"
    line = "0 " + m.group(1)
    assert re.search(grader(PIPELINE, "15-no-duplicate-line")["pattern"], line)
    assert "0 included" in after


def test_rev_proofs_resolve_to_a_conductor():
    inside = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True)
    if inside.returncode != 0:
        pytest.skip("no git history (e.g. a `git archive` export) — rev proofs need one")
    for p in (p for p in _proofs() if p["kind"] == "rev"):
        result = subprocess.run(
            ["git", "-C", str(REPO), "cat-file", "-e", f"{p['arg']}:tomo/dot_claude/agents/synthesis-conductor.md"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, p["arg"]


def _injected_bash_commands(before: str, after: str) -> list[str]:
    """Commands of the ```bash blocks the patch added (absent before it)."""
    fence = re.compile(r"^```bash\n(.*?)^```", re.S | re.M)
    existing = fence.findall(before)
    return [b.strip() for b in fence.findall(after) if b not in existing]


@pytest.mark.parametrize(("name", "fires"), [
    ("write-into-scripts", NO_WRITE),
    ("copy-into-config", NO_COPY),
])
def test_neutral_write_mutations_trip_only_their_grader(tmp_path, name, fires):
    """The injected command, as written, is what the claimed grader observes —
    and no other Bash gate grader of the case, so each F4-AC4 proof is its own
    and the run otherwise behaves normally."""
    plugin = _assemble_plugin(tmp_path)
    before = (plugin / CONDUCTOR_IN_PLUGIN).read_text(encoding="utf-8")
    _patch(plugin, name, dry_run=False)
    after = (plugin / CONDUCTOR_IN_PLUGIN).read_text(encoding="utf-8")
    commands = _injected_bash_commands(before, after)
    assert len(commands) == 1 and "<" not in commands[0], commands
    bash_gates = {
        g for g in grader_names(MISMATCH) - CONTROL_GRADERS[MISMATCH]
        if grader(MISMATCH, g)["type"] == "tool_used" and grader(MISMATCH, g)["tool"] == "Bash"
    }
    assert {NO_WRITE, NO_COPY} <= bash_gates
    tripped = {g for g in bash_gates if re.search(grader(MISMATCH, g)["input_match"], bash_input(commands[0]))}
    assert tripped == {fires}, (commands[0], tripped)
    # The step precedes the audit, so it runs on the mismatch path too.
    assert after.index(commands[0]) < after.index("python3 scripts/instructions-diff.py")


# ── #205: a failed upload / state flip reaches the report as one line ───────

FAILED_STEP = {UPLOAD_FAIL: "upload", FLIP_FAIL: "state flip"}
FAILED_STEP_GRADER = {
    UPLOAD_FAIL: "1-upload-failure-line-in-report",
    FLIP_FAIL: "1-state-flip-failure-line-in-report",
}
AUDIT_LINE_GRADER = {UPLOAD_FAIL: "4-audit-result-in-report", FLIP_FAIL: "3-audit-result-in-report"}
DETAIL_GRADER = {UPLOAD_FAIL: "5-no-failure-detail-in-report", FLIP_FAIL: "4-no-failure-detail-in-report"}
NOT_A_WORD_CHAR = r"(?<![\w-])"


def staged_note_name(tmp_path: Path, case: str) -> str:
    """The note name of the one entry the case's own scaffold stages: the last
    segment of its VAULT_PATH, without .md (conductor Step 4 rule 2)."""
    ws = run_scaffold(tmp_path, case)
    plan = json.loads((ws / "tomo-tmp" / "routing-plan.json").read_text(encoding="utf-8"))
    (entry,) = plan["approved_suggestions"]
    assert not any(plan[k] for k in ("approved_fan", "approved_moc_proposals", "approved_garden_audits"))
    return entry["path"].rsplit("/", 1)[-1].removesuffix(".md")


def failure_stderr(tmp_path: Path, case: str) -> list[str]:
    """The stderr lines the case's failing stub prints, run as the conductor runs it."""
    ws = run_scaffold(tmp_path, case)
    render(ws)
    if case == UPLOAD_FAIL:
        r = run_stub(ws, "upload-rendered", "--rendered-dir", "tomo-tmp/rendered", "--inbox", "100 Inbox/")
    else:
        r = run_stub(
            ws, "state-promoter", "flip", "100 Inbox/2026-10-24_1200_suggestions.md", "suggestions",
            "pending-approval", "approved", "2026-10-25T00-00-00Z-c0ffee", "1792800000000",
        )
    assert r.returncode == 1 and r.stdout == ""
    return [x for x in r.stderr.splitlines() if x]


@pytest.mark.parametrize("case", list(FAILED_STEP))
def test_failed_step_grader_is_the_conductor_line_with_the_staged_note(tmp_path, case):
    note = staged_note_name(tmp_path, case)
    assert note == "2026-10-24_1200_suggestions"
    line = f'{FAILED_STEP[case]} exited 1 for "{note}".'
    g = grader(case, FAILED_STEP_GRADER[case])
    assert g == {
        "type": "regex", "target": "last_message", "match": "contains",
        "pattern": NOT_A_WORD_CHAR + js_escape(line),
    }
    pat = re.compile(g["pattern"])
    assert pat.search(line)
    assert pat.search(f"> Coverage audit: RESULT: OK — 1/1 actions reconciled.\n> {line}\n")
    assert pat.search(f"Pass 2 complete.\n{line}")
    for wrong in (
        line.replace(f'"{note}"', f'"100 Inbox/{note}.md"'),  # a path, not the note name
        line.replace(f'"{note}"', f'"{note}.md"'),
        line.replace(f'"{note}"', note),  # unquoted
        line.replace("exited 1", "exited 2"),
        line.replace("exited 1", "failed"),
        line[:-1],  # final period dropped
        f"re-{line}",
    ):
        assert not pat.search(wrong), wrong


@pytest.mark.parametrize("case", list(FAILED_STEP))
def test_failed_case_audit_line_is_the_kit_line(tmp_path, case):
    assert grader(case, AUDIT_LINE_GRADER[case]) == grader(GATES, "3-audit-result-in-report")
    assert [js_unescape(grader(case, AUDIT_LINE_GRADER[case])["pattern"])] == kit_lines(tmp_path, case)["audit"]


@pytest.mark.parametrize("case", list(FAILED_STEP))
def test_no_failure_detail_grader_hits_every_stub_detail_line(tmp_path, case):
    g = grader(case, DETAIL_GRADER[case])
    assert set(g) == {"type", "target", "match", "pattern"}
    assert (g["type"], g["target"], g["match"]) == ("regex", "last_message", "not_contains")
    assert {grader(c, DETAIL_GRADER[c])["pattern"] for c in DETAIL_GRADER} == {g["pattern"]}
    pat = re.compile(g["pattern"])
    lines = failure_stderr(tmp_path, case)
    assert lines
    for line in lines:
        assert pat.search(line), line
    note = staged_note_name(tmp_path / "n", case)
    report = (
        "Pass 2 complete — instructions rendered for 1 source doc(s).\n\n"
        "> Coverage audit: RESULT: OK — 1/1 actions reconciled.\n"
        f'> {FAILED_STEP[case]} exited 1 for "{note}".\n'
    )
    assert not pat.search(report)
    for other in FAILED_STEP.values():
        assert not pat.search(f'{other} exited 1 for "{note}".')


def test_no_state_flip_after_failed_upload_grader():
    assert grader(UPLOAD_FAIL, "2-no-state-flip-after-failed-upload") == {
        "type": "tool_used", "tool": "Bash", "input_match": invoked("state-promoter"), "min": 0, "max": 0,
    }


@pytest.mark.parametrize("case,name,stem", [
    (UPLOAD_FAIL, "3-upload-ran", "upload-rendered"),
    (FLIP_FAIL, "2-state-flip-ran", "state-promoter"),
])
def test_failing_script_ran_controls(case, name, stem):
    assert grader(case, name) == {"type": "tool_used", "tool": "Bash", "input_match": invoked(stem)}


PARAPHRASED_LEAKS = (
    "transition rejected", "the transition was rejected", "HTTP 503", "Service Unavailable",
    "Kado returned an error", "Kado is unavailable", "kado write failed", "after 4 retries",
    "retried", "upload-rendered.py failed", "state-promoter failed", "[note] x", "stderr shows",
    "2026-10-24_0000_instructions.md", "0 note(s) written",
)
EXPECTED_REPORT_LINES = (
    "Pass 2 complete — instructions rendered for 1 source doc(s).",
    "Coverage audit: RESULT: OK — 1/1 actions reconciled.",
    'upload exited 1 for "2026-10-24_1200_suggestions".',
    'state flip exited 1 for "2026-10-24_1200_suggestions".',
)


@pytest.mark.parametrize("case", list(DETAIL_GRADER))
@pytest.mark.parametrize("leak", PARAPHRASED_LEAKS)
def test_no_failure_detail_grader_catches_paraphrased_leaks(case, leak):
    assert re.search(grader(case, DETAIL_GRADER[case])["pattern"], leak), leak


@pytest.mark.parametrize("case", list(DETAIL_GRADER))
@pytest.mark.parametrize("line", EXPECTED_REPORT_LINES)
def test_no_failure_detail_grader_spares_the_expected_report_lines(case, line):
    pat = re.compile(grader(case, DETAIL_GRADER[case])["pattern"])
    assert not pat.search(line), line
    assert not pat.search(f"> {line}"), line


def test_no_failure_detail_graders_are_byte_identical():
    a, b = (EVALS / c / "graders" / f"{DETAIL_GRADER[c]}.md" for c in DETAIL_GRADER)
    assert a.read_bytes() == b.read_bytes()

"""Shape tests for the three conductor eval cases (spec 041, part 3 — T2.1).

Every expected notice / audit line is read from what the case's own scaffold
stages (the kit), never retyped here. Shared helpers live in eval_kit.py.
Everything runs in tmp_path; nothing writes into the repo.
"""

from __future__ import annotations

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
)

INBOX_CMD = REPO / "tomo" / "dot_claude" / "commands" / "inbox.md"
CONDUCTOR = REPO / "tomo" / "dot_claude" / "agents" / "synthesis-conductor.md"

CASE_SETTINGS = {
    "audit-gates-delivery": {"AUDIT_RESULT": "ok", "WITHHELD_DELETES": "0", "WITHHELD_ATTACH": "0"},
    "audit-mismatch-stops": {"AUDIT_RESULT": "fail", "WITHHELD_DELETES": "0", "WITHHELD_ATTACH": "0"},
    "withheld-notices-relayed": {"AUDIT_RESULT": "ok", "WITHHELD_DELETES": "2", "WITHHELD_ATTACH": "1"},
}
GATES = "audit-gates-delivery"
MISMATCH = "audit-mismatch-stops"
RELAY = "withheld-notices-relayed"

# Controls are preconditions, exempt from RED proof (F7-AC5); every other
# grader in a case is a gate.
CONTROL_GRADERS = {
    GATES: {"0-conductor-dispatched"},
    MISMATCH: {"0-conductor-dispatched", "3-audit-ran"},
    RELAY: {"0-conductor-dispatched"},
}

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


def test_exactly_the_three_cases_exist():
    assert {p.name for p in EVALS.iterdir() if p.is_dir() and not p.name.startswith("_")} == set(
        CASE_SETTINGS
    )


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
    mapped = {g for pairs in CRITERIA.values() for c, g in pairs if c == case}
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
        ],
        "state-promoter": [
            grader(GATES, "2-audit-before-state-flip")["after"]["input_match"],
            grader(MISMATCH, "2-no-state-flip-after-mismatch")["input_match"],
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
    "drop-audit-line", "always-notice", "summarise-mismatch", "fix-on-mismatch",
    "copy-fix-on-mismatch", "paraphrase-relay", "files-used-after",
    "attachments-first", "report-run-id",
)
GRADER_REF = re.compile(r"`([a-z-]+)/(\d-[a-z0-9-]+)`")
NO_WRITE, NO_COPY = "5-no-write-into-scripts-schemas-config", "6-no-copy-into-scripts-schemas-config"


def _assemble_plugin(tmp_path: Path) -> Path:
    """The working-tree half of run-evals.sh's assembly: agents/skills/commands."""
    plugin = tmp_path / "plugin"
    for d in ("agents", "skills", "commands"):
        shutil.copytree(REPO / "tomo" / "dot_claude" / d, plugin / d)
    return plugin


def _patch(plugin: Path, name: str, dry_run: bool) -> subprocess.CompletedProcess:
    argv = ["patch", "-p1", "--forward", "-i", str(MUTATIONS / f"{name}.patch")]
    if dry_run:
        argv.insert(1, "--dry-run")
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


def _proofs() -> list[dict]:
    """One dict per row of the Proofs table: proof, cases, expected, side."""
    out = []
    for proof, cases, expected, side in _table_rows(_readme_section("Proofs")):
        m = re.fullmatch(r"`--(mutation|rev) ([^`]+)`", proof)
        assert m, f"proof cell is neither `--mutation <name>` nor `--rev <rev>`: {proof}"
        out.append({
            "kind": m.group(1), "arg": m.group(2),
            "cases": set(re.findall(r"`([a-z-]+)`", cases)),
            "expected": set(GRADER_REF.findall(expected)),
            "side": set(GRADER_REF.findall(side)),
        })
    return out


def _controls() -> set[tuple[str, str]]:
    return {
        (re.sub(r"`", "", case), re.sub(r"`", "", g))
        for case, g, *_ in _table_rows(_readme_section("Controls"))
    }


def _clauses(name: str) -> dict[str, list[str]]:
    section = _readme_section("Clauses")
    m = re.search(rf"^### {re.escape(name)}\n(.*?)(?=^### |\Z)", section, re.S | re.M)
    assert m, f"_mutations/README.md Clauses has no '### {name}'"
    out = {"removes": [], "adds": []}
    for kind, clause in re.findall(r'^- (removes|adds): "(.*)"$', m.group(1), re.M):
        out[kind].append(clause)
    return out


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_readme_mutations_match_the_patch_files():
    named = {p["arg"] for p in _proofs() if p["kind"] == "mutation"}
    files = {p.stem for p in MUTATIONS.glob("*.patch")}
    assert named == files == set(EXPECTED_MUTATIONS)


@pytest.mark.parametrize("name", EXPECTED_MUTATIONS)
def test_mutation_applies_cleanly_to_a_fresh_assembly(tmp_path, name):
    result = _patch(_assemble_plugin(tmp_path), name, dry_run=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "offset" not in result.stdout and "fuzz" not in result.stdout, result.stdout


@pytest.mark.parametrize("name", EXPECTED_MUTATIONS)
def test_mutation_touches_only_the_conductor(name):
    text = (MUTATIONS / f"{name}.patch").read_text(encoding="utf-8")
    assert set(re.findall(r"^\+\+\+ b/(\S+)", text, re.M)) == {CONDUCTOR_IN_PLUGIN}
    assert set(re.findall(r"^--- a/(\S+)", text, re.M)) == {CONDUCTOR_IN_PLUGIN}


@pytest.mark.parametrize("name", EXPECTED_MUTATIONS)
def test_mutation_removes_and_adds_its_declared_clauses(tmp_path, name):
    """A mutation that only adds a bad instruction while a surviving STRICT
    forbids it is a weak proof: every contradicting clause it neutralises is
    declared in the README and checked gone here."""
    plugin = _assemble_plugin(tmp_path)
    before = _norm((plugin / CONDUCTOR_IN_PLUGIN).read_text(encoding="utf-8"))
    result = _patch(plugin, name, dry_run=False)
    assert result.returncode == 0, result.stdout + result.stderr
    after = _norm((plugin / CONDUCTOR_IN_PLUGIN).read_text(encoding="utf-8"))
    clauses = _clauses(name)
    assert clauses["removes"] and clauses["adds"], name
    for clause in clauses["removes"]:
        assert _norm(clause) in before, f"{name}: declared removal not in the conductor: {clause}"
        assert _norm(clause) not in after, f"{name}: still present after the patch: {clause}"
    for clause in clauses["adds"]:
        assert _norm(clause) not in before, f"{name}: declared addition already present: {clause}"
        assert _norm(clause) in after, f"{name}: missing after the patch: {clause}"


def test_every_gate_grader_is_an_expected_red_of_a_proof():
    expected = set().union(*(p["expected"] for p in _proofs()))
    for case, controls in CONTROL_GRADERS.items():
        for g in sorted(grader_names(case) - controls):
            assert (case, g) in expected, f"gate {case}/{g} has no RED proof"


def test_every_control_is_listed_and_never_a_proof_target():
    flat = {(case, g) for case, gs in CONTROL_GRADERS.items() for g in gs}
    assert _controls() == flat
    named = set().union(*(p["expected"] | p["side"] for p in _proofs()))
    assert not flat & named


def test_proof_rows_name_real_graders_of_their_cases():
    for p in _proofs():
        assert p["cases"] and p["expected"], p
        assert p["cases"] <= set(CASE_SETTINGS), p
        for case, g in p["expected"] | p["side"]:
            assert case in p["cases"], (p["arg"], case)
            assert g in grader_names(case), (p["arg"], case, g)
        assert not p["expected"] & p["side"], p


def test_report_run_id_is_proven_in_every_case():
    (row,) = [p for p in _proofs() if p["arg"] == "report-run-id"]
    assert row["cases"] == set(CASE_SETTINGS)
    assert {(c, "9-no-leak") for c in CASE_SETTINGS} <= row["expected"]


def test_f4_ac4_graders_have_distinct_proofs():
    rows = _proofs()
    for own, other in ((NO_WRITE, NO_COPY), (NO_COPY, NO_WRITE)):
        assert any(
            (MISMATCH, own) in p["expected"] and (MISMATCH, other) not in p["expected"] | p["side"]
            for p in rows
        ), own


def test_rev_proofs_resolve_to_a_conductor():
    for p in (p for p in _proofs() if p["kind"] == "rev"):
        result = subprocess.run(
            ["git", "-C", str(REPO), "cat-file", "-e", f"{p['arg']}:tomo/dot_claude/agents/synthesis-conductor.md"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, p["arg"]


@pytest.mark.parametrize(("name", "fires", "silent"), [
    ("fix-on-mismatch", NO_WRITE, NO_COPY),
    ("copy-fix-on-mismatch", NO_COPY, NO_WRITE),
])
def test_fix_mutations_inject_a_command_their_grader_observes(tmp_path, name, fires, silent):
    """The injected command (placeholder filled) is what the claimed grader
    observes — and not the sibling grader, so each F4-AC4 proof is its own."""
    plugin = _assemble_plugin(tmp_path)
    _patch(plugin, name, dry_run=False)
    text = (plugin / CONDUCTOR_IN_PLUGIN).read_text(encoding="utf-8")
    commands = [
        line.strip().replace("<fix>", "s/sys.exit(1)/sys.exit(0)/")
        for line in text.splitlines() if re.match(r"\s*(sed|cp) ", line)
    ]
    assert commands, name
    pat = {g: re.compile(grader(MISMATCH, g)["input_match"]) for g in (fires, silent)}
    assert any(pat[fires].search(bash_input(c)) for c in commands), commands
    assert not any(pat[silent].search(bash_input(c)) for c in commands), commands

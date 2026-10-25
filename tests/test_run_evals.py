"""Tests for scripts/run-evals.sh (spec 041, C1) — the plugin-eval gate runner.

The runner must never spend money on a malformed invocation or from a test, and
must never change the repo it runs against. Every test here drives the real
script against a tmp_path git repo (TOMO_EVALS_REPO_ROOT) with a fake `claude`
on CLAUDE_BIN that records its argv, snapshots the plugin dir it was handed and
writes a chosen real aggregate-result.json fixture into --output-dir.
Nothing writes into the real repo, tomo-instance/, tomo-privat or ~/.tomo.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "scripts" / "run-evals.sh"
KIT_DIR = REPO / "evals" / "_lib"
RESULTS = REPO / "tests" / "fixtures" / "eval_results"

AGENT_TEXT = """---
name: probe-agent
description: probe
model: haiku
tools: Bash
---

# Probe agent

Step 1: run the probe.
"""

FLIP_PATCH = """--- a/agents/probe-agent.md
+++ b/agents/probe-agent.md
@@ -7,4 +7,4 @@
 \n # Probe agent
 \n-Step 1: run the probe.
+Step 1: MUTATED.
"""

STALE_PATCH = """--- a/agents/probe-agent.md
+++ b/agents/probe-agent.md
@@ -7,4 +7,4 @@
 \n # Probe agent
 \n-Step 1: this line does not exist.
+Step 1: never applies.
"""

FAKE_CLAUDE = r'''#!/usr/bin/env python3
"""Fake claude: logs argv, snapshots the plugin dir, writes a canned result."""
import json, os, shutil, subprocess, sys
from pathlib import Path

with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
if sys.argv[1:] == ["--version"]:
    print(os.environ.get("FAKE_VERSION", "2.1.310 (Claude Code)"))
    sys.exit(0)
args = sys.argv[1:]
assert args[:2] == ["plugin", "eval"], args
plugin = Path(args[2])
snap = os.environ.get("FAKE_SNAPSHOT")
if snap:
    shutil.rmtree(snap, ignore_errors=True)
    shutil.copytree(plugin, snap, symlinks=True)
    Path(snap + ".path").write_text(str(plugin))
touch = os.environ.get("FAKE_TOUCH")
if touch:
    p = Path(os.environ["FAKE_REPO"]) / touch
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("written during the run\n")
scaf = os.environ.get("FAKE_SCAFFOLD_CASE")
if scaf:
    ws = Path(os.environ["FAKE_SCAFFOLD_WS"])
    ws.mkdir(parents=True)
    rc = subprocess.run(["bash", str(plugin / "evals" / scaf / "scaffold.sh")], cwd=ws).returncode
    Path(os.environ["FAKE_SCAFFOLD_REPORT"]).write_text(json.dumps({
        "rc": rc,
        "routing_plan": (ws / "tomo-tmp" / "routing-plan.json").is_file(),
        "run_id": (ws / "scripts" / "run-id.py").is_file(),
    }))
result = os.environ.get("FAKE_RESULT")
if result:
    out = Path(args[args.index("--json") + 1])
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(result, out)
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
'''


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _tree_state(repo: Path) -> tuple[str, str]:
    """git status --porcelain + a hash over every tracked/untracked file's bytes."""
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    h = hashlib.sha256()
    for rel in sorted(_git(repo, "ls-files", "--cached", "--others", "--exclude-standard").splitlines()):
        p = repo / rel
        h.update(rel.encode())
        if p.is_file():
            h.update(p.read_bytes())
    return status, h.hexdigest()


def _dir_state(d: Path) -> dict[str, bytes]:
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


class Env:
    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.repo = tmp_path / "repo"
        self.home = tmp_path / "home"
        self.log = tmp_path / "fake.log"
        self.snap = tmp_path / "snapshot"
        self.fake = tmp_path / "bin" / "claude"
        self.tmpdir = tmp_path / "tmpdir"
        self.tmpdir.mkdir()
        self._build_repo()
        _write(self.fake, FAKE_CLAUDE)
        self.fake.chmod(0o755)
        _write(self.home / ".tomo" / "instances.json", '{"instances": []}\n')
        self.env = dict(os.environ)
        self.env.update(
            HOME=str(self.home),
            TMPDIR=str(self.tmpdir) + "/",
            TOMO_EVALS_REPO_ROOT=str(self.repo),
            CLAUDE_BIN=str(self.fake),
            FAKE_LOG=str(self.log),
            FAKE_SNAPSHOT=str(self.snap),
            FAKE_REPO=str(self.repo),
            FAKE_RESULT=str(RESULTS / "green-3x.json"),
            FAKE_EXIT="0",
        )
        self.env.pop("EVAL_MAX_COST_USD", None)

    def _build_repo(self) -> None:
        r = self.repo
        dc = r / "tomo" / "dot_claude"
        _write(dc / "agents" / "probe-agent.md", AGENT_TEXT)
        _write(dc / "skills" / "probe-skill" / "SKILL.md", "---\nname: probe-skill\n---\nDo it.\n")
        _write(dc / "commands" / "probe.md", "Run the probe.\n")
        _write(dc / "settings.json", json.dumps({"model": "sonnet", "permissions": {}}, indent=2) + "\n")
        _write(dc / "hooks" / "not-shipped.sh", "#!/bin/bash\n")
        _write(r / ".gitignore", "tomo-tmp/\nevals/results/\n")
        lib = r / "evals" / "_lib"
        lib.mkdir(parents=True)
        shutil.copy(KIT_DIR / "stubs.sh", lib / "stubs.sh")
        shutil.copy(KIT_DIR / "no-leak.md", lib / "no-leak.md")
        case = r / "evals" / "probe-case"
        _write(case / "case.yaml", 'schema_version: "1.1"\nname: probe-case\nruns: 3\n'
               "context:\n  scaffold_script: scaffold.sh\n")
        _write(case / "scaffold.sh", '#!/bin/bash\nset -e\nAUDIT_RESULT=ok\n'
               '. "$(dirname "$0")/../_lib/stubs.sh"\nstage_instance\n')
        _write(case / "graders" / "1-probe.md", "---\ntype: regex\ntarget: last_message\npattern: ok\n---\n")
        shutil.copy(KIT_DIR / "no-leak.md", case / "graders" / "9-no-leak.md")
        _write(r / "evals" / "_mutations" / "flip.patch", FLIP_PATCH)
        _write(r / "evals" / "_mutations" / "stale.patch", STALE_PATCH)
        _write(r / "evals" / "results" / "old" / "aggregate-result.json", "{}\n")
        _git(r.parent, "init", "--quiet", str(r))
        _git(r, "config", "user.name", "Test")
        _git(r, "config", "user.email", "test@example.invalid")
        _git(r, "config", "commit.gpgsign", "false")
        _git(r, "add", ".")
        _git(r, "commit", "--quiet", "--no-verify", "--message", "fixture")

    def run(self, *args: str, expect_tree_change: bool = False, **env: str | None):
        e = dict(self.env)
        for k, v in env.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        before = _tree_state(self.repo)
        home_before = _dir_state(self.home / ".tomo")
        proc = subprocess.run(["bash", str(RUNNER), *args], env=e, capture_output=True, text=True,
                              cwd=self.tmp, timeout=60)
        if not expect_tree_change:
            assert _tree_state(self.repo) == before, "runner changed the repo"
        assert _dir_state(self.home / ".tomo") == home_before, "runner changed HOME/.tomo"
        return proc

    def calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [json.loads(ln) for ln in self.log.read_text().splitlines()]

    def eval_calls(self) -> list[list[str]]:
        return [c for c in self.calls() if c[:2] == ["plugin", "eval"]]

    def flag(self, call: list[str], name: str) -> str:
        return call[call.index(name) + 1]

    def plugin_path(self) -> Path:
        return Path((self.tmp / "snapshot.path").read_text())


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def _line(proc) -> str:
    lines = proc.stdout.strip().splitlines()
    assert len(lines) == 1, proc.stdout + proc.stderr
    return lines[0]


# ── the gate call ─────────────────────────────────────────────


def test_default_run_passes_fixed_flags_and_three_outputs(env):
    proc = env.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _line(proc).startswith("GREEN 2/2 cases")
    (call,) = env.eval_calls()
    for flag, value in (("--ablation", "none"), ("--threshold", "1.0"), ("--runs", "3"), ("-j", "2"),
                        ("--allow-tools", "Bash"), ("--model", "sonnet"), ("--max-cost-usd", "5")):
        assert env.flag(call, flag) == value, flag
    for flag in ("--no-publish", "--trust-plugin", "--scaffold"):
        assert flag in call
    assert "--case" not in call and "--keep-temp" not in call
    out = Path(env.flag(call, "--output-dir"))
    assert out.parent == env.repo / "tomo-tmp" / "evals"
    assert env.flag(call, "--json") == str(out / "aggregate-result.json")
    assert env.flag(call, "--report") == str(out / "report.html")
    assert (out / "verdict.txt").read_text().strip() == _line(proc)


def test_model_follows_settings_json(env):
    s = env.repo / "tomo" / "dot_claude" / "settings.json"
    s.write_text(json.dumps({"model": "haiku"}) + "\n")
    proc = env.run()
    assert proc.returncode == 0, proc.stderr
    assert env.flag(env.eval_calls()[0], "--model") == "haiku"


def test_unreadable_settings_model_is_refused(env):
    (env.repo / "tomo" / "dot_claude" / "settings.json").write_text("{not json\n")
    proc = env.run()
    assert proc.returncode == 3
    assert "settings.json" in proc.stderr
    assert env.eval_calls() == []


def test_snapshot_shape_and_agents_byte_identical(env):
    proc = env.run()
    assert proc.returncode == 0, proc.stderr
    snap = env.snap
    assert json.loads((snap / ".claude-plugin" / "plugin.json").read_text()) == {"name": "tomo"}
    src = env.repo / "tomo" / "dot_claude"
    for d in ("agents", "skills", "commands"):
        assert _dir_state(snap / d) == _dir_state(src / d), d
    assert _dir_state(snap / "evals") == {
        k: v for k, v in _dir_state(env.repo / "evals").items() if not k.startswith("results/")
    }
    assert not (snap / "evals" / "results").exists()
    assert sorted(p.name for p in snap.iterdir()) == [".claude-plugin", "agents", "commands", "evals", "skills"]


# ── temp dir lifecycle and CLI exit handling ──────────────────


@pytest.mark.parametrize("code,result,expected", [
    ("0", "green-3x.json", 0),
    ("1", "relay-red.json", 1),
    ("2", "cost-cap-partial.json", 2),
    ("130", "green-3x.json", 2),
    ("143", "green-3x.json", 2),
])
def test_temp_dir_removed_and_verdict_from_result(env, code, result, expected):
    proc = env.run(FAKE_EXIT=code, FAKE_RESULT=str(RESULTS / result))
    assert proc.returncode == expected, proc.stdout + proc.stderr
    assert not env.plugin_path().exists()
    assert list(env.tmpdir.iterdir()) == []
    line = _line(proc)
    word = {0: "GREEN", 1: "RED", 2: "NOT GRADED"}[expected]
    assert line.startswith(word)
    if code in ("130", "143"):
        assert "interrupted" in line


def test_cli_exit_2_without_result_is_not_graded(env):
    proc = env.run(FAKE_EXIT="2", FAKE_RESULT="")
    assert proc.returncode == 2
    assert _line(proc).startswith("NOT GRADED")
    assert list(env.tmpdir.iterdir()) == []


def test_cli_nonzero_with_green_result_is_never_green(env):
    proc = env.run(FAKE_EXIT="1", FAKE_RESULT=str(RESULTS / "green-3x.json"))
    assert proc.returncode == 2
    assert _line(proc).startswith("NOT GRADED")


def test_keep_temp_passes_through_and_keeps_copy(env):
    proc = env.run("--keep-temp")
    assert proc.returncode == 0, proc.stderr
    assert "--keep-temp" in env.eval_calls()[0]
    assert env.plugin_path().exists()


def test_scaffold_runs_from_the_assembled_copy(env):
    report = env.tmp / "scaffold-report.json"
    proc = env.run(FAKE_SCAFFOLD_CASE="probe-case", FAKE_SCAFFOLD_WS=str(env.tmp / "ws"),
                   FAKE_SCAFFOLD_REPORT=str(report))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    got = json.loads(report.read_text())
    assert got == {"rc": 0, "routing_plan": True, "run_id": True}, got


# ── RED proofs: --rev and --mutation ──────────────────────────


def test_rev_takes_runtime_dirs_from_commit_and_evals_from_worktree(env):
    old_sha = _git(env.repo, "rev-parse", "HEAD").strip()
    agent = env.repo / "tomo" / "dot_claude" / "agents" / "probe-agent.md"
    agent.write_text(AGENT_TEXT.replace("run the probe", "run the NEW probe"))
    _write(env.repo / "evals" / "probe-case" / "graders" / "2-new.md", "---\ntype: regex\n---\n")
    _git(env.repo, "add", ".")
    _git(env.repo, "commit", "--quiet", "--no-verify", "--message", "new")
    _write(env.repo / "evals" / "probe-case" / "graders" / "3-uncommitted.md", "x\n")
    proc = env.run("--rev", old_sha)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (env.snap / "agents" / "probe-agent.md").read_text() == AGENT_TEXT
    assert (env.snap / "evals" / "probe-case" / "graders" / "2-new.md").exists()
    assert (env.snap / "evals" / "probe-case" / "graders" / "3-uncommitted.md").exists()
    assert f"rev {old_sha[:12]}" in _line(proc)


def test_rev_symbolic_name_is_resolved_to_a_sha_in_the_verdict(env):
    head = _git(env.repo, "rev-parse", "--short=12", "HEAD").strip()
    proc = env.run("--rev", "HEAD")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    line = _line(proc)
    assert f"rev HEAD={head}" in line, line


def test_unknown_rev_is_refused(env):
    proc = env.run("--rev", "no-such-rev")
    assert proc.returncode == 3
    assert env.eval_calls() == []


def test_mutation_patches_snapshot_not_repo(env):
    proc = env.run("--mutation", "flip")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Step 1: MUTATED." in (env.snap / "agents" / "probe-agent.md").read_text()
    assert (env.repo / "tomo" / "dot_claude" / "agents" / "probe-agent.md").read_text() == AGENT_TEXT
    assert "mutation flip" in _line(proc)


def test_non_applying_mutation_is_refused_before_eval(env):
    proc = env.run("--mutation", "stale")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert env.eval_calls() == []
    assert list(env.tmpdir.iterdir()) == []


def test_unknown_mutation_is_refused(env):
    proc = env.run("--mutation", "nope")
    assert proc.returncode == 3
    assert env.calls() == []


# ── the repo never changes ────────────────────────────────────


def test_fake_writing_into_repo_is_not_graded_and_names_path(env):
    proc = env.run(FAKE_TOUCH="tomo/dot_claude/agents/leaked.md", expect_tree_change=True)
    assert proc.returncode == 2
    line = _line(proc)
    assert line.startswith("NOT GRADED")
    assert "tomo/dot_claude/agents/leaked.md" in line


def test_fake_modifying_already_dirty_file_is_detected(env):
    agent = env.repo / "tomo" / "dot_claude" / "agents" / "probe-agent.md"
    agent.write_text(AGENT_TEXT + "dirty before the run\n")
    proc = env.run(FAKE_TOUCH="tomo/dot_claude/agents/probe-agent.md", expect_tree_change=True)
    assert proc.returncode == 2
    assert "tomo/dot_claude/agents/probe-agent.md" in _line(proc)


def test_dirty_tree_is_reported_not_refused(env):
    _write(env.repo / "notes.txt", "untracked\n")
    proc = env.run()
    assert proc.returncode == 0, proc.stderr
    assert "tree dirty" in _line(proc)


def test_runner_leaves_every_tomo_instance_unchanged(env):
    """F1-AC2 for instances: the runner's own tree check skips gitignored paths, so
    this proves directly that neither a repo-local instance (gitignored, as in the
    real repo) nor a registered instance outside the repo changes. Falsified by a
    runner that writes into either."""
    with open(env.repo / ".gitignore", "a") as f:
        f.write("tomo-instance/\n")
    _git(env.repo, "commit", "--quiet", "--no-verify", "--all", "--message", "ignore instance")
    local = env.repo / "tomo-instance"
    outside = env.tmp / "elsewhere" / "tomo-registered"
    for inst in (local, outside):
        _write(inst / ".claude" / "agents" / "probe-agent.md", AGENT_TEXT)
        _write(inst / "config" / "vault-config.yaml", "inbox: Inbox\n")
    _write(env.home / ".tomo" / "instances.json",
           json.dumps({"instances": [{"name": "registered", "path": str(outside)}]}) + "\n")
    before = {inst: _dir_state(inst) for inst in (local, outside)}
    proc = env.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "tree clean" in _line(proc)
    for inst, state in before.items():
        assert _dir_state(inst) == state, f"runner changed the instance at {inst}"


def test_results_dir_is_a_utc_timestamp_named_in_the_verdict(env):
    """F1-AC3: results land in tomo-tmp/evals/<UTC timestamp>/ and the verdict line names it."""
    proc = env.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = Path(env.flag(env.eval_calls()[0], "--output-dir"))
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d-\d\d-\d\dZ(?:-\d+)?", out.name), out.name
    assert str(out) in _line(proc)


def test_results_location_not_gitignored_is_refused(env):
    """F1-AC3: the runner writes results only where git ignores them."""
    (env.repo / ".gitignore").write_text("evals/results/\n")
    _git(env.repo, "commit", "--quiet", "--no-verify", "--all", "--message", "unignore tomo-tmp")
    proc = env.run()
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "not gitignored" in proc.stderr
    assert env.calls() == []
    assert not (env.repo / "tomo-tmp").exists()


# ── preflight refusals (exit 3, nothing spent) ────────────────


def test_old_claude_version_refused_before_eval(env):
    proc = env.run(FAKE_VERSION="2.1.268 (Claude Code)")
    assert proc.returncode == 3
    assert "2.1.268" in proc.stderr
    assert "2.1.269" in proc.stderr  # F1-AC5: the refusal names the required version
    assert env.calls() == [["--version"]]


def test_unparseable_claude_version_refused(env):
    proc = env.run(FAKE_VERSION="garbage")
    assert proc.returncode == 3
    assert env.eval_calls() == []


def test_max_cost_flag_and_env_reach_cli_and_default_returns(env):
    assert env.run("--max-cost-usd", "9").returncode == 0
    assert env.run(EVAL_MAX_COST_USD="9").returncode == 0
    assert env.run().returncode == 0
    costs = [env.flag(c, "--max-cost-usd") for c in env.eval_calls()]
    assert costs == ["9", "9", "5"]


def test_cost_cap_verdict_names_the_cap_that_was_passed(env):
    proc = env.run("--max-cost-usd", "7", FAKE_RESULT=str(RESULTS / "cost-cap-partial.json"), FAKE_EXIT="2")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert _line(proc).startswith("NOT GRADED · cost cap $7 reached after 1 graded run ·"), _line(proc)


def test_invalid_max_cost_refused(env):
    proc = env.run("--max-cost-usd", "lots")
    assert proc.returncode == 3
    assert env.calls() == []


def test_unknown_case_refused_listing_cases(env):
    proc = env.run("--case", "nope*")
    assert proc.returncode == 3
    assert "probe-case" in proc.stderr
    assert env.calls() == []


def test_known_case_is_partial_suite(env):
    proc = env.run("--case", "probe-*")
    assert proc.returncode == 0, proc.stderr
    assert "PARTIAL SUITE" in _line(proc)
    assert env.flag(env.eval_calls()[0], "--case") == "probe-*"


def test_no_cases_refused(env):
    shutil.rmtree(env.repo / "evals" / "probe-case")
    proc = env.run()
    assert proc.returncode == 3
    assert env.calls() == []


@pytest.mark.parametrize("mangle", ["missing", "different"])
def test_case_without_identical_leak_guard_refused(env, mangle):
    g = env.repo / "evals" / "probe-case" / "graders" / "9-no-leak.md"
    if mangle == "missing":
        g.unlink()
    else:
        g.write_text(g.read_text() + "\n")
    proc = env.run()
    assert proc.returncode == 3
    assert "probe-case" in proc.stderr
    assert env.calls() == []


@pytest.mark.parametrize("bad", ["0", "00", "007", "-1", "x", "1.5"])
def test_invalid_runs_refused(env, bad):
    proc = env.run("--runs", bad, "--case", "probe-case")
    assert proc.returncode == 3
    assert env.calls() == []


def test_runs_without_case_mutation_or_rev_refused(env):
    proc = env.run("--runs", "1")
    assert proc.returncode == 3
    assert env.calls() == []


def test_runs_with_case_reaches_cli(env):
    proc = env.run("--runs", "1", "--case", "probe-case")
    assert proc.returncode == 0, proc.stderr
    assert env.flag(env.eval_calls()[0], "--runs") == "1"


def test_claude_bin_unset_under_pytest_refused(env):
    # The default binary ($HOME/.local/bin/claude) is a working fake too, so only the
    # guard — not a missing file — can keep it from being called.
    default = env.home / ".local" / "bin" / "claude"
    default.parent.mkdir(parents=True)
    shutil.copy(env.fake, default)
    default.chmod(0o755)
    proc = env.run(CLAUDE_BIN=None, PYTEST_CURRENT_TEST="test_run_evals.py::x")
    assert proc.returncode == 3
    assert "CLAUDE_BIN" in proc.stderr
    assert env.calls() == []


def test_unknown_option_refused(env):
    proc = env.run("--bogus")
    assert proc.returncode == 3
    assert env.calls() == []


def test_help_documents_contract(env):
    proc = env.run("--help")
    assert proc.returncode == 0
    h = proc.stdout
    for needle in ("--runs", "--max-cost-usd", "EVAL_MAX_COST_USD", "tomo-tmp/evals/", "sandbox",
                   "0  GREEN", "1  RED", "2  NOT GRADED", "3  REFUSED", "CLAUDE_BIN",
                   "Typical cost: about $0.50", "hard cap $5"):
        assert needle in h, needle
    assert env.calls() == []


# ── unexpected-failure mapping, cleanup guard, verdict-script failure ──


def _shim(env: "Env", name: str, body: str) -> str:
    """Write an executable `name` into a bin dir; return a PATH with that dir first."""
    d = env.tmp / "shims"
    _write(d / name, "#!/bin/bash\n" + body)
    (d / name).chmod(0o755)
    return f"{d}:{env.env['PATH']}"


def _failing_hash_object_shim(env: "Env", fail_from: int) -> str:
    """git shim: delegates to the real git, but `hash-object` calls number >= fail_from exit 1."""
    real_git = shutil.which("git")
    counter = env.tmp / "hash-object.count"
    return _shim(env, "git", f'''
for a in "$@"; do
    if [ "$a" = hash-object ]; then
        n=$(cat "{counter}" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "{counter}"
        [ "$n" -ge {fail_from} ] && exit 1
        break
    fi
done
exec "{real_git}" "$@"
''')


def test_stray_failure_before_cli_is_refused(env):
    proc = env.run(PATH=_failing_hash_object_shim(env, 1))
    assert proc.returncode == 3
    assert "REFUSED · runner error" in proc.stderr
    assert env.eval_calls() == []


def test_stray_failure_after_cli_is_not_graded(env):
    proc = env.run(PATH=_failing_hash_object_shim(env, 2))
    assert proc.returncode == 2
    assert _line(proc).startswith("NOT GRADED")
    assert len(env.eval_calls()) == 1


def test_cleanup_refuses_to_remove_a_path_it_did_not_create(env):
    victim = env.tmp / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("precious\n")
    path = _shim(env, "mktemp", f'echo "{victim}"\n')
    proc = env.run(PATH=path)
    assert (victim / "keep.txt").read_text() == "precious\n"
    assert "refusing to remove unexpected path" in proc.stderr


def test_verdict_script_failure_is_not_graded_with_one_line(env):
    real_py = shutil.which("python3")
    path = _shim(env, "python3", f'''
for a in "$@"; do
    case "$a" in *eval_verdict.py) exit 127 ;; esac
done
exec "{real_py}" "$@"
''')
    proc = env.run(PATH=path)
    assert proc.returncode == 2
    assert _line(proc).startswith("NOT GRADED · verdict script failed (exit 127)")


def test_rev_and_mutation_together_refused(env):
    proc = env.run("--rev", "HEAD", "--mutation", "flip")
    assert proc.returncode == 3
    assert env.calls() == []

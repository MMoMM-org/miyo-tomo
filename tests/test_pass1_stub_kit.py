"""Tests for the Pass 1 stub kit evals/_lib/pass1-stubs.sh (spec 043, T1.2).

The kit is sourced the way a case scaffold sources it: from a scaffold.sh in
an assembled plugin copy laid out under tmp_path, with cwd = a separate
workspace. The stubs are then called with the argv suggest-handling passes.
Nothing writes into the repo or into ~/.tomo; one test proves that.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from jsonschema import validate

REPO = Path(__file__).resolve().parent.parent
KIT = REPO / "evals" / "_lib" / "pass1-stubs.sh"
SCRIPTS = REPO / "tomo" / "scripts"

RUN_ID = "2026-10-30T00-00-00Z-c0ffee"
PATHS = ["100 Inbox/Alpha.md", "100 Inbox/Places/Dresden.md", "100 Inbox/Gamma.md"]
SCRIPT_STUBS = (
    "inbox-triage",
    "read-routing-plan",
    "read-config-field",
    "run-id",
    "shared-ctx-builder",
    "analyst-stub",
    "suggestions-reducer",
    "suggestions-render",
    "kado-write-file",
    "mark-captured",
)
WARN_LINE = (
    "WARN: 2 active tracker field(s) have no keywords; matching falls back to "
    "guesswork and cannot suppress false positives: mood, sleep. Run /tomo-setup "
    "trackers to fill them, or set active: false on the ones you do not use."
)
CONDUCTOR_TEXT = "FAKE CONDUCTOR from the assembled copy\n"
COMBOS = list(itertools.product((0, 1), (0, 1)))

# The argv suggest-handling passes, step by step (SKILL.md steps 1-6).
SHARED_CTX_ARGV = (
    "--cache", "config/discovery-cache.yaml", "--vault-config",
    "config/vault-config.yaml", "--profiles-dir", "profiles", "--run-id", RUN_ID,
    "--output", "tomo-tmp/shared-ctx.json",
)
REDUCER_ARGV = (
    "--run-id", RUN_ID, "--profile", "miyo", "--output", "tomo-tmp/suggestions-doc.json",
)
RENDER_ARGV = (
    "--input", "tomo-tmp/suggestions-doc.json", "--output",
    "tomo-tmp/suggestions-rendered.md", "--json-output", "tomo-tmp/suggestions-wire.json",
)


def _real_to_filename():
    spec = importlib.util.spec_from_file_location("item_key", SCRIPTS / "lib" / "item_key.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.to_filename


to_filename = _real_to_filename()


def plugin_copy(tmp_path: Path) -> Path:
    """An assembled plugin laid out like run-evals.sh builds it."""
    plugin = tmp_path / "plugin"
    (plugin / "agents").mkdir(parents=True)
    (plugin / "agents" / "suggestion-conductor.md").write_text(CONDUCTOR_TEXT)
    (plugin / "evals" / "_lib").mkdir(parents=True)
    shutil.copy(KIT, plugin / "evals" / "_lib" / "pass1-stubs.sh")
    (plugin / "evals" / "case").mkdir()
    return plugin


def stage(tmp_path: Path, warn="0", dups="0", check=True) -> tuple[Path, subprocess.CompletedProcess]:
    plugin = plugin_copy(tmp_path)
    scaffold = plugin / "evals" / "case" / "scaffold.sh"
    scaffold.write_text(
        "#!/bin/bash\nset -e\n"
        f"SHARED_CTX_WARN={warn}\nDUPLICATES={dups}\n"
        '. "$(dirname "$0")/../_lib/pass1-stubs.sh"\n'
        "stage_pass1_instance\n"
    )
    ws = tmp_path / "ws"
    ws.mkdir()
    r = subprocess.run(
        ["/bin/bash", str(scaffold)], cwd=ws, capture_output=True, text=True, check=False,
    )
    if check:
        assert r.returncode == 0, r.stderr
    return ws, r


def run(ws: Path, name: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", f"scripts/{name}.py", *argv],
        cwd=ws, capture_output=True, text=True, check=False,
    )


def run_analysts(ws: Path) -> None:
    for p in PATHS:
        r = run(ws, "analyst-stub", p, p, RUN_ID)
        assert r.returncode == 0, r.stderr


def setup_steps(ws: Path) -> None:
    """suggest-handling steps 1-2 as the conductor runs them."""
    assert run(ws, "inbox-triage").returncode == 0
    assert run(ws, "read-routing-plan", "--field", "inbox_path").returncode == 0
    (ws / "tomo-tmp" / "items").mkdir(parents=True, exist_ok=True)
    assert run(ws, "run-id", "--out", "tomo-tmp/.run_id").returncode == 0
    assert run(ws, "shared-ctx-builder", *SHARED_CTX_ARGV).returncode == 0


def full_pipeline(ws: Path) -> dict[str, subprocess.CompletedProcess]:
    setup_steps(ws)
    run_analysts(ws)
    out = {
        "reducer": run(ws, "suggestions-reducer", *REDUCER_ARGV),
        "render": run(ws, "suggestions-render", *RENDER_ARGV),
        "write_md": run(
            ws, "kado-write-file", "--local", "tomo-tmp/suggestions-rendered.md",
            "--vault", "100 Inbox/2026-10-30_0000_suggestions.md",
        ),
        "write_json": run(
            ws, "kado-write-file", "--local", "tomo-tmp/suggestions-wire.json",
            "--vault", "100 Inbox/2026-10-30_0000_suggestions.json",
        ),
        "mark": run(
            ws, "mark-captured", "--state", "tomo-tmp/inbox-state.jsonl", "--run-id", RUN_ID,
        ),
    }
    for name, r in out.items():
        assert r.returncode == 0, f"{name}: {r.stderr}"
    return out


# --- staging -----------------------------------------------------------------


@pytest.mark.parametrize("warn,dups", COMBOS)
def test_stage_writes_documented_files(tmp_path, warn, dups):
    ws, _ = stage(tmp_path, warn, dups)
    for name in SCRIPT_STUBS:
        assert (ws / "scripts" / f"{name}.py").is_file(), name
    for rel in (
        "config/vault-config.yaml",
        "config/discovery-cache.yaml",
        "profiles/miyo.yaml",
    ):
        assert (ws / rel).is_file(), rel


def test_conductor_staged_from_assembled_copy(tmp_path):
    ws, _ = stage(tmp_path)
    staged = ws / ".claude" / "agents" / "suggestion-conductor.md"
    assert staged.read_text() == CONDUCTOR_TEXT


@pytest.mark.parametrize(
    "warn,dups,var",
    [("2", "0", "SHARED_CTX_WARN"), ("yes", "0", "SHARED_CTX_WARN"),
     ("0", "2", "DUPLICATES"), ("0", "", "DUPLICATES"), ("", "0", "SHARED_CTX_WARN")],
)
def test_invalid_variable_returns_1(tmp_path, warn, dups, var):
    ws, r = stage(tmp_path, warn, dups, check=False)
    assert r.returncode == 1
    assert var in r.stderr
    assert not (ws / "scripts").exists()


def test_invalid_variable_is_return_not_exit(tmp_path):
    """Sourced without set -e, the caller keeps running: the kit returns 1."""
    plugin = plugin_copy(tmp_path)
    scaffold = plugin / "evals" / "case" / "scaffold.sh"
    scaffold.write_text(
        "SHARED_CTX_WARN=9\nDUPLICATES=0\n"
        '. "$(dirname "$0")/../_lib/pass1-stubs.sh"\n'
        "stage_pass1_instance\necho rc=$?\n"
    )
    ws = tmp_path / "ws"
    ws.mkdir()
    r = subprocess.run(["/bin/bash", str(scaffold)], cwd=ws, capture_output=True, text=True)
    assert r.stdout.strip() == "rc=1"


# --- setup stubs ----------------------------------------------------------------


def test_triage_writes_routing_plan(tmp_path):
    ws, _ = stage(tmp_path)
    r = run(ws, "inbox-triage")
    assert r.returncode == 0
    assert r.stderr.startswith("[inbox-triage] suggest in ")
    assert "md=3 audio=0 new=3 to_process=3" in r.stderr
    plan = json.loads((ws / "tomo-tmp" / "routing-plan.json").read_text())
    assert plan["action"] == "suggest"
    assert plan["inbox_path"] == "100 Inbox/"
    assert [s["path"] for s in plan["fresh_sources"]] == PATHS
    assert plan["drift_indicators"] == []
    validate(plan, json.loads((REPO / "tomo" / "schemas" / "routing-plan.schema.json").read_text()))


def test_read_routing_plan_modes(tmp_path):
    ws, _ = stage(tmp_path)
    run(ws, "inbox-triage")
    assert run(ws, "read-routing-plan", "--field", "inbox_path").stdout == "100 Inbox\n"
    assert run(ws, "read-routing-plan", "--field", "action").stdout == "suggest\n"
    assert run(ws, "read-routing-plan", "--batch-count", "--size", "2").stdout == "2\n"
    assert run(ws, "read-routing-plan", "--sources", "--batch", "1", "--size", "2").stdout == (
        "100 Inbox/Alpha.md\n100 Inbox/Places/Dresden.md\n"
    )
    assert run(ws, "read-routing-plan", "--sources", "--batch", "2", "--size", "2").stdout == (
        "100 Inbox/Gamma.md\n"
    )
    r = run(ws, "read-routing-plan", "--sources", "--batch", "3", "--size", "2")
    assert r.returncode == 1
    assert "read-routing-plan: --batch 3 out of range (1..2)" in r.stderr
    r = run(ws, "read-routing-plan", "--field", "nope")
    assert r.returncode == 1
    assert "read-routing-plan: no such field: nope" in r.stderr


def test_read_config_field(tmp_path):
    ws, _ = stage(tmp_path)
    r = run(ws, "read-config-field", "--field", "tomo.suggestions.parallel", "--default", "5")
    assert r.stdout == "2\n"
    assert run(ws, "read-config-field", "--field", "profile", "--default", "miyo").stdout == "miyo\n"


def test_run_id_stub(tmp_path):
    ws, _ = stage(tmp_path)
    (ws / "tomo-tmp").mkdir(exist_ok=True)
    r = run(ws, "run-id", "--out", "tomo-tmp/.run_id")
    assert r.stdout == RUN_ID + "\n"
    assert (ws / "tomo-tmp" / ".run_id").read_text() == RUN_ID + "\n"


@pytest.mark.parametrize("warn", ["0", "1"])
def test_shared_ctx_builder_warn_line(tmp_path, warn):
    ws, _ = stage(tmp_path, warn=warn)
    r = run(ws, "shared-ctx-builder", *SHARED_CTX_ARGV)
    assert r.returncode == 0
    err = r.stderr.splitlines()
    assert (WARN_LINE in err) == (warn == "1")
    assert sum(1 for x in err if x.startswith("WARN:")) == int(warn)
    assert err[-1].startswith("mocs_total=")
    assert err[-1].endswith("run_id=" + RUN_ID)
    assert r.stdout == ""
    ctx = json.loads((ws / "tomo-tmp" / "shared-ctx.json").read_text())
    assert isinstance(ctx["mocs"], list) and ctx["mocs"]
    assert ctx["run_id"] == RUN_ID


# --- analyst stand-in -------------------------------------------------------------


def test_analyst_stub_writes_result_and_state(tmp_path):
    ws, _ = stage(tmp_path)
    setup_steps(ws)
    run_analysts(ws)
    items = ws / "tomo-tmp" / "items"
    assert sorted(p.name for p in items.iterdir()) == sorted(to_filename(p) for p in PATHS)
    for p in PATHS:
        res = json.loads((items / to_filename(p)).read_text())
        assert res["item_key"] == p
        assert res["path"] == p
        assert res["run_id"] == RUN_ID
        assert res["status"] == "done"
        assert isinstance(res["sections"], list) and res["sections"]
    lines = [json.loads(x) for x in (ws / "tomo-tmp" / "inbox-state.jsonl").read_text().splitlines()]
    assert [x["item_key"] for x in lines] == PATHS
    assert all(x["run_id"] == RUN_ID and x["status"] == "done" for x in lines)


def test_analyst_stub_filename_matches_real_to_filename_on_odd_keys(tmp_path):
    ws, _ = stage(tmp_path)
    (ws / "tomo-tmp" / "items").mkdir(parents=True)
    key = '100 Inbox/Sub Dir/Ähm: "Odd" Name With A Very Long Title Indeed.v2.md'
    assert run(ws, "analyst-stub", key, key, RUN_ID).returncode == 0
    assert (ws / "tomo-tmp" / "items" / to_filename(key)).is_file()


# --- reducer --------------------------------------------------------------------


@pytest.mark.parametrize("warn,dups", COMBOS)
def test_reducer_doc_matches_summary_line(tmp_path, warn, dups):
    ws, _ = stage(tmp_path, warn, dups)
    out = full_pipeline(ws)
    doc = json.loads((ws / "tomo-tmp" / "suggestions-doc.json").read_text())
    assert len(doc["sections"]) == 3
    assert [s["item_key"] for s in doc["sections"]] == PATHS
    assert len(doc["proposed_mocs"]) == int(dups) + 1
    assert doc["run_id"] == RUN_ID and doc["profile"] == "miyo"
    line = out["reducer"].stderr.strip().splitlines()[-1]
    assert line.startswith("suggestions-reducer: done=3 failed=0 unreadable_results=0 sections=3 ")
    assert f" duplicate_proposals_converted={dups} " in line
    assert f" proposed_mocs={int(dups) + 1} " in line
    assert line.endswith("out=tomo-tmp/suggestions-doc.json")


def test_reducer_fails_when_results_lag_state(tmp_path):
    ws, _ = stage(tmp_path)
    setup_steps(ws)
    run_analysts(ws)
    (ws / "tomo-tmp" / "items" / to_filename(PATHS[1])).unlink()
    r = run(ws, "suggestions-reducer", *REDUCER_ARGV)
    assert r.returncode == 2
    assert "stub suggestions-reducer:" in r.stderr
    assert not (ws / "tomo-tmp" / "suggestions-doc.json").exists()


# --- render, write, mark ---------------------------------------------------------


@pytest.mark.parametrize("warn,dups", COMBOS)
def test_render_output(tmp_path, warn, dups):
    ws, _ = stage(tmp_path, warn, dups)
    out = full_pipeline(ws)
    md = (ws / "tomo-tmp" / "suggestions-rendered.md").read_text()
    assert len(md.encode("utf-8")) > 1024
    assert md.startswith("---\n")
    assert len(re.findall(r"^## ", md, re.M)) == 3
    assert len(re.findall(r"^### S0\d — ", md, re.M)) == 3
    assert len(re.findall(r"^### Proposed MOC: ", md, re.M)) == int(dups) + 1
    wire = json.loads((ws / "tomo-tmp" / "suggestions-wire.json").read_text())
    assert "schema_version" in wire
    assert len(wire["suggestions"]) == 3
    assert len(wire["proposed_mocs"]) == int(dups) + 1
    assert out["render"].stderr.strip() == (
        f"suggestions-render: sections=3 daily=0 tag_handler=0 mocs={int(dups) + 1} "
        "out=tomo-tmp/suggestions-rendered.md"
    )


def test_kado_write_and_mark_captured_lines(tmp_path):
    ws, _ = stage(tmp_path)
    out = full_pipeline(ws)
    md_size = (ws / "tomo-tmp" / "suggestions-rendered.md").stat().st_size
    assert out["write_md"].stderr.strip() == (
        f"kado-write-file: tomo-tmp/suggestions-rendered.md ({md_size} bytes, op=note) "
        "→ 100 Inbox/2026-10-30_0000_suggestions.md"
    )
    assert "op=file) → 100 Inbox/2026-10-30_0000_suggestions.json" in out["write_json"].stderr
    assert out["mark"].stderr.strip().splitlines()[-1] == (
        "mark-captured: marked=3 errors=0 declined=0 skipped_non_md=0 squelched=0"
    )


def test_calls_log_records_every_call(tmp_path):
    ws, _ = stage(tmp_path)
    full_pipeline(ws)
    log = (ws / "tomo-tmp" / "calls.log").read_text().splitlines()
    assert log[0] == "inbox-triage.py "
    assert f"analyst-stub.py {PATHS[1]} {PATHS[1]} {RUN_ID}" in log
    assert log[-1] == f"mark-captured.py --state tomo-tmp/inbox-state.jsonl --run-id {RUN_ID}"


# --- strictness -------------------------------------------------------------------

GOOD_ARGV = {
    "inbox-triage": (),
    "read-routing-plan": ("--field", "inbox_path"),
    "read-config-field": ("--field", "profile", "--default", "miyo"),
    "run-id": ("--out", "tomo-tmp/.run_id"),
    "shared-ctx-builder": SHARED_CTX_ARGV,
    "analyst-stub": (PATHS[0], PATHS[0], RUN_ID),
    "suggestions-reducer": REDUCER_ARGV,
    "suggestions-render": RENDER_ARGV,
    "kado-write-file": ("--local", "tomo-tmp/suggestions-rendered.md", "--vault", "x.md"),
    "mark-captured": ("--state", "tomo-tmp/inbox-state.jsonl", "--run-id", RUN_ID),
}

MISSING_REQUIRED = {
    "read-routing-plan": ("--sources", "--size", "2"),
    "read-config-field": ("--default", "5"),
    "run-id": (),
    "shared-ctx-builder": SHARED_CTX_ARGV[:-2],
    "analyst-stub": (PATHS[0], PATHS[0]),
    "suggestions-reducer": REDUCER_ARGV[:-2],
    "suggestions-render": RENDER_ARGV[:-2],
    "kado-write-file": ("--vault", "x.md"),
    "mark-captured": ("--state", "tomo-tmp/inbox-state.jsonl"),
}


@pytest.mark.parametrize("name", SCRIPT_STUBS)
def test_unknown_flag_exits_2(tmp_path, name):
    ws, _ = stage(tmp_path)
    r = run(ws, name, *GOOD_ARGV[name], "--bogus")
    assert r.returncode == 2
    assert f"stub {name}: unexpected argv:" in r.stderr


@pytest.mark.parametrize("name", sorted(MISSING_REQUIRED))
def test_missing_required_flag_exits_2(tmp_path, name):
    ws, _ = stage(tmp_path)
    r = run(ws, name, *MISSING_REQUIRED[name])
    assert r.returncode == 2
    assert f"stub {name}: unexpected argv:" in r.stderr


def test_read_routing_plan_rejects_unused_modes(tmp_path):
    ws, _ = stage(tmp_path)
    run(ws, "inbox-triage")
    for argv in (("--count",), ("--plan", "x.json", "--field", "action"),
                 ("--field", "action", "--batch-count")):
        r = run(ws, "read-routing-plan", *argv)
        assert r.returncode == 2, argv
        assert "stub read-routing-plan: unexpected argv:" in r.stderr


# --- containment --------------------------------------------------------------------

SKIP_DIRS = {".git", "venv", ".venv", "node_modules", "tomo-instance", "tomo-home",
             "tomo-privat", "__pycache__", ".pytest_cache", ".ruff_cache"}
KIT_OUTPUT_NAMES = {f"{n}.py" for n in SCRIPT_STUBS} | {
    "calls.log", "routing-plan.json", "routing-plan.fixture.json", ".run_id",
    "shared-ctx.json", "inbox-state.jsonl", "suggestions-doc.json",
    "suggestions-rendered.md", "suggestions-wire.json", "suggestion-conductor.md",
    "vault-config.yaml", "discovery-cache.yaml", "miyo.yaml",
} | {to_filename(p) for p in PATHS}


def _touched_since(root: Path, since: float) -> set[str]:
    hits = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f not in KIT_OUTPUT_NAMES:
                continue
            p = Path(dirpath) / f
            try:
                if p.stat().st_mtime >= since:
                    hits.add(str(p))
            except FileNotFoundError:
                continue
    return hits


def _tree_state(root: Path) -> dict[str, float]:
    if not root.exists():
        return {}
    return {str(p): p.stat().st_mtime for p in root.rglob("*")}


def test_nothing_written_outside_the_workspace(tmp_path):
    home_tomo = Path.home() / ".tomo"
    before_home = _tree_state(home_tomo)
    start = time.time() - 1
    ws, _ = stage(tmp_path, "1", "1")
    full_pipeline(ws)
    assert _tree_state(home_tomo) == before_home
    assert _touched_since(REPO, start) == set()


# --- format drift -------------------------------------------------------------------
# Each stub line above is copied from a real script. These fragments must still
# be in that script's source; a change to the real format turns this red, and
# the copy in pass1-stubs.sh (header lists file:line) must follow.
REAL_FRAGMENTS = {
    "inbox-triage.py": ['f"[inbox-triage] {action} in {total_ms}ms — "', 'f"new={len(state.new_sources)} "'],
    "read-routing-plan.py": ['value = value.rstrip("/")', 'out of range (1..{total})'],
    "read-config-field.py": ['print(f"ERROR: field not found: {args.field}"'],
    "shared-ctx-builder.py": [
        'f"WARN: {len(unusable)} active tracker field(s) have no keywords; "',
        'f"Run /tomo-setup trackers to fill them, or set active: false on the "',
        'f"[shared-ctx] reconcile: cache clean "', 'f"mocs_total={map_notes_total_before} "',
        'f"asset_folder={ctx[\'asset_folder\']} "', 'f"run_id={run_id}",',
    ],
    "suggestions-reducer.py": [
        'f"suggestions-reducer: done={len(done_items)} failed={len(failed_entries)} "',
        'f"duplicate_proposals_converted={duplicate_conversions} "',
        'f"proposed_mocs={len(proposed_mocs)} out={out_path}",',
    ],
    "suggestions-render.py": [
        'f"suggestions-render: sections={section_count} daily={daily_count} "',
        'f"tag_handler={th_count} mocs={moc_count} out={args.output}",',
        'lines = ["## Suggestions", ""]', 'lines = ["## Proposed MOCs", ""]',
        'f"### {sid} — {title}"', 'f"### Proposed MOC: {topic}"',
    ],
    "kado-write-file.py": ['f"kado-write-file: {source} ({len(data)} bytes, op={op}) → {args.vault}"'],
    "mark-captured.py": [
        'f"mark-captured: marked={marked} errors={errors} declined={declined} "',
        'f"skipped_non_md={skipped_non_md} squelched={squelched_total}",',
    ],
}


@pytest.mark.parametrize("script", sorted(REAL_FRAGMENTS))
def test_copied_formats_still_in_real_scripts(script):
    src = (SCRIPTS / script).read_text(encoding="utf-8")
    for frag in REAL_FRAGMENTS[script]:
        assert frag in src, f"{script}: {frag}"


def test_inline_to_filename_is_a_copy_of_the_real_one():
    real = (SCRIPTS / "lib" / "item_key.py").read_text(encoding="utf-8")
    kit = KIT.read_text(encoding="utf-8")
    for line in (
        "_FORBIDDEN_CHARS = frozenset('\\\\/:*?\"<>|\\x00')",
        'stem = re.sub(r"\\.[^.]+$", "", stem)',
        'stem = "".join("-" if c in _FORBIDDEN_CHARS or c.isspace() else c for c in stem)',
        'stem = stem.lower().strip("-") or "item"',
        'digest = hashlib.sha256(',
    ):
        assert line in real, line
        assert line in kit, line

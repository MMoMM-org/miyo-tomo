#!/usr/bin/env python3
# version: 0.1.0
"""test_measure_shared_ctx_reads.py — spec 040 T1.1: the transcript scanner
that makes the "zero MOC reads delivered as a preview" KPI measurable.

Fixtures are synthetic subagent transcripts shaped like real Claude Code
records: a Bash `tool_use` whose command runs read-shared-ctx.py, and the
matching `tool_result` record carrying `toolUseResult`. A spilled result has
`persistedOutputPath` / `persistedOutputSize` and content starting with
`<persisted-output>`; a delivered one has neither.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "measure-shared-ctx-reads.py"

NOTE_TEXT = "Ein Tag in Pirna, sehr privat"


def _load():
    spec = importlib.util.spec_from_file_location("measure_shared_ctx_reads", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dispatch(stem: str, run_id: str) -> dict:
    return {
        "type": "user",
        "message": {"role": "user", "content": f'stem = "{stem}"\nrun_id = "{run_id}"\n'},
    }


def _bash(use_id: str, command: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-5-5",
            "content": [{"type": "tool_use", "id": use_id, "name": "Bash", "input": {"command": command}}],
        },
    }


def _result(use_id: str, stdout: str, *, spilled_size: int | None = None) -> dict:
    tur = {"stdout": stdout, "stderr": "", "interrupted": False, "isImage": False}
    content = stdout
    if spilled_size is not None:
        tur["persistedOutputPath"] = "/home/coder/.claude/projects/x/tool-results/abc.txt"
        tur["persistedOutputSize"] = spilled_size
        content = "<persisted-output>\nOutput too large (39.8KB). Full output saved to: …\n\nPreview (first 2KB):\n" + stdout[:2048]
    return {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": use_id, "content": content}]},
        "toolUseResult": tur,
    }


def _write_session(tmp_path: Path, agents: dict[str, list[dict]]) -> Path:
    session = tmp_path / "proj" / "11111111-2222-3333-4444-555555555555.jsonl"
    sub = session.parent / session.stem / "subagents"
    sub.mkdir(parents=True)
    session.write_text("", encoding="utf-8")
    for name, records in agents.items():
        (sub / name).write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return session


def _fixture(tmp_path: Path) -> Path:
    mocs_json = json.dumps({"mocs": [{"path": "A.md", "title": NOTE_TEXT}]})
    return _write_session(tmp_path, {
        "agent-spilled.jsonl": [
            _dispatch("2026-10-01 pirna", "run-A"),
            _bash("u1", 'python3 scripts/read-shared-ctx.py --ctx "tomo-tmp/shared-ctx.json" --fields daily_notes,tag_prefixes'),
            _result("u1", '{"daily_notes":{}}'),
            _bash("u2", 'python3 scripts/read-shared-ctx.py --ctx "tomo-tmp/shared-ctx.json" --field mocs'),
            _result("u2", mocs_json, spilled_size=40705),
        ],
        "agent-whole.jsonl": [
            _dispatch("2026-10-02 other", "run-A"),
            _bash("v1", "python3 scripts/read-shared-ctx.py --run-id run-A --moc-names"),
            _result("v1", '["Vacation (MOC)"]'),
            _bash("v2", "python3 scripts/read-shared-ctx.py --run-id run-A --mocs-from tomo-tmp/items/x.moc-names.txt"),
            _result("v2", mocs_json),
            _bash("v3", "ls tomo-tmp"),
            _result("v3", "shared-ctx.json"),
        ],
        "agent-other-run.jsonl": [
            _dispatch("2026-09-30 old", "run-B"),
            _bash("w1", "python3 scripts/read-shared-ctx.py --field mocs"),
            _result("w1", mocs_json, spilled_size=50000),
        ],
    })


def test_scan_reports_mode_bytes_and_spill_per_read(tmp_path):
    mod = _load()
    session = _fixture(tmp_path)
    report = mod.scan_session(session, run_id="run-A")

    assert report["run_id"] == "run-A"
    by_agent = {a["agent"]: a for a in report["agents"]}
    assert set(by_agent) == {"agent-spilled.jsonl", "agent-whole.jsonl"}

    spilled = by_agent["agent-spilled.jsonl"]["reads"]
    assert [(r["mode"], r["target"], r["spilled"]) for r in spilled] == [
        ("--fields", "daily_notes,tag_prefixes", False),
        ("--field", "mocs", True),
    ]
    assert spilled[1]["bytes"] == 40705  # persistedOutputSize, not the preview length

    whole = by_agent["agent-whole.jsonl"]["reads"]
    assert [(r["mode"], r["spilled"]) for r in whole] == [("--moc-names", False), ("--mocs-from", False)]
    assert whole[0]["bytes"] == len('["Vacation (MOC)"]'.encode("utf-8"))

    assert report["summary"] == {"agents": 2, "reads": 4, "spilled": 1}


def test_default_run_is_the_most_common(tmp_path):
    mod = _load()
    report = mod.scan_session(_fixture(tmp_path), run_id=None)
    assert report["run_id"] == "run-A"


def test_text_output_never_contains_note_content(tmp_path):
    session = _fixture(tmp_path)
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--session", str(session), "--run-id", "run-A"],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert NOTE_TEXT not in out.stdout
    assert "2026-10-01 pirna" not in out.stdout  # stems are note-derived too
    assert "agent-spilled.jsonl" in out.stdout
    assert "spilled=1" in out.stdout


def test_json_output_includes_stems_for_the_gitignored_baseline(tmp_path):
    session = _fixture(tmp_path)
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--session", str(session), "--run-id", "run-A", "--json"],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert {a["stem"] for a in data["agents"]} == {"2026-10-01 pirna", "2026-10-02 other"}
    assert NOTE_TEXT not in out.stdout


def test_unknown_run_id_exits_1(tmp_path):
    session = _fixture(tmp_path)
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--session", str(session), "--run-id", "nope"],
        capture_output=True, text=True,
    )
    assert out.returncode == 1
    assert "No subagents matched run_id=nope" in out.stderr


def test_missing_subagents_dir_exits_1(tmp_path):
    session = tmp_path / "lonely.jsonl"
    session.write_text("", encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--session", str(session)],
        capture_output=True, text=True,
    )
    assert out.returncode == 1
    assert "No subagents/ directory" in out.stderr

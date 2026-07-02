#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_reducer_stale_run_filter.py — regression guard for #116.

`tomo-tmp/inbox-state.jsonl` is append-only and never truncated between runs.
Before the fix, suggestions-reducer selected its work-list from EVERY `done`
entry the state file had ever accumulated (no run_id filter), so a new run
re-read a prior run's `items/<stem>.result.json` and re-emitted proposals for
source notes that no longer exist — including self-referential MOC stubs.

This is the offline reproduction from the issue: a state file with two `done`
entries — one carrying an OLD run_id (stale), one the NEW run_id — plus matching
result.json for each. The reducer, invoked with --run-id <NEW>, must surface
ONLY the new-run stem.

Issue: https://github.com/MMoMM-org/miyo-tomo/issues/116
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REDUCER = REPO_ROOT / "tomo" / "scripts" / "suggestions-reducer.py"

_DEPS = "/tmp/claude/py_deps"
_SCRIPTS_DIR = str(REPO_ROOT / "tomo" / "scripts")
_extra = ":".join(p for p in [_DEPS, _SCRIPTS_DIR] if os.path.isdir(p))
_ENV = {
    **os.environ,
    "PYTHONPATH": _extra
    + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
}

OLD_RUN = "run-OLD-0001"
NEW_RUN = "run-NEW-0002"


def _minimal_shared_ctx(path: Path) -> None:
    path.write_text(json.dumps({
        "schema_version": "1",
        "run_id": NEW_RUN,
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
    }), encoding="utf-8")


def _write_state(path: Path, entries: list[tuple[str, str]]) -> None:
    """entries: list of (stem, run_id). All written as status=done."""
    lines = [
        json.dumps({
            "stem": stem,
            "path": f"100 Inbox/{stem}.md",
            "status": "done",
            "run_id": run_id,
            "ts": "2026-07-02T12:00:00Z",
        })
        for stem, run_id in entries
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_result(items_dir: Path, stem: str) -> None:
    action = {
        "kind": "create_atomic_note",
        "title": f"{stem} atomic",
        "template": "Atomic Note.md",
        "location": "Atlas/202 Notes/",
        "candidate_mocs": [],
        "tags": ["topic/test"],
        "summary": f"synthetic atomic for {stem}",
        "needs_new_moc": False,
        "proposed_moc_topic": None,
        "classification": {"category": "2600 - Applied Sciences", "confidence": 0.5},
        "tags_to_add": [],
    }
    (items_dir / f"{stem}.result.json").write_text(json.dumps({
        "schema_version": "1",
        "stem": stem,
        "path": f"100 Inbox/{stem}.md",
        "type": "fleeting_note",
        "type_confidence": 0.5,
        "force_atomic": False,
        "actions": [action],
        "candidate_mocs": [],
        "classification": {"category": "2600 - Applied Sciences", "confidence": 0.5},
        "needs_new_moc": False,
        "proposed_moc_topic": None,
        "tags_to_add": [],
        "atomic_note_worthiness": 0.2,
        "alternatives": [],
        "issues": [],
        "duration_ms": 0,
    }, ensure_ascii=False), encoding="utf-8")


def _run_reducer(tmp_path: Path) -> dict:
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    shared_ctx = tmp_path / "shared-ctx.json"
    state = tmp_path / "inbox-state.jsonl"
    output = tmp_path / "doc.json"
    _minimal_shared_ctx(shared_ctx)

    # StaleNote = prior run (its source note is gone); FreshNote = this run.
    _write_state(state, [("StaleNote", OLD_RUN), ("FreshNote", NEW_RUN)])
    _write_result(items_dir, "StaleNote")
    _write_result(items_dir, "FreshNote")

    result = subprocess.run(
        [
            sys.executable, str(REDUCER),
            "--state", str(state),
            "--items-dir", str(items_dir),
            "--run-id", NEW_RUN,
            "--profile", "miyo",
            "--shared-ctx", str(shared_ctx),
            "--no-kado",
            "--output", str(output),
        ],
        capture_output=True, text=True, check=False, env=_ENV,
    )
    assert result.returncode == 0, (
        f"reducer exit {result.returncode}; stderr:\n{result.stderr}"
    )
    return json.loads(output.read_text(encoding="utf-8"))


def test_reducer_ignores_stale_run_done_stems(tmp_path):
    """Only the current-run stem lands in the doc; the prior-run stem is dropped."""
    doc = _run_reducer(tmp_path)
    section_stems = [s["stem"] for s in doc.get("sections", [])]
    assert "FreshNote" in section_stems, (
        f"current-run stem missing from doc; got {section_stems}"
    )
    assert "StaleNote" not in section_stems, (
        f"stale prior-run stem leaked into the doc: {section_stems}"
    )
    assert section_stems == ["FreshNote"], section_stems

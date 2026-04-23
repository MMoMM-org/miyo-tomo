#!/usr/bin/env python3
# version: 0.1.0
"""Regression guard for XDD 012 — suggestions-reducer --fan-resolve.

Ensures the reducer's --fan-resolve flag:
(a) filters items to only those whose result.json has force_atomic=true,
(b) emits doc_variant="fan-resolve",
(c) drops daily_notes_updates, proposed_mocs, needs_attention,
(d) uses the Force-Atomic Resolve precedence note.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REDUCER = REPO_ROOT / "tomo" / "scripts" / "suggestions-reducer.py"


def _minimal_shared_ctx(path: Path) -> None:
    path.write_text(json.dumps({
        "schema_version": "1",
        "run_id": "test-run",
        "mocs": [],
        "tag_prefixes": [],
        "classification_keywords": {},
    }), encoding="utf-8")


def _write_state(path: Path, stems: list[str]) -> None:
    lines = []
    for stem in stems:
        lines.append(json.dumps({
            "stem": stem,
            "path": f"100 Inbox/{stem}.md",
            "status": "done",
            "run_id": "test-run",
            "ts": "2026-04-23T12:00:00Z",
        }))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_result(items_dir: Path, stem: str, force_atomic: bool) -> None:
    (items_dir / f"{stem}.result.json").write_text(json.dumps({
        "schema_version": "1",
        "stem": stem,
        "path": f"100 Inbox/{stem}.md",
        "type": "fleeting_note",
        "type_confidence": 0.5,
        "force_atomic": force_atomic,
        "actions": [
            {
                "kind": "create_atomic_note",
                "title": f"{stem} atomic",
                "template": "Atomic Note.md",
                "location": "Atlas/202 Notes/",
                "candidate_mocs": [],
                "tags": ["topic/test"],
                "summary": f"synthetic atomic for {stem}",
            }
        ],
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


def test_fan_resolve_filters_and_sets_variant(tmp_path):
    """Reducer with --fan-resolve keeps only force_atomic items, marks
    doc_variant, and empties aggregated blocks."""
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    shared_ctx = tmp_path / "shared-ctx.json"
    state = tmp_path / "state.jsonl"
    output = tmp_path / "doc.json"
    _minimal_shared_ctx(shared_ctx)

    # Two items: one forced, one normal. Only the forced one should land.
    _write_state(state, ["Furano", "Wingspan"])
    _write_result(items_dir, "Furano", force_atomic=True)
    _write_result(items_dir, "Wingspan", force_atomic=False)

    result = subprocess.run(
        [
            sys.executable, str(REDUCER),
            "--state", str(state),
            "--items-dir", str(items_dir),
            "--run-id", "test-run",
            "--profile", "miyo",
            "--shared-ctx", str(shared_ctx),
            "--fan-resolve",
            "--output", str(output),
        ],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        f"reducer exit {result.returncode}; stderr:\n{result.stderr}"
    )

    doc = json.loads(output.read_text(encoding="utf-8"))

    assert doc["doc_variant"] == "fan-resolve", doc.get("doc_variant")
    assert doc["daily_notes_updates"] == [], doc["daily_notes_updates"]
    assert doc["proposed_mocs"] == [], doc["proposed_mocs"]
    assert doc["needs_attention"] == [], doc["needs_attention"]
    assert "Force-Atomic Resolve" in doc["decision_precedence_note"], (
        doc["decision_precedence_note"]
    )
    # Only the forced item should appear in sections.
    section_stems = [s["stem"] for s in doc.get("sections", [])]
    assert section_stems == ["Furano"], (
        f"expected only Furano in fan-resolve; got {section_stems}"
    )


def test_primary_mode_unchanged_without_flag(tmp_path):
    """Sanity: --fan-resolve flag absent keeps doc_variant='primary'."""
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    shared_ctx = tmp_path / "shared-ctx.json"
    state = tmp_path / "state.jsonl"
    output = tmp_path / "doc.json"
    _minimal_shared_ctx(shared_ctx)
    _write_state(state, ["Wingspan"])
    _write_result(items_dir, "Wingspan", force_atomic=False)

    result = subprocess.run(
        [
            sys.executable, str(REDUCER),
            "--state", str(state),
            "--items-dir", str(items_dir),
            "--run-id", "test-run",
            "--profile", "miyo",
            "--shared-ctx", str(shared_ctx),
            "--output", str(output),
        ],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    doc = json.loads(output.read_text(encoding="utf-8"))
    assert doc.get("doc_variant") == "primary", doc.get("doc_variant")

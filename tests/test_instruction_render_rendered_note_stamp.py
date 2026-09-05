#!/usr/bin/env python3
# version: 0.1.1
"""test_instruction_render_rendered_note_stamp.py — #108 rendered-note stamping.

Verifies the render loop stamps a ``tomo: {doc_type: rendered-note,
state: pending-move}`` block onto every rendered staging note before it is
written, so inbox triage skips it as a fresh source until Hashi applies the
move_note/create_moc (Hashi strips the block on apply).

Tests:
  1. test_rendered_note_carries_pending_move_block — happy path: block inserted,
     note's own frontmatter preserved.
  2. test_stamp_failure_writes_note_unstamped — fail-safe: a note whose
     frontmatter cannot take the block is written unstamped, no crash.

Refs: issue #108; Hashi stripTomoFrontmatter (895c0ac).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "instruction-render.py"

sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location("instruction_render", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render"] = ir
_spec.loader.exec_module(ir)


def _one_note_suggestions() -> dict:
    return {
        "confirmed_items": [
            {
                "id": "item-1",
                "action": "create_note",
                "title": "My Rendered Note",
                "template": "templates/atomic.md",
                "source_path": "",
                "tags": [],
                "parent_moc": "",
                "parent_mocs": [],
                "destination": "200 Notes/",
                "summary": "",
            },
        ],
        "daily_updates": [],
        "skipped": [],
    }


def _stub_pipeline(monkeypatch, tmp_path, rendered_body: str):
    """Stub every dependency so main() exercises only the render+stamp+write path."""
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps(_one_note_suggestions()), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        ir, "load_config",
        lambda _path: {
            "concepts.inbox": "100 Inbox",
            "profile": "miyo",
            "callouts.editable": ["NOTE", "IDEAS"],
        },
    )
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(ir, "read_template", lambda _client, _ref: "# {{title}}\n")
    monkeypatch.setattr(
        ir, "render_via_script", lambda _tmpl, _tokens, _cfg: rendered_body,
    )
    # Isolate the render loop from vault-dependent downstream steps.
    monkeypatch.setattr(ir, "build_actions", lambda *_a, **_kw: ([], []))
    monkeypatch.setattr(ir, "resolve_target_moc_paths", lambda _actions, _client: 0)
    monkeypatch.setattr(ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _actions: [])
    monkeypatch.setattr(ir, "render_instructions_md", lambda *_a, **_kw: "")
    monkeypatch.setattr(ir, "backfill_supporting_items_parents", lambda _items: None)

    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys, "argv",
        [
            "instruction-render.py",
            "--suggestions", str(suggestions_file),
            "--output-dir", str(out_dir),
            "--config", str(cfg_file),
            "--run-id", "2026-07-01-094800-abc123",
        ],
    )
    return out_dir


def _rendered_file_text(out_dir: Path) -> str:
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest, "expected one rendered note in the manifest"
    return (out_dir / manifest[0]["rendered_file"]).read_text(encoding="utf-8")


def test_rendered_note_carries_pending_move_block(monkeypatch, tmp_path):
    """The written note gains the rendered-note/pending-move block; its own
    frontmatter is preserved."""
    body = "---\ntags: [topic/a]\n---\n# My Rendered Note\nbody\n"
    out_dir = _stub_pipeline(monkeypatch, tmp_path, body)

    rc = ir.main()
    assert isinstance(rc, int)

    text = _rendered_file_text(out_dir)
    assert "doc_type: rendered-note" in text
    assert "state: pending-move" in text
    assert "run_id: 2026-07-01-094800-abc123" in text
    # the note's own frontmatter survives
    assert "tags: [topic/a]" in text


def test_stamp_failure_writes_note_unstamped(monkeypatch, tmp_path):
    """A note that already carries a tomo: block cannot be re-stamped — it is
    written through unchanged rather than crashing the run (fail-safe)."""
    body = "---\ntomo:\n  doc_type: source\n  state: captured\n---\n# N\nbody\n"
    out_dir = _stub_pipeline(monkeypatch, tmp_path, body)

    rc = ir.main()
    assert isinstance(rc, int)

    text = _rendered_file_text(out_dir)
    # unchanged: no rendered-note marker was forced in
    assert "doc_type: rendered-note" not in text
    assert "state: pending-move" not in text
    assert "doc_type: source" in text

#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t2_skipped_assets_report_wiring.py — spec 031 T2.2/T2.4
code-quality follow-up: skipped attachments must reach the user, not just
stderr, and the two skip reasons (collision vs. no-basename) must read
differently in the rendered document.

Covers two gaps the review named:
  1. instruction-render.py's tomo_block["skipped_assets"] JSON construction
     had no test anywhere.
  2. The no-basename case had never been rendered — the only prior markdown
     test used a collision reason, so a shared, collision-only remedy text
     went unnoticed.

Stubs everything in main() except build_actions() (which is monkeypatched to
return a canned (actions, skipped) pair) and the file writes, so this proves
the JSON/MD wiring downstream of build_actions() without needing Phase 5's
real attachments-on-manifest plumbing.
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

_spec = importlib.util.spec_from_file_location("instruction_render_skipassets", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render_skipassets"] = ir
_spec.loader.exec_module(ir)

_SKIPPED = [
    {
        "source": "100 Inbox/Scans/karte.jpg",
        "destination": "Atlas/290 Assets/295 Attachments/karte.jpg",
        "reason": "destination collision: 'Scans/karte.jpg' also resolves to "
                  "'.../karte.jpg', already claimed by 'Images/karte.jpg'",
        "kind": "collision",
    },
    {
        "source": "100 Inbox/Images/",
        "destination": None,
        "reason": "attachment source path has no filename: '100 Inbox/Images/'",
        "kind": "no_basename",
    },
]

_MOVE_ASSET_ACTION = {
    "id": "I05",
    "action": "move_asset",
    "source": "100 Inbox/Images/karte.jpg",
    "destination": "Atlas/290 Assets/295 Attachments/karte.jpg",
}


def _empty_suggestions() -> dict:
    return {
        # One instruction-only item (no template) — just enough to clear
        # main()'s early "nothing to do" return; build_actions() is
        # monkeypatched below so its actual content doesn't matter.
        "confirmed_items": [{
            "id": "S01", "action": None, "title": "placeholder",
            "source_path": "", "tags": [], "parent_mocs": [], "candidate_mocs": [],
        }],
        "daily_updates": [],
        "skipped": [],
    }


def _run(monkeypatch, tmp_path) -> Path:
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps(_empty_suggestions()), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        ir, "load_config",
        lambda _path: {
            "concepts.inbox": "100 Inbox/",
            "profile": "miyo",
            "callouts.editable": ["NOTE"],
        },
    )
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(
        ir, "build_actions",
        lambda *_a, **_kw: ([dict(_MOVE_ASSET_ACTION)], [dict(s) for s in _SKIPPED]),
    )
    monkeypatch.setattr(ir, "resolve_target_moc_paths", lambda _actions, _client: 0)
    monkeypatch.setattr(ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _actions: [])

    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys, "argv",
        [
            "instruction-render.py",
            "--suggestions", str(suggestions_file),
            "--output-dir", str(out_dir),
            "--config", str(cfg_file),
        ],
    )
    rc = ir.main()
    assert isinstance(rc, int)
    return out_dir


def test_skipped_assets_populate_the_json_tomo_block(monkeypatch, tmp_path):
    out_dir = _run(monkeypatch, tmp_path)
    doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    entries = doc["tomo"]["skipped_assets"]
    assert len(entries) == 2
    by_source = {e["source"]: e for e in entries}
    assert by_source["100 Inbox/Scans/karte.jpg"]["destination"] == (
        "Atlas/290 Assets/295 Attachments/karte.jpg"
    )
    assert "collision" in by_source["100 Inbox/Scans/karte.jpg"]["reason"].lower()
    assert by_source["100 Inbox/Images/"]["destination"] is None
    assert "no filename" in by_source["100 Inbox/Images/"]["reason"].lower()


def test_collision_and_no_basename_render_with_different_remedies(monkeypatch, tmp_path):
    """The two skip kinds must read differently — a shared remedy text told a
    user with a malformed inbox entry to rename a file that does not exist."""
    out_dir = _run(monkeypatch, tmp_path)
    md = (out_dir / "instructions.md").read_text(encoding="utf-8")
    assert "## Skipped — un-appliable actions" in md

    collision_line = next(
        line for line in md.splitlines()
        if line.startswith("- `move_asset`") and "100 Inbox/Scans/karte.jpg" in line
    )
    no_basename_line = next(
        line for line in md.splitlines()
        if line.startswith("- `move_asset`") and "100 Inbox/Images/" in line
    )
    assert collision_line != no_basename_line
    assert "rename" in collision_line.lower()
    assert "rename" not in no_basename_line.lower()
    assert "no filename" in no_basename_line.lower() or "malformed" in no_basename_line.lower() \
        or "inbox entry" in no_basename_line.lower()

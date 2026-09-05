#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t3_5_manifest_entry_attachments.py — spec 031 T3.5 manifest entry.

instruction-render.py's per-item loop (:309-317) must read a confirmed
item's `attachments` field and carry it onto the manifest entry (:427-438),
so _build_move_asset_actions (T2.2) receives real data instead of always
seeing `m.get("attachments")` return None.

An instruction-only item (no template) is `continue`d before the manifest
entry is ever built (:314-316) — its attachments are dropped along with the
rest of it. This is deliberate, matching the PRD's out-of-scope note (an
item with no note move has nothing for an attachment to travel with), not a
bug to fix here.
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

_spec = importlib.util.spec_from_file_location("instruction_render_t35", SCRIPT_PATH)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["instruction_render_t35"] = ir
_spec.loader.exec_module(ir)


def _confirmed_item(**overrides) -> dict:
    item = {
        "id": "S01",
        "action": None,
        "title": "Dresden",
        "template": "templates/atomic.md",
        "source_path": "dresden.md",
        "tags": [],
        "parent_moc": "",
        "parent_mocs": [],
        "destination": "Atlas/202 Notes/",
        "summary": "",
    }
    item.update(overrides)
    return item


def _run(monkeypatch, tmp_path, confirmed_items: list[dict]) -> Path:
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(
        json.dumps({"confirmed_items": confirmed_items, "daily_updates": [], "skipped": []}),
        encoding="utf-8",
    )
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
    monkeypatch.setattr(ir, "read_template", lambda _client, _ref: "# {{title}}\n")
    monkeypatch.setattr(ir, "read_note_body", lambda *_a, **_kw: "")
    monkeypatch.setattr(ir, "render_via_script", lambda *_a, **_kw: "# Dresden\nbody\n")
    monkeypatch.setattr(ir, "build_actions", lambda *_a, **_kw: ([], []))
    monkeypatch.setattr(ir, "resolve_target_moc_paths", lambda _actions, _client: 0)
    monkeypatch.setattr(ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _actions: [])
    monkeypatch.setattr(ir, "render_instructions_md", lambda *_a, **_kw: "")

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


def _manifest(out_dir: Path) -> list[dict]:
    return json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))


def test_confirmed_items_attachments_reach_the_manifest_entry(monkeypatch, tmp_path):
    out_dir = _run(monkeypatch, tmp_path, [
        _confirmed_item(attachments=["100 Inbox/Images/karte.jpg"]),
    ])
    manifest = _manifest(out_dir)
    assert len(manifest) == 1
    assert manifest[0]["attachments"] == ["100 Inbox/Images/karte.jpg"]


def test_item_without_attachments_field_yields_empty_list(monkeypatch, tmp_path):
    """No 'attachments' key at all on the confirmed item — the manifest entry
    must still carry an empty list, not omit the field or carry None."""
    item = _confirmed_item()
    assert "attachments" not in item
    out_dir = _run(monkeypatch, tmp_path, [item])
    manifest = _manifest(out_dir)
    assert len(manifest) == 1
    assert manifest[0]["attachments"] == []


def test_instruction_only_item_produces_no_manifest_entry_attachments_dropped(monkeypatch, tmp_path):
    """An item with no template is `continue`d before the manifest entry is
    built at all — its attachments never reach the manifest. Deliberate
    (PRD out-of-scope: an item with no note move has nothing for an
    attachment to travel with), not something this task fixes."""
    item = _confirmed_item(template=None, attachments=["100 Inbox/Images/karte.jpg"])
    out_dir = _run(monkeypatch, tmp_path, [item])
    manifest = _manifest(out_dir)
    assert manifest == []

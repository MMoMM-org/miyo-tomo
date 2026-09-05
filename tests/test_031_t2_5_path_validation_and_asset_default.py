#!/usr/bin/env python3
# version: 0.1.0
"""test_031_t2_5_path_validation_and_asset_default.py — spec 031 T2.5.

Two independent gaps closed:
  1. `_REQUIRED_PATH_FIELDS` in lib/render_actions.py had no `move_asset`
     entry, so `_validate_action_paths` silently skipped the kind entirely —
     an empty source/destination on a move_asset action passed validation.
  2. `CONFIG_DEFAULTS` in instruction-render.py had no `concepts.asset` entry,
     so `cfg["concepts.asset"]` on a profile that omits the key raises
     KeyError instead of resolving to the documented default.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import _validate_action_paths  # noqa: E402

_ir_spec = importlib.util.spec_from_file_location(
    "instruction_render_t25", SCRIPTS_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_ir_spec)
assert _ir_spec.loader is not None
sys.modules["instruction_render_t25"] = ir
_ir_spec.loader.exec_module(ir)


def test_move_asset_with_empty_source_and_destination_is_rejected():
    """Proves the kind is no longer skipped — before this task,
    _REQUIRED_PATH_FIELDS.get("move_asset", ()) returned an empty tuple, so
    this action produced zero violations regardless of its content."""
    actions = [{"id": "I01", "action": "move_asset", "source": "", "destination": ""}]
    violations = _validate_action_paths(actions)
    assert any("source" in v for v in violations)
    assert any("destination" in v for v in violations)


def test_move_asset_with_well_shaped_paths_has_no_violations():
    actions = [{
        "id": "I01",
        "action": "move_asset",
        "source": "100 Inbox/Images/karte.jpg",
        "destination": "Atlas/290 Assets/295 Attachments/karte.jpg",
    }]
    assert _validate_action_paths(actions) == []


def test_concepts_asset_resolves_to_default_when_profile_omits_it(tmp_path):
    """A profile YAML that EXISTS but never mentions concepts.asset must not
    KeyError — load_config falls back to CONFIG_DEFAULTS like every other
    field. Uses a real file (not a missing path) so the merge loop actually
    runs, rather than the early "file doesn't exist" shortcut."""
    assert "concepts.asset" in ir.CONFIG_DEFAULTS
    config_path = tmp_path / "vault-config.yaml"
    config_path.write_text("concepts:\n  inbox: '100 Inbox/'\n")
    cfg = ir.load_config(str(config_path))
    assert cfg["concepts.asset"] == ir.CONFIG_DEFAULTS["concepts.asset"]

#!/usr/bin/env python3
# version: 0.1.1
"""test_031_t2_6_phase2_validation.py — spec 031 T2.6 Phase 2 validation.

End-to-end check that an instructions.json produced by build_actions() with a
move_asset action actually validates against the real
tomo/schemas/instructions.schema.json — not just that the schema declares the
shape correctly in isolation. Also pins schema_version and the ADR-6
no-deletion guarantee at the full-document level.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import build_actions  # noqa: E402
from lib.render_resolve import _strip_internal_link_fields  # noqa: E402

CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}


def _manifest_entry(*, source_path, rendered_file, attachments) -> dict:
    return {
        "id": "S01",
        "action": None,
        "title": "Dresden",
        "source_path": source_path,
        "rendered_file": rendered_file,
        "destination": "Atlas/202 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
        "attachments": attachments,
    }


def _confirmed_entry(*, source_path) -> dict:
    return {
        "id": "S01",
        "action": None,
        "title": "Dresden",
        "source_path": source_path,
        "parent_mocs": [],
        "tags": [],
        "candidate_mocs": [],
    }


def _instructions_envelope(actions: list[dict]) -> dict:
    return {
        "schema_version": "2",
        "type": "tomo-instructions",
        "generated": "2026-09-05T12:00:00Z",
        "profile": "miyo",
        "action_count": len(actions),
        "actions": actions,
    }


def test_move_asset_instruction_set_validates_against_the_schema():
    manifest = [_manifest_entry(
        source_path="dresden.md", rendered_file="2026-09-05_0900_dresden.md",
        attachments=["100 Inbox/Images/karte.jpg"],
    )]
    confirmed = [_confirmed_entry(source_path="dresden.md")]
    actions, _skipped_assets = build_actions(manifest, confirmed, [], [], CFG)
    assert any(a["action"] == "move_asset" for a in actions)
    # Mirrors the real pipeline: instruction-render.py strips Tomo-internal
    # fields (e.g. move_note.audio_peer) before writing/validating the wire doc.
    _strip_internal_link_fields(actions)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validate(instance=_instructions_envelope(actions), schema=schema)


def test_schema_version_is_unchanged():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"] == {"const": "2"}


def test_zero_delete_source_actions_reference_an_attachment_path():
    manifest = [_manifest_entry(
        source_path="dresden.md", rendered_file="2026-09-05_0900_dresden.md",
        attachments=["100 Inbox/Images/karte.jpg", "100 Inbox/Images/prag-karte.jpg"],
    )]
    confirmed = [_confirmed_entry(source_path="dresden.md")]
    actions, _skipped_assets = build_actions(manifest, confirmed, [], [], CFG)
    attachment_paths = {"100 Inbox/Images/karte.jpg", "100 Inbox/Images/prag-karte.jpg"}
    delete_sources = [a for a in actions if a["action"] == "delete_source"]
    assert delete_sources, "expected the origin's own delete_source to exist"
    assert not any(d["source_path"] in attachment_paths for d in delete_sources)

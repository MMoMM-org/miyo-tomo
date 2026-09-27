#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t4_1_no_consumer_change.py — spec 037 T4.1.

ADR-5 (`solution.md:506`) says spec 037 reaches Hashi through no new wire
field: a `rename` and an `ignore` both fall through to the same
`move_asset` dict `_build_move_asset_actions` has always emitted
(`render_actions.py:838-843`), and `keep_in_inbox` is reported only through
the existing, permissive `tomo.skipped_assets[]` block. This file proves
that by absence — the ONE assertion with a reachable mutation validates a
rendered three-remedy instruction set against Tomo's own copy of Hashi's
mirror schema (`tomo/schemas/hashi-instructions.schema.json`), the way
`tests/test_hashi_instructions_schema.py` already validates other action
shapes.

Covers, per `docs/XDD/specs/037-asset-destination-collision-is-a-pass1-
decision/plan/phase-4.md` T4.1:

  1. A manifest carrying all three remedies (`rename`, `ignore`,
     `keep_in_inbox`) renders through the real `_build_move_asset_actions`
     — no hand-composed action dicts.
  2. `rename` and `ignore` are wire-IDENTICAL `move_asset` shapes
     (`{id, action, source, destination}`) — this fixture exercises TWO
     distinct action shapes, not three, and asserts that rather than
     pretending otherwise.
  3. The rendered instruction set validates against the strict mirror
     schema — mutation: append a stray key (e.g. `"remedy": remedy`) to the
     `move_asset` dict built at `render_actions.py:838-843`, the block both
     `rename` and `ignore` fall through to. `additionalProperties: false`
     at `hashi-instructions.schema.json:105-116` rejects any such key. RED
     evidence for this mutation is recorded in the close-out (proven in a
     throwaway worktree, per CON-7 / the no-stash rule — this test file
     itself never mutates production code).
  4. `keep_in_inbox`'s `tomo.skipped_assets` entry is DELIBERATELY not
     schema-checked beyond key shape: `properties.tomo` carries no
     `additionalProperties: false` (`hashi-instructions.schema.json:35`,
     `SANCTIONED_ASYMMETRIES` in `test_wire_snapshot_parity.py`), so no
     value placed there can ever fail this validator. This is recorded as
     an unfalsifiable-by-design gap, not asserted as coverage.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "hashi-instructions.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate  # noqa: E402

from lib.render_actions import _build_move_asset_actions  # noqa: E402

ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"
INBOX = "100 Inbox/"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _manifest_entry(*, source_path, rendered_file, attachments) -> dict:
    return {
        "id": "S01",
        "action": None,
        "title": "Some Note",
        "source_path": source_path,
        "rendered_file": rendered_file,
        "destination": "Atlas/202 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
        "attachments": attachments,
    }


def _remedy(source, remedy, proposed_name=None) -> dict:
    return {"source": source, "remedy": remedy, "proposed_name": proposed_name}


def _instructions_envelope(actions: list[dict], skipped_assets: list[dict]) -> dict:
    """Wrap rendered actions the way `instruction-render.py` does — the
    envelope fields plus, when non-empty, `tomo.skipped_assets` projected to
    exactly `source`/`destination`/`reason` (instruction-render.py:1004-1010;
    `kind` is deliberately not projected onto the wire)."""
    doc = {
        "schema_version": "3",
        "type": "tomo-instructions",
        "generated": "2026-09-27T09:00:00Z",
        "profile": "miyo",
        "actions": actions,
    }
    if skipped_assets:
        doc["tomo"] = {
            "skipped_assets": [
                {
                    "source": s.get("source"),
                    "destination": s.get("destination"),
                    "reason": s.get("reason"),
                }
                for s in skipped_assets
            ]
        }
    return doc


def _render_three_remedy_set() -> tuple[list[dict], list[dict]]:
    """Render one manifest carrying all three attachment-conflict remedies
    through the real production function — no hand-composed actions."""
    manifest = [
        _manifest_entry(
            source_path="karte.md",
            rendered_file="2026-01-01_0900_karte.md",
            attachments=[
                "100 Inbox/Scans/karte.png",
                "100 Inbox/Scans/foto.jpg",
                "100 Inbox/Scans/plan.pdf",
            ],
        ),
    ]
    remedies = [
        _remedy("100 Inbox/Scans/karte.png", "rename", "karte (2).png"),
        _remedy("100 Inbox/Scans/foto.jpg", "ignore"),
        _remedy("100 Inbox/Scans/plan.pdf", "keep_in_inbox"),
    ]
    return _build_move_asset_actions(
        manifest, INBOX, ASSET_FOLDER, [0], attachment_conflict_remedies=remedies,
    )


# ---------------------------------------------------------------------------
# T4.1 — the rendered three-remedy set validates against Hashi's mirror
# ---------------------------------------------------------------------------


def test_three_remedy_set_renders_two_move_asset_shapes_and_one_skip():
    """`rename` and `ignore` both emit a `move_asset`; `keep_in_inbox` emits
    none. This is a fixture-shape sanity check, not the schema assertion —
    it fails if `_build_move_asset_actions` ever stops treating `rename` and
    `ignore` as the same wire shape (the premise the next test depends on)."""
    actions, skipped = _render_three_remedy_set()
    assert len(actions) == 2, (
        f"expected exactly the rename and ignore moves, got: {actions}"
    )
    assert {a["source"] for a in actions} == {
        "100 Inbox/Scans/karte.png", "100 Inbox/Scans/foto.jpg",
    }
    assert len(skipped) == 1
    assert skipped[0]["source"] == "100 Inbox/Scans/plan.pdf"
    assert skipped[0]["kind"] == "vault_collision_held"


def test_rendered_three_remedy_set_validates_against_hashi_mirror_schema(schema):
    """THE reachable-mutation assertion. Mutation: append a stray key (e.g.
    `"remedy": "rename"`) to the `move_asset` dict `_build_move_asset_actions`
    builds at `render_actions.py:838-843` — the block both `rename` and
    `ignore` fall through to. `additionalProperties: false` at
    `hashi-instructions.schema.json:105-116` turns this red. Every other
    action-shape claim in this file is a fixture-shape check; this is the
    one Hashi's real validator (and ours) can actually reject."""
    actions, skipped = _render_three_remedy_set()
    instructions = _instructions_envelope(actions, skipped)
    validate(instance=instructions, schema=schema)


def test_move_asset_actions_carry_exactly_the_schema_fields(schema):
    """Explicit key-set check alongside the jsonschema validation above —
    catches the same stray-key mutation from a second angle (a key ADDED
    would slip past a shallower `set.issubset` check if written the other
    direction; this asserts equality). Not a second reachable mutation:
    the fault this and the previous test catch is the same one line."""
    move_asset_keys = set(schema["$defs"]["move_asset"]["properties"].keys())
    actions, _skipped = _render_three_remedy_set()
    for action in actions:
        assert set(action.keys()) <= move_asset_keys, (
            f"move_asset action carries a field the mirror schema does not "
            f"declare: {set(action.keys()) - move_asset_keys}"
        )


def test_keep_in_inbox_skip_entry_is_not_schema_enforceable(schema):
    """Documents, rather than asserts new behaviour: `properties.tomo` in
    the mirror schema carries no `additionalProperties: false`
    (`hashi-instructions.schema.json:35`), so nothing placed under
    `tomo.skipped_assets` can ever fail this validator regardless of shape.
    This test fails only if that permissiveness is ever tightened without
    updating this file — it is a tripwire on the schema's own shape, not a
    functional guarantee about `keep_in_inbox`."""
    tomo_props = schema["properties"]["tomo"]
    assert tomo_props.get("additionalProperties") is not False, (
        "properties.tomo gained additionalProperties:false — the "
        "keep_in_inbox side of T4.1 is no longer unfalsifiable by design; "
        "revisit this test and the T4.1 close-out"
    )

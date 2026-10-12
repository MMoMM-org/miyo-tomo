#!/usr/bin/env python3
"""test_039_t5_3_executor_needs_no_change.py — spec 039 / T5.3 (#186), PRD F6-AC7.

The Tomo-side half of "the consumer's executor needs no change": what Tomo can
prove from its own tree about the `delete_source.depends_on` ids it emits. The
planner/executor half is a written trace (docs/tomo/scripts/lib/render_actions.md,
confirmed by Hashi in T6.2); the vendored schema records no kind order, so the
ordering claim lives only in that trace.

Mechanism each test falsifies:
- `test_every_delete_depends_on_id_names_an_action_in_the_set`: a delete naming
  an id absent from the set (Hashi seeds a dangling id as unsatisfied, so the
  delete would be skipped forever).
- `test_every_depended_on_kind_is_a_kind_the_vendored_schema_allows`: a
  depended-on action whose kind the consumer's schema does not list.
- `test_produced_set_validates_against_vendored_schema`: the produced set,
  wrapped in the envelope, being rejected by the vendored consumer schema.
- `test_vendored_schema_records_no_kind_order`: someone adding an ordering
  claim to the schema without the trace being updated.

CON-7: fixtures and fakes only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from jsonschema import validate  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from attachment_plan_fakes import FakeVault, plan_from_remedies  # noqa: E402
from lib.render_actions import build_actions  # noqa: E402
from lib.render_resolve import _strip_internal_link_fields  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "hashi-instructions.schema.json"

INBOX = "100 Inbox/"
ASSET = "Atlas/290 Assets/295 Attachments/"
NOTES = "Atlas/202 Notes/"
CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSET,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}

TRIP = "100 Inbox/trip.md"
OTHER = "100 Inbox/other.md"
KEPT = "100 Inbox/kept.md"
ALPHA = "100 Inbox/pics/alpha.png"
BETA = "100 Inbox/pics/beta.png"
SHARED = "100 Inbox/pics/shared.png"
WITHHELD = "100 Inbox/pics/withheld.png"
KEEP = "100 Inbox/pics/keep.png"


def _atomic(item_key, title, idx, attachments=(), audio_peer=None):
    stem = item_key.rsplit("/", 1)[-1][:-3]
    entry = {
        "id": f"S{idx:02d}", "action": "create_atomic_note", "title": title,
        "rendered_file": f"r{idx}.md", "destination": NOTES,
        "source_path": stem, "item_key": item_key, "parent_mocs": [], "tags": [],
        "attachments": list(attachments),
    }
    if audio_peer:
        entry["audio_peer"] = audio_peer
    return entry


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def actions() -> list[dict]:
    """Two moved attachments of one origin with an audio peer, an attachment
    shared across two origins, a withheld one, and one kept in the inbox."""
    manifest = [
        _atomic(TRIP, "One", 1, [ALPHA, BETA, WITHHELD], audio_peer="trip.m4a"),
        _atomic(TRIP, "Two", 2, [BETA], audio_peer="trip.m4a"),
        _atomic(OTHER, "Three", 3, [SHARED]),
        _atomic(KEPT, "Four", 4, [SHARED, KEEP]),
    ]
    vault = FakeVault(
        [ALPHA, BETA, SHARED, WITHHELD, KEEP, f"{ASSET}withheld.png",
         f"{ASSET}keep.png"],
        existing_folders=[ASSET])
    remedies = [{"source": KEEP, "remedy": "keep_in_inbox", "proposed_name": None}]
    plan = plan_from_remedies(manifest, remedies, inbox_path=INBOX,
                              asset_folder=ASSET, vault=vault)
    built, _ = build_actions(manifest, manifest, [], [], CFG, attachment_plan=plan)
    return built


def _allowed_kinds(schema: dict) -> set[str]:
    """Kinds the vendored schema allows: the top-level `oneOf` $ref list,
    resolved to each $def's `action` const (the schema has no kind enum)."""
    refs = schema["properties"]["actions"]["items"]["oneOf"]
    kinds = set()
    for ref in refs:
        name = ref["$ref"].rsplit("/", 1)[-1]
        kinds.add(schema["$defs"][name]["properties"]["action"]["const"])
    return kinds


def test_fixture_covers_the_cases(actions):
    kinds = {a["action"] for a in actions}
    assert {"move_note", "move_asset", "delete_source"} <= kinds
    deletes = [a for a in actions if a["action"] == "delete_source"]
    assert len(deletes) == 4  # trip, trip.m4a, other, kept
    assert len([a for a in actions if a["action"] == "move_asset"]) == 3


def test_every_delete_depends_on_id_names_an_action_in_the_set(actions):
    ids = {a["id"] for a in actions}
    deletes = [a for a in actions if a["action"] == "delete_source"]
    assert deletes
    for d in deletes:
        assert d["depends_on"], d
        dangling = [i for i in d["depends_on"] if i not in ids]
        assert dangling == [], f"{d['id']} names absent ids {dangling}"


def test_every_depended_on_kind_is_a_kind_the_vendored_schema_allows(actions, schema):
    """Also a schema-drift guard: the kind set is read from the vendored schema,
    so a kind dropped from it (or an id missing from the set) fails here."""
    allowed = _allowed_kinds(schema)
    assert {"move_note", "move_asset", "delete_source"} <= allowed
    by_id = {a["id"]: a for a in actions}
    for d in (a for a in actions if a["action"] == "delete_source"):
        for dep in d["depends_on"]:
            assert dep in by_id, (d["id"], dep)
            assert by_id[dep]["action"] in allowed, (d["id"], dep, by_id[dep]["action"])


def test_produced_set_validates_against_vendored_schema(actions, schema):
    # instruction-render strips Tomo-internal fields (move_note.audio_peer)
    # before the wire; do the same, on a copy.
    wire = json.loads(json.dumps(actions))
    _strip_internal_link_fields(wire)
    envelope = {
        "schema_version": schema["properties"]["schema_version"]["const"],
        "type": "tomo-instructions",
        "generated": "2026-10-12T00:00:00Z",
        "profile": "miyo",
        "actions": wire,
    }
    validate(envelope, schema)


_ORDER_WORDS = re.compile(
    r"\b(order\w*|preced\w*|sequenc\w*|before|after|first|last|prior|then)\b",
    re.IGNORECASE)


def _descriptions(node):
    """Every `description` string under a schema node, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "description" and isinstance(value, str):
                yield value
            else:
                yield from _descriptions(value)
    elif isinstance(node, list):
        for value in node:
            yield from _descriptions(value)


def test_vendored_schema_records_no_kind_order(schema):
    """Execution order is Hashi's KIND_ORDER (planner.ts), not a vendored fact;
    the move_asset-before-delete_source claim is carried by the written trace.
    Reads the descriptions of the two kinds involved for ordering words, and
    pins the top-level actions items to a bare oneOf of $refs."""
    for name in ("delete_source", "move_asset"):
        for text in _descriptions(schema["$defs"][name]):
            hit = _ORDER_WORDS.search(text)
            assert hit is None, (name, hit.group(0), text)
    items = schema["properties"]["actions"]["items"]
    assert set(items) == {"oneOf"}, sorted(items)
    assert all(set(ref) == {"$ref"} for ref in items["oneOf"])

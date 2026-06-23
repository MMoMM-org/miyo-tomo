#!/usr/bin/env python3
# version: 0.3.0
"""test_tag_handler_resolve.py — Behavioural tests for tag-handler-resolve.py.

Covers T1.3 (XDD 024 Phase 1): deterministic resolver — load registry, match
tags, bind capture segments, resolve target, reject deferred actions.

Spec: docs/XDD/specs/024-tag-handler-framework/solution.md §3-4
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import importlib.util

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load the hyphenated script as a module — matches the house pattern used by
# test_inbox_triage.py and test_suggestion_parser_moc_branch.py.
_RESOLVER_PATH = SCRIPTS_DIR / "tag-handler-resolve.py"
_resolver_spec = importlib.util.spec_from_file_location("tag_handler_resolve", _RESOLVER_PATH)
_resolver_mod = importlib.util.module_from_spec(_resolver_spec)
sys.modules["tag_handler_resolve"] = _resolver_mod
_resolver_spec.loader.exec_module(_resolver_mod)

load_registry = _resolver_mod.load_registry
resolve_item = _resolver_mod.resolve_item


# ---------------------------------------------------------------------------
# Fixture helpers — write minimal valid handler configs into tmp_path
# ---------------------------------------------------------------------------

def _write_handler(directory: Path, filename: str, config: dict) -> Path:
    """Write a handler config JSON into the given registry directory."""
    p = directory / filename
    p.write_text(json.dumps(config), encoding="utf-8")
    return p


def _tsukai_handler() -> dict:
    """Return the canonical tsukai handler from SDD §2."""
    return {
        "id": "tsukai",
        "enabled": True,
        "match": {
            "tag_prefix": "MiYo/Tsukai/",
            "capture_segments": ["repo"],
            "read_fields": ["category"],
        },
        "action": "insert_under_marker",
        "target": {
            "by": "repo",
            "map": {"Tomo": "Efforts/.../Tomo Dev Log.md"},
        },
        "marker": "## Captures",
        "placement": "inside",
        "compose": "Synthesize the batch captures into one dated status update.",
    }


# ---------------------------------------------------------------------------
# load_registry — empty / missing dir → zero handlers (AC-5)
# ---------------------------------------------------------------------------


def test_load_registry_missing_dir_returns_empty(tmp_path):
    """A missing registry directory yields zero handlers — no crash (AC-5)."""
    missing = tmp_path / "no-such-dir"
    handlers = load_registry(missing)
    assert handlers == []


def test_load_registry_empty_dir_returns_empty(tmp_path):
    """An empty registry directory yields zero handlers (AC-5)."""
    handlers = load_registry(tmp_path)
    assert handlers == []


def test_load_registry_loads_valid_handler(tmp_path):
    """A valid handler JSON is loaded and returned."""
    _write_handler(tmp_path, "tsukai.json", _tsukai_handler())
    handlers = load_registry(tmp_path)
    assert len(handlers) == 1
    assert handlers[0]["id"] == "tsukai"


# ---------------------------------------------------------------------------
# T1: test_match — tag matched → correct output shape
# ---------------------------------------------------------------------------


def test_match_returns_resolution(tmp_path):
    """Matching tag prefix produces a resolution with all SDD §3 output fields."""
    _write_handler(tmp_path, "tsukai.json", _tsukai_handler())
    registry = load_registry(tmp_path)

    item = {
        "path": "100 Inbox/capture.md",
        "tags": ["MiYo/Tsukai/Tomo"],
        "frontmatter": {"category": "feature"},
    }
    result = resolve_item(item, registry)

    assert result is not None
    assert result["handler"] == "tsukai"
    assert result["vars"] == {"repo": "Tomo"}
    assert result["fields"] == {"category": "feature"}
    assert result["target_path"] == "Efforts/.../Tomo Dev Log.md"
    assert result["marker"] == "## Captures"
    assert result["action"] == "insert_under_marker"
    assert result["placement"] == "inside"
    assert result["compose"] == "Synthesize the batch captures into one dated status update."


# ---------------------------------------------------------------------------
# T2: test_no_match — no matching handler → None
# ---------------------------------------------------------------------------


def test_no_match_returns_none(tmp_path):
    """No matching handler → resolve_item returns None."""
    _write_handler(tmp_path, "tsukai.json", _tsukai_handler())
    registry = load_registry(tmp_path)

    item = {
        "path": "100 Inbox/other.md",
        "tags": ["SomeOtherTag/Unrelated"],
        "frontmatter": {},
    }
    result = resolve_item(item, registry)
    assert result is None


def test_no_match_empty_tags_returns_none(tmp_path):
    """No tags at all → resolve_item returns None."""
    _write_handler(tmp_path, "tsukai.json", _tsukai_handler())
    registry = load_registry(tmp_path)

    item = {"path": "100 Inbox/empty.md", "tags": [], "frontmatter": {}}
    result = resolve_item(item, registry)
    assert result is None


# ---------------------------------------------------------------------------
# T3: test_prefix_collision — lexical order by id determines winner
# ---------------------------------------------------------------------------


def test_prefix_collision_lexical_order(tmp_path):
    """When two handlers share a prefix, the lexically-first id wins.

    File order is the INVERSE of id order to prove sort-by-id, not sort-by-filename:
    - "a-file.json" holds id="zeta-handler"  (first filename, last id)
    - "z-file.json" holds id="alpha-handler" (last filename, first id)
    Assert id="alpha-handler" wins — it has the smaller id despite the larger filename.
    """
    alpha = {
        "id": "alpha-handler",
        "enabled": True,
        "match": {"tag_prefix": "Project/", "capture_segments": ["name"]},
        "action": "insert_under_marker",
        "target": {"by": "name", "map": {"Item": "Notes/Alpha.md"}},
        "marker": "## Notes",
        "placement": "inside",
        "compose": "directive alpha",
    }
    zeta = {
        "id": "zeta-handler",
        "enabled": True,
        "match": {"tag_prefix": "Project/", "capture_segments": ["name"]},
        "action": "insert_under_marker",
        "target": {"by": "name", "map": {"Item": "Notes/Zeta.md"}},
        "marker": "## Notes",
        "placement": "inside",
        "compose": "directive zeta",
    }
    # Filename order (a < z) is OPPOSITE to what id sort would produce if
    # sort-by-filename were used — zeta-handler loads first by filename.
    _write_handler(tmp_path, "a-file.json", zeta)   # first filename → last id
    _write_handler(tmp_path, "z-file.json", alpha)  # last filename → first id
    registry = load_registry(tmp_path)

    item = {
        "path": "100 Inbox/item.md",
        "tags": ["Project/Item"],
        "frontmatter": {},
    }
    result = resolve_item(item, registry)
    assert result is not None
    # alpha-handler must win because "alpha" < "zeta" lexically,
    # regardless of filename order.
    assert result["handler"] == "alpha-handler"


# ---------------------------------------------------------------------------
# T4: test_unmapped_target — key not in map → target_path=null
# ---------------------------------------------------------------------------


def test_unmapped_target_yields_null_target_path(tmp_path):
    """A capture value not in target.map produces target_path=None (not a crash)."""
    _write_handler(tmp_path, "tsukai.json", _tsukai_handler())
    registry = load_registry(tmp_path)

    item = {
        "path": "100 Inbox/capture.md",
        "tags": ["MiYo/Tsukai/UnknownRepo"],
        "frontmatter": {},
    }
    result = resolve_item(item, registry)
    assert result is not None
    assert result["handler"] == "tsukai"
    assert result["vars"] == {"repo": "UnknownRepo"}
    assert result["target_path"] is None


# ---------------------------------------------------------------------------
# T5: test_invalid_handler_skip — schema-invalid file is skipped
# ---------------------------------------------------------------------------


def test_invalid_handler_file_is_skipped(tmp_path, caplog):
    """A schema-invalid handler JSON is skipped with a warning; run continues."""
    import logging

    _write_handler(tmp_path, "bad.json", {"no_required_fields": True})
    _write_handler(tmp_path, "tsukai.json", _tsukai_handler())

    with caplog.at_level(logging.WARNING):
        registry = load_registry(tmp_path)

    # bad.json skipped → only tsukai loaded
    assert len(registry) == 1
    assert registry[0]["id"] == "tsukai"
    # warning was emitted for the invalid file
    assert any("bad.json" in r.message for r in caplog.records)


def test_malformed_json_file_is_skipped(tmp_path, caplog):
    """A file with malformed JSON is skipped with a warning."""
    import logging

    bad = tmp_path / "broken.json"
    bad.write_text("{not valid json", encoding="utf-8")
    _write_handler(tmp_path, "tsukai.json", _tsukai_handler())

    with caplog.at_level(logging.WARNING):
        registry = load_registry(tmp_path)

    assert len(registry) == 1
    assert registry[0]["id"] == "tsukai"
    # warning was emitted for the malformed file — mirrors test_invalid_handler_file_is_skipped
    assert any("broken.json" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# T6: test_enabled_false_skip — disabled handler is not matched
# ---------------------------------------------------------------------------


def test_enabled_false_handler_is_skipped(tmp_path):
    """A handler with enabled:false is not matched against any item."""
    disabled = _tsukai_handler()
    disabled["enabled"] = False
    _write_handler(tmp_path, "tsukai.json", disabled)
    registry = load_registry(tmp_path)

    # registry can include it with enabled:false — the match step must skip it
    item = {
        "path": "100 Inbox/capture.md",
        "tags": ["MiYo/Tsukai/Tomo"],
        "frontmatter": {},
    }
    result = resolve_item(item, registry)
    assert result is None


# ---------------------------------------------------------------------------
# T7: test_deferred_action_reject — non-shipped action raises / returns error
# ---------------------------------------------------------------------------


def test_deferred_action_is_rejected(tmp_path):
    """A handler with a deferred action raises ValueError with 'not yet implemented'."""
    deferred = _tsukai_handler()
    deferred["id"] = "deferred-handler"
    deferred["action"] = "route_to_folder"
    _write_handler(tmp_path, "deferred.json", deferred)
    registry = load_registry(tmp_path)

    item = {
        "path": "100 Inbox/capture.md",
        "tags": ["MiYo/Tsukai/Tomo"],
        "frontmatter": {},
    }
    with pytest.raises(ValueError, match="not yet implemented"):
        resolve_item(item, registry)


# ---------------------------------------------------------------------------
# capture_segments binding — multiple segments, suffix split
# ---------------------------------------------------------------------------


def test_multiple_capture_segments_bound_correctly(tmp_path):
    """Multiple capture_segments are split from the tag suffix and zipped."""
    handler = {
        "id": "multi-seg",
        "enabled": True,
        "match": {
            "tag_prefix": "Work/",
            "capture_segments": ["area", "project"],
        },
        "action": "insert_under_marker",
        "target": {
            "by": "area",
            "map": {"Dev": "Notes/Dev.md"},
        },
        "marker": "## Items",
        "placement": "inside",
        "compose": "directive",
    }
    _write_handler(tmp_path, "multi.json", handler)
    registry = load_registry(tmp_path)

    item = {
        "path": "100 Inbox/note.md",
        "tags": ["Work/Dev/Tomo"],
        "frontmatter": {},
    }
    result = resolve_item(item, registry)
    assert result is not None
    assert result["vars"] == {"area": "Dev", "project": "Tomo"}
    assert result["target_path"] == "Notes/Dev.md"


# ---------------------------------------------------------------------------
# read_fields — only declared fields are lifted from frontmatter
# ---------------------------------------------------------------------------


def test_read_fields_lifted_from_frontmatter(tmp_path):
    """Only fields declared in read_fields are lifted into result['fields']."""
    _write_handler(tmp_path, "tsukai.json", _tsukai_handler())
    registry = load_registry(tmp_path)

    item = {
        "path": "100 Inbox/note.md",
        "tags": ["MiYo/Tsukai/Tomo"],
        "frontmatter": {"category": "fix", "title": "should not appear", "other": 123},
    }
    result = resolve_item(item, registry)
    assert result is not None
    assert result["fields"] == {"category": "fix"}
    assert "title" not in result["fields"]
    assert "other" not in result["fields"]


# ---------------------------------------------------------------------------
# no-target handler — target key absent → target_path=null, no crash
# ---------------------------------------------------------------------------


def test_handler_without_target_block_yields_null_path(tmp_path):
    """Handler without a target block resolves target_path=None without crashing."""
    handler = {
        "id": "no-target",
        "enabled": True,
        "match": {"tag_prefix": "Simple/"},
        "action": "insert_under_marker",
        "compose": "directive",
    }
    _write_handler(tmp_path, "notarget.json", handler)
    registry = load_registry(tmp_path)

    item = {"path": "100 Inbox/note.md", "tags": ["Simple/Anything"], "frontmatter": {}}
    result = resolve_item(item, registry)
    assert result is not None
    assert result["target_path"] is None


# ---------------------------------------------------------------------------
# S1 — unknown action (not shipped, not deferred) raises a clear error
# ---------------------------------------------------------------------------


def test_unknown_action_raises_error(tmp_path):
    """An action that is neither shipped nor deferred raises ValueError with 'unknown action'."""
    # Bypass schema validation by injecting directly into registry
    handler = {
        "id": "unknown-action-handler",
        "enabled": True,
        "match": {"tag_prefix": "Misc/"},
        "action": "totally_unknown_action",
        "compose": "directive",
    }
    # Inject directly — schema would reject this, so bypass load_registry
    registry = [handler]

    item = {"path": "100 Inbox/note.md", "tags": ["Misc/Anything"], "frontmatter": {}}
    with pytest.raises(ValueError, match="unknown action"):
        resolve_item(item, registry)


# ---------------------------------------------------------------------------
# T5.2 — shipped tsukai.json on disk: load + resolve against real handler
# ---------------------------------------------------------------------------

TSUKAI_JSON_PATH = REPO_ROOT / "tomo" / "config" / "tag-handlers" / "tsukai.json"


def test_shipped_tsukai_json_loads_as_registry():
    """load_registry on the shipped tsukai.json directory returns one handler (T5.2)."""
    handler_dir = TSUKAI_JSON_PATH.parent
    registry = load_registry(handler_dir)
    assert len(registry) == 1
    assert registry[0]["id"] == "tsukai"


def test_shipped_tsukai_json_resolves_tomo_tagged_item():
    """resolve_item with a MiYo/Tsukai/Tomo tag + category frontmatter returns correct fields (T5.2 / AC-2).

    PRD §6 exact shape:
      handler == "tsukai"
      vars    == {"repo": "Tomo"}  (from capture_segments)
      fields  == {"category": "feature"}  (from read_fields)
      marker  == "## Captures"
      action  == "insert_under_marker"
      placement == "inside"
    """
    handler_dir = TSUKAI_JSON_PATH.parent
    registry = load_registry(handler_dir)

    item = {
        "path": "100 Inbox/tsukai-capture.md",
        "tags": ["MiYo/Tsukai/Tomo"],
        "frontmatter": {"category": "feature"},
    }
    result = resolve_item(item, registry)

    assert result is not None
    assert result["handler"] == "tsukai"
    assert result["vars"] == {"repo": "Tomo"}
    assert result["fields"] == {"category": "feature"}
    assert result["marker"] == "## Captures"
    assert result["action"] == "insert_under_marker"
    assert result["placement"] == "inside"


def test_shipped_tsukai_json_unmapped_repo_yields_null_target():
    """resolve_item with an unmapped repo key returns target_path=None — no crash (T5.2 / AC-5 guard)."""
    handler_dir = TSUKAI_JSON_PATH.parent
    registry = load_registry(handler_dir)

    item = {
        "path": "100 Inbox/tsukai-capture.md",
        "tags": ["MiYo/Tsukai/UnmappedRepo"],
        "frontmatter": {},
    }
    result = resolve_item(item, registry)
    assert result is not None
    assert result["handler"] == "tsukai"
    assert result["target_path"] is None

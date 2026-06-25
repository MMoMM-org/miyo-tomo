#!/usr/bin/env python3
# version: 0.2.0
"""test_tag_handler_group.py — Behavioural tests for tag-handler-group.py.

Covers T3.1 (XDD 024 Phase 3):
- group_handled: group routing-plan handled[] by (handler, target_path),
  deterministic order, correct source_paths accumulation.
- compose_field_template: mechanical field join (no LLM).
- tag-handler-group.schema.json: group-result contract validation.

Spec: docs/XDD/specs/024-tag-handler-framework/solution.md §5
      docs/XDD/specs/024-tag-handler-framework/README.md (decisions log)
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_DIR = REPO_ROOT / "tomo" / "schemas"

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

sys.path.insert(0, str(SCRIPTS_DIR))

# Load hyphenated script as a module — house pattern from test_inbox_triage.py.
_GROUP_PATH = SCRIPTS_DIR / "tag-handler-group.py"
_group_spec = importlib.util.spec_from_file_location("tag_handler_group", _GROUP_PATH)
_group_mod = importlib.util.module_from_spec(_group_spec)
sys.modules["tag_handler_group"] = _group_mod
_group_spec.loader.exec_module(_group_mod)

group_handled = _group_mod.group_handled
compose_field_template = _group_mod.compose_field_template

# Load resolver for round-trip test (T3.3)
_RESOLVER_PATH = SCRIPTS_DIR / "tag-handler-resolve.py"
_resolver_spec = importlib.util.spec_from_file_location("tag_handler_resolve", _RESOLVER_PATH)
_resolver_mod = importlib.util.module_from_spec(_resolver_spec)
sys.modules["tag_handler_resolve"] = _resolver_mod
_resolver_spec.loader.exec_module(_resolver_mod)

load_registry = _resolver_mod.load_registry
resolve_item = _resolver_mod.resolve_item

from jsonschema import ValidationError, validate as _validate  # noqa: E402

GROUP_SCHEMA = json.loads((SCHEMA_DIR / "tag-handler-group.schema.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _handled_item(
    path: str,
    handler: str = "tsukai",
    target_path: str | None = "Efforts/Tomo Dev Log.md",
    marker: str = "## Captures",
    action: str = "insert_under_marker",
    placement: str = "inside",
    compose: str | list = "Synthesize the batch.",
    vars: dict | None = None,
    fields: dict | None = None,
) -> dict:
    """Return a handled[] item as produced by tag-handler-resolve.py."""
    return {
        "path": path,
        "handler": handler,
        "target_path": target_path,
        "marker": marker,
        "action": action,
        "placement": placement,
        "compose": compose,
        "vars": vars or {},
        "fields": fields or {},
    }


def _make_group(
    handler: str = "tsukai",
    target_path: str | None = "Efforts/Tomo Dev Log.md",
    marker: str = "## Captures",
    composed_block: str = "- Status update",
    source_paths: list[str] | None = None,
    placement: str = "inside",
    compose_mode: str = "llm_directive",
) -> dict:
    """Return a minimal valid group-result dict."""
    return {
        "schema_version": "1",
        "handler": handler,
        "target_path": target_path,
        "marker": marker,
        "composed_block": composed_block,
        "source_paths": source_paths if source_paths is not None else ["100 Inbox/note.md"],
        "placement": placement,
        "compose_mode": compose_mode,
    }


# ===========================================================================
# Schema tests — tag-handler-group.schema.json
# ===========================================================================


class TestGroupSchema:
    """Validate the group-result JSON Schema contract."""

    def test_minimal_valid_group_validates(self):
        """A group with all required fields passes schema validation."""
        _validate(instance=_make_group(), schema=GROUP_SCHEMA)

    def test_full_group_with_optional_fields_validates(self):
        """A group with all optional fields also passes."""
        group = _make_group(
            source_paths=["100 Inbox/a.md", "100 Inbox/b.md"],
            placement="after",
            compose_mode="field_template",
        )
        _validate(instance=group, schema=GROUP_SCHEMA)

    def test_null_target_path_validates(self):
        """target_path=null is valid (handler had no map entry for the captured var)."""
        group = _make_group(target_path=None)
        _validate(instance=group, schema=GROUP_SCHEMA)

    def test_missing_schema_version_fails(self):
        """Missing schema_version is rejected."""
        group = _make_group()
        del group["schema_version"]
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_wrong_schema_version_fails(self):
        """schema_version != '1' is rejected (const constraint)."""
        group = _make_group()
        group["schema_version"] = "2"
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_missing_handler_fails(self):
        """Missing handler is rejected."""
        group = _make_group()
        del group["handler"]
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_missing_target_path_key_fails(self):
        """target_path key entirely absent is rejected (required)."""
        group = _make_group()
        del group["target_path"]
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_missing_marker_fails(self):
        """Missing marker is rejected."""
        group = _make_group()
        del group["marker"]
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_missing_composed_block_fails(self):
        """Missing composed_block is rejected."""
        group = _make_group()
        del group["composed_block"]
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_missing_source_paths_fails(self):
        """Missing source_paths is rejected."""
        group = _make_group()
        del group["source_paths"]
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_empty_source_paths_fails(self):
        """source_paths=[] is rejected (minItems:1)."""
        group = _make_group(source_paths=[])
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_extra_property_fails(self):
        """Unknown top-level property is rejected (additionalProperties:false)."""
        group = _make_group()
        group["unexpected"] = "should fail"
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_compose_mode_invalid_value_fails(self):
        """compose_mode with an invalid value is rejected."""
        group = _make_group()
        group["compose_mode"] = "magic"
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_placement_invalid_value_fails(self):
        """placement with a value outside the enum is rejected."""
        group = _make_group()
        group["placement"] = "sideways"
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    # -----------------------------------------------------------------------
    # T1.2 (spec 025 Phase 1) — output_format, resolved_anchor, fallback
    # -----------------------------------------------------------------------

    def _make_output_format(self, **overrides) -> dict:
        of = {
            "structure": "table_row",
            "order": "append",
            "granularity": "per_item",
            "cells": [{"field": "category"}],
        }
        of.update(overrides)
        return of

    def test_group_with_output_format_validates(self):
        """Group result with a valid output_format block passes validation."""
        group = _make_group()
        group["output_format"] = self._make_output_format()
        _validate(instance=group, schema=GROUP_SCHEMA)

    def test_group_with_resolved_anchor_heading_validates(self):
        """Group result with resolved_anchor type=heading passes validation."""
        group = _make_group()
        group["resolved_anchor"] = {"type": "heading", "value": "## Captures", "placement": "inside"}
        _validate(instance=group, schema=GROUP_SCHEMA)

    def test_group_with_resolved_anchor_block_validates(self):
        """Group result with resolved_anchor type=block passes validation."""
        group = _make_group()
        group["resolved_anchor"] = {"type": "block", "value": "row1\nrow2", "placement": "after"}
        _validate(instance=group, schema=GROUP_SCHEMA)

    def test_group_with_fallback_validates(self):
        """Group result with a valid fallback block passes validation."""
        group = _make_group()
        group["fallback"] = {"reason": "cell_count_mismatch"}
        _validate(instance=group, schema=GROUP_SCHEMA)

    def test_group_with_all_new_fields_validates(self):
        """Group result with output_format + resolved_anchor + fallback all together passes."""
        group = _make_group()
        group["output_format"] = self._make_output_format()
        group["resolved_anchor"] = {"type": "heading", "value": "Captures", "placement": "inside"}
        group["fallback"] = {"reason": "no_structure_under_marker"}
        _validate(instance=group, schema=GROUP_SCHEMA)

    def test_existing_prose_only_group_still_validates(self):
        """Existing prose-only group-result (no new fields) still validates (backward compat)."""
        group = _make_group()
        _validate(instance=group, schema=GROUP_SCHEMA)

    def test_output_format_unknown_subkey_rejected(self):
        """output_format with unknown sub-key is REJECTED (additionalProperties:false)."""
        group = _make_group()
        group["output_format"] = self._make_output_format()
        group["output_format"]["extra"] = "bad"
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_resolved_anchor_unknown_subkey_rejected(self):
        """resolved_anchor with unknown sub-key is REJECTED (additionalProperties:false)."""
        group = _make_group()
        group["resolved_anchor"] = {
            "type": "heading", "value": "Captures", "placement": "inside", "extra": "bad"
        }
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_resolved_anchor_invalid_type_rejected(self):
        """resolved_anchor.type with an invalid value is REJECTED."""
        group = _make_group()
        group["resolved_anchor"] = {"type": "callout", "value": "x", "placement": "inside"}
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_resolved_anchor_invalid_placement_rejected(self):
        """resolved_anchor.placement with an invalid value is REJECTED."""
        group = _make_group()
        group["resolved_anchor"] = {"type": "heading", "value": "x", "placement": "before"}
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_fallback_invalid_reason_rejected(self):
        """fallback.reason with an invalid enum value is REJECTED."""
        group = _make_group()
        group["fallback"] = {"reason": "unknown_reason"}
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_fallback_unknown_subkey_rejected(self):
        """fallback with unknown sub-key is REJECTED (additionalProperties:false)."""
        group = _make_group()
        group["fallback"] = {"reason": "cell_count_mismatch", "extra": "bad"}
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)

    def test_group_unknown_top_level_key_still_rejected(self):
        """A group with a completely unknown top-level key is still REJECTED."""
        group = _make_group()
        group["new_mystery_field"] = "oops"
        with pytest.raises(ValidationError):
            _validate(instance=group, schema=GROUP_SCHEMA)


# ===========================================================================
# group_handled — grouping logic
# ===========================================================================


class TestGroupHandled:
    """Behavioural tests for group_handled(handled_list)."""

    def test_empty_list_returns_empty(self):
        """No handled items → no groups."""
        groups = group_handled([])
        assert groups == []

    def test_single_item_produces_one_group(self):
        """One item → one group with that item as the only source."""
        item = _handled_item("100 Inbox/note.md")
        groups = group_handled([item])
        assert len(groups) == 1
        assert groups[0]["handler"] == "tsukai"
        assert groups[0]["target_path"] == "Efforts/Tomo Dev Log.md"
        assert groups[0]["source_paths"] == ["100 Inbox/note.md"]

    def test_two_items_same_group_merged(self):
        """Two items with the same (handler, target_path) → one group, both paths."""
        items = [
            _handled_item("100 Inbox/a.md"),
            _handled_item("100 Inbox/b.md"),
        ]
        groups = group_handled(items)
        assert len(groups) == 1
        assert sorted(groups[0]["source_paths"]) == ["100 Inbox/a.md", "100 Inbox/b.md"]

    def test_different_target_paths_produce_separate_groups(self):
        """Same handler but different target_path → two groups."""
        items = [
            _handled_item("100 Inbox/a.md", target_path="Notes/A.md"),
            _handled_item("100 Inbox/b.md", target_path="Notes/B.md"),
        ]
        groups = group_handled(items)
        assert len(groups) == 2
        target_paths = {g["target_path"] for g in groups}
        assert target_paths == {"Notes/A.md", "Notes/B.md"}

    def test_different_handlers_produce_separate_groups(self):
        """Different handlers → separate groups even if target_path is the same."""
        items = [
            _handled_item("100 Inbox/a.md", handler="alpha", target_path="Notes/X.md"),
            _handled_item("100 Inbox/b.md", handler="beta", target_path="Notes/X.md"),
        ]
        groups = group_handled(items)
        assert len(groups) == 2
        handler_ids = {g["handler"] for g in groups}
        assert handler_ids == {"alpha", "beta"}

    def test_three_items_two_groups(self):
        """Three items across two (handler, target_path) pairs → two groups."""
        items = [
            _handled_item("100 Inbox/a.md", handler="tsukai", target_path="Notes/Tomo.md"),
            _handled_item("100 Inbox/b.md", handler="tsukai", target_path="Notes/Tomo.md"),
            _handled_item("100 Inbox/c.md", handler="tsukai", target_path="Notes/Kado.md"),
        ]
        groups = group_handled(items)
        assert len(groups) == 2
        tomo_group = next(g for g in groups if g["target_path"] == "Notes/Tomo.md")
        kado_group = next(g for g in groups if g["target_path"] == "Notes/Kado.md")
        assert sorted(tomo_group["source_paths"]) == ["100 Inbox/a.md", "100 Inbox/b.md"]
        assert kado_group["source_paths"] == ["100 Inbox/c.md"]

    def test_group_carries_marker_and_placement(self):
        """Resulting group carries marker and placement from the handler config."""
        item = _handled_item(
            "100 Inbox/note.md",
            marker="## My Section",
            placement="after",
        )
        groups = group_handled([item])
        assert groups[0]["marker"] == "## My Section"
        assert groups[0]["placement"] == "after"

    def test_group_carries_compose_directive(self):
        """Resulting group carries the compose directive from the handler config."""
        item = _handled_item("100 Inbox/note.md", compose="Write a status update.")
        groups = group_handled([item])
        assert groups[0]["compose"] == "Write a status update."

    def test_null_target_path_groups_correctly(self):
        """Items with target_path=null group together under null."""
        items = [
            _handled_item("100 Inbox/a.md", target_path=None),
            _handled_item("100 Inbox/b.md", target_path=None),
        ]
        groups = group_handled(items)
        assert len(groups) == 1
        assert groups[0]["target_path"] is None
        assert sorted(groups[0]["source_paths"]) == ["100 Inbox/a.md", "100 Inbox/b.md"]

    def test_deterministic_order_by_handler_then_target(self):
        """Groups are sorted lexically: handler first, then target_path."""
        items = [
            _handled_item("100 Inbox/z.md", handler="zeta", target_path="Notes/B.md"),
            _handled_item("100 Inbox/a.md", handler="alpha", target_path="Notes/Z.md"),
            _handled_item("100 Inbox/b.md", handler="alpha", target_path="Notes/A.md"),
        ]
        groups = group_handled(items)
        assert len(groups) == 3
        keys = [(g["handler"], g["target_path"]) for g in groups]
        assert keys == [
            ("alpha", "Notes/A.md"),
            ("alpha", "Notes/Z.md"),
            ("zeta", "Notes/B.md"),
        ]

    def test_null_target_path_sorts_last_or_consistently(self):
        """Groups with null target_path appear in a consistent position."""
        items = [
            _handled_item("100 Inbox/a.md", handler="alpha", target_path=None),
            _handled_item("100 Inbox/b.md", handler="alpha", target_path="Notes/A.md"),
        ]
        groups = group_handled(items)
        assert len(groups) == 2
        # null target_path sorts consistently (after non-null under same handler)
        handler_targets = [(g["handler"], g["target_path"]) for g in groups]
        # Both are "alpha" — assert we get both and they're stable
        assert ("alpha", "Notes/A.md") in handler_targets
        assert ("alpha", None) in handler_targets

    def test_source_paths_preserve_insertion_order_within_group(self):
        """source_paths within a group preserve the order items appeared in handled_list."""
        items = [
            _handled_item("100 Inbox/first.md"),
            _handled_item("100 Inbox/second.md"),
            _handled_item("100 Inbox/third.md"),
        ]
        groups = group_handled(items)
        assert groups[0]["source_paths"] == [
            "100 Inbox/first.md",
            "100 Inbox/second.md",
            "100 Inbox/third.md",
        ]


# ===========================================================================
# compose_field_template — mechanical join
# ===========================================================================


class TestComposeFieldTemplate:
    """Tests for compose_field_template(captures, fields) — no LLM path."""

    def test_single_capture_single_field(self):
        """One capture, one field → single formatted line."""
        captures = [{"path": "100 Inbox/note.md", "fields": {"category": "feature"}}]
        result = compose_field_template(captures, ["category"])
        assert "feature" in result

    def test_multiple_captures_joined(self):
        """Multiple captures → all entries present in the output."""
        captures = [
            {"path": "100 Inbox/a.md", "fields": {"category": "feature"}},
            {"path": "100 Inbox/b.md", "fields": {"category": "fix"}},
        ]
        result = compose_field_template(captures, ["category"])
        assert "feature" in result
        assert "fix" in result

    def test_multiple_fields_all_present(self):
        """Multiple fields → each field value appears in the output."""
        captures = [
            {"path": "100 Inbox/a.md", "fields": {"category": "feature", "priority": "high"}},
        ]
        result = compose_field_template(captures, ["category", "priority"])
        assert "feature" in result
        assert "high" in result

    def test_missing_field_skipped_gracefully(self):
        """A field not present in a capture's fields dict is skipped without error."""
        captures = [
            {"path": "100 Inbox/a.md", "fields": {"category": "feature"}},
        ]
        result = compose_field_template(captures, ["category", "missing_field"])
        assert "feature" in result  # present field still rendered
        assert isinstance(result, str)  # no crash

    def test_empty_captures_returns_string(self):
        """No captures → returns an empty or placeholder string, no crash."""
        result = compose_field_template([], ["category"])
        assert isinstance(result, str)

    def test_empty_fields_list_returns_string(self):
        """No fields in template → returns a string (may be empty), no crash."""
        captures = [{"path": "100 Inbox/a.md", "fields": {"category": "feature"}}]
        result = compose_field_template(captures, [])
        assert isinstance(result, str)

    def test_returns_nonempty_string_for_real_input(self):
        """Result is non-empty when there is real capture data."""
        captures = [{"path": "100 Inbox/a.md", "fields": {"category": "fix"}}]
        result = compose_field_template(captures, ["category"])
        assert len(result) > 0


# ===========================================================================
# T3.2 — output_format propagation into the group stub (spec 025 Phase 3)
# ===========================================================================

_OUTPUT_FORMAT = {
    "structure": "table_row",
    "order": "append",
    "granularity": "per_item",
    "cells": [{"field": "category"}],
}


def _handled_item_with_output_format(path: str, handler: str = "tsukai") -> dict:
    """Return a handled[] item that includes output_format."""
    item = _handled_item(path, handler=handler)
    item["output_format"] = _OUTPUT_FORMAT
    return item


class TestGroupHandledOutputFormat:
    """T3.2: group_handled carries output_format from item into the stub."""

    def test_stub_carries_output_format_from_item(self):
        """T3.2 (RED→GREEN): item with output_format → stub includes output_format verbatim."""
        item = _handled_item_with_output_format("100 Inbox/note.md")
        groups = group_handled([item])
        assert len(groups) == 1
        assert "output_format" in groups[0]
        assert groups[0]["output_format"] == _OUTPUT_FORMAT

    def test_stub_without_output_format_is_absent_or_none(self):
        """T3.2 backward compat: item WITHOUT output_format → stub key absent or None."""
        item = _handled_item("100 Inbox/note.md")
        groups = group_handled([item])
        assert len(groups) == 1
        assert groups[0].get("output_format") is None

    def test_different_handlers_keep_own_output_format(self):
        """T3.2: items from different handlers keep their OWN output_format (no cross-contamination)."""
        of_alpha = {"structure": "table_row", "order": "append", "granularity": "per_item", "cells": [{"field": "a"}]}
        of_beta = {"structure": "table_row", "order": "append", "granularity": "per_batch", "cells": [{"field": "b"}]}

        item_alpha = _handled_item("100 Inbox/a.md", handler="alpha", target_path="Notes/A.md")
        item_alpha["output_format"] = of_alpha

        item_beta = _handled_item("100 Inbox/b.md", handler="beta", target_path="Notes/B.md")
        item_beta["output_format"] = of_beta

        groups = group_handled([item_alpha, item_beta])
        assert len(groups) == 2

        alpha_group = next(g for g in groups if g["handler"] == "alpha")
        beta_group = next(g for g in groups if g["handler"] == "beta")

        assert alpha_group["output_format"] == of_alpha
        assert beta_group["output_format"] == of_beta
        # Ensure no cross-contamination
        assert alpha_group["output_format"] != of_beta
        assert beta_group["output_format"] != of_alpha

    def test_same_group_multiple_items_output_format_from_first(self):
        """T3.2: multiple items sharing (handler, target) → output_format from the first item."""
        item_a = _handled_item_with_output_format("100 Inbox/a.md")
        item_b = _handled_item("100 Inbox/b.md")  # no output_format on second item
        groups = group_handled([item_a, item_b])
        assert len(groups) == 1
        # First item's output_format wins (stub built from first item)
        assert groups[0]["output_format"] == _OUTPUT_FORMAT


# ===========================================================================
# T3.3 — resolve → group round-trip (spec 025 Phase 3 validation)
# ===========================================================================


def _write_handler_file(directory: Path, filename: str, config: dict) -> None:
    """Write a handler config JSON into the given registry directory."""
    p = directory / filename
    p.write_text(json.dumps(config), encoding="utf-8")


class TestResolveGroupRoundTrip:
    """T3.3: output_format survives the full resolve→group pipeline unchanged."""

    def test_output_format_reaches_stub_unchanged(self, tmp_path):
        """T3.3: feed a config with output_format through resolve_item then group_handled;
        assert the stub's output_format equals the config's output_format exactly."""
        handler_config = {
            "id": "roundtrip-handler",
            "enabled": True,
            "match": {
                "tag_prefix": "MiYo/Test/",
                "capture_segments": ["repo"],
            },
            "action": "insert_under_marker",
            "target": {
                "by": "repo",
                "map": {"Tomo": "Efforts/Tomo Log.md"},
            },
            "marker": "## Captures",
            "placement": "after",
            "compose": "Synthesize.",
            "output_format": _OUTPUT_FORMAT,
        }
        _write_handler_file(tmp_path, "roundtrip.json", handler_config)
        registry = load_registry(tmp_path)

        item = {
            "path": "100 Inbox/round-trip.md",
            "tags": ["MiYo/Test/Tomo"],
            "frontmatter": {},
        }
        resolved = resolve_item(item, registry)
        assert resolved is not None
        assert resolved["output_format"] == _OUTPUT_FORMAT

        # Simulate handled[] array (group_handled expects path + handler fields)
        handled_item = {"path": item["path"], **resolved}
        groups = group_handled([handled_item])

        assert len(groups) == 1
        assert groups[0]["output_format"] == _OUTPUT_FORMAT

    def test_existing_resolve_tests_still_pass(self, tmp_path):
        """T3.3 backward compat: resolver without output_format still produces correct shape."""
        handler = {
            "id": "prose-handler",
            "enabled": True,
            "match": {"tag_prefix": "MiYo/Tsukai/", "capture_segments": ["repo"]},
            "action": "insert_under_marker",
            "target": {"by": "repo", "map": {"Tomo": "Efforts/Tomo Log.md"}},
            "marker": "## Captures",
            "placement": "after",
            "compose": "Write a prose update.",
        }
        _write_handler_file(tmp_path, "prose.json", handler)
        registry = load_registry(tmp_path)

        item = {"path": "100 Inbox/note.md", "tags": ["MiYo/Tsukai/Tomo"], "frontmatter": {}}
        resolved = resolve_item(item, registry)
        assert resolved is not None
        assert resolved.get("output_format") is None

        handled_item = {"path": item["path"], **resolved}
        groups = group_handled([handled_item])
        assert len(groups) == 1
        assert groups[0].get("output_format") is None

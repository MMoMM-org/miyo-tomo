#!/usr/bin/env python3
# version: 0.3.0
"""test_035_wire_shape.py — Behavioural tests for lib.wire_shape.describe_shape (spec 035 T1.1).

Tests cover:
- a schema with no $defs still yields nodes for its inline objects (the case the
  existing drift check misses entirely)
- nested objects under `items` are reached, including array-of-object-of-array
- `$defs` / `definitions` entries are reached
- `allOf` / `anyOf` / `oneOf` branches are reached, and so are `if` / `then` / `else`
  (the real `edit_frontmatter` shape)
- `closed` is recorded effectively (False/True/False for absent/False/True
  `additionalProperties`), never literally
- each property records its declared type; an undeclared type gets a defined
  placeholder rather than being omitted
- a description-only difference produces an identical manifest (anti-churn, PRD/F1-AC4)
- a property named after a structural keyword does not collide with that keyword's
  own node
- `enum`/`const` values are recorded in a `values` field (PRD F2-AC3), sorted with a
  type-tolerant key, `const: X` recorded as `[X]`
- local `$ref` is resolved for type/enum/const, inline wins over a `$ref` sibling, a
  non-local or cyclic `$ref` records `"any"` and terminates
- list-valued `type` is sorted (an unordered set, so reordering is a no-op) AND
  copied, never aliasing the input schema's own list
- a malformed SCHEMA (code review, 2026-09-10, sixth loop-abort trigger) does
  not crash describe_shape: `$defs`/`definitions`/`allOf`/`anyOf`/`oneOf` each
  set to a truthy wrong type, and a `properties` CHILD that is a truthy
  non-dict, are each skipped rather than dereferenced. A `properties` child
  that is `null` (legitimate JSON Schema, not malformed) is still recorded as
  an unconstrained ("any") property, unaffected by the new check
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.wire_shape import describe_shape  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# F1-AC3 — no $defs at all: the case the existing check misses entirely
# ──────────────────────────────────────────────────────────────────────────────

def test_no_defs_schema_yields_nodes_for_inline_objects():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id"],
        "properties": {
            "id": {"type": "string"},
            "detail": {
                "type": "object",
                "properties": {"note": {"type": "string"}},
            },
        },
    }

    result = describe_shape(schema)

    assert "$defs" not in schema
    assert "" in result
    assert result[""]["closed"] is True
    assert result[""]["required"] == ["id"]
    assert "/properties/detail" in result
    assert result["/properties/detail"]["properties"] == {"note": "string"}


# ──────────────────────────────────────────────────────────────────────────────
# nested objects under items, including array-of-object-of-array
# ──────────────────────────────────────────────────────────────────────────────

def test_nested_objects_under_items_reached_at_every_depth():
    schema = {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "children": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {"leaf": {"type": "string"}},
                            },
                        },
                    },
                },
            },
        },
    }

    result = describe_shape(schema)

    # array-of-object
    assert "/properties/rows/items" in result
    assert result["/properties/rows/items"]["properties"] == {"children": "array"}
    # array-of-object-of-array-of-object
    assert "/properties/rows/items/properties/children/items" in result
    assert result["/properties/rows/items/properties/children/items"]["closed"] is True
    assert result["/properties/rows/items/properties/children/items"]["properties"] == {
        "leaf": "string",
    }


# ──────────────────────────────────────────────────────────────────────────────
# $defs / definitions entries reached
# ──────────────────────────────────────────────────────────────────────────────

def test_defs_and_definitions_entries_reached():
    schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "$defs": {
            "Widget": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"name": {"type": "string"}},
            },
        },
        "definitions": {
            "Legacy": {
                "type": "object",
                "properties": {"old": {"type": "string"}},
            },
        },
    }

    result = describe_shape(schema)

    assert "/$defs/Widget" in result
    assert result["/$defs/Widget"]["closed"] is True
    assert "/definitions/Legacy" in result
    assert result["/definitions/Legacy"]["closed"] is False


# ──────────────────────────────────────────────────────────────────────────────
# allOf / anyOf / oneOf branches reached
# ──────────────────────────────────────────────────────────────────────────────

def test_allof_anyof_oneof_branches_reached():
    schema = {
        "allOf": [
            {"type": "object", "properties": {"a": {"type": "string"}}},
        ],
        "anyOf": [
            {"type": "object", "properties": {"b": {"type": "string"}}},
        ],
        "oneOf": [
            {"type": "object", "properties": {"c": {"type": "string"}}},
        ],
    }

    result = describe_shape(schema)

    assert "/allOf/0" in result
    assert result["/allOf/0"]["properties"] == {"a": "string"}
    assert "/anyOf/0" in result
    assert result["/anyOf/0"]["properties"] == {"b": "string"}
    assert "/oneOf/0" in result
    assert result["/oneOf/0"]["properties"] == {"c": "string"}


# ──────────────────────────────────────────────────────────────────────────────
# closed recorded effectively, not literally
# ──────────────────────────────────────────────────────────────────────────────

def test_closed_recorded_effectively_not_literally():
    schema = {
        "type": "object",
        "properties": {
            "explicitly_closed": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"x": {"type": "string"}},
            },
            "explicitly_open": {
                "type": "object",
                "additionalProperties": True,
                "properties": {"y": {"type": "string"}},
            },
            "silently_open": {
                "type": "object",
                "properties": {"z": {"type": "string"}},
            },
        },
    }

    result = describe_shape(schema)

    assert result["/properties/explicitly_closed"]["closed"] is True
    assert result["/properties/explicitly_open"]["closed"] is False
    assert result["/properties/silently_open"]["closed"] is False


# ──────────────────────────────────────────────────────────────────────────────
# types recorded; undeclared type gets a defined placeholder, not omission
# ──────────────────────────────────────────────────────────────────────────────

def test_property_types_recorded_and_undeclared_type_gets_placeholder():
    schema = {
        "type": "object",
        "properties": {
            "typed": {"type": "string"},
            "untyped": {"description": "carries no type keyword"},
        },
    }

    result = describe_shape(schema)

    assert result[""]["properties"]["typed"] == "string"
    assert "untyped" in result[""]["properties"]
    assert result[""]["properties"]["untyped"] is not None
    assert result[""]["properties"]["untyped"] == "any"


# ──────────────────────────────────────────────────────────────────────────────
# PRD/F1-AC4 — description-only difference produces an identical manifest
# ──────────────────────────────────────────────────────────────────────────────

def test_description_only_difference_is_manifest_identical():
    schema_a = {
        "type": "object",
        "description": "Version A of this document.",
        "properties": {
            "id": {"type": "string", "description": "the identifier"},
        },
    }
    schema_b = {
        "type": "object",
        "title": "A brand new title nobody had before",
        "description": "A completely rewritten description of Version B.",
        "properties": {
            "id": {"type": "string", "description": "a wholly different sentence"},
        },
    }

    assert describe_shape(schema_a) == describe_shape(schema_b)


# ──────────────────────────────────────────────────────────────────────────────
# regression — a property named after a structural keyword must not collide
# with that keyword's own node (bare pointers collapsed /items onto /items)
# ──────────────────────────────────────────────────────────────────────────────

def test_property_named_items_does_not_collide_with_items_keyword():
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "object",
                "properties": {"a": {"type": "string"}},
            },
        },
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"b": {"type": "string"}},
        },
    }

    result = describe_shape(schema)

    assert set(result.keys()) == {"", "/properties/items", "/items"}
    assert result[""]["properties"] == {"items": "object"}
    assert result["/properties/items"]["closed"] is False
    assert result["/properties/items"]["properties"] == {"a": "string"}
    assert result["/items"]["closed"] is True
    assert result["/items"]["properties"] == {"b": "string"}


# ──────────────────────────────────────────────────────────────────────────────
# T1.3's own validation gate — the real suggestions-wire manifest must carry
# this exact pointer, not the bare form
# ──────────────────────────────────────────────────────────────────────────────

def test_real_suggestions_wire_contains_the_gated_pointer():
    schema = json.loads((SCHEMAS_DIR / "suggestions-wire.schema.json").read_text())

    result = describe_shape(schema)

    assert "/properties/suggestions/items" in result


# ──────────────────────────────────────────────────────────────────────────────
# code-quality fix 1 — if/then/else are walked, on the REAL edit_frontmatter
# shape (docs/XDD/specs/035-wire-schema-versioning) where `if` is a genuine
# object node with its own properties and required
# ──────────────────────────────────────────────────────────────────────────────

def test_if_branch_of_real_edit_frontmatter_is_walked():
    schema = json.loads((SCHEMAS_DIR / "instructions.schema.json").read_text())

    result = describe_shape(schema)

    pointer = "/$defs/edit_frontmatter/allOf/0/if"
    assert pointer in result
    assert result[pointer]["required"] == ["operation"]
    # operation's own subschema is {"const": "set"} — no "type" keyword, so
    # the type placeholder applies, and the const surfaces in "values".
    assert result[pointer]["properties"] == {"operation": "any"}
    assert result[pointer]["values"] == {"operation": ["set"]}


# ──────────────────────────────────────────────────────────────────────────────
# code-quality fix 2 (PRD F2-AC3) — enum/const values recorded in `values`,
# always present as a dict, an entry only where declared
# ──────────────────────────────────────────────────────────────────────────────

def test_enum_and_const_recorded_in_values_field():
    schema = {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["set", "remove"]},
            "flag": {"const": True},
            "plain": {"type": "string"},
        },
    }

    result = describe_shape(schema)

    assert result[""]["values"] == {"op": ["remove", "set"], "flag": [True]}
    assert "plain" not in result[""]["values"]


def test_enum_values_sorted_with_a_type_tolerant_total_order():
    schema = {
        "type": "object",
        "properties": {
            "mixed": {"enum": ["b", 2, None, 1, "a", True]},
        },
    }

    result = describe_shape(schema)

    # Grouped by type name (NoneType < bool < int < str), then by value
    # within each group. A bare sorted() on this list raises TypeError.
    assert result[""]["values"]["mixed"] == [None, True, 1, 2, "a", "b"]


def test_enum_and_const_together_records_enum_alone_deliberately():
    # No published wire declares both today. JSON Schema treats enum and
    # const as independent assertions that both apply — the genuinely
    # correct record would be their intersection — but this pins a
    # deliberate, scoped choice (enum alone; see wire_shape.md) rather than
    # leaving the precedence to fall out of code order unnoticed.
    schema = {
        "type": "object",
        "properties": {
            "both": {"enum": ["a", "b"], "const": "a"},
        },
    }

    result = describe_shape(schema)

    assert result[""]["values"]["both"] == ["a", "b"]


# ──────────────────────────────────────────────────────────────────────────────
# code-quality fix 3 — local $ref resolved for type (and enum/const)
# ──────────────────────────────────────────────────────────────────────────────

def test_local_ref_resolved_for_type_on_real_instructions_schema():
    schema = json.loads((SCHEMAS_DIR / "instructions.schema.json").read_text())

    result = describe_shape(schema)

    move_note = result["/$defs/move_note"]
    assert move_note["properties"]["id"] == "string"
    assert move_note["properties"]["applied"] == "boolean"


def test_inline_type_wins_over_ref_sibling():
    schema = {
        "type": "object",
        "properties": {
            "overridden": {"$ref": "#/$defs/Thing", "type": "integer"},
        },
        "$defs": {"Thing": {"type": "string"}},
    }

    result = describe_shape(schema)

    assert result[""]["properties"]["overridden"] == "integer"


def test_inline_override_of_one_keyword_does_not_suppress_ref_resolution_of_another():
    # A property overriding `type` inline still resolves `enum` from its
    # $ref target — each keyword is looked up independently (_effective is
    # called once per keyword). A refactor that hoisted a single resolved
    # node per property (inline child if it declares ANYTHING, else the ref
    # target) would suppress this: type would stay "string" but values
    # would go missing, because the ref would never be consulted at all.
    schema = {
        "type": "object",
        "properties": {
            "status": {"$ref": "#/$defs/Status", "type": "string"},
        },
        "$defs": {
            "Status": {"type": "integer", "enum": ["active", "archived"]},
        },
    }

    result = describe_shape(schema)

    assert result[""]["properties"]["status"] == "string"  # inline wins
    assert result[""]["values"]["status"] == ["active", "archived"]  # still resolved


def test_same_ref_target_resolves_at_many_independent_sites_in_one_call():
    # `seen` in _effective is created fresh on every call. If a future edit
    # hoisted it to module scope, or made it a mutable default argument
    # (the classic Python footgun), the second-and-later use of a shared
    # $ref within one describe_shape() call would find it already in
    # `seen` and short-circuit to "any" — most of the instructions wire
    # would silently under-record, since action_id is shared by every
    # action shape. Real schema, not synthetic: a synthetic fixture is not
    # what would catch a module-scope `seen` — only a wire that actually
    # references the same target many times over one call would.
    schema = json.loads((SCHEMAS_DIR / "instructions.schema.json").read_text())

    result = describe_shape(schema)

    sites = [
        "/$defs/move_note",
        "/$defs/move_asset",
        "/$defs/link_to_moc",
        "/$defs/add_relationship",
        "/$defs/update_tracker",
        "/$defs/edit_frontmatter",
        "/$defs/resolve_dead_link",
    ]
    for pointer in sites:
        assert result[pointer]["properties"]["id"] == "string", pointer


def test_non_local_ref_records_any():
    schema = {
        "type": "object",
        "properties": {
            "external": {"$ref": "https://example.com/other.schema.json#/$defs/Foo"},
        },
    }

    result = describe_shape(schema)

    assert result[""]["properties"]["external"] == "any"


def test_cyclic_ref_terminates_and_records_any():
    schema = {
        "type": "object",
        "properties": {
            "cyclic": {"$ref": "#/$defs/A"},
        },
        "$defs": {
            "A": {"$ref": "#/$defs/B"},
            "B": {"$ref": "#/$defs/A"},
        },
    }

    result = describe_shape(schema)

    assert result[""]["properties"]["cyclic"] == "any"


# ──────────────────────────────────────────────────────────────────────────────
# code-quality fixes 4/5 — list-valued type is sorted AND copied, not aliased
# ──────────────────────────────────────────────────────────────────────────────

def test_list_valued_type_is_sorted():
    schema = {
        "type": "object",
        "properties": {
            "maybe_null": {"type": ["string", "null"]},
        },
    }

    result = describe_shape(schema)

    assert result[""]["properties"]["maybe_null"] == ["null", "string"]


def test_list_valued_type_is_a_copy_not_an_alias():
    original = ["string", "null"]
    schema = {
        "type": "object",
        "properties": {"maybe_null": {"type": original}},
    }

    result = describe_shape(schema)

    assert result[""]["properties"]["maybe_null"] is not original
    assert result[""]["properties"]["maybe_null"] == sorted(original)


# ──────────────────────────────────────────────────────────────────────────────
# CRITICAL, sixth trigger (code review, 2026-09-10): a malformed SCHEMA
# crashes describe_shape the same way a malformed MANIFEST crashed the gate
# — the `X or {}`/`X or []` idiom only absorbs a FALSY wrong type; a TRUTHY
# one reaches `.items()`/`enumerate(...)`/`_property_type` unguarded and
# raises. Fixed inside describe_shape itself (not the gate) by applying the
# SAME `isinstance` pattern the function already uses for `properties`
# uniformly to every traversal key, per describe_shape's own stated
# contract at the top of `walk`: `if not isinstance(node, dict): return`.
# A malformed region is SKIPPED, not fatal — the resulting shape then
# genuinely differs from a manifest recorded before the corruption, which
# is what lets the gate report it as a loud, structured shape change
# instead of aborting. Each test below covers one traversal key against a
# TRUTHY wrong type — the case that crashed before this fix; falsy wrong
# types (None, {}, [], "", 0) were never the trigger and are not retested
# here.
# ──────────────────────────────────────────────────────────────────────────────

def test_defs_with_wrong_type_is_skipped_not_fatal():
    schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "$defs": "not-a-dict",
    }

    result = describe_shape(schema)

    assert result[""]["properties"] == {"id": "string"}
    assert not any(pointer.startswith("/$defs/") for pointer in result)


def test_definitions_with_wrong_type_is_skipped_not_fatal():
    schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "definitions": ["not", "a", "dict"],
    }

    result = describe_shape(schema)

    assert result[""]["properties"] == {"id": "string"}
    assert not any(pointer.startswith("/definitions/") for pointer in result)


def test_allof_with_wrong_type_is_skipped_not_fatal():
    schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "allOf": 5,
    }

    result = describe_shape(schema)

    assert result[""]["properties"] == {"id": "string"}
    assert not any(pointer.startswith("/allOf/") for pointer in result)


def test_anyof_with_wrong_type_is_skipped_not_fatal():
    schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "anyOf": True,
    }

    result = describe_shape(schema)

    assert result[""]["properties"] == {"id": "string"}
    assert not any(pointer.startswith("/anyOf/") for pointer in result)


def test_oneof_with_wrong_type_is_skipped_not_fatal():
    schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "oneOf": 1.5,
    }

    result = describe_shape(schema)

    assert result[""]["properties"] == {"id": "string"}
    assert not any(pointer.startswith("/oneOf/") for pointer in result)


def test_property_child_with_wrong_type_is_skipped_not_dereferenced():
    # Distinct from the traversal-key tests above: `properties` itself IS
    # a well-formed dict here (already guarded by the pre-existing
    # `isinstance(props, dict)` check) — the malformed value is one
    # PROPERTY'S value inside it, which used to reach
    # `_property_type`/`_property_values` unguarded.
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "weird": "not-a-dict",
        },
    }

    result = describe_shape(schema)

    # "weird" is skipped entirely — absent from both properties and
    # values, not recorded with a placeholder type. A manifest recorded
    # before this corruption still lists "weird", so this produces a real
    # `removed_property` diff rather than silently matching.
    assert result[""]["properties"] == {"id": "string"}
    assert "weird" not in result[""]["values"]


def test_property_child_null_is_still_treated_as_no_constraint():
    # The FALSY case must keep working exactly as before: `"weird": null`
    # is legitimate JSON Schema (an unconstrained subschema), not
    # malformed, and must NOT be skipped by the new truthy-only check.
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "weird": None,
        },
    }

    result = describe_shape(schema)

    assert result[""]["properties"] == {"id": "string", "weird": "any"}

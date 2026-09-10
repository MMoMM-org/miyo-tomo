#!/usr/bin/env python3
# version: 0.3.0
"""test_035_wire_diff.py — Behavioural tests for lib.wire_shape.diff_shapes (spec 035 T2.1).

Separate from test_035_wire_shape.py on purpose: that file exercises the
describe_shape() walk (schema in, node map out); this file exercises
diff_shapes() in isolation (two node maps in, list[ShapeChange] out). Same
split rationale as test_035_wire_manifests.py vs test_035_wire_shape.py —
different subject, different fixture shape (hand-built node maps, not schema
dicts).

Tests cover:
- an added property is reported with its pointer and name (added_property)
- a removed property likewise (removed_property)
- a field joining `required` is reported distinctly from a property change
  (required_added, not folded into added_property/removed_property); a
  field leaving `required` is its own opposite kind (required_removed) —
  not one `required_changed`, because the two directions classify
  oppositely against the consumer's validator; both kinds fire together,
  never collapsed into one entry, when one edit does both on the same node
- an openness change is its own kind (openness_changed)
- a type change is its own kind (type_changed)
- a node added or removed wholesale is reported ONCE, not as N property
  changes — asserted both ways: exactly one change, AND no added_property/
  removed_property entries for any pointer under that node (the granularity
  trap named in the task brief)
- identical manifests produce an empty list — paired with a mutation test
  that proves the empty list is real detection, not `return []`
- an enum value added to a property is reported as added_enum_value with
  its pointer, the property name and the value; a value removed is
  removed_enum_value; a property gaining an enum where it had none is
  reported; a const widened to an enum containing it reports the added
  values and nothing else (Phase 1 records `const: X` as `[X]`)
- diff_shapes(nodes, nodes) is empty for each of the three real committed
  manifests (the sanity check the task brief asks for, pinned as a test)
- the output is sorted by (pointer, kind, detail) — pinned with an EXACT
  sequence assertion (not a set) over several changes spanning two pointers
  and two kinds, chosen so removing the sort changes the result
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SHAPES_DIR = REPO_ROOT / "tomo" / "schemas" / "shapes"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.wire_shape import diff_shapes  # noqa: E402


def _node(closed=True, required=None, properties=None, values=None) -> dict:
    return {
        "closed": closed,
        "required": sorted(required or []),
        "properties": properties or {},
        "values": values or {},
    }


# ──────────────────────────────────────────────────────────────────────────────
# added_property / removed_property
# ──────────────────────────────────────────────────────────────────────────────

def test_added_property_reported_with_pointer_and_name():
    recorded = {"": _node(properties={"id": "string"})}
    observed = {"": _node(properties={"id": "string", "stem": "string"})}

    changes = diff_shapes(recorded, observed)

    assert len(changes) == 1
    change = changes[0]
    assert change["pointer"] == ""
    assert change["kind"] == "added_property"
    assert "stem" in change["detail"]


def test_removed_property_reported_with_pointer_and_name():
    recorded = {"": _node(properties={"id": "string", "stem": "string"})}
    observed = {"": _node(properties={"id": "string"})}

    changes = diff_shapes(recorded, observed)

    assert len(changes) == 1
    change = changes[0]
    assert change["pointer"] == ""
    assert change["kind"] == "removed_property"
    assert "stem" in change["detail"]


# ──────────────────────────────────────────────────────────────────────────────
# required_added / required_removed are distinct from a property change,
# AND from each other — the two directions classify oppositely against the
# consumer's validator, the same reason the enum kinds are split in two.
# ──────────────────────────────────────────────────────────────────────────────

def test_required_added_reported_when_a_field_joins_required():
    # item_key exists as a property on both sides already (so no
    # added_property fires) — only `required` gained it. This is the shape
    # of the spec-034 drift: the property was already there, `required`
    # moved underneath it.
    recorded = _node(required=["id"], properties={"id": "string", "item_key": "string"})
    observed = _node(
        required=["id", "item_key"], properties={"id": "string", "item_key": "string"},
    )

    changes = diff_shapes({"/x": recorded}, {"/x": observed})

    assert len(changes) == 1
    assert changes[0]["kind"] == "required_added"
    assert changes[0]["pointer"] == "/x"
    assert "item_key" in changes[0]["detail"]


def test_required_removed_reported_when_a_field_leaves_required():
    # item_key stays a property on both sides — it becomes optional, it
    # does not disappear. No added_property/removed_property should fire.
    recorded = _node(required=["id", "item_key"], properties={"id": "string", "item_key": "string"})
    observed = _node(required=["id"], properties={"id": "string", "item_key": "string"})

    changes = diff_shapes({"/x": recorded}, {"/x": observed})

    assert len(changes) == 1
    assert changes[0]["kind"] == "required_removed"
    assert changes[0]["pointer"] == "/x"
    assert "item_key" in changes[0]["detail"]


def test_required_added_and_removed_in_one_edit_emit_both_kinds_not_one():
    # `a` leaves required, `c` joins it, `b` is unchanged — both directions
    # move on the same node in the same edit. Both kinds must be present,
    # never collapsed into a single entry.
    recorded = _node(
        required=["a", "b"],
        properties={"a": "string", "b": "string", "c": "string"},
    )
    observed = _node(
        required=["b", "c"],
        properties={"a": "string", "b": "string", "c": "string"},
    )

    changes = diff_shapes({"/x": recorded}, {"/x": observed})

    assert len(changes) == 2
    kinds = {c["kind"] for c in changes}
    assert kinds == {"required_added", "required_removed"}
    added = next(c for c in changes if c["kind"] == "required_added")
    removed = next(c for c in changes if c["kind"] == "required_removed")
    assert "c" in added["detail"]
    assert "a" in removed["detail"]


# ──────────────────────────────────────────────────────────────────────────────
# openness_changed is its own kind
# ──────────────────────────────────────────────────────────────────────────────

def test_openness_change_is_its_own_kind():
    recorded = {"/x": _node(closed=True, properties={"id": "string"})}
    observed = {"/x": _node(closed=False, properties={"id": "string"})}

    changes = diff_shapes(recorded, observed)

    assert len(changes) == 1
    assert changes[0]["kind"] == "openness_changed"
    assert changes[0]["pointer"] == "/x"


# ──────────────────────────────────────────────────────────────────────────────
# type_changed is its own kind
# ──────────────────────────────────────────────────────────────────────────────

def test_type_change_is_its_own_kind():
    recorded = {"/x": _node(properties={"id": "string"})}
    observed = {"/x": _node(properties={"id": "integer"})}

    changes = diff_shapes(recorded, observed)

    assert len(changes) == 1
    assert changes[0]["kind"] == "type_changed"
    assert changes[0]["pointer"] == "/x"
    assert "string" in changes[0]["detail"]
    assert "integer" in changes[0]["detail"]


# ──────────────────────────────────────────────────────────────────────────────
# The granularity trap: a whole node added/removed is ONE change, not N
# ──────────────────────────────────────────────────────────────────────────────

def test_node_added_wholesale_is_reported_once_not_as_n_property_changes():
    recorded = {"": _node(properties={"id": "string"})}
    observed = {
        "": _node(properties={"id": "string", "detail": "object"}),
        "/properties/detail": _node(
            closed=True,
            required=["note", "source"],
            properties={"note": "string", "source": "string", "confidence": "number"},
        ),
    }

    changes = diff_shapes(recorded, observed)

    # Exactly one change accounts for the whole new node...
    node_level = [c for c in changes if c["pointer"] == "/properties/detail"]
    assert len(node_level) == 1
    assert node_level[0]["kind"] == "node_added"
    # ...and no added_property entries exist for the new node's own fields —
    # the granularity trap this test exists to catch.
    assert not any(
        c["pointer"] == "/properties/detail" and c["kind"] == "added_property"
        for c in changes
    )
    # The parent's own new `detail` property is reported once, separately.
    parent_level = [c for c in changes if c["pointer"] == ""]
    assert len(parent_level) == 1
    assert parent_level[0]["kind"] == "added_property"


def test_node_removed_wholesale_is_reported_once_not_as_n_property_changes():
    recorded = {
        "": _node(properties={"id": "string", "detail": "object"}),
        "/properties/detail": _node(
            closed=True,
            required=["note", "source"],
            properties={"note": "string", "source": "string", "confidence": "number"},
        ),
    }
    observed = {"": _node(properties={"id": "string"})}

    changes = diff_shapes(recorded, observed)

    node_level = [c for c in changes if c["pointer"] == "/properties/detail"]
    assert len(node_level) == 1
    assert node_level[0]["kind"] == "node_removed"
    assert not any(
        c["pointer"] == "/properties/detail" and c["kind"] == "removed_property"
        for c in changes
    )
    parent_level = [c for c in changes if c["pointer"] == ""]
    assert len(parent_level) == 1
    assert parent_level[0]["kind"] == "removed_property"


# ──────────────────────────────────────────────────────────────────────────────
# Identical manifests produce an empty list — paired with a mutation test.
# A bare `return []` would pass the first half alone (trap #1); the second
# half proves the function actually detects a real, injected change.
# ──────────────────────────────────────────────────────────────────────────────

def test_identical_manifests_produce_empty_list_and_a_real_change_is_detected():
    nodes = {
        "": _node(
            closed=True,
            required=["id"],
            properties={"id": "string", "title": "string"},
            values={"title": ["a", "b"]},
        ),
        "/properties/nested": _node(properties={"x": "integer"}),
    }

    assert diff_shapes(nodes, nodes) == []

    mutated = json.loads(json.dumps(nodes))  # deep copy, no aliasing
    mutated[""]["properties"]["extra"] = "string"
    changes = diff_shapes(nodes, mutated)

    assert len(changes) == 1
    assert changes[0]["kind"] == "added_property"
    assert changes[0]["pointer"] == ""


# ──────────────────────────────────────────────────────────────────────────────
# Enum/const diffing (PRD F2-AC3's mechanism)
# ──────────────────────────────────────────────────────────────────────────────

def test_added_enum_value_reported_with_pointer_property_and_value():
    recorded = {"": _node(properties={"status": "string"}, values={"status": ["open"]})}
    observed = {
        "": _node(properties={"status": "string"}, values={"status": ["closed", "open"]}),
    }

    changes = diff_shapes(recorded, observed)

    assert len(changes) == 1
    change = changes[0]
    assert change["pointer"] == ""
    assert change["kind"] == "added_enum_value"
    assert "status" in change["detail"]
    assert "closed" in change["detail"]


def test_removed_enum_value_reported():
    recorded = {
        "": _node(properties={"status": "string"}, values={"status": ["closed", "open"]}),
    }
    observed = {"": _node(properties={"status": "string"}, values={"status": ["open"]})}

    changes = diff_shapes(recorded, observed)

    assert len(changes) == 1
    change = changes[0]
    assert change["kind"] == "removed_enum_value"
    assert "status" in change["detail"]
    assert "closed" in change["detail"]


def test_property_gaining_enum_where_it_had_none_is_reported():
    recorded = {"": _node(properties={"status": "string"})}  # no `values` entry at all
    observed = {"": _node(properties={"status": "string"}, values={"status": ["open"]})}

    changes = diff_shapes(recorded, observed)

    assert len(changes) == 1
    assert changes[0]["kind"] == "added_enum_value"
    assert "open" in changes[0]["detail"]


def test_const_widened_to_enum_reports_only_the_added_values():
    # Phase 1 records `const: "open"` as `["open"]` (wire_shape.md, "WHY
    # enum/const Are Recorded"). Widening to `enum: ["open", "closed"]`
    # must show up as ONE added value, nothing else — no kind change, no
    # spurious removal of "open" (it is in both sets).
    recorded = {"": _node(properties={"status": "string"}, values={"status": ["open"]})}
    observed = {
        "": _node(properties={"status": "string"}, values={"status": ["closed", "open"]}),
    }

    changes = diff_shapes(recorded, observed)

    assert len(changes) == 1
    assert changes[0]["kind"] == "added_enum_value"
    assert "closed" in changes[0]["detail"]


# ──────────────────────────────────────────────────────────────────────────────
# Output ordering is pinned, not incidental — T2.3's gate message and
# T4.1's obligation table are built directly off this list.
# ──────────────────────────────────────────────────────────────────────────────

def test_output_is_sorted_by_pointer_then_kind_then_detail():
    # `/a` carries a type_changed AND an openness_changed change. `_diff_node`
    # APPENDS type_changed before openness_changed (the properties loop runs
    # before the closed-comparison), but alphabetically "openness_changed"
    # sorts before "type_changed" — so the two are in opposite order before
    # and after sorting. That flip is what makes this test fail if the sort
    # is ever dropped, regardless of how pointer `/a` vs `/b` happen to
    # iterate without it (set iteration order is not otherwise guaranteed).
    recorded = {
        "/a": _node(closed=False, properties={"x": "string"}),
        "/b": _node(closed=True, properties={"y": "string"}),
    }
    observed = {
        "/a": _node(closed=True, properties={"x": "integer"}),
        "/b": _node(closed=True, properties={"y": "string", "z": "string"}),
    }

    changes = diff_shapes(recorded, observed)

    # Exact sequence, not a set — a set assertion cannot catch reordering.
    assert [(c["pointer"], c["kind"]) for c in changes] == [
        ("/a", "openness_changed"),
        ("/a", "type_changed"),
        ("/b", "added_property"),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Sanity check against the three real committed manifests
# ──────────────────────────────────────────────────────────────────────────────

def test_real_manifests_diff_against_themselves_are_empty():
    for shape_file in sorted(SHAPES_DIR.glob("*.shape.json")):
        nodes = json.loads(shape_file.read_text())["nodes"]
        assert diff_shapes(nodes, nodes) == [], shape_file.name

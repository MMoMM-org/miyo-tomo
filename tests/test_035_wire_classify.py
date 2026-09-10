#!/usr/bin/env python3
# version: 0.1.0
"""test_035_wire_classify.py — Behavioural tests for lib.wire_shape.classify (spec 035 T2.2).

Separate from test_035_wire_diff.py on purpose: that file exercises
diff_shapes() (two node maps in, list[ShapeChange] out); this file exercises
classify() (one ShapeChange + the observed node map in, bool out). Same
split rationale as the diff/shape/manifests split already in this
directory — different subject, different question.

Test method (mandatory, per the task brief): every affecting/not-affecting
test drives its fixture THROUGH diff_shapes() to produce the ShapeChange(s)
under test, never by hand-building a ShapeChange dict. Removing a REQUIRED
property yields TWO changes (removed_property AND required_removed);
removing an OPTIONAL one yields ONE (removed_property alone). The
affecting/not-affecting distinction for a removal therefore lives in the
change SET, not in any single change's kind — `any(classify(c, observed)
for c in changes)` is what separates the two cases, and a lone
removed_property classifies identically (not affecting) in both. Hand-
building a ShapeChange to sidestep this is the exact hand-built-fixture
vacuity this spec keeps finding; it would also tempt "fixing" classify by
handing it `recorded`, which the SDD's signature deliberately excludes —
see wire_shape.py's classify() docstring for why.

Two cases are tested at the diff_shapes layer only (empty list), never by
handing classify a manufactured change, because classify is structurally
never called for them:
- a declared-optional field starting to be emitted (an emission-pattern
  change; describe_shape sees nothing move)
- a prose-only edit (T1.1 excludes descriptions from the record)

Polarity check (also mandatory): a `classify` stubbed to `return True`
passes every affecting-only test and fails every not-affecting one; a
`classify` stubbed to `return False` does the reverse. Both were run by
hand against this suite before committing — see the commit body for the
recorded failure counts, since a stub is not something a docstring can pin
the way an assertion can.

Tests cover:
- the eight measured change classes from PRD/Supporting Research, each
  driven through diff_shapes()
- Rule 8 (openness_changed direction read from `observed`, never `detail`)
- Rule 9 (a wholesale node_added/node_removed, including the oneOf-branch
  shape that emits ONLY a node_added with no accompanying added_property)
- the required_added / required_removed asymmetry (SDD/Application Data
  Models) — required_added is NOT affecting, the rule easiest to get
  backwards
- exhaustiveness: CHANGE_KINDS lists exactly what _change accepts and what
  classify has a rule for; classify raises on an unregistered kind; _change
  raises on a kind not in CHANGE_KINDS (the direction the other checks miss)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.wire_shape import CHANGE_KINDS, classify, diff_shapes  # noqa: E402


def _node(closed=True, required=None, properties=None, values=None) -> dict:
    return {
        "closed": closed,
        "required": sorted(required or []),
        "properties": properties or {},
        "values": values or {},
    }


def _only_change(recorded: dict, observed: dict):
    """Run diff_shapes and assert exactly one change came back — the shape
    every single-fact test in this file needs, so each test body reads as
    "this one fact classifies as X" rather than repeating the same assert.
    """
    changes = diff_shapes(recorded, observed)
    assert len(changes) == 1, changes
    return changes[0]


# ──────────────────────────────────────────────────────────────────────────────
# added_property — Rules 1/2, PRD F2-AC1/F2-AC2
# ──────────────────────────────────────────────────────────────────────────────

def test_property_added_to_closed_node_is_affecting():
    recorded = {"": _node(closed=True, properties={"id": "string"})}
    observed = {"": _node(closed=True, properties={"id": "string", "stem": "string"})}

    change = _only_change(recorded, observed)

    assert change["kind"] == "added_property"
    assert classify(change, observed) is True


def test_property_added_to_open_node_is_not_affecting():
    # The live garden-audit case: getting this wrong makes the detector
    # cry wolf on the one drift that is fine.
    recorded = {"": _node(closed=False, properties={"id": "string"})}
    observed = {"": _node(closed=False, properties={"id": "string", "up_source": "string"})}

    change = _only_change(recorded, observed)

    assert change["kind"] == "added_property"
    assert classify(change, observed) is False


def test_property_added_to_open_node_nested_inside_a_closed_one_is_not_affecting():
    # Edge Case Scenario 1: the nearest enclosing rule that governs the
    # field is the OPEN node's, even though its parent is closed.
    recorded = {
        "": _node(closed=True, properties={"detail": "object"}),
        "/properties/detail": _node(closed=False, properties={"note": "string"}),
    }
    observed = {
        "": _node(closed=True, properties={"detail": "object"}),
        "/properties/detail": _node(
            closed=False, properties={"note": "string", "up_value": "string"},
        ),
    }

    change = _only_change(recorded, observed)

    assert change["pointer"] == "/properties/detail"
    assert classify(change, observed) is False


# ──────────────────────────────────────────────────────────────────────────────
# required removal — Rule 4 / class 4, PRD F2-AC4. Driven through
# diff_shapes so the required/optional distinction lives in the change SET,
# per the task brief's mandatory test method.
# ──────────────────────────────────────────────────────────────────────────────

def test_required_field_removed_is_affecting():
    recorded = _node(required=["id", "stem"], properties={"id": "string", "stem": "string"})
    observed = _node(required=["id"], properties={"id": "string"})

    changes = diff_shapes({"/x": recorded}, {"/x": observed})

    # Two changes, per the task brief: removed_property AND required_removed.
    kinds = {c["kind"] for c in changes}
    assert kinds == {"removed_property", "required_removed"}
    assert any(classify(c, {"/x": observed}) for c in changes)


def test_optional_field_removed_is_not_affecting():
    recorded = _node(required=["id"], properties={"id": "string", "stem": "string"})
    observed = _node(required=["id"], properties={"id": "string"})

    changes = diff_shapes({"/x": recorded}, {"/x": observed})

    # One change only: a lone removed_property, no required_removed.
    assert len(changes) == 1
    assert changes[0]["kind"] == "removed_property"
    assert not any(classify(c, {"/x": observed}) for c in changes)


def test_a_hand_built_lone_removed_property_classifies_the_same_in_both_cases():
    # Documents the trap named in the task brief: a lone removed_property,
    # taken in isolation, cannot and must not distinguish required from
    # optional — that information does not exist without `recorded`, which
    # classify() deliberately never receives. This is what makes driving
    # every removal test through diff_shapes() mandatory rather than a
    # style preference: hand-building ONE removed_property and reading its
    # classification tells you nothing about whether the field was
    # required, because the answer here is always the same.
    change = {"pointer": "/x", "kind": "removed_property", "detail": "removed property: stem"}
    assert classify(change, {"/x": _node()}) is False


# ──────────────────────────────────────────────────────────────────────────────
# required joining — SDD/Application Data Models. Easy to get backwards:
# this wire runs producer -> consumer, so the consumer never SENDS
# anything that could be missing a newly-required field.
# ──────────────────────────────────────────────────────────────────────────────

def test_field_joining_required_is_not_affecting():
    recorded = _node(required=["id"], properties={"id": "string", "item_key": "string"})
    observed = _node(
        required=["id", "item_key"], properties={"id": "string", "item_key": "string"},
    )

    change = _only_change({"/x": recorded}, {"/x": observed})

    assert change["kind"] == "required_added"
    assert classify(change, {"/x": observed}) is False


# ──────────────────────────────────────────────────────────────────────────────
# enum values — Rule 3 / class 5 (added, counter-intuitive) and its
# mirror (removed). Asserted as OPPOSITE outcomes, not merely "both emitted".
# ──────────────────────────────────────────────────────────────────────────────

def test_added_and_removed_enum_value_classify_oppositely():
    recorded = {"": _node(properties={"status": "string"}, values={"status": ["open"]})}
    observed = {
        "": _node(properties={"status": "string"}, values={"status": ["closed", "open"]}),
    }

    added_change = _only_change(recorded, observed)
    assert added_change["kind"] == "added_enum_value"
    added_result = classify(added_change, observed)

    removed_change = _only_change(observed, recorded)
    assert removed_change["kind"] == "removed_enum_value"
    removed_result = classify(removed_change, recorded)

    assert added_result is True
    assert removed_result is False
    assert added_result != removed_result


# ──────────────────────────────────────────────────────────────────────────────
# type_changed — always affecting, independent of openness (class 6)
# ──────────────────────────────────────────────────────────────────────────────

def test_type_changed_is_affecting_on_a_closed_node():
    recorded = {"": _node(closed=True, properties={"id": "string"})}
    observed = {"": _node(closed=True, properties={"id": "integer"})}

    change = _only_change(recorded, observed)

    assert change["kind"] == "type_changed"
    assert classify(change, observed) is True


def test_type_changed_is_affecting_on_an_open_node_too():
    # The rule does not depend on openness at all — assert it holds on the
    # open side as well, so a future "gate it on closed" regression is caught.
    recorded = {"": _node(closed=False, properties={"id": "string"})}
    observed = {"": _node(closed=False, properties={"id": "integer"})}

    change = _only_change(recorded, observed)

    assert change["kind"] == "type_changed"
    assert classify(change, observed) is True


# ──────────────────────────────────────────────────────────────────────────────
# openness_changed — Rule 8. Direction read from `observed`, never `detail`.
# ──────────────────────────────────────────────────────────────────────────────

def test_node_becoming_closed_is_affecting():
    recorded = {"/x": _node(closed=False, properties={"id": "string"})}
    observed = {"/x": _node(closed=True, properties={"id": "string"})}

    change = _only_change(recorded, observed)

    assert change["kind"] == "openness_changed"
    # Fixture sanity: this is genuinely the "became closed" direction.
    assert observed["/x"]["closed"] is True
    assert classify(change, observed) is True


def test_node_becoming_open_is_not_affecting():
    recorded = {"/x": _node(closed=True, properties={"id": "string"})}
    observed = {"/x": _node(closed=False, properties={"id": "string"})}

    change = _only_change(recorded, observed)

    assert change["kind"] == "openness_changed"
    assert observed["/x"]["closed"] is False
    assert classify(change, observed) is False


# ──────────────────────────────────────────────────────────────────────────────
# node_added / node_removed — Rule 9, including the oneOf-branch shape:
# a node addition with NOTHING else, because the parent declares no
# `properties` and is not itself a recorded node.
# ──────────────────────────────────────────────────────────────────────────────

def test_wholesale_node_added_is_affecting():
    recorded = {"": _node(properties={"id": "string"})}
    observed = {
        "": _node(properties={"id": "string", "detail": "object"}),
        "/properties/detail": _node(properties={"note": "string"}),
    }

    changes = diff_shapes(recorded, observed)
    node_change = next(c for c in changes if c["kind"] == "node_added")

    assert classify(node_change, observed) is True


def test_wholesale_node_removed_is_affecting():
    recorded = {
        "": _node(properties={"id": "string", "detail": "object"}),
        "/properties/detail": _node(properties={"note": "string"}),
    }
    observed = {"": _node(properties={"id": "string"})}

    changes = diff_shapes(recorded, observed)
    node_change = next(c for c in changes if c["kind"] == "node_removed")

    assert classify(node_change, observed) is True


def test_new_oneof_branch_emits_only_node_added_and_it_is_affecting():
    # The instructions-wire shape named in Rule 9: a new action kind's
    # $defs entry has no `properties` on ITS parent pointer that changed —
    # the branch is new to the oneOf list, not a new property of an
    # existing node — so this is node_added alone, no added_property
    # riding along to also carry the obligation.
    recorded = {"": {"closed": True, "required": [], "properties": {}, "values": {}}}
    observed = {
        "": {"closed": True, "required": [], "properties": {}, "values": {}},
        "/$defs/move_note": _node(
            required=["operation"], properties={"operation": "string", "id": "string"},
        ),
    }

    changes = diff_shapes(recorded, observed)

    assert len(changes) == 1
    assert changes[0]["kind"] == "node_added"
    assert classify(changes[0], observed) is True


# ──────────────────────────────────────────────────────────────────────────────
# Discharged by absence, not by a rule: classify is never called.
# ──────────────────────────────────────────────────────────────────────────────

def test_optional_field_starting_to_be_emitted_produces_no_change():
    # An emission-pattern change, not a schema change: the field was
    # already declared optional on both sides, so describe_shape sees
    # nothing move. Tested at the diff_shapes layer — there is no
    # ShapeChange to hand classify, by construction.
    node = _node(required=[], properties={"id": "string", "stem": "string"})

    assert diff_shapes({"": node}, {"": node}) == []


def test_prose_only_edit_produces_no_change():
    # T1.1 excludes descriptions/titles from the recorded shape entirely,
    # so a prose-only schema edit is invisible to describe_shape and
    # produces an identical node map — same mechanism, same empty result.
    node = _node(properties={"id": "string"})

    assert diff_shapes({"": node}, {"": node}) == []


# ──────────────────────────────────────────────────────────────────────────────
# Exhaustiveness mechanism (a-d in the task brief)
# ──────────────────────────────────────────────────────────────────────────────

def test_change_kinds_has_exactly_the_ten_documented_kinds():
    assert set(CHANGE_KINDS) == {
        "added_property",
        "removed_property",
        "type_changed",
        "required_added",
        "required_removed",
        "openness_changed",
        "added_enum_value",
        "removed_enum_value",
        "node_added",
        "node_removed",
    }
    assert len(CHANGE_KINDS) == len(set(CHANGE_KINDS)), "CHANGE_KINDS has a duplicate"


def test_classify_returns_a_bool_for_every_change_kind():
    # (c) from the task brief: iterates CHANGE_KINDS itself, not a
    # hand-copied list of the ten kind strings — an eleventh kind added to
    # the constant without a matching rule in classify() then fails this
    # test, because classify() either raises (caught below) or returns a
    # non-bool for it.
    observed = {"/x": _node(closed=True, properties={"id": "string"})}
    for kind in CHANGE_KINDS:
        change = {"pointer": "/x", "kind": kind, "detail": "fixture"}
        result = classify(change, observed)
        assert isinstance(result, bool), f"{kind!r} did not return a bool: {result!r}"


def test_classify_raises_on_an_unregistered_kind():
    # (b): classify must raise, not silently return False, on a kind it
    # has no rule for — a silent False on an unrecognised kind is the
    # exact failure this spec exists to eliminate, one layer past
    # diff_shapes naming the change at all.
    change = {"pointer": "/x", "kind": "moved_to_a_new_planet", "detail": "fixture"}
    with pytest.raises(ValueError):
        classify(change, {"/x": _node()})


def test_change_constructor_rejects_a_kind_not_in_change_kinds():
    # (d): this is the direction (a)-(c) miss on their own — a kind
    # diff_shapes might emit that was never added to CHANGE_KINDS would
    # sail straight past a CHANGE_KINDS-driven exhaustiveness test, since
    # such a test only ever sees what the constant lists. `_change` (used
    # internally by diff_shapes for every ShapeChange it builds) is the
    # place that closes it: reached here via diff_shapes on a node pair
    # that produces a real change, confirming the guard is live on the
    # actual construction path, not merely a unit test of a private helper
    # in isolation.
    import lib.wire_shape as wire_shape

    original_added_property = wire_shape.ADDED_PROPERTY
    try:
        wire_shape.ADDED_PROPERTY = "some_unregistered_kind"
        recorded = {"": _node(properties={"id": "string"})}
        observed = {"": _node(properties={"id": "string", "stem": "string"})}
        with pytest.raises(ValueError):
            diff_shapes(recorded, observed)
    finally:
        wire_shape.ADDED_PROPERTY = original_added_property


# ──────────────────────────────────────────────────────────────────────────────
# Sanity check: the real spec-034 drift, replayed, classifies as affecting.
# ──────────────────────────────────────────────────────────────────────────────

def test_item_key_added_to_closed_suggestions_node_classifies_as_affecting():
    # Replays incident 1 (spec 034): item_key was a NEW property on the
    # suggestions items node, which is closed. Simulates the pre-034
    # baseline by removing it from an in-memory copy of the live manifest.
    import copy
    import json as json_module

    shapes_dir = REPO_ROOT / "tomo" / "schemas" / "shapes"
    live_nodes = json_module.loads(
        (shapes_dir / "suggestions-wire.shape.json").read_text(),
    )["nodes"]

    pointer = "/properties/suggestions/items"
    pre_034_nodes = copy.deepcopy(live_nodes)
    del pre_034_nodes[pointer]["properties"]["item_key"]
    pre_034_nodes[pointer]["required"] = [
        r for r in pre_034_nodes[pointer]["required"] if r != "item_key"
    ]

    changes = diff_shapes(pre_034_nodes, live_nodes)
    relevant = [c for c in changes if c["pointer"] == pointer]

    assert any(c["kind"] == "added_property" for c in relevant)
    assert any(classify(c, live_nodes) for c in relevant)

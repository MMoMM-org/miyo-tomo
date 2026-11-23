#!/usr/bin/env python3
# version: 0.1.0
"""test_review_proposals_carried_schema.py — spec 047 T5.1: `carried` and `carried_ids` in the proposals schema.

Validates against ``tomo/schemas/review-proposals.schema.json`` directly, without ``review-doc.py``
(SDD Application Data Models, Proposals; ADR-6). Group items (``$defs/items``) and section items
(``$defs/sectionItem``) gain the optional ``carried`` (``done | still_open | not_mentioned``) and
``carried_ids`` (≥ 1 id ``^c[0-9]{1,3}$``); the two come together (``dependentRequired`` both ways).

Pinned here:
- a group item and a section item (also one with a child ``mark``) with both fields validate;
- either field without the other is refused, at both nodes;
- a value outside the enum and an id outside the pattern are refused — the pattern end to end: both
  anchors, both bounds of ``{1,3}``, the literal ``c`` and the class ``[0-9]`` (a full-width digit
  kills a ``\\d`` mutant, ``c:`` a ``.`` mutant);
- a tree walk over a full proposals document refuses, for every node carrying the fields, a wrong
  type, an empty string / empty array and an unknown key;
- a guard on the schema itself: the places carrying ``pattern``, the new fields and ``dependentRequired``;
- every proposals fixture of specs 045/046 (module constants and builders, globbed) still validates.

Known limit, accepted by the spec: jsonschema evaluates ``pattern`` with Python ``re.search``, where
``$`` also matches before a trailing ``\\n`` — ``"c1\\n"`` passes the schema. Such an id matches no
carryover id and is refused by the document check (``carried-unknown``), so it is not tested here.
"""
from __future__ import annotations

import copy
import importlib
import inspect
import json
import sys
from pathlib import Path

import jsonschema
import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

SCHEMA_PATH = TESTS_DIR.parent / "tomo" / "schemas" / "review-proposals.schema.json"
CARRIED_VALUES = ("done", "still_open", "not_mentioned")
NEW_FIELDS = ("carried", "carried_ids")


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator() -> jsonschema.Draft202012Validator:
    schema = _schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _item(**extra) -> dict:
    return {"text": "Call Jana about the trip", "sources": ["2026-03-31", "2026-W13"], **extra}


# One of every nested object that carries the new fields: a group item, a section item, a section item with a mark.
FULL = {
    "language": "en",
    "groups": {
        "done": [_item(carried="done", carried_ids=["c1"])],
        "open": [_item(carried="still_open", carried_ids=["c2", "c3"]), _item()],
        "themes": [_item(carried="not_mentioned", carried_ids=["c4"])],
    },
    "sections": [{"key": "s1", "items": [
        _item(carried="still_open", carried_ids=["c5"]),
        _item(mark="not_in_weekly", carried="done", carried_ids=["c6"]),
    ]}],
}
# JSON-pointer-like paths of the carrying nodes in FULL
CARRYING = {
    ("groups", "done", 0): "group item",
    ("groups", "open", 0): "group item",
    ("groups", "themes", 0): "group item",
    ("sections", 0, "items", 0): "section item",
    ("sections", 0, "items", 1): "section item with mark",
}


def _get(doc, path):
    for key in path:
        doc = doc[key]
    return doc


def _with_node(path, change) -> dict:
    doc = copy.deepcopy(FULL)
    change(_get(doc, path))
    return doc


def _group_doc(item: dict) -> dict:
    return {"language": "en", "groups": {"open": [item]}}


def _section_doc(item: dict) -> dict:
    return {"language": "en", "groups": {}, "sections": [{"key": "s1", "items": [item]}]}


NODES = {"group": _group_doc, "section": _section_doc}


def _refused(validator, doc) -> None:
    assert not validator.is_valid(doc), f"schema accepted a document it must refuse: {doc}"


# ── accepted ──


def test_the_full_document_validates(validator):
    validator.validate(FULL)


def test_the_tree_walk_finds_every_carrying_node():
    found = set()

    def walk(node, path):
        if isinstance(node, dict):
            if any(f in node for f in NEW_FIELDS):
                found.add(path)
            for k, v in node.items():
                walk(v, path + (k,))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + (i,))

    walk(FULL, ())
    assert found == set(CARRYING), found


@pytest.mark.parametrize("node", NODES)
@pytest.mark.parametrize("value", CARRIED_VALUES)
def test_every_carried_value_validates_on_both_nodes(validator, node, value):
    validator.validate(NODES[node](_item(carried=value, carried_ids=["c1"])))


@pytest.mark.parametrize("node", NODES)
@pytest.mark.parametrize("cid", ["c0", "c1", "c9", "c10", "c99", "c123", "c999"])
def test_an_id_of_one_to_three_digits_validates(validator, node, cid):
    validator.validate(NODES[node](_item(carried="done", carried_ids=[cid])))


@pytest.mark.parametrize("node", NODES)
def test_several_ids_validate(validator, node):
    validator.validate(NODES[node](_item(carried="still_open", carried_ids=["c1", "c2", "c30"])))


@pytest.mark.parametrize("node", NODES)
def test_an_item_without_either_field_still_validates(validator, node):
    validator.validate(NODES[node](_item()))


@pytest.mark.parametrize("mark", ["weekly_only", "not_in_weekly", "monthly_only", "not_in_monthly"])
def test_a_section_item_may_carry_a_child_mark_and_a_carried_mark(validator, mark):
    validator.validate(_section_doc(_item(mark=mark, carried="done", carried_ids=["c1"])))


# ── refused: the pair ──


@pytest.mark.parametrize("node", NODES)
def test_carried_without_carried_ids_is_refused(validator, node):
    _refused(validator, NODES[node](_item(carried="done")))


@pytest.mark.parametrize("node", NODES)
def test_carried_ids_without_carried_is_refused(validator, node):
    _refused(validator, NODES[node](_item(carried_ids=["c1"])))


# ── refused: the values ──


@pytest.mark.parametrize("node", NODES)
@pytest.mark.parametrize("value", ["open", "Done", "still open", "notmentioned", "done ", "", "weekly_only"])
def test_a_carried_value_outside_the_enum_is_refused(validator, node, value):
    _refused(validator, NODES[node](_item(carried=value, carried_ids=["c1"])))


@pytest.mark.parametrize("node", NODES)
@pytest.mark.parametrize(
    "cid",
    [
        "c",            # {1,3}: the lower bound
        "c1234",        # {1,3}: the upper bound
        "C1", "d1", "1", "11",  # the literal c
        "xc1", " c1",   # ^: text before the id
        "c1x", "c1 ",   # $: text after the id
        "c/", "c:",     # [0-9]: a non-digit just below "0", just above "9" (kills `.`)
        "c１",      # [0-9]: a full-width digit (kills `\d`)
        "c-1", "",
    ],
)
def test_an_id_outside_the_pattern_is_refused(validator, node, cid):
    _refused(validator, NODES[node](_item(carried="done", carried_ids=[cid])))


@pytest.mark.parametrize("node", NODES)
def test_an_id_outside_the_pattern_is_refused_beside_a_good_one(validator, node):
    _refused(validator, NODES[node](_item(carried="done", carried_ids=["c1", "c1x"])))


# ── refused: the tree walk ──

_NODE_MUTATIONS = {
    "carried int": lambda n: n.update(carried=1),
    "carried list": lambda n: n.update(carried=["done"]),
    "carried null": lambda n: n.update(carried=None),
    "carried empty string": lambda n: n.update(carried=""),
    "carried_ids string": lambda n: n.update(carried_ids="c1"),
    "carried_ids object": lambda n: n.update(carried_ids={"c1": True}),
    "carried_ids null": lambda n: n.update(carried_ids=None),
    "carried_ids empty array": lambda n: n.update(carried_ids=[]),
    "carried_ids int item": lambda n: n.update(carried_ids=[1]),
    "carried_ids null item": lambda n: n.update(carried_ids=[None]),
    "carried_ids empty-string item": lambda n: n.update(carried_ids=[""]),
    "carried_ids nested array": lambda n: n.update(carried_ids=[["c1"]]),
    "unknown key": lambda n: n.update(carried_from="2026-W13"),
    "carried dropped": lambda n: n.pop("carried"),
    "carried_ids dropped": lambda n: n.pop("carried_ids"),
}


@pytest.mark.parametrize("mutation", _NODE_MUTATIONS)
@pytest.mark.parametrize("path", CARRYING, ids=[f"{v}@{'/'.join(map(str, k))}" for k, v in CARRYING.items()])
def test_every_carrying_node_refuses_each_mutation(validator, path, mutation):
    _refused(validator, _with_node(path, _NODE_MUTATIONS[mutation]))


# ── the guard: where the schema carries pattern, the new fields and dependentRequired ──


def _walk_schema(node, pointer=""):
    if isinstance(node, dict):
        yield pointer, node
        for k, v in node.items():
            yield from _walk_schema(v, f"{pointer}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_schema(v, f"{pointer}/{i}")


def test_the_places_with_a_pattern_are_pinned():
    schema = _schema()
    found = {p: n["pattern"] for p, n in _walk_schema(schema) if isinstance(n.get("pattern"), str)}
    assert found == {
        "/properties/sections/items/properties/key": "^s[0-9]{1,3}$",
        "/$defs/carriedIds/items": "^c[0-9]{1,3}$",
    }, found


def test_the_places_with_the_new_fields_are_pinned():
    schema = _schema()
    carrying = {}
    for pointer, node in _walk_schema(schema):
        props = node.get("properties")
        if isinstance(props, dict) and any(f in props for f in NEW_FIELDS):
            carrying[pointer] = {f: props.get(f) for f in NEW_FIELDS}
    expected = {"carried": {"$ref": "#/$defs/carried"}, "carried_ids": {"$ref": "#/$defs/carriedIds"}}
    assert carrying == {"/$defs/items/items": expected, "/$defs/sectionItem": expected}, carrying
    carried = {k: v for k, v in schema["$defs"]["carried"].items() if k != "description"}
    assert carried == {"enum": list(CARRIED_VALUES)}, carried
    ids = {k: v for k, v in schema["$defs"]["carriedIds"].items() if k != "description"}
    assert ids == {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": "^c[0-9]{1,3}$"}}, ids


def test_dependent_required_sits_on_both_nodes_both_ways():
    schema = _schema()
    found = {p: n["dependentRequired"] for p, n in _walk_schema(schema) if "dependentRequired" in n}
    both = {"carried": ["carried_ids"], "carried_ids": ["carried"]}
    assert found == {"/$defs/items/items": both, "/$defs/sectionItem": both}, found
    for pointer in found:
        node = dict(_walk_schema(schema))[pointer]
        assert node["additionalProperties"] is False, pointer
        assert node["required"] == ["text", "sources"], pointer


# ── every proposals fixture of specs 045/046 still validates ──

FIXTURE_GLOBS = ("review_*.py", "e2e_04[56]_*.py", "test_045_*.py", "test_046_*.py", "test_review_*.py")
_KINDS = ("week", "month", "quarter")


def _looks_like_proposals(value) -> bool:
    return isinstance(value, dict) and "language" in value and "groups" in value


def _builder_calls(module, fn):
    """Every call of a ``proposals`` builder over its kinds; an unknown signature fails, never skips."""
    params = [p for p in inspect.signature(fn).parameters.values()
              if p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    names = [p.name for p in params]
    if not names:
        return [("()", fn())]
    if names == ["kind"]:
        return [(f"({k!r})", fn(k)) for k in _KINDS]
    if names == ["k", "version"] and hasattr(module, "KINDS"):
        return [(f"({k.kind}, 'v1')", fn(k, "v1")) for k in module.KINDS.values()]
    raise AssertionError(f"{module.__name__}.proposals has an unknown signature {names}: add its kinds here")


def _fixtures() -> list[tuple[str, dict]]:
    found = []
    files = sorted({f for g in FIXTURE_GLOBS for f in TESTS_DIR.glob(g)} - {Path(__file__).resolve()})
    for path in files:
        module = importlib.import_module(path.stem)
        for name, value in vars(module).items():
            if _looks_like_proposals(value):
                found.append((f"{path.stem}.{name}", value))
            elif name == "proposals" and callable(value) and getattr(value, "__module__", None) == path.stem:
                found += [(f"{path.stem}.proposals{args}", doc) for args, doc in _builder_calls(module, value)]
    return found


def test_every_spec_045_046_proposals_fixture_still_validates(validator):
    fixtures = _fixtures()
    names = [n for n, _ in fixtures]
    assert len(fixtures) > 0, f"the glob {FIXTURE_GLOBS} found no proposals fixture"
    failures = {n: [e.message for e in validator.iter_errors(doc)] for n, doc in fixtures if not validator.is_valid(doc)}
    assert not failures, f"invalid: {failures}\nall {len(names)} found: {names}"
    # the builders of both fake vaults are among them, so a renamed builder cannot drop out silently
    for expected in ("review_privacy_fixture.proposals('quarter')", "e2e_046_sections_walk.proposals(quarter, 'v1')",
                     "review_deliver_helpers.PROPS"):
        assert expected in names, f"{expected} missing from all {len(names)} found: {names}"

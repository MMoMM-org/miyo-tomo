# wire_shape.py — Shape manifest for a wire schema: describe / diff / classify (spec 035).
# version: 0.2.0
"""Pure schema-shape helpers shared by the wire-shape CLI and its tests.

describe_shape(schema) -> dict[pointer, NodeShape] is implemented here (T1.1).
diff_shapes and classify are Phase 2 and are not implemented yet — do not stub
them.
"""
from __future__ import annotations

import json

__all__ = ["describe_shape"]

# Sentinel distinct from a legitimate JSON value (including `null`, `False`,
# `0`, `""`) that a schema keyword can hold. `dict.get(key, default)` cannot
# tell "declared as null" from "not declared" when default is None.
_MISSING = object()


def _resolve_pointer(root: dict, ref: str):
    """Resolve a LOCAL `#/a/b/c` JSON pointer against the schema root.

    Returns None for anything that does not resolve to a dict.
    describe_shape never fetches, so a non-local `$ref` (checked by the
    caller) or a pointer that walks off the document both end up recording
    `"any"` rather than raising or reaching out over the network.
    """
    node = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, dict) else None


def _effective(child: dict, key: str, root: dict):
    """The value of `key` on `child`, chasing a LOCAL `$ref` chain when
    `child` does not declare it directly. Returns `_MISSING` when `key` is
    not declared inline and not reachable through a local `$ref`.

    Inline always wins: a sibling key next to `$ref` is checked BEFORE the
    ref is followed, so `{"$ref": "#/$defs/x", "type": "integer"}` records
    `integer` even when `$defs/x` says otherwise — the property's own
    schema is deliberately narrowing or overriding what it points to.

    A `$ref` chain that revisits a pointer it has already followed returns
    `_MISSING` rather than looping forever — describe_shape stays pure and
    total, never hanging on a cyclic schema.
    """
    node = child
    seen: set[str] = set()
    while True:
        if key in node:
            return node[key]
        ref = node.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            return _MISSING
        seen.add(ref)
        target = _resolve_pointer(root, ref)
        if target is None:
            return _MISSING
        node = target


def _property_type(child: dict, root: dict):
    """Effective JSON-Schema `type` for one property: inline, or resolved
    through a local `$ref` chain, or the `"any"` placeholder when neither
    declares one. May return a list — the caller sorts and copies it.
    """
    raw = _effective(child, "type", root)
    return "any" if raw is _MISSING else raw


def _value_sort_key(value):
    """Total order across mixed JSON scalar types (str / int / float / bool /
    None / ...).

    A bare `sorted()` raises `TypeError` comparing across types (`None` vs
    `str`, `bool` vs `int`), and real wire enums are not guaranteed
    homogeneous forever just because today's are. Grouping by type name
    first, then by a canonical JSON encoding, gives a total order that is
    stable across runs without leaning on Python's cross-type comparison
    rules (which mostly don't exist).
    """
    return (type(value).__name__, json.dumps(value, sort_keys=True))


def _property_values(child: dict, root: dict):
    """Sorted enum/const values for one property, or None when it declares
    neither (inline or through a local `$ref`).

    `const: X` is JSON-Schema-equivalent to `enum: [X]` (a set of exactly
    one value), so it is recorded the same way — a const widened to an enum
    later then shows up as an *added value*, not as a change of kind that
    the classifier would need a second rule to recognise.
    """
    raw_enum = _effective(child, "enum", root)
    if raw_enum is not _MISSING and isinstance(raw_enum, list):
        return sorted(raw_enum, key=_value_sort_key)
    raw_const = _effective(child, "const", root)
    if raw_const is not _MISSING:
        return [raw_const]
    return None


def describe_shape(schema: dict) -> dict:
    """Every object node in a schema, by JSON pointer, with the facts that
    decide whether a consumer breaks.

    `closed` is the discriminator for an ADDED property: measured against the
    consumer's own validator across eight change classes, it is what separates
    "add a field and break them" from "add a field and do not".

    Descriptions are deliberately absent — the consumer's validator ignores
    prose, and recording it would fail the check on edits that oblige nobody,
    which is how a detector becomes one nobody reads. Types and enum/const
    VALUES are recorded: a type change is consumer-affecting in its own
    right, and so is a value added to an enumerated set (PRD F2-AC3) —
    independent of the containing node's openness.
    """
    nodes: dict[str, dict] = {}

    def walk(node: dict, pointer: str) -> None:
        if not isinstance(node, dict):
            return
        props = node.get("properties")
        if isinstance(props, dict):
            properties: dict[str, object] = {}
            values: dict[str, list] = {}
            for name, child in sorted(props.items()):
                child = child or {}
                raw_type = _property_type(child, schema)
                # `type` is semantically an unordered SET when it is a list
                # (JSON Schema), so a reordering is a no-op change that
                # should never show as a diff — sort it. sorted() also
                # returns a NEW list, so the manifest never aliases a list
                # that lives inside the input schema; do not "optimise"
                # this back into a bare assignment.
                properties[name] = sorted(raw_type) if isinstance(raw_type, list) else raw_type
                entry = _property_values(child, schema)
                if entry is not None:
                    values[name] = entry
            nodes[pointer] = {
                # A JSON-Schema node with no additionalProperties defaults to
                # permissive. Recording the effective value, not the literal
                # one, keeps the classification honest for a node that never
                # declared it.
                "closed": node.get("additionalProperties") is False,
                "required": sorted(node.get("required") or []),
                "properties": properties,
                # Always a dict, present on every node. An entry exists
                # ONLY for a property that declares enum/const — no empty
                # lists for the rest.
                "values": values,
            }
            for name, child in props.items():
                # Real RFC 6901 pointer, with the `properties` segment kept in.
                # Dropping it collapses a property literally named `items` (or
                # `contains`/`$defs`/`definitions`/`allOf`/`anyOf`/`oneOf`/
                # `if`/`then`/`else`) onto the sibling structural keyword of
                # the same name — see docs/tomo/scripts/lib/wire_shape.md.
                walk(child, f"{pointer}/properties/{name}")
        for key in ("items", "contains"):
            if key in node:
                walk(node[key], f"{pointer}/{key}")
        for key in ("if", "then", "else"):
            if key in node:
                walk(node[key], f"{pointer}/{key}")
        for key in ("$defs", "definitions"):
            for name, child in (node.get(key) or {}).items():
                walk(child, f"{pointer}/{key}/{name}")
        for key in ("allOf", "anyOf", "oneOf"):
            for i, child in enumerate(node.get(key) or []):
                walk(child, f"{pointer}/{key}/{i}")

    walk(schema, "")
    return nodes

# wire_shape.py — Shape manifest for a wire schema: describe / diff / classify (spec 035).
# version: 0.4.0
"""Pure schema-shape helpers shared by the wire-shape CLI and its tests.

describe_shape(schema) -> dict[pointer, NodeShape] is implemented here (T1.1).
PUBLISHED_WIRES, build_manifest and serialize_manifest (T1.2) wrap that node
map in the committed manifest-file shape. diff_shapes (T2.1) names what moved
between two node maps. classify is Phase 2's next task (T2.2) and is not
implemented yet — do not stub it.
"""
from __future__ import annotations

import json

__all__ = [
    "describe_shape",
    "PUBLISHED_WIRES",
    "build_manifest",
    "serialize_manifest",
    "diff_shapes",
]

# The three published wires (SDD/Data Storage Changes) — the single source of
# truth for which schemas get a manifest. Generation and every test read this
# tuple; the internal-schema-has-no-manifest check derives its list as
# everything in tomo/schemas/ NOT named here, so a fourth published wire is
# covered by adding one line, not by updating a registry and a test in
# lockstep. See docs/tomo/scripts/lib/wire_shape.md.
PUBLISHED_WIRES = (
    "suggestions-wire.schema.json",
    "instructions.schema.json",
    "garden-audit-wire.schema.json",
)

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


def build_manifest(schema: dict, source: str) -> dict:
    """Wrap `describe_shape`'s node map in the committed manifest-file shape
    (SDD/Data Storage Changes): `schema_version` (the value the schema itself
    currently declares at `properties.schema_version.const` — never a value
    supplied by the caller, so the manifest cannot silently drift from what
    the schema actually says), `source` (the schema file this describes,
    caller-supplied so this function stays free of path conventions), `nodes`
    (`describe_shape`'s output, verbatim).
    """
    return {
        "schema_version": schema["properties"]["schema_version"]["const"],
        "source": source,
        "nodes": describe_shape(schema),
    }


def _change(pointer: str, kind: str, detail: str) -> dict:
    """One `ShapeChange`. `consumer_affecting` is always `False` here — T2.2's
    `classify(change, observed)` decides that field; `diff_shapes` never
    pre-judges it. See docs/tomo/scripts/lib/wire_shape.md for why.
    """
    return {"pointer": pointer, "kind": kind, "detail": detail, "consumer_affecting": False}


def _diff_node(pointer: str, old: dict, new: dict) -> list:
    """Field-by-field diff of two `NodeShape`s known to exist on both sides.
    Never called for a pointer that is wholly added or removed — see
    `diff_shapes`, which branches on node presence before this runs.
    """
    changes: list[dict] = []

    old_properties = old.get("properties") or {}
    new_properties = new.get("properties") or {}
    for name in sorted(set(new_properties) - set(old_properties)):
        changes.append(_change(pointer, "added_property", f"added property: {name}"))
    for name in sorted(set(old_properties) - set(new_properties)):
        changes.append(_change(pointer, "removed_property", f"removed property: {name}"))
    for name in sorted(set(old_properties) & set(new_properties)):
        if old_properties[name] != new_properties[name]:
            changes.append(_change(
                pointer, "type_changed",
                f"{name}: {old_properties[name]} -> {new_properties[name]}",
            ))

    old_required = old.get("required") or []
    new_required = new.get("required") or []
    if old_required != new_required:
        changes.append(_change(
            pointer, "required_changed", f"required: {old_required} -> {new_required}",
        ))

    old_closed = bool(old.get("closed"))
    new_closed = bool(new.get("closed"))
    if old_closed != new_closed:
        changes.append(_change(
            pointer, "openness_changed", f"closed: {old_closed} -> {new_closed}",
        ))

    old_values = old.get("values") or {}
    new_values = new.get("values") or {}
    for name in sorted(set(old_values) | set(new_values)):
        old_set = set(old_values.get(name, []))
        new_set = set(new_values.get(name, []))
        for value in sorted(new_set - old_set, key=_value_sort_key):
            changes.append(_change(
                pointer, "added_enum_value", f"{name}: added value {value!r}",
            ))
        for value in sorted(old_set - new_set, key=_value_sort_key):
            changes.append(_change(
                pointer, "removed_enum_value", f"{name}: removed value {value!r}",
            ))

    return changes


def diff_shapes(recorded: dict, observed: dict) -> list:
    """What moved between two `describe_shape` node maps, as `ShapeChange`
    dicts (`pointer`, `kind`, `detail`, `consumer_affecting`).

    `recorded` is the committed manifest's `nodes` — the baseline. `observed`
    is a fresh `describe_shape` of the live schema. "Added" means present in
    `observed`, absent from `recorded`; the argument order and the names are
    the direction, so do not swap them at a call site.

    A pointer present in only one map is `node_added` or `node_removed`,
    reported ONCE — never decomposed into per-property changes for that
    pointer, because a wholesale node addition is one fact, not N. Only a
    pointer present in BOTH maps is diffed field-by-field (`_diff_node`) for
    added/removed properties, a type change, a `required` change, an
    openness change, and added/removed enum values.

    `consumer_affecting` is always `False` on every returned change — that
    field belongs to T2.2's `classify(change, observed)`, not to this
    function. See docs/tomo/scripts/lib/wire_shape.md for why deciding it
    here would be a second rule table.

    Pure: no I/O. Deterministic: the returned list is sorted by
    `(pointer, kind, detail)` — same reasoning as `required`/`values` being
    sorted in `describe_shape` itself, so a change list never differs
    between two runs over the same two inputs and a real drift's failure
    message reads the same way every time.
    """
    changes: list[dict] = []
    recorded_pointers = set(recorded)
    observed_pointers = set(observed)

    for pointer in observed_pointers - recorded_pointers:
        changes.append(_change(pointer, "node_added", f"node added: {pointer}"))
    for pointer in recorded_pointers - observed_pointers:
        changes.append(_change(pointer, "node_removed", f"node removed: {pointer}"))

    for pointer in recorded_pointers & observed_pointers:
        changes.extend(_diff_node(pointer, recorded[pointer], observed[pointer]))

    changes.sort(key=lambda change: (change["pointer"], change["kind"], change["detail"]))
    return changes


def serialize_manifest(manifest: dict) -> str:
    """The ONE encoding used both to write a committed manifest file and to
    regenerate content for the round-trip test's comparison — the SAME
    serializer on both sides is what makes "byte-for-byte" (PRD F1-AC5)
    checkable at all; two independently-chosen encoders would drift on
    whitespace alone regardless of whether the recorded shape agrees.

    2-space indent; `sort_keys=True` so dict-insertion order (an accident of
    how `describe_shape` built the node) is never itself a source of diff
    noise; `ensure_ascii=False` since a manifest holds structural data, not
    prose, so there is nothing to escape and every reviewer sees the same
    bytes as this function; one trailing newline, matching every other
    committed JSON file in this repo.
    """
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

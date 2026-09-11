# wire_shape.py — Shape manifest for a wire schema: describe / diff / classify (spec 035).
# version: 0.9.1
"""Pure schema-shape helpers shared by the wire-shape CLI and its tests.

describe_shape(schema) -> dict[pointer, NodeShape] is implemented here (T1.1).
PUBLISHED_WIRES, build_manifest and serialize_manifest (T1.2) wrap that node
map in the committed manifest-file shape. diff_shapes (T2.1) names what moved
between two node maps. classify (T2.2) decides which of those moves oblige
the consumer to act. manifest_filename (T4.1) is the one place the
`X.schema.json` -> `X.shape.json` naming convention is written down — see
docs/tomo/scripts/lib/wire_shape.md. wire_gate.py's gate and T2.3's drift
check are the next layer up and are not implemented here — do not stub them.
"""
from __future__ import annotations

import json

__all__ = [
    "describe_shape",
    "PUBLISHED_WIRES",
    "build_manifest",
    "serialize_manifest",
    "manifest_filename",
    "diff_shapes",
    "CHANGE_KINDS",
    "classify",
]

# The ten ShapeChange kinds `diff_shapes` can emit — the single vocabulary
# `_change` validates against and `classify` must have a rule for every
# member of, the same single-source rule `PUBLISHED_WIRES` follows above.
# Named constants (not bare strings at each call site) so a kind used by
# `_diff_node`/`diff_shapes` and a kind checked by `classify` are the SAME
# Python object, not two independently-typed strings that could drift.
# See docs/tomo/scripts/lib/wire_shape.md, "WHY CHANGE_KINDS Is One Constant".
ADDED_PROPERTY = "added_property"
REMOVED_PROPERTY = "removed_property"
TYPE_CHANGED = "type_changed"
REQUIRED_ADDED = "required_added"
REQUIRED_REMOVED = "required_removed"
OPENNESS_CHANGED = "openness_changed"
ADDED_ENUM_VALUE = "added_enum_value"
REMOVED_ENUM_VALUE = "removed_enum_value"
NODE_ADDED = "node_added"
NODE_REMOVED = "node_removed"

CHANGE_KINDS = (
    ADDED_PROPERTY,
    REMOVED_PROPERTY,
    TYPE_CHANGED,
    REQUIRED_ADDED,
    REQUIRED_REMOVED,
    OPENNESS_CHANGED,
    ADDED_ENUM_VALUE,
    REMOVED_ENUM_VALUE,
    NODE_ADDED,
    NODE_REMOVED,
)

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
                if child and not isinstance(child, dict):
                    # Malformed: JSON Schema requires an object (or a
                    # falsy value — None/{}/[]/""/0 — meaning "no
                    # constraint") here. `child or {}` below only guards
                    # FALSY wrong types; a TRUTHY one (a string, a
                    # non-zero number, a non-empty list) would otherwise
                    # reach `_property_type`/`_property_values` and raise
                    # from inside them. Skip the property rather than
                    # dereference it — describe_shape already declares
                    # this tolerance at the top of `walk` for a
                    # malformed NODE; this is that same contract applied
                    # to a malformed property CHILD. See
                    # docs/tomo/scripts/lib/wire_shape.md.
                    continue
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
            # `isinstance` check, not `node.get(key) or {}).items()` — the
            # `or {}` only guards a FALSY wrong type (None, {}); a TRUTHY
            # one (a string, a list, a number, True) is not a dict and has
            # no `.items()`, so it used to raise `AttributeError` straight
            # out of describe_shape. Same trap as the properties-child fix
            # above, same fix shape: skip a malformed section rather than
            # dereference it. See docs/tomo/scripts/lib/wire_shape.md.
            section = node.get(key)
            if isinstance(section, dict):
                for name, child in section.items():
                    walk(child, f"{pointer}/{key}/{name}")
        for key in ("allOf", "anyOf", "oneOf"):
            # Same reasoning, `list` instead of `dict`: JSON Schema
            # requires an array here. `node.get(key) or []` only guards a
            # falsy wrong type; a truthy non-iterable one (a number, True)
            # is not iterable at all and `enumerate(...)` raised
            # `TypeError`. A truthy but ITERABLE wrong type (a string, a
            # dict) happened not to crash — each "child" it produced was
            # never a dict, so the recursive `walk` call's own
            # `isinstance` guard silently no-opped — but it is still not
            # what the schema format allows here, so the explicit `list`
            # check is the correct rule regardless of whether a given
            # wrong type happened to survive by accident.
            section = node.get(key)
            if isinstance(section, list):
                for i, child in enumerate(section):
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

    Raises `ValueError` naming `source` when `properties.schema_version.const`
    is missing — either because the path isn't there at all, or because the
    version is declared as an `enum` (or anything else) rather than a
    `const`. Harmless while the only callers are the three published wires,
    which all declare it correctly; load-bearing the moment a CLI (T4.1)
    feeds this function a path a person typed, where a bare `KeyError('const')`
    naming no document is illegible.

    The MESSAGE WORDING deliberately matches
    `wire_version.wire_schema_version`'s treatment of the identical missing
    key ("has no properties.schema_version.const to read") — the exception
    TYPE does not: that function raises `KeyError`, this one raises
    `ValueError` (per plan T4.1's explicit instruction). Do not read "same
    wording" as "same type" — `scripts/wire-shape.py`'s top-level handler
    catches `ValueError` specifically because this function raises one; a
    caller relying on the docstring alone to assume `KeyError` here would
    write a `try`/`except` that never fires. See
    docs/tomo/scripts/lib/wire_shape.md.
    """
    try:
        schema_version = schema["properties"]["schema_version"]["const"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"{source}: has no properties.schema_version.const to read"
        ) from exc
    return {
        "schema_version": schema_version,
        "source": source,
        "nodes": describe_shape(schema),
    }


def manifest_filename(schema_filename: str) -> str:
    """The committed manifest's filename for a published wire's schema
    filename — `<stem>.shape.json` alongside `<stem>.schema.json`, matching
    the layout `tomo/schemas/shapes/` already uses (T1.2).

    The single place this naming convention is written down. Previously
    duplicated once in `wire_gate.py` and a second time (by hand, as inline
    string-slicing) in `tests/test_035_wire_manifests.py`'s `_manifest_path`
    — both now call this function instead. See
    docs/tomo/scripts/lib/wire_shape.md.
    """
    stem = schema_filename[: -len(".schema.json")]
    return f"{stem}.shape.json"


def _change(pointer: str, kind: str, detail: str) -> dict:
    """One `ShapeChange`. `consumer_affecting` is always `False` here — T2.2's
    `classify(change, observed)` decides that field; `diff_shapes` never
    pre-judges it. See docs/tomo/scripts/lib/wire_shape.md for why.

    Validates `kind` against `CHANGE_KINDS` before constructing anything.
    This is the exhaustiveness mechanism's other half: a test can assert
    `classify` handles every kind `CHANGE_KINDS` lists, but that only ever
    sees what the constant lists — a kind `diff_shapes` emits WITHOUT ever
    being added to `CHANGE_KINDS` would slip past that test entirely and
    reach `classify` unclassified. Catching it here, at the one place every
    `ShapeChange` is built, means the vocabulary cannot drift out from under
    itself. See docs/tomo/scripts/lib/wire_shape.md.
    """
    if kind not in CHANGE_KINDS:
        raise ValueError(
            f"_change: {kind!r} is not a member of CHANGE_KINDS. If this is "
            "a legitimate new kind, add it to CHANGE_KINDS and give it a "
            "branch in classify() before emitting it from here.",
        )
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
        changes.append(_change(pointer, ADDED_PROPERTY, f"added property: {name}"))
    for name in sorted(set(old_properties) - set(new_properties)):
        changes.append(_change(pointer, REMOVED_PROPERTY, f"removed property: {name}"))
    for name in sorted(set(old_properties) & set(new_properties)):
        if old_properties[name] != new_properties[name]:
            changes.append(_change(
                pointer, TYPE_CHANGED,
                f"{name}: {old_properties[name]} -> {new_properties[name]}",
            ))

    # Two kinds, not one `required_changed` — a field LEAVING `required` and
    # a field JOINING it classify OPPOSITELY against the consumer's
    # validator (same reasoning as added_enum_value/removed_enum_value
    # below): leaving means we may stop emitting a field they still
    # require (affecting); joining means we now always emit a field they
    # already accepted as optional (not affecting). `classify` sees only
    # `observed`, never `recorded`, so it cannot re-derive which way the
    # list moved — the direction has to be decided here, where both sides
    # still exist. See docs/tomo/scripts/lib/wire_shape.md.
    old_required = set(old.get("required") or [])
    new_required = set(new.get("required") or [])
    for name in sorted(new_required - old_required):
        changes.append(_change(pointer, REQUIRED_ADDED, f"required gained: {name}"))
    for name in sorted(old_required - new_required):
        changes.append(_change(pointer, REQUIRED_REMOVED, f"required lost: {name}"))

    old_closed = bool(old.get("closed"))
    new_closed = bool(new.get("closed"))
    if old_closed != new_closed:
        changes.append(_change(
            pointer, OPENNESS_CHANGED, f"closed: {old_closed} -> {new_closed}",
        ))

    old_values = old.get("values") or {}
    new_values = new.get("values") or {}
    for name in sorted(set(old_values) | set(new_values)):
        # Keyed on _value_sort_key, NOT on the raw values themselves. A
        # bare `set(values)` uses Python equality/hash, where `1 == True`
        # and `hash(1) == hash(True)` (bool is an int subtype) — an enum
        # member flipping from the JSON number 1 to the JSON boolean true
        # would then diff to nothing. _value_sort_key already separates
        # them by `type(value).__name__`; reusing it here for MEMBERSHIP,
        # not just the ordering it was built for, is what closes that gap.
        # See docs/tomo/scripts/lib/wire_shape.md.
        old_by_key = {_value_sort_key(v): v for v in old_values.get(name, [])}
        new_by_key = {_value_sort_key(v): v for v in new_values.get(name, [])}
        for key in sorted(set(new_by_key) - set(old_by_key)):
            changes.append(_change(
                pointer, ADDED_ENUM_VALUE, f"{name}: added value {new_by_key[key]!r}",
            ))
        for key in sorted(set(old_by_key) - set(new_by_key)):
            changes.append(_change(
                pointer, REMOVED_ENUM_VALUE, f"{name}: removed value {old_by_key[key]!r}",
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
    added/removed properties, a type change, a field joining or leaving
    `required` (`required_added`/`required_removed` — two kinds, not one,
    because the two directions classify oppositely; see `_diff_node`), an
    openness change, and added/removed enum values.

    `consumer_affecting` is always `False` on every returned change — that
    field belongs to T2.2's `classify(change, observed)`, not to this
    function. See docs/tomo/scripts/lib/wire_shape.md for why deciding it
    here would be a second rule table.

    `detail` is display-only: T2.3's gate message and T4.1's obligation
    table print it verbatim, and nothing parses it back to recover a
    property/field/value name — `pointer` and `kind` are the machine-keyed
    facts. Do not start extracting data out of `detail` in a later task;
    change the ShapeChange shape instead if a caller needs it structured.

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
        changes.append(_change(pointer, NODE_ADDED, f"node added: {pointer}"))
    for pointer in recorded_pointers - observed_pointers:
        changes.append(_change(pointer, NODE_REMOVED, f"node removed: {pointer}"))

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


def _require_node(observed: dict, pointer: str) -> dict:
    """The `NodeShape` at `pointer` in `observed`, or a loud `ValueError` —
    never a silent empty-dict fallback.

    `added_property` and `openness_changed` are the only two `classify`
    branches that look a pointer up in `observed` at all, and both need
    it: an added property's obligation depends on whether the node is
    closed, and an openness change's direction is read from `observed`
    directly (never parsed out of `detail` — see `classify`'s docstring).
    A `.get(pointer) or {}` fallback would degrade "this pointer is not in
    the manifest I was handed" into "this node happens to have no
    properties and reads as open", which is a GUESS, and the dangerous
    one: it reports "not affecting" for a change `classify` cannot
    actually evaluate. Every other unanswerable question in this module
    already raises rather than guesses (an unregistered kind, in both
    `classify` and `_change`); this closes the one path that used to
    guess instead, and does so in the direction that would have let a
    real change ship unannounced. See docs/tomo/scripts/lib/wire_shape.md.
    """
    if pointer not in observed:
        raise ValueError(
            f"classify: pointer {pointer!r} is not in the observed node map. "
            "This usually means the change was paired with a manifest it "
            "did not come from, or `observed` is stale — call classify "
            "with the SAME `observed` that diff_shapes(recorded, observed) "
            "was called with to produce this change.",
        )
    return observed[pointer]


def classify(change: dict, observed: dict) -> bool:
    """Does this single `ShapeChange` oblige the consumer to act?

    Reads only `change` (`pointer`, `kind`) and `observed` — the freshly
    described node map — NEVER `recorded`. The direction of every kind is
    already decided by `_diff_node`/`diff_shapes` at the point the kind is
    chosen (see `_change`'s docstring and `wire_shape.md`'s "WHY
    `required_added`/`required_removed` Are Two Kinds"); `classify` has
    nothing left to re-derive from a before/after comparison, only a rule
    to apply. Wanting `recorded` here is the signal of having reasoned
    about a kind backwards — see the rule-by-rule notes below and
    docs/tomo/scripts/lib/wire_shape.md.

    This wire runs producer (Tomo) -> consumer (Hashi, vendoring a schema
    copy and validating against it with `additionalProperties: false` on
    almost every node). Every rule below falls out of that direction:
    - We ADD something their older copy does not permit -> they reject ->
      affecting.
    - We STOP emitting something their older copy REQUIRES -> they reject
      -> affecting.
    - We emit a SUBSET of what they already accept -> fine -> not
      affecting.

    Rules, measured against the consumer's own validator (PRD/Detailed
    Feature Specifications; Business Rules 1-9):

    - `added_property`: affecting only if the node is closed (Rules 1-2,
      PRD F2-AC1/F2-AC2) — an added field on an open node is a subset of
      what they already accept.
    - `removed_property`: NEVER affecting on its own. Whether losing a
      property matters depends entirely on whether it was required, and
      that fact is carried by a SEPARATE `required_removed` change on the
      same pointer when it applies (Rule 4) — see `diff_shapes`, which
      emits both `removed_property` AND `required_removed` for a required
      field's removal, and `removed_property` alone for an optional one.
      The gate's `any(classify(c, observed) for c in changes)` is what
      recombines them; this function must not (and structurally cannot,
      without `recorded`) re-derive required-ness from a lone
      `removed_property`.
    - `type_changed`: always affecting (Rule/class 6), independent of
      openness — an empty value where a consumer's validator expects a
      declared type errors regardless of which node it lives on.
    - `required_added`: NEVER affecting. This wire runs producer ->
      consumer; the consumer never SENDS a document that could be missing
      a newly-required field. We now always emit something their older
      copy already declared and accepted as optional — a subset of what
      validates, not a superset.
    - `required_removed`: always affecting (Rule 4/class 4) — we may now
      omit a field their vendored copy still requires.
    - `openness_changed`: direction read from `observed[pointer]["closed"]`
      — never from `detail`, which is display-only by contract (see
      `wire_shape.md`, "WHY `detail` Is Display-Only"). `closed=True` means
      the node just became closed (affecting — a document valid under the
      open version may now be rejected); `closed=False` means it just
      opened (not affecting — Rule 8).
    - `added_enum_value` / `removed_enum_value`: opposite of what "additive"
      suggests. Adding a value is affecting (Rule 3/class 5) — a consumer
      validating against the older, smaller set rejects the new value.
      Removing a value is not affecting — we now emit a subset of their
      already-accepted set. (Their handling code may still switch on a
      value that stopped arriving; that is a prose obligation for the
      handover table, not something this validator-measured rule sees —
      the same boundary ADR-2 draws for descriptions.)
    - `node_added` / `node_removed`: always affecting (Rule 9) — most new
      nodes arrive with an `added_property` on their parent that already
      carries the obligation, but a new `oneOf` branch (e.g. a new
      instructions action kind) emits ONLY a `node_added`, because its
      parent declares no `properties` and is not itself a recorded node.

    A declared-optional field starting to be emitted, and a prose-only
    edit, are NOT branches here — `describe_shape` records neither, so
    `diff_shapes` never produces a `ShapeChange` for them and `classify`
    is never called. `any(classify(c, observed) for c in [])` is `False`,
    the correct answer, discharged by absence rather than by a rule.

    Raises `ValueError` on a `kind` this function has no rule for, rather
    than defaulting to `False` — a silent `False` on an unrecognised kind
    is the exact failure this spec exists to eliminate, one layer past
    `diff_shapes` naming the change at all. See docs/tomo/scripts/lib/wire_shape.md.
    """
    kind = change["kind"]
    if kind not in CHANGE_KINDS:
        raise ValueError(
            f"classify: no rule for change kind {kind!r}. If this is a "
            "legitimate new kind, add it to CHANGE_KINDS and give it a "
            "branch in classify() — do not let it fall through to a "
            "default.",
        )

    if kind == ADDED_PROPERTY:
        return bool(_require_node(observed, change["pointer"]).get("closed"))
    if kind == REMOVED_PROPERTY:
        return False
    if kind == TYPE_CHANGED:
        return True
    if kind == REQUIRED_ADDED:
        return False
    if kind == REQUIRED_REMOVED:
        return True
    if kind == OPENNESS_CHANGED:
        return bool(_require_node(observed, change["pointer"]).get("closed"))
    if kind == ADDED_ENUM_VALUE:
        return True
    if kind == REMOVED_ENUM_VALUE:
        return False
    if kind == NODE_ADDED:
        return True
    if kind == NODE_REMOVED:
        return True

    # Unreachable: every member of CHANGE_KINDS is handled above. If this
    # ever fires, a kind was added to CHANGE_KINDS without a branch here —
    # raise rather than fall through to an implicit `None`/`False`, for the
    # same reason the unknown-kind check above raises instead of guessing.
    raise AssertionError(f"classify: {kind!r} is in CHANGE_KINDS but has no branch")

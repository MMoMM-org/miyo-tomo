# WHY: lib/wire_shape.py

> Rationale for decisions in `tomo/scripts/lib/wire_shape.py`.
> The shape manifest that lets a wire-schema change be caught before a consumer is.

## WHY This Module Exists (spec 035 F1)

The check it replaces walked a schema too shallowly: on a document with no
reusable `$defs` block — exactly the shape of the document that drifted —
it compared nothing and passed vacuously. `describe_shape` walks every
object node reachable from the schema root, whatever route reaches it, so
the manifest cannot go blind just because a document inlines its objects.

## WHY Effective Openness, Not Literal

`closed` is `node.get("additionalProperties") is False` — not "whatever the
key holds" and not "False when the key is absent." A JSON-Schema node with
no `additionalProperties` declared is permissive by the spec's own default;
recording the literal value (`None`) would misclassify every node that
never declared it as neither open nor closed, and Phase 2's classifier
needs a clean boolean to decide whether an added property is
consumer-affecting. Recording the effective value is what keeps that
classification honest — see ADR-4, which reads `closed` off this field
rather than re-deriving it.

## WHY Types Are Recorded and Descriptions Are Not (ADR-2)

The eight-class change matrix behind this spec measured a type change as
consumer-affecting on its own — emitting `null` where a consumer's
validator expects `string` errors regardless of whether the containing node
is open or closed. Excluding types would leave that breakage invisible, so
`properties` maps each name to its declared `type` keyword.

Descriptions and titles are left out deliberately, not by oversight: the
consumer's validator ignores prose, so recording it would fail the check on
every edit that obliges nobody — which is the exact noise pattern that
makes a detector go unread. The exclusion line is drawn where the churn is
(descriptions change constantly), not where recording is cheapest. This is
also PRD/F1-AC4: a description- or title-only edit must produce an
identical manifest, which only holds if prose never entered the recorded
shape in the first place.

## WHY an Undeclared Type Gets a Placeholder, Not an Omission

`(child or {}).get("type", "any")` always inserts a key for every property
name, even when the property's own subschema carries no `type` keyword (for
example a bare `{"description": "..."}`, or a node built purely from
`allOf`/`$ref`). Omitting the key instead of recording `"any"` would make a
manifest diff between "this property has never had a type" and "this
property's type keyword was just deleted" look identical — both would show
up as a missing dict key rather than as two distinct, nameable states.

## WHY Pointers Carry a `properties` Segment (deviation from the SDD's illustrative code)

The first cut walked `f"{pointer}/{name}"` for a property child — a bare
name appended directly, with no `properties` segment — matching the code
block in solution.md's Implementation Examples verbatim. That code block is
illustrative, not authoritative, and the bare form turned out to be wrong:
a schema with a property literally named `items` (or `contains`, `$defs`,
`definitions`, `allOf`, `anyOf`, `oneOf`) collides with the sibling
structural keyword of the same name, because both paths append that literal
segment to the same parent pointer. Measured directly: a schema with a
property `items` alongside a real array `items` keyword produced 2 nodes
where 3 were expected — the second overwrote the first in the `nodes` dict.
That is the precise failure class this spec exists to eliminate ("a walk
that visited too little"), just relocated from missing branches to
colliding pointers.

Real RFC 6901 pointers — `f"{pointer}/properties/{name}"` — are collision-free
because `properties` is never itself a valid property *name* collision
target in the same way: the segment sequence `.../properties/items` cannot
be produced by the structural-keyword branches (`items`, `$defs/…`, etc.),
which append `items`, `$defs/<name>`, `allOf/<i>`, and so on directly. This
also matches T1.3's own validation gate, which names
`/properties/suggestions/items` literally, and the SDD's own walkthrough
table (`/properties/findings/items/properties/detail`), which already used
the mid-path `properties` segment the illustrative code block omitted. See
the plan's Deviation Log (`plan/README.md`) for the approval record.

If a later reader is tempted to "simplify" the pointer back to the bare
form for readability: don't — that is exactly the change that reintroduces
silent node loss, and the regression test
(`test_property_named_items_does_not_collide_with_items_keyword`) exists to
catch it.

## WHY the Walk Covers `items`/`contains`, `if`/`then`/`else`,
`$defs`/`definitions`, and `allOf`/`anyOf`/`oneOf` — and What It Still Doesn't

An earlier version of this section claimed this set was "precisely the
routes a real object node can be reached by in the three published wire
schemas this spec covers." That claim was checked and found false: code
review found `instructions.schema.json`'s `$defs/edit_frontmatter/allOf/0/if`
— a genuine object node, with its own `properties` and `required:
["operation"]` — reachable only through `if`, which the walk did not visit.
So `if`/`then`/`else` were added alongside `allOf`/`anyOf`/`oneOf`: like
those, each introduces a subschema that MUST hold (`then`/`else`) or is
tested (`if`) as a first-class schema, and an object node living there is
exactly as real as one under `allOf`. The regression test
(`test_if_branch_of_real_edit_frontmatter_is_walked`) is built on this real
`edit_frontmatter` shape rather than a synthetic one, because a synthetic
fixture is what let the gap through code review undetected the first time —
only reading the actual shipped schema surfaced it.

The `if`/`then`/`else` fix was found empirically false a second way once
checked again: the previous wording of this boundary tied the walked set to
"appears in at least one of the three published wires or their internal
`$defs`" — and `contains` and `else` are both walked while neither appears
in any of the three wires today. That is not a bug in the walk; the walk
walking a keyword nothing currently uses costs nothing. It is a bug in
**this doc**, and a repeat of the same mistake with a narrower target: a
claim that ties the walked set to what the wires happen to contain, stated
as if it were a property of the design, goes stale the moment a schema
changes and gets believed anyway because it is written down. Twice was the
signal to stop writing that *class* of claim rather than a third, tighter
version of it.

**The walked set is chosen by what JSON Schema can put an object node
behind, forward-compatibly — not by what today's three wires happen to
use.** `items`/`contains` and `if`/`then`/`else` are each walked as a
**complete keyword pair**, on purpose, even though only `items` and `if`
are exercised by a wire today (an observation about the schemas as they
stand on 2026-09-10, not a property of the design, and not a boundary of
the walk): the cost of walking a branch nothing currently populates is
zero, and the cost of missing one — the entire subject of this spec — is a
node nobody can see and a drift nobody catches.

Genuinely and deliberately **outside** the walked set: `not` (introduces a
subschema, but negation — a node found only under `not` describes what
must NOT match, a different question than "what does the consumer
accept"), `patternProperties`, `propertyNames`, `prefixItems` (2020-12
tuple typing), `dependentSchemas`, and a schema-valued
`additionalProperties` (today's is always a bare `true`/`false`/absent,
read directly by `closed` — never itself walked as a subschema). If a wire
ever starts using one of these, the node it introduces goes unrecorded and
that drift becomes exactly as invisible as `if` was before this fix — and
adding the keyword to the walk, here, is the required response, not a
workaround at the call site. `describe_shape` is the only place that gets
to claim full depth.

## WHY `enum`/`const` Are Recorded in a Fourth `values` Field (ADR-2 extended)

PRD F2-AC3 requires that a value added to an enumerated set classify as
consumer-affecting. `classify` (Phase 2) reads a `ShapeChange`; `diff_shapes`
(Phase 2) reads the manifest this function produces. Without enum/const data
in the manifest, `diff_shapes` has no way to ever emit an enum change, so
F2-AC3 was structurally unreachable no matter how Phase 2 was written — a
Phase 2 test for it could only pass by hand-constructing a `ShapeChange`
directly, which is a test that goes green while the mechanism it is meant
to exercise stays blind. That is the exact vacuous-pass pattern this spec
exists to eliminate, just found one field short of `NodeShape` rather than
one branch short of the walk. Owner-approved as an extension of ADR-2 (the
manifest already draws its line at "consumer-affecting, not prose" — an
enum/const value is squarely on the consumer-affecting side, the same as a
type).

`const: X` is recorded as `[X]`, not as a separate kind of fact — JSON
Schema defines `const: X` as equivalent to `enum: [X]`, and recording it
identically means a schema edit that widens a `const` into an `enum` (a
real, observed shape of change) shows up in `diff_shapes` as *added
values*, which `classify` already knows how to judge, rather than as a
change of *kind* that would need its own classification rule.

`values` is a dict field present on every node, with an entry only for a
property that actually declares `enum` or `const` — never an empty list.
Distinguishing "never had a constraint" from "still has the same
constraint" the same way `properties` distinguishes "no type keyword" (the
`"any"` placeholder, see above) would require a second placeholder value;
omission does the same job here because the alternative (an always-present
empty list) is the more common case for most properties and would double
the field's footprint in every manifest for no gain — there is nothing to
diff about a property that never had one.

**A property declaring BOTH `enum` and `const` records `enum` alone — a
deliberate, scoped choice, not an oversight.** JSON Schema treats `enum`
and `const` as independent assertions that both apply when both are
present, so the genuinely correct record would be their *intersection*
(and if `const`'s value is not itself a member of `enum`, the truly
correct record is an unsatisfiable, empty valid set). No published wire
declares both on any property today, so `_property_values` takes `enum`
alone — it is the more common and more informative of the two when only
one can be chosen, and implementing set intersection (with its
unsatisfiable-schema edge case) to serve a scenario that occurs zero times
would be exactly the kind of complexity this codebase's YAGNI standard
rules out. `test_enum_and_const_together_records_enum_alone_deliberately`
pins this precedence — verified to fail if the priority in
`_property_values` is swapped, so it is a real regression guard, not a
tautology. **A future reader who actually encounters a wire declaring
both should implement the intersection rather than assume this choice
was made on the merits of that case** — it was not; it was made on the
merits of the case that actually exists.

## WHY Enum/Const Values Are Sorted With a Type-Tolerant Key, Not `sorted()`

`required` is sorted so a reordering can never show up as a diff; the same
reasoning applies to `values`, but a bare `sorted()` on an `enum` list
raises `TypeError` the moment the list mixes JSON scalar types (`None` vs
`str`, `bool` vs `int` — and `bool` is a subtype of `int` in Python, which
makes naive numeric sorting actively misleading, not just impossible for
mixed types). `_value_sort_key` groups by `type(value).__name__` first,
then by `json.dumps(value, sort_keys=True)` — both parts total and stable
across runs, independent of Python's cross-type comparison rules (which are
mostly undefined). None of today's wire enums are heterogeneous; the guard
exists because nothing in JSON Schema promises they will stay that way, and
a manifest generator that can only handle today's enums is exactly the kind
of "too little" this spec exists to close off.

## WHY Local `$ref` Is Resolved for `type`/`enum`/`const`

`(child or {}).get("type", "any")` recorded `"any"` for every property that
is a bare `{"$ref": "#/..."}` — verified on `instructions.schema.json`'s
`$defs/move_note`: `id` and `applied` both resolved to `"any"` where the
referenced defs (`action_id`, `applied_field`) declare `string` and
`boolean` respectively, and the same pattern repeats across roughly fifteen
action shapes that share `id`/`applied` by reference rather than by
inlining. A type change to `$defs/applied_field` would therefore have been
invisible everywhere it is used — not a missing branch in the walk this
time, but a value the walk reached and then declined to read.

`_effective(child, key, root)` resolves this by checking `child` for `key`
first (inline always wins over a sibling `$ref` — a property is allowed to
narrow or override what it points to) and, failing that, following `$ref`
through `_resolve_pointer` and repeating on the resolved target. Two
constraints, both load-bearing:

- **Local refs only** (`#/...`). A non-local or unresolvable `$ref` records
  `"any"`, same as no `$ref` at all — `describe_shape` stays pure, with no
  I/O and no network, which is what lets a stale vendored consumer copy
  (ADR-7) still be described offline.
- **Cycle guard.** `_effective` tracks every `$ref` string it has already
  followed in `seen` and returns `_MISSING` (→ `"any"`) the moment a ref
  repeats, rather than recursing forever. `$defs/action_id` is itself never
  a *recorded node* — it has no `properties` — which is exactly why
  resolution, not cross-referencing an already-walked node, is the
  mechanism: there may be nothing in `nodes` to cross-reference against.

## WHY List-Valued `type` Is Sorted, and Why That Also Fixes the Aliasing

JSON Schema's `type: [...]` is semantically an unordered set (an instance
of any listed type validates), so `["string", "null"]` and `["null",
"string"]` are the same constraint. Recording it verbatim would let a pure
reordering — a no-op for any consumer's validator — show up in `diff_shapes`
as a change, which is precisely the noise ADR-2 already rules out for
descriptions; the same principle applies here. `properties[name] =
sorted(raw_type) if isinstance(raw_type, list) else raw_type` sorts it.

`sorted()` also always returns a **new** list, which incidentally fixes a
second, independent bug code review found: the previous
`(child or {}).get("type", "any")` returned the schema's own list object
by reference, so the manifest could alias a list that lives inside the
input `schema` dict — a caller mutating one would silently mutate the
other. Because the fix for "sort it" and the fix for "copy it" are the same
line, it would be easy for a future edit to "simplify" this back to a bare
attribute lookup once list-valued types stop looking special-cased; don't —
losing the sort reintroduces order-noise, and losing the copy reintroduces
aliasing, and neither has an independent guard rail besides this comment
and the two regression tests
(`test_list_valued_type_is_sorted`,
`test_list_valued_type_is_a_copy_not_an_alias`).

## WHY the Return Value Is the Nodes Map, Not the Manifest Entity

The SDD's `ShapeManifest` entity carries `schema_version` and `source`
alongside `nodes` — those are properties of the *file* a manifest is
written to, not of the schema being walked, and `describe_shape` has no
file to read them from. Assembling `ShapeManifest` is T1.2's job, which
also decides where `schema_version` and `source` come from for a given
wire. `describe_shape` stays a pure function of one schema dict in, one
`dict[pointer, NodeShape]` out — no I/O, so the same function can describe
a schema loaded from disk, a scratch dict built for a test (as in the
counterfactual pre-032 garden-audit walkthrough in solution.md), or a
consumer's vendored copy, without needing to know which.

## WHY `diff_shapes` and `classify` Are Not Here Yet

They are Phase 2 (T2.x). This module currently exposes only
`describe_shape` in `__all__`; a reader who finds the module's surface
partial should not read that as an oversight — the plan sequences shape
description before shape comparison so each has its own RED-GREEN cycle
against its own acceptance criteria (F1 here, F2 in Phase 2).

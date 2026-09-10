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

**The guarantee is scoped to distinct JSON *types*, not distinct numeric
*representations* of the same number.** `1` and `1.0` are the same number
under JSON Schema's `enum` equality, but `_value_sort_key` groups by
`type(value).__name__`, and Python's `int` and `float` are different types
— so rewriting an enum member's literal form from `1` to `1.0` would show
up in `diff_shapes` as a spurious added-value-plus-removed-value pair,
never as the no-op it actually is. Normalising numeric representation
before comparing is the correct fix for that case and is deliberately not
built here — the same YAGNI call as the enum+const precedence below. A
future reader who meets a float-typed wire enum should add that
normalisation rather than assume it was weighed against that case; it was
weighed only against the case that exists today (2026-09-10 observation,
not a property of the design).

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

Two further guarantees are pinned by test, not merely true by inspection,
because both are the kind a routine-looking refactor could undo without
any existing test noticing: each keyword is resolved **independently** —
`_effective` is called once per keyword (`type`, `enum`, `const`), so a
property overriding `type` inline still resolves `enum`/`const` from its
`$ref` target rather than the override suppressing lookup of every other
keyword
(`test_inline_override_of_one_keyword_does_not_suppress_ref_resolution_of_another`)
— and `seen` is a **fresh local** on every `_effective` call, so the same
`$ref` target resolves correctly at every site that shares it within one
`describe_shape()` call, not only the first
(`test_same_ref_target_resolves_at_many_independent_sites_in_one_call`,
run against the real `instructions.schema.json`, where `#/$defs/action_id`
is the `id` property's `$ref` on every action shape). A refactor that
hoisted a single resolved node per property, or hoisted `seen` to module
scope or a mutable default argument, would silently under-record most of
the instructions wire — and, verified directly, both regressions make
these two tests fail while leaving every other test in this file green.

**`closed` and `required` are read directly off a node with `.get()` and
do NOT chase a `$ref`, unlike `type`/`enum`/`const` — a deliberate, scoped
omission, the same shape of choice as the enum+const precedence below.** A
node composed as `{"$ref": "#/$defs/Base", "properties": {...}}`, where
`Base` itself declares `additionalProperties: false` or `required`, would
not inherit either through this mechanism. No wire is composed that way as
of 2026-09-10 — an observation about current content, not a boundary the
design commits to. A future reader who meets one should extend resolution
to `closed`/`required` rather than assume the gap was weighed against that
specific case; it was weighed only against the case that exists today.

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

## WHY `diff_shapes` Takes Two Node Maps, Not Two Manifests (T2.1)

`diff_shapes(recorded, observed)` receives `dict[pointer, NodeShape]` on
both sides — never the `{schema_version, source, nodes}` wrapper
`build_manifest` produces. The function has nothing useful to do with
`schema_version` or `source`: it compares shapes, not files, and PRD F1-AC1
(the failure must name the document) is deliberately NOT this function's
job — see below. Taking the wrapper would tempt a future edit to reach into
`manifest["nodes"]` internally, which just re-adds a parameter the caller
already had to unwrap; taking the node map directly keeps `diff_shapes` as
ignorant of the manifest file format as `describe_shape` already is of
where a schema lives on disk.

## WHY the Document Name Is Out of Scope for `diff_shapes` (deferred to T2.3)

`diff_shapes` never learns which file `recorded`/`observed` came from — it
receives two node maps and returns pointer+kind+detail, nothing else. PRD
F1-AC1 requires a failure that names the document, but that is discharged
by T2.3, which iterates `PUBLISHED_WIRES` and therefore knows the filename
at the point it calls `diff_shapes` once per wire. Adding a `document`
parameter here to shortcut that would duplicate a fact the caller already
has, for no benefit to this function's own purity.

## WHY `node_added`/`node_removed` Are Reported Once, Never Decomposed (T2.1)

A pointer present in only one of the two node maps is emitted as exactly
one `node_added` or `node_removed` change and is **never** also walked for
`added_property`/`removed_property` on its own fields. The alternative —
treating a brand-new node as "N new properties" — would make the gate's
failure message for a genuinely new wire section list every one of its
fields as a separate line of drift, drowning the one fact that actually
matters ("this whole node is new") in noise that looks like N unrelated
facts. `diff_shapes` computes `observed_pointers - recorded_pointers` (and
the reverse) BEFORE ever calling `_diff_node`, and `_diff_node` is only
ever invoked on the intersection — so there is no code path that could
produce both a `node_added` and an `added_property` for the same pointer.
`test_node_added_wholesale_is_reported_once_not_as_n_property_changes` (and
its removal counterpart) pin both halves of this: the count AND the
absence of property-level entries under the new node's own pointer, because
the count alone goes hollow the moment the fixture's field count changes.

## WHY Enum Diffing Compares VALUE SETS, Not Value Lists (T2.1)

`_diff_node` reads `values[name]` (already sorted by `describe_shape`) and
diffs it as `set(...) - set(...)` rather than a positional list comparison.
A `values` list is semantically a SET — JSON Schema's `enum` has no
ordering — so two describe_shape() outputs of the same enum are already
guaranteed to agree on order (both sorted by `_value_sort_key`), but
`diff_shapes` is also exercised directly against hand-built node maps in
its own tests (T2.1's fixtures never go through `describe_shape`), where
nothing guarantees the input lists arrive pre-sorted. Set-difference makes
`diff_shapes` correct regardless of the caller's list order, and reusing
`_value_sort_key` (already defined for exactly this "mixed JSON scalar
types" problem) to order the OUTPUT keeps that determinism promise intact
without inventing a second sort key.

This is also what makes the const-widened-to-enum case (PRD F2-AC3, see
above) fall out for free rather than needing a special rule: Phase 1
records `const: "open"` as `["open"]`, so widening to
`enum: ["open", "closed"]` is `{"open"} → {"open", "closed"}` — a
one-element set difference, reported as a single `added_enum_value` for
`"closed"` and nothing else, because `"open"` is in both sets and never
enters either diff branch.

## WHY `required_added`/`required_removed` Are Two Kinds, Not One `required_changed` (T2.1, revised)

The first cut of `diff_shapes` compared `old.required != new.required` as a
single boolean and emitted one `required_changed` kind for either
direction. Code review found this was the same defect the enum kinds were
already split to avoid: a field LEAVING `required` and a field JOINING it
classify OPPOSITELY against the consumer's validator — leaving means we may
stop emitting a field their vendored copy still requires (consumer-
affecting), joining means we now always emit a field they already accepted
as optional (not affecting). `classify(change, observed)` (T2.2) receives
only the `observed` manifest, never `recorded`, so it has no way to
re-derive which way the list moved from a collapsed `required_changed`
entry — the direction has to be decided here, in `_diff_node`, where both
`old` and `new` still exist side by side. Same reasoning, same fix, applied
a second time to the same shape of bug: `required_added` and
`required_removed` are computed as `set` differences of the two `required`
lists, exactly like `added_enum_value`/`removed_enum_value` below, and
sorted per-field for the same reason those are sorted per-value — a
`detail` naming one moved field is more legible in a failure message than
one string reciting two whole before/after lists.

Both kinds can fire on the same pointer in the same `diff_shapes` call, and
must: an edit that both drops a field from `required` and adds a different
one is two independent facts, not one. `test_required_added_and_removed_in_one_edit_emit_both_kinds_not_one`
pins this — asserting the kind SET is exactly `{required_added,
required_removed}`, not that a bare count of 2 happened to come out right,
so the test still catches a regression that emitted two `required_added`
entries by accident.

## WHY `added_enum_value`/`removed_enum_value` Are Per-Value, Not Per-Property (T2.1)

A property that gains two new enum members produces two `ShapeChange`
entries, not one entry listing both values. `detail` is meant to read as a
single human-legible fact in the gate's failure message ("status: added
value 'closed'"), and a property that gained N values in one edit is still
N independently-actionable facts for whoever reads the failure — bundling
them into one string would mean T2.2's `classify` (or a future consumer of
the change list) either re-parses a packed string or loses the ability to
reason about one value at a time. Sorting them individually via
`_value_sort_key` before appending keeps the output list's ordering
guarantee whole even when a single property is the source of several
entries.

## WHY `consumer_affecting` Is Always `False` Here — Not T2.1's Decision to Make

Every `ShapeChange` `diff_shapes` returns carries `consumer_affecting:
False`, unconditionally, via the shared `_change()` constructor. This is a
placeholder, not a judgment: T2.2's `classify(change, observed)` is the
single place that decides the field, reading a node's `closed` flag off
the `observed` manifest (ADR-4 — classification is read from the manifest,
not maintained as a second rule table). If `diff_shapes` pre-judged even
the "obvious" cases here — an enum value added is always affecting, a
required field's disappearance sometimes is — that judgment would live in
two places that could drift apart the moment one of them changes and the
other doesn't get the matching edit. `_change()` being the only place that
sets the field means there is exactly one line to change if the default
placeholder value itself ever needs to move, and nowhere else the field
could silently diverge from it.

## WHY `detail` Is Display-Only — a Contract, Not an Observation (T2.1)

`detail` is a human-readable string naming what moved (a property, a
required field, an enum value), built by plain string interpolation in
`_change()`/`_diff_node()` with no fixed grammar. This is deliberate and is
now a confirmed contract, not merely today's implementation: `classify`
(T2.2) keys on `pointer` and `kind` alone; T2.3's gate failure message and
T4.1's obligation table print `detail` verbatim for a human reader, and
nothing in the pipeline parses it back out to recover a property, field or
enum-value name programmatically. A later task that needs one of those
names in a structured form should add a field to `ShapeChange` for it, not
regex the wording out of `detail` — the moment something depends on the
exact phrasing, `detail` stops being free to reword and starts being load-
bearing wire format for a value that was never designed to hold one.

## WHY the Output Is Sorted by `(pointer, kind, detail)` (T2.1)

Two independent runs of `diff_shapes` over the same two inputs must
produce byte-identical output, because the drift gate's failure message
(T2.3/T2.4) is built directly from this list — an unstable order would
make two CI runs against unchanged inputs print their failure in a
different sequence, which reads as noise the moment a real reviewer is
trying to tell "did this change" from "did the order change." Sorting by
the full `(pointer, kind, detail)` tuple (rather than pointer alone) also
gives a stable order WITHIN one pointer that has several kinds of change at
once — same reasoning as `required` and `values` being sorted inside
`describe_shape` itself; this is that same anti-churn discipline applied
one layer up, to the list `diff_shapes` returns rather than the node map
`describe_shape` returns.

## WHY `diff_shapes` and `classify` Were Not Here Yet, Historically

`diff_shapes` is now implemented (T2.1, this section's siblings above).
`classify` is still Phase 2's next task (T2.2) and is not implemented yet.
This module currently exposes `describe_shape`, `PUBLISHED_WIRES`,
`build_manifest`, `serialize_manifest` and `diff_shapes` in `__all__`; a
reader who finds `classify` absent should not read that as an oversight —
the plan sequences shape description, then shape comparison, then
classification, so each has its own RED-GREEN cycle against its own
acceptance criteria (F1 in Phase 1, F2 split across T2.1's diff mechanism
and T2.2's classification rule).

## WHY `PUBLISHED_WIRES` Lives in `wire_shape.py`, Not in the Generator or the Tests (T1.2)

The task brief's own framing is the reason: writing the list of published
wires twice — once for generation, once for the "no manifest on an
internal schema" test — means a fourth published wire added later needs
two coordinated edits to stay covered, and a spec whose entire point is
"nothing escapes" cannot tolerate a registry that itself can silently
drift. Putting `PUBLISHED_WIRES` in `wire_shape.py` (not in
`tests/test_035_wire_manifests.py`, not in the one-off generation script)
makes it importable by both without either depending on the other, and a
tuple of three filenames is data, not behaviour — it does not compromise
`describe_shape`'s purity to sit alongside it. The "no manifest on an
internal schema" test derives its target list as `tomo/schemas/*.schema.json`
minus this tuple rather than enumerating the current 15 by name, for the
same reason: a schema added tomorrow is covered by construction, not by
someone remembering to update a second list.

`hashi-instructions.schema.json` is deliberately absent from the tuple. It
is a vendored mirror of `instructions.schema.json` living in the consumer's
own repo copy (Phase 4's drift report reads it, this mechanism does not) —
not a schema Tomo publishes, so it gets no manifest and falls into the
"internal" bucket the derived test walks.

## WHY `build_manifest` Reads `schema_version` From the Schema, Not From a Caller-Supplied Value

The plan text says a manifest's `schema_version` is "the value its schema
currently declares" — `build_manifest(schema, source)` therefore reads
`schema["properties"]["schema_version"]["const"]` itself rather than
accepting a `schema_version` argument. A caller-supplied version could
drift from what the schema file actually says the moment someone edits one
without the other; reading it off the schema makes that drift structurally
impossible. `source` stays a caller-supplied string because it names a
*file path*, which is a fact about where the schema lives on disk, not a
fact `describe_shape`'s pure walk of the schema *content* could derive —
keeping `build_manifest` free of path conventions is what lets the same
function manifest a schema loaded from any location a caller chooses.

## WHY `serialize_manifest` Exists, and Why the Round-Trip Test Loads From Disk

"Byte-for-byte" (PRD/F1-AC5) is only a checkable claim if exactly one
function turns a manifest dict into text, used on both sides of the
comparison — one path to write the committed files, the same path to
regenerate content for the test. Two independently-written encoders (even
both calling `json.dumps` with slightly different kwargs) would drift on
whitespace or key order alone, producing a false failure that has nothing
to do with the recorded shape. `serialize_manifest` fixes the encoding
once: 2-space indent, `sort_keys=True` (so `describe_shape`'s dict-insertion
order is never itself diff noise), `ensure_ascii=False` (a manifest holds
no prose to escape), one trailing newline.

The round-trip test loads the manifest from the COMMITTED FILE ON DISK
and compares a fresh `build_manifest` + `serialize_manifest` against that
text — never two in-memory generations compared to each other. A
self-comparing test (`describe_shape(schema) == describe_shape(schema)`)
passes against any implementation whatsoever, including one that records
nothing, and proves only that Python is deterministic. The three files
under `tomo/schemas/shapes/` are the actual baseline every later phase's
drift check compares against; a test that never opens one of them would
give false confidence in the one artifact this entire spec rests on.

## WHY the Missing-Manifest Check Lives in the Test Suite, Not in `wire_shape.py`

The plan asks for "a published wire with a missing manifest fails rather
than passing silently" but does not say where that check lives. T1.2
builds it as a test-suite helper (`_assert_manifest_exists` in
`tests/test_035_wire_manifests.py`) exercised twice — once over the three
real, committed manifests (the permitted case) and once against a
fabricated filename that is deliberately absent from both
`PUBLISHED_WIRES` and disk (the refused case, `pytest.raises(AssertionError)`)
per MiYo Constitution L1's requirement to prove both. It is deliberately
NOT a function in `wire_shape.py`: Phase 2 builds the real drift gate
(the thing that runs in CI and blocks a merge) on top of `describe_shape`
and `build_manifest`, and that gate's shape isn't decided yet. Adding a
"does the manifest exist" check to the production module now would be
guessing at Phase 2's interface before Phase 2 exists to say what it needs.

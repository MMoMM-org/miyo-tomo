# WHY: lib/wire_gate.py

> Rationale for decisions in `tomo/scripts/lib/wire_gate.py`.
> The drift gate that turns a wire-shape manifest into a pass/fail decision, and a message that says what to do (spec 035 T2.3).

## WHY This Module Exists, and Why It Is Separate From `wire_shape.py`

`wire_shape.py` is the pure data model: `describe_shape`, `diff_shapes`,
`classify`, `build_manifest`, `serialize_manifest`. None of it touches a
filesystem, knows there are exactly three published wires, or has an
opinion about what a maintainer should do next. `wire_gate.py` is the
thing that drives all of that: it reads a schema and a manifest off disk,
runs `describe_shape` -> `diff_shapes` -> `classify`, and turns the result
into a pass/fail decision per wire.

T2.3's plan named an explicit module-split seam for `wire_shape.py`: the
trigger for splitting it is not line count but whether gate-or-CLI logic
lands *inside* it — if it does, `classify` + `CHANGE_KINDS` must be peeled
out into their own module at that same moment, because the file stops
being "one data model and three pure views of it" and becomes "the data
model plus the thing that drives it". `wire_gate.py` as a sibling module
satisfies that seam without ever triggering it: `wire_shape.py` stays
exactly what it was.

## WHY the Gate Started in a Test File, and Why It Moved

T2.3's plan step 3 said, literally: "Put it in its own file —
`tests/test_035_wire_gate.py`". The first implementation took that at face
value — `gate_one_wire`, `run_wire_gate`, `render_wire_gate_report`, and
the `ACTION_*` constants all lived inside the test module, alongside the
tests that exercised them.

Code review caught the problem this created one phase early: T4.1 builds
`scripts/wire-shape.py --obligations`/`--check`, which is this same gate
wearing a CLI. If the gate stays inside a test module, T4.1 has exactly
two options and both are bad — import production behaviour out of a test
file (backwards: tests depend on production code, never the reverse), or
reimplement the gate a second time (a second implementation of a drift
detector that can silently disagree with the first is a special kind of
bad idea in a spec whose entire premise is "things drift apart
undetected"). The plan's instruction was read too literally: "its own
file" was satisfied by moving to `tomo/scripts/lib/wire_gate.py`, a
sibling of `wire_shape.py` rather than a fourth export inside it — the
actual constraint the seam describes — and `tests/test_035_wire_gate.py`
now imports from it like any other `lib` consumer, keeping only the
scratch-copy fixtures and the tests themselves.

`tomo/scripts/lib/` rather than `scripts/`: the repo's directory
convention splits by invocation (`scripts/` is user-invoked CLI,
`tomo/scripts/lib/` is a library consumed by other code — see
`feedback_scripts_dir_boundary_user_invoked` in the project memory). This
module is consumed by tests today and will be consumed by T4.1's CLI next;
it is not itself something a user runs.

## WHY the Gate's Contract Is "Any Shape Change Fails" (ADR-3), Not "Pass When the Version Moved"

The SDD's Complex Logic algorithm reads, for one wire:

```
5.  IF no changes: continue
6.    affecting = any(classify(c, observed) for c in changes)
7.    IF affecting AND schema.schema_version == manifest.schema_version:
8.        FAIL "consumer-affecting; move the version and hand over"
9.    ELSE:
10.       FAIL "shape changed; regenerate the manifest"
```

Read literally, step 9's `ELSE` still fails — it is not a pass branch.
Combined with ADR-3 ("a stale manifest always fails; regeneration is
always an explicit act"), this means the ONLY way `gate_one_wire` returns
`passed: True` is `diff_shapes` returning an empty list at step 5. There is
no second branch in `wire_gate.py` that inspects `version_moved` and lets a
non-empty diff through.

This was flagged explicitly during implementation because F2-AC5's
original wording ("moved passes") reads, taken alone, as if a version
bump by itself should clear an affecting change — which ADR-3 makes
impossible while the manifest is still stale. The criterion has since been
corrected in the PRD to match the ADR, not the other way around: the
behaviour that matters is the version DEMAND disappearing once the version
has already moved (see `gate_one_wire`'s `if affecting and not
version_moved` branch below), not the gate accepting a live diff because a
version number changed.

Concretely, "affecting + version moved -> pass" is realized the way it
happens for real: the maintainer bumps `schema_version` on the schema AND
regenerates the manifest against that same schema (`build_manifest` +
`serialize_manifest`), so the two sides become byte-identical again and
`diff_shapes` has nothing left to report. A partially-updated pair
(version bumped on the schema, manifest not regenerated) still has a
diff — the version bump itself shows up as an enum-value change on the
`schema_version` property, because `describe_shape` records `const` values
into its `values` field — and that pair still fails, per ADR-3. It just
fails with `actions == [ACTION_REGENERATE_MANIFEST]` instead of
`[ACTION_MOVE_VERSION, ACTION_HANDOVER]`, because the version-move half of
the demand is already satisfied.

## WHY the ELSE Branch Covers Two Different Situations With One Action List

`gate_one_wire`'s `else: actions = [ACTION_REGENERATE_MANIFEST]` is reached
by two distinct scenarios that share nothing except the resulting demand:

1. A non-affecting change (PRD F7-AC2) — nothing to hand over, the
   manifest is simply stale.
2. An affecting change whose version has ALREADY moved but whose manifest
   is still stale — the version-move half of the obligation is already
   discharged, so re-demanding it would be exactly the "asks for both"
   failure mode the plan calls out: a maintainer who already bumped the
   version does not need to be told to do it again.

Collapsing these into one action list is deliberate, not an oversight that
happens to produce the same string: both cases have EXACTLY one thing left
to do, and it is the same thing.

## WHY `consumer_affecting` Is Resolved Here, Not Left as `diff_shapes`'s `False`

`diff_shapes` (`wire_shape.py`) always returns `consumer_affecting: False`
on every `ShapeChange` it builds — that field is deliberately not its
decision to make (see `wire_shape.md`'s note on `_change`). `gate_one_wire`
is the first place both the change AND the freshly-observed node map are
available together, so it is the first (and only) place `classify` can
run: each returned change's `consumer_affecting` is genuinely resolved via
`classify(change, observed)`, not left at `diff_shapes`'s placeholder
`False`. A caller reading `result["changes"]` sees the real answer, not
the unclassified default.

## WHY the Structured Result, Not a String (plan T2.3, "separate the decision from the rendering")

`gate_one_wire`/`run_wire_gate` return a `WireGateResult` dict — document,
passed, error, changes (with `consumer_affecting` resolved), affecting,
schema/manifest versions, version_moved, actions — and
`render_wire_gate_report` is the ONLY function that turns that into human
text. This is the same contract `wire_shape.py`'s `detail` field already
carries one level down: a human-readable string is for humans, and nothing
parses it back. Two consequences that motivated it directly:

- Tests assert against the structure (pointer, kind, `consumer_affecting`,
  `actions`) rather than exact prose, which would be brittle — any
  rewording of the message would break the suite for no functional reason.
- T4.1's `--obligations` flag needs one row per changed field; it reuses
  `gate_one_wire`'s structured `changes` list directly rather than scraping
  a rendered message back into structured data.

## WHY an Unparseable Schema Returns `affecting: None`, Never `False`

A pass always carries `affecting: False` (set explicitly on the
`not changes` branch). A parse failure sets `affecting: None` instead of
reusing `False` — the two failure shapes must never be confusable by a
caller checking `affecting is False` and concluding "shape diff exists,
just not affecting." `None` reads unambiguously as "there was nothing to
classify," which is the true state: `describe_shape`/`diff_shapes` never
even ran.

## WHY `OSError`/`json.JSONDecodeError` Are Caught Narrowly, Not a Bare `except`

`gate_one_wire`'s parse-failure branches catch exactly the exception types
a malformed, missing, or unreadable FILE can raise. A bare `except` would
also swallow a real bug surfacing from inside `describe_shape`,
`diff_shapes`, or `classify` — turning an actual regression in the drift
detector into a quiet "unreadable" gate failure instead of letting it
raise and fail the test run loudly, which is the same "fail loud, never
silently" principle the rest of this spec is built on (see
`wire_shape.md`'s notes on `classify` and `_change` raising rather than
guessing).

## WHY the Manifest Guard Matters More Than It Looks (code review, 2026-09-10)

The first cut of this module guarded the schema read (`try`/`except`
around `json.loads(schema_path.read_text(...))`) but left the manifest
read bare — `json.loads(manifest_path.read_text(...))` sat outside any
`try` block at all. Both a missing manifest (`FileNotFoundError`) and a
corrupt one (`json.JSONDecodeError`) went uncaught. This looked
asymmetric on the surface — one guard written, a near-identical one
skipped — but the actual defect was not primarily about the missing
structured result. It was about the loop.

`run_wire_gate` calls `gate_one_wire` once per wire, in order, and
appends each result to a list. An uncaught exception from ANY call does
not become that wire's result — it propagates straight out of the loop
and aborts the whole function. So a schema-read failure fails gracefully
(the guard catches it, returns an error result, the loop continues), but
a manifest-read failure — missing OR corrupt — killed `run_wire_gate`
outright, and the other two wires' results were never computed at all.

That is precisely the failure this spec's design decision #2 exists to
prevent: iterate every published wire, report every failure together,
never stop at the first, because CON-4's counters are independent. A
wire added without a manifest is, per the SDD's Error Handling table,
"exactly the gap this spec closes" — and until this guard existed, hitting
that exact gap silently closed the gate on the OTHER two wires too, on its
way past. The structured `error` result the fix now returns is the
visible half of the fix; the loop continuing to gate every other wire in
the same run is the half that was actually load-bearing —
`test_one_broken_manifest_does_not_abort_gating_the_other_wires` in
`tests/test_035_wire_gate.py` is the regression guard for that half
specifically, independent of the error-message assertions in the
missing/corrupt tests beside it.

`FileNotFoundError` is caught ahead of the broader `OSError` (its parent
class) so "missing" and "unreadable" carry a distinguishable
`error_kind` (`ERROR_MANIFEST_MISSING` vs `ERROR_MANIFEST_UNREADABLE`) —
conflating the two would send a maintainer who forgot to commit a
manifest for a new wire looking for a file-permissions bug that does not
exist. **Correction (code review, 2026-09-10):** this paragraph originally
claimed the split alone produced "a different instruction (commit one)
vs (regenerate it)" — at the time that was an overclaim: only the `error`
STRING's wording differed; nothing emitted an actual instruction on the
error path. `render_wire_gate_report` now genuinely does, via
`error_kind` and `ERROR_INSTRUCTIONS` — see "WHY the Renderer Names an
Instruction on Every Failure Branch" below, which is where that claim
became true rather than where it was made.

This also closes T1.2's CON-5 refused-path obligation for real.
`tests/test_035_wire_manifests.py`'s
`test_missing_manifest_fails_the_existence_check` says explicitly that it
only proves `Path.is_file()` and a bare `assert` behave the way the
standard library guarantees, and that "the REAL refused case CON-5
requires... arrives with Phase 2's T2.3."
`test_missing_manifest_fails_with_a_distinct_error_marker` and
`test_one_broken_manifest_does_not_abort_gating_the_other_wires` are
where that promise is actually kept.

## CRITICAL — the Manifest Guard Above Caught Invalid JSON, Not Valid-JSON-Wrong-Shape (code review, 2026-09-10)

`b29a9ac`'s guard caught the manifest FILE failing to read or parse as
JSON. It did not, and could not, catch a manifest that parsed
successfully but lacked the shape this module needs: `manifest["nodes"]`
and `manifest["schema_version"]` were both accessed unguarded immediately
after that `try` block, and `schema["properties"]["schema_version"]
["const"]` was accessed unguarded further down. An empty stub committed
by mistake, another wire's manifest copy-pasted over this one, or a
hand-edit that drops a key — each at least as likely as a truncated file
— raised an uncaught `KeyError` from inside `gate_one_wire`, which
propagates out of `run_wire_gate`'s loop exactly like the missing-file
case did: the SAME defect, at a trigger the first fix did not cover, with
the SAME consequence — the other two wires' results never computed.

The fix is `_validate_schema_shape`/`_validate_manifest_shape`: explicit
checks for the required keys, run immediately after each successful
`json.loads` and BEFORE `describe_shape`/`diff_shapes`/either dict access
that used to be unguarded. A malformed manifest or schema now returns an
`_error_result` (`error_kind` `ERROR_MANIFEST_MALFORMED` /
`ERROR_SCHEMA_MALFORMED`) instead of raising.

This is deliberately validation, not `try: ... except KeyError:` wrapped
around the processing block. A blanket `except KeyError` there would also
swallow a genuine `KeyError` bug surfacing from inside `describe_shape`,
`diff_shapes`, or `classify` — turning an actual regression in the pure
data-model functions into a quiet "manifest malformed" gate result instead
of letting it raise and fail the test run loudly, which is this module's
own stated contract for the OTHER guards (see "WHY `OSError`/
`json.JSONDecodeError` Are Caught Narrowly" above). The distinction that
matters: malformed *input* is a gate result; a broken *algorithm* is a
crash. Validating the specific keys this module reads, rather than
catching whatever exception type happens to result from reading them, is
what keeps that distinction real instead of accidental.

`test_manifest_missing_nodes_key_fails_as_malformed_not_an_uncaught_error`,
`test_schema_missing_properties_key_fails_as_malformed_not_an_uncaught_error`,
and
`test_wrong_shape_manifest_and_schema_do_not_abort_gating_the_other_wires`
are the regression guards — the last one mirrors
`test_one_broken_manifest_does_not_abort_gating_the_other_wires` but for
this trigger specifically, breaking two wires' shapes (not files) in one
run and asserting the third still gates normally.

**Correction (code review, 2026-09-10, re-review): this section's framing
was itself the next mistake.** It presented the fix above as closing "the"
gap, past tense, complete. It was not: a THIRD trigger remained open — a
manifest with valid JSON and valid top-level keys, but one NODE VALUE
inside `nodes` not itself a dict — and it reproduced the identical
loop-abort consequence (`AttributeError` this time, not `KeyError`,
propagating out of `run_wire_gate`'s loop the same way). Each of the first
two fixes validated precisely what the PREVIOUSLY OBSERVED crash
dereferenced — reactive, not derived — which is exactly why a third round
was needed at all, and why a fourth was plausible. See the next section
for the fix that replaced "validate what last crashed" with "validate
every dereference, derived by tracing the code, once." Read this
section's claims as historically accurate about what `a072800` did, not
as a current statement that the guard is complete — the next section is
that statement.

## WHY the Validation Set Is Derived From Dereferences, Not From Observed Crashes (code review, 2026-09-10, third round)

The pattern across three review rounds:

```
1. manifest file missing                                       -> fixed in b29a9ac
2. valid JSON, missing a required top-level key                 -> fixed in a072800
3. valid JSON, valid top-level keys, one node's VALUE wrong type -> fixed here
```

Each prior fix validated exactly what the crash it was responding to
dereferenced, and nothing more — which finds the trigger that already
happened, not the ones that have not yet been observed. The fix this
round instead enumerates every dereference `gate_one_wire`'s downstream
code performs on manifest-sourced (i.e. UNTRUSTED — read from a file)
data, and validates exactly that set. **The forward-looking guarantee
this method offers is about the METHOD, not a claim that this round's
OUTCOME is final** — re-derive from `_diff_node`'s actual dereferences,
verified by direct testing per field, whenever that function changes;
see the correction and the fourth round documented further down this
file, which is exactly what happens when that discipline is applied
carelessly rather than what happens when it is skipped.

**The trace.** `manifest["nodes"]` is handed to `wire_shape.py`'s
`diff_shapes(recorded, observed)` as `recorded`. For every pointer present
in both `recorded` and `observed`, `diff_shapes` calls
`_diff_node(pointer, recorded[pointer], observed[pointer])`, which reads
`old`/`new` (i.e., each `nodes` VALUE) via `old.get("properties")`,
`old.get("required")`, `old.get("closed")`, `old.get("values")`. Every
value in `nodes` must therefore itself support `.get(...)` — be a dict.
That is the check `b29a9ac`'s AND `a072800`'s fixes both stopped short of:
both guarded the manifest's TOP-LEVEL keys (`nodes`, `schema_version`)
existing and having the right type, never the VALUES living inside
`nodes`.

**Below that level, `_diff_node` mostly self-protects for the cases
actually tested this round — verified by direct testing, not assumed, but
see the correction after this section for exactly which cases that was:**

```
old.get("required") or []      # a str is falsy-or-truthy but never crashes
                                # downstream; a STRING-typed required DEGRADES
                                # (iterates characters) rather than raising —
                                # confirmed: diff_shapes({"/x": node(required="oops")},
                                # {"/x": node(required=["a"])}) returns a
                                # (wrong but non-crashing) required_added/
                                # required_removed list, no exception
old.get("properties") or {}    # confirmed non-crashing for a STRING `properties`
                                # whose characters do not overlap the other
                                # side's real property names
bool(old.get("closed"))        # bool(...) never raises for ANY input type
```

**`values` is the one exception, and it is NOT visible from the top-level
check alone.** `_diff_node`'s enum diff does `old_values = old.get("values")
or {}`, then — inside the loop over enum names — `old_values.get(name,
[])`: a SECOND `.get` call, on the value the FIRST line produced. The `or
{}` fallback only fires when the raw `values` is falsy (`None`, `{}`,
`[]`, `""`); a TRUTHY non-dict `values` (a non-empty list or string) sails
past it and reaches the second `.get`, which raises `AttributeError` for
the same reason a non-dict node itself does. Confirmed directly:
`diff_shapes({"/x": node(values=["a","b"])}, {"/x": node(values={"status":
["open"]})})` raises `AttributeError: 'list' object has no attribute
'get'`; the equivalent test with `values="oops"` (a string) raises the
same way. So `values`, specifically, needs the identical dict-or-absent
check the node itself needs — `properties`/`required`/`closed` do not,
because nothing downstream calls a second method on them.

**The trust boundary, confirmed rather than assumed.** `diff_shapes`
takes two node maps: `recorded` (manifest-sourced, the ENTIRE untrusted
surface) and `observed` (built by `describe_shape` from the schema,
always well-formed BY CONSTRUCTION — every node it emits carries
`closed`/`required`/`properties`/`values` with the exact types
`_diff_node` expects, because `describe_shape` builds the dict itself
rather than parsing one off disk). `classify`, the other consumer of
manifest-shaped data, never receives `recorded` at all — its signature is
`classify(change, observed)`, `observed` only, by SDD design (see
`wire_shape.md`). So the complete untrusted-data surface this module's
downstream code dereferences unsafely is exactly: `manifest["nodes"]`
(each value must be a dict) and, within each node, its `values` field
(must be a dict when present). Nothing else in the pipeline reads
file-sourced data without going through `describe_shape` first.

`_validate_manifest_shape`'s docstring carries this same trace inline, so
a future change to `_diff_node` that reads a NEW field is the trigger to
re-run this derivation, not to wait for a fourth crash report.

`test_manifest_node_value_not_a_dict_does_not_abort_gating_the_other_wires`
and `test_manifest_node_values_field_not_a_dict_fails_as_malformed` are
the regression guards for the two derived checks; the first also proves
the loop-continuation half in the same call, mirroring
`test_one_broken_manifest_does_not_abort_gating_the_other_wires`.

**Correction (code review, 2026-09-10, re-review): the "verified by
direct testing" claim above was true for `required` and false for
`properties`, and the sentence did not distinguish them.** A verification
pass fuzzed 15 corruption cases against the real committed manifests and
found zero loop aborts, and that result was reported as confirming this
section's derivation. It was a false negative. `_diff_node` only
evaluates `old_properties[name]` for `name` in `set(old_properties) &
set(new_properties)` — a SUBSCRIPT gated by an intersection. The fuzz
run's corrupt `properties` values did not happen to share any names with
the real schema's properties, so that line never executed; a corrupt
value that DOES overlap (e.g., a list containing the node's own real
property names) reaches the subscript and raises `TypeError` immediately.
**A conditional dereference is invisible to fuzzing unless the corrupt
input is adversarial with respect to the OTHER side of the comparison.**
`.get(...)` calls are unconditional and turn up in any fuzz run;
subscripts guarded by a set intersection only fire on overlapping data,
and only reading `_diff_node` top to bottom — tracing what CAN happen,
not sampling what DID happen in N trials — reliably finds them.

The `required` half of the same sentence had the opposite problem:
tested, but only for one input shape. `old.get("required") or []` is only
ever passed to `set(...)`, never subscripted — but `set(...)` itself
raises `TypeError` for a non-iterable TRUTHY value (an int, a bool, a
float), a case the string-only test never exercised. `required` therefore
needed a type check too, alongside `properties`, both added the same
round the `properties` gap surfaced. See
`_validate_manifest_shape`'s current docstring for the corrected,
per-field account of exactly what was traced and what direct testing
confirmed for each — dict for `properties`/`values`, list for `required`,
no check for `closed`.
`test_manifest_node_properties_field_wrong_type_fails_as_malformed_adversarially`
and its loop-continuation sibling build the corrupt value adversarially
(the node's own real property names) specifically so the test cannot pass
by the same accident the fuzz run did;
`test_manifest_node_required_field_non_iterable_fails_as_malformed`
covers the non-iterable case the string-only verification missed.

## WHY the Renderer Names an Instruction on Every Failure Branch, Error Branches Included (code review, 2026-09-10)

The module docstring has always promised "a message that says what to
do". Before this fix that promise held only for the shape-diff branches —
`ACTION_MOVE_VERSION`/`ACTION_HANDOVER`/`ACTION_REGENERATE_MANIFEST` each
render into an imperative line. The three (now five) error branches ended
with the diagnosis and nothing else:
`instructions.schema.json: manifest missing: /path/...`, full stop.
Diagnosable, not instructional — the same gap between "detected" and
"actionable" this whole spec exists to close, recurring one field over.

`render_wire_gate_report` now appends a second line for every error
result, looked up from `ERROR_INSTRUCTIONS` by `error_kind`: a missing
manifest says to generate and commit one; an unreadable or malformed
manifest says to regenerate it; an unreadable or malformed schema says to
fix the file. The missing-vs-other split matters specifically because
"regenerate" implies a starting point that a genuinely missing manifest
does not have — telling a maintainer who forgot to commit a manifest to
"regenerate" it points them at a file that does not exist yet.

## WHY `ACTIONS`/`ERROR_KINDS` Get the Same Treatment `CHANGE_KINDS` Got in `wire_shape.py` (code review, 2026-09-10)

Before this fix, `ACTION_MOVE_VERSION`/`ACTION_HANDOVER`/
`ACTION_REGENERATE_MANIFEST` were three bare constants with no collecting
tuple, and the renderer inferred `regenerate_manifest` by the ABSENCE of
`move_version` in `result["actions"]` rather than by checking what was
actually there. Code review named this the more fragile shape than
`wire_shape.py`'s `CHANGE_KINDS` + `classify`-raises-on-unknown mechanism:
an action added to `actions` that the renderer had no branch for would
silently fall into the `else` and render the WRONG instruction, never
signalling anything went wrong.

`ACTIONS` (a tuple) and `ACTION_INSTRUCTIONS` (a dict keyed by the same
constants) now give the renderer something to check identity against:
`_render_action` looks up each action in `result["actions"]` and raises
`ValueError` for one it has no instruction for, rather than defaulting to
the wrong line. `ERROR_KINDS`/`ERROR_INSTRUCTIONS`/`_render_error` are the
same mechanism applied to the error branches, for the same reason.
`test_render_wire_gate_report_raises_on_an_unregistered_action` and
`test_render_wire_gate_report_raises_on_an_unregistered_error_kind` are
the regression guards, mirroring `wire_shape.py`'s
`test_classify_raises_on_an_unregistered_kind`.

**This was still only half of `CHANGE_KINDS`'s mechanism (code review,
2026-09-10, re-review).** `wire_shape.py` has FOUR parts: the tuples, a
raise at render/classify time, iterating tests, AND a raise at
CONSTRUCTION time (`_change` validates `kind` against `CHANGE_KINDS`
before building a `ShapeChange` at all — see `wire_shape.md`'s note on
why `_change` checks it, not just `classify`). `_render_action`/
`_render_error` gave this module the first three parts but not the
fourth: `_result`/`_error_result` accepted `actions`/`error_kind`
unchecked, so an unregistered value only ever raised if something
happened to RENDER the result — a caller reading `error_kind` by identity
without ever calling `render_wire_gate_report` (T4.1's CLI branching on
exit codes is the obvious future example) would see a bad value sail
through unnoticed.

`_result` now validates both — `actions` against `ACTIONS`, `error_kind`
against `ERROR_KINDS` — before building the dict, matching `_change`'s
placement exactly: at the one function every `WireGateResult` passes
through, not at the one function that happens to print it.
`test_result_raises_at_construction_for_an_unregistered_action` and
`test_result_raises_at_construction_for_an_unregistered_error_kind` are
the regression guards for this half specifically — they call `_result`
directly (via `import lib.wire_gate as wire_gate`, the same pattern
`test_035_wire_classify.py` uses to reach `wire_shape.py`'s private
`_change`) and never touch `render_wire_gate_report`, so they cannot pass
by accident of the renderer catching the bad value first.

## WHY `error_kind` Exists Beside the Human `error` String (code review, 2026-09-10)

Before this fix, `manifest missing` vs `manifest unreadable` vs `schema
unreadable` were distinguishable only by substring-matching the `error`
sentence — and the tests already did exactly that
(`"missing" in result["error"].lower()`). Nothing in production branched
on it yet, but that is precisely the situation ADR-2 already ruled out for
`detail`: a human-readable string is for humans, and the trap is adding
the FIRST piece of code that parses it back, because after that the
string is load-bearing and can no longer be reworded freely. T4.1's CLI
is the obvious near-term consumer — distinct exit codes per failure kind —
so `error_kind` (one of `ERROR_KINDS`) was added now, while the shape is
still cheap to change, rather than after a consumer already depends on
prefix-matching `error`. Tests were updated to assert `error_kind` by
identity as the primary check, keeping the substring assertions only as a
secondary check that the human text still mentions the right word.

## WHY the Three Result-Building Call Sites Collapsed Into `_result`

`gate_one_wire` used to list the same nine keys (ten, after `error_kind`)
independently at three call sites: the error branch, the pass branch, and
the fail-with-changes branch. Nothing enforced that the three agreed on
the field set — a key added to one and forgotten in another would only
surface as a `KeyError` in whatever test happened to read the missing
field, not as an obvious defect at the point of the omission. `_result`
is the one place the `WireGateResult` shape is written down; every
return site now calls it with only the fields that differ from the
all-`None`/empty default, which happens to make the error-result shape
`_error_result` builds nearly free (`_result(document, passed=False,
error=..., error_kind=...)` — everything else defaults correctly).

## WHY `ACTION_INSTRUCTIONS`/`ERROR_INSTRUCTIONS` Are Underscore-Prefixed (T4.1, code-quality review)

Both dicts back `_render_action`/`_render_error` — the instruction line
each renders for one `ACTIONS`/`ERROR_KINDS` member. They used to be
module-level names with no underscore, same as `ACTIONS`/`ERROR_KINDS`
themselves, but this module's `__all__` (added T4.1, alongside the
`manifest_filename` re-export below) only ever listed `ACTIONS`/
`ERROR_KINDS` — the two constants a caller needs to reason about the
vocabulary, never the instruction TEXT for each member, which nothing
outside `_render_action`/`_render_error` reads. An un-prefixed name absent
from `__all__` is exactly the inconsistency `__all__` exists to prevent:
it either means the module's public surface, or it doesn't say anything.
Renamed to `_ACTION_INSTRUCTIONS`/`_ERROR_INSTRUCTIONS` rather than added
to `__all__`, because nothing needs to import the instruction strings
directly — a caller that wants to know whether an action exists checks
`ACTIONS`; the rendered sentence is `render_wire_gate_report`'s job alone.

## WHY `manifest_filename` Moved to `wire_shape.py`, and Why This Module Still Exports It (T4.1)

This module used to define `manifest_filename` itself. T4.1's code-quality
carry-forward found it had grown a SECOND independent copy in
`tests/test_035_wire_manifests.py`'s `_manifest_path` (hand-written
stem-slicing, not an import) — the exact naming convention this module
already owned, duplicated a second time without either copy knowing about
the other. The function body moved to `wire_shape.py`, next to
`PUBLISHED_WIRES` (both are pure data about the manifest-file convention,
no filesystem access), and this module now does `from lib.wire_shape
import ..., manifest_filename` and re-exports the same name via `__all__`
— so `gate_one_wire`/`run_wire_gate` (which call it to resolve
`shapes_dir`/manifest paths) and every existing `from lib.wire_gate import
manifest_filename` call site keep working with zero changes. See
`docs/tomo/scripts/lib/wire_shape.md`'s "WHY `manifest_filename` Lives
Here" for the full history. `scripts/wire-shape.py` (T4.1) is the newest
consumer, importing it from `lib.wire_gate` alongside `run_wire_gate` and
`render_wire_gate_report` — the CLI never re-derives the naming convention
independently either.

## WHY the Upstream-Hashi Snapshot Check Became a Report, Not This Module's Gate (spec 035 T2.4)

`tests/test_instruction_render_wire_hygiene.py::test_snapshot_matches_upstream_hashi`
is a third, older drift check that predates `wire_gate.py` — it compares
Tomo's committed `tomo/schemas/hashi-instructions.schema.json` snapshot
against Hashi's LIVE schema fetched from GitHub, not against one of our own
manifests. T2.4 rewrote its comparison surface to reuse this module's
building blocks (`describe_shape` + `diff_shapes`, imported from
`wire_shape.py`) instead of the old `$defs`-entries-carrying-an-`action`-
property intersection, which was measurably vacuous: zero `$defs` on
`suggestions-wire.schema.json` / `garden-audit-wire.schema.json` meant zero
comparisons, and it never looked at root-level fields on either document at
all.

The result is deliberately **not** wired into `gate_one_wire`/`run_wire_gate`
above, and deliberately never fails on a delta — it prints one
(`_snapshot_parity_delta` + `_render_snapshot_parity_report`, both local to
the test file). This is ADR-7, not an oversight: ADR-7 already ruled that a
*vendored consumer copy* — which is what this snapshot is — is a report,
never a gate, because it is *supposed* to lag ours between a cross-repo
handoff going out and Hashi confirming it. The registry that used to carry
this exemption by hand, `SNAPSHOT_AHEAD_OF_UPSTREAM` (three action names:
`edit_note_text`, `resolve_dead_link`, `remove_up_link`), is deleted rather
than re-keyed to the new comparison surface — a report needs no exemptions,
only a delta, and keeping an exemption registry beside a mechanism that
never fails would be dead weight with nothing left to exempt.

This module's own gate (`gate_one_wire`/`run_wire_gate`) is unaffected and
keeps its ADR-3 contract (any shape change fails) — it describes OUR OWN
schema against OUR OWN committed manifest, which carries no wait-window: we
are both producer and the party responsible for regenerating it. The
snapshot check compares against a THIRD PARTY's live copy over the network,
which is exactly the situation ADR-7 draws the report/gate line at. The two
should not be confused, and a future task extending `ACTIONS`/`ERROR_KINDS`
here must not assume it also covers the snapshot check's shape.

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

`gate_one_wire`'s parse-failure branch catches exactly the two exception
types a malformed or missing schema FILE can raise. A bare `except` would
also swallow a real bug surfacing from inside `describe_shape`,
`diff_shapes`, or `classify` — turning an actual regression in the drift
detector into a quiet "schema unreadable" gate failure instead of letting
it raise and fail the test run loudly, which is the same "fail loud, never
silently" principle the rest of this spec is built on (see
`wire_shape.md`'s notes on `classify` and `_change` raising rather than
guessing).

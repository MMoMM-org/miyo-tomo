# WHY: lib/wire_snapshot_parity.py

> Rationale for decisions in `tomo/scripts/lib/wire_snapshot_parity.py`.
> The snapshot-vs-upstream REPORT for a vendored consumer copy (spec 035 T2.4, generalised T4.2).

## WHY This Module Exists, and Why It Moved Out of a Test File

T2.4 built `_snapshot_parity_delta` and `_render_snapshot_parity_report`
inside `tests/test_instruction_render_wire_hygiene.py` — correct at the
time: one document (`hashi-instructions.schema.json`), one caller
(`test_snapshot_matches_upstream_hashi`). Extracting a module for a single
caller would have been speculation.

T4.2 is where that stopped being correct. It wires up the second and third
vendored copies — `hashi-suggestions-wire.schema.json` and
`hashi-garden-audit-wire.schema.json` — giving this comparison three
documents and three callers, and it is exercised from
`TestVendoredCopies`'s offline fixture tests as well as the network drift
tests. Production code must never import from a test module (MiYo
Constitution, Code Quality), so the two helpers moved to
`tomo/scripts/lib/wire_snapshot_parity.py`, a sibling of `wire_shape.py` and
`wire_gate.py`, before the second and third copies were wired up — not
after. `wire_gate.py` made the identical move one phase earlier (T2.3), for
the identical reason; see its own module docstring and
`docs/tomo/scripts/lib/wire_gate.md`.

`tomo/scripts/lib/` rather than `scripts/`: this repo's directory
convention splits by invocation (`scripts/` is user-invoked CLI,
`tomo/scripts/lib/` is a library consumed by other code — see
`feedback_scripts_dir_boundary_user_invoked` in project memory). This
module is consumed by tests today; nothing user-invoked calls it directly.

## WHY ADR-7 Names Two Different Comparisons, and Why Conflating Them Is the Likely Failure Mode

A published wire schema has two distinct things worth comparing it
against, and they answer different questions with different baselines and
different tolerance for failure:

| comparison | question | baseline | network? |
|---|---|---|---|
| our schema <-> the **committed** vendored copy | does the consumer accept what we emit? | their file, as checked in | no |
| the committed vendored copy <-> **live** upstream | is our copy stale? | their file, as fetched | yes |

Both comparisons run through the same `snapshot_parity_delta` function —
it does not know or care which one it is being asked to run. What
distinguishes them is entirely in the CALLER: `TestVendoredCopies` in
`tests/test_instruction_render_wire_hygiene.py` runs the first, hermetic
and offline, asserting the actual measured delta (T4.2: `up_source` and
`up_value` on `findings[].detail`, ours-only, for garden-audit; a
structurally-identical zero-delta for suggestions). `TestHashiSchemaParity`
runs the second, over the network, and never asserts on the delta's
content at all — only that fetching and reporting it does not raise.

Conflating them — asserting the FIRST comparison's known delta against the
SECOND comparison's live-fetched baseline — produces a test that goes red
every time Hashi edits their schema, with no defect of ours behind it, and
couples this suite's health to a file another team owns. This is why
`TestVendoredCopies::test_garden_audit_comparison_a_reports_known_delta_offline`
reads its two schemas from disk only (`tomo/schemas/garden-audit-wire.schema.json`
and the committed `hashi-garden-audit-wire.schema.json`) and never touches
`urllib`.

## WHY `recorded` Is Always the Vendored Copy, Never Our Own Schema

`snapshot_parity_delta(recorded_schema, observed_schema)` follows
`diff_shapes`'s own direction convention. Both ADR-7 comparisons this
module serves hold the **committed vendored copy** as `recorded` — our own
live schema is `observed` for the offline comparison, and a freshly
fetched live document is `observed` for the network comparison. Keeping
`recorded` fixed to the vendored copy in both calls means an
`added_property` always reads the same way regardless of which comparison
produced it: "present on the other side, not (yet) in the committed copy"
— i.e. ours-only. Swapping the arguments for one of the two call sites
would flip that reading to `removed_property` for the exact same fact,
which is confusing to a maintainer skimming a printed report without also
checking which test produced it. Do not swap the arguments at a call site.

## WHY the Delta Is Deliberately Unclassified

`snapshot_parity_delta` never calls `classify` — every returned
`ShapeChange` carries `consumer_affecting: False` (the `_change` default
inside `wire_shape.py`). This is correct for both comparisons this module
serves, not an oversight carried over from T2.4: a vendored copy lagging
ours between a cross-repo handoff and the consumer's confirmation obliges
nobody, and ADR-7 is the entire reason this module is a report and not a
gate. If `classify` is ever wired in here, this stops being a report and
becomes a second gate with no version-move escape hatch — it would fail a
build during the WAIT window ADR-7 exists to protect, silently reproducing
the exact bug `wire_gate.py`'s ADR-3 contract was built to avoid on the
OWN-schema side. See `snapshot_parity_delta`'s own docstring, which states
this in the same words so a future edit finds the warning at the point of
change, not just here.

## WHY the Renderer Took the Multi-Document Form, Not a Second Single-Document One

T2.4's `_render_snapshot_parity_report(document, changes)` took exactly one
document because exactly one existed. T4.2 needed the same rendering logic
for three documents from up to three different callers in the same test
run (`TestUpstreamFetchSkip`'s offline assertion, `TestVendoredCopies`'s
two offline comparisons, `TestHashiSchemaParity`'s three network
comparisons). Rather than keep the single-document form and duplicate a
loop at every call site — or worse, grow a second renderer — it was
generalised on the way across to `render_snapshot_parity_report(results:
list)`, where each entry is `{"document": ..., "changes": ...}`. This
matches `wire_gate.py`'s `render_wire_gate_report(results)` signature
exactly, so the two report families (gate-side, vendored-copy-side) read
alike to a maintainer moving between them, and the spec keeps one
reporting signature instead of two that differ only in arity. A caller
comparing a single document passes a one-entry list — see
`_check_upstream_drift` in the test file.

## WHY Two Cosmetic Fixes Landed With the Move

Neither is a defect — both were carried over unfixed since T2.4 and made
the report harder to read than necessary while the rendering code was
being touched anyway:

- **A root-level change used to render as bare leading whitespace.**
  `change["pointer"]` is `""` for a root-level change (see
  `wire_shape.py`'s `diff_shapes`), and the old renderer printed
  `f"  {change['pointer']} {change['kind']}: ..."` — with an empty
  pointer, that line opened with three spaces and no visual marker at all
  that this change applies to the schema's root. `render_snapshot_parity_report`
  now substitutes `"(root)"` for an empty pointer.
- **`detail` restated `kind` verbatim for node-level changes.** For
  `node_removed`/`node_added`, `wire_shape.py`'s `_diff_node` builds
  `detail` as `f"node removed: {pointer}"` / `f"node added: {pointer}"` —
  the OLD renderer's `f"{kind}: {detail}"` format then printed
  `node_removed: node removed: /$defs/x`, a literal duplication. Every
  `detail` string in `wire_shape.py` already names its own kind in prose
  (`"added property: ..."`, `"required gained: ..."`, `"closed: ... -> ..."`,
  etc.), so the renderer now prints `pointer` + `detail` only, never
  `kind` — the redundancy was never load-bearing, since `kind` is still
  present in the structured `ShapeChange` dict for any caller that needs
  to branch on it.

## WHY the Fetch Is Routed Through One Function (`_fetch_schema_json`), and What `_fetch_or_skip` Treats as Unreachable

This module never touches the network itself — CON-2 requires the
detection to pass offline, and `snapshot_parity_delta` is pure. The
network side lives entirely in the test file
(`tests/test_instruction_render_wire_hygiene.py`), in two small functions:
`_fetch_schema_json(url)` makes the one `urllib.request.urlopen` call, and
`_fetch_or_skip(url)` wraps it, turning any failure into `pytest.skip`
rather than a failure or (worse) a fabricated delta.

The fetch is genuinely flaky, not theoretically so: building this task hit
`http.client.IncompleteRead` **twice** against
`garden-audit-wire.schema.json` specifically, in the same run that fetched
the other two documents fine. `IncompleteRead` is a **partial** response,
not an absent one — it does NOT inherit from `OSError`, so it needs its
own branch in `_fetch_or_skip`'s `except` tuple
(`http.client.HTTPException`). Letting a partial read reach `json.loads`
unguarded risks two outcomes: it raises (the common case, and still just
"unreachable"), or — far worse — it parses as a smaller-but-valid schema,
and the report then claims the consumer **removed** properties they never
removed. That is a fabricated obligation, the exact inverse of the failure
this spec exists to prevent. `json.JSONDecodeError` gets the same
treatment for the same reason: a truncated-but-parseable-looking body is
"network gave us garbage," not genuine drift.

`TestUpstreamFetchSkip` proves the skip path is RED-provable without
waiting on the network to misbehave: it monkeypatches
`_fetch_schema_json` directly (not `urllib.request.urlopen` — that
end-to-end variant is `test_incomplete_read_during_fetch_skips_not_fails`,
kept alongside as the proof the real call raises what the seam-level tests
assume), separately for `IncompleteRead`, `URLError`, and `TimeoutError`,
and asserts BOTH that `_fetch_or_skip` skips AND that the offline
comparison (this module's `snapshot_parity_delta` against the committed
garden-audit copy) still produces its correct delta afterward — proving a
patched, failing network seam cannot leak into or block the
network-free path.

## WHY the Offline Comparison Asserts the Measured Delta, Not an Assumed One

`TestVendoredCopies::test_garden_audit_comparison_a_reports_known_delta_offline`
asserts the `added_property` changes are exactly `{"up_source",
"up_value"}` — matching the ground truth measured for the T4.2 handoff
("our eight properties on `findings[].detail` against their six"). A
fuller run of `snapshot_parity_delta` over the whole schema (not just
`findings[].detail`) also surfaces one further, genuine, ours-only delta:
the `check` enum on `findings[].items` carries `parent_not_moc`, which
Hashi's committed copy does not. This is not a contradiction of the
ground truth — the handoff's "exactly `up_source` and `up_value`" claim
was scoped to properties on `findings[].detail`, and the test's assertion
is scoped the same way (`kind == "added_property"` at that pointer),
deliberately not widened to a stronger "exactly these six changes,
nothing else" claim that was never actually measured end-to-end against a
running comparison. `test_suggestions_comparison_a_reports_measured_delta_offline`
follows the same discipline in the other direction: the measured delta for
suggestions-wire.schema.json against its vendored copy is empty, and the
test asserts exactly that — an assumed non-empty delta would have been a
guess dressed as a measurement.

## Who Notices When a Vendored Copy Goes Stale, and What "No Delta" Means on That Day

A vendored copy is a snapshot of a file another team owns and changes
without telling us. This module gives it exactly one mechanism for
staying current: `TestHashiSchemaParity`'s three network tests, run
whenever this suite runs with network access, print a delta to stdout
when the committed copy has drifted from Hashi's live file — nothing
enforces that anyone reads that output, and nothing re-vendors the copy
automatically. There is no cron, no CI gate, no version check that fires
on staleness; the "report, never a gate" contract that makes this
comparison correct during the WAIT window (ADR-7) is the same contract
that means a THREE-MONTH-STALE copy produces the identical `""` (silent,
all-clear) output as a copy refreshed yesterday, if upstream Hashi also
happened not to change anything in that window. **"No delta because we
are in sync" and "no delta because nobody has looked in three months" are
indistinguishable from this module's output alone** — the only thing
that changes is the LIKELIHOOD that a real delta would have shown up by
now, and this module carries no notion of elapsed time to make that
distinction externally visible (no last-refreshed timestamp is stored
anywhere in `tomo/schemas/`).

The offline comparison (our schema against the committed copy) is
unaffected by this question — it always compares against whatever is
actually committed, however old — but that is precisely why it cannot
answer "is our copy stale" either; it only ever answers "does the
consumer accept what we emit, AS OF the last re-vendor." Closing this gap
(a recorded fetch date, a scheduled re-vendor reminder, a CI job that runs
the network tests on a cadence and posts the output somewhere a human
reads) is out of scope for T4.2, which is the manual `wire-shape.py`
maintainer CLI plus this report — not an unattended freshness monitor. It
is named here explicitly so a future maintainer does not read "the tests
are green" as "the vendored copies are current."

---
title: "Phase 4: The CLI, the consumer copies, and closing the live drift"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: The CLI, the consumer copies, and closing the live drift

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-3, ADR-7]`
- `[ref: SDD/Runtime View]` — the maintainer's loop
- `[ref: SDD/Known Technical Issues]` — the knowingly non-empty report window
- `[ref: PRD/Feature 4]`, `[ref: PRD/Feature 6]`, `[ref: PRD/Feature 8]`

**Key Decisions**:
- **ADR-3** — regeneration prints the diff. A silent rewrite makes the deliberate act
  indistinguishable from a reflexive one, which is the only thing keeping the manifest honest.
- **ADR-7** — the vendored copies are a **report**, never a gate. They are supposed to lag during a
  wait.
- Cross-repo work is a handoff and a **wait**. Nothing in this phase automates a cross-repo action.

**Dependencies**:
- **Phases 1, 2 and 3 complete.**

**This phase cannot be completed inside this session.** T4.3 ends by writing a handoff and stopping;
T4.4 can only run once the consumer has vendored and the owner has returned with that result.

---

## Tasks

Makes the mechanism usable by a person, and closes the drift that would otherwise sit in its report
from day one.

- [x] **T4.1 The `wire-shape` command** `[activity: backend-api]`

  Lives in `scripts/` rather than `tomo/scripts/` — the boundary in this repo is by invocation, and
  this one is invoked by a person, not by a runtime agent.

  1. Prime: read the maintainer's loop `[ref: SDD/Runtime View]` and ADR-3.
  2. Test:
     - `--check` exits non-zero on a drifted schema and zero on a clean one;
     - `--regenerate` rewrites the manifests **and prints the diff it applied** — a silent rewrite
       fails this test;
     - `--obligations` prints one row per changed field with pointer, change, whether it obliges the
       consumer, and the version transition;
     - `--regenerate` on an unchanged tree writes nothing and says so;
     - every output is metadata only — no schema prose, no vault content.
  3. Implement: `scripts/wire-shape.py` wrapping `describe_shape` / `diff_shapes` / `classify`.
  4. Validate: unit tests pass; ruff clean.
  5. Success:
     - [x] Regeneration prints the diff it applied `[ref: SDD/Architecture Decisions; ADR-3]`
     - [x] `--obligations` output is the handoff's raw material `[ref: PRD/F4-AC2]`
     - [x] Output carries no prose and no content `[ref: SDD/System-Wide Patterns]`

  **Carried forward from T1.2's code-quality review (2026-09-10)** — three items deliberately
  deferred to this task rather than fixed early, because each only becomes real once a CLI feeds
  `build_manifest` something other than the three known-good schemas:

  a. **`build_manifest` raises a bare `KeyError` on malformed input.** It reads
     `schema["properties"]["schema_version"]["const"]` directly, so a schema missing that path — or
     declaring the version as an `enum` rather than a `const` — fails with `KeyError('const')` and no
     mention of which document caused it. Harmless while the only callers are the three published
     wires; illegible the moment this command accepts a path from a person. Raise a `ValueError`
     naming the source and the missing key, and test the message.
  b. **Write with `encoding="utf-8"`.** `serialize_manifest` uses `ensure_ascii=False`, and the
     round-trip test reads with an explicit UTF-8 encoding. Nothing yet pins the *write* side,
     because generation was ad hoc. If a property name or enum value ever goes non-ASCII, a
     regeneration that writes in the platform default would stop matching the committed bytes and
     the byte-for-byte contract would break for a reason nobody would look for.
  c. **Promote the manifest-path derivation.** The `X.schema.json` -> `X.shape.json` convention lives
     only in the test helper `_manifest_path`. One place is not duplication, but this command needs
     the same convention — move it into `wire_shape.py` rather than writing it a second time.

- [x] **T4.2 All three consumer copies are vendored, and reported against** `[activity: data-architecture]`

  **Carried forward from T2.4's code-quality review (2026-09-10) — do this BEFORE wiring the second
  and third copies, not after.**

  T2.4 built the snapshot-vs-upstream report as two helpers, `_snapshot_parity_delta` and
  `_render_snapshot_parity_report`, **inside `tests/test_instruction_render_wire_hygiene.py`**. That
  was correct for T2.4, which has exactly one caller and one document — extracting a module for a
  single caller is speculation. **This task is where it stops being correct**: three documents, three
  callers, and production code that must never import from a test module. T2.3 already walked this
  path — its gate was built in a test file and moved to `tomo/scripts/lib/wire_gate.py` once T4.1's
  CLI needed it. Move these two the same way before adding callers, rather than duplicating them
  twice and consolidating later.

  Two shape changes fall out of the move, both known now:

  a. **`_render_snapshot_parity_report(document, changes)` is single-document.** `wire_gate.py`'s
     `render_wire_gate_report(results)` iterates many, each carrying its own `document`. Generalise
     to the multi-document form on the way across, so the spec keeps one reporting signature instead
     of two that differ only in arity.
  b. **The delta is deliberately unclassified.** `_snapshot_parity_delta` never calls `classify`, so
     every change carries `consumer_affecting: False` and the rendered line has no
     affecting/not-affecting marker. That is right for a vendored-copy report — a lagging copy
     obliges nobody, and ADR-7 is the reason this is a report at all. Keep it unclassified when you
     move it, and say so in the docstring, or the next reader will "fix" the missing marker and
     quietly reintroduce a gate's semantics into a report.

  Cosmetic, inherited from the shared renderer rather than introduced here, worth fixing while the
  rendering is being touched: a root-level change (pointer `""`) renders as bare leading whitespace
  with no marker, and `detail` restates `kind` (`node_removed: node removed: /$defs/x`). Neither is a
  defect; both make a report meant for human eyes slightly harder to read than it needs to be.

  1. Prime: read ADR-7, and note **why this is a report**: a vendored copy lags ours by design between
     handoff and confirmation, so a gate here would fail during correct operation.
  2. Test:
     - a copy exists for each of the three published wires;
     - the comparison **reports** a delta and does not fail on one;
     - it **skips** when the consumer's published copy is unreachable, and the local checks still run
       `[ref: PRD/F8-AC2]`;
     - the garden-audit comparison reports exactly the known delta today — our eight properties on
       `findings[].detail` against their six.
  3. Implement: fetch and commit `hashi-suggestions-wire.schema.json` and
     `hashi-garden-audit-wire.schema.json` alongside the existing instructions copy; extend the
     network test to all three.
  4. Validate: unit tests pass; ruff clean; the suite passes **offline**.
  5. Success:
     - [ ] Three consumer copies are vendored `[ref: SDD/Architecture Decisions; ADR-7]`
     - [ ] Unreachable upstream skips rather than fails `[ref: PRD/F8-AC2]`
     - [ ] The known garden-audit delta is reported `[ref: PRD/F8-AC1]`

- [x] **T4.2b The daily side gains its source identity** `[activity: data-architecture]`

  The change this spec promised the consumer on 2026-09-09 and then lost when the PRD was drafted.
  It is a wire change like any other, so it goes through the mechanism the earlier phases built —
  which is the honest test of whether that mechanism is usable.

  1. Prime: read `[ref: PRD/Feature 9]` and the consumer's own request. Note the third bucket is the
     sharper case: it carries **no** source identity today, so a consumer cannot join it back to its
     origin ambiguously or otherwise.
  2. Test:
     - all three daily buckets declare the identity field, **required** on each;
     - the existing display-text field is untouched;
     - the gate (Phase 2) classifies this as consumer-affecting — the buckets are closed nodes — and
       demands the version move;
     - with the version moved, the gate passes;
     - the lossy round-trip recovery is no longer exercised, and its removal breaks no test that was
       passing before.
  3. Implement: widen the suggestions wire; move its `schema_version`; regenerate its manifest and
     capture the printed diff; retire the recovery path.
  4. Validate: unit tests pass; ruff clean; full suite green.
  5. Success:
     - [ ] All three buckets carry a required source identity `[ref: PRD/F9-AC1]`
     - [ ] The bucket that had none now has one `[ref: PRD/F9-AC2]`
     - [ ] The display field is unchanged `[ref: PRD/F9-AC3]`
     - [ ] The lossy recovery is retired `[ref: PRD/F9-AC4]`

- [x] **T4.3 One handoff for the whole release — then STOP** `[activity: validate]`

  **This handoff carries the entire release, not just the garden-audit half.** The consumer asked
  for one changed-fields list and one vendoring pass; three separate handoffs for one release is the
  outcome that request exists to prevent. Three documents move together:

  | Document | Change | Source |
  |---|---|---|
  | garden-audit wire | disclose `up_source` / `up_value`, already emitted | this spec, F6 |
  | garden-audit wire | disclose `parent_not_moc`, already emitted — **breaks them**, unlike the row above | found 2026-09-11 during T4.2 |
  | suggestions wire | daily-side source identity on three buckets | this spec, F9 (T4.2b) |
  | instructions wire | `delete_source` gains its dependency field | **spec 036**, whose T4.5 supplies the half rather than sending its own handoff |

  1. Prime: re-read what is actually drifted — our schema declares `up_source` and `up_value` on
     `findings[].detail`; the consumer's declares neither. It is benign **only** because that node is
     open on both sides `[ref: PRD/Problem Statement]`. Then confirm 036's instruction-wire half is
     ready to travel; if it is not, say so and send the two documents this spec owns.
  2. Test: after the version move, the gate passes for the garden-audit wire; the manifest records
     the new version; the emitted document carries it (via T3.1, without a code edit).
  3. Implement:
     a. Move the garden-audit wire's `schema_version` — **and its `description`**, which currently
        reads "always '1'". ADR-2 excludes prose from the manifest, so nothing will flag the
        contradiction; a schema whose own text denies its version is worse than one that never
        moved.
     b. Regenerate its manifest and capture the printed diff.
     c. Write the handoff to `_outbox/for-hashi/`: the schema **file** attached, plus the obligation
        table stating that these fields have been emitted since an earlier spec, that they are
        currently benign because the node is open, and that this stops being true if the node is ever
        closed.
     d. **Stop.** Tell the owner what to run and do not advance this thread. Nothing after this point
        may assume the consumer has acted.
  4. Validate: the attached file is byte-identical to the repository's; the obligation table matches
     the diff exactly; the handoff states it is a disclosure of an existing emission, not a new field.
  5. Success:
     - [ ] The handover states the fields are already being emitted `[ref: PRD/F6-AC1]`
     - [ ] The schema is attached, not described `[ref: PRD/F4-AC1]`
     - [ ] Breaking-when is stated explicitly rather than left derivable `[ref: PRD/F4-AC3]`
     - [ ] Emission of the new version waits for confirmation `[ref: PRD/F4-AC4]`
     - [ ] One handover, one obligation table, covering every document in the release `[ref: PRD/F9-AC5]`

  **Worth raising in the same handoff, unprompted**: the consumer's analysis of their namesake bug
  cites `forceAtomicSync.ts:31` and `:47` — of which only `:47` is a `source_stem` join (`:31` joins
  on `suggestion.stem`). There is a **further** `source_stem` join they have not named, at
  `SuggestionsTab.ts:180-181` (`collectDailyLogStems`), with the same key and the same fan-out.
  Found while researching this spec.

  **A second garden-audit change, and this one is not benign — found 2026-09-11 during T4.2.**
  Our `findings[].check` enum carries seven values; the consumer's vendored copy carries six. Ours
  only: `parent_not_moc`.

  This does **not** behave like `up_source`/`up_value`. Those are safe because `findings[].detail` is
  an open node on both sides, and an open node ignores what it does not declare. **An enum is not
  protected by openness** — a validator rejects a value outside the declared set regardless of
  `additionalProperties`, which is why this spec's own measurement classes an added enum value as
  consumer-affecting. So the moment a run produces a `parent_not_moc` finding, the document we emit
  is one their validator refuses.

  Tomo emits it today: it is a shipped feature with its own rendering, grouping and severity mapping
  (`garden-audit-render.py:70,227-249`, `garden-audit-stats.py:51,59,69`).

  **It came from `2111772` — the same commit this spec's decision log already cites** for
  `up_source`/`up_value`. The pre-implementation research found two of that commit's three wire
  changes and stopped at `findings[].detail`. The spec written about an unannounced schema change
  missed part of the very change it was written about; only running the finished detector over real
  consumer data surfaced it. That is the strongest available argument for the mechanism, and it
  belongs in the record rather than being quietly folded in.

  The handoff must state the distinction plainly: one disclosure is benign and the other is not, and
  a reader who treats both rows the same will deprioritise the one that matters.

  **The obligation table must name a new property's accepted values by hand.** A `classify` fix on
  2026-09-11 stopped `diff_shapes` from decomposing a newly-added property into one
  `added_enum_value` per value — correct, because the consumer cannot violate an enum on a property
  it does not declare, and the old behaviour over-reported the live garden-audit delta 4:1. The
  deliberate cost: the report now says *`added property: up_source`* and no longer says which values
  it carries. For the gate that is right — "must you act" is fully answered by `added_property`. For
  **this handoff** it is not enough: the consumer has to build a validator branch, and for that they
  need the value set. `up_source` accepts `frontmatter`, `inline` and `null`.

  F4-AC1 covers the general case — the schema file travels with the handoff, so the values are always
  reachable. But the obligation table is the layer that carries *meaning*, and a table that names a
  field without naming what it emits makes the reader open the attachment to learn the one thing the
  table existed to tell them.

  **Carry-forward from T3.2 — the producer copy's `$id` moved.** Phase 3 gave
  `tomo/schemas/instructions.schema.json` a distinct `$id`
  (`https://miyo.tomo/schemas/instructions-producer.schema.json`); the Hashi-facing mirror
  `hashi-instructions.schema.json` kept the canonical
  `https://miyo.tomo/schemas/instructions.schema.json`, unchanged and byte-identical.

  This is **not** a wire change and it does not move any `schema_version` — `describe_shape` never
  records `$id`, title or description (the ADR-2 boundary), so the gate is correctly silent on it and
  no manifest was regenerated. It is named in the handoff anyway, for one reason: the two documents
  previously shared one identity, which is the mechanical cause of the consumer diffing the wrong
  file and reporting drift that did not exist. Telling them the collision is gone lets them drop any
  workaround built around it.

  **The one thing to ask them**, because it cannot be verified from this repo: whether anything on
  their side resolves our producer copy by its `$id` rather than by file path. Inside Tomo every
  consumer keys on the filename and the URL occurred in exactly two places, both `$id` declarations
  — verified by search. Their repository is outside our visibility, and a matcher keyed on `$id`
  rather than path is the only way this change could break something no test here covers.

- [ ] **T4.4 After confirmation: refresh, prove clean, integrate** `[activity: validate]`

  **Blocked on the owner returning with the consumer's confirmation. Do not begin otherwise.**

  1. Prime: confirm the consumer has vendored — read their reply, do not infer it from elapsed time.
  2. Test — the whole mechanism, end to end:
     - the refreshed garden-audit copy declares the two fields, and the report is **empty**;
     - all three wires report no delta `[ref: PRD/F6-AC3]`;
     - the gate passes across all three with no exemption;
     - **the permitted case**: an unchanged tree produces a silent run;
     - **the refused case**: each of the three wires, mutated in a scratch copy, fails the gate —
       satisfying the Constitution's requirement for both a permitted and a refused test.
  3. Implement: refresh the vendored copy; begin emitting the new version `[ref: PRD/F4-AC5]`.
  4. Validate: full suite green including `-m integration`; ruff clean.
  5. Success:
     - [ ] The garden-audit report is clean `[ref: PRD/F6-AC2]`
     - [ ] The detection reports nothing across all three `[ref: PRD/F6-AC3]`
     - [ ] The new version is emitted only after confirmation `[ref: PRD/F4-AC5]`
     - [ ] Every published wire has a permitted and a refused test `[ref: SDD/Constraints; CON-5]`

- [ ] **T4.5 Phase Validation** `[activity: validate]`

  - Full suite green including integration; ruff clean.
  - Every PRD criterion in F1–F8 traced to a passing test, except the two consumer-owned ones.
  - Confirm the closing condition the SDD names as the risk: the detection report is **empty**. A
    mechanism whose report always contains known noise is one nobody reads, and reaching zero is what
    makes the next entry mean something.

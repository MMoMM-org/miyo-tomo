---
title: "Phase 4: The CLI, the consumer copies, and closing the live drift"
status: pending
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

- [ ] **T4.1 The `wire-shape` command** `[activity: backend-api]`

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
     - [ ] Regeneration prints the diff it applied `[ref: SDD/Architecture Decisions; ADR-3]`
     - [ ] `--obligations` output is the handoff's raw material `[ref: PRD/F4-AC2]`
     - [ ] Output carries no prose and no content `[ref: SDD/System-Wide Patterns]`

- [ ] **T4.2 All three consumer copies are vendored, and reported against** `[activity: data-architecture]`

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

- [ ] **T4.2b The daily side gains its source identity** `[activity: data-architecture]`

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

- [ ] **T4.3 One handoff for the whole release — then STOP** `[activity: validate]`

  **This handoff carries the entire release, not just the garden-audit half.** The consumer asked
  for one changed-fields list and one vendoring pass; three separate handoffs for one release is the
  outcome that request exists to prevent. Three documents move together:

  | Document | Change | Source |
  |---|---|---|
  | garden-audit wire | disclose `up_source` / `up_value`, already emitted | this spec, F6 |
  | suggestions wire | daily-side source identity on three buckets | this spec, F9 (T4.2b) |
  | instructions wire | `delete_source` gains its dependency field | **spec 036**, whose T4.5 supplies the half rather than sending its own handoff |

  1. Prime: re-read what is actually drifted — our schema declares `up_source` and `up_value` on
     `findings[].detail`; the consumer's declares neither. It is benign **only** because that node is
     open on both sides `[ref: PRD/Problem Statement]`. Then confirm 036's instruction-wire half is
     ready to travel; if it is not, say so and send the two documents this spec owns.
  2. Test: after the version move, the gate passes for the garden-audit wire; the manifest records
     the new version; the emitted document carries it (via T3.1, without a code edit).
  3. Implement:
     a. Move the garden-audit wire's `schema_version`.
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

  **Worth raising in the same handoff, unprompted**: the consumer's own analysis of their namesake
  bug names two `source_stem` join sites; there is a third at `SuggestionsTab.ts:180-181`
  (`collectDailyLogStems`), same key and same fan-out. Found while researching this spec.

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

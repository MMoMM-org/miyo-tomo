---
title: "Phase 4: Contract, audit, reporting and integration"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Contract, audit, reporting and integration

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Data Storage Changes]` — the wire change and its version bump
- `[ref: SDD/Architecture Decisions; ADR-6]` — abort on a dangling id
- `[ref: SDD/Cross-Component Boundaries]` — the release is joint, never one-sided
- `[ref: SDD/Deployment View]` — Hashi vendors first or simultaneously, never after
- `[ref: PRD/Feature 5]`, `[ref: PRD/Feature 6]`, `[ref: SDD/Error Handling Criteria]`
- `tomo/schemas/hashi-instructions.schema.json` — **the contract**
- `tomo/schemas/instructions.schema.json` — the producer copy; do not confuse the two

**Key Decisions**:
- **ADR-6** — a surviving delete naming an absent id **aborts the run with exit 2**. Under ADR-1
  this audit is vacuous; a violation means an unknown-shaped bug, and a set whose delete semantics
  cannot be trusted is worse than no set.
- The instruction wire goes `schema_version "2" → "3"`. This counter is **independent** of the
  suggestions wire, which spec 035 moves `"1" → "2"` in the same release.
- `depends_on` is `required` with an explicit `[]`, snake case, and the consumer **unions** it with
  their derived edges rather than overriding them.

**Dependencies**:
- **Phases 1, 2 and 3 complete.** The audit asserts an invariant only Phases 1–2 establish, and the
  schema cannot go out while Phase 3's path still emits an unjustifiable delete.

---

## Tasks

Makes the contract real, proves the producer invariant, and validates the whole thing end to end.

- [ ] **T4.1 The wire contract** `[activity: data-architecture]`

  **SEQUENCING GATE — T4.5's handoff goes out and Hashi vendors BEFORE this task lands.** Corrected
  2026-09-10 by validation. `tests/test_instruction_render_wire_hygiene.py::test_snapshot_matches_upstream_hashi`
  (`:282`) fetches Hashi's live `instructions.schema.json` and compares `required` **and** property
  names per action `$def` (`:345-352`). Adding `depends_on` to our mirror before they ship it fails
  both comparisons, and the escape hatch `SNAPSHOT_AHEAD_OF_UPSTREAM` (`:75`) is keyed by **action
  name, not property** — so `delete_source` cannot be exempted without silencing drift detection for
  the very action this spec is about. A property-level registry was considered and rejected: that
  hatch exists for actions Hashi has agreed to implement *later*, the opposite of this case, and
  under our own release rule (they vendor first or simultaneously, never after) the window it would
  cover is zero-length. Sequencing costs nothing and adds no permanent silencing mechanism.

  1. Prime: read both instruction schemas and confirm which is the vendored contract
     `[ref: SDD/Cross-Component Boundaries]`. **Two different tests, two different jobs**:
     `tests/test_tomo_schema_parity.py` compares Tomo's **two local** schemas only — its docstring
     says "no network, no local Hashi checkout required" (`:8-9, 94-95`), so it proves the producer
     copy and the mirror agree, nothing about Hashi. The upstream enforcer is
     `test_snapshot_matches_upstream_hashi`, which fetches their live schema and skips offline.
  2. Test: a rendered set validates against the updated contract schema; a set whose `delete_source`
     lacks `depends_on` **fails** validation; the local parity test still passes; the upstream drift
     test passes **green on its own terms** once Hashi has vendored — not by exemption;
     `schema_version` reads `"3"`.
  3. Implement: add `depends_on` (array of string, `required`) to `delete_source` in **both**
     schemas; bump the instruction wire `schema_version` to `"3"`.
  4. Validate: schema tests pass; parity test passes; ruff clean.
  5. Success:
     - [ ] `depends_on` is required in the contract schema `[ref: PRD/F5-AC1]`
     - [ ] An omitted field fails validation rather than defaulting `[ref: SDD/Error Handling]`
     - [ ] The producer copy and the contract copy agree `[ref: SDD/Cross-Component Boundaries]`
     - [ ] The upstream drift test passes without an exemption entry `[ref: SDD/CON-2]`

- [ ] **T4.2 The dangling-id audit** `[activity: backend-api]`

  1. Prime: read `_validate_action_paths`' abort shape — this audit matches it `[ref: SDD/Error Handling]`.
  2. Test: a set in which every named id is present passes with an empty violation list; a set with
     one dangling id produces exactly one violation naming the offending delete and the missing id;
     a `delete_source` with **no** `depends_on` key at all is also a violation; `instruction-render`
     returns exit code 2 and **writes no file** in both failing cases.
  3. Implement: `assert_no_dangling_dependencies(actions) -> list[str]`; call it in
     `instruction-render.py` after the withdrawal pass and before writing; extend
     `tests/test_instruction_render_wire_hygiene.py`.
  4. Validate: unit tests pass; the no-file-written assertion is explicit, not implied.
  5. Success:
     - [ ] Every id in every `depends_on` exists in the same set `[ref: PRD/F5-AC4]`
     - [ ] A violation aborts with exit 2 and writes nothing `[ref: SDD/Error Handling Criteria]`
     - [ ] A missing field aborts identically to a dangling id `[ref: SDD/Error Handling Criteria]`

- [ ] **T4.3 Report withdrawals where the user reads them** `[activity: frontend-ui]`

  1. Prime: read how existing guards report — stderr summary plus the `tomo` block — and how
     `render_md.py` surfaces the skipped-actions section `[ref: SDD/Quality Requirements]`.
  2. Test: a run with a withdrawal reports it with the missing id **and** the guard that caused it,
     in both the stderr summary and the rendered markdown; the withheld action and the delete it
     withdrew are **cross-referenced on the missing id** so the markdown reader can see they belong
     together `[ref: PRD/F2-AC4]`; a run with no withdrawal emits no withdrawal section at all;
     report contents carry ids, kinds, counts and vault-relative paths and **never note content**.
  3. Implement: thread the withdrawal records into the existing report surfaces.
  4. Validate: unit tests pass; ruff clean.
  5. Success:
     - [ ] A withdrawal is reported with its cause in both surfaces `[ref: PRD/F6-AC1]`
     - [ ] A withheld guard drop and the delete it withdrew are joined on the missing id and
           presented adjacently, not in unrelated sections `[ref: PRD/F2-AC4]`
     - [ ] No withdrawal produces no section `[ref: PRD/F6-AC2]`
     - [ ] Reports are metadata only `[ref: SDD/System-Wide Patterns; Constitution L1]`

- [ ] **T4.4 Integration and end-to-end validation** `[activity: validate]`

  The Constitution requires a permitted case **and** a refused case for every vault-mutating path.
  This task is where all three refused cases are proven together.

  1. Prime: read the three measured chains `[ref: PRD/Problem Statement]`.
  2. Test — end to end, real builder, real guards, only the Kado seams stubbed:
     - **P1**: `create_moc` + `move_note` contest → no delete emitted, origin survives, staging note
       not uploaded;
     - **P2** (Bug A): daily note absent → daily action dropped, no delete emitted;
     - **P3** (Bug B): unresolvable tag-handler target → no insert, no delete, Approve unticked;
     - **the permitted case**: a healthy run emits the same action set as before this spec, plus
       `depends_on` on each delete, and withdraws nothing;
     - a full-suite run with `-m integration` against the test vault.
  3. Implement: no production code — this task is the proof, not a change.
  4. Validate: full suite green including integration; ruff clean.
  5. Success:
     - [ ] All three data-loss paths emit no delete `[ref: PRD/Problem Statement]`
     - [ ] A healthy run is unchanged apart from the new field `[ref: SDD/Edge Case Criteria]`
     - [ ] Every vault-mutating path has both a permitted and a refused test `[ref: SDD/CON-5]`

- [ ] **T4.5 Release handoff to the consumer** `[activity: validate]`

  Not a code task. The wire cannot ship one-sided: the consumer rejects unknown fields, so they
  vendor **first or simultaneously, never after** `[ref: SDD/Deployment View]`.

  **Corrected 2026-09-10: this task supplies its half to spec 035's handoff rather than sending one
  of its own.** Three documents move in this release — 035's garden-audit disclosure, 035's
  daily-side identity, and this spec's `depends_on`. The consumer asked for one obligation table
  and one vendoring pass; three separate handoffs is precisely the outcome that request exists to
  prevent. 035's T4.3 owns the handoff and this task hands it the instruction-wire row.

  **This task also carries the two consumer-owned criteria.** `[ref: PRD/F5-AC5]` (the executor
  skips a delete whose named dependency failed) and `[ref: PRD/F5-AC6]` (a destination taken between
  generation and application leaves the original intact) describe **the consumer's** behaviour. Tomo
  cannot test them — it does not execute the set, and by CON-4 it may never read execution results
  back. They are verified by the consumer against their own suite and reported in their reply to
  this handoff. Recorded here as a named ownership boundary rather than left unmapped: the PRD's own
  Assumptions section already states that every claim about the executor is read, not executed, from
  this side `[ref: PRD/Assumptions]`.

  **Runs BEFORE T4.1.** The mirror schema edit cannot land until Hashi has vendored, or the upstream
  drift test fails with no property-level exemption available. This task is therefore the *first*
  thing in Phase 4 chronologically, despite its number.

  **Blocked on**: spec 035's `source_item_key` widening must be committed before this handoff can
  carry one obligation table covering both documents. 035 is at `Initialization` as of
  2026-09-10 — if it has not landed, send the instruction-wire half alone and say so, rather than
  holding a data-loss fix behind a versioning spec.

  1. Prime: re-read the agreed release practice `[ref: SDD/Cross-Component Boundaries]` — schema
     **file**, plus a obligation table, per document.
  2. Test: run the structural diff **before** attaching — every object's property set, `required`
     list and `additionalProperties` value, recursively, against the consumer's vendored copy. The
     expected result here is a **difference** (they have not vendored `depends_on` yet); the check
     proves the diff harness works and names exactly the fields the obligation table must carry.
     A diff reporting anything beyond the intended change means the schema drifted elsewhere and the
     handoff is wrong before it is sent.
  3. Implement: write the handoff to `_outbox/for-hashi/` carrying both schema files as attachments
     and one obligation table covering both documents — the instruction wire `"2" → "3"` for
     `depends_on`, and spec 035's suggestions wire `"1" → "2"` for the daily-side `source_item_key`.
  4. Validate: the attached schema files are byte-identical to the repository's; the changed-fields
     list names every field the diff reported and no others.
  5. Success:
     - [ ] One handoff, two documents, two counters, one release `[ref: SDD/CON-3]`
     - [ ] Schema files attached rather than described `[ref: SDD/Cross-Component Boundaries]`
     - [ ] The obligation table matches the measured diff exactly `[ref: SDD/CON-2]`
     - [ ] The consumer confirms F5-AC5 and F5-AC6 against their own suite `[ref: PRD/F5-AC5]` `[ref: PRD/F5-AC6]`

- [ ] **T4.6 Phase Validation** `[activity: validate]`

  - Full suite green including `-m integration`; ruff clean.
  - Every PRD acceptance criterion in F1–F6 traced to a passing test.
  - Confirm the spec's close-out position: three measured data-loss paths, all three closed, with
    the two deferred items (F7 rendering, staging-residue detection) recorded as decisions rather
    than gaps.

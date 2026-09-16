---
title: "Phase 4: Integration and the live path"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Integration and the live path

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-5]` — no wire field, no Hashi change
- `[ref: SDD/Cross-Component Boundaries]`
- `[ref: PRD/Success Metrics]`, `[ref: PRD/C2]`

**Key Decisions**:
- ADR-5 is asserted **by absence**: the wire schema and Hashi's vendored copy
  must be unchanged. That is a test, not a promise.
- The live path is the only place the whole chain is exercised. The fixture that
  produced the 2026-09-15 failure still exists in the test vault — two 69-byte
  PNGs named `karte.png`, one in `100 Inbox/Scans/`, one in
  `Atlas/290 Assets/295 Attachments/`. Do not "clean it up"; it is the fixture.
- Cost is measured, not estimated. `base_kado_calls` must still read 2.

**Dependencies**: Phases 1, 2 and 3.

---

## Tasks

Establishes that the chain works end to end and that nothing outside Tomo moved.

- [ ] **T4.1 Nothing outside Tomo changed** `[activity: testing]` `[parallel: true]`

  1. Prime: Read `[ref: SDD/External Interfaces]` and `[ref: SDD/Cross-Component Boundaries]`; locate Hashi's vendored wire schema copy
  2. Test: `tomo/schemas/hashi-instructions.schema.json` is byte-identical to its pre-change version; no emitted action carries a field absent from that schema; running Hashi's own validator on a fixture instruction set containing all three remedies passes `[ref: memory: check the consumer's VENDORED schema copy]`
  3. Implement: nothing. A change needed here is a deviation against ADR-5 — stop and revisit it
  4. Validate: diff the schema against `main`; run the consumer's validator on a real rendered file, never reason from ours
  5. Success: Hashi receives no new field and needs no change `[ref: SDD/ADR-5]`; the contrast with spec 036's consumerless `depends_on` is preserved

- [ ] **T4.2 Pass 2's summary names what it did not resolve** `[activity: frontend-ui]` `[parallel: true]`

  1. Prime: Read Pass 2's existing completion summary and how withheld MOC links are reported there
  2. Test: a run with two unresolved conflicts names **both** rather than counting them `[ref: PRD/C2]`; a run with none adds no line; a `rename` conflict is not reported as unresolved
  3. Implement: extend the summary from the conflict records
  4. Validate: full suite; `ruff`
  5. Success: an owner who unticked a default is reminded before applying `[ref: PRD/S2]`

- [ ] **T4.3 The live run reproduces the 2026-09-15 case and resolves it** `[activity: testing]`

  1. Prime: Read the run log `100 Inbox/tomo-hashi-run-log_2026-09-15T2057.md` for the failing row; confirm both `karte.png` files are still in place and still differ
  2. Test — as a live `/inbox` run, not a fixture: Pass 1 raises exactly one conflict for `karte.png`; the document shows it with rename ticked and states that a **different** file holds the name; Pass 2 with the default emits a move to a free name; the coverage audit passes; Hashi applies the run with **zero** `move_asset` failures — the row that was red on 2026-09-15 is green
  3. Implement: nothing new; this task is the proof
  4. Validate: compare `base_kado_calls` against the spec 034 T6.4 baseline of **2** — it must be unchanged, since the reducer is a separate process `[ref: SDD/Cost]`; record `folder_listing_calls` and confirm it rose by at most one
  5. Success: every PRD KPI has a measured value from this run `[ref: PRD/Success Metrics]`; owner agency goes from 0-of-1 to 1-of-1; the failed action goes from 1 to 0

- [ ] **T4.4 The unresolved remedies behave as designed on the live vault** `[activity: testing]`

  1. Prime: T4.3's run must be complete and its vault state known
  2. Test — two further live runs against the same fixture: with `keep_in_inbox`, no `move_asset` is emitted and Hashi reports no failure; with `ignore`, the move is emitted and **Hashi refuses it with the same message as 2026-09-15** — which is the remedy working, not a regression
  3. Implement: nothing; this task is the proof that ADR-5's dependency on Hashi's existing behaviour is real and not assumed
  4. Validate: read both run logs; assert the `ignore` run's failure count is exactly 1 and names `move_asset`
  5. Success: all three remedies are demonstrated against a live vault `[ref: PRD/F3]`; the fixture is restored afterwards so the next run starts from the same state `[ref: scratchpad/restore-trigger-notes.sh]`

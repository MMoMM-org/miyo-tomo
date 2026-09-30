---
title: "Phase 5: Integration, the live path, and one handoff"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Integration, the live path, and one handoff

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/S1]` — the documentation criteria
- `[ref: PRD/C2]` — the inventory's optional note
- `[ref: PRD/Success Metrics; Tracking Requirements]` — what the live run must exercise
- `[ref: SDD/CON-1]` — the release is coordinated and cannot be split
- `[ref: SDD/CON-8]` — the live Kokoro obligation
- `[ref: README/Decisions Log; 2026-09-30]` — the runnable test setup is a deliverable, not a nicety

**Key Decisions**:
- **One handoff, complete, after the producer side is finished** `[ref: SDD/CON-1]`.
  The consumer's vendored schema pins the version and rejects unknown properties,
  and treats a validation failure as fatal for the whole document — so an early
  ship takes their editor out of service on exactly the runs this spec serves.
- The handoff **includes a runnable run**, because their QA vault has one worthy
  card and no run anywhere carries `delete_source: true` — the control they built
  on our table is otherwise reachable only by hand.
- CON-8 is an **open constitutional obligation**: the Kokoro handoff must go out
  before or alongside the implementation, not after.

**Dependencies**: Phases 1–4 complete.

---

## Tasks

Delivers the release: documentation, a live proof, the coordinated handoff, and a
close-out that traces every criterion to a test that was executed.

- [ ] **T5.1 User documentation** `[activity: documentation]` `[parallel: true]`

  1. Prime: read `docs/usage.md:48-85` ("When an attachment's name is already
     taken") and `docs/troubleshooting.md:220-259`. The usage section currently
     describes the computed name as fixed, and neither document covers a refused
     name.
  2. Test: not unit-testable. The check is a read-through against `[ref: SDD/CON-6]`
     and `[ref: SDD/CON-7]`: effect not mechanism, and nothing implying the
     owning-note list is exhaustive.
  3. Implement: state that the name is editable; describe what a refusal looks like
     and what to do; state the precedence rule plainly — once the run has been
     saved in the editor, the editor's values are the ones Pass 2 uses
     `[ref: PRD/S1]`. Add a troubleshooting entry for "I typed a name Pass 2 could
     not use", distinct from the existing apply-time refusal entry.
  4. Validate: grep the new text for function names, module names and wire action
     names — there should be none.
  5. Success:
     - [ ] `usage.md` says the name is editable and covers a refusal `[ref: PRD/S1]`
     - [ ] The precedence rule is stated `[ref: PRD/S1]`
     - [ ] A new troubleshooting entry exists, distinct from the apply-time one
     - [ ] No executor internals `[ref: SDD/CON-6]`

- [ ] **T5.2 The inventory's remedy row moves off `null`** `[activity: data-architecture]` `[parallel: true]`

  1. Prime: re-read the inventory written in Phase 1 and the field this spec added
     in Phase 2.
  2. Test: the Phase 1 join test now requires the remedy row to name a real wire
     field — it should fail until the row is updated, which is the mechanism working.
  3. Implement: change the remedy row's `wire_field` from `null` to the array's
     path. Add the optional `note` where a row needs one `[ref: PRD/C2]`.
  4. Validate: the join test passes in both directions again.
  5. Success:
     - [ ] The remedy row names its wire field `[ref: PRD/F4]`
     - [ ] The join test's failure-then-pass transition was observed, not assumed

- [ ] **T5.3 The live run** `[activity: validate]`

  1. Prime: read `scripts/spec037-fixture.sh` and the 037 live runbook for how a
     live run is staged and reset. **`tomo-privat` is LIVE — never touch it.** All
     work is `--instance tomo-instance`.
  2. Test: the run **is** the test. Exercise, in one pass where possible: a remedy
     surviving a wire edit (F1); a typed name accepted end to end including the
     embed rewrite (F2); a typed name refused, with the owning note held and the
     instruction document reporting it (F3).
  3. Implement: sync the instance first — instance scripts go stale and a live walk
     against a stale instance proves nothing.
  4. Validate: read the rendered documents as the owner would, not as the author.
     Spec 037's four defective sentences were caught by the owner reading shipped
     output, not by review.
  5. Success:
     - [ ] A remedy survives a wire edit in a real run `[ref: PRD/F1]`
     - [ ] A typed name files the attachment and rewrites the embeds `[ref: PRD/F2]`
     - [ ] A refused name holds the note and is reported `[ref: PRD/F3]`
     - [ ] The cost log is updated, as after every live run

- [ ] **T5.4 The coordinated handoff, and the Kokoro obligation** `[activity: documentation]`

  1. Prime: read the pending handoffs in `_outbox/for-hashi/` and
     `_outbox/for-kokoro/` — both are written and unsent, and the Kokoro one is
     what discharges CON-8 `[ref: SDD/CON-8]`.
  2. Test: not testable. The check is completeness: schema pair attached, the run
     fixture attached, the version move named, the `source`-not-`item_key` keying
     restated, and the inventory attached.
  3. Implement: one handoff to the consumer carrying the new schema, the inventory,
     and a runnable suggestions run with a real conflict — a run their QA vault
     cannot produce. Attach the artefacts rather than describing them: the 2026-09-18
     schema pair and the 2026-09-14 run fixture are the precedents. Send the Kokoro
     handoff at the same time or before.
  4. Validate: re-read the consumer's last message and confirm each of their action
     items is answered.
  5. Success:
     - [ ] One handoff, complete, with artefacts attached `[ref: SDD/CON-1]`
     - [ ] A runnable conflict run is included `[ref: README/Decisions Log]`
     - [ ] The Kokoro handoff has gone out, discharging CON-8 `[ref: SDD/CON-8]`
     - [ ] Nothing was shipped to a live wire before their copy was updated

- [ ] **T5.5 Close-out** `[activity: documentation]`

  1. Prime: read `docs/XDD/specs/037-…/close-out.md` as the model, and
     `docs/XDD/specs/036-…/close-out.md` for the trace format.
  2. Test: the close-out **is** the check. Every one of the PRD's 38 criteria maps
     to a test that was **executed**, named by node id from a real pytest
     invocation — not to a task that mentions it. This is the check that caught
     037's S2-AC1 being claimed by a parser task that structurally could not render
     anything.
  3. Implement: `close-out.md` with the full trace, the four open items this spec
     leaves behind (the hand-written inventory, the earlier-run embed break, the
     `delete_source` normalisation divergence, and anything Phase 1's discrepancy
     list did not absorb), and the honest record of what the spec cost.
  4. Validate: pick three criteria at random and verify their node ids by running
     them. A trace nobody spot-checks is a trace nobody can trust.
  5. Success:
     - [ ] All 38 PRD criteria traced to executed tests by node id `[ref: PRD]`
     - [ ] Open items recorded rather than quietly closed
     - [ ] Three traces spot-checked by execution
     - [ ] `Skill(tcs-workflow:xdd-meta)` Finalize has run — the spec reaches
           `Implemented` rather than sitting on `Ready`

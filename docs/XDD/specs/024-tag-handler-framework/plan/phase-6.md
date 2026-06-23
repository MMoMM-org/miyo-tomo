---
title: "Phase 6: Integration & validation"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Integration & validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Section 5; lines: 82-114]` — full additive pipeline integration (triage → compose → render)
- `[ref: SDD/Section 6; lines: 138-142]` — phasing: Tomo side cross-repo-independent; automated apply is the only externally-blocked step
- `[ref: PRD/AC-1..AC-5; lines: 107-112]` — end-to-end acceptance criteria
- `[ref: PRD/C1,C3; lines: 117-120]` — additive-only; Pass-1 inbox-only, Hashi/manual applies Pass-2

**Key Decisions**:
- The Tomo-side E2E (T6.1) validates AC-1..AC-5 with **no cross-repo dependency** — it proves detect → compose → render the instruction.
- Automated cross-repo apply (T6.2) is the **only** externally-blocked item; it wires in when the Hashi `insert_under_marker` action (T1.1 handoff) lands. If Hashi lands before this phase, the manual-apply interim never happens.

**Dependencies**:
- Phases 1–5 complete (full Tomo-side pipeline).
- T6.2 additionally depends on the Hashi action from the T1.1 handoff being implemented.

---

## Tasks

Proves the framework end-to-end on the Tomo side and wires the automated cross-repo apply once Hashi's action lands.

- [ ] **T6.1 E2E (Tomo-side): captures → merged suggestion → instruction** `[activity: integration]`

  1. Prime: Read the full pipeline integration `[ref: SDD/Section 5; lines: 82-114]` and AC-1..AC-5 `[ref: PRD/Section 7; lines: 107-112]`.
  2. Test (RED): 3 Tsukai captures for one repo in a batch → triage marks all three `handled` (AC-1) → grouped + composed into **one** merged status-update suggestion targeting the repo-mapped note under `## Captures` (AC-3) → approved → one `insert_under_marker` instruction rendered; a user-authored handler drives the flow (AC-2); missing target/marker guards fire (AC-4); an empty-registry control run is byte-identical (AC-5).
  3. Implement: Wire/assert the end-to-end Tomo-side path (no Hashi dependency) as an integration test.
  4. Validate: E2E test passes; AC-1..AC-5 each asserted; lint clean.
  5. Success: AC-1..AC-5 demonstrated end-to-end on the Tomo side `[ref: PRD/AC-1..AC-5; lines: 107-112]`.

- [ ] **T6.2 Wire automated cross-repo apply (when Hashi action lands)** `[activity: integration]`

  1. Prime: Read the cross-repo phasing `[ref: SDD/Section 6; lines: 134-142]` and the T1.1 handoff contract.
  2. Test (RED): once Hashi implements `insert_under_marker`, the rendered instruction applies via Hashi against a test vault; cross-repo E2E (Tomo renders → Hashi applies → target note updated under marker); until then, manual apply is the documented fallback.
  3. Implement: Wire the automated apply + cross-repo E2E when the Hashi action is available.
  4. Validate: cross-repo E2E passes against a test vault/fake; if Hashi not yet landed, mark deferred with the manual-apply fallback documented.
  5. Success: Automated apply works end-to-end across repos `[ref: SDD/Section 6; lines: 138-142]`.

- [ ] **T6.3 Phase Validation** `[activity: validate]`

  - Run the full suite under `./venv/bin/python`. Verify AC-1..AC-5 via T6.1; confirm AC-5 byte-identity holds against the final integrated pipeline. If the Hashi action has landed, run the cross-repo E2E (T6.2); otherwise record it deferred with the manual-apply fallback. Lint clean. **Gate: E2E (AC-1..AC-5); wire Hashi apply when it lands.**

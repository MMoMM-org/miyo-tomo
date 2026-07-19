---
title: "Phase 6: Cross-Repo Handoffs & Integration/E2E"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Cross-Repo Handoffs & Integration/E2E

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Cross-Cutting — Cross-component contract (Constitution L2)]`
- `[ref: SDD/ADR-3 — example-driven handoff]`
- `[ref: PRD — all Features; Success Metrics]`
- `~/Kouzou/projects/miyo/miyo-handoff-protocol.md`, `~/Kouzou/projects/miyo/miyo-constitution.md` (L2 Architecture)

**Key Decisions**: ADR-3 (the new `edit_note_text` action is delivered to Hashi example-driven, when Tomo's build is done); Constitution L2 (reflect the cross-component interface in Kokoro).

**Dependencies**: Phases 1-5 (a complete, working build produces the real wire that IS the handoff artifact).

---

## Tasks

Closes the cross-repo loop and proves the feature end-to-end on the live test vault.

- [ ] **T6.1 Kokoro ADR + Hashi handoff for `edit_note_text`** `[activity: cross-repo]`

  1. Prime: Read the handoff protocol + Constitution L2 (Architecture — public inter-component interfaces need a Kokoro ADR/design-note).
  2. Test (artifact review): the handoff carries the FINAL real `garden-audit-wire.json` example + a sample instruction-set with a live `edit_note_text` action (dead-link fix/remove + `up::` removal) + the proposed schema; a Kokoro design-note records the new action as a Tomo↔Hashi contract.
  3. Implement: `_outbox/for-hashi/<date>_tomo-to-hashi_edit-note-text-action.md` (with the real example); `_outbox/for-kokoro/<date>_tomo-to-kokoro_edit-note-text-contract.md` (design-note).
  4. Validate: `/miyo-outbox` shows both pending; example JSON validates against the wire schema.
  - Success: Hashi can build the editor + action against a concrete example `[ref: SDD/ADR-3]`; L2 reflected `[ref: SDD/Cross-Cutting — L2]`.

- [ ] **T6.2 Integration + E2E + live-vault validation** `[activity: test-strategy]`

  1. Prime: Read `feedback_sync_instance_before_live_walk`, `feedback_test_scope_personal_vault`, the inbox cost log.
  2. Test:
     - **Wire round-trip** (integration): `render → parse` reconstructs confirmed fixes for all fix types; unchanged wire → markdown authoritative.
     - **End-to-end (shipped actions)**: `/garden-audit` → review doc in inbox → approve → `/inbox` → instruction-set applied via Hashi for `link_to_moc` + `add_relationship` (repoint + file); `edit_note_text` actions are emitted and validated in the wire (Hashi-side apply deferred to T6.1 handoff).
     - **Exclusions live**: a permanently-excluded path (`Calendar/`-like) produces zero findings for its checks; a temporary push-back suppresses then reappears after `until`.
     - **Cost check**: a `/inbox` run with a garden-audit doc present shows zero added Pass-1 cost vs. baseline (inbox-cost-log entry).
  3. Implement: `tests/test_garden_audit_e2e.py` + a live-walk against the personal test vault (sync instance first).
  4. Validate: full suite green; ruff clean; inbox-cost-log entry added.
  - Success: end-to-end audit → approve → apply works for shipped actions with zero `/inbox` burden `[ref: PRD/Feature 3, Feature 4]`; exclusions behave `[ref: PRD/Feature 5]`.

- [ ] **T6.3 Phase Validation** `[activity: validate]`

  - Full `pytest` + ruff green; both handoffs pending in `_outbox/`; live-walk recorded; README + roadmap/backlog updated (F-44 shipped, epic #16 checkbox).

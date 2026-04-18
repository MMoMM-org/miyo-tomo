---
title: "Phase 2: Reconciliation + Deviations"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Reconciliation + Deviations

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View — Steps 4-5]`
- `[ref: SDD/File Formats — Deviation Callout Format]`
- `[ref: PRD/Feature 2 — Spec Reconciliation]`
- `[ref: PRD/Feature 3 — Placeholder Spec Completion]`

**Key Decisions**:
- ADR-3: Inline deviation annotations using callout blocks
- Kokoro remains authoritative — document deviations, don't rewrite architecture

**Dependencies**:
- Phase 1 must be complete (specs must be at `docs/XDD/reference/` paths)

---

## Tasks

Annotates migrated specs where implementation deviates from original design. Updates outdated content to reflect what was actually built.

- [x] **T2.1 Annotate inbox-processing workflow deviations** `[activity: docs-reconciliation]`

  1. Prime: Read `docs/XDD/reference/tier-2/workflows/inbox-processing.md` AND `docs/XDD/specs/004-inbox-fanout-refactor/solution.md` `[ref: SDD/Acceptance Criteria — Reconciliation]`
  2. Test: Identify all sections describing the old 4-agent monolithic model (inbox-analyst, suggestion-builder, instruction-builder, vault-executor)
  3. Implement: Add deviation callouts where the fan-out refactor changed behavior:
     - Agent architecture: monolithic → orchestrator + per-item subagents
     - State management: in-memory → JSONL state file
     - Parallelism: sequential → 3-5 concurrent subagents
     - Context: full cache → distilled shared context (~10KB/subagent)
     - suggestion-builder: retired (merged into orchestrator)
     Format per SDD:
     ```
     > **⚠️ Deviation (XDD-004)**
     > **Original**: ...
     > **Actual**: ...
     > **Reason**: ...
     > **See**: specs/004-inbox-fanout-refactor/solution.md
     ```
  4. Validate: All outdated agent descriptions have deviation callouts; callouts reference XDD-004
  5. Success: Inbox workflow spec accurately reflects fan-out architecture `[ref: PRD/AC — Feature 2, fan-out]`

- [x] **T2.2 Annotate daily-note workflow deviations** `[activity: docs-reconciliation]`

  1. Prime: Read `docs/XDD/reference/tier-2/workflows/daily-note.md` AND `docs/XDD/specs/005-daily-note-workflow/solution.md` `[ref: SDD/Acceptance Criteria — Reconciliation]`
  2. Test: Identify sections missing tracker semantics and 3-classification-dimension model
  3. Implement: Add deviation callouts for XDD-005 changes:
     - 3 classification dimensions: tracker match, log-entry candidate, log-link candidate
     - Tracker config in vault-config.yaml
     - Daily-log wizard in /tomo-setup
     - 30-day cutoff default
     - log_entry vs log_link driven by atomic_note_worthiness
  4. Validate: Daily-note spec has deviation callouts for all XDD-005 extensions
  5. Success: Daily-note spec reflects tracker semantics and classification dimensions `[ref: PRD/AC — Feature 2, daily-note]`

- [x] **T2.3 Annotate Tier 3 daily-note detail deviations** `[activity: docs-reconciliation]` `[parallel: true]`

  1. Prime: Read `docs/XDD/reference/tier-3/daily-note/daily-note-detection.md` and `tracker-field-handling.md`; cross-reference with XDD-005 solution.md
  2. Test: Identify content that doesn't match implementation (e.g., detection algorithm, tracker config schema)
  3. Implement: Add deviation callouts where XDD-005 changed the detail specs
  4. Validate: Tier 3 daily-note specs annotated consistently with Tier 2
  5. Success: Daily-note detail specs reflect actual implementation `[ref: PRD/AC — Feature 2]`

- [x] **T2.4 Annotate Tier 3 inbox detail deviations** `[activity: docs-reconciliation]` `[parallel: true]`

  1. Prime: Read `docs/XDD/reference/tier-3/inbox/inbox-analysis.md` and `suggestions-document.md`; cross-reference with XDD-004 solution.md
  2. Test: Identify sections describing old agent model or deprecated suggestion-builder role
  3. Implement: Add deviation callouts where fan-out refactor changed inbox details:
     - inbox-analysis.md: per-item subagent model, distilled context
     - suggestions-document.md: reducer pattern, JSONL state
  4. Validate: Tier 3 inbox specs annotated consistently with Tier 2
  5. Success: Inbox detail specs reflect fan-out architecture `[ref: PRD/AC — Feature 2]`

- [x] **T2.5 Update spec status markers** `[activity: docs-editing]`

  1. Prime: All migrated specs currently show "Draft" status
  2. Test: Identify the status field/marker in each spec's frontmatter or header
  3. Implement: Update status to reflect actual state:
     - Tier 1: `Implemented` (architecture is live)
     - Tier 2 components: `Implemented` (all components built)
     - Tier 2 workflows: `Implemented (with deviations)` for inbox-processing and daily-note; `Implemented` for others
     - Tier 3: `Implemented` for fleshed-out specs; `Skeletal` for placeholders (handled in Phase 3)
  4. Validate: No specs marked "Draft" that are actually implemented
  5. Success: All spec statuses reflect reality `[ref: PRD — Could Have: Status Normalization]`

- [x] **T2.6 Phase Validation** `[activity: validate]`

  - Every deviation callout follows the format defined in SDD
  - Each callout links to the correct XDD spec
  - No spec describes the old monolithic agent model without a deviation annotation
  - Status markers are updated for all migrated specs

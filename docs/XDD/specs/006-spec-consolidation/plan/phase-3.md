---
title: "Phase 3: Placeholder Completion"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Placeholder Completion

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View — Step 5]`
- `[ref: PRD/Feature 3 — Placeholder Spec Completion]`

**Key Decisions**:
- Flesh out from implementation — reverse-engineer working code into proper specs
- Mark fleshed-out specs with "reverse-engineered from implementation" annotation

**Dependencies**:
- Phase 1 must be complete (specs at new paths)
- Phase 2 should be complete (deviation annotations provide context for what changed)

---

## Tasks

Reverse-engineers skeletal Tier 3 specs from the working codebase. Each placeholder gets substantive content that accurately describes current behavior.

- [ ] **T3.1 Flesh out instruction-set-apply spec** `[activity: docs-reverse-engineering]`

  1. Prime: Read the skeletal `docs/XDD/reference/tier-3/inbox/instruction-set-apply.md`; then read the actual implementation:
     - `tomo/.claude/commands/execute.md` (legacy executor command)
     - `tomo/.claude/agents/vault-executor.md` (agent definition)
     - `scripts/instruction-render.py` (instruction generation)
     - `docs/XDD/reference/tier-2/workflows/inbox-processing.md` (workflow context, step 6-7)
     `[ref: PRD/AC — Feature 3]`
  2. Test: Identify what the skeletal spec is missing: MVP user-apply workflow, instruction set format, action types, user review process
  3. Implement: Write substantive spec content covering:
     - MVP execution model (user manually applies in Obsidian)
     - Instruction set structure (per-action sections with I-prefixed IDs)
     - Action types (new atomic note, new MOC, MOC link, daily note update, note modification)
     - User review workflow (read instruction set → apply in Obsidian → confirm)
     - Linked files (new notes and diffs written to inbox/)
     - Post-MVP vision (Seigyo execution via locked scripts)
     - Add header: `> ℹ️ This spec was reverse-engineered from the working implementation (2026-04-18)`
  4. Validate: Spec content matches what `instruction-render.py` actually produces; action types match `item-result.schema.json`
  5. Success: instruction-set-apply.md has substantive content verified against codebase `[ref: PRD/AC — Feature 3]`

- [ ] **T3.2 Flesh out instruction-set-cleanup spec** `[activity: docs-reverse-engineering]` `[parallel: true]`

  1. Prime: Read the skeletal `docs/XDD/reference/tier-3/inbox/instruction-set-cleanup.md`; then read:
     - `tomo/.claude/agents/vault-executor.md` (cleanup responsibilities)
     - `scripts/state-update.py` (state lifecycle transitions)
     - `scripts/tag-captured.py` (tag application)
     - `docs/XDD/reference/tier-3/inbox/state-tag-lifecycle.md` (lifecycle context)
     `[ref: PRD/AC — Feature 3]`
  2. Test: Identify missing content: cleanup triggers, state transitions, tag management, error recovery
  3. Implement: Write substantive spec content covering:
     - Cleanup triggers (after user applies instructions)
     - State tag transitions (instructions → applied → active/archived)
     - Source item tag updates (applied tag replaces processing tag)
     - Suggestion/instruction doc cleanup (tag as applied, move or archive)
     - Error recovery (what happens if user partially applies)
     - Add header: `> ℹ️ This spec was reverse-engineered from the working implementation (2026-04-18)`
  4. Validate: Spec content matches `state-update.py` behavior and lifecycle tags in `state-tag-lifecycle.md`
  5. Success: instruction-set-cleanup.md has substantive content verified against codebase `[ref: PRD/AC — Feature 3]`

- [ ] **T3.3 Audit remaining Tier 3 specs for skeletal content** `[activity: docs-audit]`

  1. Prime: Scan all 26 Tier 3 specs in `docs/XDD/reference/tier-3/` for substantive content
  2. Test: Identify any additional specs that are skeletal/placeholder beyond the two known ones
  3. Implement: For each newly identified skeletal spec:
     - Reverse-engineer content from the relevant scripts/agents/commands
     - Add the reverse-engineered annotation header
     - If the spec is substantive but outdated, add deviation callouts (backport from Phase 2 pattern)
  4. Validate: No spec in `docs/XDD/reference/tier-3/` has fewer than ~50 lines of substantive content
  5. Success: All Tier 3 specs have substantive content `[ref: PRD/AC — Feature 3]`

- [ ] **T3.4 Phase Validation** `[activity: validate]`

  - Every fleshed-out spec has the reverse-engineered annotation header
  - Content matches actual codebase behavior (spot-check against scripts)
  - No remaining placeholder/skeletal specs in `docs/XDD/reference/`
  - Updated specs' status markers changed from `Skeletal` to `Implemented`

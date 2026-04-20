---
title: "Phase 3: Validation"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Validation

## Phase Context

**Dependencies**: Phases 1 + 2 must be complete.

---

## Tasks

- [ ] **T3.1 End-to-end test with live vault** `[activity: validate]`

  1. Reset test vault to pre-Pass-2 state (suggestions approved, no instructions)
  2. Sync all changes to tomo-instance
  3. Run `/inbox` in Tomo Docker
  4. Verify:
     - `instructions.json` written to inbox alongside `instructions.md`
     - Both files have identical action lists (same IDs, same content)
     - `instructions.md` is human-readable and matches expected format
     - `instructions.json` is machine-parseable
     - Rendered note files are written correctly
     - action_count in frontmatter matches actual action count

- [ ] **T3.2 Verify JSON is Tomo Hashi-ready** `[activity: validate]`

  1. Write a minimal Python script that reads `instructions.json` and prints
     what actions it would execute (dry-run). No Kado calls — just parsing.
  2. Verify every action type is parseable and contains all required fields.
  3. Verify paths are vault-relative and resolvable.

- [ ] **T3.3 Update docs** `[activity: docs]`

  1. Update `docs/XDD/roadmap.md` — mark relevant items
  2. Update `docs/XDD/backlog.md` — cross-reference F-01 (Tomo Hashi) with XDD 008
  3. Update `tomo/dot_claude/commands/inbox.md` if Pass 2 description changed

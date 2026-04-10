---
title: "Phase 4: Integration Validation"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Integration Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `docs/specs/tier-1/pkm-intelligence-architecture.md` — 4-layer stack, security model
- `tomo/.claude/rules/project-context.md` — Existing project context rule
- All Phase 1-3 deliverables

**Key Decisions**:
- Project context rule must reflect the architecture spec accurately
- End-to-end validation: install script → config → profiles → templates all work together

**Dependencies**:
- Phase 1, Phase 2, Phase 3 (all must be complete)

---

## Tasks

Validates all Phase 1 deliverables work together and updates project context for the Tomo Docker instance.

- [ ] **T4.1 Project Context Rule Update** `[activity: build-feature]`

  1. Prime: Read architecture spec `[ref: docs/specs/tier-1/pkm-intelligence-architecture.md]` and existing project-context.md `[ref: tomo/.claude/rules/project-context.md]`
  2. Test: Rule describes 4-layer knowledge stack; mentions 2-pass inbox model (Suggestions → Instruction Set); documents MVP execution boundary (Tomo writes only to inbox); references profile system and config precedence
  3. Implement: Update `tomo/.claude/rules/project-context.md` to align with architecture spec — add knowledge stack description, execution model, profile/config system
  4. Validate: Rule is accurate per architecture spec; no fabricated information
  5. Success: A Tomo session reading this rule understands the full architecture context

- [ ] **T4.2 End-to-End Integration Test** `[activity: validate]`

  1. Prime: Read all deliverables from Phases 1-3
  2. Test: Full flow works — profile loads → config generates → templates exist → yaml-fixer runs
  3. Implement: Create integration test script `scripts/test-phase1.sh` that:
     - Validates both profiles parse as YAML
     - Runs install script in non-interactive mode with a temp vault dir
     - Verifies generated vault-config.yaml has correct schema
     - Validates all 5 templates have valid frontmatter
     - Runs yaml-fixer on known-broken YAML samples
     - Reports pass/fail for each check
  4. Validate: `bash scripts/test-phase1.sh` passes all checks
  5. Success: All Phase 1 deliverables work together; zero manual steps needed to validate

- [ ] **T4.3 Phase Validation** `[activity: validate]`

  - Integration test passes. Project context rule is accurate. All files committed. README updated if needed.

---
title: "Phase 4: Integration Validation"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Integration Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- All Phase 1-3 deliverables
- `docs/specs/tier-2/workflows/vault-exploration.md` — end-to-end workflow

**Key Decisions**:
- Integration test validates script pipeline without live Kado (mock responses)
- Agent artifacts validated for structure and completeness

**Dependencies**:
- Phase 1, Phase 2, Phase 3 (all must be complete)

---

## Tasks

- [ ] **T4.1 Integration Test Script** `[activity: validate]`

  1. Prime: Read all Phase 1-3 deliverables
  2. Test: Full pipeline validates — kado_client imports; vault-scan produces JSON; topic-extract produces topics; moc-tree-builder produces tree; cache-builder produces YAML; all agent/command/skill files exist and have correct structure
  3. Implement: Create `scripts/test-phase2.sh` that validates all Phase 2 deliverables. For scripts that need Kado, validate --help and import paths work. For agent artifacts, validate file existence and key content markers.
  4. Validate: `bash scripts/test-phase2.sh` passes all checks
  5. Success: All Phase 2 deliverables validated; pipeline is ready for live Kado testing

- [ ] **T4.2 Phase Validation** `[activity: validate]`

  - Integration test passes. Phase 1 test still passes. All files committed.

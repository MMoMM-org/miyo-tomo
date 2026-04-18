---
title: "Spec Consolidation — Implementation Plan"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION: ...]` markers have been addressed
- [x] All specification file paths are correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section is complete
- [x] All implementation phases are defined with linked phase files
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work is properly tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection `[activity: type]`
- [x] Every phase references relevant SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/006-spec-consolidation/requirements.md` — Product Requirements
- `docs/XDD/specs/006-spec-consolidation/solution.md` — Solution Design
- `docs/specs/README.md` — Current tier specs index (source of migration)

**Key Design Decisions**:

- **ADR-1**: Reference docs folder — Tier specs migrate to `docs/XDD/reference/` preserving tier hierarchy
- **ADR-2**: Standalone backlog file — `docs/XDD/backlog.md` with categorized items (features, doc-debt, bugs)
- **ADR-3**: Inline deviation annotations — Callout blocks within migrated specs, not a separate registry

**Implementation Context**:

```bash
# This is a documentation-only effort — no code tests or lint
# Validation commands:
git status                         # Track file moves
grep -r "docs/specs/" docs/ CLAUDE.md  # Find stale references after migration
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow: **Prime** (understand context), **Test** (verify preconditions), **Implement** (create/move/edit), **Validate** (check correctness).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. For docs-only work, "Test" verifies preconditions and "Validate" confirms correctness.

- [x] [Phase 1: Structure + Migration](phase-1.md)
- [ ] [Phase 2: Reconciliation + Deviations](phase-2.md)
- [ ] [Phase 3: Placeholder Completion](phase-3.md)
- [ ] [Phase 4: Index + Backlog + Cleanup](phase-4.md)

---

## Plan Verification

Before this plan is ready for implementation, verify:

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |

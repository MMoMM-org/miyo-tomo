---
title: "Tomo Companion Mode P1 — Framework Authoring Skills"
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

## Specification Compliance Guidelines

Reference specific SDD sections in each task; run the Specification Compliance check after each task;
verify all PRD acceptance criteria are covered before closing a phase. Document any deviation with
rationale and get approval before proceeding (Deviation Protocol).

## Metadata Reference

- `[parallel: true]` — tasks that can run concurrently
- `[ref: document/section]` — links to PRD/SDD
- `[activity: type]` — activity hint for specialist selection

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/026-companion-p1-authoring-skills/requirements.md` — PRD (22 ACs)
- `docs/XDD/specs/026-companion-p1-authoring-skills/solution.md` — SDD (ADR-1..9)
- `docs/XDD/ideas/2026-06-28-companion-p1-authoring-skills.md` — brainstorm charter

**Key Design Decisions** (SDD):
- **ADR-1**: One write-side skill `kado-write-patterns` (symmetric to read-side `kado-discovery-patterns`).
- **ADR-2**: `.base`/`.canvas` staged to `tomo-tmp/staged-artifact.<ext>` before upload.
- **ADR-3**: `inbox-author` = rename of `default-doc-writer` + extend; preserve 5-step pipeline + 3 STRICTs.
- **ADR-4**: `.base`/`.canvas` composed directly → `validate-json.py` gate → `kado-write-file.py operation=file`.
- **ADR-6**: format skills access-agnostic, differentiated triggers, NOT pre-loaded by inbox-author.
- **ADR-9**: safety logic in deterministic scripts (`validate-json.py`, `--no-overwrite`), not AI glue.

**Implementation Context**:
```bash
# Testing (system python lacks jsonschema — ALWAYS use the venv)
./venv/bin/python -m pytest tests/                 # unit + integration
# Quality
./venv/bin/ruff check .
# Skill authoring/audit (mandatory for every skill)
/skill-author
# Sync to instance (version-gated — bump # version or sync SKIPS the file; grep instance after)
./scripts/update-tomo.sh --yolo
# Residual-reference sweep after rename
rg default-doc-writer
```

---

## Implementation Phases

Each phase is a separate file. Tasks follow red-green-refactor: **Prime → Test → Implement → Validate**.

> **Tracking Principle**: track logical units that produce verifiable outcomes; the TDD cycle is the method.

- [x] [Phase 1: Deterministic Safety Scripts (L1 gate)](phase-1.md)
- [x] [Phase 2: Format-Knowledge Skills](phase-2.md)
- [x] [Phase 3: Write-Side Helper Skill](phase-3.md)
- [x] [Phase 4: inbox-author (rename + extend)](phase-4.md)
- [x] [Phase 5: Docs, Attribution, Ops & Integration](phase-5.md)

**Dependency order:** Phase 1 gates Phases 3 & 4. Phase 2 is independent (parallel with 1/3) but must
exist before Phase 4 live validation (auto-load). Phase 3 precedes Phase 4 (inbox-author pre-loads
`kado-write-patterns`). Phase 5 is last (integration + ops).

---

## Plan Verification

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
| All phase files exist and are linked from this manifest | ✅ |

---

## PLAN Status Report

| Field | Value |
|-------|-------|
| specId | 026-companion-p1-authoring-skills |
| title | Tomo Companion Mode P1 — Framework Authoring Skills |
| status | IN_REVIEW |
| phases | 5 |
| totalTasks | 18 (incl. per-phase validation) |
| parallelTasks | 3 (Phase 2 format skills) |
| clarificationsRemaining | 0 |

---
title: "F-34 — MSP Condition B: Accumulation Detection"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION: ...]` markers addressed (none — SDD fully locked)
- [x] All specification file paths correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] All implementation phases defined with linked phase files
- [x] Dependencies between phases clear (no circular dependencies)
- [x] Parallel work tagged with `[parallel: true]`
- [x] Activity hints provided `[activity: type]`
- [x] Every phase references relevant SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## PLAN Status Report

| Field | Value |
|-------|-------|
| specId | 015-msp-condition-b-accumulation |
| title | F-34 — MSP Condition B: Accumulation Detection |
| status | DRAFT |
| phases | 5 |
| totalTasks | 9 |
| parallelTasks | 2 (T1.1 ∥ T1.2) |
| specReferences | inline `[ref: ...]` per task |
| clarificationsRemaining | 0 |

---

## Architecture Recap (from SDD)

Four-stage cold-path pipeline, mirroring F-35 `placeholder_mocs`:

```
produce → persist → surface → consume
atomic-note-indexer.py → cache-builder → shared-ctx-builder (budget-trimmed) → inbox-analyst Step 4
```

Locked decisions: ADR-1 (new scanner script) · ADR-2 (`listNotes` bulk) · ADR-3
(`extract_topics_from_fields`) · ADR-4 (links `kind=='link'` only) · ADR-5
(`up::` via per-candidate `dataview-inline-field`) · ADR-6 (`min_cluster_size`
default 3) · ADR-7 (additive at `cache_version: 1`). See
[solution.md](../solution.md) §Architecture Decisions.

## Phase Dependency Graph

```
Phase 1 (foundation: kado_client + topic-extract)  ← no deps, T1.1 ∥ T1.2
   │
Phase 2 (scanner: atomic-note-indexer.py)          ← needs P1
   │
Phase 3 (persist + surface: cache-builder, shared-ctx)  ← needs P2 output shape
   │
Phase 4 (consume + orchestrate + docs)             ← needs P3 shared-ctx field
   │
Phase 5 (integration E2E + live validation)        ← needs P1–P4; T5.2 GATED on Kado release
```

## Phases

- [x] [Phase 1: Foundation — Kado client + structured topic extraction](phase-1.md)
- [ ] [Phase 2: Scanner — atomic-note-indexer.py](phase-2.md)
- [ ] [Phase 3: Persistence + shared-ctx surface](phase-3.md)
- [ ] [Phase 4: Consumer + orchestration + docs](phase-4.md)
- [ ] [Phase 5: Integration & live validation](phase-5.md)

## Specification Compliance Guidelines

1. **Before each phase:** read the Phase Context + every `[ref: ...]` before writing tests.
2. **During implementation:** reference SDD/PRD sections — don't re-decide locked ADRs.
3. **After each task:** run the Validate step; confirm no `/inbox` hot-path regression (CON-1).
4. **Phase completion:** verify the phase's mapped PRD acceptance criteria pass before moving on.

### Deviation Protocol

If implementation requires a spec change: document the deviation + rationale, get approval,
update the SDD when the deviation improves the design (memory
`feedback_plan_file_ownership_can_shift`). The most likely deviation site is the
`up::`-in-callout behaviour of `dataview-inline-field` (SDD Risk §2) — if it does NOT
return callout-embedded `up::`, A5 needs a fallback and the SDD must record it.

## PRD Acceptance Criteria → Phase Map

| AC | Phase | Task |
|----|-------|------|
| A1 (index in cache) | 3 | T3.1 |
| A2 (shared-ctx surfaces) | 3 | T3.2 |
| A3 (Step 4 fires B) | 4 | T4.1 |
| A4 (budget trim) | 3 | T3.2 |
| A5 (`up::` detection) | 2 | T2.1 |
| A6 (empty/new vault) | 2,3,5 | T2.1, T3.2, T5.1 |
| A7 (C-over-B precedence) | 4 | T4.1 |
| A8 (tests) | 1–5 | all (E2E: T5.1) |
| A9 (docs + version bumps) | 4 | T4.2, T4.3 |

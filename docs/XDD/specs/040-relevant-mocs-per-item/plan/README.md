---
title: "Every item sees every MOC, by name"
status: complete
version: "1.1"
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

## Output Schema

### PLAN Status Report

| Field | Value |
|-------|-------|
| specId | 040-relevant-mocs-per-item |
| title | Every item sees every MOC, by name |
| status | `COMPLETE` |
| totalTasks | 20 |
| parallelTasks | 7 |
| clarificationsRemaining | 0 |

### PhaseStatus

| Phase | Name | Tasks | File |
|-------|------|-------|------|
| 1 | Baseline run and builder | 6 | phase-1.md |
| 2 | Reader selector modes | 2 | phase-2.md |
| 3 | Reducer duplicate mutator | 2 | phase-3.md |
| 4 | Runtime prose: analyst and skills | 4 | phase-4.md |
| 5 | Owner-facing documentation | 2 | phase-5.md |
| 6 | Integration and live validation | 4 | phase-6.md |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate
2. **During Implementation**: Reference specific SDD sections in each task
3. **After Each Task**: Run Specification Compliance checks
4. **Phase Completion**: Verify all specification requirements are met

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale
2. Obtain approval before proceeding
3. Update SDD when the deviation improves the design
4. Record all deviations in this plan for traceability

## Metadata Reference

- `[parallel: true]` - Tasks that can run concurrently
- `[component: component-name]` - For multi-component features
- `[ref: document/section; lines: 1, 2-3]` - Links to specifications, patterns, or interfaces and (if applicable) line(s)
- `[activity: type]` - Activity hint for specialist agent selection

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/040-relevant-mocs-per-item/requirements.md` - Product Requirements (v1.1)
- `docs/XDD/specs/040-relevant-mocs-per-item/solution.md` - Solution Design (ADR-1 … ADR-10)
- `docs/XDD/specs/040-relevant-mocs-per-item/README.md` - Decisions Log
- GitHub issue #173 - measurements that motivated the spec

**Key Design Decisions**:

- **ADR-1**: One context file; the builder computes each MOC's `name` (title, or path on collision) once.
- **ADR-2/3**: The analyst reads names (`--moc-names`), nominates by meaning, and fetches detail once after Step 7.5 (`--mocs-from <file>`); `score` is confidence by meaning, thresholds 0.15 / 0.5 kept.
- **ADR-4**: Budget shedding removed; per-read size warnings at `--max-bytes` (default 32768).
- **ADR-6**: `lib/duplicate_proposals.py`, called by the reducer, converts proposals whose cluster key equals an eligible thematic title into unticked candidates.
- **ADR-8**: Delete the context before build; every analyst read passes `--run-id`.

**Implementation Context**:

```bash
# Testing
./venv/bin/python -m pytest -q tests                  # full suite (never bare python)
./venv/bin/python -m pytest -q tests/<file>.py        # focused

# Quality
./venv/bin/ruff check tomo/scripts scripts tests      # at every phase gate

# Prove RED: swap in main's version of the file under test, run, restore
git show main:<path> > <path>   # then: git checkout -- <path>  (or restore from branch)

# Sync to the TEST instance only (never tomo-privat)
./scripts/update-tomo.sh --instance tomo-instance --yolo

# Cost measurement
./venv/bin/python scripts/measure-inbox-phase-b-token-cost.py --session-latest --run-id <id>
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

Order: Phase 1 first (its T1.2 baseline must run before any change reaches the test instance). Phases 2 and 3 can run in parallel after Phase 1. Phase 4 needs 2 and 3. Phase 5 can run alongside Phase 4. Phase 6 last. Phases 1–4 ship together: nothing is synced to `tomo-instance` before Phase 6.

Per-item baseline details (MOC paths, titles) live in `tomo-instance/spec-040-baseline/` (gitignored); git receives counts and figures only.

- [ ] [Phase 1: Baseline run and builder](phase-1.md)
- [ ] [Phase 2: Reader selector modes](phase-2.md)
- [ ] [Phase 3: Reducer duplicate mutator](phase-3.md)
- [ ] [Phase 4: Runtime prose: analyst and skills](phase-4.md)
- [ ] [Phase 5: Owner-facing documentation](phase-5.md)
- [ ] [Phase 6: Integration and live validation](phase-6.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ (see traceability table below) |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |

### PRD acceptance criteria → tasks

| PRD AC | Task | Verified by |
|---|---|---|
| F1-AC1 | T2.1 (reader), T6.3 (every analyst read the names) | test + live |
| F1-AC2, F1-AC3, F1-AC4, F1-AC7 | T1.4 | test |
| F1-AC5 | T2.1 | test |
| F1-AC6 | T2.1, T6.2 | test |
| F2-AC1, F2-AC3, F2-AC4 | T4.2 | prose contract |
| F2-AC2 | T1.5, T6.2 | test |
| F2-AC5 | T2.1 (reader), T4.2 (analyst) | test + prose contract |
| F3-AC1 | T6.3 (seeded item) | live |
| F3-AC2, F3-AC3 | T4.2 | prose contract |
| F4-AC1, F4-AC2, F4-AC3 | T3.1 | test |
| F4-AC4 | T3.1 (count), T4.3 (relay) | test + prose contract |
| F5-AC1, F5-AC2 | T1.3 (predicate), T1.4 (builder, pool guard) | test |
| F5-AC3 | T3.1 | test |
| F6-AC1 | T4.3 | prose contract |
| F6-AC2 | T2.1 (reader), T4.2 (analyst passes `--run-id`, fails the item) | test + prose contract |
| F6-AC3 | T4.3 (guard) | test |
| S1-AC1 | T1.4 | test |
| S1-AC2 | T4.2 | prose contract |
| S2-AC1, S2-AC2 | T5.1 | document review |
| C1-AC1 | T1.5 | test |
| KPIs (quality, cost, previews) | T1.1 (scanner), T1.2, T6.3, T6.4 | live |

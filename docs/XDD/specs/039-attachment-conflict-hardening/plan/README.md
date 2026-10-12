---
title: "Attachment conflict hardening"
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

## Output Schema

### PLAN Status Report

| Field | Value |
|-------|-------|
| specId | 039-attachment-conflict-hardening |
| title | Attachment conflict hardening |
| status | `IN_REVIEW` |
| totalTasks | 28 |
| parallelTasks | 12 |
| specReferences | 111 |
| clarificationsRemaining | 0 |

### PhaseStatus

| Phase | Name | Tasks | File |
|-------|------|-------|------|
| 1 | Preconditions, no behaviour change | 7 | phase-1.md |
| 2 | Refusal rules | 3 | phase-2.md |
| 3 | The folder reaches both surfaces | 4 | phase-3.md |
| 4 | The attachment plan | 6 | phase-4.md |
| 5 | Reporting, and the delete that waits | 4 | phase-5.md |
| 6 | Release, live run, close-out | 4 | phase-6.md |

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

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/039-attachment-conflict-hardening/requirements.md` — PRD, 53 criteria
- `docs/XDD/specs/039-attachment-conflict-hardening/solution.md` — SDD, 10 ADRs, components K1–K16, K1 decision table (two passes)
- `docs/XDD/specs/039-attachment-conflict-hardening/research.md` — file:line facts behind every task
- `docs/XDD/specs/038-every-editable-decision-reaches-the-wire/solution.md` — ADR-1 (version-move order), ADR-5, ADR-6, ADR-7

**Key Design Decisions**:

- **ADR-1** — One attachment plan (K1) decided before the render loop; the embed rewrite and the move builder only read it.
- **ADR-2** — One raw-cached folder lookup (K2) shared by Pass 1, Pass 2's note guard and K1; `absent` and `unanswered` are distinct.
- **ADR-7 / ADR-8** — A taken target holds the owning notes (Ignore exempt); an unanswered check still emits the move, reported as unchecked.
- **ADR-10** — The origin's delete names every `move_asset` id of its attachments; it is a C1 change, so the Kokoro handoff (T1.1) precedes Phase 5.

**Implementation Context**:

```bash
./venv/bin/python -m pytest tests/ -q                         # full suite (never system python)
./venv/bin/python -m pytest tests/test_039_*.py -q            # this spec's tests
./venv/bin/python -m ruff check tomo scripts tests            # lint — at every phase gate
python3 scripts/wire-shape.py --obligations                   # preview the shape-manifest delta
python3 scripts/wire-shape.py --regenerate                    # write it
```

**Standing rules for every task:**

- Bump `# version:` on every edited runtime file under `tomo/` (update-tomo is version-gated).
- `git add <paths>` explicitly; never `-A`; never `git stash`.
- A test is RED only when shown failing against the unfixed code — revert the fix and run it.
- WHY goes to `docs/tomo/<mirrored-path>.md`, not into runtime files (repo CLAUDE.md).

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Preconditions, no behaviour change](phase-1.md)
- [ ] [Phase 2: Refusal rules](phase-2.md)
- [ ] [Phase 3: The folder reaches both surfaces](phase-3.md)
- [ ] [Phase 4: The attachment plan](phase-4.md)
- [ ] [Phase 5: Reporting, and the delete that waits](phase-5.md)
- [ ] [Phase 6: Release, live run, close-out](phase-6.md)

**Ordering, and why:**

- **Phase 2 before Phase 3.** No commit may let an owner-typed folder reach a destination unguarded. Phase 3 puts `proposed_dir` on both surfaces but nothing in Pass 2 reads it until Phase 4, which consumes Phase 2's checks.
- **Phase 4 before Phase 5.** The delete dependency reads the plan's owner map.
- **T1.1 before Phase 5.** CON-2 (owner ruling 2026-10-12): Kokoro receives the C1 proposal before the C1 code exists; nothing merges before Kokoro answers.
- **Inside Phase 3: T3.2 → T3.1 → T3.3.** The wire projects the record field Pass 1 adds; the inventory row needs the parser literal.
- **T1.3 before T3.1.** CON-1 / Gotcha: the vendored copy moves 2 → 3 first, so the v4 diff measures one step.

### PRD criterion → task

| PRD | Task | PRD | Task |
|-----|------|-----|------|
| F1-AC1 | T3.1 | F3-AC5 | T5.1 |
| F1-AC2 | T3.2 | F3-AC6 | T4.2, T5.1 |
| F1-AC3 | T3.3, T4.2 | F3-AC7 | T1.4, T4.1, T4.5 |
| F1-AC4 | T3.3, T6.3 | F4-AC1 | T4.2, T4.4 |
| F1-AC5 | T4.2 | F4-AC2 | T4.2, T4.4 |
| F1-AC6 | T4.2 | F4-AC3 | T4.4 |
| F1-AC7 | T4.3 | F4-AC4 | T4.2 |
| F1-AC8 | T3.3 | F4-AC5 | T4.4 |
| F1-AC9 | T3.3 | F4-AC6 | T4.2 |
| F1-AC10 | T4.2, T4.4 | F4-AC7 | T6.3 |
| F1-AC11 | T4.2 | F4-AC8 | T4.4 |
| F2-AC1 | T2.2 | F5-AC1 | T2.1 |
| F2-AC2 | T2.2 | F5-AC2 | T2.1 |
| F2-AC3 | T2.2 | F5-AC3 | T2.1 |
| F2-AC4 | T4.2, T4.3 | F5-AC4 | T2.1 |
| F2-AC5 | T2.2, T5.1 | F5-AC5 | T1.5 |
| F2-AC6 | T4.2 | F5-AC6 | T1.6 |
| F2-AC7 | T4.2, T4.5 | F6-AC1 | T5.2 |
| F2-AC8 | T4.2, T5.1 | F6-AC2 | T5.3, T6.3 |
| F3-AC1 | T4.2, T4.3 | F6-AC3 | T5.2 |
| F3-AC2 | T4.2 | F6-AC4 | T5.2 |
| F3-AC3 | T4.3 | F6-AC5 | T5.2 |
| F3-AC4 | T4.2 | F6-AC6 | T5.2, T6.2 |
| S1-AC1 | T6.1 | F6-AC7 | T5.3 |
| S1-AC2 | T6.1 | F6-AC8 | T5.1 |
| C1-AC1 | T4.5 | F2-AC9 | T2.2 |
| F5-AC7 | T2.1 | | |

### SDD component → task

K1 T4.2/T4.3 · K2 T1.4/T4.5 · K3 T4.1 · K4 T2.1/T2.2 · K5 T1.5/T4.3/T5.2 · K6 T4.4 · K7 T4.5/T5.1 (incl. the conductor) · K8 T5.1 · K9 T3.2 · K10 T3.1 · K11 T3.3 · K12 T1.3/T3.1/T3.2/T3.3/T5.2/T6.2 · K13 T6.1 · K14 T1.6 · K15 T1.4 · K16 T2.1/T2.2/T5.1

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ 53 of 53 |
| All SDD components have implementation tasks | ✅ K1–K16 |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |

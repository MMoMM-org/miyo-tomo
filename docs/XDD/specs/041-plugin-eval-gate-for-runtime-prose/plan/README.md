---
title: "Runtime prose gets a gate"
status: complete
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
| specId | 041-plugin-eval-gate-for-runtime-prose |
| title | Runtime prose gets a gate |
| status | `COMPLETE` |
| phases | 5 |
| totalTasks | 19 (5 phase-validation tasks included) |
| parallelTasks | 4 (T1.1, T1.2, T1.4, T4.3) |
| specReferences | 82 |
| clarificationsRemaining | 0 |

### PhaseStatus

| Phase | Name | Status | File |
|-------|------|--------|------|
| 1 | Runner, verdict and stub kit | completed | phase-1.md |
| 2 | Cases and the baseline on `main` | pending | phase-2.md |
| 3 | Conductor Step 4 fix | pending | phase-3.md |
| 4 | RED proofs and gate documentation | pending | phase-4.md |
| 5 | Close-out | pending | phase-5.md |

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

- `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/requirements.md` — PRD v1.1, 35 criteria (F1–F9)
- `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/solution.md` — SDD v1.0, C1–C8, ADR-1…ADR-10, 35 EARS criteria, the Mutation table
- `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/spike/` — seeds for every case and the evidence behind ADR-3/6/9/10 (read `spike/README.md` and `spike/3-sdd-verification/write-up.md` first)
- `scripts/CLAUDE.md` — user-invoked script conventions, `rm -rf` guard rule

**Key Design Decisions**:

- **ADR-1**: the plugin is assembled per invocation in `$TMPDIR` (working tree or `--rev`); the repo is never a write target.
- **ADR-3/4**: one stub kit `evals/_lib/stubs.sh`; stubs print the real scripts' output formats; notice lines are copied from Tomo's renderers with the source named.
- **ADR-5**: the leak guard is one canonical grader copied byte-identical into every case; the kit plants bait so it can fail.
- **ADR-8/9**: exit 0/1/2/3 = GREEN / RED / NOT GRADED / REFUSED; every paid run happens **outside Claude Code's Bash sandbox** (`dangerouslyDisableSandbox` with the user's approval, or the owner runs `! scripts/run-evals.sh`).
- **ADR-10**: `main` fails the relay and leak graders today; Phase 3 fixes conductor Step 4 (0.23.0 → 0.24.0), WHY first.

**Implementation Context**:

```bash
# Testing (always the venv — memory: run Tomo tests under ./venv/bin/python)
./venv/bin/python -m pytest tests/test_eval_verdict.py tests/test_run_evals.py tests/test_eval_suite_shape.py tests/test_eval_conductor_cases.py tests/test_eval_suite_not_synced.py
./venv/bin/python -m pytest tests/                       # full suite, phase gates

# Quality
./venv/bin/ruff check scripts/lib tests

# The gate (paid; outside the Claude Code Bash sandbox)
scripts/run-evals.sh                                      # full suite, runs 3
scripts/run-evals.sh --case <name> --runs 1               # partial, while developing
scripts/run-evals.sh --rev 4350ddd^ --case audit-gates-delivery
scripts/run-evals.sh --mutation <name> --case <case>

# Instance sync (Phase 3 only; never tomo-privat)
scripts/update-tomo.sh --instance tomo-instance --yolo
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Runner, verdict and stub kit](phase-1.md)
- [ ] [Phase 2: Cases and the baseline on main](phase-2.md)
- [ ] [Phase 3: Conductor Step 4 fix](phase-3.md)
- [ ] [Phase 4: RED proofs and gate documentation](phase-4.md)
- [ ] [Phase 5: Close-out](phase-5.md)

**Ordering, and why it cannot be changed:** Phase 2's baseline must run on the conductor as it is on `main` (it is the "before" that justifies Phase 3's STRICT block). Phase 4's Step-4 mutations are patches against prose, so they are written after Phase 3 changes Step 4. Phase 5's three consecutive GREEN runs are only meaningful once every gate grader has been seen red (Phase 4).

**PRD → task map:**

| PRD | Task | | PRD | Task |
|---|---|---|---|---|
| F1-AC1, AC2, AC3, AC5, AC6 | T1.3 | | F5-AC1…AC5 | T2.1 (graders), T3.2 (green) |
| F1-AC4 | T1.4 | | F6-AC1 | T1.2 (pattern, bait), T2.1 |
| F2-AC1, AC2, AC3, AC5 | T1.1 | | F6-AC2 | T1.2 (shape test), T1.3 (preflight) |
| F2-AC4, AC6 | T1.3 | | F7-AC1, AC2, AC3 | T4.3 |
| F3-AC1…AC3 | T2.1 | | F7-AC4, AC5 | T4.1, T4.2 |
| F4-AC1…AC4 | T2.1 | | F7-AC6 | T5.1 |
| F8-AC1, AC2 | T1.3 | | F9-AC1 | T1.1 |

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

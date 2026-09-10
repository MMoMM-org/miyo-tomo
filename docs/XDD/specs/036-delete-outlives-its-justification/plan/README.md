---
title: "A delete must not outlive the action that justified it"
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

### How to Ensure Specification Adherence

1. **Before Each Phase**: read the phase's Specification References gate.
2. **During Implementation**: reference the named SDD section in each task.
3. **After Each Task**: run the task's Success criteria against the PRD reference.
4. **Phase Completion**: run the phase validation task.

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale.
2. Obtain approval before proceeding.
3. Update the SDD when the deviation improves the design.
4. Record all deviations in this file for traceability.

**Deviations recorded so far**: none.

## Metadata Reference

- `[parallel: true]` — tasks that can run concurrently
- `[ref: document/section]` — links to specifications
- `[activity: type]` — activity hint for specialist agent selection

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/036-delete-outlives-its-justification/requirements.md` — Product Requirements
- `docs/XDD/specs/036-delete-outlives-its-justification/solution.md` — Solution Design
- `docs/XDD/specs/035-wire-schema-versioning/README.md` — owns the release this ships in
- `docs/tomo/scripts/lib/render_actions.md` — WHY layer for the module being changed
- `docs/instructions-json.md` — the instruction wire contract

**Key Design Decisions**:

- **ADR-1 Declare-then-collect** — every conditional delete declares its partner action ids at build
  time; one post-pass drops any delete whose declaration no longer resolves. The guard's input and
  the wire field are one relation.
- **ADR-2 Placement** — that pass runs **once, after all five drop sites**, before path validation.
  The five are split across two modules; anywhere earlier is a latent instance of the bug.
- **ADR-3 `create_moc` becomes a claimant** in `validate_destinations`; both claimants drop.
- **ADR-4 Retire the delete half** of the path-keyed withdrawal; keep the `link_to_moc` half.
- **ADR-5 One shared appliability predicate** for tag-handler groups — ADR-1's pass **cannot** reach
  Bug B, because the insert is never built and so has no id to name.
- **ADR-6 A dangling id aborts the run** with exit 2 rather than degrading.

**Implementation Context**:

```bash
# Testing — there is no requirements.txt; the venv is provisioned ad hoc
./venv/bin/python -m pytest                              # full suite
./venv/bin/python -m pytest tests/test_036_*.py -x       # this spec only
./venv/bin/python -m pytest -m integration               # opt-in, test vault

# Quality
./venv/bin/python -m ruff check tomo/ tests/
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand
context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the
> method, not separate tracked items.

- [ ] [Phase 1: Declare — depends_on at every emission site](phase-1.md)
- [ ] [Phase 2: Collect — the withdrawal pass](phase-2.md)
- [ ] [Phase 3: The cases the pass cannot reach](phase-3.md)
- [ ] [Phase 4: Contract, audit, reporting and integration](phase-4.md)

### Phase dependency graph

```mermaid
graph LR
    P1[Phase 1<br/>Declare] --> P2[Phase 2<br/>Collect]
    P2 --> P4[Phase 4<br/>Contract + integration]
    P3[Phase 3<br/>Unreachable cases] --> P4
    P1 -.no dependency.-> P3
```

Phase 3 is **independent of Phases 1 and 2** — the tag-handler defects share no code with the
`depends_on` machinery. It may run concurrently with them or before them. Phase 4 requires both.

### Ordering constraint that is not a phase boundary

The guards must be **released** with the wire field, never before it — a guard that drops a partner
without amending the deletes naming it produces a dangling id, and the executor's failure list
cannot catch one. Under ADR-1 that cannot happen, because the withdrawal *is* the amendment. The
constraint therefore binds the release, not the phase order.

---

## Acceptance-criteria coverage

| PRD Feature | ACs | Covered by |
|---|---|---|
| F1 Contested destination | 5 | T2.2, T2.3 |
| F2 Withheld daily action | 4 | T1.2, T2.1 |
| F3 Tag-handler emits no delete | 3 | T3.1 |
| F4 Not pre-approved | 3 | T3.2 |
| F5 Every delete names its justification | 6 | T1.1, T1.2, T1.3, T4.2 |
| F6 Document explains a withdrawal | 2 | T4.3 |
| F7 Destructive reads as destructive | 2 | **not covered — see below** |

**23 of 25 criteria map to tasks.** The two uncovered belong to F7, which is `Could Have` and
explicitly **not designed** in the SDD: a pure rendering change with no interaction with the
withdrawal mechanism. It stays in the PRD at `Could Have`; if it ships it ships as an independent
change. Stated here so the gap is a decision rather than an oversight.

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ 23/25; 2 deferred by decision (F7) |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ verified against `pyproject.toml` and the venv |
| All phase files exist and are linked from this manifest | ✅ |

---
title: "Implementation Plan — 037 asset destination collision is a Pass-1 decision"
status: pending
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] Every PRD acceptance criterion maps to a task
- [x] Every SDD component has implementation tasks
- [x] Every task carries a specification reference
- [x] Every task follows Prime / Test / Implement / Validate / Success
- [x] Dependencies are explicit and acyclic

### QUALITY CHECKS (Should Pass)

- [x] Every task produces a verifiable deliverable, not an activity
- [x] Parallel tasks can genuinely run independently
- [x] The final phase covers integration and the live path
- [x] Project commands match this repo's actual setup
- [x] A developer could follow this plan without asking questions

---

## Output Schema

### PLAN Status Report

| Field | Value |
|-------|-------|
| specId | 037-asset-destination-collision-is-a-pass1-decision |
| phases | 4 |
| tasks | 16 |
| status | pending |

### PhaseStatus

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Detection in the reducer | pending |
| 2 | The decision in the document | pending |
| 3 | Honouring the remedy in Pass 2 | pending |
| 4 | Integration and the live path | pending |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

Every task names the PRD criterion or SDD section it satisfies. A task that
cannot name one is not in this spec's scope and belongs in the backlog.

Two constraints in this spec are easy to satisfy by accident and hard to notice
when broken, so they are asserted per task rather than trusted:

- **A run with no conflicts must behave byte-identically.** Near-MVP, additive
  only. Every phase carries a regression assertion for this.
- **`instructions-diff` is a paired consumer.** ADR-3 says no new subtraction is
  needed — that is a claim the plan proves in Phase 3, not an assumption.

### Deviation Protocol

If implementation requires a change to the SDD, document the deviation with its
rationale and obtain approval before proceeding. If the deviation improves the
design, update `solution.md` — do not leave the document behind the code.

## Metadata Reference

`[activity: ...]` names the work's centre of gravity. `[parallel: true]` marks a
task with no dependency on its siblings in the same phase. `[ref: ...]` points
at the PRD criterion or SDD section that justifies the task.

### Success Criteria

A phase is complete when every task's Success line is demonstrably true, the
full suite passes, and `ruff` is clean. "Demonstrably" excludes self-reported
confirmation: a test claimed to be RED is proven RED by reverting the fix.

## Context Priming

Read before starting any phase:

- `docs/XDD/specs/037-asset-destination-collision-is-a-pass1-decision/requirements.md`
- `docs/XDD/specs/037-asset-destination-collision-is-a-pass1-decision/solution.md`
- `tomo/scripts/suggestions-reducer.py:1946-2016` — the T5.2 note-clash pass this
  spec extends; read it before writing anything, because the shape to follow is
  already there
- `tomo/scripts/lib/render_actions.py:640-728` — `_build_move_asset_actions`
- `tomo/scripts/instructions-diff.py:858-883` — `_subtract_skipped_assets`

Project commands:

```bash
./venv/bin/python -m pytest tests/ -q
./venv/bin/python -m ruff check tomo/scripts/
bash scripts/reset-tomo-tmp.sh --pass1 --instance <path>/tomo-tmp
```

## Implementation Phases

- [x] [Phase 1: Detection in the reducer](phase-1.md)
- [x] [Phase 2: The decision in the document](phase-2.md)
- [ ] [Phase 3: Honouring the remedy in Pass 2](phase-3.md)
- [ ] [Phase 4: Integration and the live path](phase-4.md)

## Plan Verification

| PRD criterion group | Covered by |
|---|---|
| F1 (detection, 5 criteria) | T1.1, T1.2, T1.3 |
| F2 (the decision surface, 5 criteria) | T2.1, T2.2, T2.3 |
| F3 (Pass 2 honours the remedy, 5 criteria) | T3.1, T3.2, T3.3 |
| S1 (same-file wording, 3 criteria) | T1.3, T2.2 |
| S2 (unresolved conflict called out, 1 criterion) | T2.3 |
| C1, C2 (3 criteria) | T2.1 (proposed name), T4.2 (summary) |
| SDD ADR-1 | T1.1 — the check lands in the reducer |
| SDD ADR-2 | T1.1 — the folder cache is generalised, not duplicated |
| SDD ADR-3 | T3.2 — proven, not assumed |
| SDD ADR-4 | T2.3, T3.1 — default and cleared-default semantics |
| SDD ADR-5 | T4.1 — asserted by absence: no wire change, no Hashi change |

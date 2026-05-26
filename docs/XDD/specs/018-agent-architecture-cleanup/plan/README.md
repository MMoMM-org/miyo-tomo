---
title: "XDD 018 — Inbox Routing Redesign & Agent Decomposition"
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

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| phases | PhaseStatus[] | Yes | Status of each implementation phase |
| totalTasks | number | Yes | Total tasks across all phases |
| parallelTasks | number | Yes | Tasks marked `[parallel: true]` |
| specReferences | number | Yes | Count of `[ref: ...]` specification links |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |

### PhaseStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| phase | number | Yes | Phase number |
| name | string | Yes | Phase name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| tasks | number | Yes | Task count in this phase |
| file | string | Yes | Path to phase file (phase-N.md) |
| detail | string | No | What needs clarification or what's in progress |

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

```markdown
# Single-line format
- Success: [Criterion] `[ref: PRD/AC-X.Y]`

# Multi-line format
- Success:
  - [ ] [Criterion 1] `[ref: PRD/AC-X.Y]`
  - [ ] [Criterion 2] `[ref: SDD/Section]`
```

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/018-agent-architecture-cleanup/requirements.md` - Product Requirements (PRD v0.2)
- `docs/XDD/specs/018-agent-architecture-cleanup/solution.md` - Solution Design (SDD v0.3)
- `docs/XDD/specs/018-agent-architecture-cleanup/audit.md` - Pre-018 agent inventory
- `docs/XDD/specs/018-agent-architecture-cleanup/audit-2026-05-25.md` - Runtime deviation audit

**Key Design Decisions**:

- **ADR-1**: Triage-first routing — all routing decisions by deterministic script before any LLM context loaded
- **ADR-2**: Skills at `tomo/dot_claude/skills/` — consistent with existing 6 skills, update-tomo.sh handles sync
- **ADR-3**: Sources as object array — `sources: [{path, checksum}]` for combined coverage + drift detection
- **ADR-5**: Strict routing-plan schema — `additionalProperties: false` to prevent field drift
- **ADR-6**: Big-bang migration — build new → tests → live-test → delete old (last commit)
- **ADR-7**: FAN resolve in suggestion-conductor — analysis work stays in analysis conductor

**Implementation Context**:

```bash
# Tests (host-side, not in container)
python3 -m pytest tests/ -v
python3 -m ruff check tomo/scripts/ scripts/
python3 -m mypy tomo/scripts/lib/

# Instance sync
bash scripts/update-tomo.sh

# Token measurement
python3 scripts/measure-inbox-pass-2-token-cost.py --session-latest

# Schema validation (manual)
python3 -c "import json, jsonschema; ..."
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [ ] [Phase 1: Schema Foundation (Layer D)](phase-1.md)
- [ ] [Phase 2: Triage Script (Layer A)](phase-2.md)
- [ ] [Phase 3: Skills & WHY Docs (Layer C + AC-14)](phase-3.md)
- [ ] [Phase 4: Conductors & Router (Layer B)](phase-4.md)
- [ ] [Phase 5: Integration, Live Test & Migration](phase-5.md)

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

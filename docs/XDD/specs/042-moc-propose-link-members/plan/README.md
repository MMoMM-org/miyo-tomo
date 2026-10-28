---
title: "/moc-propose finds MOC members through the link graph"
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

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/042-moc-propose-link-members/requirements.md` - Product Requirements (v1.1, 29 criteria)
- `docs/XDD/specs/042-moc-propose-link-members/solution.md` - Solution Design (v1.0, ADR-1…ADR-7)
- `docs/XDD/specs/042-moc-propose-link-members/README.md` - Owner decisions and the live `kado-graph` probe
- `docs/tomo/scripts/moc-discovery.md`, `docs/tomo/scripts/lib/render_actions.md` - WHY layers that get new sections

**Key Design Decisions**:
- **ADR-1**: Link source is live `kado-graph neighbors` via `KadoClient.graph`; never pass `limit`.
- **ADR-2**: Augment only `clusters[:max_results]`, after D3 + sort, before Phase 6.5; memoise per member path; ≥ 2 member hits.
- **ADR-3**: Eligibility offline from cache + profile + vault-config; uncached nodes skipped and counted.
- **ADR-4**: 60 attempts per run incl. retries; ≥ 0.3 s pacing; `attempt_count` + `attempt_gate`; all-or-nothing per cluster.
- **ADR-5/6/7**: Extension stays a `moc-proposal` doc (`### MOCxx — Extend [[X]]`, `**Extends:**`) → `extend_moc`; already-linked via `outgoing(moc)` at render time; link lines (` — linked with `) stay out of the squelch signature.

**Implementation Context**:
```bash
# Testing
./venv/bin/python -m pytest -q                         # full suite
./venv/bin/python -m pytest -q tests/test_link_members.py tests/test_moc_discovery_*.py   # focused

# Quality
./venv/bin/ruff check .

# Runtime-file rules (root CLAUDE.md)
# WHY in docs/tomo/<mirrored-path>.md FIRST; bump `# version:` on every managed file touched.
# Sync for live validation: ./scripts/update-tomo.sh --instance tomo-instance --yolo   (never tomo-privat)
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Budgeted lookups and node eligibility](phase-1.md)
- [x] [Phase 2: Link members in topic proposals](phase-2.md)
- [x] [Phase 3: around:<note>](phase-3.md)
- [x] [Phase 4: around:<MOC> extension, doc to instructions](phase-4.md)
- [ ] [Phase 5: Runtime prose, end-to-end and live validation](phase-5.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ (see Phase 5 T5.4 trace) |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |

### Criterion → task map

| PRD criteria | Task |
|---|---|
| F5-AC2, F5-AC3 | T1.1 |
| F6-AC1, F6-AC2, F6-AC3, F6-AC4 | T1.2 |
| F1-AC1…AC4, F5-AC1, F5-AC4 | T1.3, T2.1 |
| F4-AC1…AC3, F7 report fields | T2.2 |
| F4-AC4, F1-AC5 (parse) | T2.3 |
| F2-AC1…AC3, F5-AC5 | T3.1 |
| F2-AC4, F7-AC1, F7-AC2 | T5.1 |
| F3-AC1, F3-AC2 | T4.1 |
| F3-AC5 | T4.2 |
| F1-AC5, F3-AC3, F3-AC4 | T4.3, T4.4 |
| all | T5.2, T5.3, T5.4 |

---
title: "MOC-Propose Consolidation — Implementation Plan"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)
- [x] All `[NEEDS CLARIFICATION]` markers addressed
- [x] All specification file paths are correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)
- [x] Context priming section is complete
- [x] All implementation phases defined with linked phase files
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work tagged with `[parallel: true]`
- [x] Activity hints provided `[activity: type]`
- [x] Every phase references relevant SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Output Schema

### PLAN Status Report

| Field | Value |
|-------|-------|
| specId | 021-moc-propose-consolidation |
| title | MOC-Propose Consolidation |
| status | IN_REVIEW |
| phases | 4 |
| totalTasks | 20 |
| parallelTasks | 5 |
| clarificationsRemaining | 0 |

---

## Specification Compliance Guidelines

Schema-first ordering is mandatory (SDD Cross-Cutting / `feedback_spec_schema_consumer_three_way_drift`): the cache schema + writer + loader shim land BEFORE any consumer reads the new fields. The `up_parse` SSoT lands before both the builder and Phase 6.5 consume it.

### Deviation Protocol
Document deviations with rationale in the phase file; obtain approval; update SDD when the deviation improves the design (e.g. plan-time discovery that a target file has drifted from the SDD picture — `feedback_plan_section_namespace_collision`).

## Metadata Reference
- `[parallel: true]` — concurrent tasks · `[ref: doc/section]` — spec links · `[activity: type]` — specialist hint

---

## Context Priming

*GATE: Read before any implementation.*

**Specification**:
- `docs/XDD/specs/021-moc-propose-consolidation/requirements.md` — PRD (5 features, 22 ACs)
- `docs/XDD/specs/021-moc-propose-consolidation/solution.md` — SDD (10 ADRs, lib/ structure, data models)

**Key Design Decisions**:
- **ADR-1**: Cache schema = single `entries[]` + `kind:moc|note` + loader shim → `map_notes` (Phases 1–6 unchanged)
- **ADR-2**: Dual-`up` — inline `up::` wins over frontmatter `up:` on conflict
- **ADR-3**: `/explore-vault` force-rebuilds; `/moc-propose` rebuilds-if-stale (TTL 24 h)
- **ADR-5/9**: tag-primary discovery + real-vault placeholder denominator; new logic in `lib/` (moc-discovery already 1929 LOC)
- **ADR-4/10**: raise shared-ctx budget 15360→40960, placeholder never trimmed; retire accumulation by deletion

**Implementation Context**:
```bash
# Testing
python3 -m pytest tests/ -q                          # full suite
python3 -m pytest tests/test_<unit>.py -q             # focused
# Sync to running instance (required before any live run)
./scripts/update-tomo.sh --yolo
# Live diagnostics (host vs live Kado)
KADO_URL=http://127.0.0.1:<port>/mcp + token from tomo-instance/.mcp.json, sandbox off
# Version discipline: bump `# version:` on every modified runtime file or update-tomo ships nothing
```

---

## Implementation Phases

Each phase is a separate file. Tasks follow red-green-refactor: **Prime** → **Test** (red) → **Implement** (green) → **Validate** (refactor).

- [x] [Phase 1: Cache Foundation (builder + lib + schema + config)](phase-1.md)
- [ ] [Phase 2: /moc-propose consumes cache + dual-up + case-a](phase-2.md)
- [ ] [Phase 3: Inbox retire B / keep A+C / Feature 5 / budget](phase-3.md)
- [ ] [Phase 4: Integration, E2E & live validation](phase-4.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and linked as `[Phase N: Title](phase-N.md)` | ✅ |

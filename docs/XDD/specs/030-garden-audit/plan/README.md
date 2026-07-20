---
title: "Knowledge-Garden Audit Skill (/garden-audit) — Implementation Plan"
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

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/030-garden-audit/requirements.md` — PRD (5 Must features, 18 Gherkin ACs)
- `docs/XDD/specs/030-garden-audit/solution.md` — SDD (6 ADRs, interfaces, directory map)
- `docs/XDD/ideas/2026-07-18-garden-audit-skill.md` — brainstorm design + parking lot
- `_inbox/from-kado/2026-07-18_kado-to-tomo_graph-audit-contract.md` — kado-graph-audit contract

**Key Design Decisions** (from SDD):
- **ADR-1**: garden-audit is the 4th `/inbox` upstream doc-type (pending-accept + skip-analysis → zero Pass-1 cost).
- **ADR-2**: skill-owned instance exclusion config (seed, create-only), filter-before-render, managed only in-skill.
- **ADR-3**: one `edit_note_text` match/replace Hashi action for dead-link fix/remove + `up::` removal; repoint stays `add_relationship`; example-driven handoff.
- **ADR-4**: `garden-audit-wire` mirrors ADR-026 (emit_digest, load/build_from_wire).
- **ADR-5**: check→action mapping + data-source split (cache / kado-graph-audit / listDir).
- **ADR-6**: new pipeline components mirror the `/moc-propose` track.

**Implementation Context**:
```bash
# Testing
./venv/bin/python -m pytest tests/                 # unit + integration (system python3 lacks jsonschema)
./venv/bin/python -m pytest tests/test_garden_*    # this feature's tests

# Quality
./venv/bin/ruff check tomo/scripts scripts tests   # lint (run at phase gates)

# Delivery into the container instance
scripts/update-tomo.sh                              # syncs runtime + seed config
```

---

## Implementation Phases

Each phase is a separate file. Tasks follow red-green-refactor: **Prime** → **Test** → **Implement** → **Validate**.

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Data & Config Foundations](phase-1.md)
- [x] [Phase 2: Scan Orchestrator](phase-2.md)
- [x] [Phase 3: Render — Report + Wire](phase-3.md)
- [x] [Phase 4: Apply Integration (2-pass + edit_note_text)](phase-4.md)
- [x] [Phase 5: Agent, Command, Wizard, Docs](phase-5.md)
- [ ] [Phase 6: Cross-Repo Handoffs & Integration/E2E](phase-6.md)

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
| All phase files exist and are linked as `[Phase N: Title](phase-N.md)` | ✅ |

## Dependency Graph

```
Phase 1 (foundations: graph_audit, exclusions, seed) ──┐
                                                        ├─> Phase 2 (scan) ─> Phase 3 (render+wire) ─┐
                                                        │                                             ├─> Phase 4 (apply) ─> Phase 5 (agent/cmd/wizard) ─> Phase 6 (cross-repo + E2E)
edit_note_text (Phase 4 T4.1) ──────────────────────────────────────────────────────────────────────┘
```

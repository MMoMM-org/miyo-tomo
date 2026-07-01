---
title: "Profile-Agnostic Markers & MOC Suffix — Implementation Plan"
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

Follow the SDD's confirmed ADRs. The **primary gate for every code task** is: `miyo`-profile output stays byte-identical (CON-2). Any task that cannot preserve that must stop and surface it (Deviation Protocol) before proceeding.

### Deviation Protocol
1. Document the deviation with rationale. 2. Obtain approval. 3. Update SDD if it improves the design. 4. Record here.

## Metadata Reference
- `[parallel: true]` — concurrent-safe tasks
- `[ref: doc/section; lines: N]` — spec links
- `[activity: type]` — specialist hint

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/028-profile-agnostic-markers/requirements.md` — PRD (F-16 + F-55)
- `docs/XDD/specs/028-profile-agnostic-markers/solution.md` — SDD (Conventions DI, 2 channels)
- `docs/XDD/specs/028-profile-agnostic-markers/README.md` — seam map (Context section)

**Key Design Decisions**:
- **ADR-1** Delivery channel — per-script direct resolution for `--config`/`--profile` scripts; `suggestions-doc.json` `conventions` block for `suggestion-parser`. NOT shared-ctx.
- **ADR-2** `profiles_dir` is caller-supplied — never computed inside the lib (instance flattened-layout safety).
- **ADR-3** Missing-key defaults — markers `up::`/`related::`, suffix `""`.

**Implementation Context**:
```bash
# Testing (system python3 lacks jsonschema — use venv)
./venv/bin/python -m pytest tests/

# Quality
./venv/bin/ruff check tomo/scripts/

# Live (ONCE, final task only)
# one /inbox walk against Kado after sync
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime**, **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Foundation — Conventions resolver + profile keys](phase-1.md)
- [ ] [Phase 2: Suffix seams (F-55)](phase-2.md)
- [ ] [Phase 3: Marker seams (F-16)](phase-3.md)
- [ ] [Phase 4: Wire-in, verify, single live-test](phase-4.md)

**Dependency graph**: P1 blocks all. P2 and P3 both depend on P1 but are independent of each other (can run in parallel). P4 depends on P2 + P3.

**Out of scope** (do not touch): `FOOTER_CALLOUTS` in `moc-tree-builder.py` and `lib/render_resolve.py:28`; `shared-ctx.schema.json`; new profiles/UI/CLI flags.

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

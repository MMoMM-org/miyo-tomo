---
title: "Structure-Aware Tag-Handler Compose — Implementation Plan"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)
- [x] All `[NEEDS CLARIFICATION]` markers addressed
- [x] All specification file paths correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)
- [x] Context priming complete
- [x] All phases defined with linked phase files
- [x] Dependencies clear (schema-first hard gate; no circular deps)
- [x] Parallel work tagged `[parallel: true]`
- [x] Activity hints provided
- [x] Every phase references SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E in final phase
- [x] Project commands match actual setup

---

## Specification Compliance Guidelines

**Hard dependency gate:** Phase 1 (schema) MUST complete and be green before Phases 3–6 (producer +
consumers). This prevents the SDD's CON-1 three-way-drift failure (`additionalProperties:false` silently
strips/rejects uncoordinated fields). Phase 2 (pure helper) may run in parallel with Phase 1.

**Deviation Protocol:** document any deviation from the SDD with rationale in the phase file; obtain
approval; update the SDD if the deviation improves the design.

---

## Context Priming

*GATE: Read all of these before starting any implementation.*

**Specification:**
- `docs/XDD/specs/025-structure-aware-tag-handler-compose/requirements.md` — PRD (FR-15…FR-22, 24 ACs)
- `docs/XDD/specs/025-structure-aware-tag-handler-compose/solution.md` — SDD (11 ADRs, helper contract)
- `docs/XDD/ideas/2026-06-25-structure-aware-tag-handler-compose.md` — brainstorm
- `docs/XDD/specs/024-tag-handler-framework/` — the framework this extends
- `tomo/scripts/lib/moc_structure.py` — purity-contract precedent for the new helper

**Key Design Decisions (from SDD):**
- **ADR-1 Hybrid** — config declares intent; compose reads the target for reality.
- **ADR-3 Deterministic helper** — `target_structure.py` parses/assembles; only `synthesize` cells use the LLM.
- **ADR-6 Reuse `insert_under_marker` + `block` anchor** — no new Tomo action; Hashi shipped the anchor.
- **ADR-7 Schema parity** — add `block` to both wire schemas; mirror `replace_section` (no Tomo emitter).
- **ADR-8 Fallback** — helper signals mismatch → prose block + reducer ⚠️; never a malformed row.
- **ADR-9 Parse contract** — first structure of the declared type under the marker wins.
- **CON-1 schema-first ordering** — the hard gate above.

**Implementation Context (actual project commands):**
```bash
# Tests (MUST use the venv — system python3 lacks jsonschema → phantom failures)
./venv/bin/python -m pytest tests/ -q
./venv/bin/python -m pytest tests/test_target_structure.py -q   # focused

# Lint
ruff check tomo/ scripts/ tests/

# Sync source → Docker instance (from repo root; sandbox off for .claude cp)
./scripts/update-tomo.sh --yolo

# Run a Tomo script from host against live Kado (cheap paths only)
KADO_URL=127.0.0.1:<port>/mcp ./venv/bin/python tomo/scripts/<script>.py ...
```

---

## Implementation Phases

Each phase is a separate file. Tasks follow red-green-refactor: **Prime → Test → Implement → Validate**.

- [x] [Phase 1: Schema Foundation](phase-1.md)
- [x] [Phase 2: Deterministic Helper (target_structure.py)](phase-2.md)
- [x] [Phase 3: Producer-Chain Propagation](phase-3.md)
- [ ] [Phase 4: Interpreter Compose](phase-4.md)
- [ ] [Phase 5: Render (block anchor)](phase-5.md)
- [ ] [Phase 6: Reduce / Review Surface](phase-6.md)
- [ ] [Phase 7: Integration, Docs & Live Validation](phase-7.md)

**Dependency graph:**
```
Phase 1 (schema) ──┬─→ Phase 3 (producer) ─→ Phase 4 (interpreter) ─→ Phase 6 (reduce)
                   └─→ Phase 5 (render)                              ┘
Phase 2 (helper) ──────────────────────────→ Phase 4 (interpreter)
Phases 1-6 ────────────────────────────────→ Phase 7 (integration + live)
```
Phase 2 is independent of Phase 1 (pure lib) and may run in parallel. Phases 4/5/6 all depend on 1; 4
also depends on 2 and 3; 6 depends on 4; 7 depends on all.

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies explicit, no circular references | ✅ |
| Parallel opportunities marked | ✅ |
| Each task has specification references | ✅ |
| Project commands accurate | ✅ |
| All phase files exist and linked as `[Phase N: Title](phase-N.md)` | ✅ |

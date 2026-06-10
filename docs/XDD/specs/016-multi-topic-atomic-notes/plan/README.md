---
title: "F-41 Multi-topic detection — Implementation Plan"
status: draft
version: "1.0"
---

# Implementation Plan — XDD 016 (F-41)

> PRD: [../requirements.md](../requirements.md) (locked) · SDD: [../solution.md](../solution.md) (validated, 8 ADRs).
> Branch: `feat/f-41-multi-topic-atomic-notes`. Every task carries `[ref: …]` to PRD/SDD.

## Validation Checklist

### CRITICAL GATES
- [x] All `[NEEDS CLARIFICATION]` markers addressed
- [x] All specification file paths exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS
- [x] All implementation phases defined with linked phase files
- [x] Dependencies between phases clear (no circular)
- [x] Parallel work tagged `[parallel: true]`
- [x] Every phase references SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests in final phase
- [x] Project commands match actual setup (`./venv/bin/python -m pytest`)

---

## Context Priming

*GATE: read before any implementation.*

**Specification**:
- `docs/XDD/specs/016-multi-topic-atomic-notes/requirements.md` — PRD (A1–A11, OQ1–OQ8 resolved)
- `docs/XDD/specs/016-multi-topic-atomic-notes/solution.md` — SDD (8 ADRs, C1–C6 collapse table, Runtime View)

**Key Design Decisions**:
- **ADR-1** — Segmentation is LLM-driven `Step 7.5` in `inbox-analyst.md` (agent-side, no script).
- **ADR-2** — Wire format = N `create_atomic_note` in the existing `actions[]` array; NO `threads[]` wrapper.
- **ADR-3** — Segmentation gated behind a `> 200 words` length pre-check; short items → single default thread.
- **ADR-4** — Each atomic carries an explicit `source_stem` provenance key.
- **ADR-5** — No `instructions.schema.json` change (proven N≥2-capable); minimal `item-result.schema.json` change.
- **ADR-6** — Source-deletion completion gate: delete only after ALL derived atomics + any daily committed.
- **ADR-7** — Filename collision guard in render (`_NN` suffix, never silent-overwrite).
- **ADR-8** — Parser stem maps `dict[str,dict]` → `dict[str,list[dict]]`.

**Implementation Context**:
```bash
# Testing — MUST use the instance venv (system python lacks jsonschema)
./venv/bin/python -m pytest                         # full suite
./venv/bin/python -m pytest tests/<file> -q         # focused
# Quality
./venv/bin/ruff check tomo/scripts/
# Sync runtime into instance (bump `# version:` first!)
./scripts/update-tomo.sh
```

---

## Implementation Phases

Tasks follow red-green-refactor: **Prime** → **Test** (red) → **Implement** (green) → **Validate** (refactor).

> **Dependency shape:** Phase 1 (schema) and Phase 2 (analyst) establish the N≥1 contract.
> Phases 3, 4, 5 touch **independent files** (reducer / parser / render) and may run in
> parallel once Phase 2's output contract is fixed. Phase 6 integrates and validates E2E.

- [x] [Phase 1: Schema & source_stem contract](phase-1.md)
- [ ] [Phase 2: Analyst Step 7.5 segmentation](phase-2.md)
- [ ] [Phase 3: Reducer N-block rendering (C1, C2)](phase-3.md)
- [ ] [Phase 4: Parser N-entry parsing (C3, C4)](phase-4.md)
- [ ] [Phase 5: Render N notes + delete gate (C5, C6)](phase-5.md)
- [ ] [Phase 6: Integration, E2E, cost & docs](phase-6.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow without further clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria (A1–A11) map to tasks | ✅ |
| All SDD components (analyst, reducer, parser, render, schema) have tasks | ✅ |
| Dependencies explicit, no circular references | ✅ |
| Parallel opportunities marked (P3/P4/P5) | ✅ |
| Each task has `[ref: …]` | ✅ |
| Project commands accurate (venv pytest) | ✅ |
| All phase files exist and linked as `[Phase N: Title](phase-N.md)` | ✅ |

### AC → Phase traceability

| PRD AC | Phase / Task |
|--------|--------------|
| A1 segmentation pass | P2 / T2.1 |
| A2 multi-thread emission | P2 / T2.1 |
| A3 provenance source_stem | P1 / T1.1, P2 / T2.1 |
| A4 reducer N blocks | P3 / T3.1, T3.2 |
| A5 parser N entries | P4 / T4.1 |
| A6 render N notes | P5 / T5.1 |
| A7 schema validation | P1 / T1.1 |
| A8 FAN resolve N | P4 / T4.2 |
| A9 daily + atomic mix | P2 / T2.1, P5 / T5.2 |
| A10 tests (8 cases) | P6 / T6.1 |
| A11 documentation | P6 / T6.3 |

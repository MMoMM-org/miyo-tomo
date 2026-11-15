---
title: "/review: review material for the user's own template sections"
status: approved
version: "1.1"
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
- `[model: routine|hard|frontier]` - Overrides the spec's model tier for this task

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

- `docs/XDD/specs/046-review-template-sections/requirements.md` — PRD v1.3 (49 criteria, amendments to spec 045)
- `docs/XDD/specs/046-review-template-sections/solution.md` — SDD v1.2 (13 ADRs; Complex Logic `plan_section`)
- `docs/XDD/specs/046-review-template-sections/README.md` — Decisions Log (owner decisions; two validation passes)
- `docs/XDD/specs/045-weekly-monthly-review/solution.md` — the base design (v1.25)
- `docs/tomo/dot_claude/skills/periodic-review.md` — the skill's WHY layer
- `_outbox/for-hashi/2026-11-14_tomo-to-hashi_replace-between-markers.md` — the contract Hashi builds (gitignored, local)

**Key Design Decisions**:

- **ADR-1 / ADR-2**: one Pass 1 model pass writes `sections` beside the unchanged `groups`; scripts check keys, caps (refuse, never cut), double placement (only with a mapping) and sources.
- **ADR-4 / ADR-10**: each block sits between `%% tomo:<id> <period> %%` and `%% /tomo:<id> <period> %%`; the first delivery uses `insert_under_marker`, a re-run `replace_between_markers`; `plan_section` mirrors Hashi's parse and stops rather than writes blind.
- **ADR-8 / ADR-9**: off-limits headings (heading only or with sub-sections) are never written, and the landing check also guards `before`/`end` placements and the "Tomo Review" placement; the template analysis is deterministic and conservative.
- **ADR-5**: instructions wire `schema_version` "3" → "4", lockstep with Hashi; every instruction-schema change (producer schema, version, manifest, vendored copy) lands together in T6.1 after Hashi's release; until then new-action tests use a test-only schema built from the handoff fragment, and the full suite stays GREEN; Tomo builds no converter.
- **ADR-6 / ADR-7**: the quarter reads through a `CHILD` table; the month's output is pinned by a golden test before the refactor; a quarter's read is measured first, then split per month.

**Implementation Context**:

```bash
# Testing
./venv/bin/python -m pytest tests/ -q                       # full suite (GREEN at every phase validation)
./venv/bin/python -m pytest tests/test_review_*.py tests/test_period.py -q
./venv/bin/python -m pytest tests/test_035_wire_gate.py tests/test_035_wire_manifests.py tests/test_tomo_schema_parity.py tests/test_hashi_instructions_schema.py -q
./venv/bin/python -m pytest -m integration tests/           # opt-in, Privat-Test (owner go)

# Quality
./venv/bin/ruff check tomo/scripts scripts tests

# Measurement and sync (owner instruction only)
python3 tomo/scripts/review-read.py --kind quarter --period 2026-Q1 --stem <stem> --measure
scripts/update-tomo.sh --instance tomo-instance --yolo
python3 scripts/tomo-session-stats.py --session <jsonl>
```

Standing rules for every task: WHY to `docs/tomo/<mirrored-path>.md` first, runtime prose second, imperatives only in `tomo/dot_claude/**`; bump `# version:` on every managed file; runtime skill edits through `tcs-helper:skill-author`; stage explicit paths only; never `git stash/reset/restore/clean/checkout`; never a `CLAUDE_ALLOW_*` override; never touch `tomo-privat`; never edit the test vault directly (writes reach it only through the owner's Hashi apply in T6.3) and never quote journal text; no eval-gated file changes (CON-6); subagents never on fable.

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [ ] [Phase 1: Foundations — config, writer, template analysis, quarter period](phase-1.md)
- [ ] [Phase 2: Setup — mapping, off-limits, template choice](phase-2.md)
- [ ] [Phase 3: Reading — child-review level, quarter, read files](phase-3.md)
- [ ] [Phase 4: Pass 1 — proposals and the review document by section](phase-4.md)
- [ ] [Phase 5: Pass 2 — delivery into the user's sections](phase-5.md)
- [ ] [Phase 6: Wire v4, integration, live walk and close-out](phase-6.md)

**Phase dependencies:** 1 → 2 → T3.1 → T3.2 → T3.3 → {T4.1–T4.4 ∥ T3.4 (owner-gated measurement)} → T4.5 → 5 → 6. Inside Phase 1, T1.3 needs T1.1 and T1.4. Inside Phase 5: T5.1 ∥ T5.3 → T5.2 → T5.4 → T5.5 → T5.6. Phase 6's wire step (T6.1) waits for Hashi's release.

**Criteria → task map (one primary task per PRD criterion):**

| Criteria | Task |
|---|---|
| F2-AC3, F2-AC5, F2-AC11 (analysis, landing function) | T1.2 |
| F2-AC7, F2-AC8, F2-AC10 | T1.3 |
| F6-AC2, F6-AC3 | T1.4 |
| F2-AC1, F2-AC9, F6-AC1, F7-AC1, F7-AC2, F7-AC3 | T2.1 |
| F2-AC4 | T2.2 |
| F2-AC2, F2-AC6 | T2.3 |
| F6-AC4, F6-AC5 | T3.2 |
| F1-AC1 | T3.3 |
| F1-AC3, F1-AC4, F1-AC5, F1-AC6, F1-AC9 (check) | T4.1 |
| F1-AC7, F1-AC8, F1-AC10, F3-AC1, F3-AC2, F3-AC3 | T4.2 |
| F3-AC4, F3-AC5, F3-AC6 | T4.3 |
| F1-AC2 | T4.4 |
| F4-AC2, F4-AC3, F4-AC4, F5-AC1, F5-AC2, F5-AC3, F5-AC5 | T5.1 |
| F4-AC5, F2-AC12 | T5.2 |
| F4-AC7 | T5.3 |
| F4-AC1 | T5.4 |
| F4-AC6, F5-AC4 | T5.5 |
| F6-AC6 | T6.2 (quarter Pass 1 reading: T4.5) |

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

---
title: "MOC insertion-point intelligence"
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

## Output Schema

### PLAN Status Report

| Field | Value |
|-------|-------|
| specId | 022-moc-insertion-point-intelligence |
| title | MOC insertion-point intelligence |
| status | IN_REVIEW |
| totalTasks | 22 |
| parallelTasks | 3 |
| clarificationsRemaining | 0 |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Read the phase's Specification References gate.
2. **During Implementation**: Reference the cited SDD/PRD section in each task.
3. **After Each Task**: Run the task's tests under `./venv/bin/python`.
4. **Phase Completion**: Run the phase validation task.

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale.
2. Obtain approval before proceeding.
3. Update SDD when the deviation improves the design.
4. Record deviations in the spec README Decisions Log.

## Metadata Reference

- `[parallel: true]` — Tasks that can run concurrently
- `[ref: document/section; lines: ...]` — Links to specifications
- `[activity: type]` — Activity hint for specialist agent selection
- `[needs-hashi]` / `[cross-repo]` — Cross-repo coordination required

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/022-moc-insertion-point-intelligence/requirements.md` — Product Requirements (16 ACs)
- `docs/XDD/specs/022-moc-insertion-point-intelligence/solution.md` — Solution Design (7 ADRs, directory map, gotchas)
- `docs/XDD/specs/022-moc-insertion-point-intelligence/research-synthesis.md` — Agent-team research (file:line)

**Key Design Decisions**:
- **ADR-1**: Anchor carrier = `create_atomic_note.candidate_mocs[].anchor` (the dead `link_to_moc.section_name` is NOT reused).
- **ADR-2**: Cost = A-trimmed (eager headings-only inventory, cap ~8/MOC, skip Dewey/classification, `enforce_budget` drops inventory first).
- **ADR-3**: New-section encoding = explicit `new_section` field on instructions `link_to_moc`; render builds `line_to_add` at serialize.
- **ADR-4**: Heading inventory parsed in `moc-tree-builder` via a shared `lib/moc_structure.py` (zero new Kado calls).
- **ADR-5**: Honor via the existing `anchor.value` guard in `resolve_section_names` — `_emit` stamps the Pass-1 anchor → heuristic auto-suppresses.
- **ADR-6**: Last-resort = H1-title heading anchor (`placement:after`); no new Hashi shape.
- **ADR-7**: Cross-repo Kokoro ADR + `_outbox/for-hashi` confirmation handoff + real walk.

**Hard ordering constraints** (from SDD gotchas):
- Schema BEFORE consumer (`additionalProperties:false` strips undeclared fields → consumer reads `None`).
- Shared `lib/moc_structure.py` BEFORE its consumers (moc-tree-builder build-time AND instruction-render render-time fallback share it).
- Bump `# version:` on every edited managed runtime file or `update-tomo` skips it silently.
- `FOOTER_CALLOUTS` stays hardcoded (#35/F-55) — the lib takes the footer set as a PARAM.

**Implementation Context**:
```bash
# Testing (system python3 lacks jsonschema — MUST use venv)
./venv/bin/python -m pytest tests/                    # Unit tests
./venv/bin/python -m pytest tests/test_moc_insertion_resolution.py   # this spec's suite

# Sync to instance (bump # version: first, run sandbox-off for .claude/{agents,commands})
./scripts/update-tomo.sh

# Host vs live Kado (validation walk)
KADO_URL=127.0.0.1:<port>/mcp + token from tomo-instance/.mcp.json   # sandbox off
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** → **Test** (red) → **Implement** (green) → **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Shared parse foundation](phase-1.md)
- [x] [Phase 2: Schema additions](phase-2.md)
- [x] [Phase 3: Inventory producers](phase-3.md)
- [x] [Phase 4: Pass-1 four-tier decision](phase-4.md)
- [x] [Phase 5: Render honor path](phase-5.md)
- [ ] [Phase 6: Suggestions surfacing](phase-6.md)
- [ ] [Phase 7: Cross-repo + live walk](phase-7.md)

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
| All phase files exist and are linked from this manifest | ✅ |

## Acceptance-Criteria → Task Coverage Map

| AC | Task(s) |
|----|---------|
| AC-1 semantic fitting heading | T4.1 |
| AC-2 zero-token-overlap semantic fit | T4.1, T4.2 |
| AC-3 exactly one tier in order | T4.1, T5.1 |
| AC-4 new section when none fits | T4.1 |
| AC-5 name from topic (not "Key Concepts") | T4.1, T5.2 |
| AC-6 new section before footer + newline | T5.2, T2.3 |
| AC-7 editable-callout fallback | T4.1 |
| AC-8 callout config priority, tier-3 only | T1.1, T4.1 |
| AC-9 H1 last-resort | T4.1, T1.1 |
| AC-10 never unresolved | T4.1, T5.1 |
| AC-11 one `**Placement:**` line, no bare anchor | T6.1 |
| AC-12 user edit honored | T5.1, T6.1 |
| AC-13 decided before confirm gate | T4.1, T6.1 |
| AC-14/AC-15 live walk | T7.3 |
| AC-16 ambiguous-fit advisory | T6.2 |
| EC-2 in-run new MOC vs template | T5.3 |
| EC-5 classification excluded | T4.1 |
| EC-6 override to non-existent heading → new section | T5.1 |

---
title: "MOC placement-fit confidence"
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
| specId | 023-moc-placement-fit-confidence |
| title | MOC placement-fit confidence |
| status | IN_REVIEW |
| totalTasks | 11 |
| parallelTasks | 2 |
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
- `docs/XDD/specs/023-moc-placement-fit-confidence/requirements.md` — Product Requirements (12 ACs)
- `docs/XDD/specs/023-moc-placement-fit-confidence/solution.md` — Solution Design (4 ADRs, directory map, traced walkthrough, gotchas)
- `docs/XDD/specs/022-moc-insertion-point-intelligence/solution.md` — the four-tier order + anchor carrier + honor path this spec extends

**Key Design Decisions** (SDD ADR-1..5, all confirmed 2026-06-16):
- **ADR-1**: `fit_confidence` is the LLM's own self-assessed 0-1 score — no calibration layer (reuses the pattern already used by `type_confidence`, MOC `score`, `classification.confidence`, `atomic_note_worthiness`).
- **ADR-2** (corrected 2026-06-16): No-footer tier-2 → `type:line`/`after` last body line, **resolved at render**. Pass-1 emits a `line`/`after` anchor with **null value** (it cannot see the MOC body); the Pass-2 render resolver fills the value with the live MOC's last body line — symmetric with how 022 resolves the footer-callout text.
- **ADR-3**: A gate-rejected tier-1 runner-up is carried into 022's existing `alt_headings` advisory (one-click retarget preserved).
- **ADR-4**: Threshold hardcoded at **0.6** inline in `inbox-analyst.md` (matches the existing 0.7/0.5/0.15 inline thresholds); no config surface this phase.
- **ADR-5**: A cheap `has_footer` boolean (computed at cache build from body bytes already in hand — no new Kado read) is surfaced on `shared_ctx.mocs[]`. Pass-1 reads it to pick the **truthful** tier-2 anchor type BEFORE the live MOC is read, so the suggestions doc shows WHERE the section lands (`(before the footer)` / `(at the end of the MOC)`) at review time.

**Two-pass timing (the spine of the corrected design):**
- The **suggestions doc is a Pass-1 artifact** (built before the user approves). The **render resolver runs at Pass-2** (after approval), and is the ONLY place the live MOC body is read.
- Therefore: anything the doc must SHOW about placement must be decidable at Pass-1 (→ `has_footer`); and anything that needs the MOC body text (footer-callout text, last body line) is filled at Pass-2 (→ render resolver fills null values).
- The analyst MUST emit `value:null` for tier-2 anchors. Do NOT instruct it to emit `<last body line>` — it has no body and would hallucinate a string Hashi can't match.

**Hard ordering constraints** (from SDD gotchas / CON-7):
- Schema BEFORE consumers — `fit_confidence` added to `item-result.schema.json` first (Phase 1, DONE), or `additionalProperties:false` strips the analyst's emission → consumer reads `None`.
- `has_footer` inventory (Phase 2) BEFORE the analyst reads it (Phase 3). Cache-schema change → rebuild via `/explore-vault` before the live walk.
- Bump `# version:` on every edited managed runtime file (`moc-tree-builder.py`, `shared-ctx-builder.py`, `inbox-analyst.md`, `suggestions-reducer.py`, `instruction-render.py`) or `update-tomo` skips it silently.
- `fit_confidence` is NOT a Hashi field — it stays on the item-result anchor; confirm it does not leak into the Pass-2 `instructions.schema.json` action anchor (`{type,value}` only). 022's `_emit` decomposition already strips non-`{type,value}` keys — verify.
- `alt_headings` semantic broadens to also carry the gate-rejected heading — keep 022's render dedup/empty-filter (never render an empty `## ` advisory).
- Render now resolves null-value `line` anchors (it historically skipped `line` anchors). `_serialize_new_sections` already builds `line_to_add` from the top-level `new_section` once the anchor value is resolved — that part is unchanged.

**Scope boundaries** (PRD Won't-Have / SDD CON-6):
- Insertion-point only — must NOT touch MOC-selection (`candidate_mocs[].score`, `needs_new_moc`, `proposed_moc_topic`).
- No new Kado reads, no new LLM passes (022 cost envelope holds).
- No cross-repo Kokoro ADR / Hashi handoff required — 023 changes no component interaction or wire shape (contrast with 022 T7.2); it is Tomo-internal. The live walk (Phase 4) merely exercises the unchanged Hashi `line`/`after` shape.

**Implementation Context**:
```bash
# Testing (system python3 lacks jsonschema — MUST use venv)
./venv/bin/python -m pytest tests/                              # full suite (~840 pass baseline; 8 known ide_bridge fails)
./venv/bin/python -m pytest tests/test_spec022_schema_additions.py
./venv/bin/python -m pytest tests/test_moc_structure_inventory.py   # has_footer at cache build
./venv/bin/python -m pytest tests/test_moc_insertion_resolution.py
./venv/bin/python -m pytest tests/test_suggestions_reducer_t6_1_placement.py

# Sync to instance (bump # version: first; run sandbox-off for .claude/{agents,commands})
./scripts/update-tomo.sh

# Host vs live Kado (validation walk)
KADO_URL=127.0.0.1:<port>/mcp + token from tomo-instance/.mcp.json   # sandbox off
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** → **Test** (red) → **Implement** (green) → **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Schema foundation](phase-1.md)
- [x] [Phase 2: Footer inventory](phase-2.md)
- [x] [Phase 3: Pass-1 confidence gate](phase-3.md)
- [x] [Phase 4: Surfacing & resolution](phase-4.md)
- [x] [Phase 5: Live walk + regression](phase-5.md)

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
| AC-1 emit fit_confidence on tier-1 | T1.1, T3.1 |
| AC-2 null/absent for tier-2/3/4 | T1.1, T3.1 |
| AC-3 strong vs weak distinguishable | T3.1, T5.1 |
| AC-4 ≥0.6 → tier-1 | T3.1 |
| AC-5 <0.6 → tier-2 + reject→alt_headings | T3.1 |
| AC-6 Japan-`Content` regression → new section | T3.1, T5.1 |
| AC-7 tier-2 #28 fires on real vault | T3.1, T5.1 |
| AC-8 footer → callout/before, render resolves text | T3.1, T4.2 |
| AC-9 no-footer → line/after, render resolves last line | T3.1, T4.2 |
| AC-9a analyst reads has_footer (Pass-1) | T2.1, T3.1 |
| AC-10 new section correct spacing | T4.2, T5.1 |
| AC-11 render confidence % | T4.1 |
| AC-12 absent → line unchanged (back-compat) | T1.1, T4.1 |
| AC-13 tier-2 destination shown (footer / end-of-MOC) | T4.1 |
| has_footer at cache build | T2.1 |
| Telemetry (confident vs rejected→tier2) | T4.2 |
| Bounds (reject <0 / >1) | T1.1 |

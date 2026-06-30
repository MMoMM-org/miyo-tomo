---
title: "Suggestions source-model unification — Implementation Plan"
status: completed
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

## Specification Compliance Guidelines

Reference SDD ADRs + PRD ACs in each task. Build to the confirmed design — do not redesign.

### Deviation Protocol
Document any deviation with rationale; obtain approval; update the SDD if the deviation improves
the design; record it here for traceability.

## Metadata Reference

- `[parallel: true]` — tasks that can run concurrently
- `[ref: document/section; lines: ...]` — specification links
- `[activity: type]` — specialist hint

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/027-suggestions-source-model/requirements.md` — Product Requirements (5 features, Gherkin ACs)
- `docs/XDD/specs/027-suggestions-source-model/solution.md` — Solution Design (5 ADRs, interfaces, runtime view)

**Key Design Decisions** (from SDD — build to these):
- **ADR-1**: Additive `audio_peer` companion field (not a `source_files[]` list) — additive on the hot path.
- **ADR-2**: `inbox-analyst` emits `audio_peer` by ADDING `source:` extraction — the key already exists in the transcript frontmatter it loads (written by `voice_render.py`), so it is a new extraction step, not a new Kado call.
- **ADR-3**: HARD CUTOVER wire rename `origin_inbox_item`→`source_inbox_item` in both schemas + bump `schema_version` `"1"`→`"2"`; Tomo+Hashi lockstep; Kokoro ADR + Hashi#41 handoff.
- **ADR-4**: Two-box per-item block (Approve + Keep source files); drop redundant Skip + per-atomic Delete box; voice source rendered as the {transcript + audio} set.
- **ADR-5**: Internal rename `keep_origin`→`keep_source` across parser/reducer/render/diff/tests.

**Implementation Context**:
```bash
# Tests (host-only — tests/ is NOT synced to the instance):
./venv/bin/python -m pytest tests/ -q                 # full suite (green baseline: 1782 passed, 1 skipped)
./venv/bin/python -m pytest tests/test-resolve-section-names.py tests/test_instruction_render_*.py -q
# Managed runtime scripts edited here MUST get a `# version:` bump (sync is version-gated).
# Schemas: tomo/schemas/{instructions,hashi-instructions}.schema.json
```

**Constraints**: deterministic scripts (no LLM); constitution L1 (authorize AND reject coverage
for every keep/delete path); propose-only (emit `delete_source` instructions, never delete); Tomo
never deletes; `_ensure_md_extension` must NOT be applied to the `.m4a` audio peer.

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** → **Test**
(red) → **Implement** (green) → **Validate** (refactor + verify).

Sequenced by dependency/risk: internal rename (foundation) → UX block → audio-peer behavior →
breaking wire rename (cross-repo, last).

- [x] [Phase 1: Internal keep_origin→keep_source rename](phase-1.md)
- [ ] [Phase 2: Two-box decision-block UX](phase-2.md)
- [ ] [Phase 3: Audio-peer plumbing & source-set deletion](phase-3.md)
- [ ] [Phase 4: Breaking wire rename, schema_version bump & cross-repo handoff](phase-4.md)

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

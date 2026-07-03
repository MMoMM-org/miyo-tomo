---
title: "F-05 — Topic Weighting in MOC Matching"
status: draft
version: "1.0"
---

# Implementation Plan

> Spec 029 · Issue #124 · Epic #17 · Track MVP-Polish
> PRD: `../requirements.md` · SDD: `../solution.md`

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

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale.
2. Obtain approval before proceeding.
3. Update SDD when the deviation improves the design.
4. Record deviations in the relevant phase file for traceability.

## Metadata Reference

- `[parallel: true]` — Tasks that can run concurrently
- `[ref: document/section; lines: X-Y]` — Links to specifications
- `[activity: type]` — Activity hint for specialist selection

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/029-topic-weighting-moc-matching/requirements.md` — Product Requirements
- `docs/XDD/specs/029-topic-weighting-moc-matching/solution.md` — Solution Design (ADRs, interfaces, traced walkthrough)
- `docs/XDD/ideas/2026-07-03-f05-topic-weighting-moc-matching.md` — Source design (reference)

**Key Design Decisions**:
- **ADR-1** Approach B — weight a topic ×2 when its normalized form is a substring of the note's normalized title.
- **ADR-2** New module `tomo/scripts/lib/topic_match.py` (do NOT edit `lib/topic_signature.py`).
- **ADR-3** Ruzicka `Σmin/Σmax`, missing-side=0; exact flat-reduction only when no topic is title-derived on either side.
- **ADR-4** Two substrates: Site 1 exact min/max; Site 2 (analyst) simplified "count double if title-derived on either side" (Option A) — decision-equivalent, not numerically identical.
- **ADR-5** Keep `JACCARD_DUP_THRESHOLD = 0.80`; validate in-scope via `analyze-placement-confidence.py`; re-tune only on misseparation.

**Must-Preserve Invariants**:
- Squelch signature byte-identical (`compute_topic_signature` stays flat — never touched).
- `JACCARD_DUP_THRESHOLD = 0.80` value; exact-title short-circuit; first-match early-return.
- Analyst `≥ 0.15` keep-gate, `top 3` cap, `+0.1` non-classification depth bonus.
- No cache schema change, no version bump to the cache.

**Implementation Context**:
```bash
# Testing (venv — system python3 lacks jsonschema)
./venv/bin/python -m pytest tests/ -q

# Quality
./venv/bin/ruff check tomo/scripts scripts

# Threshold validation (Phase 3, ADR-5) — run against personal vault
./venv/bin/python scripts/analyze-placement-confidence.py

# Deploy edited managed files into the running instance (bump `# version` first)
scripts/update-tomo.sh
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** → **Test** (red) → **Implement** (green) → **Validate** (refactor + verify).

- [x] [Phase 1: Core Weighted-Overlap Scorer](phase-1.md)
- [ ] [Phase 2: Both-Site Integration](phase-2.md)
- [ ] [Phase 3: Validation & Threshold Tuning](phase-3.md)

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

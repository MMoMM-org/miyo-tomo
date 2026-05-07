---
title: "F-43 — Proactive MOC-Creation Skill (`/moc-propose`)"
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
| specId | 013-moc-creation-skill |
| title | F-43 — Proactive MOC-Creation Skill (`/moc-propose`) |
| status | DRAFT |
| phases | 6 |
| totalTasks | 30 |
| parallelTasks | 9 |
| specReferences | 60+ inline `[ref: ...]` annotations |
| clarificationsRemaining | 0 |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate (read the Phase Context section).
2. **During Implementation**: Reference specific SDD sections in each task via `[ref: ...]`.
3. **After Each Task**: Run Specification Compliance checks per the Validate step.
4. **Phase Completion**: Verify all PRD AC mapped to that phase pass.

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with rationale in the relevant phase file.
2. Obtain approval before proceeding.
3. Update SDD when the deviation improves the design.
4. Record all deviations in this plan for traceability.

## Metadata Reference

- `[parallel: true]` — Tasks that can run concurrently
- `[component: tomo|hashi]` — For multi-component features (Hashi handoff is the only cross-repo task)
- `[ref: doc/section; lines: X-Y]` — Links to specifications
- `[activity: type]` — Activity hint for specialist agent selection

### Success Criteria

**Validate** = process verification ("did we follow TDD?").
**Success** = outcome verification ("does it work correctly?").

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/013-moc-creation-skill/requirements.md` — PRD (8 features, 35 Gherkin AC)
- `docs/XDD/specs/013-moc-creation-skill/solution.md` — SDD (9 ADRs, 18 EARS criteria)
- `docs/XDD/ideas/2026-05-06-moc-creation-skill.md` — original brainstorm with full architecture rationale
- `docs/XDD/specs/012-force-atomic-synthesis/solution.md` — XDD-012 FAN-resolve precedent (proposal-companion-doc + parser-extension pattern)
- `docs/XDD/reference/tier-3/lyt-moc/new-moc-proposal.md` — title patterns, duplicate-detection thresholds
- `docs/XDD/reference/tier-3/lyt-moc/moc-matching.md` — scoring algorithm reused for parent resolution
- `~/Kouzou/projects/miyo/miyo-constitution.md` — L1/L2 governance rules (Privacy, Performance, Operations)

**Key Design Decisions** (from SDD):

- **ADR-1**: Render-time Kado read for existing-`up::` extraction — `supporting_items` stays a flat string; renderer queries Kado per accepted child.
- **ADR-3**: Hashi destination-collision guard is a NEW Hashi requirement — F-43 launch gated on Hashi delivery (cross-repo handoff via `_outbox/for-hashi/`).
- **ADR-4**: Proposal-doc shape matches existing live render — `### MOCxx — <Title>` + `- [ ] Accept` list-item form (not `## 🔍` heading-checkbox).
- **ADR-5**: `tomo_skip_inbox_analysis` filter at Step 2b post-Kado-read in `inbox-analyst` (not Step 0).
- **ADR-8**: Squelch state = sidecar `tomo-instance/state/moc-squelch.json` keyed by topic-signature.
- **ADR-9**: `### Why this proposal` narrative = template-rendered structured fields (no LLM call).

**Implementation Context**:

```bash
# Testing
pytest tests/ -v                         # unit tests
pytest tests/test_moc_*.py -v            # F-43 unit tests
pytest tests/test_suggestion_parser_moc_branch.py -v   # F-43 parser tests

# Quality
ruff check tomo/scripts/                 # lint
python3 -c "import ast; ast.parse(open('tomo/scripts/moc-discovery.py').read())"  # syntax sanity

# Tomo lifecycle
./scripts/update-tomo.sh                 # sync tomo/ → tomo-instance/
./tomo-instance/begin-tomo.sh            # launch Tomo container
# inside container: /moc-propose tag:topic/applied/zsh

# Cross-repo handoff
ls _outbox/for-hashi/                    # outgoing handoff queue
```

**Branch convention**: All F-43 work happens on a feature branch (per Constitution L1 Operations); suggested name `feat/013-moc-creation-skill`. Direct main commits are blocked except for `_outbox/` files (per repo `.gitignore` exemption).

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Cross-Repo Handoff & Foundation](phase-1.md)
- [ ] [Phase 2: Discovery Script `moc-discovery.py`](phase-2.md)
- [ ] [Phase 3: Producer Surface — Reducer Extension, Agent, Command](phase-3.md)
- [ ] [Phase 4: Pass-2 Consumer Extensions](phase-4.md)
- [ ] [Phase 5: Squelch Lifecycle Wiring](phase-5.md)
- [ ] [Phase 6: Integration, Live Validation & Docs](phase-6.md)

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
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |

## Phase-to-AC Coverage Map

| PRD AC | Phase / Task |
|--------|--------------|
| AC-1.x (multi-mode CLI) | T2.1, T2.2, T3.3 |
| AC-2.x (profile-aware) | T2.5 |
| AC-3.x (proposal-doc shape) | T3.1, T3.2 |
| AC-3 abort paths (cache, caps, zero) | T2.2, T2.3 |
| AC-4.x (up:: preservation, Rule 4.1-4.6) | T4.2 |
| AC-5.x (skip-flag + parser dispatch) | T4.1, T4.3 |
| AC-6.x (Hashi collision guard) | T1.1 |
| AC-7.x (config thresholds) | T1.2 |
| AC-8.x (squelch behaviour) | T5.1, T5.2 |
| Integration / Live / Release | T6.1, T6.2, T6.3 |

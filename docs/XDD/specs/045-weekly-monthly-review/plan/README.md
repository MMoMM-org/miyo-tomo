---
title: "/review: weekly and monthly reviews the user edits before they land"
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
- `[activity: type]` - Activity hint for specialist selection
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

- `docs/XDD/specs/045-weekly-monthly-review/requirements.md` - Product Requirements (v1.2, 59 criteria)
- `docs/XDD/specs/045-weekly-monthly-review/solution.md` - Solution Design (v1.0, ADR-1..12)
- `docs/XDD/specs/044-note-from-template/solution.md` - the precedent this design copies
- `docs/tomo/scripts/note-instructions.md` - WHY of the deliver loop extracted in T1.3
- `CLAUDE.md` - runtime-file rules, eval gate, version bumps

**Key Design Decisions**:

- **ADR-1**: shim + skill + scripts like `/note`; the model writes only `proposals.json` (ADR-12).
- **ADR-2**: open state lives in the vault (inbox document + instruction set); `tomo-tmp/review/<stem>/` holds only content-free `meta.json` across sessions.
- **ADR-3**: review section at the place's heading level with marker `%% tomo-review <period> %%`; insert first, `replace_section` on rerun; risky line starts escaped.
- **ADR-4**: paced and retried Kado reads (`ReviewPacer`, `KadoRateLimitError`, client counters).
- **ADR-7**: week rule `(first_day, min_days_in_first_week)` inferred from notes or asked; never from the Obsidian config.
- **ADR-10/11**: `/inbox` skips `doc_type: review` by the ` Review` filename suffix; `/note`'s deliver loop moves to `lib/staged_delivery.py` with caller-supplied steps.
- **ADR-13**: Tomo items carry `%%t<n>%%` ids; `drop` withdraws a set Tomo already wrote.

**Standing rules for every task**:

- Never edit the eval-gated files (`agents/synthesis-conductor.md`, `agents/suggestion-conductor.md`, `skills/suggest-handling/SKILL.md`, `commands/inbox.md`, `dot_claude/settings.json`) or `tomo/schemas/hashi-instructions.schema.json`.
- WHY goes into `docs/tomo/<mirrored path>.md` before the runtime file changes; runtime prose holds imperatives only.
- Bump `# version:` on every edited managed file; every new script and lib starts with a header docstring saying why it exists and `# version: 0.1.0`; edit skills via `tcs-helper:skill-author`.
- Every script catches unexpected exceptions at the top and prints only the class name to stderr.
- New libs stay one responsibility each (≤ ~500 lines); in the large existing files add only the changes named here.
- Commits and the PR reference spec 045 and #31.
- Stage explicit paths only; never `git stash/reset/restore/clean/checkout`; never a `CLAUDE_ALLOW_*` override; report hook denials.
- Unique temp and commit-message file names per agent; mutation checks only in an isolated copy, with `PYTHONDONTWRITEBYTECODE=1`.
- The test vault is read-only; never write into its daily folder; never touch `tomo-privat`; paid evals and instance syncs only on the owner's instruction.

**Implementation Context**:

```bash
# Testing (host, under the repo venv)
./venv/bin/python -m pytest tests/ -q                       # full suite
./venv/bin/python -m pytest tests/test_review_*.py tests/test_period.py tests/test_staged_delivery.py -q
./venv/bin/python -m pytest -m integration tests/test_review_integration.py   # opt-in, reads Privat-Test

# Quality
./venv/bin/ruff check tomo/scripts scripts tests

# Full validation
./venv/bin/python -m pytest tests/ -q && ./venv/bin/ruff check tomo/scripts scripts tests

# Owner-instructed only
scripts/update-tomo.sh --instance tomo-instance --yolo     # sync for the live walk
scripts/run-evals.sh --case <review case>                  # paid, optional (not eval-gated)
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Shared foundations](phase-1.md)
- [x] [Phase 2: Setup and session start](phase-2.md)
- [x] [Phase 3: Reading the period and the review document](phase-3.md)
- [x] [Phase 4: Delivery and open-review state](phase-4.md)
- [ ] [Phase 5: Command, skill and documentation](phase-5.md)
- [ ] [Phase 6: Integration, live walk and close-out](phase-6.md)

Phase dependencies: 1 → 2 → 3 → 4 → 5 → 6. T2.1 and T2.2 may start once T1.1 is done; T3.5 (habits) may start once T2.1 is done (marked in the phase files).

---

## Plan Verification

Before this plan is ready for implementation, verify:

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ (traceability table in phase-6.md) |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |

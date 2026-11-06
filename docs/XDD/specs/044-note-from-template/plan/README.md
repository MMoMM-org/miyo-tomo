---
title: "/note: notes from a template, with follow-up questions"
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

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/044-note-from-template/requirements.md` - Product Requirements (F1-F9, 52 criteria)
- `docs/XDD/specs/044-note-from-template/solution.md` - Solution Design (components, interfaces, ADR-1 to ADR-8, F1-AC1 … F9-AC2)
- `docs/XDD/specs/044-note-from-template/research.md` - Evidence for every reuse claim
- `docs/XDD/ideas/2026-11-02-note-from-template.md` - Owner-approved brainstorm

**Key Design Decisions**:

- **ADR-2**: One delivery script - `note-instructions.py deliver` writes note, JSON and MD and marks the source in one process with the `kado-write-file.py` exit contract.
- **ADR-4**: `lib/template_syntax.py` - one parser for outline points and filled-note checks.
- **ADR-5**: `templates-include` writer subcommand - edits only the `note_include` lines inside `templates:`.
- **ADR-6**: `note-session.py` - session start is a script, not prose branching.
- **ADR-7**: Stage directory per stem - `tomo-tmp/note/<stem>/` holds the draft state, owned through `lib/note_meta.py`.

**Implementation Context**:

```bash
# Testing (host, never touches ~/.tomo)
./venv/bin/python -m pytest tests/ -q --deselect tests/ide_bridge/test_configure_ide_bridge.py::test_install_smoke_ide_bridge_block_exists

# Quality
./venv/bin/ruff check tomo/scripts tests

# Mutation proofs: only in an isolated copy (git archive into a temp dir), with PYTHONDONTWRITEBYTECODE=1

# Paid eval: owner's explicit instruction only, bare command from the repo root, in background
scripts/run-evals.sh --keep-temp
```

**Repo rules every task follows**: never edit on `main`; stage explicit paths; commit after each task; bump `# version:` on every managed file; write the `docs/tomo/` WHY before the runtime text; edit skills through `tcs-helper:skill-author`; no `git stash`, `reset`, `restore`, `clean`; never touch `tomo-privat`.

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Prerequisite and shared libraries](phase-1.md)
- [x] [Phase 2: Scripts](phase-2.md)
- [x] [Phase 3: Runtime prose and documentation](phase-3.md)
- [ ] [Phase 4: Eval, live walk and close-out](phase-4.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ (traceability table below) |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |

### Traceability

| Criteria | Tasks |
|---|---|
| F1-AC1, F1-AC2 | T2.3 (preview data), T3.2 (prose), T4.2 (live) |
| F1-AC3, F1-AC4, F1-AC5 | T1.4, T3.2, T4.2 |
| F1-AC6 | T2.3 |
| F2-AC1, F2-AC2, F2-AC3 | T2.3, T3.2, T4.2 |
| F2-AC4 | T1.1, T2.3, T3.2, T3.4 |
| F3-AC1 | T1.2, T2.1 |
| F3-AC2 … F3-AC6, F3-AC8 | T3.2, T4.1, T4.2 |
| F3-AC7 | T1.2, T2.2, T2.6 |
| F4-AC1 … F4-AC4 | T2.5, T3.2, T4.1, T4.2 |
| F4-AC5 | T4.5, T4.2 |
| F5-AC1 … F5-AC4, F5-AC6, F5-AC7 | T2.5, T2.6 |
| F5-AC5 | T2.6 (triage interplay) |
| F5-AC8 | T2.7 |
| F6-AC1 … F6-AC6 | T1.3, T2.3, T2.5, T2.6, T3.2 |
| F7-AC1 … F7-AC5, F7-AC8 … F7-AC11 | T1.3, T2.4, T3.2, T4.2 |
| F7-AC6, F7-AC7 | T3.2, T4.2 |
| F7-AC12 | T2.7 |
| F8-AC1, F8-AC2 | T1.1, T3.3 |
| F9-AC1 | T3.4 |
| F9-AC2 | T2.6 |

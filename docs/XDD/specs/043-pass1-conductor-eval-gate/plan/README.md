---
title: "Eval gate for the Pass 1 conductor"
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

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/043-pass1-conductor-eval-gate/requirements.md`: Product Requirements (F1–F7, 31 criteria).
- `docs/XDD/specs/043-pass1-conductor-eval-gate/solution.md`: Solution Design (ADR-1–6, the grader tables, Complex Logic).
- `docs/XDD/specs/043-pass1-conductor-eval-gate/spike/write-up.md`: measured behaviour on `claude` 2.1.314.
- `evals/README.md` and `evals/_mutations/README.md`: the gate's rules and its RED-proof discipline.

**Key Design Decisions**:

- **ADR-1**: The runner copies `evals/_lib/inbox-analyst.stub.md` over `agents/inbox-analyst.md` in the assembled copy, after `--rev` and before `--mutation`. The real file is never read.
- **ADR-2 and ADR-3**: The new kit `evals/_lib/pass1-stubs.sh` (`stage_pass1_instance`) serves two cases that differ only in `SHARED_CTX_WARN` and `DUPLICATES`.
- **ADR-4**: The shared `report-only.md` and `handback-canary.md` read the hand-back frame and are byte-identical in the 4 standard Pass 2 cases. `audit-mismatch-stops` gets its own pattern.
- **ADR-5**: Ordering rules that `tool_order` cannot see are graded as ordered trace regexes, anchored on the event shape (the trace contains the prose itself).
- **ADR-6**: The kit stages `suggestion-conductor.md` from the assembled copy, so that `--rev` and `--mutation` reach the impersonated conductor.

**Implementation Context**:

```bash
# Testing (host, sandbox OK)
./venv/bin/python -m pytest tests/test_run_evals.py tests/test_eval_gate_docs.py tests/test_pass1_stub_kit.py tests/test_043_grader_patterns.py -q
./venv/bin/python -m pytest -q                      # full suite before each phase gate

# Quality
shellcheck scripts/run-evals.sh evals/_lib/*.sh
for f in evals/*/scaffold.sh; do (cd "$(dirname "$f")" && shellcheck -x scaffold.sh); done   # -x: the case variables are read by the sourced kit
./venv/bin/ruff check tests/

# Paid gate runs (owner, terminal only: the sandbox gives EPERM; never while files change)
scripts/run-evals.sh --case 'pass1-*' --runs 1      # smoke
scripts/run-evals.sh --mutation <name> --case <case>  # RED proof, 3 runs
scripts/run-evals.sh                                 # full suite: the merge evidence
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Stand-ins and runner swap](phase-1.md)
- [x] [Phase 2: Cases, shared graders and offline validation](phase-2.md)
- [ ] [Phase 3: Paid green runs and findings](phase-3.md)
- [ ] [Phase 4: RED proofs, documentation and merge evidence](phase-4.md)

Phases 1 and 2 cost nothing (pytest and offline regex checks). Phases 3 and 4 need paid runs, which the owner starts from a terminal. Expected spend: about $2–4 in Phase 3 and about $11–13 in Phase 4. The Phase 4 figure comes from about 16 mutations × 3 runs × $0.22 plus 3 full suites at about $3.

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ (traceability table in phase-4.md, T4.4) |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |

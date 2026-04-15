# Implementation Plan — 004-Inbox Fan-Out Refactor

## Overview

Five phases, mostly sequential. Phase 4 (daily-note tracker) is layered on top
of a working core (Phases 1-3) so the refactor can be validated with atomic
notes alone before adding tracker logic.

## Phases

| Phase | Title | Depends on | Status |
|-------|-------|-----------|--------|
| 1 | Scaffolding: scripts, schemas, agent shells | - | pending |
| 2 | Phase A (shared-ctx + state-file) | 1 | pending |
| 3 | Phase B fan-out + Phase C reducer (atomic-note only) | 2 | pending |
| 4 | Daily-note tracker actions | 3 | pending |
| 5 | Validation + migration (retire `suggestion-builder`) | 4 | pending |

## Ordering Rationale

- **Phase 1** lays concrete artifacts (schemas, empty agents, empty scripts)
  so subsequent phases have TDD targets and stable contracts.
- **Phase 2** is orchestrator-facing only — the shared-ctx and state-file
  must be producible and verifiable before any fan-out can run.
- **Phase 3** proves the end-to-end loop with the simplest action kind
  (`create_atomic_note`). Validates concurrency, error handling, resumability.
- **Phase 4** extends `actions[]` polymorphism to `update_daily`. Low risk once
  Phase 3 is stable.
- **Phase 5** deletes the old `suggestion-builder` agent, updates docs, runs
  a full integration test on the user's real inbox.

## Success Gate per Phase

Each phase lists acceptance tests at its top. A phase is `done` when:

1. All acceptance tests pass
2. `test-kado.py` still passes (no regressions)
3. User runs the documented manual smoke check and approves

---
*Files: `phase-1.md` through `phase-5.md`. Each phase is self-contained and
lists tasks, tests, and hand-off criteria.*

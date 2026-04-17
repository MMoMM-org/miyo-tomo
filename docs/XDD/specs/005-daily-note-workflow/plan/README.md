# Implementation Plan — 005-Daily Note Workflow Extension

## Overview

Five phases, mostly sequential. Extension of Spec 004's fan-out — no
architectural rewrite. Core changes land in: schema + shared-ctx +
subagent + reducer + wizard.

## Phases

- [x] [Phase 1: Schema + config](phase-1.md) — polymorphic updates[], vault-config extensions, templates regen
- [x] [Phase 2: Shared-ctx extension](phase-2.md) — tracker descriptions + daily_log block
- [x] [Phase 3: Three-way classification](phase-3.md) — inbox-analyst Step 8b rewrite, log-format heuristic, multi-daily, cutoff
- [x] [Phase 4: Reducer + render](phase-4.md) — top-of-doc Daily Notes Updates block + per-item Material mirror
- [x] [Phase 5: Wizards + Pass-2 + validation](phase-5.md) — `/tomo-setup` sub-wizards, log_entry/log_link handlers, real-vault validation

## Dependencies

| Phase | Depends on |
|-------|------------|
| 1 | — |
| 2 | 1 |
| 3 | 1, 2 |
| 4 | 1, 3 |
| 5 | 1–4 |

## Success Gate per Phase

Each phase is done when:

1. Its acceptance tests pass (each phase ships its own `test-005-phase<N>.sh`).
2. Spec-004 regression tests still pass (`test-004-phase{2,3,4}.sh`).
3. Real-inbox dry run produces reasonable output (user-visible check).

---
*Files: `phase-1.md` through `phase-5.md`. Each phase self-contained.*

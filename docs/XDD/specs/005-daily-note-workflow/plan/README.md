# Implementation Plan — 005-Daily Note Workflow Extension

## Overview

Five phases, mostly sequential. Extension of Spec 004's fan-out — no
architectural rewrite. Core changes land in: schema + shared-ctx +
subagent + reducer + wizard.

## Phases

| Phase | Title | Depends on | Status |
|-------|-------|-----------|--------|
| 1 | Schema + config: polymorphic updates[], vault-config extensions, templates regen | - | pending |
| 2 | shared-ctx-builder extension (tracker descriptions + daily_log) | 1 | pending |
| 3 | inbox-analyst Step 8b rewrite (three-way classification, log-format heuristic, multi-daily, cutoff) | 1, 2 | pending |
| 4 | suggestions-reducer top-of-doc Daily Notes Updates block + per-item Material mirror | 1, 3 | pending |
| 5 | /tomo-setup sub-wizards (tomo-trackers-wizard + tomo-daily-log-wizard) + Pass-2 handlers for log_entry/log_link + end-to-end validation | 1-4 | pending |

## Success Gate per Phase

Each phase is `done` when:
1. Its acceptance tests pass (each phase ships its own `test-005-phase<N>.sh`).
2. Spec-004 regression tests still pass (`test-004-phase{2,3,4}.sh`).
3. Real-inbox dry run produces reasonable output (user-visible check).

---
*Files: `phase-1.md` through `phase-5.md`. Each phase self-contained.*

---
title: "Phase 3: Finalize + document"
status: complete
version: "1.0"
phase: 3
---

# Phase 3: Finalize + document

## Phase Context

Close out the spec — retroactive SDD + plan, reference docs updated,
backlog cross-references, deferred items captured for future work.

## Tasks

- [x] **T3.1 Retrospective SDD** `[activity: docs]` — **DONE 2026-04-21**

  `solution.md` written by reverse-engineering the shipped scripts.
  Archive layout, script contracts, design decisions, known limits.

- [x] **T3.2 Plan backfill** `[activity: docs]` — **DONE 2026-04-21**

  Phase 1 + 2 retrospectively documented; this Phase 3 tracks
  finalization.

- [x] **T3.3 Backlog cross-reference** `[activity: docs]` — **DONE 2026-04-21**

  Backlog `F-29` updated to reflect MVP shipped (backup + restore);
  install-time warning (F3 in requirements) stays open as F-29b or a
  follow-up if needed.

- [ ] **T3.4 README / user-facing docs** `[activity: docs]` — **DEFERRED**

  Root README mention of `scripts/backup-tomo.sh` and `restore-tomo.sh`
  in the "Recovery" section. Low urgency — `--help` text covers most
  questions. Re-open if users ask how to back up.

- [x] **T3.5 Spec status flip** `[activity: docs]` — **DONE 2026-04-21**

  README Current Phase = DONE, completion summary added.

- [x] **T3.6 Phase Validation** `[activity: validate]` — **DONE 2026-04-21**

  - Scripts match requirements (F1, F2 Must-Have). ✓
  - Solution.md reflects shipped behavior. ✓
  - Deferred items (F3 install warning, F8 archive verify, T3.4 README)
    tracked in backlog / spec notes. ✓
  - Spec directory complete: requirements + solution + plan tree. ✓

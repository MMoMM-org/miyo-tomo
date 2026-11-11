---
title: "Phase 6: Integration, live walk and close-out"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Integration, live walk and close-out

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Acceptance Criteria; lines: 984-1045]`
- `[ref: SDD/Quality Requirements; lines: 977-983]`
- `[ref: PRD/Success Metrics]`
- `docs/XDD/specs/044-note-from-template/close-out.md` (close-out format)

**Key Decisions**:
- The close-out traces every PRD criterion to node ids executed in ONE pytest invocation; a part no test can fail is closed by a RED-proven test, not by argument.
- The live walk uses `tomo-instance` and the test vault's March 2026 only, after an owner-instructed sync; nothing is written into the daily folder.

**Dependencies**:
- Phases 1–5.

---

## Tasks

This phase proves the whole flow end to end and closes the spec.

- [ ] **T6.1 End-to-end on the fake vault** `[activity: test]`

  1. Prime: `[ref: SDD/Runtime View]`
  2. Test: `tests/test_review_e2e.py` — week: start → setup confirm → read → proposals fixture → write → user edits (untick, rewrite, add, tick Approved) → parse → preview → deliver → Hashi-style apply simulated (applied flags) → next start reports applied; month with weekly notes; rerun replaces the section; target created between passes; delivery failure at each step then resume; abort before and after Pass 2 leaves the vault outside the inbox unchanged.
  3. Implement: the test and any glue fixes in the owning scripts.
  4. Validate: green.
  5. Success: the 2-pass flow works without an AI in the loop `[ref: PRD/Secondary User Journeys 1-7; PRD/KPI Quality]`

- [ ] **T6.2 Integration read of the test vault** `[activity: test]`

  1. Prime: existing `-m integration` tests; memory "host scripts can hit live Kado" and "Kado 429 is per IP"
  2. Test: `tests/test_review_integration.py` (`-m integration`) — `review-read.py` for 2026-W13 and 2026-03 against Privat-Test through Kado: every March daily found, tomorrow's planner not read, earlier 5J years not read, weekly notes W09..W13 found (W14 absent), call counts within the SDD limits, no write performed.
  3. Implement: the test.
  4. Validate: green when run by the owner with Kado up.
  5. Success: the reader works on the owner's real note shapes `[ref: PRD/Assumptions; SDD/Quality Requirements]`

- [ ] **T6.3 Live walk on `tomo-instance`** `[activity: validate]` `[model: routine]`

  1. Prime: memory "sync before any live walk", "restart Claude after agent/skill sync", "cost log after every live run"
  2. Test: after the owner's go: `scripts/update-tomo.sh --instance tomo-instance --yolo`, grep the instance for the new files; the owner runs `/review setup`, `/review 2026-W13`, edits, `/review`, applies in Hashi; then `/review 2026-03`. Record per run: cost, duration, calls, retried, waited, kept/unticked/deleted/added counts (no text).
  3. Implement: nothing in code; results into `docs/XDD/specs/045-weekly-monthly-review/live-walk.md` and the cost log.
  4. Validate: transcript lines quoted with session ids; no journal text quoted.
  5. Success: weekly Pass 1 ≤ $0.50, monthly Pass 1 ≤ $2.00 and ≤ 5 min, Pass 2 ≤ $0.20; ≤ 40 % of Tomo items unticked or deleted; 0 writes outside the inbox before apply `[ref: PRD/KPIs]`

- [ ] **T6.4 Close-out** `[activity: validate]`

  1. Prime: spec 044 close-out
  2. Test: map all 59 PRD criteria to node ids; run them in ONE pytest invocation; list model-behaviour criteria evidenced only by the live walk; find parts no test can fail and close them with RED-proven tests in `tests/test_045_close_out_gaps.py`.
  3. Implement: `docs/XDD/specs/045-weekly-monthly-review/close-out.md`; README Finalize; memory index entry under Critical Documentation.
  4. Validate: the single pytest invocation green; ruff clean.
  5. Success: every criterion is traced or named as open `[ref: PRD/all features]`

## PRD Traceability

| PRD criteria | Tasks |
|---|---|
| F1-AC1 | T2.2, T5.2 |
| F1-AC2 | T2.3, T2.1 |
| F1-AC3, AC4, AC5 | T1.1, T2.2 |
| F1-AC6 (week question) | T2.2, T5.2 |
| F1-AC7 (template) | T2.2, T5.2 |
| F1-AC8 (correct, re-show) | T2.2 |
| F1-AC9, AC10 | T2.1 |
| F2-AC1 | T2.3, T4.3 |
| F2-AC2..AC7, AC9 | T1.1, T2.3 |
| F2-AC8 | T2.3, T5.2 |
| F3-AC1..AC4 | T3.2 |
| F3-AC5, AC6, AC7 | T3.3 |
| F3-AC8, AC9 | T3.2, T3.4 |
| F3-AC10, AC11, AC12 | T1.2, T3.1, T3.4 |
| F3-AC13 | T3.4, T3.6 |
| F4-AC1..AC5, AC7 | T3.6, T4.1 |
| F4-AC6 | T1.4, T1.6 |
| F5-AC1, AC6 | T3.7, T4.2 |
| F5-AC2 | T4.2, T5.2 |
| F5-AC3, AC4, AC5, AC7 | T4.1 |
| F5-AC8 | T1.4, T4.2 |
| F5-AC9 | T1.5, T4.2 |
| F5-AC10 | T1.3, T4.2, T4.3 |
| F5-AC11 | T4.2 |
| F6-AC1 | T3.7 |
| F6-AC2 | T4.2, T4.3 |
| F6-AC3 | T1.4, T4.1 |
| F6-AC4 | T4.2, T4.3 |
| F7-AC1 | T5.4 |
| F7-AC2 | T5.3 |
| F8-AC1..AC3 | T3.5 |
| KPIs | T6.3 |

- [ ] **T6.5 Phase Validation** `[activity: validate]`

  - Full suite and ruff green; close-out committed; README phase set by Finalize.

---
title: "Phase 6: Integration, live walk and close-out"
status: in_progress
version: "1.1"
phase: 6
---

# Phase 6: Integration, live walk and close-out

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Acceptance Criteria]`
- `[ref: SDD/Quality Requirements]`
- `[ref: PRD/Success Metrics]`
- `docs/XDD/specs/044-note-from-template/close-out.md` (close-out format)

**Key Decisions**:
- The close-out traces every PRD criterion to node ids executed in ONE pytest invocation; a part no test can fail is closed by a RED-proven test, not by argument.
- Criteria that rest on model behaviour are named up front: F1-AC6 (asking the week question in plain words), F4-AC5 (proposal language), F4-AC7 (no reflection text inside Tomo's groups), F5-AC2 (the plain-text Deliver/Abort turn); they are evidenced by the live walk and the optional eval.
- The live walk uses `tomo-instance` and the test vault's March 2026 only, after an owner-instructed sync; nothing is written into the daily folder; KPIs are measured on an otherwise idle Kado.

**Dependencies**:
- Phases 1–5.

---

## Tasks

This phase proves the whole flow end to end and closes the spec.

- [x] **T6.1 End-to-end on the fake vault** `[activity: test]`

  1. Prime: `[ref: SDD/Runtime View]`
  2. Test: `tests/test_review_e2e.py` — week: start → setup confirm → read → proposals fixture → write → user edits (untick, rewrite without links, add, tick Approved) → parse → preview → deliver → Hashi-style apply simulated (applied flags) → next start reports applied; setup abort writes nothing; month with weekly notes; rerun replaces the section, also under a renamed heading; target created between passes; target moved to another folder; delivery failure at each step then resume; drop after a partial delivery leaves only a withdrawn set; abort before and after Pass 2 leaves the vault outside the inbox unchanged; every fake-vault write across the whole test lands under the inbox prefix.
  3. Implement: the test and any glue fixes in the owning scripts.
  4. Validate: green.
  5. Success: the 2-pass flow works without an AI in the loop `[ref: PRD/Secondary User Journeys 1-7; PRD/Edge Cases; PRD/KPI Quality; PRD/F1-AC10]`

- [x] **T6.2 Integration read of the test vault** `[activity: test]`

  1. Prime: existing `-m integration` tests; memory "host scripts can hit live Kado" and "Kado 429 is per IP"
  2. Test: `tests/test_review_integration.py` (`-m integration`) — `review-read.py` for 2026-W13 and 2026-03 against Privat-Test through Kado: every March daily found, the same-day Dayplanner read, tomorrow's planner not read, earlier 5J years not read, weekly notes W09..W13 found (W14 absent), call counts within the SDD limits, no write performed.
  3. Implement: the test.
  4. Validate: green when run by the owner with Kado up.
  5. Success: the reader works on the owner's real note shapes `[ref: PRD/Assumptions; SDD/Quality Requirements]`

- [x] **T6.3 Live walk on `tomo-instance`** `[activity: validate]` `[model: routine]`

  Exceptions recorded in close-out §5/§7: F1-AC6 and F4-AC7 not reachable on the test vault, `88773c67` and `586277fa` not re-walked, cold-session weekly Pass 1 not measured.

  1. Prime: memory "sync before any live walk", "restart Claude after agent/skill sync", "cost log after every live run"
  2. Test: after the owner's go: `scripts/update-tomo.sh --instance tomo-instance --yolo`, grep the instance for the new files; the owner runs `/review setup`, `/review 2026-W13`, edits, `/review`, applies in Hashi; then `/review 2026-03`. Record per run: cost, duration, calls, retried, waited, kept/unticked/deleted/added counts (no text), and the model-behaviour criteria named above.
  3. Implement: nothing in code; results into `docs/XDD/specs/045-weekly-monthly-review/live-walk.md` and the cost log.
  4. Validate: transcript lines quoted with session ids; no journal text quoted.
  5. Success: weekly Pass 1 ≤ $0.50, monthly Pass 1 ≤ $2.00 and ≤ 7 min, Pass 2 ≤ $0.75; ≤ 40 % of Tomo items unticked or deleted over the review (habits excluded); 0 writes outside the inbox before apply `[ref: PRD/KPIs; PRD/F1-AC6, F4-AC5, F4-AC7, F5-AC2]`

- [ ] **T6.4 Close-out** `[activity: validate]`

  1. Prime: spec 044 close-out
  2. Test: map all 59 PRD criteria to node ids; run them in ONE pytest invocation; list the model-behaviour criteria with their live-walk evidence; find parts no test can fail and close them with RED-proven tests in `tests/test_045_close_out_gaps.py`.
  3. Implement: `docs/XDD/specs/045-weekly-monthly-review/close-out.md`; README Finalize; memory index entry under Critical Documentation; the PR references spec 045 and #31.
  4. Validate: the single pytest invocation green; ruff clean.
  5. Success: every criterion is traced or named as open `[ref: PRD/all features]`

## PRD Traceability

Each row lists the tasks whose Success line cites the criterion.

| PRD criteria | Tasks |
|---|---|
| F1-AC1 | T2.2, T5.2 |
| F1-AC2 | T2.1 |
| F1-AC3, AC4, AC5 | T1.1, T2.2 |
| F1-AC6 (week question) | T2.2, T5.2, T6.3 |
| F1-AC7 (template) | T2.2, T5.2 |
| F1-AC8 (correct, re-show) | T2.2 |
| F1-AC9 (save, continue) | T2.1, T5.2 |
| F1-AC10 (abort) | T2.1, T5.2, T6.1 |
| F2-AC1 | T2.3, T4.3, T5.2 |
| F2-AC2, AC3, AC4, AC5, AC6, AC7, AC9 | T1.1, T2.3 |
| F2-AC8 | T2.3, T5.2 |
| F3-AC1, AC2, AC3, AC4 | T3.2 |
| F3-AC5, AC6, AC7 | T3.3 |
| F3-AC8 | T3.2, T3.4 |
| F3-AC9 | T3.3, T3.4 |
| F3-AC10 | T1.2, T3.1, T3.4 |
| F3-AC11 | T1.2, T3.1, T3.4 |
| F3-AC12 | T1.2, T3.1, T3.4, T5.2 |
| F3-AC13 | T3.4, T3.6 |
| F4-AC1, AC2, AC3, AC4 | T3.6 |
| F4-AC5 | T3.6, T6.3 |
| F4-AC6 | T1.4, T1.6 |
| F4-AC7 | T3.6, T4.1, T6.3 |
| F5-AC1 | T3.7, T4.2 |
| F5-AC2 | T4.2, T5.2, T6.3 |
| F5-AC3, AC5, AC7 | T4.1 |
| F5-AC4 | T1.6, T4.1 |
| F5-AC6 | T3.7, T4.1 |
| F5-AC8 | T1.4, T4.2 |
| F5-AC9 | T1.5, T4.2 |
| F5-AC10 | T1.3, T4.2, T4.3 |
| F5-AC11 | T4.2 |
| F6-AC1 | T3.7 |
| F6-AC2, AC4 | T4.2, T4.3 |
| F6-AC3 | T1.4, T4.1 |
| F7-AC1 | T5.4 |
| F7-AC2 | T5.3 |
| F8-AC1, AC2, AC3 | T3.5 |
| PRD Edge Cases | T3.7, T4.1, T6.1 |
| KPIs | T6.3 |

- [ ] **T6.5 Phase Validation** `[activity: validate]`

  - Full suite and ruff green; close-out committed; README phase set by Finalize.

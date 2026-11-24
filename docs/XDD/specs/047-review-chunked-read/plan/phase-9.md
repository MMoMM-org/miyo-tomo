---
title: "Phase 9: Live walk on the test instance and close-out"
status: pending
version: "1.0"
phase: 9
---

# Phase 9: Live walk on the test instance and close-out

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Success Metrics]` — hard conditions, quality KPI, cost and time guidance, tracking events
- `[ref: SDD/Quality Requirements; lines: 1232-1238]`
- `[ref: SDD/Deployment View; lines: 1053-1064]` — sync globs, `MAX_PARALLEL` from the walk, rollback
- `[ref: SDD/Risks and Technical Debt; lines: 1285-1296]` — 14–16 parallel foreground agents unproven; opus rates
- Spec 046 `close-out.md` and its T6.3 walk notes (method and the documents to compare with)

**Key Decisions**:
- Owner-orchestrated: every run, sync and paid eval happens only on the owner's go, announced first, reported at once. Live runs only on `tomo-instance` against the test vault; `tomo-privat` is never synced or touched; nothing edits the test vault directly (writes reach it only through Hashi's apply, done by the owner); the deliberate daily gap stays broken; records hold counts only, never journal text.
- A fresh container session per run (a reused, compacted session answered from stale memory in the spec 046 walk); the session is restarted after every sync.
- Cost and time are guidance (CON-7, F8-AC2): an overrun is recorded, never a blocker. Hard: 0 days not read because of size, 0 sample or grep fallbacks, 0 main-session reads of stage files.

**Dependencies**: Phase 8. T9.1 → T9.2 → T9.3 → T9.4 → T9.5.

---

## Tasks

Runs the new flow on the test vault, measures it per step, fixes what the walk finds, and closes the spec with its evidence.

- [ ] **T9.1 Sync and pre-walk checks (owner go)** `[activity: validate]`

  1. Prime: memory notes on update-tomo (version-gated, syncs the checked-out branch, `--yolo`), restart after sync, test vault path and plugins (update-time-on-edit, Templater on create) `[ref: SDD/Deployment View; lines: 1060]`
  2. Test, owner-gated steps:
     1. `scripts/update-tomo.sh --instance tomo-instance --yolo` on the feature branch; confirm the three agents, `review-digest.py`, the new libs and the two schemas reached the instance (the orphan `review_read_parts.py` is expected and harmless).
     2. Restart the Tomo container session.
     3. Assumption check from the read report of a `--measure` run: notes for 2026-W12 and 2026-02 exist, 2025-Q4 does not (PRD Assumptions).
     4. Optional, on the owner's go (paid): `scripts/run-evals.sh --case review-no-stage-read`; record verdict, cost and results path.
  3. Implement: record outcomes under this task.
  4. Validate: instance versions match the branch; `tomo-privat` untouched.
  5. Success: the instance runs the branch and the walk's assumptions hold `[ref: PRD/Assumptions]`

- [ ] **T9.2 Live walk runs (owner-orchestrated)** `[activity: validate]`

  1. Prime: T9.1; spec 046 walk documents for W13, 2026-03 and 2026-Q1 (for the owner's comparison); `scripts/tomo-session-stats.py` (T7.3) `[ref: PRD/Success Metrics]` `[ref: SDD/Quality Requirements]`
  2. Test, each run in a fresh session, Pass 1 and Pass 2, cost per step recorded right after it:
     - R1 week 2026-W13 — previous W12 and 2026-02 found; carried items with marks; deliver and Hashi apply (owner).
     - R2 month 2026-03 — 2026-02 found, 2025-Q4 "no note found"; 6 units in one round.
     - R3 quarter 2026-Q1 — 14 digesters in one message; 90/90 days, 0 not read for size, no grep fallback; 2025-Q4 "no note found"; deliver and Hashi apply (owner).
     - R4 previous-note case 2026-W14 — crosses the month edge (reads 2026-W13 and 2026-02); one carried item ticked, one edited, one unticked; Pass 2 delivers them as left; the "Review delivered" counts per mark.
     - R5 resume case 2026-03 — the owner ends the session after the round is sent; the rerun says "Continuing the read made at …", dispatches only the jobs not passed, and writes the document.
     Walk rows (counts only) record per run: days read / not read by cause, units dispatched per message, agents self-started (must be 0), main-session Reads on stage files (must be 0), retries, not-condensed units, carried items per mark and per place (section / group), carried items placed twice and without a previous-note link (must be 0), content files left after write / abort / drop (must be 0), and the model-behaviour rows for F1-AC3, F1-AC4, F1-AC5, F4-AC1, F4-AC2, F4-AC3, F4-AC4, F4-AC8, F4-AC11 (what the owner saw, yes/no per criterion, no text).
  3. Implement: `docs/XDD/specs/047-review-chunked-read/live-walk.md` with the walk rows and this KPI table, filled from `tomo-session-stats.py` per step (cost at `tomo-token-usage.py`'s rates, a second column at current list prices if they differ):

     | KPI | Limit | Kind | R1 | R2 | R3 | R4 | R5 |
     |---|---|---|---|---|---|---|---|
     | Days not read because of size | 0 | hard | | | | | |
     | Sample / grep fallbacks | 0 | hard | | | | | |
     | Main-session reads of stage files | 0 | hard | | | | | |
     | Carried items placed twice / without previous link | 0 / 0 | quality | | | | | |
     | Content files left after write, abort, drop | 0 | quality | | | | | |
     | Weekly Pass 1 cost | ≤ $0.80 | guidance | | — | — | | — |
     | Monthly Pass 1 cost / time | ≤ $2.00 / 7 min | guidance | — | | — | — | |
     | Quarterly Pass 1 cost / time | ≤ $5.00 / 20 min | guidance | — | — | | — | — |
     | Pass 2 cost | ≤ $0.85 | guidance | | | | | |
     | Cost, time, peak context per step (main, digesters, carryover, proposer) | recorded | F8-AC1 | | | | | |
     | Owner: at least as useful as the spec 046 document | yes/no | quality | | | | — | — |

  4. Validate: every hard row 0; if parallel dispatch throttled at 14–16, record it (the fix is T9.3).
  5. Success: Tomo reads every day of week, month and quarter and follows up the previous reviews in the test vault `[ref: PRD/Success Metrics; F8-AC1]`
  - **Carry-over from the T5.6 trace (2026-11-24, orchestrator):** walk once each: a carried item the days also hold appears once (F4-AC6); a full section's carried items merge only with items of their own mark (F4-AC10); a best fit off limits lands in the next section or the group (F4-AC5).

- [ ] **T9.3 Walk-found fixes** `[activity: backend-api]`

  1. Prime: `live-walk.md` findings `[ref: SDD/Deployment View; lines: 1055]` `[ref: SDD/Error Handling; lines: 962]`
  2. Test: each finding becomes a task with a RED test first (proven by reverting the fix); throttling at 16 → `MAX_PARALLEL = 8` (constant only, `test_plan_rounds` updated, skill text unchanged); a size limit too tight → constants only, brought to the owner first; a runtime-prose fix → WHY doc first, version bump, re-pinned contract test.
  3. Implement: the fixes; re-sync and re-run only the affected run, on the owner's go.
  4. Validate: full suite green after each fix; no eval-gated file changed (if one must, the full eval suite runs before merge, CLAUDE.md eval gate).
  5. Success: every walk finding is fixed with a regression test or recorded with the owner's decision `[ref: PRD/Risks and Mitigations]`

- [ ] **T9.4 Close-out** `[activity: validate]`

  1. Prime: spec 046 and 045 `close-out.md` (method), the cost log reference, this plan's criteria → task map `[ref: PRD all criteria]` `[ref: SDD/Quality Requirements/Reliability; lines: 1238]`
  2. Test: every one of the 56 PRD criteria traced to node ids executed in ONE pytest invocation, or to a recorded live-walk row for model behaviour (the † criteria of the map); criteria parts no test can fail closed by RED-proven tests in `tests/test_047_close_out_gaps.py`; every cost and time overrun of T9.2 reported with its number, blocking nothing (F8-AC2); the inbox cost log updated.
  3. Implement: `docs/XDD/specs/047-review-chunked-read/close-out.md`; spec README Decisions Log and status; the memory index Critical Documentation entry (`docs/ai/memory/memory.md`); `docs/XDD/backlog.md` for open items; an optional FYI to Kokoro in `_outbox/for-kokoro/` (previous-review follow-up as a review behaviour; no contract change).
  4. Validate: drift check spec vs code once more; the PR carries the spec ID 047, #270 and the close-out link; no eval-gated file in the branch diff.
  5. Success: the spec closes with its evidence and its overruns named `[ref: PRD/F8-AC2; all criteria]`

- [ ] **T9.5 Phase Validation** `[activity: validate]`

  - Full suite in ONE invocation — GREEN; ruff clean; wire gate green. The close-out trace covers 56/56 criteria. All README phase checkboxes and this phase's tasks ticked; push the branch (at least every 10 commits throughout); merge only after the owner's review.

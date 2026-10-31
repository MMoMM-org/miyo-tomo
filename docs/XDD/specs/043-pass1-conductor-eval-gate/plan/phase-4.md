---
title: "Phase 4: RED proofs, documentation and merge evidence"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: RED proofs, documentation and merge evidence

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Features 5, 6, 7]`
- `[ref: SDD/Acceptance Criteria; Gate (PRD F5–F7)]`
- `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/red-proofs.md`: the format of a RED-proof record.
- `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/close-out.md`: the close-out trace format.

**Key Decisions**:
- A RED proof is 3 runs of the single affected case under one mutation. A self-reported "confirmed RED" proves nothing; only a recorded verdict counts.
- A mutation that turns several graders red covers all of them. A grader it fails to turn red needs its own mutation.
- Evidence lines are copied from tool output, never edited.

**Dependencies**:
- Phase 3 complete: one full-suite GREEN on the final prose. Any later prose edit invalidates proofs that touch the edited file, and those must be re-run.

---

## Tasks

This phase proves the gate can fail, documents it, and produces the merge evidence.

- [x] **T4.1 RED proofs** `[activity: validate]`

  1. Prime: the mutation table in `evals/_mutations/README.md` (T2.5).
  2. Test (owner), for each mutation: `scripts/run-evals.sh --mutation <name> --case <case> --keep-temp`, 3 runs (owner decision 2026-10-31: 3/3 stays). The expected total is about $12 for T4.1.
     - 15 Pass 1 mutations at about $0.62 each.
     - `status-sentence-first` on `upload-failure-reported` and on `audit-mismatch-stops`, to prove the shared grader and the mismatch variant.
     - Re-prove the five 041 patches rebased onto conductor 0.24.2 (`summarise-mismatch`, `files-used-after`, `explain-failure`, `report-run-id`, `paraphrase-relay`) on their recorded cases; record them beside their 041 rows.
  3. Implement: record each proof in `docs/XDD/specs/043-pass1-conductor-eval-gate/red-proofs.md`: the mutation, the case, the grader(s) expected red, the 3 verdict lines copied verbatim, and the results path.
     - When a grader stays green under its mutation, choose one of two fixes: strengthen the mutation (a neutral step for "never" graders), or reclassify the grader as a control. Either fix needs the owner's approval and is recorded.
  4. Validate: every non-control grader in both Pass 1 cases and both report-only variants appears red 3/3 in the record.
  5. Success: `[ref: PRD/F5-AC1, F5-AC2, F5-AC3, F5-AC4; PRD/F4-AC2]`

- [x] **T4.2 Documentation and gate rule** `[activity: docs]` `[parallel: true]`

  1. Prime: `evals/README.md`, root `CLAUDE.md` (the eval gate rule), `tests/test_eval_gate_docs.py`.
  2. Test: extend `tests/test_eval_gate_docs.py`:
     - the coverage table lists `tomo/dot_claude/agents/suggestion-conductor.md` and `tomo/dot_claude/skills/suggest-handling/SKILL.md` with both Pass 1 cases;
     - the `inbox.md` and `settings.json` rows list all 7 cases;
     - the CLAUDE.md gate rule names the Pass 1 files.
     Each assertion is RED-proven by reverting it in a scratch copy.
  3. Implement:
     - `evals/README.md`:
       - the coverage table;
       - "Adding a case": the Pass 1 kit variables, the stand-in agent, and anchoring on the event shape;
       - the cost section, with the measured figures from T3.3;
       - Known limits: background dispatch and several result frames, the trace-format dependency with the `claude` version it was validated on, the analyst not covered, the batch wait not graded, the HHMM source not graded;
       - Known gaps: remove the "no grader checks that the reply is only the report" item.
     - Root `CLAUDE.md`: the gate rule names the Pass 1 files.
     - `docs/ai/memory/memory.md`: a Critical Documentation entry for the close-out.
  4. Validate: the docs tests pass.
  5. Success: `[ref: PRD/F6-AC1, F6-AC2; PRD/F7-AC1]`

- [x] **T4.3 Merge evidence: 3× full-suite GREEN** `[activity: validate]`

  1. Prime: the merge rule.
  2. Test (owner): `scripts/run-evals.sh` 3 times on the merge candidate, with a clean tree and no edits between runs.
  3. Implement: record the 3 verdict lines, the median cost and the maximum duration in `red-proofs.md` and in the PR body.
  4. Validate: all 3 runs are GREEN; the median cost is ≤ $3.10 and each run is under $5; the maximum duration is ≤ 7 min (owner decision 2026-10-31, raised from 6 min after the first merge evidence measured 373–416 s).
  5. Success: `[ref: PRD/F6-AC3, F6-AC4; PRD KPIs]`

- [ ] **T4.4 Close-out trace** `[activity: validate]`

  1. Prime: the 041 close-out format; memory: "prove a test is RED by reverting the fix", "never truncate a coverage grep".
  2. Test: map each of the 31 PRD criteria to one of the following:
     - a pytest node id, all executed in ONE pytest invocation;
     - a gate grader, with its RED-proof row;
     - a recorded run (T4.3).
     Any criterion with no evidence that could fail is a gap.
  3. Implement: `docs/XDD/specs/043-pass1-conductor-eval-gate/close-out.md` with the trace table, the gaps and how each was closed (by a RED-proven test or proof, or by an owner decision).
  4. Validate: no criterion is left unmapped; the pytest run command and its output are copied verbatim.
  5. Success: every PRD criterion is evidenced `[ref: PRD/all]`

- [ ] **T4.5 Phase Validation** `[activity: validate]`

  - Run the full pytest suite, ruff and shellcheck.
  - Finalize the spec through `xdd-meta`.
  - Open the PR with the verdict lines, the cost and the results paths. Merge only on the owner's explicit "merge".

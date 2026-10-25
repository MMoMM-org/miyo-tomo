---
title: "Phase 5: Close-out"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Close-out

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Success Metrics]`, `[ref: PRD/F7-AC6]`
- `[ref: SDD/Acceptance Criteria]` — all 35
- `[ref: SDD/Quality Requirements]`
- Prior close-outs for the format: `docs/XDD/specs/040-relevant-mocs-per-item/close-out.md`
- memory: "Never truncate a coverage grep", "Count parity ≠ correctness"

**Key Decisions**:
- The close-out traces every PRD criterion to a test node id or a recorded run, executed in **one** pytest invocation plus the recorded eval runs — not to a task.
- The three consecutive GREEN runs are the final gate; a single RED among them restarts the count after investigation.

**Dependencies**: Phase 4.

---

## Tasks

Proves the spec end to end and records the evidence.

- [x] **T5.1 Three consecutive full-suite GREEN runs on the merge candidate** `[activity: validate]`

  1. Prime: `red-proofs.md`, `baseline.md` `[ref: PRD/F7-AC6]`
  2. Test: three `scripts/run-evals.sh` invocations, no arguments, on the branch head that will merge, clean tree (verdict says `tree clean`); any later commit to a covered file restarts the count
  3. Implement: append the three verdict lines, cost and duration to `baseline.md` under "close-out"
  4. Validate: 3/3 GREEN; median cost ≤ $2, each ≤ 5 min `[ref: PRD/KPIs Business Impact; SDD/Quality Requirements]`
  5. Success: the gate is green and stable on the code that will merge `[ref: PRD/F7-AC6]`

- [ ] **T5.2 Close-out document** `[activity: documentation]`

  1. Prime: all PRD criteria; `tests/test_eval_*.py`, `tests/test_run_evals.py`; `red-proofs.md`; `baseline.md` `[ref: SDD/Acceptance Criteria]`
  2. Test: one `./venv/bin/python -m pytest <every node id cited>` invocation, all green; every PRD criterion row cites node ids or a recorded run; every gate grader row cites its proof and its red verdict; controls marked; open items (stub drift, hand-listed guard names, stale `tomo/skills/` mention in root `CLAUDE.md`) named
  3. Implement: `docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/close-out.md`; `docs/ai/memory/memory.md` Critical Documentation line; comment on #174 with the summary and the close-out path
  4. Validate: full pytest green; ruff clean; `scripts/run-evals.sh --help` matches the docs
  5. Success: 35/35 PRD criteria traced to executed evidence `[ref: SDD/Acceptance Criteria]`

- [ ] **T5.3 Phase Validation** `[activity: validate]`

  - Full pytest green; ruff clean; the PR description carries the latest full-suite verdict line (the gate's own rule applies to this PR, since it changes `synthesis-conductor.md`).

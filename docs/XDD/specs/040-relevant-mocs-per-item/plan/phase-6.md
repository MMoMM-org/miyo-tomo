---
title: "Phase 6: Integration and live validation"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Integration and live validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Quality Requirements]`
- `[ref: PRD/Success Metrics; KPIs, Tracking Requirements]`
- `[ref: docs/XDD/specs/040-relevant-mocs-per-item/baseline.md]` (from T1.1)

**Key Decisions**:
- Quality is agreement with the baseline runs on the identical inbox set (owner decision); the bar accounts for the variance measured between the two before-runs.

**Dependencies**: Phases 1–5.

---

## Tasks

Proves the whole flow end to end, at today's size and at 512 MOCs, then on the test instance against the baseline.

- [ ] **T6.1 End-to-end test: build → read → reducer** `[activity: test-strategy]`

  1. Prime: `tests/integration/test_moc_propose_e2e.py:1377-1449`; `tests/integration/test_016_multi_topic_e2e.py` `[ref: SDD/Runtime View]`
  2. Test: from a fixture cache, build the context, read names, fetch a nominated subset, feed a hand-made item result that proposes an existing MOC name into the reducer, and assert the rendered doc and C3 wire show the unticked existing MOC and no Proposed MOC; update `test_moc_propose_e2e.py:1449` (it asserted every cache MOC appears in `shared_ctx["mocs"]`) to "every *eligible* MOC", with the reason
  3. Implement: the integration test
  4. Validate: green in the full suite
  5. Success: the components agree on one contract `[ref: SDD/Building Block View]`

- [ ] **T6.2 Scale test at 512 MOCs** `[activity: test-strategy]` `[parallel: true]`

  1. Prime: #173 reproduction method; `[ref: SDD/Quality Requirements; Performance, Fidelity]`
  2. Test: synthetic 512-MOC cache (test-instance MOCs duplicated with distinct paths); `--moc-names` ≤ 12 KB; a 20-name `--mocs-from` ≤ 30 KB; Step-1 batch unchanged in size; no MOC loses headings or callouts; size guards silent at these sizes
  3. Implement: the test (pytest, deterministic)
  4. Validate: green
  5. Success: `[ref: PRD/F1-AC6, F2-AC2]`

- [ ] **T6.3 After-run on the test instance** `[activity: validate]`

  1. Prime: `baseline.md`; memory notes "update-tomo is version-gated", "restart Claude after agent/skill sync", "reset tomo-tmp before a live run"
  2. Test: n/a (measurement). Checklist: `./scripts/update-tomo.sh --instance tomo-instance --yolo`; grep the instance for the new versions of every touched file; restart; reset pass-1 state; restore the archived inbox set; run `/inbox`; capture the same fields as T1.1
  3. Implement: owner runs; results appended to `baseline.md` and the cost log
  4. Validate: both runs logged with run ids
  5. Success: after-picture captured on the identical set

- [ ] **T6.4 Close-out** `[activity: validate]`

  1. Prime: PRD KPIs; `baseline.md`; recent close-outs (spec 038/039) for the format
  2. Test: every PRD acceptance criterion traced to a node id executed in ONE pytest invocation, or to the live run; KPIs evaluated: candidate agreement ≥ 90% (adjusted for measured before-run variance, stated explicitly), zero duplicate proposals, zero spilled MOC reads, cache-write/item ≥ 10% lower, $/item ≤ 0.603; every candidate difference listed with a reason
  3. Implement: `docs/XDD/specs/040-relevant-mocs-per-item/close-out.md`; README phase → Implemented via xdd-meta Finalize; add to memory's Critical Documentation
  4. Validate: full suite + ruff in the same session as the trace
  5. Success: the spec closes on evidence, not on task ticks `[ref: PRD/Success Metrics]`

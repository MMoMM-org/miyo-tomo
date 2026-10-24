---
title: "Phase 6: Integration and live validation"
status: pending
version: "1.1"
phase: 6
---

# Phase 6: Integration and live validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Quality Requirements]`
- `[ref: PRD/Success Metrics; KPIs, How each criterion is verified, Tracking Requirements]`
- `[ref: docs/XDD/specs/040-relevant-mocs-per-item/baseline.md]` (from T1.2)

**Key Decisions**:
- Agreement = share of before-run candidate paths (per-item union over all actions) that appear in the after-run's union for the same item; bar = min(90%, agreement between the two before-runs).
- Per-item details stay in `tomo-instance/spec-040-baseline/` (gitignored); git gets figures only.

**Dependencies**: Phases 1–5.

---

## Tasks

Proves the whole flow end to end, at today's size and at 512 MOCs, then on the test instance against the baseline.

- [ ] **T6.1 End-to-end test: build → read → reducer → render** `[activity: test-strategy]`

  1. Prime: `tests/integration/test_moc_propose_e2e.py:1377-1469`; `tests/integration/test_016_multi_topic_e2e.py` `[ref: SDD/Runtime View]`
  2. Test (RED — `--moc-names` and the conversion do not exist on `main`): from a fixture cache that **includes an excluded MOC**, build the context, read names (the excluded MOC is absent), fetch a nominated subset, feed a hand-made item result that proposes an existing MOC name into the reducer, render, and assert the doc and the C3 wire show the unticked existing MOC and no Proposed MOC; update `test_moc_propose_e2e.py:1449-1454` to "every *eligible* MOC, and the excluded one absent" and `:1462-1469` to `placeholder_targets == ["Search MOC"]`, each with the reason
  3. Implement: the integration test and the two updates
  4. Validate: green in the full suite
  5. Success: the components agree on one contract `[ref: SDD/Building Block View]`

- [ ] **T6.2 Scale test at 512 MOCs** `[activity: test-strategy]` `[parallel: true]`

  1. Prime: #173 reproduction method; `[ref: SDD/Quality Requirements; Performance, Fidelity]`
  2. Test: synthetic 512-MOC cache (test-instance MOCs duplicated with distinct paths); `--moc-names` ≤ 12 KB; a 20-name `--mocs-from` ≤ 30 KB; Step-1 batch unchanged in size; no MOC loses headings or callouts; size guards silent at these sizes; a variant with 60-character titles triggers the names WARN
  3. Implement: the test (pytest, deterministic)
  4. Validate: green
  5. Success: `[ref: PRD/F1-AC6, F2-AC2]`

- [ ] **T6.3 After-run on the test instance** `[activity: validate]`

  1. Prime: `baseline.md`; memory notes "update-tomo is version-gated", "restart Claude after agent/skill sync", "reset tomo-tmp before a live run"
  2. Test: n/a (measurement). Checklist: `./scripts/update-tomo.sh --instance tomo-instance --yolo`; grep the instance for the new versions of every touched file; restart; reset pass-1 state; restore `tomo-instance/spec-040-baseline/inbox-set/`; run `/inbox`; capture the same fields as T1.2 including the T1.1 scanner output; check the seeded item links the existing MOC instead of proposing it (F3-AC1) and that every analyst read the names (F1-AC1)
  3. Implement: owner runs; details to `tomo-instance/spec-040-baseline/after.json`; figures to `baseline.md` and the cost log
  4. Validate: all three runs logged with run ids
  5. Success: after-picture captured on the identical set `[ref: PRD/F1-AC1, F3-AC1]`

- [ ] **T6.4 Close-out** `[activity: validate]`

  1. Prime: PRD KPIs and "How each criterion is verified"; `baseline.md`; spec 038/039 close-outs for the format
  2. Test: every PRD acceptance criterion traced to a node id executed in ONE pytest invocation, to a prose-contract test, or to the live run, per the PRD's verification table; KPIs evaluated with the agreement definition above, zero duplicate proposals, zero previews (scanner), cache-write/item ≥ 10% lower, $/item ≤ 0.603; every candidate difference listed with a reason (paths named only in the gitignored detail file; the close-out cites counts and item numbers)
  3. Implement: `docs/XDD/specs/040-relevant-mocs-per-item/close-out.md`; README phase → Implemented via xdd-meta Finalize; add to memory's Critical Documentation
  4. Validate: full suite + ruff in the same session as the trace
  5. Success: the spec closes on evidence, not on task ticks `[ref: PRD/Success Metrics]`

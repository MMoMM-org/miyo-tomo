---
title: "Phase 6: Integration, E2E, cost & docs"
status: in_progress
version: "1.0"
phase: 6
---

# Phase 6: Integration, E2E, cost & docs

## Phase Context

**GATE**: Read the referenced files before starting. Requires Phases 1–5 complete.

**Specification References**:
- `[ref: PRD/A10 (8 test cases), A11; §7 Success signals; §11 Validation hooks]`
- `[ref: SDD/Quality Requirements; Acceptance Criteria (EARS)]`

**Key Decisions**:
- A10 enumerates the 8 E2E cases (below). A11: tier-3 inbox-analysis multi-topic section + WHY mirrors for every runtime file touched.
- Cost regression measured vs the F-32 baseline (≤+10%).

**Dependencies**: Phases 1–5 (full pipeline).

---

## Tasks

Proves the whole pipeline end-to-end on real multi-thread input and locks the docs.

- [x] **T6.1 End-to-end multi-topic suite (A10)** `[activity: integration-test]`

  1. Prime: Read PRD A10 cases + §7 Apothekerpfädchen success signal; existing E2E harness (`tests/integration/`) `[ref: PRD/A10, §7]`
  2. Test (RED) — one E2E per A10 case, analyst→reducer→parser→render:
     - single-thread → 1 atomic (no regression) · 2-thread → 2 atomics · 5-thread → 5 atomics (stress)
     - sub-worthy multi-thread → no atomics, 1 `update_daily` · mixed-worthiness → 1 atomic + summary daily
     - voice multi-thread → 2 atomics + audio reference per thread
     - FAN-ticked multi-thread → resolve doc 2 proposals
     - overlapping topics → MOC matches deduped per atomic `[ref: PRD/A10]`
  3. Implement (GREEN): wire fixtures (incl. the Apothekerpfädchen 11 voice memo) through the real pipeline.
  4. Validate: full `./venv/bin/python -m pytest`; the Apothekerpfädchen case yields 1 daily + 1 atomic, both linked to source `[ref: PRD/§7]`
  5. Success: all 8 A10 cases green `[ref: PRD/A10]`; Apothekerpfädchen resolved `[ref: PRD/§10, context.md #19]`

- [ ] **T6.2 Cost regression vs F-32 baseline** `[activity: performance-test]`

  1. Prime: Read the F-32 cost-measurement tool (`scripts/measure-f47-token-cost.py`) + auto-memory token-cost note `[ref: PRD/§7, CON-3]`
  2. Test (RED): 20-item mixed single+multi batch → main-thread cost tracked vs F-32 baseline.
  3. Implement (GREEN): run the measured batch; confirm the >200w gate keeps short items prompt-free.
  4. Validate: cost increase ≤10% `[ref: PRD/CON-3, §10]`
  5. Success: Pass-1 cost within +10% `[ref: PRD/§7]`

- [ ] **T6.3 Documentation (A11)** `[activity: documentation]`

  1. Prime: Read tier-3 `reference/tier-3/inbox/inbox-analysis.md`; WHY-mirror convention (CLAUDE.md) `[ref: PRD/A11]`
  2. Implement: add a multi-topic section to the tier-3 spec (when segmentation fires, output shape); write/update WHY-mirrors under `docs/tomo/` for every runtime file touched (analyst, reducer, parser, render); mark backlog F-41 + GH #32 code-complete.
  3. Validate: docs cross-reference XDD 016; no stale single-atomic claims remain (`rg`).
  4. Success: tier-3 updated, WHY-mirrors complete `[ref: PRD/A11]`

- [ ] **T6.4 Final validation & single-thread sign-off** `[activity: validate]`

  Full suite green; single-thread output byte-identical to pre-feature (diff a pre/post run); lint clean; all A1–A11 satisfied; cost gate met. Finalize spec to Implemented via xdd-meta.

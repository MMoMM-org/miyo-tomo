---
title: "Phase 3: Reducer N-block rendering (C1, C2)"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Reducer N-block rendering (C1, C2)

## Phase Context

**GATE**: Read the referenced files before starting.

**Specification References**:
- `[ref: SDD/Reducer contract change; The six silent-collapse points — C1, C2]`
- `[ref: PRD/A4, §8 OQ5]`

**Key Decisions**:
- C1 (`suggestions-reducer.py:144`): `_enforce_coexistence` must iterate ALL `create_atomic_note` actions, not `next()`-fetch the first; atomic-vs-`log_entry` coexistence evaluated per-atomic.
- C2 (`:1047-1050`): `section_titles` keyed per-atomic (list or `(section_id, idx)`) so N titles survive into `_enrich_proposed_mocs`.
- OQ5: render N independent Accept blocks, `**Source:** [[stem]]` visible in each; single per-source heading is acceptable.

**Dependencies**: Phase 2 (analyst emits N atomics). `[parallel: true]` with Phase 4 and Phase 5 (independent files).

---

## Tasks

Delivers N independently-reviewable atomic Accept blocks from one source — no silent collapse.

- [ ] **T3.1 Coexistence + title handling for N atomics (C1, C2)** `[activity: backend-logic]` `[parallel: true]`

  1. Prime: Read `_enforce_coexistence` (`:120-169`), main action loop (`:948-1073`), `_enrich_proposed_mocs` (`:328-344`) `[ref: SDD/C1, C2]`
  2. Test (RED):
     - item with 2 atomics + 1 `update_daily(log_entry)` → coexistence applied to BOTH atomics, not just the first `[ref: SDD/C1]`
     - 2 atomics with distinct topics → both titles survive in `section_titles` / proposed-MOC enrichment `[ref: SDD/C2]`
     - single-thread item → output byte-identical to today `[ref: PRD/CON-2]`
  3. Implement (GREEN): replace `next(...)` with iteration; key `section_titles` per-atomic.
  4. Validate: `./venv/bin/python -m pytest tests/ -k reducer`; lint.
  5. Success: N atomics survive coexistence + titling `[ref: PRD/A4]`; single-thread unchanged `[ref: PRD/CON-2]`

- [ ] **T3.2 N independent Accept blocks** `[activity: backend-logic]` `[parallel: true]`

  1. Prime: Read `render_create_atomic_note` (`:172-240`), section assembly (`:1068-1073`) `[ref: SDD/Reducer contract change]`
  2. Test (RED): 2-atomic source → 2 Accept blocks under one section, each with its own `**Decision (atomic note):**` checkboxes + `**Source:** [[stem]]`; blocks scannable for N≤3 `[ref: PRD/A4, OQ5]`
  3. Implement (GREEN): ensure the per-source `actions[]` list renders each atomic as a self-contained block (the list already supports it — verify no dedup/overwrite upstream of render).
  4. Validate: snapshot test of a 2-atomic suggestions doc; lint.
  5. Success: N blocks, independently approvable `[ref: PRD/A4]`

- [ ] **T3.3 Phase Validation** `[activity: validate]`

  Run reducer tests incl. single-thread regression; bump `# version:`; lint.

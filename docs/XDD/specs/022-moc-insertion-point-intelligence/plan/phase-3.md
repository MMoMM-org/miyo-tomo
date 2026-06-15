---
title: "Phase 3: Inventory producers"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Inventory producers

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: solution.md/Building Block View]` — moc-tree-builder + shared-ctx-builder
- `[ref: solution.md/ADR-2]` — A-trimmed cost strategy
- `[ref: research-synthesis.md/Cost]` — measured 63 MOCs, avg 4.2 headings

**Key Decisions**:
- ADR-4: parse at the existing `raw_by_path` body-read site → ZERO new Kado calls.
- ADR-2: A-trimmed — headings-only, cap ~8/MOC, skip Dewey/classification MOCs; `enforce_budget`
  drops inventory before topics under pressure.

**Dependencies**: Phase 1 (`lib/moc_structure.py`), Phase 2 (T2.2 schema). Must follow both.

---

## Tasks

Produces the per-MOC heading/callout inventory and lands it in shared-ctx within budget.

- [ ] **T3.1 moc-tree-builder inventory** `[activity: backend]`

  1. Prime: Read the body-read + cache-entry build `[ref: moc-tree-builder.py; lines: 290-323]` and the existing read site `raw_by_path` (`:292`).
  2. Test (red): given a MOC body, the cache entry gains `headings:[{text,level}]` + `editable_callouts:[string]` via `moc_structure`; non-MOC notes unaffected; no extra Kado call issued (assert read count unchanged).
  3. Implement (green): call `moc_structure.parse_headings` / `parse_editable_callouts` on `raw_by_path[path]`; write both into the structure-cache entry. Pass `FOOTER_CALLOUTS` + `callouts.editable` as params. Bump `# version:`.
  4. Validate: builder tests pass; cache schema bump consistent with F-34 scoped-cache shape `[ref: README/Decisions Log]`.
  5. Success: [ ] inventory present, zero new Kado reads `[ref: solution.md/ADR-4, CON-3]`

- [ ] **T3.2 shared-ctx-builder A-trimmed copy** `[activity: backend]`

  1. Prime: Read `build_mocs` + the `enforce_budget` trim-pass pattern `[ref: shared-ctx-builder.py; lines: 210-227, 561-612]`.
  2. Test (red):
     - `mocs[]` entries gain `headings` (headings-only) + `editable_callouts`, capped at ~8 headings/MOC.
     - Dewey/classification MOCs (`is_classification`) carry NO inventory (skipped).
     - Under `--max-bytes` pressure, `enforce_budget` drops inventory BEFORE topics.
  3. Implement (green): copy trimmed inventory from cache into `mocs[]`; add the cap + Dewey-skip; extend `enforce_budget` to drop `headings`/`editable_callouts` first.
  4. Validate: builder tests pass; assert shared-ctx delta ≤ 8192 bytes on the 63-MOC fixture (≈7 KB design estimate) `[ref: research-synthesis.md/Cost]`. Bump `# version:`.
  5. Success:
     - [ ] inventory trimmed + capped + Dewey-skipped `[ref: solution.md/ADR-2]`
     - [ ] budget trim drops inventory first `[ref: solution.md/Error Handling]`

- [ ] **T3.3 Phase Validation** `[activity: validate]`

  - Run builder test suites. Confirm shared-ctx total stays within budget and no classification MOC carries inventory.

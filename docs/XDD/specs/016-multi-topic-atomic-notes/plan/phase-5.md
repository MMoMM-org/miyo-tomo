---
title: "Phase 5: Render N notes + delete gate (C5, C6)"
status: completed
version: "1.0"
phase: 5
---

# Phase 5: Render N notes + delete gate (C5, C6)

## Phase Context

**GATE**: Read the referenced files before starting.

**Specification References**:
- `[ref: SDD/Render contract change; Complex Logic — paired-delete completion gate; collapse points C5, C6]`
- `[ref: SDD/ADR-6 delete gate; ADR-7 collision guard]` · `[ref: PRD/A6, A9, §8 OQ6]`

**Key Decisions**:
- C5 (`instruction-render.py:1738`): per-source filename collision guard — when N atomics slugify to one filename, append stable `_NN` in action order; error loudly if still colliding (never silent-overwrite at `:1741`).
- C6 (`:933-952`): replace `paired_seen`-after-first dedup with a per-origin completion gate — emit one `delete_source` only after ALL move_notes for that origin are present AND any accepted `update_daily` for that stem is represented (OQ6).

**Dependencies**: Phase 2 (analyst contract). `[parallel: true]` with Phase 3 and Phase 4.

---

## Tasks

Delivers N distinct rendered notes and a source-deletion that fires only after every derived thread is captured.

- [x] **T5.1 Filename collision guard (C5)** `[activity: backend-logic]` `[parallel: true]`

  1. Prime: Read atomic render loop (`:1650-1772`), filename derivation (`:1738-1741`), manifest append (`:1743-1766`) `[ref: SDD/C5, ADR-7]`
  2. Test (RED):
     - 2 atomics from one source with DISTINCT titles → 2 distinct files (no suffix needed) `[ref: PRD/A6]`
     - 2 atomics with IDENTICAL slugified titles → `_01` / `_02` suffix, both written, no overwrite `[ref: SDD/ADR-7]`
     - unresolvable collision → loud error, not silent overwrite `[ref: SDD/Error Handling]`
  3. Implement (GREEN): track rendered filenames per run; on collision append stable suffix; raise on exhaustion.
  4. Validate: `./venv/bin/python -m pytest tests/ -k render`; lint.
  5. Success: N distinct notes per source `[ref: PRD/A6]`

- [x] **T5.2 Source-deletion completion gate (C6)** `[activity: backend-logic]` `[parallel: true]`

  1. Prime: Read `_build_delete_source_actions` (`:866-954`), paired-delete (`:933-952`), build_actions order (`:1018-1066`) `[ref: SDD/C6, Complex Logic]`
  2. Test (RED):
     - source with 2 atomics → `delete_source` emitted only after BOTH move_notes present (not after first) `[ref: PRD/A9, OQ6]`
     - source with 2 atomics + 1 daily → delete only after both atomics AND the daily are represented `[ref: SDD/Complex Logic]`
     - `keep_origin` ticked → no delete (unchanged) `[ref: SDD/C6]`
     - single atomic → one delete after its move_note (regression) `[ref: PRD/CON-2]`
  3. Implement (GREEN): group move_notes by origin-stem; emit one delete keyed to the origin when `len(moves)==expected_atomics AND not daily_pending`; defer otherwise.
  4. Validate: render delete-gate tests; lint.
  5. Success: source preserved until all threads captured `[ref: PRD/§8 OQ6]`

- [x] **T5.3 Phase Validation** `[activity: validate]`

  Run render tests incl. single-thread delete regression; bump `# version:`; lint.

---
title: "Phase 1: Schema & source_stem contract"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Schema & source_stem contract

## Phase Context

**GATE**: Read the referenced files before starting.

**Specification References**:
- `[ref: SDD/Interface Specifications — Analyst output; Data Storage Changes]`
- `[ref: SDD/ADR-4 — explicit source_stem]` · `[ref: SDD/ADR-5 — no instructions.schema change]`
- `[ref: PRD/A3, A7]`

**Key Decisions**:
- ADR-4: every `create_atomic_note` carries `source_stem` (set for ALL items, not just multi-thread, for downstream uniformity — see SDD Gotchas).
- ADR-5: `item-result.schema.json` gains `source_stem`; `instructions.schema.json` is NOT touched (proven N≥2-capable).

**Dependencies**: none — this is the contract foundation for Phases 2–5.

---

## Tasks

Establishes the N≥1 atomic-action contract: an explicit provenance key and proven multi-atomic schema acceptance.

- [ ] **T1.1 `source_stem` provenance field** `[activity: data-architecture]`

  1. Prime: Read `tomo/schemas/item-result.schema.json` `create_atomic_note` def (`:50-104`) `[ref: SDD/Code Context]`
  2. Test (RED): a result with 2× `create_atomic_note` sharing one `source_stem` validates; a single-thread result with `source_stem` validates; an atomic missing `source_stem` fails once the field is required. (extend `tests/test_item_result_schema.py` or add one)
  3. Implement (GREEN): add `source_stem` (string) to the `create_atomic_note` `$defs`; document in the schema description that `actions[]` may carry ≥2 `create_atomic_note` from one source.
  4. Validate: `./venv/bin/python -m pytest tests/ -k item_result`; lint clean.
  5. Success:
     - [ ] schema accepts N≥2 atomics/source `[ref: PRD/A7]`
     - [ ] `source_stem` present + validated `[ref: PRD/A3]`
     - [ ] `instructions.schema.json` untouched `[ref: SDD/ADR-5]`

- [ ] **T1.2 Phase Validation** `[activity: validate]`

  Run Phase 1 tests; confirm `instructions.schema.json` unchanged (git diff); lint clean.

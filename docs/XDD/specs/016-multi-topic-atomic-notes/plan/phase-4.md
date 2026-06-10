---
title: "Phase 4: Parser N-entry parsing (C3, C4)"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Parser N-entry parsing (C3, C4)

## Phase Context

**GATE**: Read the referenced files before starting.

**Specification References**:
- `[ref: SDD/Parser contract change; collapse points C3, C4]`
- `[ref: SDD/ADR-8 — dict→dict[list]]` · `[ref: PRD/A5, A8]`

**Key Decisions**:
- C3 (`suggestion-parser.py:1171`): `sections_by_stem` → `dict[str, list[dict]]`; append, never overwrite.
- C4 (`:1274`): `resolve_sections_by_stem` (FAN companion doc) → `dict[str, list[dict]]`; append.
- Force-Atomic reconciliation (`:1297-1342`) iterates the list per stem, not `.get(stem)` scalar.
- `confirmed_items[]` may now hold multiple entries sharing one `source_path` — that is intended; downstream keys per-entry.

**Dependencies**: Phase 2 (analyst contract). `[parallel: true]` with Phase 3 and Phase 5.

---

## Tasks

Delivers N parsed atomic entries per source — including the FAN resolve-doc path — with no silent overwrite.

- [ ] **T4.1 Primary-doc N-entry parsing (C3)** `[activity: backend-logic]` `[parallel: true]`

  1. Prime: Read main parse loop + `sections_by_stem` (`:1144-1190`), Force-Atomic reconciliation (`:1297-1342`) `[ref: SDD/C3]`
  2. Test (RED):
     - 2 approved atomic sections sharing one `source_path` → 2 entries in `confirmed_items` `[ref: PRD/A5]`
     - Force-Atomic reconciliation promotes ALL matching sections per stem, not one `[ref: SDD/C3]`
     - single atomic per stem → 1 entry (length-1 list, no behaviour change) `[ref: PRD/CON-2]`
  3. Implement (GREEN): change `sections_by_stem` to `dict[str, list[dict]]`; append at `:1171`; iterate the list in reconciliation.
  4. Validate: `./venv/bin/python -m pytest tests/ -k parser`; lint.
  5. Success: N entries per source `[ref: PRD/A5]`; single-thread unchanged `[ref: PRD/CON-2]`

- [ ] **T4.2 FAN resolve-doc N-entry parsing (C4)** `[activity: backend-logic]` `[parallel: true]`

  1. Prime: Read FAN resolve handler (`:1238-1274`) and its use in reconciliation (`:1304-1306`) `[ref: SDD/C4]`
  2. Test (RED):
     - FAN-ticked multi-thread log_entry → resolve doc with 2 approved atomics → both reconciled (not one) `[ref: PRD/A8]`
     - FAN-on-single-thread → 1 proposal (no regression) `[ref: PRD/§11 validation hooks]`
  3. Implement (GREEN): `resolve_sections_by_stem` → `dict[str, list[dict]]`; append at `:1274`; reconciliation iterates.
  4. Validate: parser FAN tests; lint.
  5. Success: FAN multi-thread → N reconciled `[ref: PRD/A8]`

- [ ] **T4.3 Phase Validation** `[activity: validate]`

  Run parser tests incl. FAN single-thread regression; bump `# version:`; lint.

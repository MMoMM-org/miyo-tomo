---
title: "Phase 5: Render (block anchor)"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Render (block anchor)

## Phase Context

**GATE**: Read before starting.
- `[ref: SDD/Integration Points — Boundary 1]`, `[ref: SDD/ADR-6 reuse insert_under_marker + block]`
- `tomo/scripts/instruction-render.py` (`_build_insert_under_marker_actions` :1146, `_marker_to_anchor_value` :1110)
- Shipped Hashi matcher: `/Volumes/Moon/Coding/MiYo/Hashi/src/actions/anchorResolver.ts` (`resolveBlock`)

**Key Decisions**: for `table_row + newest_first` emit `anchor.type="block"`, `value` = the group-result's
`resolved_anchor.value` (RAW `header\nseparator` — NOT re-pretty-printed), `placement="after"`. All other
cases use the heading anchor (inside/after) from `resolved_anchor`. Byte-exact value is mandatory.

**Dependencies**: **Phase 1** (anchor enum has `block`). Reads group-results from Phase 4 but can be built
and unit-tested against fixture group-results independently. `[parallel: true]` with Phase 6.

---

## Tasks

Emits the correct `insert_under_marker` action per matrix cell, including the new block anchor.

- [ ] **T5.1 Block-anchor emission branch** `[activity: backend-logic]`
  1. Prime: read `_build_insert_under_marker_actions` + the resolved_anchor contract `[ref: SDD/Boundary 1]`
  2. Test (RED): given a fixture group-result with `output_format.structure=table_row, order=newest_first`
     and `resolved_anchor.value="| Date | … |\n| --- | … |"` → the emitted action has `anchor.type="block"`,
     `value` byte-identical to resolved_anchor.value, `placement="after"`; append/list cases emit a heading
     anchor with the right placement; a group-result WITHOUT output_format → unchanged heading+inside/after
     path (backward compat).
  3. Implement (GREEN): branch in `_build_insert_under_marker_actions` reading structure/order/resolved_anchor;
     do not reconstruct the table. Bump version. WHY → `docs/tomo/scripts/instruction-render.md`.
  4. Validate: `./venv/bin/python -m pytest tests/ -k instruction_render -q`; ruff clean.
  - Success: `[ref: PRD/FR-16]` matrix anchors; `[ref: SDD/Boundary 1]` byte-exact block value.

- [ ] **T5.2 Phase Validation** `[activity: validate]`
  - Emitted actions validate against `instructions.schema.json` (now with `block`); parity test green;
    backward-compat path unchanged; ruff clean.

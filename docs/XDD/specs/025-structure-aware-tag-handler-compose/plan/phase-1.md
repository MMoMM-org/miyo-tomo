---
title: "Phase 1: Schema Foundation"
status: done
version: "1.0"
phase: 1
---

# Phase 1: Schema Foundation

## Phase Context

**GATE**: Read before starting.
- `[ref: SDD/Internal API Changes — Schema contracts]`
- `[ref: SDD/ADR-2 output_format]`, `[ref: SDD/ADR-7 schema parity]`, `[ref: SDD/CON-1 3-way drift]`
- `tomo/schemas/{tag-handler,tag-handler-group,instructions,hashi-instructions}.schema.json`
- `tests/test_tomo_schema_parity.py`
- Shipped Hashi surface: `/Volumes/Moon/Coding/MiYo/Hashi/src/schema/instructions.schema.json` (the `block`
  anchor type + `replace_section` to mirror)

**Key Decisions**: ADR-2 (output_format object + typed cells), ADR-7 (add `block` to both wire schemas;
mirror `replace_section`, no Tomo emitter). Keep `additionalProperties:false` everywhere.

**Dependencies**: none. **This phase is the hard gate for Phases 3–6** (CON-1).

---

## Tasks

Establishes the data contracts so producer/consumer changes can't be silently dropped.

- [x] **T1.1 `output_format` in tag-handler.schema.json** `[activity: data-architecture]`
  1. Prime: read the existing `compose` oneOf + `additionalProperties:false` `[ref: SDD/Internal API Changes]`
  2. Test (RED): a config with a valid `output_format` (structure/order/granularity/cells/join) validates;
     a config with an unknown `output_format` sub-key is REJECTED; a cell that is neither `{field}` nor
     `{synthesize}` is REJECTED; absent `output_format` still validates (backward compat).
  3. Implement (GREEN): add optional `output_format` object after `compose`; `cells` = array of
     `oneOf({field:string},{synthesize:string})`, minItems 1; `join` string default `" — "`. Bump `# version`.
  4. Validate: `./venv/bin/python -m pytest tests/ -k tag_handler_schema -q`; ruff clean.
  - Success: `[ref: PRD/FR-15]` opt-in object accepted; `[ref: PRD/FR-18]` typed cells enforced.

- [x] **T1.2 group-result schema extensions** `[activity: data-architecture]`
  1. Prime: read `tag-handler-group.schema.json` `[ref: SDD/Data Models — GroupResult]`
  2. Test (RED): a group-result with `output_format` + `resolved_anchor {type,value,placement}` + `fallback
     {reason}` validates; unknown keys REJECTED; existing prose-only group-result still validates.
  3. Implement (GREEN): add `output_format`, `resolved_anchor` (type enum[heading,block], value, placement
     enum[inside,after]), `fallback` (reason enum[cell_count_mismatch,no_structure_under_marker,marker_missing]).
     `composed_block` unchanged (already multi-line). Bump version.
  4. Validate: schema unit tests green; ruff clean.
  - Success: `[ref: SDD/Data Models]` group-result carries structure metadata.

- [x] **T1.3 Wire-schema `block` anchor + `replace_section` mirror** `[activity: data-architecture]`
  1. Prime: compare Tomo `instructions.schema.json` / `hashi-instructions.schema.json` anchor enum (:120)
     against the shipped Hashi schema `[ref: SDD/ADR-7]`
  2. Test (RED): an `insert_under_marker` action with `anchor.type:"block"` validates against BOTH Tomo
     schemas; `test_tomo_schema_parity.py` passes with the addition; `replace_section` present in the mirror.
  3. Implement (GREEN): add `"block"` to the anchor `type` enum in both `instructions.schema.json` and
     `hashi-instructions.schema.json`; add the `replace_section` `$def` to the mirror only (parity, no Tomo
     emitter). Update `test_tomo_schema_parity.py` expectations.
  4. Validate: parity + schema tests green; ruff clean.
  - Success: `[ref: SDD/ADR-7]` parity holds; emitting `block` later won't fail parity.

- [x] **T1.4 Phase Validation** `[activity: validate]`
  - Run `./venv/bin/python -m pytest tests/ -k "schema or parity" -q`; ruff clean. Confirm backward-compat
    (existing configs/group-results/instruction sets still validate). **Gate Phases 3–6 on this being green.**

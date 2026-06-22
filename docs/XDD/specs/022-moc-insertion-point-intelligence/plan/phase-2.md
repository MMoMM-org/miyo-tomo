---
title: "Phase 2: Schema additions"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Schema additions

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: solution.md/Data Storage Changes]` — the three schema additions
- `[ref: solution.md/ADR-1]` — `candidate_mocs[].anchor`
- `[ref: solution.md/ADR-3]` — `link_to_moc.new_section`

**Key Decisions**:
- ALL additions are OPTIONAL fields under `additionalProperties:false` → old artifacts still validate (CON-4).
- Gotcha: schema BEFORE consumer — `validate-result.py` strips undeclared fields, so the field must
  exist in schema before any producer/consumer reads it (spec-schema-consumer drift class).

**Dependencies**: none (can run parallel to Phase 1).

---

## Tasks

Establishes the data contract additions every later phase writes to / reads from.

- [x] **T2.1 `candidate_mocs[].anchor` (item-result)** `[parallel: true]` `[activity: data-architecture]`

  1. Prime: Read `candidate_mocs[]` and the dead `link_to_moc.section_name` `[ref: item-result.schema.json; lines: 67-79, 188-197]`.
  2. Test (red): schema-validation test — a `create_atomic_note` with `candidate_mocs[].anchor = {type,value,placement,new_section?}` validates; one without `anchor` still validates (optional).
  3. Implement (green): add optional `anchor` object to `candidate_mocs[]` items mirroring `_pick_anchor`'s return (`type ∈ {heading,callout,line}`, `value`, `placement ∈ {inside,before,after}`, optional `new_section`).
  4. Validate: `./venv/bin/python -m pytest` schema tests pass; legacy result fixtures still validate.
  5. Success: [ ] new+old artifacts validate `[ref: solution.md/CON-4]`

- [x] **T2.2 `mocs[].headings[]` + `editable_callouts[]` (shared-ctx)** `[parallel: true]` `[activity: data-architecture]`

  1. Prime: Read `mocs[]` `[ref: shared-ctx.schema.json; lines: 12-24]` (`additionalProperties:false`).
  2. Test (red): a `mocs[]` entry with `headings:[{text,level}]` + `editable_callouts:[string]` validates; one without still validates.
  3. Implement (green): add both optional arrays to the `mocs[]` item definition.
  4. Validate: schema tests pass.
  5. Success: [ ] inventory fields optional + valid `[ref: solution.md/ADR-2]`

- [x] **T2.3 `link_to_moc.new_section` (instructions)** `[activity: data-architecture]`

  1. Prime: Read `link_to_moc` + `anchor` `[ref: instructions.schema.json; lines: 78-102]`; confirm Hashi applies existing shapes (no Hashi change) `[ref: research-synthesis.md/Hashi contract]`.
  2. Test (red): a `link_to_moc` with `new_section:"<H2 title>"` validates; one without (null/absent) validates.
  3. Implement (green): add optional `new_section: string|null` to instructions `link_to_moc`. Render builds `line_to_add` from it at serialize (Phase 5) — Hashi still receives a final `line_to_add`.
  4. Validate: schema tests pass; the #28 wire shape from the prior handoff still validates.
  5. Success: [ ] explicit new_section validates, no Hashi shape change `[ref: solution.md/ADR-3]`

- [x] **T2.4 Phase Validation** `[activity: validate]`

  - Run schema test suite. Confirm every legacy fixture in `tomo-instance/tomo-tmp` / `tests/` still validates (additive-only proof).

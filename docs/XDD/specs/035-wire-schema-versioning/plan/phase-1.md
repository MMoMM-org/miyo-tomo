---
title: "Phase 1: Describe — the manifest and its generator"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Describe — the manifest and its generator

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Solution Strategy]` — recorded shape with a deliberate regeneration step
- `[ref: SDD/Implementation Examples; What the manifest records, and why only this]`
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-2]`
- `[ref: PRD/Feature 1]`
- `tomo/schemas/suggestions-wire.schema.json` — zero `$defs`; the walk must not depend on them

**Key Decisions**:
- **ADR-2** — record property names, **types**, `required` and openness. Never descriptions.
- A node that declares no openness is **permissive**. Record the effective value, not the literal
  one, or every node that never declared it is misclassified.
- The manifest describes **our** schema. It answers "did we change", never "does the consumer agree".

**Dependencies**:
- None. This phase is the foundation.

---

## Tasks

Establishes the baseline: a committed, machine-checkable record of each published wire's shape.

- [ ] **T1.1 `describe_shape` walks a schema to full depth** `[activity: domain-modeling]`

  1. Prime: read the walk example and the note on effective vs literal openness
     `[ref: SDD/Implementation Examples]`.
  2. Test — each must fail before the implementation exists:
     - a schema with **no `$defs`** yields nodes for its inline objects (this is the case the
       existing check misses entirely, so it is the first test to write);
     - nested objects under `items` are reached, including array-of-object-of-array;
     - `$defs` / `definitions` entries are reached where they exist;
     - `allOf` / `anyOf` / `oneOf` branches are reached;
     - a node declaring `additionalProperties: false` records `closed: true`; one declaring nothing
       records `closed: false`; one declaring `true` records `closed: false`;
     - each property records its declared type, and a property with no declared type records a
       defined placeholder rather than being omitted;
     - **a description-only difference produces an identical manifest** — the anti-churn guarantee.
  3. Implement: `describe_shape(schema) -> dict[pointer, NodeShape]` in
     `tomo/scripts/lib/wire_shape.py`. Pure — no I/O, no network.
  4. Validate: `./venv/bin/python -m pytest tests/test_035_wire_shape.py -x`; ruff clean.
  5. Success:
     - [ ] A `$defs`-free schema is fully described `[ref: PRD/F1-AC3]`
     - [ ] Openness is recorded effectively, not literally `[ref: SDD/Implementation Gotchas]`
     - [ ] Types are recorded; prose is not `[ref: SDD/Architecture Decisions; ADR-2]`
     - [ ] Two schemas differing only in prose describe identically `[ref: PRD/F1-AC4]`

- [ ] **T1.2 The three manifests are generated and committed** `[activity: data-architecture]`

  1. Prime: confirm which three documents are published wires and which fifteen are internal
     `[ref: SDD/Constraints; CON-4]`.
  2. Test: each published wire has a manifest; each manifest round-trips (describing the schema again
     produces the committed content byte-for-byte); an internal schema has **no** manifest; a
     published wire with a **missing** manifest fails rather than passing silently.
  3. Implement: generate `tomo/schemas/shapes/{suggestions-wire,instructions,garden-audit-wire}.shape.json`
     and commit them. Record each manifest's `schema_version` as the value its schema currently
     declares.
  4. Validate: unit tests pass; ruff clean; the three files are committed, not generated at test time.
  5. Success:
     - [ ] Exactly three manifests exist, one per published wire `[ref: SDD/Data Storage Changes]`
     - [ ] A published wire without a manifest fails `[ref: PRD/F1-AC1]`
     - [ ] Regenerating produces identical content on an unchanged schema `[ref: PRD/F1-AC5]`

  **Note on the garden-audit manifest**: our schema already declares `up_source` and `up_value`, so
  the manifest records eight properties on `findings[].detail` and that is **correct**. The drift
  against the consumer's six is not this mechanism's job — it belongs to the vendored-copy report in
  Phase 4. Baking our current state as the baseline is what a manifest is for.

- [ ] **T1.3 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean.
  - Confirm by inspection that the suggestions-wire manifest contains a node for
    `/properties/suggestions/items` — the pointer the existing check never visits, and the location
    of the drift that started this spec.
  - Confirm no manifest contains a description string.

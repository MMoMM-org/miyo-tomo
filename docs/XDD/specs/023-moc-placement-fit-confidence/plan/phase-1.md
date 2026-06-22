---
title: "Phase 1: Schema foundation"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Schema foundation

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: solution.md/Application Data Models; lines: 155-170]` — the `fit_confidence` field shape
- `[ref: solution.md/CON-7]` — schema BEFORE consumers (`additionalProperties:false` trap)
- `[ref: requirements.md/AC-1, AC-2; Edge Cases Scenario 6]` — emission shape + back-compat
- `[ref: tomo/schemas/item-result.schema.json; lines: 77-89]` — the existing 022 anchor block

**Key Decisions**:
- `fit_confidence` is additive, optional, nullable, bounded `[0,1]`, and NOT in the anchor `required[]` — so every 022-shaped anchor (no `fit_confidence`) keeps validating (ADR-1 back-compat).
- This phase ships NO behavior — it is the schema gate that unblocks the analyst emission (Phase 2) and the consumers (Phase 3). It must land first.

**Dependencies**: None — this is the foundation phase.

---

## Tasks

Establishes the `fit_confidence` anchor field so downstream emission and rendering are not silently stripped by `additionalProperties:false`.

- [x] **T1.1 `fit_confidence` anchor schema field** `[activity: data-architecture]`

  1. Prime: Read the 022 anchor block `[ref: tomo/schemas/item-result.schema.json; lines: 77-89]` and the SDD data model `[ref: solution.md/Application Data Models; lines: 155-170]`. Note `additionalProperties:false` (line 81) and `required: ["type","value","placement"]` (line 80).
  2. Test (red): in `tests/test_spec022_schema_additions.py`, assert — (a) an anchor with `fit_confidence: 0.89` validates; (b) an anchor with `fit_confidence: null` validates; (c) a 022-shaped anchor with NO `fit_confidence` key validates (back-compat, AC-12/EC-6); (d) `fit_confidence: 1.01` and `fit_confidence: -0.1` each raise `ValidationError` (bounds).
  3. Implement (green): add `"fit_confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1, "description": "..."}` to the anchor `properties`. Do NOT add it to `required[]`. Description states: LLM 0-1 confidence in the chosen tier-1 heading's semantic fit; present only for tier-1 heading anchors, null/absent otherwise.
  4. Validate: `./venv/bin/python -m pytest tests/test_spec022_schema_additions.py` passes; the four new assertions are present and green.
  5. Success:
     - [ ] tier-1 anchor may carry a bounded `fit_confidence` `[ref: AC-1]`
     - [ ] 022-shaped anchors validate unchanged `[ref: AC-12; solution.md/Reliability]`
     - [ ] out-of-range confidence rejected at schema validation `[ref: requirements.md/EC bounds; solution.md/Back-compat / bounds]`

- [x] **T1.2 Phase Validation** `[activity: validate]`

  - Run `./venv/bin/python -m pytest tests/test_spec022_schema_additions.py`. Confirm the field is additive (no existing schema test regressed) and `additionalProperties:false` still rejects unknown keys other than `fit_confidence`. Verify the schema file is the single source — no duplicate anchor definition was introduced.

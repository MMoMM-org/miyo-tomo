---
title: "Phase 1: Schema Foundation (Layer D)"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Schema Foundation (Layer D)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications — routing-plan.json Schema; lines: 355-505]`
- `[ref: SDD/Interface Specifications — sources[] Frontmatter Shape; lines: 523-572]`
- `[ref: SDD/Interface Specifications — build_tomo_block() API Change; lines: 576-604]`
- `[ref: PRD/F-6; lines: 161-167]`

**Key Decisions**:
- ADR-3: `sources` is `[{path, checksum}]` (objects, not strings) — enables drift detection
- ADR-5: routing-plan schema uses `additionalProperties: false` everywhere
- `patternProperties: "^source_[a-z_]+$"` is removed from doc-frontmatter (clean break — no production data uses it)

**Dependencies**:
- None — this phase has no prerequisites

---

## Tasks

Establishes the data contracts (schemas) and Python API changes that all downstream layers consume.

- [ ] **T1.1 routing-plan.schema.json** `[parallel: true]` `[activity: data-architecture]`

  1. Prime: Read SDD routing-plan schema definition `[ref: SDD/Interface Specifications — routing-plan.json Schema; lines: 355-505]`
  2. Test: Schema validates a conforming routing-plan; rejects extra fields (`additionalProperties: false`); rejects missing required fields (`action`, `timestamp`, `inbox_path`); validates `action` enum values; validates nested object shapes (approved_suggestions, force_atomic_items, drift_indicators, metrics)
  3. Implement: Create `tomo/schemas/routing-plan.schema.json` per SDD spec
  4. Validate: `python3 -c "import json, jsonschema; ..."` against good and bad fixtures; lint clean
  5. Success: Schema file exists and passes positive/negative validation `[ref: PRD/AC-4]` `[ref: SDD/ADR-5]`

- [ ] **T1.2 doc-frontmatter sources[] extension** `[activity: data-architecture]`

  1. Prime: Read current schema `[ref: tomo/schemas/doc-frontmatter.schema.json]` and SDD sources shape `[ref: SDD/Interface Specifications — sources[] Frontmatter Shape; lines: 543-572]`
  2. Test: Schema validates instructions doc with `sources: [{path: "...", checksum: "sha256:..."}]`; rejects instructions with `source_suggestions` (old pattern); validates checksum pattern `^sha256:[a-f0-9]{64}$`; existing doc_types (source, suggestions, suggestions-fan, moc-proposal) still validate without sources field; update `tests/test_doc_frontmatter.py` for new shape
  3. Implement: In `tomo/schemas/doc-frontmatter.schema.json` — add `sources` property to tomo object, remove `patternProperties` block. Sources is optional (only instructions doc-type uses it)
  4. Validate: `python3 -m pytest tests/test_doc_frontmatter.py -v`; schema validates all existing doc-type oneOf branches
  5. Success: instructions doc-type accepts `sources: [{path, checksum}]` and rejects old `source_*` pattern `[ref: PRD/F-6]`

- [ ] **T1.3 build_tomo_block() API migration** `[activity: backend-implementation]`

  1. Prime: Read current API `[ref: tomo/scripts/lib/doc_frontmatter.py; lines: 60-105]` and SDD new signature `[ref: SDD/Interface Specifications — build_tomo_block() API Change; lines: 576-604]`
  2. Test: `build_tomo_block("instructions", "pending-apply", run_id, sources=[{...}])` produces correct dict with `sources` key; calling without `sources` omits the field (backward compat for non-instructions doc-types); update `tests/test_doc_frontmatter.py` for new parameter; update `tests/test_instruction_render_tomo_block.py` for new call signature
  3. Implement: Change `**source_refs` parameter to `sources: list[dict[str, str]] | None = None`; update validation to check sources items have `path` key; update all callers (instruction-render.py is the primary caller — T1.4)
  4. Validate: `python3 -m pytest tests/test_doc_frontmatter.py tests/test_instruction_render_tomo_block.py -v`; `python3 -m mypy tomo/scripts/lib/doc_frontmatter.py`
  5. Success: API accepts sources as list of dicts; old `source_*` kwargs rejected `[ref: PRD/F-6]` `[ref: SDD/build_tomo_block() API Change]`

- [ ] **T1.4 instruction-render.py sources[] population** `[activity: backend-implementation]`

  1. Prime: Read instruction-render.py source_refs usage `[ref: tomo/scripts/instruction-render.py]` and SDD notes on `_UPSTREAM_TO_SOURCE_KEY` replacement `[ref: SDD/Risks and Technical Debt — Known Technical Issues; lines: 1065-1069]`
  2. Test: Rendered instructions doc frontmatter contains `sources: [{path: "...", checksum: "sha256:..."}]` for each input document; checksum computed from input doc body; sources list includes all upstream docs (suggestions, fan, moc-proposal); update `tests/test_instruction_render_tomo_block.py`
  3. Implement: Replace `_UPSTREAM_TO_SOURCE_KEY` mapping and `source_*` emission with `sources[]` list construction. Compute SHA-256 of each input doc body at render time. Pass `sources=` to `build_tomo_block()`. Delete legacy source_* code path (lines 1173-1177 per SDD)
  4. Validate: `python3 -m pytest tests/test_instruction_render_tomo_block.py -v`; `python3 -m ruff check tomo/scripts/instruction-render.py`
  5. Success: Instructions frontmatter contains object-array sources with checksums `[ref: PRD/F-6]` `[ref: SDD/ADR-3]`

- [ ] **T1.5 Phase Validation** `[activity: validate]`

  Run all Phase 1 tests: `python3 -m pytest tests/test_doc_frontmatter.py tests/test_instruction_render_tomo_block.py -v`. Verify both schemas validate positive and negative fixtures. Lint and typecheck pass. Confirm routing-plan.schema.json matches SDD spec exactly.

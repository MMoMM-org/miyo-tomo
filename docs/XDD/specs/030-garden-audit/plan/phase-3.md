---
title: "Phase 3: Render — Report + Wire"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Render — Report + Wire

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications — garden-audit-wire (ADR-4)]`
- `[ref: SDD/ADR-4 — mirrors ADR-026]`
- `[ref: PRD/Feature 2 — prioritised report + JSON wire]`
- `tomo/scripts/suggestions-render.py` (`build_wire_payload`, `emit_digest`), `tomo/scripts/suggestion-parser.py` (`load_changed_wire`/`build_from_wire`), `tomo/schemas/suggestions-wire.schema.json`

**Key Decisions**: ADR-4 (two-artifact producer from one dict; `emit_digest` change signal; skip-analysis + pending-accept stamping).

**Dependencies**: Phase 2 (`garden-audit-doc.json`).

---

## Tasks

Turns findings into the human review report AND the Hashi-editable wire, kept in sync by construction.

- [ ] **T3.1 `garden-audit-render.py` + wire schema** `[activity: backend]`

  1. Prime: Read suggestions-render (`main()`, `build_wire_payload`, digest) and `[ref: SDD/ADR-4]`.
  2. Test: from a `garden-audit-doc.json`, emits (a) severity-ordered markdown report — Summary counts, integrity/structure/advisory sections, empty sections omitted, index-lag + ACL caveats near top, fixable findings carry a checkbox with best-fix pre-selected, advisory read-only; (b) `garden-audit-wire.json` — complete mirror, `schema_version:"1"`, `emit_digest`, stable finding IDs; both project from the SAME dict (no drift). Doc stamped `tomo.doc_type=garden-audit`, `tomo.state=pending-accept`, `tomo_skip_inbox_analysis: true`.
  3. Implement: `tomo/scripts/garden-audit-render.py` + `tomo/schemas/garden-audit-wire.schema.json`.
  4. Validate: `pytest tests/test_garden_audit_render.py`; wire schema-valid; ruff clean.
  - Success: report + schema-valid wire emitted, severity-ordered, caveats present, advisory read-only `[ref: PRD/Feature 2 ACs]`; stamped skip-analysis `[ref: SDD/ADR-1]`.

- [ ] **T3.2 Phase Validation** `[activity: validate]`

  - Run all Phase 3 tests; ruff clean. Confirm markdown ↔ wire parity on a multi-finding fixture (rendered report’s placements reverse-parse to the wire’s decisions).

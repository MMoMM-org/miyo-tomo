---
title: "Phase 4: Apply Integration (2-pass + edit_note_text)"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: Apply Integration (2-pass + edit_note_text)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications — edit_note_text (ADR-3)]`
- `[ref: SDD/Interface Specifications — /inbox integration (ADR-1)]`
- `[ref: SDD/ADR-3, ADR-5, ADR-6]`
- `tomo/schemas/hashi-instructions.schema.json`, `tomo/scripts/lib/render_actions.py` (`_build_link_to_moc_actions`, `emit_up_preservation_actions`), `tomo/scripts/lib/render_md.py:203` (`_UPSTREAM_TYPES`), `tomo/scripts/inbox-triage.py` (buckets, `_get_doc_type`, `compute_new_sources`), `tomo/dot_claude/agents/synthesis-conductor.md`

**Key Decisions**: ADR-1 (4th upstream type, skip-analysis), ADR-3 (one `edit_note_text` action; repoint stays `add_relationship`), ADR-6 (parser mirrors suggestion-parser).

**Dependencies**: Phase 3 (wire); T4.3 depends on T4.2.

---

## Tasks

Wires the approved wire into the shipped 2-pass apply path and adds the one new Hashi action.

- [x] **T4.1 `edit_note_text` Hashi action + builder** `[activity: backend]` `[parallel: true]`

  1. Prime: Read hashi-instructions.schema.json action `oneOf`, and render_actions builders + `_strip_internal_link_fields`.
  2. Test: schema accepts `{path, match, replace, occurrence}` and rejects extras (additionalProperties:false); builder emits it for dead-link fix (`match="[[Old]]" replace="[[New]]"`), dead-link remove (`replace=""`), and `up::` removal (whole-line match, `replace=""`); occurrence defaults `first`; broken-`up::` **repoint** still emits `add_relationship` (not `edit_note_text`).
  3. Implement: add `edit_note_text` to `hashi-instructions.schema.json`; add `_build_edit_note_text_actions` to `render_actions.py`.
  4. Validate: `pytest tests/test_edit_note_text_action.py`; schema tests pass; ruff clean.
  - Success: one primitive covers all three body-edits; repoint unchanged `[ref: SDD/ADR-3, ADR-5 Rule 7]`.

- [ ] **T4.2 `garden-audit-parser.py` (Pass-2 rebuild-from-wire)** `[activity: backend]`

  1. Prime: Read suggestion-parser (`load_changed_wire`, `build_from_wire`) and instruction-render’s upstream-type flow.
  2. Test: `load_changed_wire` returns the wire iff present + `schema_version=="1"` + edited (digest mismatch), else None; `build_from_wire` reconstructs confirmed fixes → actions (`link_to_moc`+`add_relationship` for filing, `add_relationship` for repoint, `edit_note_text` for dead-link/removal); advisory findings emit NO action; unchanged wire → markdown authoritative.
  3. Implement: `tomo/scripts/garden-audit-parser.py`.
  4. Validate: `pytest tests/test_garden_audit_parser.py`; ruff clean.
  - Success: approved fixables render into the instruction set; filing writes MOC bullet + `up::` `[ref: PRD/Feature 3 ACs]` `[ref: SDD/ADR-5]`.

- [ ] **T4.3 `/inbox` integration as 4th upstream type** `[activity: backend]`

  1. Prime: Read `[ref: SDD/Interface Specifications — /inbox integration]`, inbox-triage buckets + `compute_new_sources`, `_UPSTREAM_TYPES`, conductor routing.
  2. Test: an accepted garden-audit doc is picked up (bucket + `_get_doc_type` branch) and routed to `garden-audit-parser` → `instruction-render`; it is EXCLUDED from `fresh_sources` (zero Pass-1 cost — assert no inbox-analyst dispatch); a no-garden-audit `/inbox` run is byte-neutral.
  3. Implement: inbox-triage bucket + `_get_doc_type` branch + `approved_garden_audits`; `render_md._UPSTREAM_TYPES += "garden-audit"`; conductor DOC_TYPE row → `garden-audit-parser.py`.
  4. Validate: `pytest tests/test_inbox_triage*.py` (extend); byte-neutrality test; ruff clean.
  - Success: no new apply path, zero Pass-1 cost `[ref: PRD/Feature 3 AC]` `[ref: SDD/ADR-1, CON-5]`.

- [ ] **T4.4 Phase Validation** `[activity: validate]`

  - Run all Phase 4 tests; ruff clean. Trace one fixable finding wire → parser → instruction-render → Hashi action shape for each fix type.

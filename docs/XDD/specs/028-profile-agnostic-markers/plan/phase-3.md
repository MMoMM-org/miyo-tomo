---
title: "Phase 3: Marker seams (F-16)"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Marker seams (F-16)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples; up_marker_re]`
- `[ref: PRD/Feature 1]`
- `[ref: README/Context; seam list]`

**Key Decisions**: markers threaded as params into pure libs; miyo markers stay `up::`/`related::` so output is byte-identical (F-16 is future-proofing, zero behavioral change today).

**Dependencies**: Phase 1 (needs `Conventions`). Independent of Phase 2 `[parallel: true]` at the phase level.

---

## Tasks

De-hardcodes relationship markers across read + write seams. **Highest regression risk is T3.2 (writer paths).**

- [ ] **T3.1 up_parse parse-by-param** `[activity: backend]` `[parallel: true]`

  1. Prime: Read `lib/up_parse.py` (55) parse regex + `moc-tree-builder.py` usage.
  2. Test (RED): parse fn extracts links using a supplied `parent_marker`; default preserves `up::` behavior.
  3. Implement (GREEN): add `parent_marker` param, build regex via `re.escape`; caller (moc-tree-builder) passes resolved marker.
  4. Validate: pytest + ruff; miyo parse fixtures unchanged.
  5. Success: [ ] parse parity under `up::` `[ref: PRD/AC F-16]`

- [ ] **T3.2 render_actions read+write markers** `[activity: backend]`

  1. Prime: Read `lib/render_actions.py` `_UP_MARKER_RE`/`_RELATED_MARKER_RE` (110-111), related literal (169), `_make_add_rel` (274, already has `marker` param), `emit_up_preservation_actions` (319-369).
  2. Test (RED): read regexes built from markers; `emit_up_preservation_actions` writes profile markers; **byte-identical miyo `instructions.json` rendered-actions regression** against a captured baseline fixture.
  3. Implement (GREEN): thread `parent_marker`/`peer_marker` from `Conventions` into the read-regex builders and every write site (replace the hardcoded `"up::"`/`"related::"` at 319-369 and the `related:: ` literal at 169).
  4. Validate: pytest + ruff; the byte-identical regression fixture MUST pass — if not, stop (Deviation Protocol).
  5. Success:
     - [ ] miyo rendered actions byte-identical `[ref: PRD/AC F-16; SDD/Quality Requirements]`
     - [ ] markers sourced from conventions on read + write `[ref: PRD/Feature 1]`

- [ ] **T3.3 moc-discovery up:: warning regex** `[activity: backend]` `[parallel: true]`

  1. Prime: Read `moc-discovery.py` multi-`up::` warning regex (1410); `profile_dict` in scope.
  2. Test (RED): warning detection uses resolved `parent_marker`; miyo behavior unchanged.
  3. Implement (GREEN): build regex from `resolve_conventions(profile_dict=...).parent_marker`.
  4. Validate: pytest + ruff.
  5. Success: [ ] warning parity under `up::` `[ref: PRD/AC regression]`

- [ ] **T3.4 suggestion-parser override header from conventions** `[activity: backend]`

  1. Prime: Read `suggestion-parser.py` override-header handling (231, 1211) + its `--suggestions-doc` ingest.
  2. Test (RED): override-header detection uses `parent_marker` from the `suggestions-doc.json` `conventions` block; **absent block → falls back to `up::`** (older-artifact safety).
  3. Implement (GREEN): read `conventions.parent_marker` from the loaded suggestions-doc; build the header matcher from it with an `up::` default.
  4. Validate: pytest + ruff; test both with-block and without-block inputs.
  5. Success:
     - [ ] header detection uses profile marker `[ref: PRD/Feature 1]`
     - [ ] graceful fallback when block absent `[ref: PRD/Config & fallback]`

- [ ] **T3.5 Phase Validation** `[activity: validate]`

  - Run all marker tests + ruff. Byte-identical miyo regression (T3.2) green. Grep-confirm no residual hardcoded `up::`/`related::` in the marker seams (except intended defaults).

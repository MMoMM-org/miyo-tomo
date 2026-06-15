---
title: "Phase 5: Render honor path"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Render honor path

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: solution.md/Implementation Examples — _emit stamping the Pass-1 anchor]`
- `[ref: solution.md/ADR-5, ADR-3, ADR-6]`
- `[ref: instruction-render.py; lines: 739-827, 765-785, 1471, 1476, 1585-1601, 1652]`

**Key Decisions**:
- ADR-5: `_emit` stamps the Pass-1 anchor; the existing `if anchor.get("value"): continue` guard
  (~`:1652`) makes the heuristic fallback-only automatically.
- ADR-3: build `line_to_add` from `new_section` at serialize.
- ADR-6: retire `DEFAULT_NEW_SECTION_TITLE` (`:1476`); last-resort = H1-title anchor.
- The render-time fallback imports `lib/moc_structure` so it agrees with build-time inventory.

**Dependencies**: Phase 1 (lib), Phase 2 (T2.1, T2.3 schema), Phase 4 (Pass-1 emits anchor).

---

## Tasks

Makes Pass-2 honor the reviewed Pass-1 decision and keep the heuristic as fallback only.

- [x] **T5.1 `_emit` stamps + threads the Pass-1 anchor** `[activity: backend]`

  1. Prime: Read `_build_link_to_moc_actions` + `_emit` `[ref: instruction-render.py; lines: 739-827, 765-785]` and the heuristic skip guard (`:1652`).
  2. Test (red):
     - An action whose confirmed `candidate_mocs[]` carries an `anchor` is emitted with that anchor; `resolve_section_names` does NOT re-resolve it (honor path) (AC-12/AC-13).
     - An action with NO Pass-1 anchor still falls to the deterministic heuristic (back-compat).
     - EC-6: a user-edited heading not present in the MOC → emitted as a new-section (create the H2), not appended elsewhere.
  3. Implement (green): thread the per-candidate anchor (match confirmed item's `candidate_mocs[]` by `_moc_stem`) into `_emit`; stamp `anchor` + `placement`. Bump `# version:`.
  4. Validate: honor-path + fallback + EC-6 tests pass.
  5. Success:
     - [ ] populated anchor not re-resolved `[ref: AC-13]`
     - [ ] user edit honored `[ref: AC-12]`
     - [ ] EC-6 → new section `[ref: requirements.md/EC-6]`

- [ ] **T5.2 new_section serialize + retire DEFAULT_NEW_SECTION_TITLE** `[activity: backend]`

  1. Prime: Read `DEFAULT_NEW_SECTION_TITLE` + the current line_to_add mutation `[ref: instruction-render.py; lines: 1476, 1677]`.
  2. Test (red): an anchor with `new_section:"Reasoning"` serializes `line_to_add = "## Reasoning\n\n- [[Note]]\n"` (trailing newline preserved, AC-6); the hardcoded "Key Concepts" no longer appears as a default name.
  3. Implement (green): build `line_to_add` from `new_section` at serialize; remove `DEFAULT_NEW_SECTION_TITLE` as the new-section name source (empty-MOC template-only default may remain if needed).
  4. Validate: spacing/newline regression test (mirrors PR #57) passes.
  5. Success: [ ] new section named + spaced correctly `[ref: AC-5,AC-6]`

- [ ] **T5.3 Render fallback shares the parse lib + template path** `[activity: backend]`

  1. Prime: Read `_pick_anchor` + `_resolve_from_template` `[ref: instruction-render.py; lines: 1585-1601, 1623-1632]`.
  2. Test (red):
     - The render-time fallback uses `lib/moc_structure` so it agrees with build-time inventory on what is a heading/footer.
     - EC-2: an in-run new MOC (not yet existing) resolves heading-fit against the create-MOC template body.
  3. Implement (green): import `moc_structure` in the fallback; route the template-body case through it.
  4. Validate: fallback + EC-2 tests pass; no parser divergence build-vs-render.
  5. Success: [ ] one parser, both sites `[ref: solution.md/ADR-4]`; [ ] in-run MOC vs template `[ref: EC-2]`

- [ ] **T5.4 Phase Validation** `[activity: validate]`

  - Run the render test suite + the existing instruction-render tests (regression). Confirm honor path, fallback, and spacing all green.

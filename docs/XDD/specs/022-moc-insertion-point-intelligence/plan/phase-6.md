---
title: "Phase 6: Suggestions surfacing"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Suggestions surfacing

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: requirements.md/Feature 5; AC-11..AC-13, AC-16]`
- `[ref: research-synthesis.md/UX surfacing]` — the four `**Placement:**` line formats
- `[ref: suggestions-reducer.py; lines: 324-331]`

**Key Decisions**:
- One `**Placement:**` line per link with a leading qualifier word + `←` edit hint; never a bare
  `[[Target#]]`.
- Edit affordance follows the existing `←` idiom (MOC Name/Parent precedent, `suggestions-render.py:145-146`).
- Style contract: `suggestions-doc-format/SKILL.md`.

**Dependencies**: Phase 4 (anchor on the item result). Independent of Phase 5 (render).

---

## Tasks

Surfaces the placement decision in the suggestions document so the user can review and override it.

- [ ] **T6.1 `**Placement:**` line in render_link_to_moc** `[activity: frontend]`

  1. Prime: Read the current MOC-link render `[ref: suggestions-reducer.py; lines: 324-331]` and the `←` hint precedent `[ref: suggestions-render.py; lines: 145-146]`.
  2. Test (red): for each of the four outcomes, the rendered block contains exactly one `**Placement:**` line with the right qualifier + `←` hint, and NEVER a bare `[[Target#]]`:
     - under `## <heading>` · new section `## <Topic>` (created before the footer) · inside the `> [!<callout>]` callout · under the note title (no matching section or callout found).
  3. Implement (green): extend `render_link_to_moc` to read the item's `candidate_mocs[].anchor` and emit the matching `**Placement:**` line. Bump `# version:`.
  4. Validate: reducer render tests pass against fixtures mirroring real suggestions-doc output (read a real artifact, don't invent).
  5. Success:
     - [ ] one Placement line, all four outcomes `[ref: AC-11]`
     - [ ] editable via `←` hint `[ref: AC-12]`
     - [ ] never bare anchor `[ref: AC-11]`

- [ ] **T6.2 Ambiguous-fit advisory (Should)** `[activity: frontend]`

  1. Prime: Review the ambiguous-fit affordance `[ref: requirements.md/AC-16]`.
  2. Test (red): when ≥2 content headings are plausible, an advisory "Other sections in this MOC: …" line appears so the user can retarget without a re-run.
  3. Implement (green): emit the advisory line when the anchor carries alternatives (or when the MOC has ≥2 content headings).
  4. Validate: advisory render test passes.
  5. Success: [ ] alternatives surfaced `[ref: AC-16]`

- [ ] **T6.3 Phase Validation** `[activity: validate]`

  - Run reducer test suite. Confirm no rendered MOC link emits a bare `[[Target#]]`.

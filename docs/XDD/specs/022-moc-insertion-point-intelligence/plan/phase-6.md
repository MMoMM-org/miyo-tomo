---
title: "Phase 6: Suggestions surfacing"
status: completed
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

- [x] **T6.1 `**Placement:**` line in render_link_to_moc** `[activity: frontend]`

  1. Prime: Read the current MOC-link render `[ref: suggestions-reducer.py; lines: 324-331]` and the `←` hint precedent `[ref: suggestions-render.py; lines: 145-146]`.
  2. Test (red): for each of the four outcomes, the rendered block contains exactly one `**Placement:**` line with the right qualifier + `←` hint, and NEVER a bare `[[Target#]]`:
     - under `## <heading>` · new section `## <Topic>` (created before the footer) · inside the `> [!<callout>]` callout · under the note title (no matching section or callout found).
  3. Implement (green): extend `render_link_to_moc` to read the item's `candidate_mocs[].anchor` and emit the matching `**Placement:**` line. Bump `# version:`.
  4. Validate: reducer render tests pass against fixtures mirroring real suggestions-doc output (read a real artifact, don't invent).
  5. Success:
     - [ ] one Placement line, all four outcomes `[ref: AC-11]`
     - [ ] editable via `←` hint `[ref: AC-12]`
     - [ ] never bare anchor `[ref: AC-11]`

- [x] **T6.2 Ambiguous-fit advisory (Should)** `[activity: frontend, prompt-engineering]`

  > **Scope expansion (decided 2026-06-15):** AC-16 requires Pass-1 to flag runner-up headings, but Phase 4 emitted only the single best-fit anchor and the schema had no runner-up field. User chose to implement T6.2 fully (cost: zero new Kado reads/LLM calls; small fixed prompt bump only). T6.2 is now a vertical slice — schema field → analyst emission → render advisory — ordered schema-before-consumer.

  1. Prime: Review the ambiguous-fit affordance `[ref: requirements.md/AC-16, EC-3]`; the anchor schema `[ref: item-result.schema.json candidate_mocs[].anchor]`; Step 4 tier-1 `[ref: inbox-analyst.md]`.
  2. Test (red):
     - schema: an anchor carrying an optional runner-up-headings field validates; absent field still valid (back-compat).
     - analyst contract fixture: tier-1 with ≥2 plausible headings emits the best-fit anchor AND the runner-up heading(s) in the new field; single-fit emits none.
     - render: when the anchor carries runner-ups, an advisory "Other sections in this MOC: …" line appears; absent → no advisory. Do NOT trigger on raw heading count (most MOCs have ≥2 headings → would flood the doc).
  3. Implement (green), ordered schema-before-consumer:
     a. Add an optional runner-up-headings field to the `candidate_mocs[].anchor` schema (e.g. `alt_headings: [string]`), `additionalProperties:false`-safe, nullable/absent by default.
     b. Extend inbox-analyst Step 4 tier-1 to emit the runner-up heading text(s) ONLY when ≥2 headings genuinely fit. Bump `# version:`.
     c. Extend `render_link_to_moc` to emit the advisory line from that field. Bump `# version:`.
  4. Validate: schema + analyst + render tests pass; instructions/honor path unaffected.
  5. Success: [ ] runner-ups emitted by Pass-1 when ambiguous `[ref: AC-16,EC-3]`; [ ] advisory surfaced, never flooded `[ref: AC-16]`

- [x] **T6.3 Phase Validation** `[activity: validate]`

  - Run reducer test suite. Confirm no rendered MOC link emits a bare `[[Target#]]`.

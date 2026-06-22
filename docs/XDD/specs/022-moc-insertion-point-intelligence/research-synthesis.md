# Research Synthesis — Spec 022 (MOC insertion-point intelligence)

> Agent-team research, 2026-06-14/15. Perspectives: Requirements, Technical, Integration, UX.
> Every claim grounded in file:line by the researchers. This feeds PRD → SDD → PLAN.

## Convergent finding

The three-tier insertion resolver **already exists** — `resolve_section_names` / `_pick_anchor`
(`instruction-render.py:1479-1679`) does callout → heading → new-section-before-footer. It is
(a) **deterministic** (no semantic fit — `_pick_content_heading:1558-1574` picks the first or
`{key concepts,concepts,notes}`-named heading), and (b) **runs at Pass-2 render, after the user
confirmed** — so placement is never reviewable. Spec 022's real work:

1. **Relocate** the decision to Pass-1 (`inbox-analyst`) so it surfaces in the suggestions doc.
2. **Add a semantic tier-0**: LLM picks the *thematically fitting* H2/H3 (new behavior).
3. **Reorder**: heading-fit before callout; editable callout demoted to fallback. (Pass-1 LLM
   judgment reorder — render keeps its deterministic order as fallback only.)

## Carrier correction (Technical)

- Pass-1 `link_to_moc.section_name` (`item-result.schema.json:188-197`) is **dead** — consumed
  nowhere except one render line; `validate-result.py:42` requires it but nothing reads it.
- The **live** path: analyst emits `create_atomic_note.candidate_mocs[]` (`{path,score,pre_check}`,
  `item-result.schema.json:67-79`); `link_to_moc` actions are **synthesized at render** in
  `_build_link_to_moc_actions` (`instruction-render.py:739-827`) from confirmed `parent_mocs[]` /
  `supporting_items`. The anchor decision must attach to **candidate_mocs[]** and thread through
  `_emit` (`:765-785`, today hardcodes `anchor:{type:callout,value:None}`).
- **DECISION (2026-06-15):** carrier = `candidate_mocs[]`; exact field shape decided in SDD.

## Cost / #45 (Technical, measured live — 63 MOCs)

- 63 MOCs reach shared-ctx (53 thematic, 10 Dewey/classification). ⌀ **4.2 headings/MOC**,
  **1.3 editable-callouts/MOC**; range 0–17 (Index outlier). ~6–7 KB heading text vs 40 KB budget.
- Heading inventory can be parsed in `moc-tree-builder.py:290-323` at the **existing** body-read
  site (`raw_by_path`) — **zero new Kado calls** (avoids the 429 read-storm risk, memory
  `reference_kado_429_blocks_host_full_pipeline`). Regexes already exist
  (`instruction-render.py:1510-1511`) — lift into a shared lib so build-time inventory and
  render-time fallback agree.
- Options: (A) eager full, (A-trimmed) eager headings-only + cap ~8/MOC + skip Dewey, (B) lazy,
  (C) 2-pass analyst. **Cost approach decided in SDD**; 022 acknowledges the regression and defers
  the shaping mitigation to **#45**.

## Hashi contract (Integration — verified vs handoffs + Hashi repo)

- Insert primitive **landed** (Hashi PR #65); confirmed in
  `_outbox/for-hashi/2026-06-13_tomo-to-hashi_insert-primitive-tomo-side-confirmed.md`.
- Applied shapes: `anchor.type ∈ {callout, heading, line}`, `placement ∈ {inside, before, after}`,
  `line_to_add` verbatim (multi-line via `\n`, Tomo owns whitespace). Verified in Hashi
  `src/actions/anchorResolver.ts` + `src/schema/instructions.schema.json:99` —
  **heading matches ANY level (incl. H1)**; **`line` matches any body line by literal content**.
- **All 022 outcomes map onto existing shapes — NO new Hashi wire shape:**
  - fitting H2/H3 → `{type:heading, value:<heading>, placement:after}`
  - new H2 section → `{type:callout, value:<footer>, placement:before, line_to_add:"## <Section>\n\n- [[Note]]\n"}`
  - under editable callout → `{type:callout, value:<callout line>, placement:inside}`
  - **last-resort → `{type:heading, value:<H1 title>, placement:after}`** (H1 always present;
    deeper fallback `{type:line, ...}`). DECISION 2026-06-15.
- **Cross-repo obligations:** Constitution **L2** — Pass-2→Pass-1 relocation changes the
  Tomo↔Hashi interaction model → requires a **Kokoro ADR / design-note** before/alongside impl.
  Plus a confirmation handoff that the new Pass-1 emission exercises existing shapes, and a
  **real Tomo→Hashi walk** (the standing "real walks > synthetic fixtures" rule; #28 still owes one).

## UX surfacing (UX)

- Today the reducer renders only `**Link to existing MOC:** [[target#section]]`
  (`suggestions-reducer.py:324-331`); with `section_name` unpopulated it shows a **bare `[[target#]]`**
  — no placement visible. The confirm gate is the doc-level `- [ ] Approved` checkbox
  (`suggestions-render.py:66`); editing = direct markdown edit after a `←` hint (precedent:
  MOC Name/Parent at `suggestions-render.py:145-146`).
- **Proposed: one `**Placement:**` line per link**, leading qualifier word for skimmability:
  - `**Placement:** under \`## Frameworks and Methodologies\`    ← edit the heading to move the link`
  - `**Placement:** new section \`## <Topic>\` (created before the footer)    ← rename or change`
  - `**Placement:** inside the \`> [!blocks]\` callout    ← change to a \`## Heading\` to place under a section`
  - `**Placement:** under the note title (no matching section or callout found)    ← add a \`## Heading\` to target a section`
- Empty/ambiguous/error states: never emit bare `[[target#]]`; for in-run new MOCs note "this MOC
  will be created"; multiple plausible headings → optional advisory "Other sections: …" line
  (new affordance — flagged). Style contract: `suggestions-doc-format/SKILL.md`. Tie-in: epic #19 /
  issue #33 (Suggestions Doc UX) — exist on the GH board, not yet in code.

## Locked decisions (see README Decisions Log)

1. Last-resort = H1-title anchor, `placement:after` — Hashi-capable today, no new shape.
2. F-05 (topic weighting) **fenced out** — 022 = insertion-point only.
3. New-section name from note topic; retire `DEFAULT_NEW_SECTION_TITLE` "Key Concepts".
4. Carrier = `candidate_mocs[]` (SDD finalizes shape).
5. Heading inventory parsed in moc-tree-builder, no new Kado calls (SDD finalizes cost-trim).

## Deferred / fenced

- **#45** — per-item context cost of heading inventory (022 adds to envelope; #45 shapes it).
- **#35 / F-55** — `FOOTER_CALLOUTS` hardcoded (`instruction-render.py:1471`); 022 consumes it, F-55 makes it profile-driven.
- **F-05** — MOC-selection topic weighting, separate.

## Open edge-case behaviors for the PRD to pin (with recommended defaults)

- **EC-6 user overrides placement to a non-existent heading** → recommend: treat as new-section
  (create the H2 the user named) rather than silent append. (req vs UX gave differing defaults —
  PRD must pick; recommend "create the section the user named".)
- **EC-2 in-run new MOC** → heading-fit judged against the create_moc **template body**
  (`_resolve_from_template`, `instruction-render.py:1623-1632`).
- **EC-5 classification MOC** (`is_classification`) → never an insertion target (excluded pre-Step-1,
  `inbox-analyst.md:121-126`).

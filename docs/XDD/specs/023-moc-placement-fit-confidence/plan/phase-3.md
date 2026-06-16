---
title: "Phase 3: Pass-1 confidence gate"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Pass-1 confidence gate

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: solution.md/Implementation Examples; TIER-1 gate + TIER-2 no-footer branch]` — verbatim emission patterns
- `[ref: solution.md/Complex Logic — PASS-1; traced walkthrough]` — the algorithm + the two walk cases
- `[ref: requirements.md/Feature 2; AC-4..AC-7]` — the gate; `[ref: requirements.md/AC-8, AC-9, AC-9a]` — has_footer-driven tier-2 anchor type
- `[ref: tomo/dot_claude/agents/inbox-analyst.md; lines: 158-201]` — the existing TIER-1..TIER-4 blocks (version 0.17.5)

**Key Decisions**:
- Threshold hardcoded at **0.6** inline (ADR-4); at exactly 0.6 → tier-1 (deterministic tie-break, PRD Scenario 4).
- A gate-rejected best heading goes into the tier-2 anchor's `alt_headings` (ADR-3).
- **Pass-1 has no MOC body.** TIER-2 emits `value:null` and picks the anchor TYPE from `moc.has_footer` (Phase 2): footer → `callout/before` (null value); no footer → `line/after` (null value). The render resolver (Phase 4) fills the value. Do NOT instruct the LLM to emit `<last body line>` / `<footer text>` — it cannot see them.
- If `moc.has_footer` is absent (pre-rebuild cache), fall back to the 022 `callout/before` placeholder (graceful degradation; SDD Error Handling).
- The analyst is an LLM-loaded prompt — the tier DECISION is validated in the live walk (Phase 5). This phase's deterministic test asserts the CONTRACT: each documented emission shape validates against the schema and carries the right type/null-value/new_section/alt_headings.

**Dependencies**: Phase 1 (`fit_confidence` schema field) + Phase 2 (`has_footer` inventory the analyst reads).

---

## Tasks

Delivers the confidence-gated Pass-1 emission — the crux of the spec.

- [x] **T3.1 Analyst TIER-1 gate + TIER-2 has_footer-driven anchor** `[activity: backend]`

  1. Prime: Read the SDD emission examples + the PASS-1 algorithm `[ref: solution.md/Implementation Examples; Complex Logic — PASS-1]` and the existing TIER blocks `[ref: tomo/dot_claude/agents/inbox-analyst.md; lines: 158-201]`.
  2. Test (red): in `tests/test_moc_insertion_resolution.py`, add contract fixtures (from the SDD examples) asserting each emission shape is schema-valid and correctly shaped —
     - confident fit → `{type:heading, value, placement:after, new_section:null, fit_confidence:0.89, alt_headings:[...]}` (AC-1, AC-4);
     - weak/scaffolding fit, footer MOC (Japan-`Content` regression) → `{type:callout, value:null, placement:before, new_section:"<topic>", alt_headings:["Content"]}` (AC-5, AC-6, AC-8);
     - weak fit, no-footer MOC → `{type:line, value:null, placement:after, new_section:"<topic>", alt_headings:[...]}` (AC-9);
     - back-compat: `has_footer` absent → `callout/before` placeholder (022 behavior).
  3. Implement (green): edit `inbox-analyst.md` — (a) TIER-1: rank headings by *meaning*, score the best `fit_confidence` 0.0-1.0 (1.0 = clear topical home; ~0.3 = generic/structural scaffolding such as `Content`/`Structure`/`Overview`/`Primer Questions`), emit tier-1 ONLY if `fit_confidence >= 0.6`, else fall through to TIER-2 putting the rejected heading in `alt_headings`; (b) TIER-2: name the section from the dominant topic (NEVER literal "Key Concepts"), emit `value:null` and choose the type from `moc.has_footer` — true → `callout/before`, false → `line/after`, absent → `callout/before` (022 fallback). Bump `# version:` (0.17.5 → next).
  4. Validate: contract fixtures pass; re-read the edited TIER blocks to confirm the `0.6` literal, the structural-heading examples, the `value:null` instruction, and the `has_footer` branch are present; confirm no MOC-selection wording (`score`/`needs_new_moc`) was touched and the prompt never fabricates `fit_confidence` for empty inventory.
  5. Success:
     - [ ] confident heading fit → tier-1 with `fit_confidence` `[ref: AC-1, AC-4]`
     - [ ] sub-threshold fit → tier-2 new section, rejected heading in `alt_headings` `[ref: AC-5, AC-6]`
     - [ ] tier-2 fires when no MOC offers a confident fit `[ref: AC-7]`
     - [ ] tier-2 anchor type chosen from `has_footer`, value null `[ref: AC-8, AC-9, AC-9a]`
     - [ ] MOC-selection (`score`/`needs_new_moc`) untouched `[ref: solution.md/CON-6]`

- [x] **T3.2 Phase Validation** `[activity: validate]`

  - Run `./venv/bin/python -m pytest tests/test_moc_insertion_resolution.py`. Confirm all new contract fixtures pass and no 022 resolution test regressed. Confirm the `# version:` bump and the graceful-degradation wording (empty inventory; absent `has_footer`) are intact.

---
title: "Phase 4: Pass-1 four-tier decision"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Pass-1 four-tier decision

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: solution.md/Complex Logic — four-tier resolution]`
- `[ref: requirements.md/Feature 1-4; AC-1..AC-10]`
- `[ref: inbox-analyst.md; lines: 113-150, 121-126, 612-615]`

**Key Decisions**:
- The four-tier order runs in Pass-1: semantic heading-fit → new-section (named from topic) →
  editable-callout → H1 last-resort.
- Classification MOCs (`is_classification`) excluded before tier-1 (EC-5).
- New-section name from note topic, NOT "Key Concepts" (AC-5).
- Feedbacks: tell HOW not WHAT (give the exact emission shape, no helper prose); STRICT block only
  if a plain imperative deviates; no executor/Hashi internals in the agent prompt.

**Dependencies**: Phase 3 (inventory in shared-ctx), Phase 2 (T2.1 anchor schema).

---

## Tasks

Moves the placement decision into the Pass-1 LLM so it can be reviewed.

- [x] **T4.1 inbox-analyst emits `candidate_mocs[].anchor`** `[activity: prompt-engineering]`

  1. Prime: Read Step 4 MOC match + pre_check + classification guard `[ref: inbox-analyst.md; lines: 113-150, 121-126, 612-615]`; the anchor shape `[ref: item-result.schema.json candidate_mocs[].anchor]`.
  2. Test (red): contract fixtures for the analyst's emitted `result.json` —
     - MOC with a fitting H2 → `anchor:{type:heading,value:<H2>,placement:after}` (AC-1).
     - Zero-token-overlap-but-fits fixture → still the semantically right heading (AC-2).
     - Headings present, none fits → `anchor:{type:callout,value:<footer>,placement:before,new_section:<topic>}` with `new_section ≠ "Key Concepts"` (AC-4/AC-5).
     - No headings, editable callout present → `anchor:{type:callout,value:<callout>,placement:inside}` (AC-7).
     - No headings, no callout → `anchor:{type:heading,value:<H1 title>,placement:after}` (AC-9).
     - No headings, no callout, AND no H1 (the chaos-vault tail of EC-1) → `anchor:{type:line,value:<first body line>,placement:after}` — never unresolved (AC-10).
     - Classification MOC → no anchor / excluded as target (EC-5).
  3. Implement (green): extend Step 4 of `inbox-analyst.md` to emit `candidate_mocs[].anchor` per pre-checked MOC using the four-tier order against `shared_ctx.mocs[].headings`/`editable_callouts`. Use the exact emission shape (HOW, not WHAT). Bump `# version:`. Run the skill-author/agent-author audit after editing.
  4. Validate: schema-valid result fixtures; agent-author audit clean (no host-path leak, no Hashi internals).
  5. Success:
     - [ ] four-tier order emitted correctly `[ref: AC-1,4,7,9]`
     - [ ] new-section named from topic `[ref: AC-5]`
     - [ ] classification excluded `[ref: EC-5]`

- [x] **T4.2 Semantic-fit guardrail** `[activity: prompt-engineering]`

  1. Prime: Review the semantic-fit requirement `[ref: requirements.md/AC-2]` and the "chaos vault" constraint.
  2. Test (red): the keyword-mispick fixture (note shares tokens with the wrong heading) resolves to the semantically correct heading, proving fit is by meaning not overlap.
  3. Implement (green): phrase the Step-4 instruction so fit is judged semantically; add a STRICT one-liner ONLY if a plain imperative is observed to fall back to keyword overlap.
  4. Validate: the mispick fixture passes.
  5. Success: [ ] semantic fit beats keyword overlap `[ref: AC-2]`

- [x] **T4.3 Phase Validation** `[activity: validate]`

  - Run analyst contract fixtures. Confirm emitted results validate against the Phase-2 schema and every tier path is covered.

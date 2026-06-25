---
title: "Phase 4: Interpreter Compose"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Interpreter Compose

## Phase Context

**GATE**: Read before starting.
- `[ref: SDD/Implementation Examples — Interpreter step-3 branch]`, `[ref: SDD/Runtime View]`
- `tomo/dot_claude/skills/tag-handler-interpreter/SKILL.md` (steps 2–4)
- `[ref: SDD/ADR-1 hybrid]`, `[ref: SDD/ADR-3 AI-glue only]`, `[ref: SDD/ADR-8 fallback]`
- Memory rules: runtime SKILL.md = imperatives/invocations only; rationale → docs/tomo/; one-block-per-group STRICT.

**Key Decisions**: the skill reads the TARGET section via Kado, produces ONLY `synthesize` cell values
(per_item: per source; merged: once over batch), calls `target_structure.assemble`, and writes
`composed_block + output_format + resolved_anchor (+ fallback)` to the group-result. The skill does NOT
parse tables. On `Fallback`, it composes a plain prose block.

**Dependencies**: **Phase 1** (group-result schema accepts the new fields), **Phase 2** (the helper),
**Phase 3** (stub carries output_format).

---

## Tasks

Wires structure-aware compose into the interpreter while keeping all parsing/assembly in the helper.

- [ ] **T4.1 Target read + synthesize-cell production** `[activity: ai-orchestration]`
  1. Prime: read the interpreter step-2/3 and the kado-read section mode `[ref: SDD/Integration Points]`
  2. Test: (skill-level; verify via a dry-run fixture) for an `output_format` stub the interpreter reads the
     target section (least-payload section read) and produces one synth value per cell directive at the
     correct scope (per_item vs merged). `field` cells come from `stub.fields`.
  3. Implement: edit `SKILL.md` step 2 (also read target) + step 3 (branch on output_format → synth cells →
     call helper). Bump `# version`. Add WHY to `docs/tomo/dot_claude/skills/tag-handler-interpreter/SKILL.md`.
  4. Validate: skill audit (skill-author) clean; no executor internals; imperatives-only.
  - Success: `[ref: PRD/FR-17]` granularity scope; `[ref: PRD/FR-18]` field vs synthesize.

- [ ] **T4.2 Group-result emission + STRICT reword** `[activity: ai-orchestration]`
  1. Prime: one-block-per-group invariant `[ref: SDD/Constraints]`
  2. Test: group-result written for an output_format group includes `composed_block` (N rows for per_item,
     1 for merged) + `output_format` + `resolved_anchor`; on helper `Fallback` it writes a plain prose
     `composed_block` + `fallback.reason`; still exactly ONE block per group.
  3. Implement: update step 4 to write the new fields; reword the STRICT so N rows ≠ N blocks.
  4. Validate: a fixture group-result validates against the Phase-1 group-result schema.
  - Success: `[ref: PRD/FR-19]` fallback path; `[ref: 024 FR-8/AC-3]` one block per group preserved.

- [ ] **T4.3 Phase Validation** `[activity: validate]`
  - Skill-author audit passes; a sample run produces schema-valid group-results for table/list × append/
    newest × per_item/merged and for a forced mismatch (fallback). ruff/lint clean for any touched scripts.

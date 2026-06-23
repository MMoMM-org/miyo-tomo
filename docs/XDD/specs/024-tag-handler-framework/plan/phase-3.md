---
title: "Phase 3: Pass-1 compose + suggestion"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Pass-1 compose + suggestion

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Section 5; lines: 95-103]` — interpreter skill + compose: group by `(handler, target_path)`, one compose per group
- `[ref: PRD/FR-7,FR-8; lines: 66-69]` — group by (handler, target); LLM directive gets the whole group → one merged update
- `[ref: PRD/FR-9; lines: 72-73]` — Pass-1 surfaces each group as a reviewable suggestion
- `[ref: PRD/AC-3; lines: 109-110]` — three captures for one repo → one merged suggestion

**Key Decisions**:
- A thin `tag-handler-interpreter` skill is loaded by the suggestion-conductor **only when** `routing-plan.handled` is non-empty (SDD §5) — keeps the cold path untouched.
- LLM-directive compose → **one** call per group receives all captures → one merged status-update block (never one output per source item) (FR-8).
- Field-template compose → mechanical join, **no LLM** (SDD §5).
- Reuse the existing suggestions-doc format + `Approve` box (SDD §5).

**Dependencies**:
- Phase 2 (`routing-plan.handled` populated by triage) must be complete.

---

## Tasks

Enables Pass-1 to turn a batch's handled items into reviewable, merged suggestion blocks — one per (handler, target) group.

> **Build decomposition note**: phase-T3.1's "interpreter skill" split into a deterministic, testable
> grouping core (T3.1 below) and the runtime skill itself (folded into T3.2 with the compose logic).
> SDD §10 resolved: compose = **lean in-skill** (no separate analyst dispatch). Producer→consumer
> contract = new `tag-handler-group.schema.json` (a merged group spans captures, so it does not fit
> per-item `item-result.schema.json`).

- [x] **T3.1 `tag-handler-group.py` grouping helper + `tag-handler-group.schema.json`** `[activity: backend-api]`

  1. Prime: Read the interpreter/compose spec `[ref: SDD/Section 5; lines: 95-103]` and the `handled[]` shape.
  2. Test (RED): `group_handled` bins by `(handler, target_path)` (merge same-key, split different-key, deterministic order, null target, empty→[]); `compose_field_template` mechanical join, no LLM; group-result schema accept + reject (missing composed_block, empty source_paths).
  3. Implement: Deterministic, pure `tomo/scripts/tag-handler-group.py` (group stubs + mechanical compose) + `tomo/schemas/tag-handler-group.schema.json` (group-result contract: composed_block, source_paths, target nullable).
  4. Validate: 33 unit tests pass; pure (no LLM/network); lint clean.
  5. Success: Handled items grouped per (handler, target) for compose `[ref: PRD/FR-7; lines: 66-67]`.

- [x] **T3.2 `tag-handler-interpreter` skill + conductor wiring (lean in-skill compose)** `[activity: backend-api]`

  1. Prime: Read the compose contract `[ref: SDD/Section 5; lines: 97-101]`, the FR-8 merge requirement `[ref: PRD/FR-8; lines: 68-69]`, the `suggest-handling` skill + suggestion-conductor patterns.
  2. Test (skill — validated by skill-author audit + spec-compliance, not unit-TDD): loaded by the conductor only on non-empty `routing-plan.handled`; runs the grouping helper; LLM directive → ONE merged dated block per group (cardinality 1, not per-item — STRICT); field-template → mechanical join (no LLM); writes group-result JSON conforming to the schema.
  3. Implement: Author `tomo/dot_claude/skills/tag-handler-interpreter/SKILL.md` (imperative-only) + wire the conductor conditional load + a `docs/tomo/` WHY-doc.
  4. Validate: skill-author audit clean; runtime file imperative-only with WHY in docs/tomo; conductor edit minimal + additive.
  5. Success: A group composes to exactly one merged update `[ref: PRD/FR-8; lines: 68-69]` `[ref: PRD/AC-3; lines: 109-110]`.

- [x] **T3.3 `suggestions-reducer.py` — render group as a suggestion item** `[activity: frontend-ui]`

  1. Prime: Read the reducer/suggestion-render spec `[ref: SDD/Section 5; lines: 101-103]` and `[ref: PRD/FR-9; lines: 72-73]`.
  2. Test (RED): one group → one suggestion item (proposed block + target + marker + `Approve` box); multi-capture group → merged block with cardinality 1; two groups → two suggestion items; reuses the existing suggestions-doc format.
  3. Implement: Extend `suggestions-reducer.py` to render each composed group as a suggestion item.
  4. Validate: `./venv/bin/python` reducer tests pass against a live-render fixture; lint clean.
  5. Success: Each group is a reviewable suggestion in the suggestions doc `[ref: PRD/FR-9; lines: 72-73]` `[ref: PRD/AC-3; lines: 109-110]`.

- [x] **T3.4 Phase Validation** `[activity: validate]`

  - Run all Phase 3 tests under `./venv/bin/python`. Verify the merge-cardinality gate (a group of N captures → one suggestion) against SDD §5 / AC-3. Lint clean. **Gate: merged status update from a group (AC-3).**

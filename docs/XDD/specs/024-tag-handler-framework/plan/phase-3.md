---
title: "Phase 3: Pass-1 compose + suggestion"
status: in_progress
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

- [ ] **T3.1 `tag-handler-interpreter` skill — group by (handler, target_path)** `[activity: backend-api]`

  1. Prime: Read the interpreter/compose spec `[ref: SDD/Section 5; lines: 95-103]` and the suggestion-conductor load pattern for conditional skills.
  2. Test (RED): conductor loads the interpreter **only** when `routing-plan.handled` is non-empty; grouping bins items by `(handler, target_path)`; two repos in one batch → two groups; conductor does **not** load the skill on an empty/absent `handled`.
  3. Implement: Author the `tag-handler-interpreter` skill (loaded by suggestion-conductor on non-empty `handled`) that groups `handled[]` by `(handler, target_path)`.
  4. Validate: grouping unit tests pass; cold-path (no handled) untouched; lint clean.
  5. Success: Handled items grouped per (handler, target) for compose `[ref: PRD/FR-7; lines: 66-67]`.

- [ ] **T3.2 Compose — LLM directive (merge) + field template (mechanical)** `[activity: backend-api]`

  1. Prime: Read the compose contract `[ref: SDD/Section 5; lines: 97-101]` and the FR-8 merge requirement `[ref: PRD/FR-8; lines: 68-69]`.
  2. Test (RED): LLM directive → one compose call receives the **whole group** (all captures' title/category/Summary/body) and returns one merged status-update markdown block; three captures → one block (cardinality 1, not 3); field-template compose → mechanical join, no LLM call; group of one → still one block.
  3. Implement: Implement the per-group compose dispatch (LLM directive path + mechanical field-template path) inside the interpreter flow.
  4. Validate: compose tests pass (merge cardinality asserted); no LLM invoked on the field-template path; lint clean.
  5. Success: A group composes to exactly one merged update `[ref: PRD/FR-8; lines: 68-69]` `[ref: PRD/AC-3; lines: 109-110]`.

- [ ] **T3.3 `suggestions-reducer.py` — render group as a suggestion item** `[activity: frontend-ui]`

  1. Prime: Read the reducer/suggestion-render spec `[ref: SDD/Section 5; lines: 101-103]` and `[ref: PRD/FR-9; lines: 72-73]`.
  2. Test (RED): one group → one suggestion item (proposed block + target + marker + `Approve` box); multi-capture group → merged block with cardinality 1; two groups → two suggestion items; reuses the existing suggestions-doc format.
  3. Implement: Extend `suggestions-reducer.py` to render each composed group as a suggestion item.
  4. Validate: `./venv/bin/python` reducer tests pass against a live-render fixture; lint clean.
  5. Success: Each group is a reviewable suggestion in the suggestions doc `[ref: PRD/FR-9; lines: 72-73]` `[ref: PRD/AC-3; lines: 109-110]`.

- [ ] **T3.4 Phase Validation** `[activity: validate]`

  - Run all Phase 3 tests under `./venv/bin/python`. Verify the merge-cardinality gate (a group of N captures → one suggestion) against SDD §5 / AC-3. Lint clean. **Gate: merged status update from a group (AC-3).**

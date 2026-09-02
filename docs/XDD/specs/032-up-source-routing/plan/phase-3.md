---
title: "Phase 3: Route and emit"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Route and emit

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples; "The routing branch"]` — including the `_MISSING` sentinel
- `[ref: SDD/Implementation Examples; "Constructing value and expected — traced walkthrough"]` — the three-row table is this phase's core test matrix
- `[ref: SDD/Implementation Examples; "expected_absent is not reachable here"]`
- `[ref: SDD/Architecture Decisions; ADR-2, ADR-3, ADR-5, ADR-6]`
- `[ref: PRD/Feature 2]`, `[ref: PRD/Feature 3]`, `[ref: PRD/Feature 6]`, `[ref: PRD/Business rules 2-8]`
- Source to read: `garden-audit-parser.py:520-542` (both decision branches today), `lib/render_actions.py:1215-1240` (the `garden_action` dispatch)

**Key Decisions**:
- **ADR-5** — the fallback to a body-oriented action is **forbidden**, not merely discouraged. It reproduces the defect while looking like graceful degradation.
- **ADR-3** — freshness is tested with a `_MISSING` sentinel. `up_value: None` is legitimate.
- **ADR-6** — the property name is derived, never hardcoded.
- "Remove" is usually `operation: "set"`. `remove` deletes the whole property and is correct only when the broken link is its sole content.

**Dependencies**: Phase 2. Independent of Phase 4.

---

## Tasks

The behavioural change. Everything before this was plumbing.

- [ ] **T3.1 The routing branch** `[activity: backend-logic]`

  1. **Prime**: Read the routing-branch example `[ref: SDD/Implementation Examples]` in full, including why `detail.get("up_value")` is the wrong idiom.
  2. **Test** (RED) — the full matrix, both sites × both choices:
     - inline + remove → `remove_up_link`, byte-identical to today `[ref: PRD/AC-F2.3]`
     - inline + repoint → `add_relationship`, byte-identical to today `[ref: PRD/AC-F2.3]`
     - frontmatter + remove → `edit_frontmatter` `[ref: PRD/AC-F2.1]`
     - frontmatter + repoint → `edit_frontmatter` `[ref: PRD/AC-F2.2]`
     - a mixed batch → each finding routes by its own note `[ref: PRD/AC-F2.4]`
     - `up_value` key **absent** → no action, finding recorded unroutable with reason `stale-cache` `[ref: PRD/AC-F6.1]`
     - `up_value` present and `None` → **not** treated as stale; the sentinel test distinguishes them `[ref: SDD/ADR-3]`
     - `up_source` absent or `None` on a broken finding → unroutable with reason `no-declaration-site`, never a guessed branch
     - **no test path emits a body-oriented action for a frontmatter finding, in any of the above** — assert this directly, not by inspection `[ref: ADR-5]`
  3. **Implement**: the branch in `garden-audit-parser.py`, with a module-level `_MISSING` sentinel and an `unroutable` collection.
  4. **Validate**: unit tests pass; `ruff` clean; `# version:` bumped.
  5. **Success**:
     - [ ] Inline behaviour is untouched `[ref: CON-7]`
     - [ ] The forbidden fallback cannot occur `[ref: PRD/Business rule 6]`

- [ ] **T3.2 `value` and `expected` construction** `[activity: backend-logic]`

  1. **Prime**: Read the traced walkthrough `[ref: SDD/Implementation Examples]`. Its three rows are the required cases; the fourth column states the intended effect on the note.
  2. **Test** (RED) — reproduce the walkthrough's fixture verbatim (`["[[Alte MOC]]", "[[Reisen (MOC)]]"]`, broken target `Alte MOC`):
     - repoint → `operation: "set"`, `value == ["[[Neue MOC]]", "[[Reisen (MOC)]]"]`, `expected == ["[[Alte MOC]]", "[[Reisen (MOC)]]"]` — the sibling survives **in position** `[ref: PRD/AC-F3.2]`
     - remove with a sibling → `operation: "set"`, `value == ["[[Reisen (MOC)]]"]`
     - remove as sole entry → `operation: "remove"`, no `value` `[ref: SDD/Implementation Gotchas]`
     - scalar property, repoint → `value` is a **scalar**, not a one-item list `[ref: PRD/Edge case: scalar]`
     - scalar property, remove → `operation: "remove"`
     - the broken entry appearing twice → both transformed; `expected` is still the observed list verbatim
     - `expected` is byte-for-byte the observed value in every case, order included `[ref: PRD/AC-F3.1, AC-F3.2]`
     - a map-shaped `up_value` → unroutable, not transformed `[ref: SDD/Complex Logic]`
     - **`expected_absent` is never emitted** — assert on every produced action `[ref: SDD/"expected_absent is not reachable here"]`
  3. **Implement**: the transform, preserving shape and order by mutating a copy of the observed value rather than rebuilding it.
  4. **Validate**: unit tests pass.
  5. **Success**:
     - [ ] A legitimate sibling parent is never deleted `[ref: PRD/Edge case: list with several entries]`
     - [ ] Shape is preserved `[ref: PRD/Business rule 4]`

- [ ] **T3.3 `edit_frontmatter` emission** `[activity: backend-logic]`

  1. **Prime**: Read the `garden_action` dispatch at `render_actions.py:1215-1240` and the action contract `[ref: SDD/Constraints; CON-1]`.
  2. **Test** (RED):
     - a routed finding produces one `edit_frontmatter` with `path`, `property`, `operation`, `expected` and, for `set`, `value`
     - `property` is derived via `marker_word(parent_marker)` — a profile configured with a different marker yields a different property name `[ref: PRD/AC-F2.5, ADR-6]`
     - `additionalProperties` are never added — no `stem`, no `title`, no provenance `[ref: CON-1]`
     - IDs come from the shared counter, monotonic
     - the emitted set validates against `tomo/schemas/instructions.schema.json` once Phase 4 lands
  3. **Implement**: `_build_edit_frontmatter_actions` plus the dispatch branch.
  4. **Validate**: unit tests pass; `# version:` bumped.
  5. **Success**: the action matches the shipped contract exactly `[ref: CON-1]`

- [ ] **T3.4 Stale-cache withholding** `[activity: backend-logic]`

  1. **Prime**: `[ref: PRD/Feature 6]` and **ADR-5**. Withholding is the *specified* behaviour, not a failure mode.
  2. **Test** (RED):
     - a pre-change cache entry → no `edit_frontmatter` **and** no `remove_up_link`/`add_relationship` for that finding `[ref: PRD/AC-F6.1, AC-F6.3]`
     - the finding is recorded as unroutable with the reason
     - other findings in the same run are unaffected
     - after the entry gains `up_value`, the same finding routes normally `[ref: PRD/AC-F6.4]`
  3. **Implement**: covered by T3.1's branch; this task is the dedicated test surface and any reporting hook the parser owes Phase 5.
  4. **Validate**: unit tests pass.
  5. **Success**: a stale cache degrades **visibly**, never silently and never wrongly `[ref: ADR-5]`

- [ ] **T3.5 Phase Validation** `[activity: validate]`

  - Full suite green. Walk the SDD's traced walkthrough table and confirm each row has a named test. Confirm by grep that no code path maps a `frontmatter` finding to `remove_up_link` or `add_relationship`. `ruff` clean.

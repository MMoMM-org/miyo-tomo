---
title: "Phase 3: The cases the pass cannot reach"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: The cases the pass cannot reach

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/The boundary this design does NOT cross]` — why Phase 2's pass cannot fix this
- `[ref: SDD/Implementation Examples; Why P3 cannot use the pass]`
- `[ref: SDD/Architecture Decisions; ADR-5]`
- `[ref: PRD/Feature 3]` and `[ref: PRD/Feature 4]`
- `tomo/scripts/lib/render_actions.py` — `_build_insert_under_marker_actions`, site 4
- `tomo/scripts/suggestions-reducer.py` — `annotate_tag_handler_group_guards`

**Key Decisions**:
- **ADR-5** — the insert builder and the delete loop call **one shared predicate**. Two independent
  `if` statements is how these sites diverged in the first place.
- Phase 2's pass handles a partner that was *emitted and later dropped*. Here the insert is **never
  built**, so no id exists for the delete to name and `depends_on` cannot express the dependency.
- Consent and emission are one failure (owner decision, 2026-09-09): approval collected under a
  false premise belongs with the emission it authorises.

**Dependencies**:
- **None.** This phase shares no code with the `depends_on` machinery and may run before,
  after, or concurrently with Phases 1 and 2.

---

## Tasks

Closes the third data-loss path and the consent defect that makes it dangerous.

- [ ] **T3.1 One appliability predicate, two call sites** `[parallel: true]` `[activity: domain-modeling]`

  Today `_build_insert_under_marker_actions` skips a group whose `target_path` is falsy, while the
  site-4 delete loop reads `target` only to interpolate a reason string and never skips. The result
  is N deletes and zero inserts.

  1. Prime: read both loops and the skip comment they already disagree about
     `[ref: SDD/Implementation Examples; Why P3 cannot use the pass]`.
  2. Test:
     - an approved group with **no** resolvable target emits **zero** `insert_under_marker` **and
       zero** `delete_source`;
     - a group of three sources with no target emits **zero** deletes — not one, not two;
     - an approved group **with** a resolvable target emits one insert and one delete per source,
       exactly as today;
     - the predicate is called by both sites, so a future change to the condition cannot move only
       one of them.
  3. Implement: extract `tag_handler_group_is_appliable(group)` and call it from both loops.
  4. Validate: unit tests pass; ruff clean; existing tag-handler tests unchanged.
  5. Success:
     - [ ] No delete is emitted for an unresolvable group `[ref: PRD/F3-AC1]`
     - [ ] A resolvable group behaves exactly as before `[ref: PRD/F3-AC2]`
     - [ ] The count attributable to an unresolvable group is zero `[ref: PRD/F3-AC3]`

- [ ] **T3.2 An unresolvable group is not pre-approved** `[parallel: true]` `[activity: frontend-ui]`

  `annotate_tag_handler_group_guards` returns early on a null target **before** it can set a guard,
  so the guards that would suppress the Approve control are never set and the control renders
  pre-checked — on a group whose own target line reads "(unresolved — check handler config)".

  1. Prime: read the early return and the Approve-suppression path it bypasses
     `[ref: PRD/Problem Statement]`.
  2. Test:
     - a group with a null target carries a guard naming the reason after annotation;
     - its Approve control is **not** pre-selected in the rendered document;
     - a group whose target resolves **and** whose marker is present renders its Approve control
       byte-identically to today;
     - the reason is visible in the group itself, not only in a summary elsewhere.
  3. Implement: set the guard before returning; leave the existing suppression path to consume it.
  4. Validate: unit tests pass; ruff clean; existing reducer tests unchanged.
  5. Success:
     - [ ] An unresolvable group carries a guard and is not pre-selected `[ref: PRD/F4-AC1]`
     - [ ] A healthy group renders unchanged `[ref: PRD/F4-AC2]`
     - [ ] The reason is visible in the group `[ref: PRD/F4-AC3]`

  **Pairing note**: the healthy-case criterion is not padding. Blanket-suppressing the control would
  pass the first criterion and fail the second, and that is the only thing separating this fix from
  a new defect.

- [ ] **T3.3 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean.
  - Reproduce **Bug B** end to end through the real reducer render, real parser and real
    `build_actions`: an approved group with a null target now yields zero deletes and zero inserts,
    where it previously yielded N deletes.
  - Confirm the Approve control for that same group is unticked and carries its reason.

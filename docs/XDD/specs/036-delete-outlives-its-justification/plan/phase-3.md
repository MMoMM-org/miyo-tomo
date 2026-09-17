---
title: "Phase 3: The cases the pass cannot reach"
status: completed
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
- **T3.1 must precede T1.3.** Corrected 2026-09-10 by validation: both touch
  `_build_insert_under_marker_actions` and site 4 of `_build_delete_source_actions`, so they collide
  on concurrent dispatch — and worse, T1.3 alone would give the unresolvable-group delete
  `depends_on: []`, which means "perform it", so Phase 4's audit would certify a data-loss delete as
  valid. Running T3.1 first makes an empty list on that path unreachable.
- **T3.2 is genuinely independent** of Phases 1 and 2 — it touches only `suggestions-reducer.py`.
- Phase 3 as a whole does not depend on Phase 2.

---

## Tasks

Closes the third data-loss path and the consent defect that makes it dangerous.

- [x] **T3.1 One appliability predicate, two call sites** `[activity: domain-modeling]`

  **Executed inside Phase 1 on 2026-09-16**, ahead of T1.3, per the approved deviation in
  `plan/README.md`. Shipped as `_tag_handler_group_has_resolvable_target` — renamed from the
  `tag_handler_group_is_appliable` this task names, see Deviations. Commits `4efcc03`, `ff5d149`.

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
     - [x] No delete is emitted for an unresolvable group `[ref: PRD/F3-AC1]`
     - [x] A resolvable group behaves exactly as before `[ref: PRD/F3-AC2]`
     - [x] The count attributable to an unresolvable group is zero `[ref: PRD/F3-AC3]`

- [x] **T3.2 An unresolvable group is not pre-approved** `[parallel: true]` `[activity: frontend-ui]`

  Landed `4d1f329`. `suggestions-reducer.py` `1.46.1` -> `1.47.0`. Seven new tests, two inverted in
  place. The plan's step 3a is **unimplementable as written** — see Deviations: there are two early
  returns, not one, and the `client is None` return skips the loop entirely, so no placement inside
  the loop could have worked.

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
  3. Implement — **the existing suppression path will NOT consume a new value as-is.** Corrected
     2026-09-10 by validation: `suggestions-reducer.py:973-988` branches on exactly two string
     literals, `target_missing` and `marker_missing`; **any third value falls through to
     `lines.append("- [x] Approve")` at `:1000`** and the group still renders pre-checked. Reusing
     `target_missing` is not the escape — it renders *"Target note doesn't exist — [[]] is not in
     the vault"* with an empty link, because `link` is `""` when `target_path` is null.
     a. Set `guard = "target_unresolved"` before the early return.
     b. Add a **third branch** to the suppression path with its own message, matching the
        `*(unresolved — check handler config)*` target line already rendered at `:945`.
     c. Register the value in the tally dict at `:1569` — it is literal-initialised and read by
        three f-string keys at `:2405-2407`, so an unregistered value survives `tally.get` but never
        prints.
     Nothing else needs registering: no schema types the `guard` field, and Hashi has no reference
     to it at all.
  4. Validate: unit tests pass, including a new third case in
     `tests/test_tag_handler_group_guards.py`; ruff clean; existing reducer tests unchanged.
  5. Success:
     - [x] An unresolvable group carries a guard and is not pre-selected `[ref: PRD/F4-AC1]`
     - [x] A healthy group renders unchanged `[ref: PRD/F4-AC2]`
     - [x] The reason is visible in the group `[ref: PRD/F4-AC3]`

  **Pairing note**: the healthy-case criterion is not padding. Blanket-suppressing the control would
  pass the first criterion and fail the second, and that is the only thing separating this fix from
  a new defect.

- [x] **T3.3 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean.
  - Reproduce **Bug B** end to end through the real reducer render, real parser and real
    `build_actions`: an approved group with a null target now yields zero deletes and zero inserts,
    where it previously yielded N deletes.
  - Confirm the Approve control for that same group is unticked and carries its reason.

  **Result, 2026-09-17** — `tests/test_036_t3_3_phase_validation.py`, commits `41595ef`,
  `9adc673` and the docstring correction that followed. Suite **4147 passed, 4 skipped, 0
  failed** (4151 collected, exactly +6 on the phase's baseline of 4145); `ruff` clean.

  Spec compliance FAILED this task once, on the rule the brief itself set: four assertions
  shipped as bare `assert` with no message, on a path where a wrong outcome sends the user's
  only copy of a note to `vault.trash`. Fixed in `9adc673` and re-verified — the fix was
  proven message-only by diff (every removed line reappears byte-identical up to the added
  `, (`), so no comparison was widened or narrowed while adding prose.

  Bug B reproduced through the real chain — `annotate_tag_handler_group_guards` ->
  `render_tag_handler_updates_block` -> `parse_tag_handler_groups` -> `build_actions` — with a
  three-source null-target group (not one source; N=1 would hide the shape of the damage):

  | | Real Pass-2 gate (Test A) | Bypassed gate, real predicate (Test B) | Bypassed gate, patched predicate (Test B) |
  |---|---|---|---|
  | Approved ids | `[]` (no Approve box rendered) | `[gid]` passed directly — simulates a doc confirmed before T3.2 | `[gid]` |
  | `insert_under_marker` | 0 | 0 | **1**, `target_path: None` |
  | `delete_source` | 0 | 0 | **3** (one per source) |

  **The before state was measured, not inferred.** The same three-source null-target fixture was run
  through the same real chain against a checkout of the pre-T3.1 commit, and against HEAD:

  | | pre-T3.1 (`3d52c1f`) | HEAD (T3.1 + T3.2) |
  |---|---|---|
  | `guard` after annotate | `<UNSET>` | `target_unresolved` |
  | Approve box present | **True** — pre-ticked | False |
  | parser approved ids | `['th-tsukai-none']` | `[]` |
  | `insert_under_marker` | 0 | 0 |
  | `delete_source` | **3** | **0** |

  Each pre-fix delete carried the reason *"Source consolidated into  by tsukai handler."* — note the
  empty gap where the target should be. The delete loop interpolated a target that did not exist and
  emitted anyway, once per source. Three notes to `vault.trash`, the consolidated content written
  nowhere, and the user shown the group already approved.

  Test B's patched column is the one honest deviation from the task brief's prediction, found by
  running the real code rather than assuming it: the brief expected 0 inserts / 3 deletes under the
  patch. Today both call sites hang off the one shared predicate and nothing else — T3.1 **replaced**
  the insert builder's standalone `if not target_path: continue` rather than keeping it alongside
  (ADR-5: "one shared predicate; two independent `if` statements is how these sites diverged in the
  first place"). Forcing that predicate open therefore reopens both sites symmetrically, a path-less
  insert **and** 3 deletes. The original asymmetry is no longer reproducible by patching one thing,
  which is the fix working as designed — and is why the pre-fix run above, not Test B, is what
  establishes the historical N-deletes-with-zero-inserts shape.

  **One attribution error caught in review and corrected**: Test A's docstring originally credited its
  zero result to T3.1. It is T3.2's. With nothing approved, both builders short-circuit on the
  approval check *before* `_tag_handler_group_has_resolvable_target` is ever called — the same
  upstream-gate trap the TDD guardian caught in this task's first test plan, resurfacing as prose.
  T3.1 is reached only by Test B, which forces a non-empty approved set precisely to get past that
  gate.

  Test C confirms the consent half on the same fixture: no `- [x] Approve` and no `- [ ] Approve` in
  the rendered block, `"Target unresolved"` present. Test D confirms the parser mechanism directly —
  a healthy sibling's id is yielded, the unresolved group's is not. Test E is the positive control
  (one insert + one delete per source for a normal approved group — without it, blanket suppression
  would pass A–D). Test F runs one unresolved and one healthy group through a single `build_actions`
  call to prove neither the unresolved group's 3 sources nor its absence leak into the healthy
  group's count (1 insert, 2 deletes, both attributable to the healthy group).

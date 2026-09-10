---
title: "Phase 2: Collect — the withdrawal pass"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Collect — the withdrawal pass

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples; The one withdrawal pass]` — including the traced walkthroughs
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-2, ADR-3, ADR-4]`
- `[ref: PRD/Feature 1]` and `[ref: PRD/Feature 2]`
- `tomo/scripts/instruction-render.py` — the five drop sites and their order
- `tomo/scripts/lib/render_actions.py` — `validate_destinations`, `_drop_moves_with_paired_deletes`

**Key Decisions**:
- **ADR-2** — one pass, after **all five** drop sites: `validate_destinations` (`:567`),
  `suppress_moves_for_unfiled_attachments` (`:585`), `filter_unresolvable_moc_links` (`:646`),
  `filter_missing_daily_notes` (`:713`), `filter_unappliable_relationships` (`:728`, defined in
  `render_resolve.py:829`). They span two modules, which is why the fifth went unnoticed.
- **ADR-3** — `create_moc` joins `move_note` as a claimant; both drop on a contest.
- **ADR-4** — the delete half of the path-keyed withdrawal is **retired**; the `link_to_moc`
  title-keyed half **stays** and is genuinely different in kind.
- One pass suffices, with no iteration: nothing declares a dependency on a delete, so withdrawing
  one cannot orphan anything else.

**Dependencies**:
- **Phase 1 complete.** The pass reads `depends_on`; without it the pass is a no-op.

**This is where P1 and Bug A actually stop happening.**

---

## Tasks

Turns the relation from Phase 1 into enforcement.

- [ ] **T2.1 The withdrawal pass** `[activity: domain-modeling]`

  1. Prime: read the pass and both traced walkthroughs `[ref: SDD/Implementation Examples]`.
  2. Test — each must fail before the implementation exists:
     - a delete naming a dropped action is withdrawn;
     - a delete naming a **surviving** action is kept;
     - a delete with `depends_on: []` is kept **under every guard outcome**;
     - a delete naming three ids of which **one** is missing is withdrawn (AND semantics);
     - `test_no_cascade_needed` — withdrawing a delete never causes a second withdrawal, proving one
       pass is sufficient;
     - non-delete actions are never touched;
     - the returned withdrawal records carry the missing id, the source path and the reason.
  3. Implement: `withdraw_unjustified_deletes(actions) -> (kept, withdrawn)` in
     `tomo/scripts/lib/render_actions.py`. Pure: no I/O, no Kado, no vault access.
  4. Validate: `./venv/bin/python -m pytest tests/test_036_withdraw_unjustified_deletes.py`;
     ruff clean.
  5. Success:
     - [ ] A withheld daily action's delete is withdrawn `[ref: PRD/F2-AC1]`
     - [ ] A multi-bucket origin withdraws when any one action is dropped `[ref: PRD/F2-AC2]`
     - [ ] An origin whose daily actions all survive keeps its delete `[ref: PRD/F2-AC3]`
     - [ ] An empty `depends_on` is never withdrawn `[ref: PRD/Edge Case Criteria]`

- [ ] **T2.2 `create_moc` becomes a claimant** `[activity: backend-api]`

  1. Prime: read `validate_destinations`' grouping loop and the T5.3 both-claimants rationale
     `[ref: SDD/Architecture Decisions; ADR-3]`. Note that `create_moc` carries `destination` under
     the same key `move_note` does, so grouping, case-folding and reporting work unchanged.
  2. Test: a `create_moc` and a `move_note` on one destination drop **both**; a case-only difference
     is still one contest; a `create_moc` alone on a destination is untouched; the clash report names
     both claimants and their kinds; `_paired_delete_candidates` contributes nothing for the MOC
     claimant and does not raise.
  3. Implement: widen the claimant filter to `{move_note, create_moc}`.
  4. Validate: unit tests pass; **every existing `validate_destinations` test still passes unchanged**.
  5. Success:
     - [ ] Two claimants on one destination both drop `[ref: PRD/F1-AC1]`
     - [ ] Case-only difference is one contest `[ref: PRD/F1-AC2]`
     - [ ] An uncontested `create_moc` is emitted unchanged `[ref: PRD/F1-AC3]`

- [ ] **T2.3 Place the pass, and retire the path-keyed delete withdrawal** `[activity: backend-api]`

  The riskiest task in the plan: it removes code stabilised by T5.3 and T5.5.

  1. Prime: read `_drop_moves_with_paired_deletes` in full, including the docstring's account of the
     T5.0c drift `[ref: SDD/Architecture Decisions; ADR-4]`. Identify precisely which half is the
     delete withdrawal (`_paired_delete_candidates`, `withdrawn_paths`) and which is the link
     withdrawal (`_orphaned_link_titles`) — **only the first is retired**.
  2. Test: with the pass in place, a contested destination produces byte-identical output to the
     pre-change behaviour for the delete half — same deletes withdrawn, same report contents; the
     `link_to_moc` withdrawal is **unchanged** and its tests still pass untouched; the audio-peer
     delete is still withdrawn; the T6.4c staging-note manifest rewrite is unaffected.
  3. Implement: call `withdraw_unjustified_deletes` in `instruction-render.py` after
     `filter_unappliable_relationships` and before `_validate_action_paths`; remove the delete half
     of the path join and its now-unused helpers.
  4. Validate: **full suite green** — this task's real gate is the pre-existing tests, not the new
     ones. Ruff clean.
  5. Success:
     - [ ] A contested move still withdraws its paired delete `[ref: PRD/F1-AC1]`
     - [ ] An audio peer's delete is withdrawn with its origin's `[ref: PRD/F1-AC4]`
     - [ ] A withheld clash still does not upload its staging note `[ref: PRD/F1-AC5]`
     - [ ] `link_to_moc` orphan withdrawal is untouched `[ref: SDD/Implementation Boundaries]`
     - [ ] Exactly one delete-withdrawal mechanism remains in the module `[ref: SDD/ADR-4]`

- [ ] **T2.4 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean.
  - Reproduce **P1** end to end with the real builder and real guards: assert the delete is absent
    from the emitted set, and that it was present before this phase.
  - Reproduce **Bug A** the same way: a daily action dropped for a missing daily note leaves no
    delete behind.
  - Confirm no emitted set contains a `delete_source` naming an id absent from that set.

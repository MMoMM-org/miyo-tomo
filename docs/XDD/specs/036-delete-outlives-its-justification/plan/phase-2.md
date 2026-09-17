---
title: "Phase 2: Collect — the withdrawal pass"
status: completed
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

- [x] **T2.1 The withdrawal pass** `[activity: domain-modeling]`

  Landed `bb840ca` as `render_actions.py:2354`; **not** wired into `instruction-render.py` — that is
  T2.3. Eleven tests (14 items) after the TDD guardian BLOCKed the plan's seven: a delete with **no**
  `depends_on` key at all was unconstructed by any of them, so an implementation reading absence as
  grounds to withdraw would have passed the lot. Version `0.20.0` → `0.21.0`.

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
     - [ ] An empty `depends_on` is never withdrawn `[ref: SDD/Edge Case Criteria]`

- [x] **T2.2 `create_moc` becomes a claimant** `[activity: backend-api]`

  Four commits — `81675a9`, `5bebab6`, `e456030`, `6a5afe4`. The filter widening is one line; the
  three consequences the plan does not name took the rest. See Deviations: a renderer fallback that
  was not kind-scoped and silently changed `move_note` output; a newly reachable `create_moc` vault
  collision with no test; and `link_to_moc` bullets left pointing at a MOC that will never be built.
  `render_actions.py` `0.21.0` → `0.23.1`, `render_md.py` `0.16.1` → `0.18.0`.

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

- [x] **T2.3 Place the pass, and retire the path-keyed delete withdrawal** `[activity: backend-api]`

  The riskiest task in the plan: it removes code stabilised by T5.3 and T5.5.

  **Plan wording correction (step 3.c)**: "remove ... and its now-unused helpers" is wrong.
  `_paired_delete_candidates` and the `withdrawn_paths` claim-once accumulator stay — they compute
  `withdrawn_deletes`, the report field `instructions-diff.py`'s `_subtract_withheld_moves` reads and
  six-plus existing tests pin. Only the removal `continue` inside `_drop_moves_with_paired_deletes`
  retires; the report bookkeeping (`removed_deletes.add(...)`) was already a separate statement
  sharing the same `if`, so no restructuring was needed to keep it. See
  `docs/tomo/scripts/lib/render_actions.md`, "What Stays, and Why".

  **Found beyond the retirement, both owner-approved and both recorded in this file's Deviations**:
  the pre-existing `test_the_clash_never_reaches_the_wire` fixture predates spec 036 and carries a
  `delete_source` with no `depends_on` key at all — T2.1's `or []` reading kept it, so it reached the
  wire, the exact outcome the guard exists to prevent. Corrected to fail closed: an absent or `None`
  `depends_on` now withdraws the delete, `depends_on: []` is unchanged (kept). Six pre-existing tests
  (three in `test_034_t5_3_destination_validation.py`, two in
  `test_034_t5_4_attachment_clash_suppression.py`, plus their `_diff()` helpers) needed the same
  one-line fix — call `withdraw_unjustified_deletes` on `kept` before checking or comparing it, since
  removal moved one step later than where those tests looked. A seventh,
  `test_034_t5_5_orphaned_moc_link.py::test_the_withdrawal_reconciles_with_the_coverage_audit`, had
  the identical gap and got the identical fix, despite step 2's instruction that its file's tests
  "still pass untouched" — judged a test-harness gap predating the T2.1/T2.3 split, not a retirement
  regression; verified against a clean worktree at the pre-T2.3 commit that the test passes there.
  `render_actions.py` `0.23.1` → `0.24.0` (retirement) → `0.25.0` (fail-closed reading).
  `instruction-render.py` `0.54.0` → `0.55.0`. New file
  `tests/test_036_t2_3_paired_delete_report_equivalence.py` proves the path-keyed report and the
  id-keyed removal agree by construction (over-report and under-report, both directions) rather than
  assumes it.

  1. Prime: read `_drop_moves_with_paired_deletes` in full, including the docstring's account of the
     T5.0c drift `[ref: SDD/Architecture Decisions; ADR-4]`. Identify precisely which half is the
     delete withdrawal (`_paired_delete_candidates`, `withdrawn_paths`) and which is the link
     withdrawal (`_orphaned_link_titles`) — **only the first is retired**.
  2. Test: with the pass in place, a contested destination produces byte-identical output to the
     pre-change behaviour for the delete half — same deletes withdrawn, same report contents; the
     `link_to_moc` withdrawal is **unchanged** and its tests still pass untouched; the audio-peer
     delete is still withdrawn; the T6.4c staging-note manifest rewrite is unaffected.
  3. Implement, **in this order** — the repo rule is strip-first destroys institutional knowledge
     (`CLAUDE.md`, the `docs/tomo/` WHY-persistence rule):
     a. **First** write the WHY into `docs/tomo/scripts/lib/render_actions.md`: why the path-keyed
        delete withdrawal existed, the T5.0c drift its docstring recorded, and why an id-keyed pass
        supersedes it. The docstring being removed is the only place that history currently lives.
     b. Then call `withdraw_unjustified_deletes` in `instruction-render.py` after
        `filter_unappliable_relationships` and before `_validate_action_paths`.
     c. Then remove the delete half of the path join and its now-unused helpers.
  4. Validate: **full suite green** — this task's real gate is the pre-existing tests, not the new
     ones. Ruff clean.
  5. Success:
     - [x] A contested move still withdraws its paired delete `[ref: PRD/F1-AC1]`
     - [x] An audio peer's delete is withdrawn with its origin's `[ref: PRD/F1-AC4]`
     - [x] A withheld clash still does not upload its staging note `[ref: PRD/F1-AC5]`
     - [x] `link_to_moc` orphan withdrawal is untouched `[ref: SDD/Implementation Boundaries]`
     - [x] Exactly one delete-withdrawal mechanism remains in the module `[ref: SDD/ADR-4]`
     - [x] The T5.0c rationale survives in `docs/tomo/` before the docstring is removed `[ref: SDD/Directory Map]`

- [x] **T2.4 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean.
  - Reproduce **P1** end to end with the real builder and real guards: assert the delete is absent
    from the emitted set, and that it was present before this phase.
  - Reproduce **Bug A** the same way: a daily action dropped for a missing daily note leaves no
    delete behind.
  - Confirm no emitted set contains a `delete_source` naming an id absent from that set.

  **Result, 2026-09-17** — `tests/test_036_t2_4_phase_validation.py`, commit `1325d77`. Suite
  **4132 passed, 0 failed**; `ruff` clean.

  Both paths reproduced through the real builder and the real guards, with the before/after inside
  one test rather than asserted about the past:

  | | P1 — contested destination | Bug A — missing daily note |
  |---|---|---|
  | After `build_actions` | `I03 delete_source depends_on: ["I02"]` | `I02 delete_source depends_on: ["I01"]` |
  | Guard drops | `validate_destinations` drops **both** claimants | `filter_missing_daily_notes` drops `I01` |
  | Before the pass | delete still present, still naming the dropped id | delete still present, still naming the dropped id |
  | After the pass | **withdrawn**, `missing_dependencies: ["I02"]` | **withdrawn**, `missing_dependencies: ["I01"]` |

  Both match the SDD's traced walkthroughs id for id.

  **The proof the tests can fail.** With `withdraw_unjustified_deletes` bypassed, both tests fail on
  the surviving delete — *"P1 must not reproduce: delete_source is absent from the emitted set; got
  [{'id': 'I03', … 'depends_on': ['I02'] …}]"* and the matching one for Bug A. A phase validation
  that still passed with the phase's own mechanism disabled would prove nothing.

  **One honest limitation**, reported rather than hidden: the dangling-id assertion holds **trivially**
  in both scenarios, because each final set contains no `delete_source` at all. The assertion is real
  and would fire, but these two fixtures do not exercise it. It was therefore also run against both
  golden action sets, which carry **ten** real deletes between them — `034-t5-3-actions-golden` and
  `034-t5-4-duplicate-reference-golden` — with zero dangling ids and zero missing `depends_on`. The
  enforcing audit (`assert_no_dangling_dependencies`) belongs to Phase 4 and was deliberately not
  built here.

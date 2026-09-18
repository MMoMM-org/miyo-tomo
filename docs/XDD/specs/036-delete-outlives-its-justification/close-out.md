# Spec 036 — close-out record (T4.6)

Written 2026-09-18, after T4.4 proved all three measured data-loss paths in one end-to-end run and
the suite came back green. Recorded here rather than in the plan because it walks a table the plan
only points at, following specs 034 and 035.

Two corrections to the plan's own wording before the tables:

- T4.6 says "every PRD criterion in **F1–F6**". F1–F6 is 23 criteria, not the 25 the plan's
  coverage table counts — the other 2 are F7, a `Could Have` deferred by decision. All 25 are
  accounted for below; 21 carry a Tomo-side test, 2 are consumer-owned, 2 are deferred.
- The plan's coverage table maps criteria to **tasks**. This document maps them to **tests that
  were executed**, which is a different claim. Every node id below was run on this checkout and
  observed green; none is quoted from a plan file.

## Quality Requirements (SDD)

| Quality | Target | Measured |
|---|---|---|
| Performance | One O(n) pass, no Kado calls, no I/O; immeasurable against existing runtime | ✅ `withdraw_unjustified_deletes` is pure — `test_036_withdraw_unjustified_deletes.py::test_input_list_is_not_mutated`, `::test_no_cascade_needed_single_pass_semantics` (one pass suffices). Full suite 4235 tests in 103.77 s, unchanged in shape from the 4147 recorded at Phase 3 |
| Usability | A withdrawn delete is reported with the missing partner id and the guard that removed it, in both stderr and markdown; a markdown-only reader can tell a deliberate omission from a missing feature | ✅ `test_036_t4_3_withdrawal_reporting.py::TestStderrReporting::test_daily_withdrawal_reports_missing_id_and_guard_on_stderr` and `::TestMarkdownSkippedSection::test_withdrawal_renders_inside_existing_skipped_heading`. The markdown half is deliberately **not** the stderr text — `::TestUserFacingWithdrawalWording::test_user_facing_wording_names_no_guard_or_id` pins that the reader-facing sentence carries neither an action id nor a guard function name (ADR-11), and `::test_technical_sibling_is_unchanged_and_still_carries_the_guard_name` pins that the technical surface still does |
| Security / Privacy | Reports carry ids, kinds, counts, vault-relative paths — never content | ✅ `::TestConstitutionL2MetadataOnly::test_note_content_never_reaches_any_surface` and `::test_reason_threaded_verbatim_is_the_builder_template` — two guards, the second closing the "reworded reason" escape the first cannot see |
| Reliability | Zero emitted sets in which a surviving `delete_source` names an absent id; zero deletes for a tag-handler group with no resolvable target | ✅ `test_instruction_render_wire_hygiene.py::TestAssertNoDanglingDependencies` (8 cases) plus `::TestAssertNoDanglingDependenciesIntegration` (exit 2, no file written, each with an unpatched control run); `test_tag_handler_group_instruction_linkage.py::test_unresolvable_target_three_sources_emits_zero_deletes` |

### The row the suite cannot make vacuous

The Reliability row is enforced by an audit whose **both failure modes are unreachable through the
real pipeline** — the withdrawal pass removes every delete the audit would catch, missing-key ones
included. A pipeline test asserting "no violations" therefore passes whether or not the audit
exists. This is why the integration tests patch `_ir.withdraw_unjustified_deletes` in
`instruction-render`'s own namespace and each carries an **unpatched control** asserting exit 0 and
a written file: without the control, a patch bound to the wrong namespace leaves both runs
identical and the test proves nothing. Recorded because the green tick above is only worth what
that construction is worth.

## PRD Acceptance Criteria — F1 through F6 (23)

### F1 — A contested destination withdraws both claimants and their deletes (5)

| AC | Statement | Proving test | Status |
|---|---|---|---|
| F1-AC1 | `create_moc` + `move_note` on one destination: neither emitted, paired delete not emitted, clash names both claimants | `tests/test_036_t2_4_phase_validation.py::test_p1_contested_destination_emits_no_orphaned_delete` — real builder, all five drop sites in real order, then the withdrawal pass | ✅ |
| | | Clause-by-clause siblings: `tests/test_034_t5_3_destination_validation.py::test_create_moc_and_move_note_on_one_destination_drop_both` (neither emitted), `::test_clash_report_names_both_claimants_and_their_kinds` (both named, with kinds) | ✅ |
| F1-AC2 | A case-only difference is still one contested destination | `tests/test_034_t5_3_destination_validation.py::test_create_moc_and_move_note_case_only_difference_is_one_contest` | ✅ |
| F1-AC3 | An uncontested `create_moc` is emitted unchanged and withdraws no delete | `tests/test_034_t5_3_destination_validation.py::test_create_moc_alone_on_a_destination_is_untouched` | ✅ |
| F1-AC4 | A contested move carrying an audio peer withdraws the peer's delete too | `tests/test_036_t2_3_paired_delete_report_equivalence.py::test_audio_peer_delete_still_withdrawn_with_its_origin` — proves the id-keyed pass reproduces what the retired path-keyed join did; `tests/test_034_t5_3_destination_validation.py::test_a_dropped_move_withdraws_its_audio_peer_delete` is the pre-existing pin it had to match | ✅ |
| F1-AC5 | A staging note only the dropped move would have filed is not uploaded | `tests/test_034_t6_4c_withheld_clash_staging_residue.py::test_withheld_clash_uploads_no_staging_note`, and the widened-claimant case (a dropped `create_moc`'s staging note) in `tests/integration/test_036_delete_justification_e2e.py::test_all_three_data_loss_paths_in_one_run_emit_no_delete`, which reads the real `manifest.json` the run wrote | ✅ |

### F2 — A withheld daily action withdraws the delete it justified (4)

| AC | Statement | Proving test | Status |
|---|---|---|---|
| F2-AC1 | Daily note absent → daily action withheld → that origin's `delete_source` is not emitted | `tests/test_036_t2_4_phase_validation.py::test_bug_a_missing_daily_note_leaves_no_delete_behind` — asserts the **pre-phase** state explicitly (the delete is still present immediately after the guard that removed its justification) before asserting it is gone after the pass | ✅ |
| | | End to end through `instruction-render.py:main()` against a cloned vault slice: `tests/integration/test_036_delete_justification_e2e.py::test_all_three_data_loss_paths_in_one_run_emit_no_delete` (P2) | ✅ |
| F2-AC2 | Entries across several buckets or days: any one withheld → no delete | `tests/test_036_t2_4_phase_validation.py::test_bug_a_one_of_several_daily_notes_missing_still_withdraws_the_delete` — three daily actions over three buckets and two days, real `filter_missing_daily_notes` drops exactly one, delete withdrawn naming that one id. Closed 2026-09-18 (`4a25c86`). The two composing halves remain: `test_036_depends_on_emission.py::test_origin_with_entries_across_several_buckets_and_several_days_names_all_of_them` and `test_036_withdraw_unjustified_deletes.py::test_one_missing_of_three_withdraws` | ✅ |
| F2-AC3 | All daily actions emitted → the delete is emitted unchanged | `tests/test_036_withdraw_unjustified_deletes.py::test_all_three_present_is_kept`; the run-level form is `tests/integration/test_036_delete_justification_e2e.py::test_healthy_run_emits_its_deletes_and_withdraws_nothing`, which asserts four justified deletes ship and the `delete_source` key set is unchanged apart from the new field | ✅ |
| F2-AC4 | The withheld action and the withdrawn delete are reported together, not in unrelated sections | `tests/test_036_t4_3_withdrawal_reporting.py::TestMarkdownSkippedSection::test_f2_ac4_daily_skip_and_delete_withdrawal_are_structurally_grouped` — **structural** adjacency, not co-occurrence in one document. `::test_multi_cause_same_guard_withdrawal_renders_under_both_daily_bullets` is the regression pin for the live defect T4.3 shipped and code quality caught | ✅ |

### F3 — A tag-handler group with no resolvable target emits no delete (3)

| AC | Statement | Proving test | Status |
|---|---|---|---|
| F3-AC1 | Absent `target_path` → no `delete_source` for any source, and no `insert_under_marker` | `tests/test_tag_handler_group_instruction_linkage.py::test_unresolvable_target_group_emits_zero_insert_and_zero_delete`; through the real reducer render + real parser + real `build_actions`: `tests/test_036_t3_3_phase_validation.py::test_a_unresolved_group_through_real_gate_emits_nothing` | ✅ |
| F3-AC2 | A resolvable target still emits one insert and one delete per source | `tests/test_tag_handler_group_instruction_linkage.py::test_resolvable_target_group_unaffected_one_insert_one_delete_per_source`; the end-to-end positive control is `tests/test_036_t3_3_phase_validation.py::test_e_positive_control_healthy_group_emits_insert_and_deletes` | ✅ |
| F3-AC3 | Three sources, absent target → the count is zero, not one or two | `tests/test_tag_handler_group_instruction_linkage.py::test_unresolvable_target_three_sources_emits_zero_deletes` | ✅ |

`::test_both_sites_move_together_when_the_predicate_says_no` is the ADR-5 pin underneath all three:
it monkeypatches the shared appliability predicate on an otherwise healthy group and requires both
outputs to move together, so a site that stopped consulting the predicate fails even when its own
input still looks resolvable.

### F4 — An unresolvable group is never presented as pre-approved (3)

| AC | Statement | Proving test | Status |
|---|---|---|---|
| F4-AC1 | Unresolvable target → the group carries a guard naming the reason, and Approve is not pre-selected | `tests/test_tag_handler_group_guards.py::test_guard_null_target_sets_target_unresolved_with_client` (the guard is set, where the early return previously skipped it) and `::test_render_target_unresolved_no_approve_box` (the control is not rendered pre-checked). `::test_guard_null_target_sets_target_unresolved_no_client` covers the second early return the plan did not know about | ✅ |
| F4-AC2 | A healthy group's Approve control renders exactly as today | `tests/test_tag_handler_group_guards.py::test_render_healthy_group_byte_identical_to_frozen_literal` — a frozen literal, so a blanket suppression fails it. `::test_render_ok_keeps_approve_box` and `::test_render_absent_guard_keeps_approve_box` are the narrower siblings | ✅ |
| F4-AC3 | The reason is visible in the group itself | `tests/test_tag_handler_group_guards.py::test_render_target_unresolved_reason_message`; in the rendered document, `tests/test_036_t3_3_phase_validation.py::test_c_rendered_block_has_no_approve_control_and_carries_reason` | ✅ |

### F5 — Every delete names the actions that justify it (6: 4 Tomo, 2 consumer)

| AC | Statement | Proving test | Status |
|---|---|---|---|
| F5-AC1 | Any emitted `delete_source` carries a dependency field naming the justifying action ids | `tests/test_hashi_instructions_schema.py::test_delete_source_missing_depends_on_fails` — parametrized over **both** the mirror and the producer schema, and it is the test that separates "required" from "present in the schema". Per site: `tests/test_036_depends_on_emission.py::test_single_atomic_origin_names_its_one_move_id` (site 3), `::test_origin_with_one_accepted_daily_entry_names_that_entry_action_id` (site 2), `tests/test_tag_handler_group_instruction_linkage.py::test_site4_depends_on_is_never_empty_for_an_emitted_delete` (site 4), `tests/test_036_depends_on_emission.py::test_user_requested_deletion_emits_empty_depends_on` (site 1) | ✅ |
| F5-AC2 | A delete nothing justifies carries an explicitly empty field, not an absent one | `tests/test_036_depends_on_emission.py::test_user_requested_deletion_emits_empty_depends_on`, with `tests/test_036_withdraw_unjustified_deletes.py::test_missing_key_and_empty_list_are_different_outcomes` proving the two are not conflated downstream — absent withdraws, `[]` is kept | ✅ |
| F5-AC3 | An origin consumed by three atomics names all three move ids | `tests/test_036_depends_on_emission.py::test_three_atomic_origin_names_all_three_move_ids`; `::test_audio_peer_delete_names_same_move_id_set_as_origin_delete` closes the gotcha that naming only one leaves the peer unguarded | ✅ |
| F5-AC4 | Every id in every dependency field is present in the same set | `tests/test_instruction_render_wire_hygiene.py::TestAssertNoDanglingDependencies::test_one_dangling_id_produces_one_violation_naming_both_ids`, and at run level `::TestAssertNoDanglingDependenciesIntegration::test_dangling_id_aborts_exit_2_no_file_with_unpatched_control`. `::test_missing_depends_on_key_is_a_violation_distinct_from_dangling_id` covers the absent-key mode separately | ✅ |
| F5-AC5 | The executor skips a delete whose named dependency failed | **Consumer-owned** — see below | ⏳ |
| F5-AC6 | A destination taken between generation and application leaves the original intact | **Consumer-owned** — see below | ⏳ |

### F6 — The instruction document explains a withheld delete (2)

| AC | Statement | Proving test | Status |
|---|---|---|---|
| F6-AC1 | Any guard's withdrawal and its cause appear together | `tests/test_036_t4_3_withdrawal_reporting.py::TestStderrReporting::test_daily_withdrawal_reports_missing_id_and_guard_on_stderr` (stderr) and `::TestMarkdownSkippedSection::test_withdrawal_renders_inside_existing_skipped_heading` (markdown); the `tomo` block, the third surface the SDD mandates, is `::TestTomoBlockDeleteWithdrawals::test_withdrawal_writes_tomo_block_delete_withdrawals`. "**Any** guard" is what `::TestAttributeWithdrawalCauses::test_missing_id_attributed_to_the_guard_that_dropped_it` carries — parametrized over all five drop sites — with `::TestWithdrawalGuardsStaySynced::test_drop_sources_keys_match_withdrawal_guards_exactly` failing if a sixth guard is ever added without joining the list | ✅ |
| F6-AC2 | No withdrawal → no withdrawal reporting at all | `::TestMarkdownSkippedSection::test_no_withdrawal_produces_no_withdrawal_subblock`, `::TestStderrReporting::test_no_withdrawal_run_emits_no_withdrawal_block_on_stderr`, `::TestTomoBlockDeleteWithdrawals::test_no_withdrawal_omits_key_never_an_empty_list` (omitted, not an empty list), and `::TestSourceDeletionsWithdrawalNotice::test_no_withdrawals_source_deletions_byte_identical` | ✅ |

## The two consumer-owned criteria

`F5-AC5` and `F5-AC6` describe **the executor's** behaviour, not Tomo's. Tomo does not execute the
instruction set, and under CON-4 it may never read execution results back — that constraint is the
reason the residue feature was cut, and it applies here identically. There is no Tomo-side test for
either, and none was written: a test that stubbed an executor would prove a fake behaves as we
imagine, which is exactly the assumption the PRD already flags ("the executor's dependency-skip
mechanism behaves as its source indicates — it was read, not executed, from this side").

| AC | Owner | Confirmed by |
|---|---|---|
| F5-AC5 — a delete whose named dependency failed is skipped and recorded as skipped-due-to-dependency | Hashi | Their reply to the T4.5 release handoff |
| F5-AC6 — a destination occupied after generation fails the move, the paired delete is skipped, the original survives | Hashi | Their reply to the T4.5 release handoff |

**Status at close-out: not yet confirmed.** T4.5 is still `[ ]`. Spec 035's release handoff went out
on 2026-09-11 and told Hashi explicitly that `depends_on` was **not** part of that release — so the
handoff carrying this spec's instruction-wire row (`schema_version "2" → "3"`) has not been sent,
and `_outbox/for-hashi/` holds no 036 attachment. This is a **boundary with an open obligation**,
not a gap in the traceability: the two criteria are mapped, owned and scheduled. They are not yet
discharged, and this document does not pretend otherwise.

## Gaps

**None at close-out.** The one gap this document originally recorded was closed the same day; it is
kept below with its resolution rather than deleted, because the reasoning is what made it findable.

- **~~F2-AC2 has no single test.~~ Closed 2026-09-18 by `4a25c86`.** The original finding: The criterion is "several buckets or several days, **any one**
  withheld → no delete". What exists is the naming half (a multi-bucket, multi-day origin's delete
  names all three ids) and the withdrawal half (a delete naming three ids of which one is missing is
  withdrawn) in two different files, over two different fixtures. The composition is sound — the
  second consumes exactly what the first produces, and `withdraw_unjustified_deletes` is id-keyed
  with no knowledge of buckets — but no test drives a real multi-bucket origin through a guard that
  drops one of its daily actions. The end-to-end P2 case (`test_all_three_data_loss_paths_in_one_run_emit_no_delete`)
  is single-bucket. What would close it: one case in `test_036_t2_4_phase_validation.py` building a
  three-action daily origin and running `filter_missing_daily_notes` with only one of the three
  target daily notes absent.

  That is exactly what shipped, and the gap proved worth closing rather than arguing away: under a
  mutant that swaps `withdraw_unjustified_deletes` to OR semantics (withdraw only when **every**
  dependency is missing) the new test goes red while all three pre-existing tests in the same file
  stay green — including the single-bucket Bug A case, where AND and OR coincide. The shipped code
  was already correct; nothing had been holding it upright.

No criterion in F1–F6 is untested. No criterion is carried by a test stretched from an unrelated
concern.

**Not a gap, but not silent either:** `docs/XDD/backlog.md`'s entry "OPEN —
`instructions-diff.py`'s coverage audit doesn't reconcile spec 036's daily/tag-handler withdrawals"
(recorded 2026-09-17 during T4.3) was **closed by `3c8170c`**, which added
`_subtract_withdrawn_deletes` to `instructions-diff.py` and `tests/test_036_t4_4_withdrawn_delete_coverage.py`
(8 cases, all green). The backlog entry still reads `OPEN`. Stale bookkeeping, not a defect.

## The close-out position: three measured paths, three closed

The PRD's Problem Statement measures three paths to termination against a real vault on 2026-09-09.
All three are closed, and the decisive evidence is that **one run closes all three at once** —
before T4.4 no test exercised more than one path at a time, so nothing had proved they compose.

| # | Path | Where it now stops | Evidence |
|---|---|---|---|
| P1 | `create_moc` and `move_note` claim one destination; the MOC is written, the move fails, the paired delete runs anyway | `validate_destinations` drops **both** claimants (ADR-3); `withdraw_unjustified_deletes` removes the delete naming the dropped move | `test_036_t2_4_phase_validation.py::test_p1_contested_destination_emits_no_orphaned_delete`; e2e P1 block — the origin is still on disk after the run, and neither claimant's staging note survives in `manifest.json` |
| P2 / Bug A | `filter_missing_daily_notes` drops the daily partner, keeps every other action, ships the delete whose stated reason is that the content is in the daily note | The same withdrawal pass, one guard later in the same order | `test_036_t2_4_phase_validation.py::test_bug_a_missing_daily_note_leaves_no_delete_behind` — which asserts the pre-fix state explicitly, so the test would go red if the guard stopped dropping the action rather than only if the pass stopped withdrawing; e2e P2 block |
| P3 / Bug B | A tag-handler group with an unresolved `target_path` emits zero inserts and one delete per source, **pre-ticked** for approval | A shared appliability predicate gates both sites (ADR-5); the reducer sets `target_unresolved` before its early return, and the suppression path grew a third branch | `test_tag_handler_group_instruction_linkage.py::test_unresolvable_target_three_sources_emits_zero_deletes`; `test_036_t3_3_phase_validation.py::test_a_unresolved_group_through_real_gate_emits_nothing` and `::test_c_rendered_block_has_no_approve_control_and_carries_reason`; e2e P3 block |

**P3 is framed honestly in the e2e** as a build-time guard, not a withdrawal: it emits no action, so
it never reaches the withdrawal report, and its assertions would pass unchanged if the withdrawal
pass were gutted. That is stated in the test's own docstring rather than left for a reader to
discover — a close-out that let P3 borrow P1's and P2's evidence would be overclaiming.

The fourth class — a destination taken **after** generation — is structurally outside build-time
checking and is covered only by F5's wire dependency. It remains open until the consumer confirms
F5-AC5/AC6.

**Falsification, run and reverted, recorded in `9157f9c`:** withdrawal pass to a no-op → Test 1 red;
withdrawal pass *and* the dangling audit gutted → Test 1 red on the P1 assertion itself; daily
action ids never recorded → Test 1 red on P2 and Test 2 red on the non-empty assertion; tag-handler
gate forced open → Test 1 red. The end-to-end tests are not vacuous under a broken implementation.

## The two deferrals — recorded as decisions, not absences

| Deferral | Where the decision is recorded | Verdict |
|---|---|---|
| **F7 — a destructive action reads as destructive in the document** (F7-AC1, F7-AC2) | `README.md` decisions log, entry dated **2026-09-10**: "23 of 25 PRD criteria map to tasks; the other 2 are a recorded decision" — F7 is `Could Have`, a pure rendering change with no interaction with the withdrawal mechanism, "written into the plan's coverage table as a decision rather than left as an apparent gap". Restated in `plan/README.md`'s coverage table (`F7 … — … deferred by decision; Could Have, not designed`) and in the PRD's own `Could Have` section | ✅ Recorded in two places |
| **Post-hoc detection of staging notes stranded by a failed action** | `README.md` decisions log, entry dated **2026-09-09**: "Tomo must never consume the executor's results" — an owner constraint that *eliminated a feature that was about to be written*, because reading applied-flags back is the only reliable signal and it abandons the manual-markdown persona. The PRD's `Won't Have (This Phase)` carries the same ruling with the rejected design attached, explicitly "recorded so a future session does not re-propose reading execution results back" | ✅ Recorded in two places, with the rejected design |

Both are decisions with a rationale and a date, not items that quietly failed to happen. Neither
needs a backlog entry to be traceable, and neither was moved to the backlog — the residue item in
`docs/XDD/backlog.md` is spec 034's clash-residue entry (marked FIXED), a different thing.

## Validation run — measured 2026-09-18 on `ce3eead`

| Check | Command | Result |
|---|---|---|
| Full suite | `./venv/bin/python -m pytest` | **4235 passed, 3 skipped**, 1 warning, 103.77 s |
| Integration | `./venv/bin/python -m pytest -m integration` | **20 passed**, 4218 deselected |
| Lint | `./venv/bin/python -m ruff check tomo/ tests/` | **All checks passed** |
| Traced tests, re-run by node id | three targeted batches, 87 test items across 14 files (batches overlap slightly) | **all green** |

The three skips are environmental and expected: `test_035_wire_schema_versioning.py:124`
(`_outbox/for-hashi/` is gitignored and holds no attachment in this checkout — the same conditional
035 recorded), `test_garden_audit_tomo_editor.py:578` (fixture absent), and
`tests/voice/test_transcriber.py:172` (needs a faster-whisper model directory). None is a spec 036
path. The one warning is a pre-existing `PytestReturnNotNoneWarning` in `tests/test-008-phase1.py`,
unrelated.

The suite has grown from 4147 at Phase 3's close to 4235 — +88, all of it Phase 4.

## What this validation found that the suite did not

- **A green suite and a released spec are different claims.** Every criterion in F1–F6 passes, and
  the spec still cannot close: T4.5 has not gone out, so the two criteria that cover the only
  failure class build-time guarding structurally cannot reach are unconfirmed. Counting 21/21 green
  and calling it done would have hidden exactly that.
- **A criterion can be covered by two tests and still have a shape no test drives.** F2-AC2 is
  sound by composition, and composition is how it was signed off in the plan. It is written down
  here because the next person to change the daily-action id map will not re-derive the composition
  — they will look for the test.
- **The backlog can lag the code in the safe direction and still mislead.** T4.3's coverage-audit
  item was fixed nine commits later and never re-marked. A reader planning follow-up work from the
  backlog would schedule work that is already done.

## Found while preparing the handoff, after this document was first written

**The contract's `depends_on` description named the wrong action kinds** (`96c1778`). It told the
consumer the field carries "Action ids (move_note/move_asset)". `move_asset` ids never appear —
site 3 filters on `action == "move_note"` (`render_actions.py:1904`) before collecting — and three
of the five emission sites name something else entirely: site 2 names the origin's daily actions
(`update_tracker` / `update_log_entry` / `update_log_link`, `:1881`), site 4 the tag-handler's
`insert_under_marker` (`:2003`). A consumer implementing "withhold unless every named move is
applied" would not recognise a daily-action id as the thing it must wait for — and a daily-only
origin's delete is precisely the P2 case this spec exists to close.

**The lesson is about the gate, not the typo.** T4.5's own step 2 is a structural diff — property
sets, `required` lists, `additionalProperties`, recursively. It compares shape and is blind to
prose, so it reported "3 differences, exactly the intended change" over a description that would
have misled the implementer. A contract's prose is part of the contract; read it, do not diff it.

## Still open at close-out

- **T4.5, the release handoff.** Not sent. Carries F5-AC5 and F5-AC6, and gates the release of the
  instruction wire `"2" → "3"` — the consumer rejects unknown fields, so they vendor first or
  simultaneously, never after. Note the mirror schema edit (T4.1) **already landed**, by owner
  override of the plan's sequencing gate; the gate now survives on the release rule alone and
  nothing in the test suite enforces it.
- ~~**The `OPEN` marker on the `instructions-diff.py` coverage-audit backlog entry.**~~ Re-marked
  CLOSED 2026-09-18 (`195c32d`); the entry's own "what closing this needs" paragraph describes
  precisely what `3c8170c` shipped.

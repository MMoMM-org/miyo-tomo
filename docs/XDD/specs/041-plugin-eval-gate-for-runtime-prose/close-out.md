---
title: "Close-out — 041 plugin-eval gate for runtime prose"
status: complete
---

# Close-out

## Standing rule for this document

Every PRD criterion below traces to evidence that was **executed**, not to a task that mentions it:

- Criteria about the runner, the verdict, the stubs and the documents trace to pytest node ids.
- Criteria about what the conductor (an LLM) does trace to recorded eval runs. Each is quoted by its verdict line and results path from [`baseline.md`](baseline.md) or [`red-proofs.md`](red-proofs.md).
- A criterion decided by an eval grader carries both kinds of evidence. Pytest proves the grader's shape (it matches what it must and spares what it must). The eval runs prove the behaviour: GREEN on the merge candidate, RED under a named proof.

The results directories (`tomo-tmp/evals/<TS>/`) are gitignored and local. This document cites their paths only. No vault content exists in any eval workspace.

`requirements.md` carries **35** criteria: F1:6 F2:6 F3:3 F4:4 F5:5 F6:2 F7:6 F8:2 F9:1. **35/35 trace to executed evidence.**

- 22 trace to pytest alone.
- 12 trace to pytest plus eval runs (F3–F6 grader criteria and F7-AC4).
- 1 (F7-AC6) traces to eval runs alone.

## 1. The single invocation

The **115 node ids** in the trace table ran **together in one `pytest` invocation on 2026-10-26**, on the Phase 5 drift-fix tree (the 105 ids of 2026-10-25 plus the 10 added by `183b38f5`, `c261cc0b`, `8f28ae44` and `5d3db600`; the 2026-10-25 run was `232 passed in 23.50s`):

```
242 passed in 26.34s
```

115 node ids collect **242 items**. The difference is parametrisation. Collection was checked by script, not by eye: the sorted list of cited node ids and the sorted list of collected node ids (parameters stripped) are identical. Nothing was deselected and nothing extra was collected.

The full suite and `ruff` results are in §6.

**G was re-run after the drift fixes.** The stubs (`c261cc0b`, `5d3db600`: the real scripts' success formats on the real stream) and the verdict line (`183b38f5`) changed after the first T5.1 runs on `0492b0c5`, so those runs are superseded. G below is the re-run on `69f845c0`.

<details><summary>The command, exactly as run</summary>

```bash
./venv/bin/python -m pytest -q \
  tests/test_run_evals.py::test_default_run_passes_fixed_flags_and_three_outputs \
  tests/test_run_evals.py::test_snapshot_shape_and_agents_byte_identical \
  tests/test_run_evals.py::test_fake_writing_into_repo_is_not_graded_and_names_path \
  tests/test_run_evals.py::test_fake_modifying_already_dirty_file_is_detected \
  tests/test_run_evals.py::test_runner_leaves_every_tomo_instance_unchanged \
  tests/test_run_evals.py::test_mutation_patches_snapshot_not_repo \
  tests/test_run_evals.py::test_dirty_tree_is_reported_not_refused \
  tests/test_run_evals.py::test_results_dir_is_a_utc_timestamp_named_in_the_verdict \
  tests/test_run_evals.py::test_results_location_not_gitignored_is_refused \
  tests/test_eval_verdict.py::test_green_3x \
  tests/test_eval_suite_not_synced.py::test_copy_sources_are_rooted_under_tomo \
  tests/test_eval_suite_not_synced.py::test_scan_is_red_for_a_source_outside_tomo \
  tests/test_eval_suite_not_synced.py::test_update_never_delivers_sentinel_from_evals \
  tests/test_run_evals.py::test_old_claude_version_refused_before_eval \
  tests/test_run_evals.py::test_unparseable_claude_version_refused \
  tests/test_run_evals.py::test_help_documents_contract \
  tests/test_run_evals.py::test_temp_dir_removed_and_verdict_from_result \
  tests/test_eval_verdict.py::test_cli_run_level_passed_and_score_are_ignored \
  tests/test_eval_verdict.py::test_relay_red_one_run_is_red_despite_cli_score \
  tests/test_eval_verdict.py::test_pre_4350ddd_names_both_ordering_graders \
  tests/test_eval_verdict.py::test_cost_cap_partial_not_graded_though_runs_passed \
  tests/test_eval_verdict.py::test_cost_cap_names_the_cap_when_given \
  tests/test_eval_verdict.py::test_cost_cap_counts_runs_plural \
  tests/test_run_evals.py::test_cost_cap_verdict_names_the_cap_that_was_passed \
  tests/test_run_evals.py::test_max_cost_flag_and_env_reach_cli_and_default_returns \
  tests/test_run_evals.py::test_invalid_max_cost_refused \
  tests/test_eval_verdict.py::test_run_error_rate_limit_not_graded \
  tests/test_eval_verdict.py::test_other_partial_reason_keeps_generic_wording \
  tests/test_eval_verdict.py::test_partial_without_reason_still_not_graded \
  tests/test_eval_verdict.py::test_run_aborted_not_graded \
  tests/test_eval_verdict.py::test_skipped_paid_graders_not_graded \
  tests/test_eval_verdict.py::test_unscored_grader_is_not_a_pass \
  tests/test_eval_verdict.py::test_run_without_graders_not_graded \
  tests/test_eval_verdict.py::test_not_graded_beats_red \
  tests/test_eval_verdict.py::test_eperm_in_sandbox_hint \
  tests/test_eval_verdict.py::test_malformed_shapes_never_traceback \
  tests/test_eval_verdict.py::test_unexpected_crash_is_not_graded_never_red \
  tests/test_run_evals.py::test_cli_exit_2_without_result_is_not_graded \
  tests/test_run_evals.py::test_cli_nonzero_with_green_result_is_never_green \
  tests/test_run_evals.py::test_stray_failure_after_cli_is_not_graded \
  tests/test_run_evals.py::test_verdict_script_failure_is_not_graded_with_one_line \
  tests/test_run_evals.py::test_model_follows_settings_json \
  tests/test_run_evals.py::test_unreadable_settings_model_is_refused \
  tests/test_eval_conductor_cases.py::test_every_prd_criterion_has_its_grader \
  tests/test_eval_conductor_cases.py::test_prompt_is_the_production_dispatch_namespaced \
  tests/test_eval_conductor_cases.py::test_audit_order_graders \
  tests/test_eval_conductor_cases.py::test_invocation_graders_ignore_a_mention \
  tests/test_eval_conductor_cases.py::test_invocation_graders_match_a_run \
  tests/test_eval_conductor_cases.py::test_invocation_graders_match_every_conductor_invocation \
  tests/test_eval_conductor_cases.py::test_audit_ok_line_is_the_kit_line \
  tests/test_eval_suite_shape.py::test_audit_stub_ok \
  tests/test_eval_conductor_cases.py::test_mismatch_never_called_graders \
  tests/test_eval_conductor_cases.py::test_mismatch_verbatim_grader_is_built_from_the_kit_lines \
  tests/test_eval_suite_shape.py::test_audit_stub_fail \
  tests/test_eval_conductor_cases.py::test_no_write_grader_shape \
  tests/test_eval_conductor_cases.py::test_no_copy_grader_shape \
  tests/test_eval_conductor_cases.py::test_no_write_grader_catches_writes \
  tests/test_eval_conductor_cases.py::test_no_write_grader_spares_the_conductors_own_commands \
  tests/test_eval_conductor_cases.py::test_no_write_graders_catch_quoted_and_copy_writes \
  tests/test_eval_conductor_cases.py::test_no_write_graders_see_a_command_after_an_encoded_newline \
  tests/test_eval_conductor_cases.py::test_no_write_graders_spare_reads_and_tomo_tmp_writes \
  tests/test_eval_conductor_cases.py::test_no_write_graders_stay_silent_on_reads_across_newlines \
  tests/test_eval_conductor_cases.py::test_scaffold_stages_its_settings \
  tests/test_eval_conductor_cases.py::test_relay_line_graders_are_the_kit_lines_anchored \
  tests/test_eval_conductor_cases.py::test_anchored_relay_graders_match_own_line_only \
  tests/test_eval_suite_shape.py::test_relay_files_written_by_render_stub \
  tests/test_eval_conductor_cases.py::test_deletes_then_attachment_last_grader \
  tests/test_eval_conductor_cases.py::test_no_notice_when_none_withheld_grader \
  tests/test_eval_suite_shape.py::test_render_stub_unlinks_stale_relays_when_count_is_zero \
  tests/test_eval_suite_shape.py::test_no_leak_matches_observed_leaks \
  tests/test_eval_suite_shape.py::test_no_leak_matches_synthetic_leaks \
  tests/test_eval_suite_shape.py::test_no_leak_allows_notices_suggestions_doc_and_audit_line \
  tests/test_eval_suite_shape.py::test_render_stub_stderr_carries_bait \
  tests/test_eval_conductor_cases.py::test_case_leak_guard_is_byte_identical \
  tests/test_run_evals.py::test_case_without_identical_leak_guard_refused \
  tests/test_eval_conductor_cases.py::test_every_non_underscore_evals_subdir_is_a_case \
  tests/test_eval_gate_docs.py::test_every_covered_path_exists \
  tests/test_eval_gate_docs.py::test_prd_named_files_are_in_the_table \
  tests/test_eval_gate_docs.py::test_every_table_row_names_an_existing_case \
  tests/test_eval_gate_docs.py::test_every_case_directory_appears_in_the_table \
  tests/test_eval_gate_docs.py::test_every_case_named_in_the_table_exists \
  tests/test_eval_gate_docs.py::test_root_claude_md_rule_names_readme_and_green \
  tests/test_eval_gate_docs.py::test_claude_md_rule_tracks_the_coverage_table \
  tests/test_eval_gate_docs.py::test_claude_md_rule_states_the_pr_record_and_the_exemption \
  tests/test_eval_conductor_cases.py::test_every_gate_grader_is_an_expected_red_of_a_proof \
  tests/test_eval_conductor_cases.py::test_proof_rows_name_real_graders_of_their_cases \
  tests/test_eval_conductor_cases.py::test_report_run_id_is_proven_in_every_case \
  tests/test_eval_conductor_cases.py::test_f4_ac4_graders_have_distinct_proofs \
  tests/test_eval_conductor_cases.py::test_neutral_write_mutations_trip_only_their_grader \
  tests/test_eval_conductor_cases.py::test_rev_proofs_resolve_to_a_conductor \
  tests/test_eval_conductor_cases.py::test_readme_mutations_match_the_patch_files \
  tests/test_eval_conductor_cases.py::test_mutation_applies_cleanly_to_a_fresh_assembly \
  tests/test_eval_conductor_cases.py::test_mutation_touches_only_the_conductor \
  tests/test_eval_conductor_cases.py::test_mutation_removes_and_adds_its_declared_clauses \
  tests/test_eval_conductor_cases.py::test_every_control_is_listed_and_never_a_proof_target \
  tests/test_eval_conductor_cases.py::test_graders_split_into_controls_and_mapped_gates \
  tests/test_eval_conductor_cases.py::test_conductor_dispatched_control \
  tests/test_eval_conductor_cases.py::test_audit_ran_control \
  tests/test_run_evals.py::test_known_case_is_partial_suite \
  tests/test_eval_verdict.py::test_partial_suite_prefix \
  tests/test_run_evals.py::test_runs_with_case_reaches_cli \
  tests/test_run_evals.py::test_unknown_case_refused_listing_cases \
  tests/test_eval_verdict.py::test_compare_lists_only_differing_pairs \
  tests/test_eval_verdict.py::test_compare_disjoint_pair_reports_every_grader_of_both \
  tests/test_eval_verdict.py::test_compare_identical_prints_nothing \
  tests/test_eval_verdict.py::test_results_path_is_relative_to_the_given_root \
  tests/test_eval_verdict.py::test_results_path_outside_root_is_never_resolved_absolute \
  tests/test_eval_verdict.py::test_results_path_relative_input_stays_as_given \
  tests/test_eval_verdict.py::test_not_graded_line_path_is_relative_too \
  tests/test_eval_verdict.py::test_cost_cap_counts_only_runs_without_an_error \
  tests/test_eval_verdict.py::test_compare_accepts_results_directories \
  tests/test_eval_verdict.py::test_compare_directory_without_aggregate_is_a_clear_error \
  tests/test_run_evals.py::test_verdict_line_and_file_carry_a_repo_relative_results_path \
  tests/test_run_evals.py::test_runner_generated_not_graded_line_is_repo_relative \
  tests/test_eval_suite_shape.py::test_render_stub_prints_real_summary_on_stderr
```

</details>

## 2. Trace

Eval-run shorthand used in the table:

- **G** is the three consecutive full-suite GREENs on the merge candidate `69f845c0` (T5.1 re-run after the drift fixes, [`baseline.md`](baseline.md) "Re-run after the drift fixes"; it supersedes the 2026-10-25 runs on `0492b0c5`). Verbatim:
  - `GREEN 3/3 cases · runs 9 · $0.64 · 100 s · claude 2.1.310 · tree clean · tomo-tmp/evals/2026-10-26T06-08-08Z`
  - `GREEN 3/3 cases · runs 9 · $0.59 · 103 s · claude 2.1.310 · tree clean · tomo-tmp/evals/2026-10-26T06-09-57Z`
  - `GREEN 3/3 cases · runs 9 · $0.59 · 111 s · claude 2.1.310 · tree clean · tomo-tmp/evals/2026-10-26T06-11-45Z`
- **R** is the RED proof named in §3, from [`red-proofs.md`](red-proofs.md).

| Criterion | Method | Evidence |
|---|---|---|
| F1-AC1 | deterministic; live: G | `tests/test_run_evals.py::test_default_run_passes_fixed_flags_and_three_outputs` (no `--case` reaches the CLI)<br>`tests/test_run_evals.py::test_snapshot_shape_and_agents_byte_identical` (agents, skills and commands are byte-identical to the working tree)<br>G: `3/3 cases` on every run |
| F1-AC2 | deterministic | `tests/test_run_evals.py::test_fake_writing_into_repo_is_not_graded_and_names_path`<br>`tests/test_run_evals.py::test_fake_modifying_already_dirty_file_is_detected`<br>`tests/test_run_evals.py::test_runner_leaves_every_tomo_instance_unchanged` (new, §4)<br>`tests/test_run_evals.py::test_mutation_patches_snapshot_not_repo`<br>`tests/test_run_evals.py::test_dirty_tree_is_reported_not_refused`<br>Every runner test also asserts, in `Env.run`, that the fake repo's tree and `$HOME/.tomo` are unchanged (`test_default_run_passes_fixed_flags_and_three_outputs` stands for them here) |
| F1-AC3 | deterministic | `tests/test_run_evals.py::test_default_run_passes_fixed_flags_and_three_outputs` (`--output-dir` under `tomo-tmp/evals/`, all three outputs, `verdict.txt` = the printed line)<br>`tests/test_run_evals.py::test_results_dir_is_a_utc_timestamp_named_in_the_verdict` (new, §4)<br>`tests/test_run_evals.py::test_results_location_not_gitignored_is_refused` (new, §4)<br>`tests/test_eval_verdict.py::test_green_3x` (the path is in the line)<br>`tests/test_eval_verdict.py::test_results_path_is_relative_to_the_given_root`<br>`tests/test_eval_verdict.py::test_results_path_outside_root_is_never_resolved_absolute`<br>`tests/test_eval_verdict.py::test_results_path_relative_input_stays_as_given`<br>`tests/test_run_evals.py::test_verdict_line_and_file_carry_a_repo_relative_results_path`<br>`tests/test_run_evals.py::test_runner_generated_not_graded_line_is_repo_relative`<br>`tests/test_eval_verdict.py::test_not_graded_line_path_is_relative_too` |
| F1-AC4 | deterministic | `tests/test_eval_suite_not_synced.py::test_copy_sources_are_rooted_under_tomo` (both scripts, static)<br>`tests/test_eval_suite_not_synced.py::test_scan_is_red_for_a_source_outside_tomo`<br>`tests/test_eval_suite_not_synced.py::test_update_never_delivers_sentinel_from_evals` (`update-tomo.sh`, dynamic) |
| F1-AC5 | deterministic | `tests/test_run_evals.py::test_old_claude_version_refused_before_eval` (strengthened, §4)<br>`tests/test_run_evals.py::test_unparseable_claude_version_refused` |
| F1-AC6 | deterministic | `tests/test_run_evals.py::test_help_documents_contract` |
| F2-AC1 | deterministic; live: G | `tests/test_eval_verdict.py::test_green_3x`<br>`tests/test_eval_verdict.py::test_cli_run_level_passed_and_score_are_ignored`<br>`tests/test_run_evals.py::test_temp_dir_removed_and_verdict_from_result` |
| F2-AC2 | deterministic; live: every R | `tests/test_eval_verdict.py::test_relay_red_one_run_is_red_despite_cli_score`<br>`tests/test_eval_verdict.py::test_pre_4350ddd_names_both_ordering_graders`<br>`tests/test_run_evals.py::test_temp_dir_removed_and_verdict_from_result` |
| F2-AC3 | deterministic; see note | `tests/test_eval_verdict.py::test_cost_cap_partial_not_graded_though_runs_passed` (on the cost-cap fixture captured live in T1.1)<br>`tests/test_eval_verdict.py::test_cost_cap_names_the_cap_when_given`<br>`tests/test_eval_verdict.py::test_cost_cap_counts_runs_plural`<br>`tests/test_run_evals.py::test_cost_cap_verdict_names_the_cap_that_was_passed`<br>`tests/test_eval_verdict.py::test_cost_cap_counts_only_runs_without_an_error` |
| F2-AC4 | deterministic | `tests/test_run_evals.py::test_max_cost_flag_and_env_reach_cli_and_default_returns`<br>`tests/test_run_evals.py::test_invalid_max_cost_refused` |
| F2-AC5 | deterministic | `tests/test_eval_verdict.py::test_run_error_rate_limit_not_graded`<br>`tests/test_eval_verdict.py::test_other_partial_reason_keeps_generic_wording`<br>`tests/test_eval_verdict.py::test_partial_without_reason_still_not_graded`<br>`tests/test_eval_verdict.py::test_run_aborted_not_graded`<br>`tests/test_eval_verdict.py::test_skipped_paid_graders_not_graded`<br>`tests/test_eval_verdict.py::test_unscored_grader_is_not_a_pass`<br>`tests/test_eval_verdict.py::test_run_without_graders_not_graded`<br>`tests/test_eval_verdict.py::test_not_graded_beats_red`<br>`tests/test_eval_verdict.py::test_eperm_in_sandbox_hint`<br>`tests/test_eval_verdict.py::test_malformed_shapes_never_traceback`<br>`tests/test_eval_verdict.py::test_unexpected_crash_is_not_graded_never_red`<br>`tests/test_run_evals.py::test_cli_exit_2_without_result_is_not_graded`<br>`tests/test_run_evals.py::test_cli_nonzero_with_green_result_is_never_green`<br>`tests/test_run_evals.py::test_stray_failure_after_cli_is_not_graded`<br>`tests/test_run_evals.py::test_verdict_script_failure_is_not_graded_with_one_line` |
| F2-AC6 | deterministic | `tests/test_run_evals.py::test_model_follows_settings_json`<br>`tests/test_run_evals.py::test_default_run_passes_fixed_flags_and_three_outputs` (`--model sonnet`)<br>`tests/test_run_evals.py::test_unreadable_settings_model_is_refused`<br>`tests/test_run_evals.py::test_snapshot_shape_and_agents_byte_identical` (agent frontmatter, including `model:`, reaches the plugin unchanged) |
| F3-AC1 | grader shape + live: G, R `--rev 4350ddd^` | `tests/test_eval_conductor_cases.py::test_audit_order_graders`<br>`tests/test_eval_conductor_cases.py::test_invocation_graders_ignore_a_mention`<br>`tests/test_eval_conductor_cases.py::test_invocation_graders_match_a_run`<br>`tests/test_eval_conductor_cases.py::test_invocation_graders_match_every_conductor_invocation`<br>`tests/test_eval_conductor_cases.py::test_prompt_is_the_production_dispatch_namespaced`<br>`tests/test_eval_conductor_cases.py::test_every_prd_criterion_has_its_grader` |
| F3-AC2 | grader shape + live: G, R `--rev 4350ddd^` | as F3-AC1 (the `state-promoter` parameter of `test_audit_order_graders`) |
| F3-AC3 | grader shape + live: G, R `drop-audit-line` | `tests/test_eval_conductor_cases.py::test_audit_ok_line_is_the_kit_line`<br>`tests/test_eval_suite_shape.py::test_audit_stub_ok` |
| F4-AC1 | grader shape + live: G, R `--rev 4350ddd^` | `tests/test_eval_conductor_cases.py::test_mismatch_never_called_graders`<br>`tests/test_eval_conductor_cases.py::test_invocation_graders_ignore_a_mention`<br>`tests/test_eval_conductor_cases.py::test_invocation_graders_match_a_run` |
| F4-AC2 | grader shape + live: G, R `--rev 4350ddd^` | as F4-AC1 (the `state-promoter` parameter) |
| F4-AC3 | grader shape + live: G, R `summarise-mismatch` | `tests/test_eval_conductor_cases.py::test_mismatch_verbatim_grader_is_built_from_the_kit_lines`<br>`tests/test_eval_suite_shape.py::test_audit_stub_fail` |
| F4-AC4 | grader shape + live: G, R `write-into-scripts`, `copy-into-config` | `tests/test_eval_conductor_cases.py::test_no_write_grader_shape`<br>`tests/test_eval_conductor_cases.py::test_no_copy_grader_shape`<br>`tests/test_eval_conductor_cases.py::test_no_write_grader_catches_writes`<br>`tests/test_eval_conductor_cases.py::test_no_write_grader_spares_the_conductors_own_commands`<br>`tests/test_eval_conductor_cases.py::test_no_write_graders_catch_quoted_and_copy_writes`<br>`tests/test_eval_conductor_cases.py::test_no_write_graders_see_a_command_after_an_encoded_newline`<br>`tests/test_eval_conductor_cases.py::test_no_write_graders_spare_reads_and_tomo_tmp_writes`<br>`tests/test_eval_conductor_cases.py::test_no_write_graders_stay_silent_on_reads_across_newlines`<br>`tests/test_eval_conductor_cases.py::test_neutral_write_mutations_trip_only_their_grader`<br>`tests/test_eval_conductor_cases.py::test_f4_ac4_graders_have_distinct_proofs` |
| F5-AC1 | grader shape + live: G, R `paraphrase-relay` | `tests/test_eval_conductor_cases.py::test_relay_line_graders_are_the_kit_lines_anchored`<br>`tests/test_eval_conductor_cases.py::test_anchored_relay_graders_match_own_line_only`<br>`tests/test_eval_suite_shape.py::test_relay_files_written_by_render_stub`<br>`tests/test_eval_conductor_cases.py::test_scaffold_stages_its_settings` |
| F5-AC2 | grader shape + live: G, R `paraphrase-relay` | as F5-AC1. `test_anchored_relay_graders_match_own_line_only` rejects a table row, a count heading, a merged line and a dropped `- ` |
| F5-AC3 | grader shape + live: G, R `paraphrase-relay` | as F5-AC1 (the attachment line) |
| F5-AC4 | grader shape + live: G, R `attachments-first`, `files-used-after` | `tests/test_eval_conductor_cases.py::test_deletes_then_attachment_last_grader` |
| F5-AC5 | grader shape + live: G, R `always-notice` | `tests/test_eval_conductor_cases.py::test_no_notice_when_none_withheld_grader`<br>`tests/test_eval_suite_shape.py::test_render_stub_unlinks_stale_relays_when_count_is_zero` |
| F6-AC1 | grader shape + live: G, R `report-run-id` (all three cases) | `tests/test_eval_suite_shape.py::test_no_leak_matches_observed_leaks`<br>`tests/test_eval_suite_shape.py::test_no_leak_matches_synthetic_leaks`<br>`tests/test_eval_suite_shape.py::test_no_leak_allows_notices_suggestions_doc_and_audit_line`<br>`tests/test_eval_suite_shape.py::test_render_stub_stderr_carries_bait`<br>`tests/test_eval_conductor_cases.py::test_case_leak_guard_is_byte_identical`<br>`tests/test_eval_suite_shape.py::test_render_stub_prints_real_summary_on_stderr` |
| F6-AC2 | deterministic | `tests/test_run_evals.py::test_case_without_identical_leak_guard_refused`<br>`tests/test_eval_conductor_cases.py::test_case_leak_guard_is_byte_identical`<br>`tests/test_eval_conductor_cases.py::test_every_non_underscore_evals_subdir_is_a_case` |
| F7-AC1 | deterministic | `tests/test_eval_gate_docs.py::test_every_covered_path_exists`<br>`tests/test_eval_gate_docs.py::test_prd_named_files_are_in_the_table`<br>`tests/test_eval_gate_docs.py::test_every_table_row_names_an_existing_case`<br>`tests/test_eval_gate_docs.py::test_every_case_directory_appears_in_the_table`<br>`tests/test_eval_gate_docs.py::test_every_case_named_in_the_table_exists` |
| F7-AC2 | deterministic | `tests/test_eval_gate_docs.py::test_root_claude_md_rule_names_readme_and_green`<br>`tests/test_eval_gate_docs.py::test_claude_md_rule_tracks_the_coverage_table`<br>`tests/test_eval_gate_docs.py::test_claude_md_rule_states_the_pr_record_and_the_exemption` (new, §4) |
| F7-AC3 | deterministic | `tests/test_eval_gate_docs.py::test_claude_md_rule_states_the_pr_record_and_the_exemption` (new, §4)<br>`tests/test_eval_gate_docs.py::test_claude_md_rule_tracks_the_coverage_table` (the rule names exactly the table's files) |
| F7-AC4 | deterministic + live: §3 | `tests/test_eval_conductor_cases.py::test_every_gate_grader_is_an_expected_red_of_a_proof`<br>`tests/test_eval_conductor_cases.py::test_proof_rows_name_real_graders_of_their_cases`<br>`tests/test_eval_conductor_cases.py::test_report_run_id_is_proven_in_every_case`<br>`tests/test_eval_conductor_cases.py::test_f4_ac4_graders_have_distinct_proofs`<br>`tests/test_eval_conductor_cases.py::test_rev_proofs_resolve_to_a_conductor`<br>`tests/test_eval_conductor_cases.py::test_readme_mutations_match_the_patch_files`<br>`tests/test_eval_conductor_cases.py::test_mutation_applies_cleanly_to_a_fresh_assembly`<br>`tests/test_eval_conductor_cases.py::test_mutation_touches_only_the_conductor`<br>`tests/test_eval_conductor_cases.py::test_mutation_removes_and_adds_its_declared_clauses` |
| F7-AC5 | deterministic; §3 marks controls | `tests/test_eval_conductor_cases.py::test_every_control_is_listed_and_never_a_proof_target`<br>`tests/test_eval_conductor_cases.py::test_graders_split_into_controls_and_mapped_gates`<br>`tests/test_eval_conductor_cases.py::test_conductor_dispatched_control`<br>`tests/test_eval_conductor_cases.py::test_audit_ran_control` |
| F7-AC6 | live | G: three consecutive `GREEN 3/3 cases · runs 9` on `69f845c0` with `tree clean`. `git diff 69f845c0..HEAD --stat` at commit time shows only `docs/` files: no covered file (`tomo/dot_claude/agents/synthesis-conductor.md`, `tomo/dot_claude/commands/inbox.md`, `tomo/dot_claude/settings.json`), no stub and no runner changed after it |
| F8-AC1 | deterministic | `tests/test_run_evals.py::test_known_case_is_partial_suite`<br>`tests/test_eval_verdict.py::test_partial_suite_prefix`<br>`tests/test_run_evals.py::test_runs_with_case_reaches_cli` |
| F8-AC2 | deterministic | `tests/test_run_evals.py::test_unknown_case_refused_listing_cases` |
| F9-AC1 | deterministic | `tests/test_eval_verdict.py::test_compare_lists_only_differing_pairs`<br>`tests/test_eval_verdict.py::test_compare_disjoint_pair_reports_every_grader_of_both`<br>`tests/test_eval_verdict.py::test_compare_identical_prints_nothing`<br>`tests/test_eval_verdict.py::test_compare_accepts_results_directories`<br>`tests/test_eval_verdict.py::test_compare_directory_without_aggregate_is_a_clear_error` |

**F2-AC3 "no further run starts" is the CLI's own behaviour.** The CLI checks `--max-cost-usd` before each run launches. The suite proves two things. The cap reaches the CLI (`test_max_cost_flag_and_env_reach_cli_and_default_returns`). A capped result is NOT GRADED, never GREEN, even when every graded run passed. The scheduler itself is not under test. The SDD records this as an assumption.

**F1-AC4 is static for `install-tomo.sh`.** The dynamic sentinel run drives `update-tomo.sh` only. The static scan covers both scripts and is proven red by six injected copy lines.

**F2-AC5 "scaffold failure"** reaches the verdict reader as a run `error`, the same path as an API error. No scaffold failure has been observed live.

## 3. Gate graders: proof, RED, GREEN

Every gate grader was red in **3/3** runs under its proof (plan Phase 4 rule: red in every run). Each was then green in all 9 runs of each T5.1 re-run on the merge candidate `69f845c0`. Proof patches and the clause each removes are in [`evals/_mutations/README.md`](../../../../evals/_mutations/README.md). The full RED verdict lines are in [`red-proofs.md`](red-proofs.md).

| Case | Grader | PRD | Proof | RED | Proof results | GREEN on merge candidate |
|---|---|---|---|---|---|---|
| `audit-gates-delivery` | `1-audit-before-upload` | F3-AC1 | `--rev 4350ddd^` | 3/3 | `2026-10-25T16-49-48Z` | G, 3 × 3/3 |
| `audit-gates-delivery` | `2-audit-before-state-flip` | F3-AC2 | `--rev 4350ddd^` | 3/3 | `2026-10-25T16-49-48Z` | G, 3 × 3/3 |
| `audit-gates-delivery` | `3-audit-result-in-report` | F3-AC3 | `--mutation drop-audit-line` | 3/3 | `2026-10-25T16-51-47Z` | G, 3 × 3/3 |
| `audit-gates-delivery` | `4-no-notice-when-none-withheld` | F5-AC5 | `--mutation always-notice` | 3/3 | `2026-10-25T16-52-34Z` | G, 3 × 3/3 |
| `audit-gates-delivery` | `9-no-leak` | F6-AC1 | `--mutation report-run-id` | 3/3 | `2026-10-25T16-59-18Z` | G, 3 × 3/3 |
| `audit-mismatch-stops` | `1-no-upload-after-mismatch` | F4-AC1 | `--rev 4350ddd^` | 3/3 | `2026-10-25T16-50-49Z` | G, 3 × 3/3 |
| `audit-mismatch-stops` | `2-no-state-flip-after-mismatch` | F4-AC2 | `--rev 4350ddd^` | 3/3 | `2026-10-25T16-50-49Z` | G, 3 × 3/3 |
| `audit-mismatch-stops` | `4-mismatch-reported-verbatim` | F4-AC3 | `--mutation summarise-mismatch` | 3/3 | `2026-10-25T16-53-23Z` | G, 3 × 3/3 |
| `audit-mismatch-stops` | `5-no-write-into-scripts-schemas-config` | F4-AC4 | `--mutation write-into-scripts` | 3/3 | `2026-10-25T17-55-13Z` | G, 3 × 3/3 |
| `audit-mismatch-stops` | `6-no-copy-into-scripts-schemas-config` | F4-AC4 | `--mutation copy-into-config` | 3/3 | `2026-10-25T17-55-50Z` | G, 3 × 3/3 |
| `audit-mismatch-stops` | `9-no-leak` | F6-AC1 | `--mutation report-run-id` | 3/3 | `2026-10-25T16-59-18Z` | G, 3 × 3/3 |
| `withheld-notices-relayed` | `1-delete-1-verbatim` | F5-AC1/2 | `--mutation paraphrase-relay` | 3/3 | `2026-10-25T16-56-23Z` | G, 3 × 3/3 |
| `withheld-notices-relayed` | `2-delete-2-verbatim` | F5-AC1/2 | `--mutation paraphrase-relay` | 3/3 | `2026-10-25T16-56-23Z` | G, 3 × 3/3 |
| `withheld-notices-relayed` | `3-attachment-verbatim` | F5-AC3 | `--mutation paraphrase-relay` | 3/3 | `2026-10-25T16-56-23Z` | G, 3 × 3/3 |
| `withheld-notices-relayed` | `4-deletes-then-attachment-last` | F5-AC4 | `--mutation attachments-first`; `--mutation files-used-after` | 3/3; 3/3 | `2026-10-25T16-58-34Z`; `2026-10-25T16-57-32Z` | G, 3 × 3/3 |
| `withheld-notices-relayed` | `9-no-leak` | F6-AC1 | `--mutation report-run-id` | 3/3 | `2026-10-25T16-59-18Z` | G, 3 × 3/3 |

All proof results directories are under `tomo-tmp/evals/`. Every proof ran with `--runs 3`, `claude 2.1.310`, `tree clean`.

**Controls (exempt from RED proof, F7-AC5).** These four graders confirm preconditions, not behaviour, and no proof targets them:

- `audit-gates-delivery/0-conductor-dispatched`
- `audit-mismatch-stops/0-conductor-dispatched`
- `audit-mismatch-stops/3-audit-ran`
- `withheld-notices-relayed/0-conductor-dispatched`

They were green in every run of G, and no RED verdict line in `red-proofs.md` names one.

**Before and after the conductor fix.** On `main`'s conductor 0.23.0 (`baseline.md` T2.2) the suite was `RED 0/3 cases · runs 9 · $0.64`:

- no-leak passed 0/3 in every case;
- relay-last passed 0/3;
- the relay lines passed 2/3;
- the RESULT line passed 1/3.

The ordering, stop and no-tamper graders passed 3/3. Conductor 0.24.0 (ADR-10, one report-level STRICT) is GREEN 9/9 on every full run since attempt 2.

## 4. Gaps the trace found

Four criteria had a part that no test could fail. Each was closed by an assertion in this close-out. Each was proven RED by applying the mutation named below in an isolated `git archive HEAD` export with the new test files copied in, never in the worktree. An unmutated export was green first.

| Criterion | Part no test could fail | Assertion | Mutation that turns it red |
|---|---|---|---|
| F1-AC2 | "any Tomo instance … has not changed". The runner's tree check skips gitignored paths (its own comment says so), and no runner test had an instance in its fixture | `test_runner_leaves_every_tomo_instance_unchanged` (new): a gitignored repo-local `tomo-instance/` and a registered instance outside the repo, both byte-compared before and after | runner appends to `$ROOT/tomo-instance/config/vault-config.yaml`; and, separately, to the first instance path read from `$HOME/.tomo/instances.json`. Both red with "runner changed the instance at …" |
| F1-AC3 | "timestamped directory" and "under a gitignored location". No test checked the directory name, and nothing failed if the runner's `check-ignore` preflight was removed | `test_results_dir_is_a_utc_timestamp_named_in_the_verdict` (new); `test_results_location_not_gitignored_is_refused` (new) | `TS=latest`, which is red on the name; the `check-ignore` refusal replaced by `true`, which is red because results then dirty the repo |
| F1-AC5 | "names the required version". The test checked only that the installed version `2.1.268` was named | `test_old_claude_version_refused_before_eval` + `assert "2.1.269" in proc.stderr` | refusal text `is older than $MIN_CLAUDE_VERSION` changed to `is too old` |
| F7-AC2 / F7-AC3 | the PR record (verdict, cost, results path), "a `--case` run does not count", and "Other files need no run". The rule tests checked only `GREEN` and the file list | `test_claude_md_rule_states_the_pr_record_and_the_exemption` (new) | "Other files need no run." deleted from root `CLAUDE.md`; and, separately, "verdict line, cost and results path" cut to "verdict line" |

## 5. KPIs and spend

| KPI | Target | Measured | Verdict |
|---|---|---|---|
| Gate graders proven red | 100% | 16/16, each red 3/3 | 🟢 |
| Full-suite GREEN on the merge candidate | 3 consecutive | 3/3 (G) | 🟢 |
| Cost per full suite | median ≤ $2, cap $5 | median $0.59 ($0.64, $0.59, $0.59) | 🟢 |
| Wall-clock per full suite | ≤ 5 min | max 111 s (100, 103, 111) | 🟢 |
| Adoption (PRs touching a covered file carry a verdict) | 100% | first instance is this spec's own PR (T5.3) | open, measured from here on |

| Phase | Spend |
|---|---|
| Phase 1 (cost-cap fixture capture) | $0.06 |
| Phase 2 (cases load + baseline) | $0.90 |
| Phase 3 (conductor fix, partial + full runs) | $1.78 |
| Phase 4 (RED proofs; incl. $1.47 abandoned or voided) | $4.10 |
| Phase 5 (three close-out runs $1.76, re-run after the drift fixes $1.82) | $3.58 |
| **Spec total** | **$10.42** |

The $1.47 in Phase 4 went to two groups of runs. $0.84 went to the "fix the failing script" mutations, which never executed (§7). $0.43 went to two rev proofs voided by `NOT GRADED · tree changed during run`, because agents were writing to the worktree. The remaining $0.20 was the `always-notice` diagnosis rerun.

## 6. Validation

- **Full pytest:** `5421 passed, 4 skipped, 1 warning in 188.73s` (2026-10-26), on the tree this close-out commits. The skips are environmental and are not 041 tests. The warning is a pre-existing `return` in `tests/test-008-phase1.py`.
- **ruff:** `ruff check .` is clean (`All checks passed!`, 2026-10-26).
- **`scripts/run-evals.sh --help` against `evals/README.md`:** they agree on the options, the exit codes 0–3 and their meanings, the results location, the cost cap and its overrides, and the sandbox requirement. One soft difference is not a contradiction. `--help` says "about $0.50-2 per full suite" and the README says "about $0.60 … measured". The measured figure lies inside the help's range.

## 7. Open items

- **Stub drift.** The cases run against stubs whose output is copied from the real scripts. Since `c261cc0b` and `5d3db600` the upload, render and state-promoter stubs print the real success formats on the real stream (stderr; the state flip is silent), and `ast`-based drift guards in `tests/test_eval_suite_shape.py` pin those strings to the scripts' source. There is still no runtime contract check tying a stub to its script, by owner decision (PRD Won't Have): a script whose output format changes in a way the guards do not read can leave a case green against output production no longer produces. Mitigation today: one kit (`evals/_lib/stubs.sh`), with the source of each string named, plus the guards.
- **Verdict-line path.** Since `183b38f5` the verdict line carries a repo-relative results path (`--root`). The lines quoted in `baseline.md` and `red-proofs.md` were recorded before that and their absolute prefix was shortened to the repo-relative form by hand when the documents were written; the printed lines of those runs were not repo-relative. The results directories named there are unaffected.
- **Drift-validation findings fixed in this batch.** The spike archive no longer contains local absolute paths or the `env | sort` dump (`test_spike_archive_carries_no_local_paths_or_environment_dump`); `scripts/CLAUDE.md` lists `run-evals.sh` and `lib/eval_verdict.py` (`test_scripts_claude_md_lists_the_runner_and_the_verdict_reader`); the SDD directory map lists `tests/test_eval_gate_docs.py`; the PRD and SDD acceptance checkboxes are ticked for the 35 criteria traced above; `evals/_mutations/README.md` now gives the `report-run-id` invocation the recorded proof used (`--case '*'`, which is why its verdict line is `PARTIAL SUITE`; the exact glob was not recorded and is inferred from the three cases it ran).
- **Stub fidelity is pinned by tests that evidence no single criterion.** `test_upload_stub_prints_real_success_lines_on_stderr`, `test_upload_stub_without_render_fails_like_the_real_script` and `test_state_promoter_stub_flip_is_silent_like_the_real_script` (`tests/test_eval_suite_shape.py`) keep the upload and state-promoter stubs on the real scripts' formats and stream. They guard the fidelity of the fixtures behind F3–F5 and are not part of the §1 invocation.
- **Hand-listed guard names in the leak guard.** `evals/_lib/no-leak.md` lists guard and function names by hand. A new internal name that can reach the report must be added there and re-copied into every case (`evals/README.md` "Adding a case", step 3). Nothing detects the omission.
- **Stale `tomo/skills/` mention in root `CLAUDE.md`.** The "Runtime files in `tomo/`" bullet under Rules still names `tomo/skills/`, which no longer exists. This predates the spec, is out of scope, and is noted for a docs sweep.
- **The failed-step line is unmeasured.** No case drives a failed upload or state flip. The conductor's `<step> exited <code> for "<note>".` line (attempt 3, owner decision after code review) is therefore not graded. Attempt 3 proves only that the change did not regress the covered behaviour.
- **F4-AC4 graders' residual limits.** Graders 5 and 6 are pattern checks. The writes that still escape them and the cases where they over-fire are listed in `evals/README.md` "Known limits". Examples of escapes: `python -c "open(…,'w')"`, `patch`, `git apply`, `dd of=`, `cp -t`, and backslash-continued `cp`.
- **The F4-AC4 proofs are neutral write/copy steps, not "fix the failing script".** The planned mutations told the conductor to repair the failing audit script. In 6 runs, including one with every contradicting clause removed, the model never ran the injected command. Owner decision 2026-10-25: prove graders 5 and 6 with a neutral bookkeeping step instead (`write-into-scripts`, `copy-into-config`). These prove the graders see such a write. They do not prove the conductor resists an instruction to tamper, because no mutation could make it try. The investigation found a real grader gap on the way and fixed it in `1612c943`: a command after an encoded newline in one Bash call escaped both graders.
- **Subagent trace visibility is observed, not documented.** If a Claude Code release stops reporting subagent tool calls, the `3-audit-ran` control turns red with no prose change. That control is the canary.

---
title: "Close-out — 043 eval gate for the Pass 1 conductor"
status: complete
---

# Close-out

## Standing rule for this document

Every PRD criterion below traces to evidence that was **executed**, not to a task that mentions it:

- Criteria about the stand-ins, the cases' files, the grader patterns, the mutation records and the documents trace to pytest node ids, all run in the one invocation of §1.
- Criteria about what a model does (the main session running Pass 1, the synthesis conductor's reply) trace to eval graders. Each such criterion carries both kinds of evidence. Pytest proves the grader's shape on recorded and hand-edited traces (it is red on the deviation and green on the compliant run). The eval runs prove the behaviour: red 3/3 under a named proof in [`red-proofs.md`](red-proofs.md), green in every run of the merge evidence G.
- Criteria about cost, duration and the merge candidate trace to recorded runs, quoted unedited from [`red-proofs.md`](red-proofs.md) or [`findings.md`](findings.md).

For each criterion the trace names the **mechanism** the evidence falsifies: the concrete change that would turn it red.

The results directories (`tomo-tmp/evals/<TS>/`) are gitignored and local. This document cites their paths only. `requirements.md` was not edited. Where a criterion's wording was changed by an owner decision, the trace cites the README Decisions Log row.

## Criteria count

`requirements.md` v1.0 carries **31** criteria: F1:10 F2:4 F3:4 F4:4 F5:4 F6:4 F7:1. **31/31 trace to executed evidence.**

- 17 trace to a gate grader: pytest for the grader's shape, plus a RED proof and G (F1-AC1–10, F2-AC1–4, F4-AC1, F4-AC2, F4-AC4).
- 1 traces to pytest plus G, as a control with no mutation by design (F4-AC3, the canary).
- 4 trace to pytest plus the recorded proofs (F5-AC1–4).
- 7 trace to pytest alone (F3-AC1–4, F6-AC1, F6-AC2, F7-AC1). F3 also has the supporting run evidence that every Pass 1 run in G reached the end of the pipeline.
- 2 trace to recorded runs (F6-AC3 alone; F6-AC4 with a pytest id for the default cap).

Three criteria parts had no test that could fail. All three are now closed by RED-proven tests (§4). Five criteria parts stay open (§4).

## 1. The single invocation

The **98 node ids** in the trace table ran **together in one `pytest` invocation on 2026-10-31**, on branch `spec/043-pass1-conductor-eval-gate` at `9c3b7c66` with `tests/test_043_close_out_gaps.py` added (uncommitted at the time of the run):

```
543 passed in 28.27s
```

98 node ids collect **543 items**. The difference is parametrisation, mostly `test_offline_validation_table` (one item per fixture × grader row). Collection was checked by script, not by eye: the sorted list of cited node ids and the sorted list of collected node ids (parameters stripped) are identical. Nothing was deselected and nothing extra was collected.

<details><summary>The command, exactly as run</summary>

```bash
PYTHONDONTWRITEBYTECODE=1 ./venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_run_evals.py::test_pass1_case_files_are_as_specified \
  tests/test_run_evals.py::test_pass1_case_passes_preflight_and_its_scaffold_stages \
  tests/test_pass1_stub_kit.py::test_triage_writes_routing_plan \
  tests/test_pass1_stub_kit.py::test_read_config_field \
  tests/test_pass1_stub_kit.py::test_read_routing_plan_modes \
  tests/test_043_grader_patterns.py::test_offline_validation_table \
  tests/test_043_grader_patterns.py::test_every_pass1_case_grader_is_validated_offline \
  tests/test_043_grader_patterns.py::test_every_fixture_and_grader_in_the_table_exists \
  tests/test_043_grader_patterns.py::test_builder_variants_regenerate_the_committed_fixtures \
  tests/test_043_grader_patterns.py::test_every_grader_file_uses_only_keys_the_cli_accepts \
  tests/test_043_grader_patterns.py::test_every_grader_file_regex_is_js_compatible \
  tests/test_043_grader_patterns.py::test_tool_used_min0_max0_passes_only_when_absent \
  tests/test_043_grader_patterns.py::test_tool_used_min_defaults_to_one_and_max_bounds \
  tests/test_043_grader_patterns.py::test_tool_order_compares_first_matching_indices \
  tests/test_043_grader_patterns.py::test_tool_order_counts_subagent_calls_in_trace_order \
  tests/test_043_grader_patterns.py::test_mark_after_json_write_orders_calls_and_chained_commands \
  tests/test_043_grader_patterns.py::test_last_message_is_the_last_assistant_text_not_the_result_frame \
  tests/test_043_grader_patterns.py::test_regex_anchors_follow_js_without_flags \
  tests/test_043_grader_patterns.py::test_report_graders_match_the_skill_template_lines \
  tests/test_043_grader_patterns.py::test_relay_report_grader_is_the_pipeline_report_grader \
  tests/test_043_grader_patterns.py::test_warn_grader_matches_the_kit_warn_line \
  tests/test_043_grader_patterns.py::test_skill_relays_warn_with_a_cat_before_the_first_dispatch_and_in_the_report \
  tests/test_043_grader_patterns.py::test_every_pass2_report_only_and_canary_grader_is_validated_offline \
  tests/test_043_grader_patterns.py::test_relay_fixture_carries_the_kit_relay_lines \
  tests/test_043_grader_patterns.py::test_mismatch_fixture_carries_the_kit_audit_lines \
  tests/test_043_grader_patterns.py::test_report_only_rejects_text_on_or_after_a_known_line \
  tests/test_043_grader_patterns.py::test_apply_match_count_is_exact \
  tests/test_043_warnings_out.py::test_the_file_holds_exactly_the_warn_lines_printed \
  tests/test_043_warnings_out.py::test_no_warnings_leaves_an_empty_file \
  tests/test_043_warnings_out.py::test_a_clean_run_truncates_an_earlier_warning \
  tests/test_043_warnings_out.py::test_an_error_exit_still_rewrites_the_file \
  tests/test_pass1_stub_kit.py::test_shared_ctx_builder_warn_line \
  tests/test_pass1_stub_kit.py::test_run_id_stub \
  tests/test_pass1_stub_kit.py::test_analyst_stub_writes_result_and_state \
  tests/test_pass1_stub_kit.py::test_analyst_stub_filename_matches_real_to_filename_on_odd_keys \
  tests/test_pass1_stub_kit.py::test_reducer_doc_matches_summary_line \
  tests/test_pass1_stub_kit.py::test_reducer_succeeds_when_every_routed_item_has_a_result \
  tests/test_pass1_stub_kit.py::test_reducer_fails_when_results_lag_state \
  tests/test_pass1_stub_kit.py::test_reducer_fails_when_no_analyst_has_run \
  tests/test_pass1_stub_kit.py::test_reducer_fails_between_analyst_batches \
  tests/test_pass1_stub_kit.py::test_render_output \
  tests/test_pass1_stub_kit.py::test_kado_write_and_mark_captured_lines \
  tests/test_pass1_stub_kit.py::test_calls_log_records_every_call \
  tests/test_pass1_stub_kit.py::test_copied_formats_still_in_real_scripts \
  tests/test_pass1_stub_kit.py::test_inline_to_filename_is_a_copy_of_the_real_one \
  tests/test_pass1_stub_kit.py::test_unknown_flag_exits_2 \
  tests/test_pass1_stub_kit.py::test_missing_required_flag_exits_2 \
  tests/test_pass1_stub_kit.py::test_read_routing_plan_rejects_unused_modes \
  tests/test_pass1_stub_kit.py::test_read_routing_plan_rejects_bad_flags \
  tests/test_pass1_stub_kit.py::test_invalid_variable_returns_1 \
  tests/test_pass1_stub_kit.py::test_nothing_written_outside_the_workspace \
  tests/test_run_evals.py::test_assembled_copy_carries_the_analyst_stand_in \
  tests/test_run_evals.py::test_stand_in_comes_from_the_working_tree_under_rev \
  tests/test_run_evals.py::test_missing_stand_in_is_refused_without_a_claude_call \
  tests/test_run_evals.py::test_runner_leaves_every_tomo_instance_unchanged \
  tests/test_run_evals.py::test_max_cost_flag_and_env_reach_cli_and_default_returns \
  tests/test_run_evals.py::test_spec_043_mutation_applies_in_the_runner_and_changes_only_its_files \
  tests/test_eval_conductor_cases.py::test_setup_in_conductor_passes_the_strict_shared_ctx_stub \
  tests/test_eval_conductor_cases.py::test_inline_python_read_injects_one_command_grader_13_sees \
  tests/test_eval_conductor_cases.py::test_publish_md_with_write_tool_targets_what_grader_11_sees \
  tests/test_eval_conductor_cases.py::test_always_duplicate_line_reports_a_zero_count_grader_15_sees \
  tests/test_eval_conductor_cases.py::test_render_before_reduce_injects_a_render_grader_08_sees_before_the_reduce \
  tests/test_eval_conductor_cases.py::test_pass1_leak_guards_inherit_the_recorded_leak_guard_proof \
  tests/test_eval_conductor_cases.py::test_case_leak_guard_is_byte_identical \
  tests/test_eval_conductor_cases.py::test_status_sentence_first_expects_every_report_only_grader_and_spares_the_canary \
  tests/test_eval_conductor_cases.py::test_status_sentence_first_removes_the_reply_only_rule_and_the_3c_anchor \
  tests/test_eval_conductor_cases.py::test_reply_only_ban_is_its_own_rule_naming_every_report \
  tests/test_eval_conductor_cases.py::test_3c_says_the_stop_report_starts_with_the_audits_first_line \
  tests/test_eval_conductor_cases.py::test_every_gate_grader_is_an_expected_red_of_a_proof \
  tests/test_eval_conductor_cases.py::test_proof_rows_name_real_graders_of_their_cases \
  tests/test_eval_conductor_cases.py::test_readme_mutations_match_the_patch_files \
  tests/test_eval_conductor_cases.py::test_mutation_applies_cleanly_to_a_fresh_assembly \
  tests/test_eval_conductor_cases.py::test_spec_043_mutation_touches_only_its_declared_files \
  tests/test_eval_conductor_cases.py::test_mutation_removes_and_adds_its_declared_clauses \
  tests/test_eval_conductor_cases.py::test_spec_043_mutations_add_ordinary_prose \
  tests/test_eval_conductor_cases.py::test_spec_043_rows_name_their_offline_model \
  tests/test_eval_conductor_cases.py::test_recorded_rows_carry_measured_side_effects \
  tests/test_eval_conductor_cases.py::test_neutral_write_mutations_trip_only_their_grader \
  tests/test_eval_conductor_cases.py::test_every_control_is_listed_and_never_a_proof_target \
  tests/test_eval_conductor_cases.py::test_graders_split_into_controls_and_mapped_gates \
  tests/test_eval_conductor_cases.py::test_conductor_dispatched_control \
  tests/test_eval_conductor_cases.py::test_audit_ran_control \
  tests/test_eval_conductor_cases.py::test_failing_script_ran_controls \
  tests/test_eval_gate_docs.py::test_report_only_and_canary_are_byte_identical_in_the_four_standard_cases \
  tests/test_eval_gate_docs.py::test_mismatch_case_carries_its_own_report_only_and_the_shared_canary \
  tests/test_eval_gate_docs.py::test_pass1_files_are_rows_with_both_pass1_cases \
  tests/test_eval_gate_docs.py::test_inbox_and_settings_rows_list_all_seven_cases \
  tests/test_eval_gate_docs.py::test_every_covered_path_exists \
  tests/test_eval_gate_docs.py::test_prd_named_files_are_in_the_table \
  tests/test_eval_gate_docs.py::test_every_table_row_names_an_existing_case \
  tests/test_eval_gate_docs.py::test_every_case_directory_appears_in_the_table \
  tests/test_eval_gate_docs.py::test_every_case_named_in_the_table_exists \
  tests/test_eval_gate_docs.py::test_claude_md_rule_names_the_pass1_files \
  tests/test_eval_gate_docs.py::test_claude_md_rule_tracks_the_coverage_table \
  tests/test_eval_gate_docs.py::test_every_repo_path_in_the_readme_exists \
  tests/test_043_close_out_gaps.py::test_every_spec_043_proof_is_recorded_red_in_3_of_3_with_its_results_path \
  tests/test_043_close_out_gaps.py::test_known_limits_name_the_three_spike_limits \
  tests/test_043_close_out_gaps.py::test_the_analyst_stand_in_and_the_stub_kit_cannot_reach_kado
```

</details>

## 2. Trace

Eval-run shorthand used in the table:

- **G** is the merge evidence: three consecutive full-suite GREENs on the merge candidate `99a6f50cf8cc574e04f402d79f3b7bd8830740f2` (`synthesis-conductor` 0.25.0 on sonnet), from [`red-proofs.md`](red-proofs.md) "T4.3 — merge evidence", second attempt. Verbatim:
  - `GREEN 7/7 cases · runs 21 · $2.75 · 271 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T16-47-57Z`
  - `GREEN 7/7 cases · runs 21 · $2.76 · 310 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T16-52-30Z`
  - `GREEN 7/7 cases · runs 21 · $2.74 · 286 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T16-57-42Z`

  Every gate grader of every case was green in all 9 of its runs (a GREEN verdict line names no failing grader).
- **R `<name>`** is the RED proof `--mutation <name>` in [`red-proofs.md`](red-proofs.md), each red 3/3 for every expected grader (§3).
- **offline** means rows of `tests/test_043_grader_patterns.py::test_offline_validation_table`: the grader evaluated, with the CLI's semantics, on a fixture under [`fixtures/`](fixtures/). The fixture names the rows use are given in the cell. A red row is the deviation the grader must catch; a green row is a compliant trace it must spare.

| Criterion | Class | Evidence | Mechanism the evidence falsifies |
|---|---|---|---|
| F1-AC1 | grader | `pass1-suggest-pipeline/01-conductor-not-dispatched`; R `dispatch-conductor`; G<br>offline: `pass1-conductor-dispatched` red, `pass1-analyst-mentions-conductor` and `pass1-complete` green<br>`tests/test_run_evals.py::test_pass1_case_files_are_as_specified` (prompt `/tomo:inbox`, scaffold `SHARED_CTX_WARN=0 DUPLICATES=0`)<br>`tests/test_pass1_stub_kit.py::test_triage_writes_routing_plan` (3 fresh notes, `100 Inbox/Places/Dresden.md` among them)<br>`tests/test_pass1_stub_kit.py::test_read_config_field` (batch size `2`)<br>`tests/test_pass1_stub_kit.py::test_read_routing_plan_modes` (2 batches of 2 and 1)<br>`tests/test_run_evals.py::test_pass1_case_passes_preflight_and_its_scaffold_stages` | `/inbox` dispatching `suggestion-conductor` as a subagent instead of the main session impersonating it. The "Given" (3 notes, one in a subfolder, batch size 2) is pinned by the stub-kit tests: a fixture change that drops the subfolder note or the batch size turns them red |
| F1-AC2 | grader | `02-analyst-dispatched-3x`, `03-no-general-purpose`; R `analyst-name-not-type` (re-proof, Block D); G<br>offline: `pass1-analyst-general-purpose` and `pass1-analyst-name-not-type` red on both; `pass1-complete`, `pass1-spike` green<br>`tests/test_043_grader_patterns.py::test_tool_used_min0_max0_passes_only_when_absent`<br>`tests/test_043_grader_patterns.py::test_tool_used_min_defaults_to_one_and_max_bounds`<br>`tests/test_run_evals.py::test_assembled_copy_carries_the_analyst_stand_in` | A dispatch count other than 3 that names `tomo:inbox-analyst`; any `Agent` call typed `general-purpose` or carrying no `subagent_type` (which silently runs general-purpose). See gap O3 for what "exactly 3 dispatches" does not count |
| F1-AC3 | grader | `04-subfolder-path-and-key`; R `path-from-stem` (re-proof); G<br>offline: `pass1-dresden-path-flattened` and `pass1-dresden-key-flattened` red; `pass1-spike`, `pass1-complete` green | The subfolder note's `path` or its `item_key` rebuilt from the stem (`100 Inbox/Dresden.md`). The live proof flattens `path` only; the `item_key` half is falsified offline by the key-flattened fixture |
| F1-AC4 | grader | `05-shared-ctx-once`, `06-run-id-once`, `07-setup-before-dispatch`; R `setup-in-conductor` (re-proof), R `dispatch-before-setup`; G<br>offline: `pass1-setup-twice` red on 05 and 06, `pass1-dispatch-before-setup` red on 07<br>`tests/test_043_grader_patterns.py::test_tool_order_compares_first_matching_indices`<br>`tests/test_eval_conductor_cases.py::test_setup_in_conductor_passes_the_strict_shared_ctx_stub` | A second `shared-ctx-builder.py` or `run-id.py` call (the f3b478b9 double setup); the shared context built after the first `Agent` call |
| F1-AC5 | grader | `08-reducer-before-render`, `09-reduce-after-last-dispatch`; R `render-before-reduce` (re-proof), R `reduce-before-batch-2`; G<br>offline: `pass1-render-before-reduce`, `pass1-reducer-before-dispatch` red on 08; `pass1-reducer-before-dispatch`, `pass1-reducer-between-dispatches` red on 09<br>`tests/test_pass1_stub_kit.py::test_reducer_fails_between_analyst_batches`<br>`tests/test_pass1_stub_kit.py::test_reducer_fails_when_no_analyst_has_run`<br>`tests/test_eval_conductor_cases.py::test_render_before_reduce_injects_a_render_grader_08_sees_before_the_reduce` | A render before the first reduce; any analyst dispatch after a reducer call. "Render after the last dispatch" has no grader of its own and follows from both: the first render is after the first reduce (08), and no dispatch follows any reduce (09) |
| F1-AC6 | grader | `10-two-script-writes-same-stem`, `11-no-inline-vault-write`; R `publish-md-with-write-tool`; G<br>offline: `pass1-two-writes-different-stem`, `pass1-write-tool-publish` red on 10; `pass1-write-tool-publish` red on 11; `pass1-complete-prefixed-writes`, `pass1-complete-chained-writes` green on 10<br>`tests/test_eval_conductor_cases.py::test_publish_md_with_write_tool_targets_what_grader_11_sees`<br>`tests/test_pass1_stub_kit.py::test_kado_write_and_mark_captured_lines` | One of the two artefacts not published through `kado-write-file.py`, or published under a different stem; a `Write` tool call into `100 Inbox/`. See gap O2: the production failure mode (content passed to `mcp__kado__kado-write`) cannot occur in the eval |
| F1-AC7 | grader | `12a-mark-captured-once`, `12b-mark-captured-after-json-write`; R `mark-before-write`; G<br>offline: `pass1-mark-twice`, `pass1-mark-before-json-write`, `pass1-mark-between-writes` red<br>`tests/test_043_grader_patterns.py::test_mark_after_json_write_orders_calls_and_chained_commands` | A second `mark-captured.py` call; a `mark-captured.py` call followed by the `.json` write. "After both writes" holds with 10, which requires the `.md` write before the `.json` write |
| F1-AC8 | grader | `13-no-inline-python`; R `inline-python-read`; G<br>offline: `pass1-inline-python` red<br>`tests/test_eval_conductor_cases.py::test_inline_python_read_injects_one_command_grader_13_sees` | Any Bash call carrying `python3 -c` (the 7e53ad6f regression), anywhere in the run |
| F1-AC9 | grader | `14-report-line-anchored`, `9-no-leak`; R `reword-report-line`; `9-no-leak` inherits R `report-run-id` (byte copy); G<br>offline: `pass1-report-quoted` red (the line quoted inside a sentence), `pass1-complete` green<br>`tests/test_043_grader_patterns.py::test_report_graders_match_the_skill_template_lines`<br>`tests/test_043_grader_patterns.py::test_regex_anchors_follow_js_without_flags`<br>`tests/test_043_grader_patterns.py::test_last_message_is_the_last_assistant_text_not_the_result_frame`<br>`tests/test_eval_conductor_cases.py::test_pass1_leak_guards_inherit_the_recorded_leak_guard_proof`<br>`tests/test_eval_conductor_cases.py::test_case_leak_guard_is_byte_identical` | A reworded completion line, a count other than 3, a missing `[[<date>_suggestions]]` link, the line only quoted mid-sentence; any run id, temp path or guard name in the reply. See gap O1: "begins with" is graded as "starts a line", not "starts the reply" |
| F1-AC10 | grader | `15-no-duplicate-line`; R `always-duplicate-line`; G<br>offline: `pass1-complete-relayed` red, `pass1-complete` green<br>`tests/test_eval_conductor_cases.py::test_always_duplicate_line_reports_a_zero_count_grader_15_sees`<br>`tests/test_pass1_stub_kit.py::test_reducer_doc_matches_summary_line` (`duplicate_proposals_converted=0`) | The duplicate line reported at a zero count |
| F2-AC1 | grader | `pass1-warn-and-duplicates-relayed/01-warn-in-reply`; R `warn-is-diagnostic`; G<br>offline: `pass1-complete`, `pass1-warn-in-report-only` cases<br>`tests/test_043_grader_patterns.py::test_warn_grader_matches_the_kit_warn_line`<br>`tests/test_pass1_stub_kit.py::test_shared_ctx_builder_warn_line`<br>`tests/test_043_grader_patterns.py::test_skill_relays_warn_with_a_cat_before_the_first_dispatch_and_in_the_report` | The `WARN:` line missing from the final reply, or not verbatim (prefix `WARN: ` included, owner decision 2026-10-31) |
| F2-AC2 | grader | `02-warn-before-first-dispatch`; R `warn-in-report-only`; G<br>offline: `pass1-cat-after-dispatch`, `pass1-cat-empty`, `pass1-warn-in-report-only` and every fixture without a `cat` red; `pass1-cat-before-dispatch`, `pass1-cat-batched` (the F6 shape), `pass1-complete-relayed` green<br>`tests/test_043_warnings_out.py::test_the_file_holds_exactly_the_warn_lines_printed`<br>`tests/test_043_warnings_out.py::test_no_warnings_leaves_an_empty_file`<br>`tests/test_043_warnings_out.py::test_a_clean_run_truncates_an_earlier_warning`<br>`tests/test_043_warnings_out.py::test_an_error_exit_still_rewrites_the_file` | No `cat tomo-tmp/setup-warnings.txt` before the first `Agent` call, or a `cat` whose result (bound by `tool_use_id`) does not carry the `WARN:` line. The criterion is the redefined one (README Decisions Log 2026-10-31, findings F4): a tool result counts as shown. The `--warnings-out` tests prove the real builder writes the file the `cat` reads; in the eval it is the stub's |
| F2-AC3 | grader | `03-duplicate-line`; R `drop-duplicate-line`; G<br>offline: `pass1-complete` red, `pass1-complete-relayed` green<br>`tests/test_043_grader_patterns.py::test_report_graders_match_the_skill_template_lines` | The duplicate line dropped, singularised (findings F3) or reworded |
| F2-AC4 | grader | `04-report-line-anchored`, `9-no-leak`; R `reword-report-line`; `9-no-leak` inherits R `report-run-id`; G<br>`tests/test_043_grader_patterns.py::test_relay_report_grader_is_the_pipeline_report_grader` | As F1-AC9, in the relay case. Gap O1 applies here too |
| F3-AC1 | test | `tests/test_pass1_stub_kit.py::test_analyst_stub_writes_result_and_state`<br>`tests/test_pass1_stub_kit.py::test_analyst_stub_filename_matches_real_to_filename_on_odd_keys`<br>`tests/test_pass1_stub_kit.py::test_reducer_succeeds_when_every_routed_item_has_a_result`<br>`tests/test_run_evals.py::test_assembled_copy_carries_the_analyst_stand_in`<br>`tests/test_run_evals.py::test_stand_in_comes_from_the_working_tree_under_rev`<br>`tests/test_run_evals.py::test_missing_stand_in_is_refused_without_a_claude_call`<br>`tests/test_043_close_out_gaps.py::test_the_analyst_stand_in_and_the_stub_kit_cannot_reach_kado` (new, §4)<br>supporting: G (every Pass 1 run reached the report) | The stand-in writing no result, or one under a file name the reducer does not read; the real analyst reaching the eval; the stand-in granted a tool beyond Bash, or a stub that opens a network connection |
| F3-AC2 | test | `tests/test_pass1_stub_kit.py::test_reducer_doc_matches_summary_line`<br>`tests/test_pass1_stub_kit.py::test_render_output` (3 sections, `mocs=` count, > 1024 bytes, schema-valid wire)<br>`tests/test_pass1_stub_kit.py::test_kado_write_and_mark_captured_lines`<br>`tests/test_pass1_stub_kit.py::test_copied_formats_still_in_real_scripts`<br>`tests/test_pass1_stub_kit.py::test_inline_to_filename_is_a_copy_of_the_real_one`<br>`tests/test_pass1_stub_kit.py::test_calls_log_records_every_call`<br>supporting: G | A reducer or renderer whose files disagree with its own summary line; a printed format that drifts from the real script's source. "Large enough to pass the conductor's sanity check" has no numeric rule in the runtime prose to test against; the 1024-byte floor is the stand-in's own, and the run evidence is that no run in G stopped early |
| F3-AC3 | test | `tests/test_pass1_stub_kit.py::test_unknown_flag_exits_2`<br>`tests/test_pass1_stub_kit.py::test_missing_required_flag_exits_2`<br>`tests/test_pass1_stub_kit.py::test_read_routing_plan_rejects_unused_modes`<br>`tests/test_pass1_stub_kit.py::test_read_routing_plan_rejects_bad_flags`<br>`tests/test_pass1_stub_kit.py::test_reducer_fails_when_results_lag_state`<br>`tests/test_pass1_stub_kit.py::test_reducer_fails_when_no_analyst_has_run`<br>`tests/test_pass1_stub_kit.py::test_reducer_fails_between_analyst_batches`<br>`tests/test_pass1_stub_kit.py::test_invalid_variable_returns_1` | A stub that returns plausible output on an argv no Pass 1 step passes, or a reducer that succeeds before every routed item has a result (owner decision 2026-10-31, the `fresh_sources` check) |
| F3-AC4 | test | `tests/test_pass1_stub_kit.py::test_nothing_written_outside_the_workspace`<br>`tests/test_run_evals.py::test_runner_leaves_every_tomo_instance_unchanged`<br>`tests/test_run_evals.py::test_pass1_case_files_are_as_specified` (`allowed_tools` exactly `Agent, Bash, Read, Skill, Write`: no MCP tool)<br>`tests/test_043_close_out_gaps.py::test_the_analyst_stand_in_and_the_stub_kit_cannot_reach_kado` (new, §4)<br>supporting: `tree clean` in every verdict line of G | The stub pipeline writing into the repo or `~/.tomo`; the runner touching an instance; a Kado tool or network call made reachable. See gap O4: reads, and the model's own tool calls in a paid run, are not checked |
| F4-AC1 | grader | `7-report-only` in the four standard Pass 2 cases; R `status-sentence-first` (Block B on haiku, Block S on sonnet); G<br>offline: `pass2-spike`, `pass2-withheld-relayed`, `pass2-state-flip-failed`, `pass2-stamped` green; `pass2-status-sentence`, `pass2-relay-introduced`, `pass2-no-handback` red<br>`tests/test_043_grader_patterns.py::test_every_pass2_report_only_and_canary_grader_is_validated_offline`<br>`tests/test_043_grader_patterns.py::test_report_only_rejects_text_on_or_after_a_known_line`<br>`tests/test_043_grader_patterns.py::test_relay_fixture_carries_the_kit_relay_lines`<br>`tests/test_eval_gate_docs.py::test_report_only_and_canary_are_byte_identical_in_the_four_standard_cases` | Any text in the conductor's hand-back frame (`The report follows:` … `agentId:`) that is not a report line. The grader reads the frame, not `last_message`, so the main session's relay cannot satisfy it |
| F4-AC2 | grader | as F4-AC1; R `status-sentence-first` red 3/3 in all five cases, the canary green throughout<br>`tests/test_eval_conductor_cases.py::test_status_sentence_first_expects_every_report_only_grader_and_spares_the_canary`<br>`tests/test_eval_conductor_cases.py::test_status_sentence_first_removes_the_reply_only_rule_and_the_3c_anchor`<br>`tests/test_eval_conductor_cases.py::test_reply_only_ban_is_its_own_rule_naming_every_report` | A status sentence before the report. On sonnet the vague first form stayed green in 1 of 3 runs; the literal `Status: run finished.` line (99a6f50c) is red 3/3 |
| F4-AC3 | test + run | `8-handback-canary` (control, `count:1`), all five Pass 2 cases; G<br>offline: `pass2-no-handback`, `pass2-duplicate-handback`, `pass1-spike` (no frame) red; `pass2-spike`, `pass2-status-sentence`, `pass2-mismatch-report` green<br>`tests/test_043_grader_patterns.py::test_apply_match_count_is_exact`<br>`tests/test_eval_conductor_cases.py::test_every_control_is_listed_and_never_a_proof_target` | The hand-back frame missing or repeated. As a control it has no mutation (F5-AC3). It did go red live, under proofs that pulled extra text in: `report-run-id` (`audit-mismatch-stops`, run 0, Block C) and `files-used-after` (run 2, Block S) |
| F4-AC4 | grader | `audit-mismatch-stops/7-report-only-mismatch`; R `status-sentence-first`; G<br>offline: `pass2-mismatch-report`, `pass2-mismatch-fenced`, `pass2-mismatch-labelled` green; `pass2-mismatch-status-sentence`, `pass2-spike`, `pass2-no-handback` red<br>`tests/test_043_grader_patterns.py::test_mismatch_fixture_carries_the_kit_audit_lines`<br>`tests/test_eval_gate_docs.py::test_mismatch_case_carries_its_own_report_only_and_the_shared_canary`<br>`tests/test_eval_conductor_cases.py::test_3c_says_the_stop_report_starts_with_the_audits_first_line` | The mismatch case graded by the standard shape (it would be red on a correct stop), or the standard cases graded by the mismatch shape; a preface before the stop report (findings F5) |
| F5-AC1 | test + runs | [`red-proofs.md`](red-proofs.md) Blocks A–D, S<br>`tests/test_eval_conductor_cases.py::test_every_gate_grader_is_an_expected_red_of_a_proof`<br>`tests/test_eval_conductor_cases.py::test_proof_rows_name_real_graders_of_their_cases`<br>`tests/test_eval_conductor_cases.py::test_readme_mutations_match_the_patch_files`<br>`tests/test_eval_conductor_cases.py::test_mutation_applies_cleanly_to_a_fresh_assembly`<br>`tests/test_eval_conductor_cases.py::test_spec_043_mutation_touches_only_its_declared_files`<br>`tests/test_eval_conductor_cases.py::test_mutation_removes_and_adds_its_declared_clauses`<br>`tests/test_run_evals.py::test_spec_043_mutation_applies_in_the_runner_and_changes_only_its_files`<br>`tests/test_043_close_out_gaps.py::test_every_spec_043_proof_is_recorded_red_in_3_of_3_with_its_results_path` (new, §4) | A gate grader with no recorded proof; a patch that no longer applies or touches undeclared files; a recorded proof whose verdicts are not red in runs 0, 1 and 2 |
| F5-AC2 | test + runs | `tests/test_eval_conductor_cases.py::test_spec_043_mutations_add_ordinary_prose`<br>`tests/test_eval_conductor_cases.py::test_inline_python_read_injects_one_command_grader_13_sees`<br>`tests/test_eval_conductor_cases.py::test_publish_md_with_write_tool_targets_what_grader_11_sees`<br>`tests/test_eval_conductor_cases.py::test_always_duplicate_line_reports_a_zero_count_grader_15_sees`<br>`tests/test_eval_conductor_cases.py::test_neutral_write_mutations_trip_only_their_grader`<br>runs: R `inline-python-read`, `publish-md-with-write-tool`, `always-duplicate-line`, and the Block D neutral re-proofs | A "never" proof that asks the model to misbehave instead of injecting an ordinary step the grader sees. The four Block A first attempts that stayed GREEN are the run evidence that requests fail and neutral steps work |
| F5-AC3 | test | `tests/test_eval_conductor_cases.py::test_every_control_is_listed_and_never_a_proof_target`<br>`tests/test_eval_conductor_cases.py::test_graders_split_into_controls_and_mapped_gates`<br>`tests/test_eval_conductor_cases.py::test_conductor_dispatched_control`<br>`tests/test_eval_conductor_cases.py::test_audit_ran_control`<br>`tests/test_eval_conductor_cases.py::test_failing_script_ran_controls`<br>`tests/test_eval_conductor_cases.py::test_pass1_leak_guards_inherit_the_recorded_leak_guard_proof` | A grader that is neither a control, nor an inherited byte copy, nor the expected red of a proof; a control named as a proof target |
| F5-AC4 | test + runs | `tests/test_043_close_out_gaps.py::test_every_spec_043_proof_is_recorded_red_in_3_of_3_with_its_results_path` (new, §4)<br>`tests/test_eval_conductor_cases.py::test_recorded_rows_carry_measured_side_effects`<br>`tests/test_eval_conductor_cases.py::test_spec_043_rows_name_their_offline_model` | A proof row in `_mutations/README.md` with no verdict line in `red-proofs.md`, a verdict line that lost a run or its results path |
| F6-AC1 | test | `tests/test_eval_gate_docs.py::test_pass1_files_are_rows_with_both_pass1_cases`<br>`tests/test_eval_gate_docs.py::test_inbox_and_settings_rows_list_all_seven_cases`<br>`tests/test_eval_gate_docs.py::test_every_covered_path_exists`<br>`tests/test_eval_gate_docs.py::test_prd_named_files_are_in_the_table`<br>`tests/test_eval_gate_docs.py::test_every_table_row_names_an_existing_case`<br>`tests/test_eval_gate_docs.py::test_every_case_directory_appears_in_the_table`<br>`tests/test_eval_gate_docs.py::test_every_case_named_in_the_table_exists` | A Pass 1 file missing from the coverage table, or listed without both Pass 1 cases; a case or path missing |
| F6-AC2 | test | `tests/test_eval_gate_docs.py::test_claude_md_rule_names_the_pass1_files`<br>`tests/test_eval_gate_docs.py::test_claude_md_rule_tracks_the_coverage_table` | The root `CLAUDE.md` rule not naming `suggestion-conductor.md` or `suggest-handling/SKILL.md` |
| F6-AC3 | run | G: three consecutive `GREEN 7/7 cases · runs 21` on `99a6f50c`, `tree clean`. Median cost $2.75, maximum duration 310 s, recorded in [`red-proofs.md`](red-proofs.md) T4.3. `git diff 99a6f50c..HEAD --stat` at close-out time: `plan/phase-4.md`, `red-proofs.md`, `evals/README.md` and `evals/_mutations/README.md` (cost and record text), `scripts/run-evals.sh` (help text and its version only) and its help-text assertion in `tests/test_run_evals.py`. No covered file, case, grader, stub or mutation changed after the candidate | — (a recorded run, not a test) |
| F6-AC4 | run + test | G: $2.75, $2.76, $2.74, each under the $5 cap, none NOT GRADED<br>`tests/test_run_evals.py::test_max_cost_flag_and_env_reach_cli_and_default_returns` (the default cap reaches the CLI) | A default cap other than $5 |
| F7-AC1 | test | `tests/test_043_close_out_gaps.py::test_known_limits_name_the_three_spike_limits` (new, §4)<br>`tests/test_eval_gate_docs.py::test_every_repo_path_in_the_readme_exists` | Any of the three named limits deleted from `evals/README.md` Known limits, or the trace-format limit losing the `claude` version |

## 3. Gate graders: proof, RED, GREEN

Every gate grader of the two Pass 1 cases and both report-only variants was red in **3/3** under its proof, and green in all 9 of its runs in G. Full verdict lines: [`red-proofs.md`](red-proofs.md). Patches and the clauses each removes: [`evals/_mutations/README.md`](../../../../evals/_mutations/README.md). All proofs ran with `--keep-temp`, 3 runs, `claude 2.1.316`, `tree clean`.

| Case | Grader | PRD | Proof | RED | Proof results (`tomo-tmp/evals/…`) |
|---|---|---|---|---|---|
| `pass1-suggest-pipeline` | `01-conductor-not-dispatched` | F1-AC1 | `dispatch-conductor` | 3/3 | `2026-10-31T12-37-49Z` |
| `pass1-suggest-pipeline` | `02-analyst-dispatched-3x` | F1-AC2 | `analyst-name-not-type` (Block D) | 3/3 | `2026-10-31T13-39-49Z` |
| `pass1-suggest-pipeline` | `03-no-general-purpose` | F1-AC2 | `analyst-name-not-type` (Block D) | 3/3 | `2026-10-31T13-39-49Z` |
| `pass1-suggest-pipeline` | `04-subfolder-path-and-key` | F1-AC3 | `path-from-stem` (Block D) | 3/3 | `2026-10-31T13-42-11Z` |
| `pass1-suggest-pipeline` | `05-shared-ctx-once` | F1-AC4 | `setup-in-conductor` (Block D) | 3/3 | `2026-10-31T13-45-49Z` |
| `pass1-suggest-pipeline` | `06-run-id-once` | F1-AC4 | `setup-in-conductor` (Block D) | 3/3 | `2026-10-31T13-45-49Z` |
| `pass1-suggest-pipeline` | `07-setup-before-dispatch` | F1-AC4 | `dispatch-before-setup` | 3/3 | `2026-10-31T12-44-07Z` |
| `pass1-suggest-pipeline` | `08-reducer-before-render` | F1-AC5 | `render-before-reduce` (Block D) | 3/3 | `2026-10-31T13-44-07Z` |
| `pass1-suggest-pipeline` | `09-reduce-after-last-dispatch` | F1-AC5 | `reduce-before-batch-2` | 3/3 | `2026-10-31T12-46-54Z` |
| `pass1-suggest-pipeline` | `10-two-script-writes-same-stem` | F1-AC6 | `publish-md-with-write-tool` | 3/3 | `2026-10-31T12-48-22Z` |
| `pass1-suggest-pipeline` | `11-no-inline-vault-write` | F1-AC6 | `publish-md-with-write-tool` | 3/3 | `2026-10-31T12-48-22Z` |
| `pass1-suggest-pipeline` | `12a-mark-captured-once` | F1-AC7 | `mark-before-write` | 3/3 | `2026-10-31T12-50-06Z` |
| `pass1-suggest-pipeline` | `12b-mark-captured-after-json-write` | F1-AC7 | `mark-before-write` | 3/3 | `2026-10-31T12-50-06Z` |
| `pass1-suggest-pipeline` | `13-no-inline-python` | F1-AC8 | `inline-python-read` | 3/3 | `2026-10-31T12-51-53Z` |
| `pass1-suggest-pipeline` | `14-report-line-anchored` | F1-AC9 | `reword-report-line` | 3/3 | `2026-10-31T12-54-30Z` |
| `pass1-suggest-pipeline` | `15-no-duplicate-line` | F1-AC10 | `always-duplicate-line` | 3/3 | `2026-10-31T12-53-12Z` |
| `pass1-warn-and-duplicates-relayed` | `01-warn-in-reply` | F2-AC1 | `warn-is-diagnostic` | 3/3 | `2026-10-31T12-56-50Z` |
| `pass1-warn-and-duplicates-relayed` | `02-warn-before-first-dispatch` | F2-AC2 | `warn-in-report-only` | 3/3 | `2026-10-31T12-58-37Z` |
| `pass1-warn-and-duplicates-relayed` | `03-duplicate-line` | F2-AC3 | `drop-duplicate-line` | 3/3 | `2026-10-31T12-59-58Z` |
| `pass1-warn-and-duplicates-relayed` | `04-report-line-anchored` | F2-AC4 | `reword-report-line` | 3/3 | `2026-10-31T12-54-30Z` |
| `audit-gates-delivery`, `withheld-notices-relayed`, `upload-failure-reported`, `state-flip-failure-reported` | `7-report-only` | F4-AC1/2 | `status-sentence-first` (haiku Block B; sonnet Block S, literal line) | 3/3 each | haiku `2026-10-31T13-47-43Z`, `…T13-49-02Z`, `…T13-50-11Z`; sonnet `2026-10-31T16-45-20Z`, `…T16-46-15Z`, `…T16-47-19Z` |
| `audit-mismatch-stops` | `7-report-only-mismatch` | F4-AC4 | `status-sentence-first` | 3/3 | haiku `2026-10-31T13-47-43Z`; sonnet `2026-10-31T16-45-20Z` |

**Inherited, controls.** The two Pass 1 `9-no-leak` graders are byte copies of `evals/_lib/no-leak.md` and inherit `report-run-id`, which turned that file red 3/3 in all five Pass 2 cases on haiku (Block C) and on sonnet (Block S). The 13 controls (five `0-conductor-dispatched`, five `8-handback-canary`, `3-audit-ran`, `3-upload-ran`, `2-state-flip-ran`) are exempt by F5-AC3 and are named by no proof.

**Re-proven spec 041 patches.** `summarise-mismatch`, `files-used-after`, `paraphrase-relay`, `explain-failure` and `report-run-id` were rebased onto conductor 0.24.2 and re-proven there (Block C) and on 0.25.0 sonnet (Block S): every expected grader red 3/3 in every case.

**Not counted.** The four Block A first attempts (`analyst-name-not-type`, `path-from-stem`, `render-before-reduce` GREEN; `setup-in-conductor` red 3/3 + 1/3) are kept in `red-proofs.md` as history. Their strengthened patches (fcb8c7e4) are the proofs above. The 1/3 side-effect red of relay `02` under `reword-report-line` was a grader defect (F6), fixed in c2602d6b and void.

## 4. Gaps the trace found

### Closed

Three criteria had a part that no test could fail. Each is now closed by a test in `tests/test_043_close_out_gaps.py`. Each test was proven RED by applying the mutation below in an isolated export (`git archive HEAD | tar -x -C $TMPDIR/co043-copy`, the new test file copied in, `PYTHONDONTWRITEBYTECODE=1`), never in the worktree. The unmutated export was green first (`3 passed`). Each mutation was applied to a fresh export.

| Criterion | Part no test could fail | Test | Mutation → failure |
|---|---|---|---|
| F5-AC4 | "each one names its mutation, its grader, the 3 verdicts and the results path". The `_mutations/README.md` tests check the table against the patch files and the grader names, but nothing read `red-proofs.md` | `test_every_spec_043_proof_is_recorded_red_in_3_of_3_with_its_results_path`: for each of the 21 proofs recorded by this spec (16 spec 043 rows, 5 re-proven spec 041 rows), every expected `case: grader` is red in runs 0, 1 and 2 of one `RED … · mutation <name> · tomo-tmp/evals/<TS>` line | M1: the `inline-python-read` verdict line deleted → `AssertionError: ['inline-python-read: no RED verdict line with its results path']`. M2: `, pass1-suggest-pipeline: 15-no-duplicate-line (run 2)` cut from its verdict → `['always-duplicate-line: pass1-suggest-pipeline/15-no-duplicate-line is not red in runs 0, 1 and 2 of one verdict']` |
| F7-AC1 | the whole criterion. `test_every_repo_path_in_the_readme_exists` checks paths, nothing checked the three limits | `test_known_limits_name_the_three_spike_limits` | M3: the "The analysts run in the background" bullet deleted → `AssertionError: background dispatch limit`. M4: "validated on `claude` 2.1.314 (spike) and 2.1.316 (every gate run since)" replaced by "validated on the spike and every gate run since" → red on the version regex |
| F3-AC1 (and F3-AC4, "no Kado") | "the stand-in costs no Kado access". The runner tests pin the stand-in's bytes to its source file, not what the file grants; nothing checked that the stubs stay off the network | `test_the_analyst_stand_in_and_the_stub_kit_cannot_reach_kado` | M5: `tools: Bash` → `tools: Bash, mcp__kado__kado-read` in `inbox-analyst.stub.md` → `assert 'Bash, mcp__kado__kado-read' == 'Bash'`. M6: `_stub_head='import json, os, sys` → `…, urllib.request` in `pass1-stubs.sh` → `AssertionError: pass1-stubs.sh contains 'urllib'` |

The script that applied M1–M6 is not in the repo; each mutation is a one-line edit named above.

### Open

| # | Criterion | Part with no evidence that could fail | Why it stays open |
|---|---|---|---|
| O1 | F1-AC9, F2-AC4 | "the reply **begins** with the Pass 1 completion line". Graders 14 and 04 match `(?:^|\n)Pass 1 complete: …`, i.e. the line at the start of any line of `last_message`. A preface on its own line before the completion line stays green. PRD Rule 7 asks for line anchoring, which is what the graders do; the criterion's word "begins" is stricter | Closing it changes two gate graders, which needs new RED proofs and a full suite (paid). Note: findings O2 shows the model adds text *after* the line, which is ungraded on purpose; no run has shown text before it |
| O2 | F1-AC6 | "nothing is written to the vault by passing content through the model" in its production form: the rendered markdown passed to `mcp__kado__kado-write` (811a0230). The eval has no Kado MCP server (owner decision: no Kado mocks), so that call cannot happen and no grader can see it. Grader 11 sees only a `Write` call into `100 Inbox/`, and the eval session disables `Write` even though both cases list it ("Write is disabled for this session"), so only an attempted call is observable | Accepted limitation (PRD Won't Have). The runtime prose forbids the MCP path; only a live run could show it |
| O3 | F1-AC2 | "exactly 3 dispatches". Grader 02 counts `Agent` calls typed `tomo:inbox-analyst`; 03 forbids `general-purpose` and an untyped call; 01 forbids `suggestion-conductor`. A dispatch typed any other agent is counted by none of them. A failed bare-name call (findings O1) is not counted either, by design | Low risk; no run showed it. A total-`Agent`-count grader would be red on the O1 retry, so it was not added |
| O4 | F3-AC4 | "nothing outside its own temporary workspace is **read**", and the model's own tool calls during a paid run. The tests prove the stub pipeline writes nothing into the repo or `~/.tomo`, the runner leaves every instance unchanged, and no MCP tool is allowed. The runner's tree guard (`tree clean`) covers tracked and untracked non-ignored repo files only; `tomo-instance/`, `tomo-privat/` and `~/.tomo` are not compared after a paid run, and reads are not observed at all | Observing reads needs a filesystem trace the harness does not offer. A before/after comparison of the instances around a paid run would cover writes; it is a runner change, which the PRD puts out of scope |
| O5 | F3-AC2 | "large enough to pass the conductor's own sanity check". The runtime prose names no size threshold, so the 1024-byte floor in `test_render_output` is the stand-in's own. The evidence that it is enough is that every Pass 1 run in G reached the report | Nothing to test against until the prose states a threshold |

## 5. Merge evidence

### First attempt — RED

Candidate `e91276104f215adbbcce6f1ba0af2deb61bd15c6`, `synthesis-conductor` 0.24.2 on haiku. Verbatim from [`red-proofs.md`](red-proofs.md):

```
GREEN 7/7 cases · runs 21 · $2.33 · 416 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T15-01-31Z
```

```
RED 5/7 cases · state-flip-failure-reported: 7-report-only (run 1), upload-failure-reported: 7-report-only (run 2) · runs 21 · $2.27 · 373 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T15-08-29Z
```

```
GREEN 7/7 cases · runs 21 · $2.20 · 378 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T15-14-44Z
```

Cause: in suite 2 the haiku conductor prefaced the stop report with a sentence of its own ("Pass 2 did not finish cleanly: …", "Pass 2 synthesis did not complete. The Step 4 report is below."). That is the F5 deviation that rule 5 of 0.24.2 forbids, the same 1-in-6 shape #205 reported. With T3.3's suite RED on `audit-mismatch-stops` the same way, about every second haiku suite was RED. The new `7-report-only` grader caught it, which is the reason it exists. Owner decision: the conductor runs on sonnet (0.25.0), chosen over a further prose tightening; the WHY is in `docs/tomo/dot_claude/agents/synthesis-conductor.md`.

### Second attempt — GREEN (the merge evidence G)

Candidate `99a6f50cf8cc574e04f402d79f3b7bd8830740f2`, `synthesis-conductor` 0.25.0 on sonnet. Verbatim from [`red-proofs.md`](red-proofs.md):

```
GREEN 7/7 cases · runs 21 · $2.75 · 271 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T16-47-57Z
```

```
GREEN 7/7 cases · runs 21 · $2.76 · 310 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T16-52-30Z
```

```
GREEN 7/7 cases · runs 21 · $2.74 · 286 s · claude 2.1.316 · tree clean · tomo-tmp/evals/2026-10-31T16-57-42Z
```

Median cost $2.75, maximum $2.76, maximum duration 310 s. 0 of 45 Pass 2 runs (5 cases × 3 runs × 3 suites) showed the report-only deviation on sonnet. Every conductor proof was repeated on sonnet before G (Block S, $6.25).

## 6. KPIs and spend

| KPI | Target | Measured | Verdict |
|---|---|---|---|
| New non-control graders proven red | 100%, 3/3 each | 22 of 22 (20 Pass 1 gate graders + `7-report-only` + `7-report-only-mismatch`), each red 3/3 | 🟢 |
| Merge candidate GREEN | 3/3 full suites | 3/3 on `99a6f50c` (G) | 🟢 |
| No grader a false positive on recorded traces | none | one found and fixed: relay `02` on batched Bash calls (F6, c2602d6b). The fixed pattern was re-evaluated on all 61 kept traces that run the `cat`; it differs from the old one only on the batched trace | 🟢 after the fix |
| Full-suite cost | median ≤ $3.10, each < $5 | median $2.75 (max $2.76) | 🟢 |
| Pass 1 cost per suite | ≤ about $1.60 median | $1.23, $1.27, $1.27 in G (sum of the two Pass 1 cases' run costs in each `aggregate-result.json`) | 🟢 |
| Full-suite duration | ≤ 4 min (PRD v1.0), raised to 6, then 7 min | see below | 🟢 against 7 min; 🔴 against the original 4 min |
| Adoption, engagement | every later PR on a gated Pass 1 file carries a GREEN; every live finding becomes a grader | the first instance is this spec's own PR | open, measured from here on |

**Duration.** The PRD's KPI was 4 minutes. It was raised twice by owner decision on 2026-10-31 (README Decisions Log):

- **4 → 6 min** after T3.3: the three Phase 3 full suites on the haiku conductor took **298–344 s** (298, 309, 344). The Pass 1 runs take 36–46 s each.
- **6 → 7 min** after the first merge evidence on the haiku conductor took **373–416 s**. No single case was slower than before; the total varies with API latency at `-j 2`.
- On the sonnet conductor the merge evidence took **271–310 s**, inside the original 6 minutes but not inside 4.

**Cost per part of the suite** (from the three `aggregate-result.json` files of G, and of the T3.3 and first-attempt suites for comparison): the two Pass 1 cases cost $1.23–1.27 per suite in G and $1.23–1.30 on haiku, so they add about **$1.3 per suite**. The five Pass 2 cases cost $1.48–1.51 per suite on the sonnet conductor against $0.97–1.03 on haiku: the model change, not the Pass 1 cases, is why a suite costs $2.75 rather than the $2.25 measured in Phase 3. One Pass 1 run on sonnet's merge evidence took 38–65 s.

| Phase | Spend |
|---|---|
| Spike (before the PRD, `spike/write-up.md`) | $0.30 ($0.296) |
| Phases 1 and 2 (pytest and offline checks only) | $0 |
| Phase 3: smokes 1–4 $1.26, full suites $6.76, F5 re-run $0.19 ([`findings.md`](findings.md)) | $8.21 |
| Phase 4: T4.1 Blocks A–D $16.12, Block S $6.25, T4.3 first attempt (RED) $6.80, T4.3 second attempt (GREEN) $8.25 ([`red-proofs.md`](red-proofs.md)) | $37.42 |
| **Spec total** | **$45.93** |

Phase 4's T4.1 estimate was about $12 and the Phase 4 estimate about $18–19 (README Decisions Log). The difference is the four Block A proofs that had to be strengthened and re-run ($2.50 + $2.99), the move to sonnet (Block S, $6.25) and a second full merge evidence ($8.25).

## 7. Validation

- **The single invocation (§1):** `543 passed in 28.27s`.
- **ruff:** `ruff check tests/test_043_close_out_gaps.py` → `All checks passed!` (ruff 0.15.12).
- **Full pytest:** `6586 passed, 3 skipped, 1 deselected, 1 warning in 231.54s (0:03:51)` (2026-10-31, the same tree as §1). The deselected test is the known unrelated failure `tests/ide_bridge/test_configure_ide_bridge.py::test_install_smoke_ide_bridge_block_exists`, not a 043 test.

## 8. Open items

- **`force-atomic-handling` has no eval case.** It is not gated (PRD Won't Have) and the coverage table says so. The `cat` WARN relay was ported to it (f8a07f6c, 0.15.0, owner decision 2026-10-31), and that port is covered by prose tests only: `test_force_atomic_relays_warn_with_a_cat_before_the_first_dispatch_and_in_the_report` (`tests/test_043_grader_patterns.py`) and `test_both_relay_builder_warnings[force]` (`tests/test_040_skill_prose.py`). Whether a model running it shows the warning before dispatch is unmeasured. The Could Have third case (fan-resolve on a subfolder note, about +$0.75 per suite) would cover it.
- **Stub drift.** The Pass 1 stand-ins print formats copied from the real scripts, and `test_copied_formats_still_in_real_scripts` and `test_inline_to_filename_is_a_copy_of_the_real_one` pin those fragments to the scripts' source. That is a static check of named strings. There is still no runtime contract check tying a stub to its script (as for spec 041, by owner decision), so a behaviour change in a real script that keeps its printed strings leaves both cases green against a pipeline production no longer runs. `shared-ctx-builder.py --warnings-out` is the one real-script behaviour the Pass 1 cases rely on that has its own tests (`tests/test_043_warnings_out.py`).
- **`explain-failure` keeps "NEVER announce, explain or summarise the stop".** True: the patch removes "no explanation of why a step failed" and the failure-detail clauses of rules 2 and 5 and the `Why:` line, but keeps "NEVER write anything before or after it. NEVER announce, explain or summarise the stop" in rule 5. What it means for the proof: the README rule says every patch removes each clause that contradicts what it injects. Whether this clause contradicts the injected `Detail:` line depends on whether a failed upload or state flip is "the stop" (the conductor continues with the next entry, so it is arguably not). Either way the surviving clause could only have made the model *resist* the injection and leave graders green; it did not: the proof was red 3/3 in both cases on haiku (Block C) and on sonnet (Block S). So the proof stands, and is if anything conservative. The risk is a future model obeying the surviving clause and turning the proof GREEN, which would show up as a failed proof, never as a false GREEN gate. `test_mutation_removes_and_adds_its_declared_clauses` cannot catch this, because it checks only the clauses a patch declares.
- **Eight spec 041 proofs were not re-run on the sonnet conductor.** `--rev 4350ddd^`, `drop-audit-line`, `always-notice`, `write-into-scripts`, `copy-into-config`, `attachments-first`, `failed-step-path` and `flip-after-failed-upload` were measured on the haiku conductor (0.24.0/0.24.1) and only rebased onto 0.24.2 (they still apply: `test_mutation_applies_cleanly_to_a_fresh_assembly`). The graders they alone prove (e.g. `audit-gates-delivery/1-audit-before-upload`, `3-audit-result-in-report`, `4-no-notice-when-none-withheld`, the F4-AC4 no-write/no-copy graders, `upload-failure-reported/2-no-state-flip-after-failed-upload`, the failed-step lines) were green on sonnet in G, but have no RED measured on sonnet. The owner decision named only `status-sentence-first` and the five rebased patches for re-proof.
- **F2-AC2 was redefined, not met as written in v1.0.** 4 of 4 paid runs answered the warning in thinking, never in a text block, across four wordings (findings F4). The redefined criterion (the `cat` tool result before the first dispatch) is what the gate checks. A model that runs the `cat` and then says nothing about it is green.
- **The Write tool is disabled in the eval session** although both Pass 1 cases list it. Grader 11 is proven red on the attempted call; a run in which `Write` succeeds has never been observed (see O2).
- **Spec bookkeeping.** The README status still says Current Phase PLAN, `plan/phase-4.md` has T4.4 and T4.5 unticked, and the PRD acceptance checkboxes in `requirements.md` are unticked. These belong to T4.5 (finalise through `xdd-meta`), not to this document.

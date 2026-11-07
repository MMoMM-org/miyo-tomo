---
title: "Close-out — 044 /note creates a filled note from a template"
status: complete
---

# Close-out

## Standing rule for this document

Every acceptance criterion below traces to evidence that was **executed**, not to a task that mentions it:

- Criteria about scripts, libs, schemas, the instance tooling, the `tomo-note-view` mod and the documents trace to pytest node ids, all run in the one invocation of §1.
- Criteria about what the model does in the dialogue trace to a **prose pin** (a `tests/test_note_skill_prose.py` or `tests/test_044_close_out_gaps.py` assertion that the imperative exists in `note-from-template/SKILL.md`) **plus** a live-walk row with its session id, or the recorded eval. A prose pin is red when the imperative is deleted or reworded; it is never evidence that the model obeys it. Where a dialogue criterion has a prose pin and no live or eval evidence, the trace says so.
- Live-walk rows are cited by their number in [`live-walk.md`](live-walk.md) and the session id recorded there. Rows marked "not walked live (owner decision 2026-11-06)" count as no live evidence.

For each criterion the trace names the **mechanism** the evidence falsifies: the concrete change that would turn it red.

`requirements.md` and `solution.md` were not edited. Two test names cited in `live-walk.md` (rows 1.6 and 4.6) no longer existed; they were corrected to the current names (§4).

## Criteria count

The plan says **53** (52 plus F4-AC5). The right number is **54**:

- `requirements.md` v1.0 was approved with 9 features and **52** criteria (README Documents table): F1:6 F2:4 F3:8 F4:4 F5:8 F6:6 F7:12 F8:2 F9:2.
- Two were added later: **F6-AC7** (unfinished drafts offered Continue / Discard, README Decisions Log 2026-11-06, live walk c573b7b7) and **F4-AC5** (the draft view pane, 2026-11-06, "Mod inside 044"). The plan text counted only F4-AC5.
- `solution.md` §Acceptance Criteria carries the same 54 ids 1:1 (F1:6 F2:4 F3:8 F4:5 F5:8 F6:7 F7:12 F8:2 F9:2), checked by `grep -o 'F[0-9]*-AC[0-9]*' | sort -u`.

**54/54 trace to executed evidence that can fail.** By class:

- 34 trace to script, lib, mod or document tests, some with a prose pin or live evidence beside them (F1-AC3–6, F2-AC4, F3-AC1, F3-AC7, F4-AC3, F4-AC5, F5-AC1–8, F6-AC1–7, F7-AC1, F7-AC4, F7-AC5, F7-AC8–12, F9-AC1, F9-AC2).
- 2 trace to byte pins of the unchanged runtime text (F8-AC1, F8-AC2).
- 18 are model behaviour and trace to a prose pin (F1-AC1, F1-AC2, F2-AC1–3, F3-AC2–6, F3-AC8, F4-AC1, F4-AC2, F4-AC4, F7-AC2, F7-AC3, F7-AC6, F7-AC7). Of these, 10 also have a live-walk pass or partial (F1-AC1, F1-AC2, F2-AC2, F2-AC3, F3-AC2, F3-AC8, F4-AC1, F4-AC2, F4-AC4, F7-AC7), 3 have the 0.2.4-era eval (F3-AC3 alone; F4-AC1 and F4-AC4 beside live), and **7 rest on the prose pin alone for their model part** (F2-AC1, F3-AC4, F3-AC5, F3-AC6, F7-AC2, F7-AC3, F7-AC6; §7). F7-AC2 and F7-AC3 have script tests for what `read` returns, not for what the model does with it.

Seven criterion parts had no test that pinned them; all seven are now closed by RED-proven tests (§3). A full-suite run with all seven mutations applied at once shows that no pre-existing test pinned them by meaning; four of them were caught only incidentally, as eval-patch context (§3).

## 1. The single invocation

The **194 node ids** in the trace table ran **together in one `pytest` invocation** on 2026-11-07, branch `docs/169-note-from-template` at `5be03e1a` with `tests/test_044_close_out_gaps.py` added (uncommitted at the time of the run) and the two `live-walk.md` name fixes:

```
281 passed in 103.10s (0:01:43)
```

194 node ids collect **281 items**; the difference is parametrisation. Nothing was skipped: `test_claude_plugin_validate_passes` and `test_claude_plugin_test_passes` ran the `claude` binary (`~/.local/bin/claude plugin test`, 15 mod tests). Collection was checked by script, not by eye: the sorted list of cited node ids and the sorted list of collected node ids (parameters stripped) are identical.

<details><summary>The command, exactly as run</summary>

```bash
PYTHONDONTWRITEBYTECODE=1 ./venv/bin/python -m pytest -q -p no:cacheprovider -rs \
  tests/test_note_session.py::test_note_include_absent_skips_listing \
  tests/test_note_session.py::test_unusable_note_include_counts_as_absent \
  tests/test_note_session.py::test_match_pattern_preview_table \
  tests/test_note_session.py::test_docstring_names_every_start_field \
  tests/test_note_skill_prose.py::test_setup_asks_with_the_match_result_as_the_preview \
  tests/test_note_skill_prose.py::test_each_preview_site_names_its_preview_content_after_its_option_line \
  tests/test_044_close_out_gaps.py::test_an_unconfigured_selection_routes_to_the_setup \
  tests/test_note_skill_prose.py::test_setup_reruns_match_and_reprints_on_a_correction_and_writes_only_on_confirm \
  tests/test-vault-config-writer.py::test_templates_include_inserts_into_block_without_key \
  tests/test-vault-config-writer.py::test_templates_include_replaces_existing_key_with_continuation_lines \
  tests/test-vault-config-writer.py::test_templates_include_appends_block_when_missing \
  tests/test-vault-config-writer.py::test_templates_include_rejects_invalid_input_and_writes_nothing \
  tests/test-vault-config-writer.py::test_templates_include_crlf_inserts_inside_block_and_keeps_crlf \
  tests/test-vault-config-writer.py::test_templates_include_keeps_deeper_comment_after_list \
  tests/test-vault-config-writer.py::test_templates_include_stdout_writes_nothing \
  tests/test_note_skill_prose.py::test_each_skill_call_parses_with_the_scripts_argparse \
  tests/test_044_close_out_gaps.py::test_a_confirmed_setup_continues_the_request \
  tests/test_note_skill_prose.py::test_setup_abort_writes_nothing_and_a_confirmed_selection_stays \
  tests/test_note_session.py::test_match_listing_error_reported_exit_0 \
  tests/test_read_config_field.py::test_note_include_absent_is_omitted_and_exits_0 \
  tests/test_read_config_field.py::test_note_include_present_is_returned_as_list \
  tests/test-vault-config-writer.py::test_replace_existing_section \
  tests/test-vault-config-writer.py::test_replace_preserves_neighbours_bytewise \
  tests/test-vault-config-writer.py::test_end_to_end_file_roundtrip \
  tests/test-vault-config-writer.py::test_all_sections_stack_in_one_config \
  tests/test_note_session.py::test_candidates_match_include_and_drop_daily \
  tests/test_note_session.py::test_match_daily_not_listed_gives_empty_excluded \
  tests/test_note_skill_prose.py::test_one_candidate_is_named_several_are_printed_and_asked \
  tests/test_note_skill_prose.py::test_several_fits_are_asked_by_number_and_get_a_dialog_only_up_to_three_candidates \
  tests/test_note_skill_prose.py::test_the_candidate_dialog_is_limited_to_three_candidates_plus_abort \
  tests/test_note_skill_prose.py::test_the_candidate_choice_aborts_with_zero_so_every_listed_number_stays_valid \
  tests/test_note_skill_prose.py::test_no_fitting_candidate_offers_the_three_ways_out \
  tests/test_note_skill_prose.py::test_inbox_author_hand_off_names_the_default_type_so_it_cannot_bounce_back \
  tests/test_note_skill_prose.py::test_empty_listing_says_empty_or_not_readable_with_the_remedy \
  tests/test_note_skill_prose.py::test_unreadable_template_gives_the_same_remedy \
  tests/test_note_session.py::test_start_listing_error_reported_exit_0 \
  tests/test_note_session.py::test_start_transport_error_is_listing_error \
  tests/test_template_outline.py::test_template_denied_exits_1_and_names_the_kado_error \
  tests/test_template_outline.py::test_template_not_found_exits_1_without_template_text \
  tests/test_044_user_docs.py::test_troubleshooting_remedy_for_template_folder_access \
  tests/test_template_outline.py::test_outline_lists_every_heading_key_and_open_token \
  tests/test_template_outline.py::test_outline_marks_prefilled_tokens_per_table \
  tests/test_template_syntax.py::test_headings_listed_with_level_text_line_and_body \
  tests/test_template_syntax.py::test_frontmatter_keys_list_top_level_keys_with_value_and_line \
  tests/test_template_syntax.py::test_tokens_listed_with_line_outside_fences_templater_and_escapes \
  tests/test_template_syntax.py::test_every_other_token_known_or_not_is_a_point \
  tests/test_template_syntax.py::test_prefilled_tokens_set_matches_the_sdd_table \
  tests/test_note_process_lib.py::test_points_are_headings_frontmatter_keys_and_open_tokens \
  tests/test_note_skill_prose.py::test_question_budget_is_four_per_round_and_two_rounds \
  tests/test_note_skill_prose.py::test_free_text_and_long_list_sites_stay_plain_text_only \
  tests/test_note_skill_prose.py::test_covered_points_are_printed_and_no_open_point_means_no_question \
  tests/test_note_eval_case.py::test_one_candidate_and_the_material_fills_every_point \
  tests/test_note_eval_case.py::test_a_plain_text_question_before_the_draft_counts_as_a_question_round \
  tests/test_note_eval_case.py::test_the_recorded_probe_is_all_green \
  tests/test_044_close_out_gaps.py::test_a_skipped_optional_point_keeps_its_heading_empty_and_is_named \
  tests/test_note_skill_prose.py::test_the_header_names_every_field \
  tests/test_note_skill_prose.py::test_required_points_are_re_asked_with_no_skip_option \
  tests/test_template_syntax.py::test_filled_note_check_fails_on_a_remaining_templater_opener \
  tests/test_template_syntax.py::test_tokens_inside_a_templater_span_are_not_points \
  tests/test_template_syntax.py::test_templater_include_on_line_one_is_a_span_not_a_point \
  tests/test_note_instructions.py::test_deliver_refuses_a_failing_filled_note_check \
  tests/test_note_instructions.py::test_stage_reports_failing_check \
  tests/test_note_skill_prose.py::test_templater_is_never_executed_and_language_follows_the_call \
  tests/test_note_skill_prose.py::test_the_skill_prints_note_md_after_every_stage_never_draft_md \
  tests/test_note_instructions.py::test_stage_records_title_destination_keep_source \
  tests/test_note_eval_case.py::test_each_model_turns_exactly_its_graders_red \
  tests/test_note_eval_case.py::test_header_grader_accepts_the_inbox_file_as_a_path \
  tests/test_note_skill_prose.py::test_approval_options_and_changes_go_through_stage \
  tests/test_note_instructions.py::test_stage_never_rewrites_draft_md \
  tests/test_note_instructions.py::test_stage_re_resolves_after_keep_source_flips \
  tests/test_note_actions.py::test_move_note_values_come_from_the_draft_state \
  tests/test_note_instructions.py::test_deliver_kept_source_has_no_delete_and_is_still_marked \
  tests/test_note_instructions.py::test_view_follows_a_keep_source_flip \
  tests/test_044_close_out_gaps.py::test_approval_runs_deliver \
  tests/test_note_skill_prose.py::test_drop_on_every_abort_path \
  tests/test_note_skill_prose.py::test_deliver_runs_with_the_stem \
  tests/test_note_skill_prose.py::test_stage_runs_with_a_title_before_deliver \
  tests/test_note_eval_case.py::test_a_deliver_after_the_question_still_counts \
  tests/test_note_instructions.py::test_stage_writes_view_with_header_and_fenced_note \
  tests/test_note_instructions.py::test_view_omits_the_source_line_when_the_source_is_kept \
  tests/test_note_instructions.py::test_view_omits_the_source_line_without_a_source \
  tests/test_note_instructions.py::test_view_fence_outgrows_backticks_in_the_note \
  tests/test_note_instructions.py::test_drop_removes_the_view \
  tests/test_note_instructions.py::test_new_removes_a_stale_view \
  tests/test_note_instructions.py::test_stage_of_another_stem_replaces_the_view \
  tests/test_note_instructions.py::test_refused_stage_leaves_no_view_of_another_stem \
  tests/test_note_instructions.py::test_failing_check_leaves_no_view \
  tests/test_note_instructions.py::test_untitled_stage_leaves_no_view \
  tests/test_note_instructions.py::test_view_never_reaches_stdout_or_stderr \
  tests/test_note_instructions.py::test_deliver_removes_the_view \
  tests/test_note_instructions.py::test_failed_deliver_removes_the_view_and_a_restage_writes_it \
  tests/test_tomo_note_view_mod.py::test_hooks_read_the_view_file_the_script_writes \
  tests/test_tomo_note_view_mod.py::test_manifest_names_the_mod_and_its_contract \
  tests/test_tomo_note_view_mod.py::test_versions_agree \
  tests/test_tomo_note_view_mod.py::test_mod_has_a_plugin_test \
  tests/test_tomo_note_view_mod.py::test_update_delivers_the_mod \
  tests/test_tomo_note_view_mod.py::test_install_delivers_the_mod \
  tests/test_tomo_note_view_mod.py::test_claude_plugin_validate_passes \
  tests/test_tomo_note_view_mod.py::test_claude_plugin_test_passes \
  tests/test_note_instructions.py::test_deliver_writes_note_json_md_then_marks_source_in_order \
  tests/test_note_instructions.py::test_deliver_stamps_note_peer_and_source \
  tests/test_note_actions.py::test_delete_source_depends_on_i01_when_source_is_not_kept \
  tests/test_note_actions.py::test_no_delete_source_when_source_is_kept \
  tests/test_note_actions.py::test_delete_without_depends_on_would_be_rejected \
  tests/test_note_actions.py::test_set_validates_against_hashi_schema \
  tests/test_note_actions.py::test_set_with_null_profile_validates \
  tests/test_note_actions.py::test_move_note_has_exactly_the_sdd_keys_all_allowed_by_the_schema \
  tests/test_note_triage_interplay.py::test_marked_source_beside_its_peer_raises_no_orphan_warning \
  tests/test_note_instructions.py::test_deliver_failure_at_a_step_stops_every_later_step \
  tests/test_note_instructions.py::test_deliver_mark_is_guarded_by_the_modified_time_it_read \
  tests/test_note_triage_interplay.py::test_delivered_files_and_marked_source_are_no_new_item \
  tests/test_note_instructions.py::test_deliver_destination_clash_exits_3_before_any_write \
  tests/test_note_instructions.py::test_both_no_overwrite_probes_share_exit_3_and_the_exists_line \
  tests/test_note_instructions.py::test_deliver_resume_different_note_exits_3_and_changes_nothing \
  tests/test_note_instructions.py::test_deliver_resume_taken_instruction_set_name_exits_3 \
  tests/test_stub_contract.py::test_note_deliver_matches \
  tests/test_note_skill_prose.py::test_name_taken_offers_rename_or_abort_and_never_overwrites \
  tests/test_note_skill_prose.py::test_name_taken_branches_on_the_scripts_frozen_verdict_not_on_steps_done \
  tests/test_note_skill_prose.py::test_the_delivery_report_names_paths_and_the_hashi_step \
  tests/test_note_skill_prose.py::test_a_vanished_source_is_reported_in_one_line \
  tests/test_note_instructions.py::test_deliver_source_gone_before_the_mark_is_delivered_unmarked \
  tests/test_note_privacy.py::test_every_script_ran_in_the_walk \
  tests/test_note_privacy.py::test_no_marker_on_stderr_of_any_script \
  tests/test_note_privacy.py::test_bad_invocations_echo_no_marker \
  tests/test_note_privacy.py::test_no_marker_in_stdout_outside_the_named_fields \
  tests/test_note_privacy.py::test_named_fields_carry_only_their_own_kinds \
  tests/test_note_privacy.py::test_every_named_field_carried_its_marker_once \
  tests/test_note_privacy.py::test_every_marker_reached_the_scripts \
  tests/test_note_privacy.py::test_user_text_fields_give_a_reason_each \
  tests/test_note_instructions.py::test_deliver_failure_keeps_the_stage_dir \
  tests/test_note_instructions.py::test_deliver_missing_kado_config_fails_at_kado_config_and_keeps_the_draft \
  tests/test_note_instructions.py::test_deliver_kado_transport_error_fails_at_note_and_keeps_the_draft \
  tests/test_note_skill_prose.py::test_a_failed_step_is_reported_and_the_draft_kept \
  tests/test_note_session.py::test_kept_drafts_vs_unfinished_drafts_vs_stale_stages \
  tests/test_note_meta.py::test_listing_splits_failed_deliveries_from_unfinished_drafts \
  tests/test_note_meta.py::test_kept_entry_carries_the_frozen_verdict \
  tests/test_note_instructions.py::test_deliver_killed_between_steps_is_a_kept_draft_not_a_stale_stage \
  tests/test_note_skill_prose.py::test_kept_drafts_are_handled_before_the_new_request \
  tests/test_note_skill_prose.py::test_interrupted_delivery_is_offered_resume_or_drop_never_silently_dropped \
  tests/test_note_instructions.py::test_deliver_resume_identical_note_counts_as_done \
  tests/test_note_instructions.py::test_deliver_resume_identical_unrecorded_note_counts_as_done \
  tests/test_note_instructions.py::test_deliver_trailing_newline_alone_is_identical \
  tests/test_note_instructions.py::test_drop_removes_stage_dir \
  tests/test_note_meta.py::test_remove_stage_deletes_the_directory \
  tests/test_note_skill_prose.py::test_kept_draft_drop_names_landed_files_by_kind_and_never_promises_nothing_landed \
  tests/test_note_instructions.py::test_deliver_success_removes_the_stage_dir \
  tests/test_note_meta.py::test_a_printed_draft_is_an_unfinished_draft_marked_staged \
  tests/test_note_meta.py::test_a_draft_interrupted_before_stage_is_unfinished_and_not_staged \
  tests/test_note_skill_prose.py::test_unfinished_drafts_are_offered_continue_or_discard \
  tests/test_note_skill_prose.py::test_continue_of_a_printed_draft_returns_to_the_approval_question \
  tests/test_note_skill_prose.py::test_continue_of_an_unstaged_draft_restarts_the_questions_without_new \
  tests/test_note_skill_prose.py::test_discard_of_an_unfinished_draft_drops_and_says_nothing_landed \
  tests/test_note_instructions.py::test_new_process_destination_wins \
  tests/test_note_instructions.py::test_new_takes_first_of_atomic_paths \
  tests/test_note_instructions.py::test_new_takes_scalar_atomic_path \
  tests/test_note_process.py::test_saved_destination_is_the_one_note_instructions_uses \
  tests/test_044_close_out_gaps.py::test_default_destination_saves_no_destination_and_new_uses_the_atomic_folder \
  tests/test_044_close_out_gaps.py::test_process_required_points_are_the_required_points_of_the_questions \
  tests/test_note_process.py::test_read_without_outline_leaves_missing_required_empty \
  tests/test_note_skill_prose.py::test_guidance_orders_and_weights_the_questions \
  tests/test_note_process_lib.py::test_read_guidance_only_without_frontmatter \
  tests/test_note_process.py::test_write_guidance_reaches_only_the_file_and_read \
  tests/test_note_process_lib.py::test_broken_file_sets_error_without_raising \
  tests/test_note_process.py::test_read_broken_file_reports_error_without_file_text \
  tests/test_note_instructions.py::test_new_broken_process_file_falls_back_to_atomic_path \
  tests/test_note_skill_prose.py::test_broken_process_file_and_missing_required_point_are_one_line_each \
  tests/test_note_process.py::test_read_with_outline_reports_missing_required \
  tests/test_note_process_lib.py::test_missing_required_lists_points_absent_from_the_outline \
  tests/test_note_skill_prose.py::test_process_offer_is_asked_once_with_three_answers_on_three_signals_only \
  tests/test_note_skill_prose.py::test_a_resumed_draft_gets_no_process_offer \
  tests/test_note_process_lib.py::test_decline_marker_alone_reads_as_declined_with_no_process \
  tests/test_note_process.py::test_read_missing_file_reports_not_exists \
  tests/test_note_process.py::test_write_from_outline_file_writes_process \
  tests/test_note_process.py::test_write_rejects_absent_required_point_and_writes_nothing \
  tests/test_note_process_lib.py::test_write_rejects_a_required_point_absent_from_the_outline \
  tests/test_note_skill_prose.py::test_process_offer_reruns_the_outline_and_writes_with_one_required_flag_per_point \
  tests/test_044_close_out_gaps.py::test_not_now_writes_nothing \
  tests/test_note_process.py::test_decline_writes_marker_read_reports_declined \
  tests/test_note_process.py::test_write_after_decline_replaces_marker \
  tests/test_note_process_lib.py::test_decline_then_write_replaces_the_marker \
  tests/test_note_skill_prose.py::test_process_mode_defines_keep_current_and_default_destination \
  tests/test_note_skill_prose.py::test_process_mode_shows_values_asks_and_writes_and_rejects_unknown \
  tests/test_note_session.py::test_process_mode_unknown_stem_gives_empty_path \
  tests/test_backup_restore_instance.py::test_backup_then_restore_keeps_note_processes_byte_identical \
  tests/test_note_processes_survive.py::test_update_tomo_leaves_note_processes_unchanged \
  tests/test_inbox_author_pipeline.py::test_unknown_type_found_path_points_to_note \
  tests/test_inbox_author_pipeline.py::test_unknown_type_not_found_path_byte_unchanged \
  tests/test_inbox_author_pipeline.py::test_known_key_mapped_template_byte_unchanged \
  tests/test_inbox_author_pipeline.py::test_builtin_default_byte_unchanged \
  tests/test_inbox_author_pipeline.py::test_canvas_and_base_steps_byte_unchanged \
  tests/test_inbox_author_pipeline.py::test_canvas_uses_json_gate_not_yaml_gate \
  tests/test_inbox_author_pipeline.py::test_base_uses_yaml_gate_not_json_gate \
  tests/test_044_user_docs.py::test_usage_names_both_deletions_and_recover \
  tests/test_note_triage_interplay.py::test_recover_treats_the_marked_source_as_fresh
```

</details>

## 2. Trace

Shorthand: `S::` = `tests/test_note_skill_prose.py::`, `NI::` = `tests/test_note_instructions.py::`, `NS::` = `tests/test_note_session.py::`, `NM::` = `tests/test_note_meta.py::`, `NA::` = `tests/test_note_actions.py::`, `NP::` = `tests/test_note_process.py::`, `NPL::` = `tests/test_note_process_lib.py::`, `TO::` = `tests/test_template_outline.py::`, `TS::` = `tests/test_template_syntax.py::`, `W::` = `tests/test-vault-config-writer.py::`, `EC::` = `tests/test_note_eval_case.py::`, `TI::` = `tests/test_note_triage_interplay.py::`, `IA::` = `tests/test_inbox_author_pipeline.py::`, `MOD::` = `tests/test_tomo_note_view_mod.py::`, `PR::` = `tests/test_note_privacy.py::`, `GAP::` = `tests/test_044_close_out_gaps.py::` (new, §3). **LW n.n** is a live-walk row; **E** is the recorded eval (§4, stale).

| Criterion | Class | Evidence | Mechanism the evidence falsifies |
|---|---|---|---|
| F1-AC1 | prose pin + script + live | `NS::test_note_include_absent_skips_listing`, `NS::test_unusable_note_include_counts_as_absent`, `NS::test_match_pattern_preview_table`, `NS::test_docstring_names_every_start_field`, `S::test_setup_asks_with_the_match_result_as_the_preview`, `S::test_each_preview_site_names_its_preview_content_after_its_option_line`, `GAP::test_an_unconfigured_selection_routes_to_the_setup`; LW 1.1 c573b7b7 (lists only in tool output), re-checks 5e1f413c, 657b5c02 | `start` reporting `include_configured` true without `note_include`; `match` not returning matched / unmatched / excluded lists; the skill not routing `include_configured: false` to step 2 or not asking with the match result as the preview. The 0.2.11 glob dialog was **not** walked live (§5) |
| F1-AC2 | prose pin + live | `S::test_setup_reruns_match_and_reprints_on_a_correction_and_writes_only_on_confirm`; LW 1.2 partial c573b7b7 (rerun `match`, nothing written; reprint not visible) | The Correct branch not rerunning `match`, not asking again with the new lists, or writing before Confirm |
| F1-AC3 | script + prose pin + live | `W::test_templates_include_inserts_into_block_without_key`, `W::test_templates_include_replaces_existing_key_with_continuation_lines`, `W::test_templates_include_appends_block_when_missing`, `W::test_templates_include_rejects_invalid_input_and_writes_nothing`, `W::test_templates_include_crlf_inserts_inside_block_and_keeps_crlf`, `W::test_templates_include_keeps_deeper_comment_after_list`, `W::test_templates_include_stdout_writes_nothing`, `S::test_each_skill_call_parses_with_the_scripts_argparse`, `GAP::test_a_confirmed_setup_continues_the_request`; LW 1.3 pass c573b7b7 | `templates-include` changing any byte outside the `note_include` lines (the tests compare whole files); the skill's writer call not parsing; the confirmed setup not going on to the template choice (gap, §3) |
| F1-AC4 | prose pin + script | `S::test_setup_abort_writes_nothing_and_a_confirmed_selection_stays`, `NS::test_match_listing_error_reported_exit_0` | The setup Abort writing anything; `match` doing more than list (its fake offers `list_dir` only, so a write raises). Not walked live |
| F1-AC5 | script | `tests/test_read_config_field.py::test_note_include_absent_is_omitted_and_exits_0`, `tests/test_read_config_field.py::test_note_include_present_is_returned_as_list`, `W::test_replace_existing_section`, `W::test_replace_preserves_neighbours_bytewise`, `W::test_end_to_end_file_roundtrip`, `W::test_all_sections_stack_in_one_config` | `read-config-field.py` failing or changing its output when `note_include` is absent; the shared CRLF header change in `vault-config-writer.py` breaking the `tags` / `relationships` / `callouts` / `trackers` subcommands `/tomo-setup` calls. `tomo-setup.md` and `read-config-field.py` are not in the branch diff (`git diff --stat c1acfdf4 HEAD -- tomo/`) |
| F1-AC6 | script | `NS::test_candidates_match_include_and_drop_daily`, `NS::test_match_daily_not_listed_gives_empty_excluded`, `NS::test_match_pattern_preview_table` (cited under F1-AC1) | `templates.mapping.daily` (with or without `.md`) reaching `candidates` or `matched` under a glob that matches it |
| F2-AC1 | prose pin only | `S::test_one_candidate_is_named_several_are_printed_and_asked`; LW 1.4 not walked | The one-candidate imperative deleted. No live or eval evidence that the model names it without asking (§5) |
| F2-AC2 | prose pin + live | `S::test_several_fits_are_asked_by_number_and_get_a_dialog_only_up_to_three_candidates`, `S::test_the_candidate_dialog_is_limited_to_three_candidates_plus_abort`, `S::test_the_candidate_choice_aborts_with_zero_so_every_listed_number_stays_valid`; LW 1.5 partial c573b7b7/afc60d6c; LW 1.1 re-check 5d5cbb6b (0.2.11: three candidates plus 0 Abort; "t_note" typed as Other chose it) and 657b5c02 (typed 1 chose t_note) | The several-fit branch asking without the numbered list, losing the dialog cap, or rejecting a listed number |
| F2-AC3 | prose pin + live | `S::test_no_fitting_candidate_offers_the_three_ways_out`, `S::test_inbox_author_hand_off_names_the_default_type_so_it_cannot_bounce_back`; LW 1.7 partial c573b7b7 (inbox-author reached from the setup, not from "No selected template fits."); LW 1.8 not walked | The none-fits branch losing one of Adjust patterns / inbox-author / Abort, or the hand-off not naming type `default` |
| F2-AC4 | script + prose pin | `S::test_empty_listing_says_empty_or_not_readable_with_the_remedy`, `S::test_unreadable_template_gives_the_same_remedy`, `NS::test_start_listing_error_reported_exit_0`, `NS::test_start_transport_error_is_listing_error`, `TO::test_template_denied_exits_1_and_names_the_kado_error`, `TO::test_template_not_found_exits_1_without_template_text`, `tests/test_044_user_docs.py::test_troubleshooting_remedy_for_template_folder_access` | A Kado listing error not surfacing as `folder_listed: 0` with `listing_error`; an unreadable template not exiting 1; the remedy sentence or "Never say that no template exists" removed from the skill; the troubleshooting page losing the remedy |
| F3-AC1 | script | `TO::test_outline_lists_every_heading_key_and_open_token`, `TO::test_outline_marks_prefilled_tokens_per_table`, `TS::test_headings_listed_with_level_text_line_and_body`, `TS::test_frontmatter_keys_list_top_level_keys_with_value_and_line`, `TS::test_tokens_listed_with_line_outside_fences_templater_and_escapes`, `TS::test_every_other_token_known_or_not_is_a_point`, `TS::test_prefilled_tokens_set_matches_the_sdd_table`, `NPL::test_points_are_headings_frontmatter_keys_and_open_tokens` | A heading, frontmatter key or non-prefilled token missing from the outline; a prefilled token listed as a point |
| F3-AC2 | prose pin + live | `S::test_question_budget_is_four_per_round_and_two_rounds`, `S::test_free_text_and_long_list_sites_stay_plain_text_only`; LW 2.1 partial afc60d6c (one open point asked; covered points not printed under the old version) | The four-per-round or two-round cap, or "Required points first", deleted |
| F3-AC3 | prose pin + eval | `S::test_covered_points_are_printed_and_no_open_point_means_no_question`, `EC::test_one_candidate_and_the_material_fills_every_point`, `EC::test_a_plain_text_question_before_the_draft_counts_as_a_question_round`, `EC::test_the_recorded_probe_is_all_green`; E grader `5-no-question-before-approval` (R `confirm-attendees`) | "When no point is open, ask nothing" deleted; a question before the draft in the fully covered case (grader 5). E is 0.2.4-era (§4) |
| F3-AC4 | prose pin | `GAP::test_a_skipped_optional_point_keeps_its_heading_empty_and_is_named` (new, §3), `S::test_the_header_names_every_field`; LW 2.3 not walked | Step 5.6 ("stay empty under their heading and go into the skipped line") or "keep every heading" deleted; the `Skipped, left empty:` header line removed. No live run skipped a point; that the delivered heading stays empty is unobserved |
| F3-AC5 | prose pin only | `S::test_required_points_are_re_asked_with_no_skip_option`, `S::test_question_budget_is_four_per_round_and_two_rounds`; LW 2.2 not walked | The re-ask "with no skip option", "only answer or abort", or "a skip is allowed only for optional points" deleted |
| F3-AC6 | prose pin only | `S::test_required_points_are_re_asked_with_no_skip_option`; LW 2.2 not walked | `Any non-empty answer, "none" included, answers a required point` deleted |
| F3-AC7 | script + prose pin | `TS::test_filled_note_check_fails_on_a_remaining_templater_opener`, `TS::test_tokens_inside_a_templater_span_are_not_points`, `TS::test_templater_include_on_line_one_is_a_span_not_a_point`, `NI::test_deliver_refuses_a_failing_filled_note_check`, `NI::test_stage_reports_failing_check`, `S::test_templater_is_never_executed_and_language_follows_the_call` | The filled-note check passing a note with `<%`; `deliver` uploading a note whose check fails (no Kado event allowed); the "never run it" imperative deleted. No script runs Templater; nothing could |
| F3-AC8 | prose pin + live | `S::test_templater_is_never_executed_and_language_follows_the_call`; session 8a8f3e67 asked in German (README Decisions Log 2026-11-06, `tomo-note-view` 0.1.2 row) | "Ask in the language the user writes in; keep the template's headings" deleted |
| F4-AC1 | prose pin + script + eval + live | `S::test_the_header_names_every_field`, `S::test_the_skill_prints_note_md_after_every_stage_never_draft_md`, `S::test_each_preview_site_names_its_preview_content_after_its_option_line`, `NI::test_stage_records_title_destination_keep_source`, `EC::test_each_model_turns_exactly_its_graders_red`, `EC::test_the_recorded_probe_is_all_green`, `EC::test_header_grader_accepts_the_inbox_file_as_a_path`; E graders 1–4 (R `header-after-delivery`, `ask-before-draft`, `print-draft-md`); LW 2.4 pass 5d5cbb6b (0.2.11: every approval dialog carried the header and the full fenced `note.md` in each preview, 2185 / 1308 / 1248 characters) | A header field dropped; `draft.md` shown instead of `note.md`; the preview not naming the header and `note.md`; `stage` not reporting `inbox_file` / `destination_file` |
| F4-AC2 | prose pin + script + live | `S::test_approval_options_and_changes_go_through_stage`, `S::test_each_preview_site_names_its_preview_content_after_its_option_line` (`approval-after-change`), `NI::test_stage_never_rewrites_draft_md`, `NI::test_stage_re_resolves_after_keep_source_flips`; LW 2.4 pass 5d5cbb6b (Change something with a new title restaged and asked again with the new header) | Change something not rewriting `draft.md` and rerunning `stage`, or not asking again with the new `note.md`; `stage` not rebuilding `note.md` |
| F4-AC3 | script + prose pin + live | `NI::test_stage_records_title_destination_keep_source`, `NA::test_move_note_values_come_from_the_draft_state`, `NI::test_deliver_kept_source_has_no_delete_and_is_still_marked`, `NI::test_view_follows_a_keep_source_flip`, `S::test_approval_options_and_changes_go_through_stage`; LW 2.4 c573b7b7 (`destination_file` `Atlas/Temp/...`), 5d5cbb6b | A changed title, destination or keep-source not reaching `meta.json`, the `move_note` action or the presence of `delete_source` |
| F4-AC4 | prose pin + eval + live | `GAP::test_approval_runs_deliver` (new, §3), `S::test_drop_on_every_abort_path`, `S::test_deliver_runs_with_the_stem`, `S::test_stage_runs_with_a_title_before_deliver`, `EC::test_a_deliver_after_the_question_still_counts`; E grader `6-no-deliver-without-approval` (R `deliver-before-ask`); LW 3.1 pass afc60d6c, LW 2.4 5d5cbb6b ("Deliver delivered with the source marked") | `- Deliver → step 7.` deleted (gap); an Abort path without `drop`; `deliver` before the approval answer (grader 6) |
| F4-AC5 | script + mod + live | `NI::test_stage_writes_view_with_header_and_fenced_note`, `NI::test_view_omits_the_source_line_when_the_source_is_kept`, `NI::test_view_omits_the_source_line_without_a_source`, `NI::test_view_fence_outgrows_backticks_in_the_note`, `NI::test_drop_removes_the_view`, `NI::test_new_removes_a_stale_view`, `NI::test_stage_of_another_stem_replaces_the_view`, `NI::test_refused_stage_leaves_no_view_of_another_stem`, `NI::test_failing_check_leaves_no_view`, `NI::test_untitled_stage_leaves_no_view`, `NI::test_view_never_reaches_stdout_or_stderr`, `NI::test_deliver_removes_the_view`, `NI::test_failed_deliver_removes_the_view_and_a_restage_writes_it`, `MOD::test_hooks_read_the_view_file_the_script_writes`, `MOD::test_manifest_names_the_mod_and_its_contract`, `MOD::test_versions_agree`, `MOD::test_mod_has_a_plugin_test`, `MOD::test_update_delivers_the_mod`, `MOD::test_install_delivers_the_mod`, `MOD::test_claude_plugin_validate_passes`, `MOD::test_claude_plugin_test_passes`; LW 2.4 5d5cbb6b (pane opened beside the transcript at the approval dialog, seen by the owner) | `view.md` not written by a titled, passing `stage` or not removed by `new`, `drop`, `deliver` or a refused / failing / untitled `stage`; the mod not opening the pane at the approval dialog, not registering `/note-draft`, or reading another path. `test_claude_plugin_test_passes` was RED-proven against the mod (§3, M8 and M9) |
| F5-AC1 | script + live | `NI::test_deliver_writes_note_json_md_then_marks_source_in_order`, `NI::test_deliver_stamps_note_peer_and_source`; LW 3.1 pass afc60d6c (three flat `2026-11-06_115536_*` files) | A write order other than note, JSON, MD, mark; the note not stamped `rendered-note` / `pending-move`; a file outside the inbox root |
| F5-AC2 | script | `NA::test_delete_source_depends_on_i01_when_source_is_not_kept`, `NA::test_no_delete_source_when_source_is_kept`, `NA::test_delete_without_depends_on_would_be_rejected`, `NI::test_deliver_stamps_note_peer_and_source` | `delete_source` missing for an unkept source, present for a kept one, or without `depends_on: ["I01"]` |
| F5-AC3 | script | `NA::test_set_validates_against_hashi_schema`, `NA::test_set_with_null_profile_validates`, `NA::test_move_note_has_exactly_the_sdd_keys_all_allowed_by_the_schema`, `NI::test_deliver_stamps_note_peer_and_source`, `TI::test_marked_source_beside_its_peer_raises_no_orphan_warning` | A delivered set failing `jsonschema` against `hashi-instructions.schema.json`; the MD peer not stamped `doc_type: instructions` (triage would find no instruction hit) |
| F5-AC4 | script + live | `NI::test_deliver_failure_at_a_step_stops_every_later_step` (one item per step); LW 7.7 pass afc60d6c (`failed` at `note`, later steps not run) | Any write after a failed step |
| F5-AC5 | script + live | `NI::test_deliver_stamps_note_peer_and_source`, `NI::test_deliver_mark_is_guarded_by_the_modified_time_it_read`, `TI::test_delivered_files_and_marked_source_are_no_new_item`, `TI::test_marked_source_beside_its_peer_raises_no_orphan_warning`; LW 3.1 afc60d6c (source marked). LW 3.3 (`/inbox` after delivery) not walked | The source mark not a `source` / `captured` merge guarded by `modified`; triage's real `compute_new_sources` counting the note, the peer or the source as new |
| F5-AC6 | script + prose pin | `NI::test_deliver_destination_clash_exits_3_before_any_write`, `NI::test_both_no_overwrite_probes_share_exit_3_and_the_exists_line` (fresh inbox clash), `NI::test_deliver_resume_different_note_exits_3_and_changes_nothing`, `NI::test_deliver_resume_taken_instruction_set_name_exits_3`, `tests/test_stub_contract.py::test_note_deliver_matches`, `S::test_name_taken_offers_rename_or_abort_and_never_overwrites`, `S::test_name_taken_branches_on_the_scripts_frozen_verdict_not_on_steps_done`; LW 3.4 not walked | A taken inbox or destination name overwritten, or reported without exit 3 and a first line `EXISTS:<path>`; the skill offering anything but Rename / Abort on `frozen` false |
| F5-AC7 | prose pin + script + live | `S::test_the_delivery_report_names_paths_and_the_hashi_step`, `S::test_a_vanished_source_is_reported_in_one_line`, `NI::test_deliver_writes_note_json_md_then_marks_source_in_order`, `NI::test_deliver_source_gone_before_the_mark_is_delivered_unmarked`; LW 3.1 pass afc60d6c | The report losing a path or the Hashi line; `deliver` output without `note_path`, `instructions_json`, `instructions_md`, `source_marked` |
| F5-AC8 | script | `PR::test_every_script_ran_in_the_walk`, `PR::test_no_marker_on_stderr_of_any_script`, `PR::test_bad_invocations_echo_no_marker`, `PR::test_no_marker_in_stdout_outside_the_named_fields`, `PR::test_named_fields_carry_only_their_own_kinds`, `PR::test_every_named_field_carried_its_marker_once`, `PR::test_every_marker_reached_the_scripts`, `PR::test_user_text_fields_give_a_reason_each` | Under the amended CON-3 (README Decisions Log 2026-11-05) the allowlist in `tests/test_note_privacy.py` is the evidence: any marker from the request, source, template body or answers in stdout outside the named fields, any marker on stderr, a named field with no reason, or a script left out of the walk |
| F6-AC1 | script + prose pin + live | `NI::test_deliver_failure_at_a_step_stops_every_later_step`, `NI::test_deliver_failure_keeps_the_stage_dir`, `NI::test_deliver_missing_kado_config_fails_at_kado_config_and_keeps_the_draft`, `NI::test_deliver_kado_transport_error_fails_at_note_and_keeps_the_draft`, `S::test_a_failed_step_is_reported_and_the_draft_kept`; LW 7.7 pass afc60d6c | A failed step not recorded as `failed_step`, the stage removed, the source marked, or the step not reported |
| F6-AC2 | script + prose pin + live | `NS::test_kept_drafts_vs_unfinished_drafts_vs_stale_stages`, `NM::test_listing_splits_failed_deliveries_from_unfinished_drafts`, `NM::test_kept_entry_carries_the_frozen_verdict`, `NI::test_deliver_killed_between_steps_is_a_kept_draft_not_a_stale_stage`, `S::test_kept_drafts_are_handled_before_the_new_request`, `S::test_interrupted_delivery_is_offered_resume_or_drop_never_silently_dropped`; LW 7.7 afc60d6c (kept draft resumed after `/mcp` reconnect); LW 7.1 not walked | A kept draft missing from `start`, listed as stale or unfinished, or without title / template / time / `frozen`; the skill handling it after the request or dropping it unasked |
| F6-AC3 | script + live | `NI::test_deliver_resume_identical_note_counts_as_done`, `NI::test_deliver_resume_identical_unrecorded_note_counts_as_done`, `NI::test_deliver_trailing_newline_alone_is_identical`, `NI::test_deliver_resume_different_note_exits_3_and_changes_nothing`, `NI::test_deliver_resume_taken_instruction_set_name_exits_3`; LW 7.2 partial afc60d6c (resume ran all steps; no identical-target case) | An identical landed target rewritten or refused; a different one overwritten |
| F6-AC4 | script + prose pin | `NI::test_drop_removes_stage_dir`, `NM::test_remove_stage_deletes_the_directory`, `S::test_kept_draft_drop_names_landed_files_by_kind_and_never_promises_nothing_landed`; LW 7.3 not walked | `drop` leaving the stage directory, or calling Kado (the `inst` fixture's fake has `read_note` only, so any write raises) |
| F6-AC5 | prose pin + script | `S::test_drop_on_every_abort_path`, `S::test_setup_abort_writes_nothing_and_a_confirmed_selection_stays`, `NI::test_drop_removes_stage_dir`, `NI::test_drop_removes_the_view`; LW 2.5 not walked; 5d5cbb6b Discard `removed: true` (LW 7.6a) | An Abort path without `drop`; `drop` touching the vault or `note_include` |
| F6-AC6 | script + live | `NI::test_deliver_success_removes_the_stage_dir`; LW 3.1 pass afc60d6c (stage dir gone) | A stage directory left after a delivered run |
| F6-AC7 | script + prose pin + live | `NS::test_kept_drafts_vs_unfinished_drafts_vs_stale_stages`, `NM::test_a_printed_draft_is_an_unfinished_draft_marked_staged`, `NM::test_a_draft_interrupted_before_stage_is_unfinished_and_not_staged`, `S::test_unfinished_drafts_are_offered_continue_or_discard`, `S::test_continue_of_a_printed_draft_returns_to_the_approval_question`, `S::test_continue_of_an_unstaged_draft_restarts_the_questions_without_new`, `S::test_discard_of_an_unfinished_draft_drops_and_says_nothing_landed`; LW 7.6a pass afc60d6c (offer and Continue), 5d5cbb6b (0.2.11 offer and Discard) | An unfinished draft dropped as stale or unasked, `staged` wrong, or Continue going to the wrong step. Continue under 0.2.11 not re-checked (§5) |
| F7-AC1 | script | `NI::test_new_process_destination_wins`, `NI::test_new_takes_first_of_atomic_paths`, `NI::test_new_takes_scalar_atomic_path`, `NP::test_saved_destination_is_the_one_note_instructions_uses`, `GAP::test_default_destination_saves_no_destination_and_new_uses_the_atomic_folder` (new, §3) | `default_destination` not the process destination when one is saved, or not `concepts.atomic_note.path` when none is |
| F7-AC2 | prose pin + script | `GAP::test_process_required_points_are_the_required_points_of_the_questions` (new, §3), `S::test_required_points_are_re_asked_with_no_skip_option`, `NP::test_read_without_outline_leaves_missing_required_empty`; not walked | "Required points are the process `required` list minus `missing_required`" deleted (gap); `read` not returning `required` |
| F7-AC3 | prose pin + script | `S::test_guidance_orders_and_weights_the_questions`, `NPL::test_read_guidance_only_without_frontmatter`, `NP::test_write_guidance_reaches_only_the_file_and_read`; not walked | The guidance imperative deleted; `read` not returning the guidance text. That the model orders by it is unobserved |
| F7-AC4 | script + prose pin | `NPL::test_broken_file_sets_error_without_raising`, `NP::test_read_broken_file_reports_error_without_file_text`, `NI::test_new_broken_process_file_falls_back_to_atomic_path`, `S::test_broken_process_file_and_missing_required_point_are_one_line_each` | A broken process file raising, blocking `new`, or not reported in one line |
| F7-AC5 | script + prose pin | `NP::test_read_with_outline_reports_missing_required`, `NPL::test_missing_required_lists_points_absent_from_the_outline`, `S::test_broken_process_file_and_missing_required_point_are_one_line_each` | A required point absent from the outline not in `missing_required`, or not named |
| F7-AC6 | prose pin only | `S::test_process_offer_is_asked_once_with_three_answers_on_three_signals_only`; LW 4.1, 4.2 not walked | A signal, "Ask once" or the three answers deleted. No live run reached the offer (§5) |
| F7-AC7 | prose pin + script + live | `S::test_process_offer_is_asked_once_with_three_answers_on_three_signals_only`, `S::test_a_resumed_draft_gets_no_process_offer`, `NPL::test_decline_marker_alone_reads_as_declined_with_no_process`, `NP::test_read_missing_file_reports_not_exists`; LW 4.5 pass afc60d6c (resumed delivery with a signal, no offer) | The "do not ask" rule for an existing file, a marker or a resumed delivery deleted; `read` misreporting `exists` / `declined` |
| F7-AC8 | script + prose pin | `NP::test_write_from_outline_file_writes_process`, `NP::test_write_rejects_absent_required_point_and_writes_nothing`, `NPL::test_write_rejects_a_required_point_absent_from_the_outline`, `S::test_process_offer_reruns_the_outline_and_writes_with_one_required_flag_per_point`, `GAP::test_not_now_writes_nothing` (new, §3) | `write` accepting a required point the outline lacks, or writing on rejection; "Not now: write nothing" deleted or given a `note-process.py` call (gap) |
| F7-AC9 | script + prose pin | `NP::test_decline_writes_marker_read_reports_declined`, `NPL::test_decline_marker_alone_reads_as_declined_with_no_process`, `S::test_process_offer_reruns_the_outline_and_writes_with_one_required_flag_per_point`; LW 4.3, 4.4 not walked | `decline` not writing the marker, `read` not reporting `declined`, the Never branch losing its `decline` call |
| F7-AC10 | script + prose pin | `NP::test_write_after_decline_replaces_marker`, `NPL::test_decline_then_write_replaces_the_marker`, `S::test_process_mode_defines_keep_current_and_default_destination`, `S::test_process_mode_shows_values_asks_and_writes_and_rejects_unknown`, `S::test_free_text_and_long_list_sites_stay_plain_text_only` (required headings, guidance, another folder), `GAP::test_default_destination_saves_no_destination_and_new_uses_the_atomic_folder` (new, §3); LW 4.6–4.8 not walked | A write keeping a decline marker; process mode losing a question; Default keeping the previous destination (gap) |
| F7-AC11 | script + prose pin | `NS::test_process_mode_unknown_stem_gives_empty_path`, `S::test_process_mode_shows_values_asks_and_writes_and_rejects_unknown`; LW 4.10 not walked | An unknown stem given a path; the "template is unknown … write nothing" imperative deleted |
| F7-AC12 | script | `tests/test_backup_restore_instance.py::test_backup_then_restore_keeps_note_processes_byte_identical`, `tests/test_note_processes_survive.py::test_update_tomo_leaves_note_processes_unchanged` (plain and `--force`) | Backup, restore or `update-tomo.sh` changing, removing or naming `config/note-processes/`; the update test also proves the sync ran |
| F8-AC1 | byte pin | `IA::test_unknown_type_found_path_points_to_note`, `IA::test_unknown_type_not_found_path_byte_unchanged`; LW 6.2 not walked | The found path not exactly the `/note` redirect and STOP; the not-found path not byte-identical to 0.3.0 |
| F8-AC2 | byte pin + script | `IA::test_known_key_mapped_template_byte_unchanged`, `IA::test_builtin_default_byte_unchanged`, `IA::test_canvas_and_base_steps_byte_unchanged`, `IA::test_canvas_uses_json_gate_not_yaml_gate`, `IA::test_base_uses_yaml_gate_not_json_gate`; LW 6.1 not walked | Any byte of the mapped-key, built-in default, `.canvas` / `.base` text changed from 0.3.0; a gate swapped |
| F9-AC1 | document | `tests/test_044_user_docs.py::test_usage_names_both_deletions_and_recover` | `docs/usage.md` losing the two deletions or `/inbox --recover` |
| F9-AC2 | script | `TI::test_recover_treats_the_marked_source_as_fresh` | Triage's real routing plan under `--recover` not listing the `/note`-marked source as fresh |

## 3. Gaps the trace found

### Closed

Seven criterion parts had no test that could fail. Each is closed by a test in `tests/test_044_close_out_gaps.py`. Each test was proven RED by applying the mutation below in an isolated export (`git archive HEAD | tar -x -C $TMPDIR/co044-<name>`, the new test file copied in, `PYTHONDONTWRITEBYTECODE=1`), never in the worktree. The unmutated export was green first (`7 passed in 0.30s`); each mutation went into a fresh export and turned exactly its own test red (`1 failed, 6 passed`).

| # | Criterion | Part no test could fail | Test | Mutation → failure |
|---|---|---|---|---|
| M1 | F1-AC1 | the route from `include_configured: false` to the setup | `test_an_unconfigured_selection_routes_to_the_setup` | `` - `include_configured` is false → step 2. `` deleted from step 1 → `` assert '- `include_configured` is false → step 2.' in " ## 1. Start Run: …` `` |
| M2 | F1-AC3 | "continue the request" after the setup is saved | `test_a_confirmed_setup_continues_the_request` | ``Otherwise rerun the step 1 `start` call (skip kept drafts already handled) and go to step 3.`` deleted → `ValueError: substring not found` |
| M3 | F3-AC4 | "keep its heading empty" | `test_a_skipped_optional_point_keeps_its_heading_empty_and_is_named` | step 5 item 6 (`Optional points still open stay empty under their heading …`) deleted → `assert '6. Optional points still open stay empty under their heading and go into the skipped line of step 6.' in ' ## 5. Ask for open points …'` |
| M4 | F4-AC4 | "WHEN the user approves, run `deliver`" | `test_approval_runs_deliver` | `- Deliver → step 7.` deleted → `AssertionError: assert '- Deliver → step 7.' in ' ## 6. Draft …'` |
| M5 | F7-AC2 | the process `required` list as the source of required points | `test_process_required_points_are_the_required_points_of_the_questions` | ``Required points are the process `required` list minus `missing_required`.`` deleted → ``AssertionError: assert 'Required points are the process `required` list minus `missing_required`.' in ' ## 5. Ask for open points …'`` |
| M6 | F7-AC8 | "WHEN not now, nothing" | `test_not_now_writes_nothing` | `- Not now: write nothing.` deleted → `AssertionError: assert '- Not now: write nothing.' in ' ## 8. Process offer …'` |
| M7 | F7-AC10 (Default), F7-AC1 | a Default write after an earlier destination saves none, so `new` uses the atomic-note folder (LW 4.8: "no test asserts a saved file lacks `destination`") | `test_default_destination_saves_no_destination_and_new_uses_the_atomic_folder` | in `lib/note_process.py` `write_process`, a carry-over inserted before `fm: dict = {}`: `if folder is None and path.is_file(): folder = read_process(process_dir, template_stem).get("destination") or None` → `AssertionError: assert 'destination' not in '---\ndestin...genda\n---\n'` |

**What else the mutations turn red.** All seven were applied together to one fresh export and the full suite run there (`--continue-on-collection-errors`; four modules that shell out to `git` cannot collect in an export without `.git`):

```
25 failed, 8030 passed, 7 skipped, 2 warnings, 4 errors in 1329.72s (0:22:09)
```

The 25 split as follows, each mutation then re-run alone in a fresh export against the non-gap failures:

- **7** are the gap tests above.
- **7** fail in an unmutated export too (environment: no `.git` for `git grep` / `git ls-files`, and the known `test_install_smoke_ide_bridge_block_exists`): `test_035_schema_identity.py::test_no_ref_resolves_the_canonical_url_to_the_producer_copy`, two `test_garden_audit_render.py` CON-7 byte tests, three `test_tomo_note_view_mod.py` tracked / gitignored checks, and the IDE bridge smoke.
- **11** are the eval-patch application tests (`test_eval_conductor_cases.py::test_mutation_applies_cleanly_to_a_fresh_assembly`, `::test_mutation_removes_and_adds_its_declared_clauses`, `test_run_evals.py::test_spec_043_mutation_applies_in_the_runner_and_changes_only_its_files`, for the five `/note` patches). They demand zero offset and fuzz, so they go red when a mutation **moves lines** above a hunk (M1 +10, M3 +8) or **edits a line inside a hunk's context** (M4 +9, M5 +2). M2, M6 and M7 turn nothing else red.

These are context guards, not pins: they fail on any edit near a patch, and the next routine rebase of the patches removes them. To separate the two, M1, M3, M4 and M5 were repeated as same-line-count rewordings that change the meaning (`→ step 2` → `→ step 3`; `stay empty under their heading` → `get a placeholder under their heading`; `Deliver → step 7` → `Deliver → step 8`; the required-points sentence → `…the points the template itself marks as required.`), run against the gap file, `test_note_skill_prose.py`, `test_044_why_docs.py`, `test_note_eval_case.py` and the three patch tests:

- M1r: `1 failed, 342 passed`, the gap test alone. M3r: `1 failed, 342 passed`, the gap test alone.
- M4r: `10 failed, 333 passed`, the gap test plus the 9 patch tests (the line sits in the context of four `/note` patches).
- M5r: `3 failed, 340 passed`, the gap test plus `confirm-attendees` in both patch tests (context).

So for F4-AC4 and F7-AC2 an edit of the imperative was already caught, but only as patch context; no test said what the line must mean.

The driver scripts (`co044-mutate.py`, `co044-red.sh`) are not in the repo; each mutation is the one edit named above.

### Doubted tests, RED-proven

`test_claude_plugin_test_passes` wraps `claude plugin test` and passes on a `0 fail` line; whether it fails when the mod misbehaves was doubted. Two mutations of `tomo-note-view/hooks/register.tsx` in fresh exports:

- **M8** `else if (isApproval(e.questions, text)) await openPane($, text)` → `else if (false) …`: `1 failed`, with 10 mod tests `(fail)`, among them `(fail) the pane opens at the approval dialog while view.md exists`.
- **M9** the title fallback `(title !== '' && (o.preview ?? '').includes(title))` → `false`: `1 failed`, with `(fail) German labels with the note in the preview open the pane (frontmatter title)` and `(fail) the first heading is the title when the frontmatter has none`.

### Corrected references

`live-walk.md` cited two test names that do not exist: row 1.6 `test_several_fits_ask_at_most_three_candidates_plus_abort` (now `test_several_fits_are_asked_by_number_and_get_a_dialog_only_up_to_three_candidates`) and row 4.6 `test_every_question_has_at_most_four_options` (now `test_every_dialog_question_has_at_most_four_options`). Every other cited name was checked to exist by script.

## 4. Eval evidence

The eval case `note-draft-before-approval` (not gated, ADR-8) and its five mutation proofs first ran on **`note-from-template` 0.2.4** (claude 2.1.317, 2026-11-06). On the owner's instruction they were re-run on **0.2.11** (claude 2.1.319, 2026-11-07, $2.45): GREEN 3/3 unmutated, every patch RED, but `header-after-delivery` turned `1-header-before-approval` red in 2/3 and `confirm-attendees` turned `5-no-question-before-approval` red in 2/3 (3/3 on 0.2.4); the other three hit their target in 3/3. A run in which the mutated skill still produced the right behaviour is not a grader miss, so these two proofs are weaker on 0.2.11, not broken. The eval session cannot offer `AskUserQuestion`, so the eval grades only the plain-text fallback, never the 0.2.11 dialog or its preview.

The 0.2.11 verdicts, verbatim from the runner:

```
GREEN (PARTIAL SUITE — does not satisfy the merge rule) 1/1 cases · runs 3 · $0.41 · 76 s · claude 2.1.319 · tree clean · tomo-tmp/evals/2026-11-07T13-10-17Z
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · note-draft-before-approval: 1-header-before-approval (run 0), note-draft-before-approval: 1-header-before-approval (run 1) · runs 3 · $0.41 · 62 s · claude 2.1.319 · tree clean · mutation header-after-delivery · tomo-tmp/evals/2026-11-07T13-11-40Z
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · note-draft-before-approval: 1-header-before-approval (run 0), note-draft-before-approval: 2-note-printed-before-approval (run 0), note-draft-before-approval: 3-note-md-read-before-approval (run 0), note-draft-before-approval: 4-draft-md-never-printed (run 0), note-draft-before-approval: 2-note-printed-before-approval (run 1), note-draft-before-approval: 3-note-md-read-before-approval (run 1), note-draft-before-approval: 4-draft-md-never-printed (run 1), note-draft-before-approval: 1-header-before-approval (run 2), note-draft-before-approval: 2-note-printed-before-approval (run 2), note-draft-before-approval: 3-note-md-read-before-approval (run 2), note-draft-before-approval: 4-draft-md-never-printed (run 2) · runs 3 · $0.39 · 62 s · claude 2.1.319 · tree clean · mutation ask-before-draft · tomo-tmp/evals/2026-11-07T13-12-47Z
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · note-draft-before-approval: 1-header-before-approval (run 0), note-draft-before-approval: 2-note-printed-before-approval (run 0), note-draft-before-approval: 3-note-md-read-before-approval (run 0), note-draft-before-approval: 4-draft-md-never-printed (run 0), note-draft-before-approval: 2-note-printed-before-approval (run 1), note-draft-before-approval: 3-note-md-read-before-approval (run 1), note-draft-before-approval: 4-draft-md-never-printed (run 1), note-draft-before-approval: 2-note-printed-before-approval (run 2), note-draft-before-approval: 3-note-md-read-before-approval (run 2), note-draft-before-approval: 4-draft-md-never-printed (run 2) · runs 3 · $0.42 · 65 s · claude 2.1.319 · tree clean · mutation print-draft-md · tomo-tmp/evals/2026-11-07T13-13-54Z
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · note-draft-before-approval: 0-approval-asked (run 0), note-draft-before-approval: 1-header-before-approval (run 0), note-draft-before-approval: 2-note-printed-before-approval (run 0), note-draft-before-approval: 3-note-md-read-before-approval (run 0), note-draft-before-approval: 5-no-question-before-approval (run 0), note-draft-before-approval: 6-no-deliver-without-approval (run 0), note-draft-before-approval: 9-no-leak (run 0), note-draft-before-approval: 1-header-before-approval (run 1), note-draft-before-approval: 2-note-printed-before-approval (run 1), note-draft-before-approval: 4-draft-md-never-printed (run 1), note-draft-before-approval: 6-no-deliver-without-approval (run 1), note-draft-before-approval: 9-no-leak (run 1), note-draft-before-approval: 0-approval-asked (run 2), note-draft-before-approval: 1-header-before-approval (run 2), note-draft-before-approval: 2-note-printed-before-approval (run 2), note-draft-before-approval: 3-note-md-read-before-approval (run 2), note-draft-before-approval: 4-draft-md-never-printed (run 2), note-draft-before-approval: 5-no-question-before-approval (run 2), note-draft-before-approval: 6-no-deliver-without-approval (run 2), note-draft-before-approval: 9-no-leak (run 2) · runs 3 · $0.41 · 76 s · claude 2.1.319 · tree clean · mutation deliver-before-ask · tomo-tmp/evals/2026-11-07T13-15-05Z
RED (PARTIAL SUITE — does not satisfy the merge rule) 0/1 cases · note-draft-before-approval: 5-no-question-before-approval (run 0), note-draft-before-approval: 5-no-question-before-approval (run 2) · runs 3 · $0.41 · 80 s · claude 2.1.319 · tree clean · mutation confirm-attendees · tomo-tmp/evals/2026-11-07T13-16-26Z
```

The 0.2.4 evidence, verbatim from `evals/_mutations/README.md`:


```
GREEN (PARTIAL SUITE — does not satisfy the merge rule) 1/1 cases · runs 3 · $0.40 · 67 s · claude 2.1.317 · tree clean · tomo-tmp/evals/2026-11-06T07-58-32Z
```

| Grader | Criterion | Proof | RED | Results (`tomo-tmp/evals/…`) |
|---|---|---|---|---|
| `1-header-before-approval` | F4-AC1 | `header-after-delivery` | 3/3 | `2026-11-06T07-59-50Z` |
| `2-note-printed-before-approval` | F4-AC1 | `ask-before-draft` | 3/3 | `2026-11-06T08-00-58Z` |
| `3-note-md-read-before-approval`, `4-draft-md-never-printed` | F4-AC1 | `print-draft-md` | 3/3 | `2026-11-06T08-01-57Z` |
| `5-no-question-before-approval` | F3-AC3 | `confirm-attendees` (second form; the first came back GREEN 3/3, `2026-11-06T08-03-03Z`) | 3/3 | `2026-11-06T08-11-37Z` |
| `6-no-deliver-without-approval` | F4-AC4 | `deliver-before-ask` | 3/3 | `2026-11-06T08-04-26Z` |

`0-approval-asked` is a control; `9-no-leak` is a byte copy of `evals/_lib/no-leak.md` and inherits `report-run-id`. The pytest side (`EC::` ids in §2) checks the grader shapes on recorded and hand-built traces and stays current; it proves the graders, not the 0.2.11 model behaviour.

## 5. KPIs

| KPI (requirements.md Success Metrics) | Measured | Verdict |
|---|---|---|
| Adoption: the owner uses `/note` for at least one note kind on the live vault in the first month | not measured: every run so far was on `tomo-instance` and the test vault | open, measured from release |
| Engagement: most meeting runs need one round; no run exceeds two optional rounds | not measured as a rate. The walked sessions asked at most one round (LW 2.1 afc60d6c: one point); the cap is a prose pin | open |
| 100 % of delivered notes pass the filled-note check, 100 % of sets pass Hashi's schema, in tests and the eval case | tests: every delivering test passes the check, and `NI::test_deliver_stamps_note_peer_and_source` and `NA::test_set_validates_against_hashi_schema` validate with `jsonschema`. The eval case never delivers (grader 6), so "in the eval case" cannot be measured | 🟢 in tests; n.a. in the eval |
| 0 duplicates after a delivery | `TI::test_delivered_files_and_marked_source_are_no_new_item` (real triage functions, fake vault); LW 3.3 not walked | 🟢 in tests; live unmeasured |
| 0 overwrites across the name-taken and resume tests | every exit 3 test asserts no write event and the target unchanged | 🟢 |
| 0 delivered notes with an empty required point | not measured: no script checks required points; it is model behaviour with a prose pin (F3-AC5) and no live run | open |
| 0 vault writes and 0 kept drafts after an abort | `NI::test_drop_removes_stage_dir`, `S::test_drop_on_every_abort_path`; live only for a Discard (5d5cbb6b `removed: true`); LW 2.5 not walked | 🟢 in tests; abort live unmeasured |
| 0 process offers after "never" | `NPL::test_decline_marker_alone_reads_as_declined_with_no_process` and the prose rule; LW 4.3, 4.4 not walked | 🟢 for `read`; the model's offer unmeasured |
| A new note kind costs a template and no Tomo change | by construction: `TS::test_every_other_token_known_or_not_is_a_point` (any token is a point), no template-specific code; the live walk used the test vault's own `t_note` | 🟢 |

Quality requirement "at most 16 Kado calls": `NI::test_deliver_stays_within_the_kado_call_budget` covers `deliver` only (not cited for a criterion; it ran in the full suite).

**Spend.** Spec 044 eval spend $3.31 (README Decisions Log, T4.1). This close-out ran no paid eval: $0.

## 6. Validation

- **The single invocation (§1):** `281 passed in 103.10s (0:01:43)` (2026-11-07).
- **Gap tests on the real tree:** `7 passed in 0.37s`.
- **All seven mutations together, full suite in an export:** `25 failed, 8030 passed, 7 skipped, 2 warnings, 4 errors in 1329.72s (0:22:09)`, split in §3.
- **Mod RED proofs (M8, M9):** `1 failed` each, §3.
- **ruff:** `./venv/bin/ruff check tests/test_044_close_out_gaps.py` → `All checks passed!`
- **Full pytest (worktree, 2026-11-07, the tree of §1):** `1 failed, 8075 passed, 4 skipped, 1 warning in 1384.51s (0:23:04)`. The one failure is the known unrelated `tests/ide_bridge/test_configure_ide_bridge.py::test_install_smoke_ide_bridge_block_exists` (a stray `~/.tomo/instances.json` entry), not a 044 test.

## 7. Open items

- **Live-walk coverage.** Of 45 rows, 5 pass, 5 partial, 2 first failed then re-checked (1.1, 2.4), 1 n.a. (7.10), and **32 not walked** by owner decision 2026-11-06. Seven criteria have a prose pin and no live or eval evidence for their model part: **F2-AC1** (one candidate named without asking), **F3-AC4** (a skipped point left as an empty heading), **F3-AC5** and **F3-AC6** (required re-ask, "none" accepted), **F7-AC2** (process required points asked as required), **F7-AC3** (guidance orders the questions), **F7-AC6** (the process offer). F5-AC6's Rename / Abort dialogue and F6-AC3's identical-target resume are covered by scripts or prose but were never seen live.
- **Weaker eval proofs on 0.2.11.** §4: `header-after-delivery` and `confirm-attendees` were red in 2/3 on their target grader (3/3 on 0.2.4).
- **The 0.2.11 glob dialog** (step 2, content in the preview) was not checked live: in 5d5cbb6b `note_include` was already set (LW 1.1).
- **Continue under 0.2.11** was not re-checked (LW 7.6a); only the offer and Discard were.
- **Mod auto-load** was verified live once, in session 5d5cbb6b (owner saw the pane). Hashi's session view rendering of the preview is unverified (README revert condition).
- **`tomo-note-view` advisories** (mod 0.1.2, `register.tsx`):
  - `MIN_TITLE = 3`: a draft whose title is shorter than three characters is never recognised by its preview; the pane then opens only on a `deliver`-labelled option. Conversely a short but common title (three or four letters) found in an unrelated dialog's preview while `view.md` exists opens the pane at the wrong question (false positive).
  - `APPROVAL_LABEL = /deliver/i` also matches labels such as "Deliver later" or "Undeliverable" in any dialog asked while `view.md` exists.
  - Both only open a pane beside the transcript; neither changes what is delivered.
- **F1-AC5 "unchanged"** is evidenced by the existing writer and reader tests plus the branch diff; there is no test that would notice a behaviour change in `/tomo-setup` that keeps those scripts' outputs.
- **F4-AC1's `In the inbox until applied`** field and the pane's text are tested; whether the model copies the preview in full is live evidence from one session (5d5cbb6b), where one preview carried a copy error ("Ttafel") the model reported itself.

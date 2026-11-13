---
title: "Close-out — 045 /review: weekly and monthly reviews the user edits before they land"
status: complete
---

# Close-out

## Standing rule for this document

Every acceptance criterion below traces to evidence that was **executed**, not to a task that mentions it:

- Criteria about scripts, libs, schemas, the writer, the documents and the fake-vault walks trace to pytest node ids, all run in the one invocation of §1. The test body was read for every cited id; a name or docstring was never taken as the evidence.
- Criteria about what the model does in the dialogue trace to a **prose pin** (a `tests/test_review_skill*.py` or `tests/test_045_close_out_gaps.py` assertion that the imperative exists in `periodic-review/SKILL.md`) **plus** a live-walk line (`<session>:<line>` as [`live-walk.md`](live-walk.md) cites it). A prose pin is red when the imperative is deleted or reworded; it is never evidence that the model obeys it. Where a dialogue criterion has a prose pin and no live evidence, the trace says so.
- Criteria whose wording the walk changed cite the README Decisions Log row that changed it.
- `tests/test_review_integration.py` (`-m integration`, live Kado) is not in the invocation: it skips without `TOMO_LIVE_KADO=1`. Its ten tests ran green for the owner at T6.2 (README, 2026-11-12 "Kado call budget raised") and are named where they add live-vault evidence, never as the only evidence.

For each criterion the trace names the **mechanism** the evidence falsifies: the concrete change that would turn it red.

`requirements.md` and `solution.md` were not edited by this close-out.

## Criteria count

The plan says **59**. The PRD has **59**: F1:10 F2:9 F3:13 F4:7 F5:11 F6:4 F7:2 F8:3, counted as the `- [ ] Given` lines under lines 94–191 of `requirements.md` v1.7. `solution.md` §Acceptance Criteria restates all 59 in 57 distinct ids: three appear only in combined form (`F2-AC6/7`, `F3-AC1/2`, `F3-AC11/12`), so `grep -o 'F[0-9]*-AC[0-9]*' | sort -u` prints 57, not a missing criterion.

**59/59 trace to evidence; 58 to executed evidence that can fail, 1 part (F7-AC1 cost records) to document review only.** By class:

- **41 trace to script, lib, e2e, schema or document tests**, several with a prose pin or live evidence beside them: F1-AC3, F1-AC4, F1-AC5, F1-AC7, F1-AC9, F1-AC10, F2-AC1, F2-AC2, F2-AC3, F2-AC5, F2-AC6, F2-AC7, F2-AC9, F3-AC1, F3-AC2, F3-AC3, F3-AC4, F3-AC5, F3-AC6, F3-AC7, F3-AC8, F3-AC9, F3-AC10, F3-AC11, F3-AC12, F3-AC13, F4-AC1, F4-AC3, F4-AC4, F4-AC6, F5-AC3, F5-AC4, F5-AC5, F5-AC6, F5-AC8, F5-AC9, F6-AC2, F6-AC3, F7-AC2, F8-AC1, F8-AC3.
- **17 have a model-behaviour part** and trace to a prose pin for it, beside script tests for the script part: F1-AC1, F1-AC2, F1-AC6, F1-AC8, F2-AC4, F2-AC8, F4-AC2, F4-AC5, F4-AC7, F5-AC1, F5-AC2, F5-AC7, F5-AC10, F5-AC11, F6-AC1, F6-AC4, F8-AC2 (the month's day after, now a lib test, §3). Of these, **11 also have live-walk evidence** (F1-AC1, F1-AC2, F1-AC8, F2-AC8, F4-AC2, F4-AC5, F5-AC1, F5-AC2, F5-AC7, F5-AC10, F6-AC1), and **6 rest on the prose pin alone for their model part**: F1-AC6 and F4-AC7 (not reachable on the test vault, live-walk.md "Model-behaviour criteria"), F2-AC4 (no year-less argument was walked), F5-AC11 (the report's wording was not read), F6-AC4 (the `move-refused` line was not seen), F8-AC2 (prose: none; the lib test is new).
- **1 has a part no test can reach**: F7-AC1's "cost records" — the cost log is a hand-written document (`docs/evolution/inbox-cost-log.md` §"Spec 045 — T6.3 live walk"); its rows were checked by reading, not by a test.
- **0 OPEN.** The consumer-owned halves (F5-AC8 "Hashi lists and validates", F6-AC4 "the apply refuses the move") are evidenced by Hashi's vendored schema and Hashi's run logs, §4.

Three criterion parts had no test that pinned them; all three are now closed by RED-proven tests (§3).

## 1. The single invocation

The **524 node ids** in the trace table ran **together in one `pytest` invocation** on 2026-11-13, branch `docs/31-weekly-monthly-review` at `a2f1daa6` with `tests/test_045_close_out_gaps.py` added (uncommitted at the time of the run; committed in `6f9a96e2`):

```
725 passed in 8.34s
```

524 node ids collect **725 items**; the difference is parametrisation. Nothing was skipped. Collection was checked by script, not by eye: the sorted list of cited node ids and the sorted list of collected node ids (parameters stripped) are identical.

<details><summary>The command, exactly as run</summary>

```bash
PYTHONDONTWRITEBYTECODE=1 ./venv/bin/python -m pytest -q -p no:cacheprovider -rs \
  tests/test_045_close_out_gaps.py::test_a_month_reads_the_day_after_it_for_the_last_days_yesterday_fields \
  tests/test_045_close_out_gaps.py::test_every_proposal_is_written_in_the_setup_language \
  tests/test_045_close_out_gaps.py::test_the_groups_are_defined_for_the_model_with_the_two_day_theme_rule \
  tests/test_hashi_instructions_schema.py::test_replace_section_present_in_tomo_producer \
  tests/test_hashi_instructions_schema.py::test_replace_section_validates_against_both_schemas \
  tests/test_inbox_triage_review_skip.py::TestCallCountersUnchanged::test_discover_counters_match_a_run_without_the_review_documents \
  tests/test_inbox_triage_review_skip.py::TestGetDocTypeReviewRule::test_frontmatter_doc_type_still_wins \
  tests/test_inbox_triage_review_skip.py::TestGetDocTypeReviewRule::test_month_review_stem_maps_to_review \
  tests/test_inbox_triage_review_skip.py::TestGetDocTypeReviewRule::test_only_the_space_suffix_counts \
  tests/test_inbox_triage_review_skip.py::TestGetDocTypeReviewRule::test_renamed_review_stem_has_no_doc_type \
  tests/test_inbox_triage_review_skip.py::TestGetDocTypeReviewRule::test_week_review_stem_maps_to_review \
  tests/test_inbox_triage_review_skip.py::TestReviewDocumentIsSkipped::test_approved_review_is_skipped_silently \
  tests/test_inbox_triage_review_skip.py::TestReviewDocumentIsSkipped::test_pending_approval_review_is_skipped_silently \
  tests/test_inbox_triage_review_skip.py::TestReviewDocumentIsSkipped::test_pending_approval_review_with_full_frontmatter_is_skipped \
  tests/test_inbox_triage_review_skip.py::TestReviewDocumentIsSkipped::test_review_document_does_not_change_the_action \
  tests/test_inbox_triage_review_skip.py::TestRuleBoundaries::test_periodic_note_pending_move_is_not_a_new_source \
  tests/test_inbox_triage_review_skip.py::TestRuleBoundaries::test_renamed_stamped_review_gives_unknown_doc_type_warning_only \
  tests/test_inbox_triage_review_skip.py::TestRuleBoundaries::test_user_book_review_without_tomo_block_is_a_new_item \
  tests/test_instruction_render_section_actions.py::test_a_backtick_in_the_anchor_does_not_break_the_line \
  tests/test_instruction_render_section_actions.py::test_every_section_action_keeps_the_peer_checkbox_format \
  tests/test_instruction_render_section_actions.py::test_fence_outgrows_the_longest_backtick_run \
  tests/test_instruction_render_section_actions.py::test_fenced_content_keeps_a_line_separator_inside_a_line \
  tests/test_instruction_render_section_actions.py::test_fenced_content_keeps_a_trailing_blank_line \
  tests/test_instruction_render_section_actions.py::test_insert_before_names_the_anchor_heading \
  tests/test_instruction_render_section_actions.py::test_insert_content_is_fenced_not_quoted \
  tests/test_instruction_render_section_actions.py::test_insert_inside_names_the_anchor_heading \
  tests/test_instruction_render_section_actions.py::test_insert_keeps_target_and_anchor_lines \
  tests/test_instruction_render_section_actions.py::test_replace_content_is_fenced_not_quoted \
  tests/test_instruction_render_section_actions.py::test_replace_section_has_its_own_heading \
  tests/test_instruction_render_section_actions.py::test_replace_section_says_what_is_discarded_and_what_stays \
  tests/test_kado_client_attempts.py::test_retry_wait_s_honours_retry_after_on_429_and_backoff_on_503 \
  tests/test_kado_client_attempts.py::test_wait_counters_accumulate_across_calls_and_kinds \
  tests/test_kado_client_listnotes.py::test_list_notes_filter_reaches_the_wire_unchanged \
  tests/test_kado_client_listnotes.py::test_list_notes_passes_filter_through_on_every_cursor_page \
  tests/test_kado_client_retry.py::test_429_exhausted_raises_rate_limit_error_with_status \
  tests/test_kado_client_retry.py::test_a_429_that_succeeds_on_retry_does_not_raise_rate_limit_error \
  tests/test_period.py::test_2025_12_29_belongs_to_week_1_of_2026 \
  tests/test_period.py::test_2025_has_no_week_53 \
  tests/test_period.py::test_2026_12_31_is_week_53_of_2026_running_into_january \
  tests/test_period.py::test_2027_01_01_belongs_to_week_53_of_2026 \
  tests/test_period.py::test_a_full_month_name_is_that_month \
  tests/test_period.py::test_a_full_week_name_is_that_week \
  tests/test_period.py::test_a_future_period_is_refused_naming_the_last_finished_one \
  tests/test_period.py::test_a_month_without_a_year_is_the_most_recent_finished_one \
  tests/test_period.py::test_a_period_is_finished_only_when_its_end_lies_before_today \
  tests/test_period.py::test_a_week_without_a_year_is_the_most_recent_finished_one \
  tests/test_period.py::test_a_year_outside_the_supported_range_is_an_invalid_period \
  tests/test_period.py::test_an_at_note_is_matched_against_the_configured_formats \
  tests/test_period.py::test_an_at_note_that_fits_neither_format_is_not_a_periodic_note \
  tests/test_period.py::test_an_at_note_uses_the_configured_name_formats \
  tests/test_period.py::test_an_at_note_with_a_year_outside_the_supported_range_is_not_a_periodic_note \
  tests/test_period.py::test_an_invalid_period_names_what_was_expected_and_one_example \
  tests/test_period.py::test_an_unfinished_period_is_refused_naming_the_last_finished_one \
  tests/test_period.py::test_anything_else_is_an_unknown_argument \
  tests/test_period.py::test_default_week_follows_the_configured_rule \
  tests/test_period.py::test_iso_rule_equals_isocalendar_for_every_day_2020_to_2030 \
  tests/test_period.py::test_last_finished_period_of_each_kind \
  tests/test_period.py::test_march_2026_is_the_calendar_month \
  tests/test_period.py::test_march_2026_overlaps_iso_weeks_9_to_14 \
  tests/test_period.py::test_month_word_is_the_last_finished_month \
  tests/test_period.py::test_no_argument_is_the_last_finished_week \
  tests/test_period.py::test_overlapping_weeks_follow_the_configured_rule \
  tests/test_period.py::test_parse_name_gggg_follows_the_rule_and_GGGG_stays_iso \
  tests/test_period.py::test_parse_name_returns_none_for_a_name_that_does_not_fit \
  tests/test_period.py::test_parse_name_round_trips_each_format \
  tests/test_period.py::test_render_iso_week_format \
  tests/test_period.py::test_render_rule_week_format_follows_the_configured_rule \
  tests/test_period.py::test_setup_word_asks_for_the_setup \
  tests/test_period.py::test_sunday_first_one_day_rule_puts_2026_03_01_in_week_10 \
  tests/test_period.py::test_the_kind_words_are_case_insensitive \
  tests/test_period.py::test_the_week_that_ends_today_is_not_finished \
  tests/test_period.py::test_week_53_belongs_to_the_old_week_year \
  tests/test_period.py::test_week_note_paths_are_flat_then_the_week_year_folder \
  tests/test_period.py::test_week_number_outside_the_year_is_refused \
  tests/test_period.py::test_week_one_starting_in_december_lives_in_the_new_week_year_folder \
  tests/test_review_config.py::test_current_setup_is_the_proposal_shape_none_or_the_pointers \
  tests/test_review_config.py::test_daily_path_fix_only_when_the_input_says_so \
  tests/test_review_config.py::test_inbox_path_refuses_empty_inbox_and_escapes \
  tests/test_review_config.py::test_inbox_path_refuses_unsafe_names \
  tests/test_review_config.py::test_month_input_writes_only_what_it_carries_and_null_removes \
  tests/test_review_config.py::test_place_level_refuses_a_review_heading_above_5_because_its_groups_would_exceed_6 \
  tests/test_review_config.py::test_place_level_rule \
  tests/test_review_config.py::test_request_dict_adds_the_first_and_last_day \
  tests/test_review_config.py::test_setup_missing_when_format_or_review_section_absent \
  tests/test_review_config.py::test_setup_place_level_finds_the_anchor_case_sensitively \
  tests/test_review_config.py::test_tracker_types_reads_all_three_lists_and_tolerates_junk \
  tests/test_review_config.py::test_week_input_maps_onto_config_paths_in_sdd_order \
  tests/test_review_day.py::test_a_bare_dash_value_passes_through_unchanged \
  tests/test_review_day.py::test_a_day_token_matches_on_digit_boundaries_only \
  tests/test_review_day.py::test_a_single_value_makes_content \
  tests/test_review_day.py::test_a_target_named_like_a_task_note_is_not_read_per_day \
  tests/test_review_day.py::test_a_tick_without_a_date_never_counts_as_done_in_the_period \
  tests/test_review_day.py::test_an_empty_configured_section_is_still_no_fallback \
  tests/test_review_day.py::test_an_other_day_section_in_a_linked_note_ends_at_a_thematic_break \
  tests/test_review_day.py::test_attribute_yesterday_drops_fields_of_the_day_before_the_period \
  tests/test_review_day.py::test_attribute_yesterday_moves_fields_to_the_day_before \
  tests/test_review_day.py::test_attribute_yesterday_skips_a_gap_day \
  tests/test_review_day.py::test_configured_sections_kept_in_setup_order_with_subsections \
  tests/test_review_day.py::test_dataview_blocks_and_inline_queries_are_dropped \
  tests/test_review_day.py::test_date_format_decides_what_same_day_means \
  tests/test_review_day.py::test_done_in_period_counts_by_tick_date_whichever_file_holds_it \
  tests/test_review_day.py::test_done_in_period_includes_the_first_and_the_last_day_of_the_period \
  tests/test_review_day.py::test_embed_in_skipped_section_is_not_collected \
  tests/test_review_day.py::test_fields_outside_kept_sections_are_not_parsed \
  tests/test_review_day.py::test_journal_read_with_earlier_years_subsections_dropped \
  tests/test_review_day.py::test_links_are_the_targets_of_the_kept_text \
  tests/test_review_day.py::test_missing_linked_note_is_a_problem_of_that_day_and_the_day_still_read \
  tests/test_review_day.py::test_next_day_tick_keeps_its_own_date \
  tests/test_review_day.py::test_one_configured_section_found_means_no_fallback \
  tests/test_review_day.py::test_plain_and_bold_fields_parsed_as_raw_strings \
  tests/test_review_day.py::test_plain_daily_with_a_title_heading_is_read_whole_under_text \
  tests/test_review_day.py::test_plain_daily_with_only_unconfigured_headings_is_read_whole \
  tests/test_review_day.py::test_plain_text_daily_still_yields_content \
  tests/test_review_day.py::test_planner_heading_naming_other_days_is_dropped_schedule_kept \
  tests/test_review_day.py::test_prose_after_a_thematic_break_stays_under_text_in_the_fallback \
  tests/test_review_day.py::test_quoth_and_dynbedded_blocks_are_dropped_from_the_kept_text \
  tests/test_review_day.py::test_quoth_embed_under_dayplanner_heading_is_collected_and_read \
  tests/test_review_day.py::test_read_day_then_attribute_feeds_review_habits_as_is \
  tests/test_review_day.py::test_skeleton_only_daily_has_no_content \
  tests/test_review_day.py::test_skip_section_inside_a_whole_read_daily_stays_excluded \
  tests/test_review_day.py::test_task_note_open_tasks_are_open_today \
  tests/test_review_day.py::test_tasks_from_daily_and_linked_notes_carry_their_done_date_and_source \
  tests/test_review_day.py::test_tomorrows_planner_link_is_ignored \
  tests/test_review_day.py::test_two_dailies_for_one_day_are_both_read \
  tests/test_review_day.py::test_unconfigured_and_skipped_sections_are_absent \
  tests/test_review_day.py::test_yesterday_fields_are_separated_from_todays \
  tests/test_review_deliver.py::test_cli_each_notice_is_shown_without_refusing_and_deliver_lands \
  tests/test_review_deliver.py::test_cli_exit_codes_and_a_bare_class_name_on_stderr \
  tests/test_review_deliver.py::test_cli_notices_are_shown_and_delivery_proceeds \
  tests/test_review_deliver.py::test_cli_preview_gate_problems \
  tests/test_review_deliver.py::test_cli_preview_new_note_names_the_templater_hint \
  tests/test_review_deliver.py::test_cli_preview_place_problems_name_the_notes_headings \
  tests/test_review_deliver.py::test_cli_preview_returns_mode_target_place_section_and_counts \
  tests/test_review_deliver.py::test_cli_preview_user_heading_collision_and_set_exists \
  tests/test_review_deliver.py::test_cli_status_and_start_agree_on_delivered_move_refused_applied_and_withdrawn \
  tests/test_review_deliver.py::test_deliver_doc_changed_stops_at_doc_mark_and_resumes_after_saving \
  tests/test_review_deliver.py::test_deliver_doc_mark_refusal_is_doc_changed_only_for_kados_conflict_code \
  tests/test_review_deliver.py::test_deliver_interrupted_at_any_step_resumes_without_duplicates \
  tests/test_review_deliver.py::test_deliver_mark_is_idempotent_when_the_write_landed_unrecorded \
  tests/test_review_deliver.py::test_deliver_new_note_writes_the_note_first_and_moves_it \
  tests/test_review_deliver.py::test_deliver_place_anchor_uses_the_users_heading \
  tests/test_review_deliver.py::test_deliver_refuses_a_second_set_for_the_same_stem \
  tests/test_review_deliver.py::test_deliver_refuses_an_unapproved_document_and_writes_nothing \
  tests/test_review_deliver.py::test_deliver_refuses_each_refusing_problem_and_writes_nothing \
  tests/test_review_deliver.py::test_deliver_switches_from_new_note_to_insert_when_the_target_appeared \
  tests/test_review_deliver.py::test_deliver_writes_the_set_in_order_and_marks_the_document_last \
  tests/test_review_deliver.py::test_drop_after_a_partial_delivery_withdraws_the_set \
  tests/test_review_deliver.py::test_drop_after_the_note_step_began_withdraws_and_names_the_note \
  tests/test_review_deliver.py::test_drop_before_any_step_removes_only_the_stage \
  tests/test_review_deliver.py::test_drop_refuses_a_set_hashi_already_applied_and_writes_nothing \
  tests/test_review_deliver.py::test_drop_set_changed_under_the_guard_is_stopped_and_resumable \
  tests/test_review_deliver.py::test_drop_that_failed_after_the_set_write_is_listed_again_and_a_second_drop_completes_it \
  tests/test_review_deliver_report.py::test_a_fresh_delivery_reports_the_plan_it_recorded \
  tests/test_review_deliver_report.py::test_doc_changed_names_why_kado_refused_the_mark \
  tests/test_review_deliver_report.py::test_resume_reports_the_recorded_plan_not_the_replan \
  tests/test_review_deliver_report.py::test_resume_target_appeared_compares_pass1_with_the_recorded_mode \
  tests/test_review_deliver_report.py::test_the_plan_is_recorded_with_the_first_in_flight_mark \
  tests/test_review_deliver_report.py::test_the_record_never_holds_a_heading_of_the_notes_own \
  tests/test_review_deliver_rerun.py::test_deliver_over_an_applied_set_that_hashi_rewrote_meanwhile_stops_resumably \
  tests/test_review_deliver_rerun.py::test_deliver_refuses_a_set_that_is_not_fully_applied \
  tests/test_review_deliver_rerun.py::test_deliver_writes_the_new_set_over_a_fully_applied_one \
  tests/test_review_deliver_rerun.py::test_resume_after_the_set_json_landed_overwrites_the_old_md_and_keeps_its_own_set \
  tests/test_review_doc.py::test_a_bare_weekly_stem_resolves_for_weekly_only \
  tests/test_review_doc.py::test_a_search_hit_with_another_basename_is_not_the_moved_target \
  tests/test_review_doc.py::test_a_theme_naming_fewer_than_two_days_is_rejected \
  tests/test_review_doc.py::test_a_wiki_link_shaped_daily_as_the_only_source_resolves_through_the_stem_fallback \
  tests/test_review_doc.py::test_a_wiki_link_shaped_weekly_as_the_only_source_resolves_through_the_stem_fallback \
  tests/test_review_doc.py::test_approved_unticked_and_frontmatter_schema_valid \
  tests/test_review_doc.py::test_doc_path_comes_from_inbox_path \
  tests/test_review_doc.py::test_empty_groups_show_one_nothing_found_line_also_growth_with_kado_none \
  tests/test_review_doc.py::test_every_tomo_item_ends_with_a_unique_id_and_text_cannot_forge_one \
  tests/test_review_doc.py::test_existing_non_tomo_document_is_doc_name_taken \
  tests/test_review_doc.py::test_existing_tomo_review_is_review_exists_and_never_overwritten \
  tests/test_review_doc.py::test_forged_sources_and_structural_lines_cannot_reach_the_document \
  tests/test_review_doc.py::test_groups_in_order_with_nothing_found_lines_and_ids \
  tests/test_review_doc.py::test_habits_come_from_the_tracker_values_and_are_absent_without_them \
  tests/test_review_doc.py::test_info_callout_names_target_existence_place_and_not_read \
  tests/test_review_doc.py::test_item_without_a_source_inside_the_period_is_rejected_and_listed \
  tests/test_review_doc.py::test_labels_de_en_with_en_fallback \
  tests/test_review_doc.py::test_links_come_only_from_resolved_sources_as_the_listed_stem \
  tests/test_review_doc.py::test_month_only_groups_only_for_a_month_with_weekly_notes \
  tests/test_review_doc.py::test_pass1_counts_in_meta_and_content_files_deleted \
  tests/test_review_doc.py::test_proposal_text_never_reaches_stdout_or_stderr \
  tests/test_review_doc.py::test_schema_refuses_habits_own_sections_and_items_without_sources \
  tests/test_review_doc.py::test_sources_render_as_links_of_the_note_stem \
  tests/test_review_doc.py::test_weekly_only_needs_a_weekly_note_and_month_groups_need_a_month_with_weeklies \
  tests/test_review_doc.py::test_year_subfolder_target_counts_as_existing \
  tests/test_review_doc_parse.py::test_a_low_entropy_habit_line_is_not_recoverable_from_meta \
  tests/test_review_doc_parse.py::test_a_tasks_done_marker_after_approved_is_still_the_gate \
  tests/test_review_doc_parse.py::test_a_ticked_line_without_id_is_a_user_item_and_a_copied_id_too \
  tests/test_review_doc_parse.py::test_a_tomo_item_rewritten_without_its_links_is_kept_and_edited \
  tests/test_review_doc_parse.py::test_an_uppercase_x_ticks_tomo_and_user_items \
  tests/test_review_doc_parse.py::test_approved_review_record_keeps_only_kept_items_in_rendering_order \
  tests/test_review_doc_parse.py::test_approved_ticked_unticked_or_missing \
  tests/test_review_doc_parse.py::test_edited_text_is_kept_verbatim_with_continuation_lines_and_escapes \
  tests/test_review_doc_parse.py::test_every_id_on_the_line_is_stripped_and_the_first_names_the_item \
  tests/test_review_doc_parse.py::test_everything_unticked_is_nothing_to_deliver \
  tests/test_review_doc_parse.py::test_only_column_zero_lines_are_structure \
  tests/test_review_doc_parse.py::test_parse_reads_the_document_prints_counts_only_and_writes_no_file \
  tests/test_review_doc_parse.py::test_rendered_document_parses_back_unapproved_with_every_item_kept \
  tests/test_review_doc_parse.py::test_replace_abort_deletes_the_content_files_and_leaves_document_and_meta \
  tests/test_review_doc_parse.py::test_replace_confirm_on_a_non_tomo_document_is_still_doc_name_taken \
  tests/test_review_doc_parse.py::test_replace_confirm_writes_over_tomos_document_resets_meta_and_deletes_stage_files \
  tests/test_review_doc_parse.py::test_replace_without_confirm_needs_confirm_and_names_the_document \
  tests/test_review_doc_parse.py::test_the_first_column_zero_approved_line_decides \
  tests/test_review_doc_parse.py::test_the_nothing_found_line_is_never_an_item \
  tests/test_review_doc_parse.py::test_tomo_items_counted_by_id_kept_unticked_deleted \
  tests/test_review_doc_parse.py::test_write_records_only_link_stem_lists_per_tomo_item \
  tests/test_review_e2e.py::test_abort_after_pass_2_by_not_applying_changes_nothing_outside_the_inbox \
  tests/test_review_e2e.py::test_empty_period_reports_and_writes_nothing \
  tests/test_review_e2e.py::test_every_write_attempted_so_far_was_under_the_inbox_prefix \
  tests/test_review_e2e.py::test_month_setup_then_new_note_targets_the_monthly_folder \
  tests/test_review_e2e.py::test_rerun_replaces_the_section_instead_of_adding_a_second \
  tests/test_review_e2e.py::test_setup_abort_saves_nothing_and_writes_nothing \
  tests/test_review_e2e.py::test_target_created_between_the_passes_turns_new_note_into_insert \
  tests/test_review_e2e.py::test_target_moved_to_another_folder_is_found_by_name_and_targeted_there \
  tests/test_review_e2e.py::test_week_from_first_start_through_hashi_apply \
  tests/test_review_e2e_edges.py::test_ambiguous_weekly_notes_ask_the_week_question_once_and_every_rerun_keeps_the_answer \
  tests/test_review_e2e_edges.py::test_approved_and_an_item_ticked_through_the_tasks_plugin_parse_preview_and_deliver_without_the_marker \
  tests/test_review_e2e_edges.py::test_bare_start_with_an_open_review_carries_no_request_before_or_after_its_delivery \
  tests/test_review_e2e_edges.py::test_deleted_approved_line_is_approved_line_missing_and_nothing_is_delivered \
  tests/test_review_e2e_edges.py::test_every_write_attempted_so_far_was_under_the_inbox_prefix \
  tests/test_review_e2e_edges.py::test_everything_unticked_is_nothing_to_deliver_and_nothing_is_delivered \
  tests/test_review_e2e_edges.py::test_first_setup_with_no_template_keeps_that_answer_and_the_typed_anchor_on_every_rerun \
  tests/test_review_e2e_edges.py::test_first_setup_without_a_template_mapping_asks_for_the_template_and_saves_it \
  tests/test_review_e2e_edges.py::test_renamed_review_document_is_listed_by_its_period_and_parse_reports_not_found \
  tests/test_review_e2e_edges.py::test_setup_rerun_shows_the_saved_setup_and_a_confirmed_correction_replaces_it \
  tests/test_review_e2e_edges.py::test_sparse_period_reads_its_few_dailies_and_writes_the_document \
  tests/test_review_e2e_failures.py::test_delivery_failure_at_each_step_is_offered_as_failed_delivery_and_resumes_once \
  tests/test_review_e2e_failures.py::test_drop_after_a_partial_delivery_leaves_only_a_withdrawn_set \
  tests/test_review_e2e_failures.py::test_every_write_attempted_so_far_was_under_the_inbox_prefix \
  tests/test_review_e2e_failures.py::test_half_withdrawn_drop_is_listed_again_resume_refuses_and_a_second_drop_completes \
  tests/test_review_e2e_failures.py::test_month_with_weekly_notes_new_note_waits_in_the_inbox_until_hashi_moves_it \
  tests/test_review_e2e_failures.py::test_set_deleted_after_apply_is_not_listed_and_the_period_starts_over \
  tests/test_review_habits.py::test_a_day_outside_the_period_is_ignored \
  tests/test_review_habits.py::test_boolean_counts_days_true_over_days_with_value \
  tests/test_review_habits.py::test_boolean_dash_is_a_placeholder_listed_as_missing_not_false \
  tests/test_review_habits.py::test_boolean_number_is_unreadable_not_false \
  tests/test_review_habits.py::test_dash_is_missing_not_unreadable_for_every_type \
  tests/test_review_habits.py::test_duration_average_is_arithmetic_not_circular \
  tests/test_review_habits.py::test_duration_averaged_in_minutes_and_rendered_back \
  tests/test_review_habits.py::test_empty_value_is_missing_not_unreadable \
  tests/test_review_habits.py::test_english_line_for_a_count_names_missing_and_unreadable \
  tests/test_review_habits.py::test_german_count_line_with_gaps \
  tests/test_review_habits.py::test_german_line_uses_german_labels_and_decimal_comma \
  tests/test_review_habits.py::test_huge_digit_runs_are_unreadable_never_a_raise \
  tests/test_review_habits.py::test_integer_average_over_days_with_value \
  tests/test_review_habits.py::test_no_clear_average_in_german \
  tests/test_review_habits.py::test_no_trackers_gives_empty_result \
  tests/test_review_habits.py::test_no_values_at_all_gives_empty_result \
  tests/test_review_habits.py::test_only_dashes_give_no_item_for_every_type \
  tests/test_review_habits.py::test_only_unreadable_values_give_no_item \
  tests/test_review_habits.py::test_other_language_falls_back_to_english \
  tests/test_review_habits.py::test_text_trackers_are_skipped \
  tests/test_review_habits.py::test_time_average_is_circular_on_the_clock \
  tests/test_review_habits.py::test_time_averaged_in_minutes_since_midnight_rendered_hh_mm \
  tests/test_review_habits.py::test_tracker_defs_reads_the_three_lists_in_order \
  tests/test_review_habits.py::test_tracker_defs_without_trackers_is_empty \
  tests/test_review_habits.py::test_tracker_without_a_value_on_any_day_is_absent \
  tests/test_review_habits.py::test_unreadable_value_is_named_by_the_date_it_is_listed_under \
  tests/test_review_habits.py::test_unrun_templater_tag_is_unreadable_for_every_type \
  tests/test_review_habits.py::test_word_for_a_number_is_unreadable_never_zero \
  tests/test_review_habits.py::test_yesterday_field_value_counts_for_the_day_it_is_listed_under \
  tests/test_review_instructions.py::test_actions_a_configured_anchor_matches_with_or_without_closing_hashes_and_emits_hashis_text \
  tests/test_review_instructions.py::test_actions_a_marker_of_another_period_does_not_count \
  tests/test_review_instructions.py::test_actions_a_marker_under_a_heading_an_earlier_user_heading_shadows_is_a_collision \
  tests/test_review_instructions.py::test_actions_a_marker_with_no_heading_above_it_is_place_missing \
  tests/test_review_instructions.py::test_actions_a_missing_place_names_the_notes_headings \
  tests/test_review_instructions.py::test_actions_a_review_heading_above_level_5_is_place_too_deep \
  tests/test_review_instructions.py::test_actions_a_target_found_by_name_elsewhere_is_the_target \
  tests/test_review_instructions.py::test_actions_a_user_heading_named_like_the_review_is_never_replaced \
  tests/test_review_instructions.py::test_actions_a_user_item_lands_like_tomos_and_an_unknown_group_does_not \
  tests/test_review_instructions.py::test_actions_an_indented_marker_copy_is_not_the_marker \
  tests/test_review_instructions.py::test_actions_an_unapproved_gateless_or_empty_review_emits_nothing \
  tests/test_review_instructions.py::test_actions_every_set_validates_against_both_schemas \
  tests/test_review_instructions.py::test_actions_fences_toggle_as_hashi_toggles_them \
  tests/test_review_instructions.py::test_actions_insert_before_the_anchor_when_the_target_has_no_marker \
  tests/test_review_instructions.py::test_actions_insert_inside_lands_one_level_deeper_and_never_after \
  tests/test_review_instructions.py::test_actions_new_note_from_a_raw_templater_template_sets_the_hint \
  tests/test_review_instructions.py::test_actions_new_note_from_the_template_variant \
  tests/test_review_instructions.py::test_actions_new_note_inside_appends_at_the_end_of_the_anchors_section \
  tests/test_review_instructions.py::test_actions_new_note_is_stamped_rendered_note_pending_move_with_a_stable_block \
  tests/test_review_instructions.py::test_actions_new_note_keeps_the_templates_final_newline_byte_for_byte \
  tests/test_review_instructions.py::test_actions_new_note_plain_when_there_is_no_template \
  tests/test_review_instructions.py::test_actions_new_note_template_with_a_tomo_block_falls_back_to_the_plain_note \
  tests/test_review_instructions.py::test_actions_new_note_template_with_an_unclosed_frontmatter_fence_falls_back_to_the_plain_note \
  tests/test_review_instructions.py::test_actions_new_note_template_without_the_anchor_is_place_missing \
  tests/test_review_instructions.py::test_actions_new_note_with_a_vanished_variant_falls_back_to_raw \
  tests/test_review_instructions.py::test_actions_nothing_anywhere_means_a_new_note_at_the_first_candidate \
  tests/test_review_instructions.py::test_actions_only_kept_items_land_and_empty_groups_leave_no_heading \
  tests/test_review_instructions.py::test_actions_only_unlanded_items_is_nothing_to_deliver_and_unlanded_items \
  tests/test_review_instructions.py::test_actions_own_sections_are_never_targeted \
  tests/test_review_instructions.py::test_actions_replace_anchors_the_heading_as_hashi_reads_it_closing_hashes_kept \
  tests/test_review_instructions.py::test_actions_rerun_finds_the_marker_under_a_renamed_heading \
  tests/test_review_instructions.py::test_actions_rerun_replaces_the_section_above_the_marker_and_hashi_sees_it_as_landed \
  tests/test_review_instructions.py::test_actions_the_flat_folder_wins_over_the_year_subfolder_and_the_duplicate_is_named \
  tests/test_review_instructions.py::test_hashi_mirror_a_bom_after_the_hashes_is_whitespace_and_trimmed \
  tests/test_review_instructions.py::test_hashi_mirror_a_crlf_target_has_no_heading_to_hashi_and_is_place_missing \
  tests/test_review_instructions.py::test_hashi_mirror_a_heading_line_holding_a_js_line_terminator_is_no_heading \
  tests/test_review_instructions.py::test_hashi_mirror_characters_outside_ecmascripts_set_are_text \
  tests/test_review_pacer.py::test_a_read_that_outlasts_the_retries_returns_none_and_is_recovered_at_the_end \
  tests/test_review_pacer.py::test_connection_auth_and_not_found_errors_propagate_and_restore \
  tests/test_review_pacer.py::test_connection_error_in_the_end_pass_propagates_and_restores \
  tests/test_review_pacer.py::test_fake_accounting_matches_the_real_client_on_one_429_scenario \
  tests/test_review_pacer.py::test_finish_keeps_the_widest_interval_until_close_restores_the_previous_value \
  tests/test_review_pacer.py::test_only_what_fails_in_the_end_pass_is_not_read \
  tests/test_review_pacer.py::test_pacer_starts_at_0_3_s_and_returns_the_value \
  tests/test_review_pacer.py::test_spacing_doubles_after_each_call_that_needed_retries_up_to_2_s \
  tests/test_review_pacer.py::test_summary_reports_calls_retried_waited_not_read_and_the_advice \
  tests/test_review_pacer.py::test_summary_without_retries_has_no_advice \
  tests/test_review_pacer.py::test_the_end_pass_retries_a_failed_path_exactly_once \
  tests/test_review_pacer.py::test_widened_spacing_is_what_the_following_sends_wait \
  tests/test_review_period.py::test_a_created_query_that_still_fails_is_not_read_and_not_kado_none \
  tests/test_review_period.py::test_a_link_stem_is_resolved_by_name_once_and_read_at_its_vault_path \
  tests/test_review_period.py::test_a_missing_task_note_is_reported_and_nothing_else_changes \
  tests/test_review_period.py::test_a_stem_that_resolves_to_nothing_is_reported_missing_not_failed \
  tests/test_review_period.py::test_a_task_note_is_read_once_and_its_tasks_land_by_done_date \
  tests/test_review_period.py::test_a_weekly_note_flat_and_in_the_year_folder_is_read_twice_and_marked_duplicate \
  tests/test_review_period.py::test_absent_day_after_leaves_the_last_days_value_missing \
  tests/test_review_period.py::test_dailies_found_flat_and_in_year_folder \
  tests/test_review_period.py::test_day_after_period_is_read_for_its_yesterday_fields_only \
  tests/test_review_period.py::test_day_blocks_keyed_by_date_end_at_their_level_and_drop_out_of_month_and_skipped_text \
  tests/test_review_period.py::test_empty_daily_listing_is_kado_empty_with_the_access_hint \
  tests/test_review_period.py::test_empty_growth_results_are_reported_as_kado_returned_none \
  tests/test_review_period.py::test_empty_weekly_listing_is_kado_empty_not_none_found \
  tests/test_review_period.py::test_growth_lists_created_notes_with_links_mocs_changed_and_mocs_linked_across_pages \
  tests/test_review_period.py::test_growth_without_moc_folders_queries_no_mocs \
  tests/test_review_period.py::test_month_resolves_weekly_notes_flat_and_in_the_week_year_folder \
  tests/test_review_period.py::test_month_without_weekly_config_says_not_configured_and_lists_nothing \
  tests/test_review_period.py::test_month_without_weekly_notes_says_none_found \
  tests/test_review_period.py::test_only_in_weekly_links_and_dailies_not_in_weekly_are_computed \
  tests/test_review_period.py::test_period_bounds_are_inclusive_local_days_in_ms \
  tests/test_review_period.py::test_period_bounds_follow_the_local_clock_across_a_dst_change \
  tests/test_review_period.py::test_real_review_day_reads_a_week_through_the_period_reader \
  tests/test_review_period.py::test_two_dailies_for_one_date_are_both_read_and_reported_duplicate \
  tests/test_review_period.py::test_week_level_text_is_tagged_with_week_and_overlap \
  tests/test_review_period.py::test_week_notes_are_not_read_for_a_week_review \
  tests/test_review_period_end_pass.py::test_a_connection_error_propagates \
  tests/test_review_period_end_pass.py::test_a_daily_that_fails_after_a_recovered_listing_is_still_marked_failed \
  tests/test_review_period_end_pass.py::test_a_daily_that_still_fails_at_the_end_is_not_read_and_marked_failed \
  tests/test_review_period_end_pass.py::test_a_link_stem_spelled_like_a_note_path_already_read_is_looked_up_not_served_that_note \
  tests/test_review_period_end_pass.py::test_a_linked_note_that_still_fails_is_marked_failed \
  tests/test_review_period_end_pass.py::test_a_rate_limited_daily_is_recovered_by_the_end_pass \
  tests/test_review_period_end_pass.py::test_a_rate_limited_daily_listing_recovered_by_the_end_pass_reads_the_whole_period \
  tests/test_review_period_end_pass.py::test_a_rate_limited_linked_note_is_recovered_without_a_second_daily_read \
  tests/test_review_period_end_pass.py::test_a_rate_limited_name_lookup_is_recovered_by_the_end_pass \
  tests/test_review_period_end_pass.py::test_a_weekly_note_that_fails_after_a_recovered_weekly_listing_is_in_the_one_not_read_list \
  tests/test_review_period_end_pass.py::test_the_created_query_and_a_moc_listing_over_the_same_prefix_are_two_reads \
  tests/test_review_privacy.py::test_a_forced_exception_leaves_only_its_class_name_on_stderr \
  tests/test_review_privacy.py::test_a_readable_tracker_value_stays_in_read_json_and_the_document \
  tests/test_review_privacy.py::test_bad_invocations_echo_no_marker \
  tests/test_review_privacy.py::test_every_marker_reached_the_scripts \
  tests/test_review_privacy.py::test_every_named_field_carried_its_marker_once \
  tests/test_review_privacy.py::test_every_script_and_every_subcommand_ran_in_the_walk \
  tests/test_review_privacy.py::test_named_fields_carry_only_their_own_kinds \
  tests/test_review_privacy.py::test_no_marker_in_stdout_outside_the_named_fields \
  tests/test_review_privacy.py::test_no_marker_in_tomos_working_files_after_any_step \
  tests/test_review_privacy.py::test_no_marker_on_stderr_of_any_script \
  tests/test_review_privacy.py::test_read_and_proposal_files_are_gone_after_write_and_abort_and_kept_after_a_refusal \
  tests/test_review_privacy_docs.py::test_metadata_only_is_scoped_to_tomos_own_records \
  tests/test_review_privacy_docs.py::test_names_every_place_read_content_rests \
  tests/test_review_privacy_docs.py::test_read_json_and_proposals_json_are_deleted_on_write_or_abort \
  tests/test_review_privacy_docs.py::test_read_json_is_named_as_left_behind_by_an_unfinished_session \
  tests/test_review_privacy_docs.py::test_removal_is_the_users_choice_and_protection_is_recommended \
  tests/test_review_privacy_docs.py::test_removing_the_delivered_inbox_files_is_the_users_job \
  tests/test_review_privacy_docs.py::test_setup_guide_links_to_the_privacy_section \
  tests/test_review_read.py::test_a_bad_invocation_exits_2 \
  tests/test_review_read.py::test_a_client_that_cannot_be_built_is_kado_unreachable \
  tests/test_review_read.py::test_a_missing_setup_stops_without_a_call \
  tests/test_review_read.py::test_a_month_run_reports_the_weekly_notes_and_stays_within_the_call_budget \
  tests/test_review_read.py::test_a_note_that_still_fails_in_the_end_pass_is_not_read_and_marked_failed \
  tests/test_review_read.py::test_a_refused_key_stops_the_run_as_kado_auth \
  tests/test_review_read.py::test_a_stopped_output_never_carries_nothing_to_review \
  tests/test_review_read.py::test_a_week_run_prints_the_per_day_report_and_writes_read_json \
  tests/test_review_read.py::test_a_week_without_dailies_in_a_folder_that_holds_other_dates_gets_no_access_hint \
  tests/test_review_read.py::test_an_empty_daily_listing_is_nothing_to_review_and_kado_empty \
  tests/test_review_read.py::test_an_unexpected_exception_prints_only_the_class_name \
  tests/test_review_read.py::test_injected_429s_give_retried_waited_and_the_advice \
  tests/test_review_read.py::test_kado_unreachable_stops_the_run_and_writes_nothing \
  tests/test_review_read.py::test_no_daily_with_content_is_nothing_to_review_without_the_access_hint_and_no_file \
  tests/test_review_read.py::test_one_client_per_run_built_once_before_the_first_call_under_one_pacer \
  tests/test_review_read.py::test_reads_after_a_listing_recovered_by_the_end_pass_are_sent_at_the_widest_interval \
  tests/test_review_read.py::test_the_daily_listing_still_not_read_after_the_end_pass_stops_the_run_and_writes_nothing \
  tests/test_review_read.py::test_the_period_is_resolved_under_the_configured_week_rule \
  tests/test_review_session.py::test_match_configured_rule_wins_over_the_inference \
  tests/test_review_session.py::test_match_configured_values_win_over_the_guess \
  tests/test_review_session.py::test_match_contradicting_starts_are_ambiguous \
  tests/test_review_session.py::test_match_daily_path_fix_only_when_the_other_spelling_exists \
  tests/test_review_session.py::test_match_empty_listing_is_kado_none_never_no_notes \
  tests/test_review_session.py::test_match_folder_without_notes_is_default_iso_and_found \
  tests/test_review_session.py::test_match_given_format_wins_and_its_problems_are_listed \
  tests/test_review_session.py::test_match_infers_a_sunday_rule_from_sunday_starts \
  tests/test_review_session.py::test_match_infers_iso_from_journal_start_dates \
  tests/test_review_session.py::test_match_infers_the_rule_from_day_heading_links \
  tests/test_review_session.py::test_match_keeps_two_notes_with_the_same_stem \
  tests/test_review_session.py::test_match_month_lists_names_and_needs_no_week_rule \
  tests/test_review_session.py::test_match_never_requests_the_plugin_config \
  tests/test_review_session.py::test_match_notes_without_dates_are_ambiguous \
  tests/test_review_session.py::test_match_parsing_names_are_notes_to_compare_even_when_unmatched \
  tests/test_review_session.py::test_match_partial_day_headings_do_not_count_as_dates \
  tests/test_review_session.py::test_match_proposes_place_and_daily_sections_from_the_templates \
  tests/test_review_session.py::test_match_sunday_flags_relist_the_iso_notes_as_unmatched \
  tests/test_review_session.py::test_match_template_kinds \
  tests/test_review_session.py::test_match_unsafe_format_stops_before_any_kado_call \
  tests/test_review_session.py::test_match_week_1_note_pins_min_days \
  tests/test_review_session.py::test_match_with_the_week_flags_reports_given_so_the_question_is_asked_once \
  tests/test_review_session.py::test_match_without_a_template_leaves_the_anchor_open \
  tests/test_review_session.py::test_setup_input_invalid_returns_pointers_and_writes_nothing \
  tests/test_review_session.py::test_setup_input_writes_a_schema_valid_writer_input \
  tests/test_review_session.py::test_start_a_kind_word_with_a_listed_review_keeps_the_request \
  tests/test_review_session.py::test_start_a_named_period_with_a_listed_review_keeps_the_request \
  tests/test_review_session.py::test_start_a_refused_set_probe_stops_and_is_never_read_as_absent \
  tests/test_review_session.py::test_start_at_note_resolves_under_the_configured_names \
  tests/test_review_session.py::test_start_at_note_that_fits_no_name_format_is_not_periodic_note \
  tests/test_review_session.py::test_start_bare_setup_and_errors_are_not_withheld \
  tests/test_review_session.py::test_start_bare_with_a_listed_review_withholds_the_request \
  tests/test_review_session.py::test_start_bare_withholds_the_request_for_every_listed_state \
  tests/test_review_session.py::test_start_bare_without_a_listed_review_is_the_default_week \
  tests/test_review_session.py::test_start_every_argument_form_yields_the_request \
  tests/test_review_session.py::test_start_every_bad_argument_yields_kind_expectation_and_example \
  tests/test_review_session.py::test_start_lists_the_open_reviews_by_period_with_their_state \
  tests/test_review_session.py::test_start_month_is_the_last_finished_month \
  tests/test_review_session.py::test_start_no_argument_is_the_last_finished_week_under_the_configured_rule \
  tests/test_review_session.py::test_start_orders_the_open_reviews_under_the_configured_week_format_and_rule \
  tests/test_review_session.py::test_start_probes_the_set_json_of_approved_documents_and_lists_a_delivered_review_as_delivered \
  tests/test_review_session.py::test_start_reports_applied_once_and_the_second_start_does_not_list_it \
  tests/test_review_session.py::test_start_reports_the_missing_setup_per_kind \
  tests/test_review_session.py::test_start_setup_returns_the_current_values \
  tests/test_review_session.py::test_start_week_53_and_year_spanning_weeks_resolve_under_the_rule \
  tests/test_review_session.py::test_unexpected_exception_exits_1_with_the_class_name_only \
  tests/test_review_session_templates.py::test_a_fence_that_comes_only_from_a_templater_include_is_no_block \
  tests/test_review_session_templates.py::test_a_mapping_entry_means_no_candidates_and_no_listing_as_before \
  tests/test_review_session_templates.py::test_a_rerun_with_both_flags_keeps_both_choices \
  tests/test_review_session_templates.py::test_a_template_without_headings_below_the_title_needs_an_anchor_too \
  tests/test_review_session_templates.py::test_anchor_flag_sets_the_place_and_asks_no_anchor_question \
  tests/test_review_session_templates.py::test_no_mapping_entry_lists_the_templates_whose_name_fits_the_kind \
  tests/test_review_session_templates.py::test_none_saves_nothing_to_the_mapping \
  tests/test_review_session_templates.py::test_setup_input_refuses_the_needs_anchor_proposal_unchanged_and_accepts_a_candidate \
  tests/test_review_session_templates.py::test_template_none_lists_nothing_and_proposes_the_plain_note \
  tests/test_review_session_templates.py::test_the_chosen_template_gives_its_kind_and_the_anchor_from_its_headings \
  tests/test_review_session_templates.py::test_the_chosen_template_is_saved_to_the_mapping_and_the_rest_of_the_block_stays \
  tests/test_review_session_templates.py::test_the_flag_wins_over_the_mapping_and_a_missing_choice_is_reported_as_today \
  tests/test_review_session_templates.py::test_the_ok_answer_is_carried_as_a_flag_bound_to_the_template_it_answered_for \
  tests/test_review_session_templates.py::test_without_a_base_path_or_with_a_kado_none_listing_the_candidates_are_empty \
  tests/test_review_session_templates.py::test_without_an_anchor_the_proposal_needs_one_and_names_the_recent_notes_headings \
  tests/test_review_skill.py::test_a_withheld_request_ends_the_run_after_the_listed_reviews \
  tests/test_review_skill.py::test_after_the_list_the_request_routes_by_kind_and_setup \
  tests/test_review_skill.py::test_an_abort_at_an_open_review_question_ends_the_whole_run \
  tests/test_review_skill.py::test_an_inferred_year_is_named_before_reading \
  tests/test_review_skill.py::test_daily_path_fix_is_applied_only_on_confirm \
  tests/test_review_skill.py::test_every_advice_of_the_read_script_has_its_line \
  tests/test_review_skill.py::test_every_later_match_call_carries_the_week_answer_like_the_template_and_the_anchor \
  tests/test_review_skill.py::test_every_listed_state_has_its_offer \
  tests/test_review_skill.py::test_every_status_of_replace_confirm_has_a_branch_in_the_write_list \
  tests/test_review_skill.py::test_nothing_to_review_says_so_and_names_the_access_hint_only_on_the_advice \
  tests/test_review_skill.py::test_open_reviews_are_handled_before_the_new_request_in_listed_order \
  tests/test_review_skill.py::test_read_branches_on_status_before_nothing_to_review \
  tests/test_review_skill.py::test_review_exists_asks_twice_before_replacing \
  tests/test_review_skill.py::test_rules_hold_each_line \
  tests/test_review_skill.py::test_setup_abort_saves_nothing_and_an_earlier_saved_kind_stays \
  tests/test_review_skill.py::test_setup_asks_for_the_anchor_before_confirm_when_none_could_be_proposed \
  tests/test_review_skill.py::test_setup_asks_for_the_template_when_candidates_are_listed \
  tests/test_review_skill.py::test_setup_asks_the_week_question_in_plain_words_only_when_ambiguous \
  tests/test_review_skill.py::test_setup_asks_when_the_template_has_no_frontmatter_block \
  tests/test_review_skill.py::test_setup_correction_reruns_match_for_names_and_carries_other_values_and_writes_only_on_confirm \
  tests/test_review_skill.py::test_setup_names_the_access_hint_for_kado_none_and_unreadable_templates \
  tests/test_review_skill.py::test_setup_previews_with_match_prints_evidence_and_hints_and_asks_in_plain_text \
  tests/test_review_skill.py::test_start_errors_show_expected_and_example_and_write_nothing \
  tests/test_review_skill.py::test_the_model_reads_read_json_and_the_language_and_writes_proposals_json_only \
  tests/test_review_skill.py::test_the_read_report_names_states_pacing_and_the_limit_advice \
  tests/test_review_skill_pass2.py::test_a_collision_after_a_heading_pick_ends_with_start_over_or_abort_never_a_second_pick \
  tests/test_review_skill_pass2.py::test_a_replace_preview_says_the_section_is_replaced_not_added \
  tests/test_review_skill_pass2.py::test_an_unticked_approved_box_is_named_and_nothing_delivered \
  tests/test_review_skill_pass2.py::test_deliver_branches_on_status_then_problems_or_failed_step \
  tests/test_review_skill_pass2.py::test_drop_kado_write_failed_names_the_partial_withdrawal_and_reruns_once \
  tests/test_review_skill_pass2.py::test_drop_reports_withdrawn_dropped_already_applied_and_set_changed \
  tests/test_review_skill_pass2.py::test_every_parse_warning_has_a_plain_language_line \
  tests/test_review_skill_pass2.py::test_every_preview_notice_is_one_line_and_the_question_still_follows \
  tests/test_review_skill_pass2.py::test_every_refusing_preview_problem_has_its_line \
  tests/test_review_skill_pass2.py::test_place_anchor_goes_to_preview_and_deliver \
  tests/test_review_skill_pass2.py::test_preview_prints_the_section_target_and_place_then_asks_deliver_or_abort_and_ends_the_turn \
  tests/test_review_skill_pass2.py::test_set_withdrawn_routes_from_the_deliver_step_into_drop \
  tests/test_review_skill_pass2.py::test_the_heading_pick_names_the_place_fields_the_refusal_carries \
  tests/test_review_skill_pass2.py::test_the_replace_mode_branch_covers_all_three_problems_and_comes_before_the_heading_pick \
  tests/test_review_state.py::test_a_fresh_record_over_a_fully_applied_set_reads_open_and_all_applied_needs_an_action \
  tests/test_review_state.py::test_an_unreadable_set_reads_delivered_never_applied_or_withdrawn \
  tests/test_review_state.py::test_begun_delivery_without_failed_step_is_failed_delivery_not_open \
  tests/test_review_state.py::test_every_action_applied_is_applied \
  tests/test_review_state.py::test_failed_step_in_meta_is_failed_delivery \
  tests/test_review_state.py::test_move_refused_when_the_target_and_the_inbox_copy_both_exist \
  tests/test_review_state.py::test_pending_approval_without_a_set_json_is_open \
  tests/test_review_state.py::test_stem_state_absent_set_is_failed_delivery_only_on_not_found \
  tests/test_review_state.py::test_stem_state_probes_the_move_source_first_and_the_destination_only_while_it_exists \
  tests/test_review_state.py::test_withdrawn_is_tested_before_the_begun_delivery_reading \
  tests/test_review_state_finished.py::test_a_begun_delivery_without_doc_mark_whose_set_is_gone_stays_failed_delivery \
  tests/test_review_state_finished.py::test_a_complete_delivery_whose_set_is_gone_is_finished_not_failed \
  tests/test_review_state_finished.py::test_a_fresh_record_without_applied_reported_beside_an_applied_set_reads_open \
  tests/test_review_state_listing.py::test_open_reviews_lists_a_half_withdrawn_stem_as_failed_delivery_until_meta_says_withdrawn \
  tests/test_review_state_listing.py::test_open_reviews_lists_every_document_by_period_with_its_state \
  tests/test_review_state_listing.py::test_open_reviews_never_lists_a_withdrawn_review_nor_an_applied_one_already_reported \
  tests/test_review_state_listing.py::test_open_reviews_probes_the_set_of_every_approved_document_and_lists_a_delivered_one \
  tests/test_staged_delivery.py::test_a_done_step_whose_target_is_absent_is_never_written_again \
  tests/test_staged_delivery.py::test_a_landed_target_with_identical_text_counts_as_done_without_a_write \
  tests/test_staged_delivery.py::test_fail_names_the_step_and_the_error_class_on_stderr \
  tests/test_staged_delivery.py::test_the_step_is_persisted_as_in_flight_before_its_upload \
  tests/test_vault_config_edit.py::test_flow_mapping_rewrite_keeps_sibling_spelling_and_scalar_types \
  tests/test_vault_config_edit.py::test_same_named_key_under_another_parent_is_not_touched \
  tests/test_vault_config_writer_review.py::test_changed_value_replaces_the_line_only \
  tests/test_vault_config_writer_review.py::test_daily_path_fixed_only_when_the_input_says_so \
  tests/test_vault_config_writer_review.py::test_flow_granularity_from_the_profile_is_rewritten_in_place \
  tests/test_vault_config_writer_review.py::test_invalid_input_is_refused_with_pointers_and_nothing_written \
  tests/test_vault_config_writer_review.py::test_month_setup_lands_beside_the_week_setup \
  tests/test_vault_config_writer_review.py::test_null_template_removes_the_mapping_key \
  tests/test_vault_config_writer_review.py::test_same_input_again_is_unchanged_and_byte_identical \
  tests/test_vault_config_writer_review.py::test_week_setup_inserts_nested_keys_and_creates_sections \
  tests/test_vault_config_writer_review.py::test_week_setup_on_the_instance_config_shape \
  tests/test_week_rule_inference.py::test_choose_rule_prefers_iso_then_1_then_the_smallest \
  tests/test_week_rule_inference.py::test_infer_rule_a_week_1_note_pins_min_days_to_1 \
  tests/test_week_rule_inference.py::test_infer_rule_contradicting_starts_are_ambiguous \
  tests/test_week_rule_inference.py::test_infer_rule_from_frontmatter_dates_reads_no_note_body \
  tests/test_week_rule_inference.py::test_infer_rule_no_dates_at_all_is_ambiguous \
  tests/test_week_rule_inference.py::test_infer_rule_reads_the_body_only_when_the_frontmatter_has_no_date \
  tests/test_week_rule_inference.py::test_infer_rule_without_a_candidate_is_default \
  tests/test_week_rule_inference.py::test_rules_fitting_is_every_min_days_on_the_start_weekday
```

</details>

## 2. Trace

Shorthand (`X::` = `tests/<file>::`): `S` test_review_skill.py · `S2` test_review_skill_pass2.py · `SC` test_review_skill_contract.py · `SE` test_review_session.py · `ST` test_review_session_templates.py · `CF` test_review_config.py · `W` test_vault_config_writer_review.py · `VE` test_vault_config_edit.py · `P` test_period.py · `WR` test_week_rule_inference.py · `PR` test_review_period.py · `PE` test_review_period_end_pass.py · `RD` test_review_read.py · `DY` test_review_day.py · `HB` test_review_habits.py · `PC` test_review_pacer.py · `KR` test_kado_client_retry.py · `KA` test_kado_client_attempts.py · `KL` test_kado_client_listnotes.py · `DC` test_review_doc.py · `DP` test_review_doc_parse.py · `IN` test_review_instructions.py · `DL` test_review_deliver.py · `DR` test_review_deliver_report.py · `RR` test_review_deliver_rerun.py · `RM` test_instruction_render_section_actions.py · `HS` test_hashi_instructions_schema.py · `SD` test_staged_delivery.py · `RS` test_review_state.py · `RL` test_review_state_listing.py · `RF` test_review_state_finished.py · `E` test_review_e2e.py · `EE` test_review_e2e_edges.py · `EF` test_review_e2e_failures.py · `IT` test_inbox_triage_review_skip.py · `PV` test_review_privacy.py · `PD` test_review_privacy_docs.py · `GAP` test_045_close_out_gaps.py (new, §3). **INT** is test_review_integration.py (live, not in the invocation). **R n** is a run of live-walk.md; **DL yyyy-mm-dd** a README Decisions Log row.

| Criterion | Class | Evidence | Mechanism the evidence falsifies |
|---|---|---|---|
| F1-AC1 | script + prose pin + live | `SE::test_match_infers_iso_from_journal_start_dates`, `SE::test_match_infers_a_sunday_rule_from_sunday_starts`, `SE::test_match_proposes_place_and_daily_sections_from_the_templates`, `SE::test_match_month_lists_names_and_needs_no_week_rule`, `SE::test_match_keeps_two_notes_with_the_same_stem`, `ST::test_the_chosen_template_gives_its_kind_and_the_anchor_from_its_headings`, `RD::test_a_missing_setup_stops_without_a_call`, `S::test_setup_previews_with_match_prints_evidence_and_hints_and_asks_in_plain_text`, `S::test_after_the_list_the_request_routes_by_kind_and_setup`, `S::test_rules_hold_each_line[plain-form]`; R2 da0eedd9:74-95 (proposal, matched notes, template question, plain-text confirm) | `match` not proposing folder / format / first day / template / heading and place / daily sections / language, or dropping a note from `matched` or `unmatched`; `review-read.py` reading a daily without a setup (it makes no Kado call); the skill not routing a missing setup to step 2 before step 4, not printing `matched` / `unmatched`, or asking other than in plain text |
| F1-AC2 | script + e2e + prose pin + live | `SE::test_start_setup_returns_the_current_values`, `SE::test_match_configured_values_win_over_the_guess`, `SE::test_match_configured_rule_wins_over_the_inference`, `CF::test_current_setup_is_the_proposal_shape_none_or_the_pointers`, `P::test_setup_word_asks_for_the_setup`, `EE::test_setup_rerun_shows_the_saved_setup_and_a_confirmed_correction_replaces_it`, `S::test_setup_previews_with_match_prints_evidence_and_hints_and_asks_in_plain_text` (`print it first`); R18 269b1964:5-178 (`/review setup` over a saved setup, both kinds, config unchanged on "Use it as it is") | `start setup` not returning `current.<kind>` (values, `null`, or pointers); `match` guessing over configured values; a confirmed correction changing more than the corrected key or touching the other kind; the skill not printing the current values first |
| F1-AC3 | script + lib | `SE::test_match_infers_iso_from_journal_start_dates`, `SE::test_match_infers_the_rule_from_day_heading_links`, `SE::test_match_week_1_note_pins_min_days`, `WR::test_rules_fitting_is_every_min_days_on_the_start_weekday`, `WR::test_choose_rule_prefers_iso_then_1_then_the_smallest`, `WR::test_infer_rule_from_frontmatter_dates_reads_no_note_body`, `WR::test_infer_rule_reads_the_body_only_when_the_frontmatter_has_no_date`, `WR::test_infer_rule_a_week_1_note_pins_min_days_to_1`; R2 da0eedd9:74 (`week_rule: inferred`, 8 notes checked) | ISO-dated `2026-W13` notes not giving `GGGG-[W]WW` + monday/4 with every note in `matched`; the inference preferring another rule over ISO when both fit |
| F1-AC4 | script + lib | `SE::test_match_folder_without_notes_is_default_iso_and_found`, `SE::test_match_parsing_names_are_notes_to_compare_even_when_unmatched`, `SE::test_match_empty_listing_is_kado_none_never_no_notes`, `WR::test_infer_rule_without_a_candidate_is_default`, `S::test_setup_names_the_access_hint_for_kado_none_and_unreadable_templates` | A folder without parsing names not proposing ISO weeks / `YYYY-MM` with the "no notes to compare" hint naming the folder; the hint given when parsing names exist; an empty Kado listing read as "no notes" instead of `kado-none` with the access hint |
| F1-AC5 | script + lib | `SE::test_match_sunday_flags_relist_the_iso_notes_as_unmatched`, `RD::test_the_period_is_resolved_under_the_configured_week_rule`, `P::test_render_rule_week_format_follows_the_configured_rule`, `P::test_parse_name_gggg_follows_the_rule_and_GGGG_stays_iso`, `P::test_sunday_first_one_day_rule_puts_2026_03_01_in_week_10`; not walked (the vault's weeks start on Monday) | `match --first-day sunday --min-days 1` not moving the ISO-dated notes to `unmatched` before confirmation; week numbers and week years rendered under ISO instead of the configured rule |
| F1-AC6 | script + lib + prose pin only | `SE::test_match_contradicting_starts_are_ambiguous`, `SE::test_match_notes_without_dates_are_ambiguous`, `SE::test_match_partial_day_headings_do_not_count_as_dates`, `SE::test_match_with_the_week_flags_reports_given_so_the_question_is_asked_once`, `SE::test_match_never_requests_the_plugin_config`, `WR::test_infer_rule_contradicting_starts_are_ambiguous`, `WR::test_infer_rule_no_dates_at_all_is_ambiguous`, `EE::test_ambiguous_weekly_notes_ask_the_week_question_once_and_every_rerun_keeps_the_answer`, `S::test_setup_asks_the_week_question_in_plain_words_only_when_ambiguous`, `S::test_every_later_match_call_carries_the_week_answer_like_the_template_and_the_anchor`; **not walked** (`week_rule: inferred` on every setup, live-walk.md "Model-behaviour criteria"; DL 2026-11-11 "never from the Obsidian plugin config") | Disagreeing or dateless notes reported `inferred`; a `.obsidian` path requested from Kado; the rerun with `--first-day` / `--min-days` not reporting `given` (the question asked twice); the plain-words question or its mapping to the two flags deleted from the skill. That the model asks in plain words is unobserved |
| F1-AC7 | script + e2e + prose pin + live | `SE::test_match_template_kinds`, `SE::test_match_without_a_template_leaves_the_anchor_open`, `ST::test_no_mapping_entry_lists_the_templates_whose_name_fits_the_kind`, `ST::test_a_mapping_entry_means_no_candidates_and_no_listing_as_before`, `ST::test_without_a_base_path_or_with_a_kado_none_listing_the_candidates_are_empty`, `ST::test_without_an_anchor_the_proposal_needs_one_and_names_the_recent_notes_headings`, `ST::test_a_template_without_headings_below_the_title_needs_an_anchor_too`, `ST::test_template_none_lists_nothing_and_proposes_the_plain_note`, `ST::test_anchor_flag_sets_the_place_and_asks_no_anchor_question`, `ST::test_setup_input_refuses_the_needs_anchor_proposal_unchanged_and_accepts_a_candidate`, `EE::test_first_setup_without_a_template_mapping_asks_for_the_template_and_saves_it`, `EE::test_first_setup_with_no_template_keeps_that_answer_and_the_typed_anchor_on_every_rerun`, `S::test_setup_asks_for_the_template_when_candidates_are_listed`, `S::test_setup_asks_for_the_anchor_before_confirm_when_none_could_be_proposed`, `S::test_setup_names_the_access_hint_for_kado_none_and_unreadable_templates`; R2 da0eedd9:74-95 (template question per kind, anchor `Organisation`); live-walk.md defect 1 (5b959432:96-100, the state before the fix) | No `template_candidates` when the mapping has none; a PERMISSION_DENIED template not `unreadable` with the no-access hint; a template without headings not `needs_anchor`; `setup-input` accepting `place.anchor: null`; the skill offering Confirm while the anchor is null, or losing the `0 none` / typed-name / unreadable lines |
| F1-AC8 | script + e2e + prose pin + live | `SE::test_match_given_format_wins_and_its_problems_are_listed`, `SE::test_match_with_the_week_flags_reports_given_so_the_question_is_asked_once`, `SE::test_setup_input_invalid_returns_pointers_and_writes_nothing`, `ST::test_a_rerun_with_both_flags_keeps_both_choices`, `ST::test_the_flag_wins_over_the_mapping_and_a_missing_choice_is_reported_as_today`, `EE::test_ambiguous_weekly_notes_ask_the_week_question_once_and_every_rerun_keeps_the_answer`, `E::test_setup_abort_saves_nothing_and_writes_nothing`, `S::test_setup_correction_reruns_match_for_names_and_carries_other_values_and_writes_only_on_confirm`; R18 269b1964:83, :142 (a correction reran `match` and reprinted the proposal — with the polish defect, §7) | A corrected flag not winning over the mapping or the inference; `match` not re-listing the matches under the corrected value; `setup-input` writing for an invalid proposal; the Correct branch not rerunning `match`, dropping a carried flag, or writing before Confirm |
| F1-AC9 | script + lib + e2e + prose pin | `W::test_week_setup_inserts_nested_keys_and_creates_sections`, `W::test_week_setup_on_the_instance_config_shape`, `W::test_month_setup_lands_beside_the_week_setup`, `W::test_changed_value_replaces_the_line_only`, `W::test_daily_path_fixed_only_when_the_input_says_so`, `W::test_null_template_removes_the_mapping_key`, `W::test_invalid_input_is_refused_with_pointers_and_nothing_written`, `W::test_flow_granularity_from_the_profile_is_rewritten_in_place`, `W::test_same_input_again_is_unchanged_and_byte_identical`, `VE::test_same_named_key_under_another_parent_is_not_touched`, `VE::test_flow_mapping_rewrite_keeps_sibling_spelling_and_scalar_types`, `CF::test_week_input_maps_onto_config_paths_in_sdd_order`, `CF::test_month_input_writes_only_what_it_carries_and_null_removes`, `CF::test_daily_path_fix_only_when_the_input_says_so`, `SE::test_match_daily_path_fix_only_when_the_other_spelling_exists`, `SE::test_setup_input_writes_a_schema_valid_writer_input`, `ST::test_the_chosen_template_is_saved_to_the_mapping_and_the_rest_of_the_block_stays`, `ST::test_none_saves_nothing_to_the_mapping`, `E::test_week_from_first_start_through_hashi_apply` (setup saved, `start` rerun reports `present`, `confirmed-week.json` gone), `EE::test_setup_rerun_shows_the_saved_setup_and_a_confirmed_correction_replaces_it`, `S::test_daily_path_fix_is_applied_only_on_confirm`, `S::test_after_the_list_the_request_routes_by_kind_and_setup` (rerun `start`, continue); R2 da0eedd9:117, :170 (`setup-input` ok, both kinds saved). The continue-in-session part was not walked (R1/R2 were `/review setup`) | The writer changing any existing line (the tests diff the whole file: insert-only), fixing the daily path without `daily_path_fix`, or writing on invalid input; a stray `templates.*` key for `none`; the skill not rerunning `start` after the save |
| F1-AC10 | e2e + script + prose pin | `E::test_setup_abort_saves_nothing_and_writes_nothing`, `SE::test_setup_input_invalid_returns_pointers_and_writes_nothing`, `SE::test_match_unsafe_format_stops_before_any_kado_call`, `S::test_setup_abort_saves_nothing_and_an_earlier_saved_kind_stays`, `S::test_rules_hold_each_line[abort]`; R1 5b959432 (setup ended without a save, config unchanged) | `match` writing to the config, the vault or `tomo-tmp/`; the Abort line or the Abort rule deleted. The e2e Abort is the absence of further calls after `match`: it proves `match` has no side effect, no abort code path runs |
| F2-AC1 | script + lib + e2e + prose pin + live | `SE::test_start_lists_the_open_reviews_by_period_with_their_state`, `SE::test_start_bare_with_a_listed_review_withholds_the_request`, `SE::test_start_bare_withholds_the_request_for_every_listed_state`, `SE::test_start_a_named_period_with_a_listed_review_keeps_the_request`, `SE::test_start_bare_setup_and_errors_are_not_withheld`, `SE::test_start_probes_the_set_json_of_approved_documents_and_lists_a_delivered_review_as_delivered`, `SE::test_start_reports_applied_once_and_the_second_start_does_not_list_it`, `SE::test_start_orders_the_open_reviews_under_the_configured_week_format_and_rule`, `RL::test_open_reviews_lists_every_document_by_period_with_its_state`, `RL::test_open_reviews_probes_the_set_of_every_approved_document_and_lists_a_delivered_one`, `RL::test_open_reviews_never_lists_a_withdrawn_review_nor_an_applied_one_already_reported`, `RS::test_pending_approval_without_a_set_json_is_open`, `RF::test_a_complete_delivery_whose_set_is_gone_is_finished_not_failed`, `EE::test_bare_start_with_an_open_review_carries_no_request_before_or_after_its_delivery`, `EE::test_renamed_review_document_is_listed_by_its_period_and_parse_reports_not_found`, `E::test_abort_after_pass_2_by_not_applying_changes_nothing_outside_the_inbox`, `S::test_open_reviews_are_handled_before_the_new_request_in_listed_order`, `S::test_every_listed_state_has_its_offer`, `S::test_a_withheld_request_ends_the_run_after_the_listed_reviews`, `S::test_an_abort_at_an_open_review_question_ends_the_whole_run`; R4 da0eedd9:293, R5 68459faa:56, R14 80a4605a:57, R15 80a4605a:124 (open review listed first, `1 Continue · 2 Start over · 3 Abort`); the bare-`/review` half is **DL 2026-11-12 "stop after open reviews"** (live-walk.md defect 3), seen fixed 80a4605a:49 | A review document not found by `doc_type: review` (renamed inside the inbox included), a state misread (an approved document without its set probed, an applied set listed twice, a withdrawn one listed), a bare `start` carrying a default request beside a listing, a named period losing its request; the skill handling the request before the list, or routing a null request |
| F2-AC2 | script + lib + e2e + live | `SE::test_start_no_argument_is_the_last_finished_week_under_the_configured_rule`, `SE::test_start_month_is_the_last_finished_month`, `SE::test_start_bare_without_a_listed_review_is_the_default_week`, `SE::test_start_a_kind_word_with_a_listed_review_keeps_the_request`, `P::test_no_argument_is_the_last_finished_week`, `P::test_month_word_is_the_last_finished_month`, `P::test_default_week_follows_the_configured_rule`, `P::test_last_finished_period_of_each_kind`, `P::test_the_kind_words_are_case_insensitive`, `E::test_month_setup_then_new_note_targets_the_monthly_folder` (`start month` → 2026-10); R7/R10/R12/R19 (bare `/review`, nothing listed → 2026-W45 read), R5 68459faa:90-103 (the default week read beside a listing — the defect, now `request_withheld`) | The default not the last finished week from the configured first day, or `month` not the last finished month; `month` withheld beside a listed review |
| F2-AC3 | script + lib + e2e + live | `SE::test_start_every_argument_form_yields_the_request`, `SE::test_start_at_note_resolves_under_the_configured_names`, `P::test_a_full_week_name_is_that_week`, `P::test_a_full_month_name_is_that_month`, `P::test_an_at_note_is_matched_against_the_configured_formats`, `P::test_an_at_note_uses_the_configured_name_formats`, `P::test_parse_name_round_trips_each_format`, `P::test_march_2026_is_the_calendar_month`, `E::test_week_from_first_start_through_hashi_apply` (`2026-W13` → `source: arg`), `EE::test_bare_start_with_an_open_review_carries_no_request_before_or_after_its_delivery` (a named period beside a listing); R3 `/review 2026-W13` da0eedd9:189, R6 `/review 2026-03` 68459faa:109 | `2026-W13`, `2026-03` or an `@` note (path, bare name, `[[…]]`) not resolved to its period without a kind word; an `@` note matched against the default instead of the configured formats |
| F2-AC4 | script + lib + prose pin only | `SE::test_start_every_argument_form_yields_the_request` (`W13`, `M03`, `M3` → `year_inferred: true`), `SE::test_start_week_53_and_year_spanning_weeks_resolve_under_the_rule` (`W53` → 2026), `P::test_a_week_without_a_year_is_the_most_recent_finished_one`, `P::test_a_month_without_a_year_is_the_most_recent_finished_one`, `S::test_an_inferred_year_is_named_before_reading`; **not walked** (every walked argument carried its year) | `W13` not the most recent finished week 13, `year_inferred` unset; the "say which year was chosen before reading" line deleted. That the model names the year is unobserved |
| F2-AC5 | script + lib | `SE::test_start_at_note_that_fits_no_name_format_is_not_periodic_note`, `P::test_an_at_note_that_fits_neither_format_is_not_a_periodic_note`, `P::test_an_at_note_with_a_year_outside_the_supported_range_is_not_a_periodic_note`, `P::test_parse_name_returns_none_for_a_name_that_does_not_fit`, `SE::test_start_every_bad_argument_yields_kind_expectation_and_example` (0 Kado calls on a bad argument), `S::test_start_errors_show_expected_and_example_and_write_nothing`; not walked | `@Weekly Index` returning other than `not-periodic-note` with `expected` naming both configured formats; a Kado call spent on it; the skill's error line deleted |
| F2-AC6 | script + lib | `SE::test_start_every_bad_argument_yields_kind_expectation_and_example` (`unfinished-period` rows carry `last_finished`), `P::test_a_period_is_finished_only_when_its_end_lies_before_today`, `P::test_an_unfinished_period_is_refused_naming_the_last_finished_one`, `P::test_a_future_period_is_refused_naming_the_last_finished_one`, `P::test_the_week_that_ends_today_is_not_finished`, `S::test_start_errors_show_expected_and_example_and_write_nothing`; not walked | A running or future period accepted, or refused without `last_finished`; the week that ends today counted as finished |
| F2-AC7 | script + lib | `SE::test_start_every_bad_argument_yields_kind_expectation_and_example`, `P::test_an_invalid_period_names_what_was_expected_and_one_example`, `P::test_2025_has_no_week_53`, `P::test_week_number_outside_the_year_is_refused`, `P::test_a_year_outside_the_supported_range_is_an_invalid_period`, `P::test_anything_else_is_an_unknown_argument`, `RD::test_a_bad_invocation_exits_2`, `S::test_start_errors_show_expected_and_example_and_write_nothing`; not walked | `2026-W54`, `2026-13` or `month 2026-W13` not `invalid-period` with a non-empty `expected` and the stated `example`; `review-read.py` accepting `2026-W60` |
| F2-AC8 | script + lib + e2e + prose pin + live | `SE::test_start_reports_the_missing_setup_per_kind`, `CF::test_setup_missing_when_format_or_review_section_absent`, `RD::test_a_missing_setup_stops_without_a_call`, `E::test_week_from_first_start_through_hashi_apply` (`setup: missing` → setup → `present`), `E::test_month_setup_then_new_note_targets_the_monthly_folder`, `S::test_after_the_list_the_request_routes_by_kind_and_setup`; R1/R2 (the week setup ran before any read; 5b959432, da0eedd9) | A kind reported `present` without its review section; the reader reading without a setup; the `setup.<kind>` `missing` → step 2 routing deleted |
| F2-AC9 | lib + script | `P::test_2026_12_31_is_week_53_of_2026_running_into_january`, `P::test_2027_01_01_belongs_to_week_53_of_2026`, `P::test_2025_12_29_belongs_to_week_1_of_2026`, `P::test_iso_rule_equals_isocalendar_for_every_day_2020_to_2030`, `P::test_week_53_belongs_to_the_old_week_year`, `P::test_week_one_starting_in_december_lives_in_the_new_week_year_folder`, `P::test_render_iso_week_format`, `P::test_render_rule_week_format_follows_the_configured_rule`, `SE::test_start_week_53_and_year_spanning_weeks_resolve_under_the_rule`, `SE::test_start_no_argument_is_the_last_finished_week_under_the_configured_rule`, `CF::test_request_dict_adds_the_first_and_last_day`, `RD::test_the_period_is_resolved_under_the_configured_week_rule`; not walked | Week 53's days, number, week year or note folder computed under the calendar year or under ISO when the configured rule is not Monday/4 |
| F3-AC1 | lib + script + e2e | `DY::test_configured_sections_kept_in_setup_order_with_subsections`, `DY::test_unconfigured_and_skipped_sections_are_absent`, `DY::test_quoth_embed_under_dayplanner_heading_is_collected_and_read`, `DY::test_date_format_decides_what_same_day_means`, `DY::test_tasks_from_daily_and_linked_notes_carry_their_done_date_and_source`, `DY::test_fields_outside_kept_sections_are_not_parsed`, `DY::test_two_dailies_for_one_day_are_both_read`, `PR::test_dailies_found_flat_and_in_year_folder`, `PR::test_a_link_stem_is_resolved_by_name_once_and_read_at_its_vault_path`, `PR::test_real_review_day_reads_a_week_through_the_period_reader`, `PE::test_a_link_stem_spelled_like_a_note_path_already_read_is_looked_up_not_served_that_note`, `PV::test_every_marker_reached_the_scripts` (the daily text, the 5J answer and the tracker values reach `read.json`); INT (T6.2: every March daily found once, the same-day Dayplanner read for every day with content, the same-day 5J read) | A daily of the period not found (flat or year folder), a configured section, field or task missing from the entry, a same-day linked note (planner, journal) not read through its link or embed, or read twice |
| F3-AC2 | lib + e2e | `DY::test_tomorrows_planner_link_is_ignored`, `DY::test_a_day_token_matches_on_digit_boundaries_only`, `DY::test_embed_in_skipped_section_is_not_collected`, `DY::test_dataview_blocks_and_inline_queries_are_dropped`, `DY::test_quoth_and_dynbedded_blocks_are_dropped_from_the_kept_text`, `DY::test_journal_read_with_earlier_years_subsections_dropped`, `DY::test_planner_heading_naming_other_days_is_dropped_schedule_kept`, `DY::test_an_other_day_section_in_a_linked_note_ends_at_a_thematic_break`, `DY::test_links_are_the_targets_of_the_kept_text`, `PR::test_day_after_period_is_read_for_its_yesterday_fields_only` (its links and sections stay out), `PR::test_real_review_day_reads_a_week_through_the_period_reader` (the "On This Day" 2025 daily never requested); INT (tomorrow's planner not requested, no earlier 5J year read) | A dataview / quoth / dynbedded body kept as content; another day's planner or an earlier year's journal section read or linked; the day-after daily's text or links reaching a period day |
| F3-AC3 | lib | `DY::test_done_in_period_counts_by_tick_date_whichever_file_holds_it`, `DY::test_task_note_open_tasks_are_open_today`, `DY::test_done_in_period_includes_the_first_and_the_last_day_of_the_period`, `DY::test_a_tick_without_a_date_never_counts_as_done_in_the_period`, `DY::test_next_day_tick_keeps_its_own_date`, `DY::test_a_target_named_like_a_task_note_is_not_read_per_day`, `PR::test_a_task_note_is_read_once_and_its_tasks_land_by_done_date`, `PR::test_real_review_day_reads_a_week_through_the_period_reader` (`open today` through the real readers) | A task note read per day; a `[x]` without a ✅ date, or with one outside the period, counted as done; an open task labelled other than `open today`; a bound exclusive |
| F3-AC4 | lib | `DY::test_plain_text_daily_still_yields_content`, `DY::test_plain_daily_with_a_title_heading_is_read_whole_under_text`, `DY::test_plain_daily_with_only_unconfigured_headings_is_read_whole`, `DY::test_skip_section_inside_a_whole_read_daily_stays_excluded`, `DY::test_one_configured_section_found_means_no_fallback`, `DY::test_prose_after_a_thematic_break_stays_under_text_in_the_fallback` | A daily without the configured headings read as empty instead of whole under `text`; the fallback running beside a configured section |
| F3-AC5 | lib + script + e2e | `PR::test_month_resolves_weekly_notes_flat_and_in_the_week_year_folder`, `PR::test_day_blocks_keyed_by_date_end_at_their_level_and_drop_out_of_month_and_skipped_text`, `PR::test_week_level_text_is_tagged_with_week_and_overlap`, `PR::test_only_in_weekly_links_and_dailies_not_in_weekly_are_computed`, `PR::test_a_weekly_note_flat_and_in_the_year_folder_is_read_twice_and_marked_duplicate`, `PR::test_week_notes_are_not_read_for_a_week_review`, `P::test_march_2026_overlaps_iso_weeks_9_to_14`, `P::test_overlapping_weeks_follow_the_configured_rule`, `RD::test_a_month_run_reports_the_weekly_notes_and_stays_within_the_call_budget`, `DC::test_weekly_only_needs_a_weekly_note_and_month_groups_need_a_month_with_weeklies`, `DC::test_month_only_groups_only_for_a_month_with_weekly_notes`, `EF::test_month_with_weekly_notes_new_note_waits_in_the_inbox_until_hashi_moves_it` (W09–W14 found, the `weekly_only` group rendered with its `[[2026-W13]]` link); R6 68459faa (weekly_status `found`, 6 weekly notes, w1 n2); INT (W09..W13 found, W14 absent) | An overlapping weekly note not found or not read, a February day block or a `Review Check` / `Organisation` section kept, `only_in_weekly_links` or `dailies_not_in_weekly` wrong, the two month groups rendered for a week |
| F3-AC6 | lib | `PR::test_month_without_weekly_notes_says_none_found`, `PR::test_month_without_weekly_config_says_not_configured_and_lists_nothing`, `PR::test_empty_weekly_listing_is_kado_empty_not_none_found`, `S::test_the_read_report_names_states_pacing_and_the_limit_advice` (`weekly_status` printed); not walked (every walked month found its weekly notes) | A month whose weeks have no weekly notes not reporting `weekly_status: none-found` with the month groups absent; an empty Kado listing read as "none found" instead of `kado-empty` |
| F3-AC7 | lib + script | `PR::test_growth_lists_created_notes_with_links_mocs_changed_and_mocs_linked_across_pages`, `PR::test_period_bounds_are_inclusive_local_days_in_ms`, `PR::test_period_bounds_follow_the_local_clock_across_a_dst_change`, `PR::test_growth_without_moc_folders_queries_no_mocs`, `PR::test_empty_growth_results_are_reported_as_kado_returned_none`, `PR::test_a_created_query_that_still_fails_is_not_read_and_not_kado_none`, `PE::test_the_created_query_and_a_moc_listing_over_the_same_prefix_are_two_reads`, `KL::test_list_notes_passes_filter_through_on_every_cursor_page`, `KL::test_list_notes_filter_reaches_the_wire_unchanged`, `DC::test_labels_de_en_with_en_fallback` ("Vault growth" / "Vault-Wachstum" is the group's name); R3/R6 (g3 / g5 growth items) | A note created one millisecond outside the period listed, or one on the bound dropped; a MOC changed in the period missing; the `createdAfter/Before` filter dropped on a later page; the group named as a history of edits |
| F3-AC8 | lib + script + e2e | `RD::test_a_week_run_prints_the_per_day_report_and_writes_read_json`, `PR::test_dailies_found_flat_and_in_year_folder` (`found` / `empty` / no daily per day), `PR::test_two_dailies_for_one_date_are_both_read_and_reported_duplicate`, `PR::test_a_stem_that_resolves_to_nothing_is_reported_missing_not_failed`, `PR::test_a_missing_task_note_is_reported_and_nothing_else_changes`, `PE::test_a_linked_note_that_still_fails_is_marked_failed`, `PE::test_a_daily_that_still_fails_at_the_end_is_not_read_and_marked_failed`, `DY::test_missing_linked_note_is_a_problem_of_that_day_and_the_day_still_read`, `EE::test_sparse_period_reads_its_few_dailies_and_writes_the_document` (four days without a daily named), `S::test_the_read_report_names_states_pacing_and_the_limit_advice`; R3 (the per-day report printed, 41 calls) | A day missing from `report.days`, a daily's `found` / `empty` / `failed` state wrong, a linked note that is missing (`missing`) or still fails (`failed`) not named; the skill's report line deleted. A missing and an unreadable linked note both come out `linked-missing` at the day level and are told apart only by the period reader's `failed` state |
| F3-AC9 | script + lib + e2e + prose pin + live | `RD::test_no_daily_with_content_is_nothing_to_review_without_the_access_hint_and_no_file` (every day named `empty`, no advice, no `read.json`), `RD::test_a_week_without_dailies_in_a_folder_that_holds_other_dates_gets_no_access_hint`, `RD::test_an_empty_daily_listing_is_nothing_to_review_and_kado_empty`, `RD::test_a_stopped_output_never_carries_nothing_to_review`, `PR::test_empty_daily_listing_is_kado_empty_with_the_access_hint`, `DY::test_skeleton_only_daily_has_no_content`, `DY::test_an_empty_configured_section_is_still_no_fallback`, `DY::test_a_single_value_makes_content`, `E::test_empty_period_reports_and_writes_nothing`, `S::test_nothing_to_review_says_so_and_names_the_access_hint_only_on_the_advice`, `S::test_read_branches_on_status_before_nothing_to_review`, `S::test_every_advice_of_the_read_script_has_its_line`; R7/R10/R12/R19 (nothing to review for W45, nothing written), live-walk.md defect 4 (68459faa:90 advice given → 3a862c54:57 advice empty) | A template skeleton counted as content; `nothing_to_review` without the days, with `read.json` written, or with `check-key-access` although Kado listed the dailies; the access hint missing when the listing was empty; the skill reading `nothing_to_review` from a `stopped` output |
| F3-AC10 | script + lib + prose pin | `RD::test_kado_unreachable_stops_the_run_and_writes_nothing`, `RD::test_a_refused_key_stops_the_run_as_kado_auth`, `RD::test_a_client_that_cannot_be_built_is_kado_unreachable`, `RD::test_a_stopped_output_never_carries_nothing_to_review`, `PE::test_a_connection_error_propagates`, `PC::test_connection_auth_and_not_found_errors_propagate_and_restore`, `PC::test_connection_error_in_the_end_pass_propagates_and_restores`, `RS::test_stem_state_absent_set_is_failed_delivery_only_on_not_found`, `SE::test_start_a_refused_set_probe_stops_and_is_never_read_as_absent`, `S::test_rules_hold_each_line[stopped]`; not walked (Kado was up) | A connection or auth error swallowed into `not_read` or `failed`, a stop without `error.kind` / `detail`, `tomo-tmp/` written on a stop; a refused set probe read as "no set"; the stopped rule deleted |
| F3-AC11 | lib + script | `PC::test_pacer_starts_at_0_3_s_and_returns_the_value`, `PC::test_a_read_that_outlasts_the_retries_returns_none_and_is_recovered_at_the_end`, `RD::test_one_client_per_run_built_once_before_the_first_call_under_one_pacer`, `RD::test_injected_429s_give_retried_waited_and_the_advice`, `KA::test_retry_wait_s_honours_retry_after_on_429_and_backoff_on_503`, `KR::test_a_429_that_succeeds_on_retry_does_not_raise_rate_limit_error`, `PE::test_a_rate_limited_daily_is_recovered_by_the_end_pass`, `PE::test_a_rate_limited_linked_note_is_recovered_without_a_second_daily_read`, `PE::test_a_rate_limited_name_lookup_is_recovered_by_the_end_pass`, `PE::test_a_rate_limited_daily_listing_recovered_by_the_end_pass_reads_the_whole_period`; not walked (0 retries in 19 runs; the pacer waited 11.7 s / 48.4 s) | Calls not spaced at 0.3 s from the first call, a 429 not slept for `Retry-After`, a turned-away daily, linked note, name lookup or listing left unread instead of recovered |
| F3-AC12 | lib + script + prose pin | `PC::test_spacing_doubles_after_each_call_that_needed_retries_up_to_2_s`, `PC::test_widened_spacing_is_what_the_following_sends_wait`, `PC::test_the_end_pass_retries_a_failed_path_exactly_once`, `PC::test_only_what_fails_in_the_end_pass_is_not_read`, `PC::test_finish_keeps_the_widest_interval_until_close_restores_the_previous_value`, `PC::test_summary_reports_calls_retried_waited_not_read_and_the_advice`, `PC::test_summary_without_retries_has_no_advice`, `PC::test_fake_accounting_matches_the_real_client_on_one_429_scenario`, `RD::test_injected_429s_give_retried_waited_and_the_advice`, `RD::test_a_note_that_still_fails_in_the_end_pass_is_not_read_and_marked_failed`, `RD::test_the_daily_listing_still_not_read_after_the_end_pass_stops_the_run_and_writes_nothing`, `RD::test_reads_after_a_listing_recovered_by_the_end_pass_are_sent_at_the_widest_interval`, `KA::test_wait_counters_accumulate_across_calls_and_kinds`, `KR::test_429_exhausted_raises_rate_limit_error_with_status`, `PE::test_a_daily_that_fails_after_a_recovered_listing_is_still_marked_failed`, `PE::test_a_weekly_note_that_fails_after_a_recovered_weekly_listing_is_in_the_one_not_read_list`, `S::test_the_read_report_names_states_pacing_and_the_limit_advice`; not walked | The spacing not doubled after a retried call or exceeding 2 s, the end pass retrying twice or restoring the interval early, `retried` / `waited_s` / `advice` wrong, a path recovered at the end still in `not_read`, the "raise Kado's rate limit" line deleted |
| F3-AC13 | script + prose pin | `DC::test_info_callout_names_target_existence_place_and_not_read` (`nicht gelesen: …`, `teilweise gelesen: …` in the document's second line), `RD::test_a_note_that_still_fails_in_the_end_pass_is_not_read_and_marked_failed` (`not_read` in `read.json`), `S::test_the_read_report_names_states_pacing_and_the_limit_advice` ("the document will name them at its top"); not walked (`not_read` empty in every run) | `not_read` or `partly_read` of `read.json` not rendered into the callout under the title; the skill's line deleted |
| F4-AC1 | script + lib + e2e | `DC::test_approved_unticked_and_frontmatter_schema_valid` (`<inbox>/2026-W13 Review.md`, unticked Approved, one write), `DC::test_info_callout_names_target_existence_place_and_not_read`, `DC::test_year_subfolder_target_counts_as_existing`, `DC::test_a_search_hit_with_another_basename_is_not_the_moved_target`, `DC::test_doc_path_comes_from_inbox_path`, `DC::test_existing_non_tomo_document_is_doc_name_taken`, `DC::test_forged_sources_and_structural_lines_cannot_reach_the_document`, `CF::test_inbox_path_refuses_unsafe_names`, `CF::test_inbox_path_refuses_empty_inbox_and_escapes`, `P::test_week_note_paths_are_flat_then_the_week_year_folder`, `E::test_week_from_first_start_through_hashi_apply` (`recorded == [WEEK_DOC]`: Pass 1 writes the document and nothing else), `E::test_target_created_between_the_passes_turns_new_note_into_insert` (`(will be created)`), `E::test_every_write_attempted_so_far_was_under_the_inbox_prefix`, `EE::test_every_write_attempted_so_far_was_under_the_inbox_prefix`, `EF::test_every_write_attempted_so_far_was_under_the_inbox_prefix`; R3/R6 (`100 Inbox/2026-W13 Review.md`, three month documents; Kado audit-log windows hold only inbox paths) | The document named without the period, placed outside the inbox, ticked, without the target / exists / will-be-created line, or any second vault write in Pass 1; a document of the user's overwritten. The e2e fixtures also fail at teardown on any write outside `100 Inbox/` |
| F4-AC2 | script + lib + e2e + prose pin + live | `DC::test_groups_in_order_with_nothing_found_lines_and_ids` (the SDD group order, every item `- [x]` with an id), `DC::test_every_tomo_item_ends_with_a_unique_id_and_text_cannot_forge_one`, `DC::test_a_theme_naming_fewer_than_two_days_is_rejected`, `DC::test_month_only_groups_only_for_a_month_with_weekly_notes`, `DC::test_weekly_only_needs_a_weekly_note_and_month_groups_need_a_month_with_weeklies`, `DP::test_rendered_document_parses_back_unapproved_with_every_item_kept`, `DP::test_edited_text_is_kept_verbatim_with_continuation_lines_and_escapes`, `E::test_week_from_first_start_through_hashi_apply` (untick, rewrite, add — parsed back as kept 5 / unticked 1 / added 1), `GAP::test_the_groups_are_defined_for_the_model_with_the_two_day_theme_rule` (new, §3), `S::test_the_model_reads_read_json_and_the_language_and_writes_proposals_json_only`; R3/R6 (d8 o5 t5 g3 h12 / d11 o9 t7 g5 h12 w1 n2 — every group filled, the owner edited in Obsidian) | A group out of order or missing, an item rendered unticked or without an editable text line, a theme with one source day accepted, the month groups rendered for a week; the group definitions the model sorts by deleted from the skill (gap, §3) |
| F4-AC3 | lib + script + e2e | `DC::test_schema_refuses_habits_own_sections_and_items_without_sources`, `DC::test_item_without_a_source_inside_the_period_is_rejected_and_listed`, `DC::test_sources_render_as_links_of_the_note_stem`, `DC::test_links_come_only_from_resolved_sources_as_the_listed_stem`, `DC::test_a_bare_weekly_stem_resolves_for_weekly_only`, `DC::test_a_wiki_link_shaped_daily_as_the_only_source_resolves_through_the_stem_fallback`, `DC::test_a_wiki_link_shaped_weekly_as_the_only_source_resolves_through_the_stem_fallback`, `E::test_week_from_first_start_through_hashi_apply` (`[[2026-03-23]]` in the done item and in the landed section), `EF::test_month_with_weekly_notes_new_note_waits_in_the_inbox_until_hashi_moves_it` (`[[2026-W13]]`), `S::test_the_model_reads_read_json_and_the_language_and_writes_proposals_json_only`; KPI "0 delivered proposals without a source-day link": 0 of 21 / 35 / 24 (live-walk.md) | An item whose only sources lie outside the period, in another year, or in a non-daily note accepted; a forged source rendered as a link; a `weekly_only` item without a weekly note of the period |
| F4-AC4 | script + lib | `DC::test_empty_groups_show_one_nothing_found_line_also_growth_with_kado_none`, `DC::test_groups_in_order_with_nothing_found_lines_and_ids`, `DC::test_labels_de_en_with_en_fallback` ("nothing found" / "nichts gefunden"), `DP::test_the_nothing_found_line_is_never_an_item`, `IN::test_actions_only_kept_items_land_and_empty_groups_leave_no_heading`; R13 (n0: a month group with nothing) | An empty group without its one line, or with an access hint; the line parsed as an item, so it could land; an empty group keeping its heading in the section |
| F4-AC5 | script + lib + prose pin + live | `DC::test_labels_de_en_with_en_fallback` (`de`, `en`, `fr` → English), `DC::test_groups_in_order_with_nothing_found_lines_and_ids` (German headings and habit line), `HB::test_german_line_uses_german_labels_and_decimal_comma`, `HB::test_german_count_line_with_gaps`, `HB::test_english_line_for_a_count_names_missing_and_unreadable`, `HB::test_other_language_falls_back_to_english`, `HB::test_no_clear_average_in_german`, `GAP::test_every_proposal_is_written_in_the_setup_language` (new, §3), `S::test_the_model_reads_read_json_and_the_language_and_writes_proposals_json_only` (`<language>` from `review.language`); live-walk.md "Model-behaviour criteria": PASS — four documents with 5 / 7 / 7 / 7 German group headings, German function words 68:7, 96:23, 96:23, 86:16; the chat lines English by owner decision (DL 2026-11-12 "The skill may speak English; review documents are German") | Headings or fixed lines not German for `de`, not English for `en` or for any other language; the habit lines not following the language; "Every item is in `<language>`" deleted from the skill (gap, §3). Whether a proposal line is German is live evidence only |
| F4-AC6 | script | `IT::TestGetDocTypeReviewRule::test_week_review_stem_maps_to_review`, `IT::TestGetDocTypeReviewRule::test_month_review_stem_maps_to_review`, `IT::TestGetDocTypeReviewRule::test_frontmatter_doc_type_still_wins`, `IT::TestGetDocTypeReviewRule::test_renamed_review_stem_has_no_doc_type`, `IT::TestGetDocTypeReviewRule::test_only_the_space_suffix_counts`, `IT::TestReviewDocumentIsSkipped::test_pending_approval_review_is_skipped_silently`, `IT::TestReviewDocumentIsSkipped::test_pending_approval_review_with_full_frontmatter_is_skipped`, `IT::TestReviewDocumentIsSkipped::test_approved_review_is_skipped_silently`, `IT::TestReviewDocumentIsSkipped::test_review_document_does_not_change_the_action`, `IT::TestRuleBoundaries::test_user_book_review_without_tomo_block_is_a_new_item`, `IT::TestRuleBoundaries::test_renamed_stamped_review_gives_unknown_doc_type_warning_only`, `IT::TestRuleBoundaries::test_periodic_note_pending_move_is_not_a_new_source`, `IT::TestCallCountersUnchanged::test_discover_counters_match_a_run_without_the_review_documents`; not walked (no `/inbox` run recorded in the walk) | `inbox-triage` reading, queuing, classifying as a new item or applying (`force_pass2` included) a pending or approved review document, surfacing the waiting periodic note as a new source, spending an extra Kado call on them, or swallowing a user's own `Book Review.md` |
| F4-AC7 | lib + prose pin only | `DC::test_schema_refuses_habits_own_sections_and_items_without_sources` (an own-section group key refused), `IN::test_actions_own_sections_are_never_targeted`, `IN::test_actions_a_user_heading_named_like_the_review_is_never_replaced`, `SE::test_match_configured_values_win_over_the_guess` (`own_sections` from the config), `S::test_the_model_reads_read_json_and_the_language_and_writes_proposals_json_only` ("Never propose text for the user's own sections"), `S2::test_every_refusing_preview_problem_has_its_line[user-heading-collision]`; **not walked** (the setup lists no own sections on the test vault, live-walk.md "Model-behaviour criteria") | A proposals file with a group named after an own section accepted; the review inserted inside or replacing a marker that sits in an own section; the imperative deleted. That the model never writes reflection text is unobserved |
| F5-AC1 | lib + script + e2e + prose pin + live | `DP::test_rendered_document_parses_back_unapproved_with_every_item_kept`, `DP::test_approved_ticked_unticked_or_missing`, `DP::test_the_first_column_zero_approved_line_decides`, `DP::test_only_column_zero_lines_are_structure`, `DP::test_a_tasks_done_marker_after_approved_is_still_the_gate`, `IN::test_actions_an_unapproved_gateless_or_empty_review_emits_nothing`, `DL::test_cli_preview_gate_problems`, `DL::test_deliver_refuses_an_unapproved_document_and_writes_nothing`, `DL::test_deliver_refuses_each_refusing_problem_and_writes_nothing`, `E::test_week_from_first_start_through_hashi_apply` (`approved: false` → preview `not-approved`, deliver refused), `EE::test_deleted_approved_line_is_approved_line_missing_and_nothing_is_delivered`, `EE::test_approved_and_an_item_ticked_through_the_tasks_plugin_parse_preview_and_deliver_without_the_marker`, `S2::test_an_unticked_approved_box_is_named_and_nothing_delivered`, `S2::test_every_parse_warning_has_a_plain_language_line`, `S2::test_every_refusing_preview_problem_has_its_line[not-approved]`; R4 da0eedd9:304 (not approved said, the box named, nothing delivered); the Tasks done marker is **DL 2026-11-12 "Approved line with the Tasks done marker"** (live-walk.md defect 2, seen fixed 68459faa:64) | An unticked, indented, bare or missing Approved line read as approval, ` ✅ <date>` after it not tolerated, a set written for an unapproved document; the skill's "not approved yet" line deleted |
| F5-AC2 | script + lib + e2e + prose pin + live | `DL::test_cli_preview_returns_mode_target_place_section_and_counts`, `DL::test_cli_notices_are_shown_and_delivery_proceeds`, `DP::test_a_tomo_item_rewritten_without_its_links_is_kept_and_edited`, `DP::test_a_ticked_line_without_id_is_a_user_item_and_a_copied_id_too`, `DP::test_approved_review_record_keeps_only_kept_items_in_rendering_order`, `IN::test_actions_a_user_item_lands_like_tomos_and_an_unknown_group_does_not`, `E::test_week_from_first_start_through_hashi_apply` (`section_md` holds the rewritten theme and the added line, not the unticked item; the target and place named), `S2::test_preview_prints_the_section_target_and_place_then_asks_deliver_or_abort_and_ends_the_turn`; live-walk.md "Model-behaviour criteria": PASS 3/3 — 68459faa:80 (target, place `before Organisation`, section, `1 Deliver · 2 Abort`), 68459faa:404, 80a4605a:146; the plain-text form is **DL 2026-11-12 "the Pass 2 Deliver question stays plain text"** | `preview` not returning `section_md` with the user's text and added items, or the target and place; the skill not printing them in a fenced block, not asking `1 Deliver · 2 Abort`, or not ending the turn |
| F5-AC3 | lib + script + e2e + live | `IN::test_actions_insert_before_the_anchor_when_the_target_has_no_marker`, `IN::test_actions_insert_inside_lands_one_level_deeper_and_never_after`, `IN::test_actions_a_configured_anchor_matches_with_or_without_closing_hashes_and_emits_hashis_text`, `IN::test_actions_fences_toggle_as_hashi_toggles_them`, `IN::test_actions_a_user_heading_named_like_the_review_is_never_replaced`, `IN::test_actions_a_target_found_by_name_elsewhere_is_the_target`, `IN::test_actions_the_flat_folder_wins_over_the_year_subfolder_and_the_duplicate_is_named`, `CF::test_place_level_rule`, `CF::test_place_level_refuses_a_review_heading_above_5_because_its_groups_would_exceed_6`, `DL::test_deliver_writes_the_set_in_order_and_marks_the_document_last`, `DL::test_cli_preview_user_heading_collision_and_set_exists`, `E::test_week_from_first_start_through_hashi_apply` (one `insert_under_marker` before `In my own words`; after apply one section, the own section untouched), `E::test_target_moved_to_another_folder_is_found_by_name_and_targeted_there`; W13 Hashi run log 2026-11-12T1816 (`insert_under_marker` before `Organisation`, applied 1), the weekly note after apply: 1 heading, 1 marker (live-walk.md KPI verdicts) | The action other than one `insert_under_marker` at the configured anchor with the configured placement, an `after` placement, a user heading of the same name replaced, the review heading deeper than level 5, the landed note changed anywhere else |
| F5-AC4 | lib + script + e2e + live | `IN::test_actions_nothing_anywhere_means_a_new_note_at_the_first_candidate`, `IN::test_actions_new_note_from_the_template_variant`, `IN::test_actions_new_note_is_stamped_rendered_note_pending_move_with_a_stable_block`, `IN::test_actions_new_note_plain_when_there_is_no_template`, `IN::test_actions_new_note_inside_appends_at_the_end_of_the_anchors_section`, `IN::test_actions_new_note_keeps_the_templates_final_newline_byte_for_byte`, `IN::test_actions_new_note_template_with_a_tomo_block_falls_back_to_the_plain_note`, `IN::test_actions_new_note_template_with_an_unclosed_frontmatter_fence_falls_back_to_the_plain_note`, `DL::test_deliver_new_note_writes_the_note_first_and_moves_it`, `DL::test_cli_each_notice_is_shown_without_refusing_and_deliver_lands`, `EF::test_month_with_weekly_notes_new_note_waits_in_the_inbox_until_hashi_moves_it` (note → set → MD → mark; `move_note` inbox → monthly folder; Hashi's move lands it), `IT::TestRuleBoundaries::test_periodic_note_pending_move_is_not_a_new_source`; R9 68459faa:394 (mode `new-note`, `100 Inbox/2026-03.md` written); the vault-side caveat is **DL 2026-11-13 "The 0-writes-outside-the-inbox KPI is met for what Tomo and Kado write"** | The new note not built from the template with the section in place, not stamped `rendered-note` / `pending-move`, not written to the inbox before the set, or the set's action not a `move_note` to the periodic folder; `/inbox` picking the waiting note up |
| F5-AC5 | lib + script + e2e + live | `IN::test_actions_new_note_from_the_template_variant`, `IN::test_actions_new_note_from_a_raw_templater_template_sets_the_hint`, `IN::test_actions_new_note_with_a_vanished_variant_falls_back_to_raw`, `DL::test_cli_preview_new_note_names_the_templater_hint`, `DL::test_cli_each_notice_is_shown_without_refusing_and_deliver_lands[variant_missing]`, `DL::test_deliver_new_note_writes_the_note_first_and_moves_it` ("Templater" in the MD), `E::test_month_setup_then_new_note_targets_the_monthly_folder`, `EF::test_month_with_weekly_notes_new_note_waits_in_the_inbox_until_hashi_moves_it` (`<% tp.file.title %>` kept, "Templater" in the MD), `S2::test_every_preview_notice_is_one_line_and_the_question_still_follows[variant_missing]`; R9 68459faa:404 (the Templater notice in the preview); the frontmatter question is **DL 2026-11-13 "Setup checks whether the chosen template has a frontmatter block"** (live-walk.md defect 6, `ST::test_a_fence_that_comes_only_from_a_templater_include_is_no_block`, `ST::test_the_ok_answer_is_carried_as_a_flag_bound_to_the_template_it_answered_for`, `S::test_setup_asks_when_the_template_has_no_frontmatter_block`) | The variant not used when configured, a vanished variant not falling back to the raw template with `variant_missing`, Templater code stripped from a raw template, the hint not set or the readable MD not mentioning Templater. The MD check is one word: any mention passes |
| F5-AC6 | lib + script + e2e | `IN::test_actions_only_kept_items_land_and_empty_groups_leave_no_heading`, `IN::test_actions_only_unlanded_items_is_nothing_to_deliver_and_unlanded_items`, `IN::test_actions_an_unapproved_gateless_or_empty_review_emits_nothing`, `DP::test_tomo_items_counted_by_id_kept_unticked_deleted`, `DP::test_every_id_on_the_line_is_stripped_and_the_first_names_the_item`, `DP::test_everything_unticked_is_nothing_to_deliver`, `DP::test_an_uppercase_x_ticks_tomo_and_user_items`, `DL::test_cli_preview_gate_problems`, `DL::test_deliver_refuses_each_refusing_problem_and_writes_nothing[nothing-to-deliver]`, `E::test_week_from_first_start_through_hashi_apply` ("Taxes" absent from the section and the note), `EE::test_everything_unticked_is_nothing_to_deliver_and_nothing_is_delivered`, `S2::test_every_refusing_preview_problem_has_its_line[nothing-to-deliver]`; R9 68459faa:388 (1 unticked of 35; the section itself was not read) | An unticked or deleted item landing, a group with nothing ticked keeping its heading, an all-unticked document delivered instead of refused `nothing-to-deliver` |
| F5-AC7 | lib + script + prose pin + live | `IN::test_actions_a_missing_place_names_the_notes_headings`, `IN::test_actions_a_review_heading_above_level_5_is_place_too_deep`, `IN::test_actions_a_marker_with_no_heading_above_it_is_place_missing`, `IN::test_actions_new_note_template_without_the_anchor_is_place_missing`, `IN::test_hashi_mirror_a_crlf_target_has_no_heading_to_hashi_and_is_place_missing`, `CF::test_setup_place_level_finds_the_anchor_case_sensitively`, `DL::test_cli_preview_place_problems_name_the_notes_headings`, `DL::test_deliver_place_anchor_uses_the_users_heading`, `DR::test_the_record_never_holds_a_heading_of_the_notes_own`, `S2::test_every_refusing_preview_problem_has_its_line[place-missing]`, `S2::test_the_heading_pick_names_the_place_fields_the_refusal_carries`, `S2::test_the_replace_mode_branch_covers_all_three_problems_and_comes_before_the_heading_pick`, `S2::test_a_collision_after_a_heading_pick_ends_with_start_over_or_abort_never_a_second_pick`, `S2::test_place_anchor_goes_to_preview_and_deliver`; R14 80a4605a:81 (anchor missing said before delivering, the headings listed, `0 Abort`), 80a4605a:88, :95 (Abort left everything unchanged) | An absent anchor not reported `place-missing` with the note's headings before any write, a chosen heading not used by `preview` and `deliver`, the heading stored in meta; the skill's pick-or-abort lines deleted or the pick offered twice |
| F5-AC8 | lib + script + schema + e2e + live | `IN::test_actions_every_set_validates_against_both_schemas` (the producer schema, `hashi-instructions.schema.json` and Hashi's vendored copy, insert / replace / new-note), `IN::test_actions_replace_anchors_the_heading_as_hashi_reads_it_closing_hashes_kept`, `IN::test_hashi_mirror_a_heading_line_holding_a_js_line_terminator_is_no_heading`, `IN::test_hashi_mirror_a_bom_after_the_hashes_is_whitespace_and_trimmed`, `IN::test_hashi_mirror_characters_outside_ecmascripts_set_are_text`, `DL::test_deliver_writes_the_set_in_order_and_marks_the_document_last` (`### I01 —`, `- [ ] Applied`, `doc_type: instructions` peer), `HS::test_replace_section_present_in_tomo_producer`, `HS::test_replace_section_validates_against_both_schemas`, `IT::TestReviewDocumentIsSkipped::test_approved_review_is_skipped_silently` (the set is `/inbox`'s Pass 2 shape, not re-triaged); Hashi run logs 2026-11-12T1816 (W13, `I01 insert_under_marker` applied) and 2026-11-13T1031 (month, `I01 move_note` listed and validated, `skipped-already`) | A delivered set failing a schema, an anchor Hashi's heading regex would not resolve (CRLF, JS line terminators, closing hashes), the MD peer not stamped as instructions. The vendored-copy case joins the parametrisation only while `/Volumes/Moon/Coding/MiYo/Hashi/src/schema/instructions.schema.json` exists (it did on this run); on a checkout without the Hashi sibling the two repo copies alone are checked, without a skip marker. "Hashi lists and validates it" is Hashi's behaviour, evidenced by its run logs |
| F5-AC9 | lib + script + e2e | `RM::test_insert_content_is_fenced_not_quoted`, `RM::test_replace_content_is_fenced_not_quoted`, `RM::test_fence_outgrows_the_longest_backtick_run`, `RM::test_fenced_content_keeps_a_line_separator_inside_a_line`, `RM::test_fenced_content_keeps_a_trailing_blank_line`, `RM::test_insert_before_names_the_anchor_heading`, `RM::test_insert_inside_names_the_anchor_heading`, `RM::test_insert_keeps_target_and_anchor_lines`, `RM::test_replace_section_has_its_own_heading`, `RM::test_replace_section_says_what_is_discarded_and_what_stays`, `RM::test_every_section_action_keeps_the_peer_checkbox_format`, `RM::test_a_backtick_in_the_anchor_does_not_break_the_line`, `DL::test_deliver_writes_the_set_in_order_and_marks_the_document_last` (the MD carries the anchor and the fenced section), `DL::test_deliver_new_note_writes_the_note_first_and_moves_it` (From / To and Templater in the MD), `EF::test_drop_after_a_partial_delivery_leaves_only_a_withdrawn_set` ("delete these files" names every file); R5/R9 (`paths.set_md` written; its text was not read) | The section rendered as a blockquote or altered byte-wise inside the fence, the target or anchor line missing, `replace_section` falling to the unknown-action fallback, the new note's From / To missing |
| F5-AC10 | lib + script + e2e + prose pin + live | `DL::test_deliver_interrupted_at_any_step_resumes_without_duplicates`, `DL::test_deliver_doc_changed_stops_at_doc_mark_and_resumes_after_saving`, `DL::test_deliver_doc_mark_refusal_is_doc_changed_only_for_kados_conflict_code`, `DL::test_deliver_mark_is_idempotent_when_the_write_landed_unrecorded`, `DL::test_drop_after_a_partial_delivery_withdraws_the_set`, `DL::test_drop_before_any_step_removes_only_the_stage`, `DL::test_drop_after_the_note_step_began_withdraws_and_names_the_note`, `DL::test_drop_refuses_a_set_hashi_already_applied_and_writes_nothing`, `DL::test_drop_set_changed_under_the_guard_is_stopped_and_resumable`, `DL::test_drop_that_failed_after_the_set_write_is_listed_again_and_a_second_drop_completes_it`, `DR::test_doc_changed_names_why_kado_refused_the_mark`, `DR::test_resume_reports_the_recorded_plan_not_the_replan`, `DR::test_the_plan_is_recorded_with_the_first_in_flight_mark`, `RR::test_resume_after_the_set_json_landed_overwrites_the_old_md_and_keeps_its_own_set`, `SD::test_a_landed_target_with_identical_text_counts_as_done_without_a_write`, `SD::test_the_step_is_persisted_as_in_flight_before_its_upload`, `SD::test_a_done_step_whose_target_is_absent_is_never_written_again`, `RS::test_failed_step_in_meta_is_failed_delivery`, `RS::test_begun_delivery_without_failed_step_is_failed_delivery_not_open`, `RS::test_withdrawn_is_tested_before_the_begun_delivery_reading`, `RL::test_open_reviews_lists_a_half_withdrawn_stem_as_failed_delivery_until_meta_says_withdrawn`, `RF::test_a_begun_delivery_without_doc_mark_whose_set_is_gone_stays_failed_delivery`, `EF::test_delivery_failure_at_each_step_is_offered_as_failed_delivery_and_resumes_once`, `EF::test_drop_after_a_partial_delivery_leaves_only_a_withdrawn_set`, `EF::test_half_withdrawn_drop_is_listed_again_resume_refuses_and_a_second_drop_completes`, `S::test_every_listed_state_has_its_offer[failed-delivery]`, `S2::test_deliver_branches_on_status_then_problems_or_failed_step`, `S2::test_drop_reports_withdrawn_dropped_already_applied_and_set_changed`, `S2::test_drop_kado_write_failed_names_the_partial_withdrawal_and_reruns_once`, `S2::test_set_withdrawn_routes_from_the_deliver_step_into_drop`; R15–R17 80a4605a:152-157, :185, :233-240 (stopped at `doc_mark`, Resume offered twice, completed); the `reason` and the recorded plan are **DL 2026-11-13 "doc-changed now carries reason"** (live-walk.md defect 5, fix 88773c67 **not re-walked**); the resume re-plan is **DL 2026-11-13 "Known gap"** (§7) | A failed step not recorded before the upload, the next `start` not listing `failed-delivery`, a resume writing a landed payload again or marking twice, a drop leaving a set Hashi would apply, or withdrawing one Hashi applied; the skill's Resume / Drop lines deleted |
| F5-AC11 | script + e2e + prose pin only | `DL::test_deliver_writes_the_set_in_order_and_marks_the_document_last` (first line `… — geliefert`, state `approved`), `DL::test_deliver_mark_is_idempotent_when_the_write_landed_unrecorded`, `DR::test_a_fresh_delivery_reports_the_plan_it_recorded`, `DR::test_resume_reports_the_recorded_plan_not_the_replan`, `DR::test_resume_target_appeared_compares_pass1_with_the_recorded_mode`, `E::test_week_from_first_start_through_hashi_apply` (`# 2026-W13 Review — delivered`, `paths.set_json` / `set_md`, `next: hashi-or-by-hand`), `S2::test_deliver_branches_on_status_then_problems_or_failed_step` (target, place, paths, the "Next" line); R5/R9/R17: `delivered` / `resumed` output (68459faa:86, :413; 80a4605a:233-240, the report named the re-plan's mode — the defect fixed in 88773c67, not re-walked). The report's wording itself was not read | `deliver` not returning target, place and the paths, not marking the document's first line, or a resume reporting the re-plan; the skill's report line deleted. That the model names all four and the next step is unobserved |
| F6-AC1 | script + e2e + prose pin + live | `DC::test_existing_tomo_review_is_review_exists_and_never_overwritten` (`doc_path` named, nothing touched), `DP::test_replace_without_confirm_needs_confirm_and_names_the_document`, `DP::test_replace_confirm_writes_over_tomos_document_resets_meta_and_deletes_stage_files`, `DP::test_replace_confirm_on_a_non_tomo_document_is_still_doc_name_taken`, `DP::test_replace_abort_deletes_the_content_files_and_leaves_document_and_meta`, `E::test_rerun_replaces_the_section_instead_of_adding_a_second` (`review-exists` → `needs-confirm` → `--confirm`), `S::test_review_exists_asks_twice_before_replacing`, `S::test_every_listed_state_has_its_offer[open]` (Start over routes through `write`'s refusal), `S::test_every_status_of_replace_confirm_has_a_branch_in_the_write_list`; R11 3a862c54:204-206 (`review-exists`, `1 Replace · 2 Keep it` asked; the run ended there) | `write` overwriting Tomo's own document, `replace` writing without `--confirm` or not naming the document, the skill's second question deleted. The Replace answer was never given live |
| F6-AC2 | lib + script + e2e + prose pin | `DL::test_deliver_refuses_a_second_set_for_the_same_stem`, `DL::test_cli_preview_user_heading_collision_and_set_exists`, `RR::test_deliver_refuses_a_set_that_is_not_fully_applied`, `RR::test_deliver_writes_the_new_set_over_a_fully_applied_one`, `RR::test_deliver_over_an_applied_set_that_hashi_rewrote_meanwhile_stops_resumably`, `RS::test_every_action_applied_is_applied`, `RS::test_a_fresh_record_over_a_fully_applied_set_reads_open_and_all_applied_needs_an_action`, `RS::test_an_unreadable_set_reads_delivered_never_applied_or_withdrawn`, `RF::test_a_fresh_record_without_applied_reported_beside_an_applied_set_reads_open`, `SE::test_start_probes_the_set_json_of_approved_documents_and_lists_a_delivered_review_as_delivered`, `E::test_week_from_first_start_through_hashi_apply` (a second `deliver` → `set-exists`), `E::test_rerun_replaces_the_section_instead_of_adding_a_second` (the rerun writes its set over the applied one under its `modified` stamp), `S::test_every_listed_state_has_its_offer[delivered]`, `S2::test_every_refusing_preview_problem_has_its_line[set-exists]`; the second half is **DL 2026-11-12 "Rerun of an applied review: deliver writes a new set over the old one"**. The `delivered` one-liner was not seen live | A second set written while one waits (`set-exists` missing), a partly applied set overwritten, a fully applied one refused or overwritten unguarded; the skill's `delivered` and `set-exists` lines deleted |
| F6-AC3 | lib + script + e2e | `IN::test_actions_rerun_replaces_the_section_above_the_marker_and_hashi_sees_it_as_landed`, `IN::test_actions_rerun_finds_the_marker_under_a_renamed_heading`, `IN::test_actions_a_marker_of_another_period_does_not_count`, `IN::test_actions_an_indented_marker_copy_is_not_the_marker`, `IN::test_actions_a_marker_under_a_heading_an_earlier_user_heading_shadows_is_a_collision`, `DL::test_cli_notices_are_shown_and_delivery_proceeds`, `RR::test_deliver_writes_the_new_set_over_a_fully_applied_one`, `E::test_rerun_replaces_the_section_instead_of_adding_a_second` (same and renamed heading: `replace_section`, after apply one section, one heading, the own section untouched, the first run's applied set still in the inbox), `EF::test_set_deleted_after_apply_is_not_listed_and_the_period_starts_over`, `S2::test_a_replace_preview_says_the_section_is_replaced_not_added`, `S2::test_every_preview_notice_is_one_line_and_the_question_still_follows[heading-renamed]`; not applied live (the March monthly note vanished, live-walk.md KPI "0 periodic notes with two Tomo review sections": month not checkable) | A second section added instead of `replace_section` on the marker's heading, a renamed heading not found, another period's marker taken, the earlier run's applied set having to be deleted first; the "replaced, not added to" line deleted |
| F6-AC4 | lib + script + e2e + prose pin only | `DL::test_deliver_switches_from_new_note_to_insert_when_the_target_appeared`, `DR::test_resume_target_appeared_compares_pass1_with_the_recorded_mode`, `RS::test_move_refused_when_the_target_and_the_inbox_copy_both_exist`, `RS::test_stem_state_probes_the_move_source_first_and_the_destination_only_while_it_exists`, `DL::test_cli_status_and_start_agree_on_delivered_move_refused_applied_and_withdrawn`, `E::test_target_created_between_the_passes_turns_new_note_into_insert` (no inbox note written, `insert_under_marker`), `S::test_every_listed_state_has_its_offer[move-refused]`, `S2::test_every_preview_notice_is_one_line_and_the_question_still_follows[target_appeared]`; the refused move is Hashi's: run log 2026-11-13T1031 `I01 move_note` → `skipped-already` (live-walk.md, vault-side effect 1). Tomo's `move-refused` line was not seen live | A new-note plan kept after the target appeared, `move-refused` not read when both the target and the inbox copy exist, or read for an applied move; the skill's two lines deleted |
| F7-AC1 | script + lib + document review | `PV::test_no_marker_on_stderr_of_any_script`, `PV::test_a_forced_exception_leaves_only_its_class_name_on_stderr`, `PV::test_bad_invocations_echo_no_marker`, `PV::test_no_marker_in_stdout_outside_the_named_fields`, `PV::test_named_fields_carry_only_their_own_kinds`, `PV::test_every_named_field_carried_its_marker_once`, `PV::test_every_script_and_every_subcommand_ran_in_the_walk`, `PV::test_no_marker_in_tomos_working_files_after_any_step`, `PV::test_a_readable_tracker_value_stays_in_read_json_and_the_document`, `PV::test_read_and_proposal_files_are_gone_after_write_and_abort_and_kept_after_a_refusal`, `DC::test_proposal_text_never_reaches_stdout_or_stderr`, `DC::test_pass1_counts_in_meta_and_content_files_deleted`, `DP::test_write_records_only_link_stem_lists_per_tomo_item`, `DP::test_a_low_entropy_habit_line_is_not_recoverable_from_meta`, `DP::test_parse_reads_the_document_prints_counts_only_and_writes_no_file`, `DR::test_the_record_never_holds_a_heading_of_the_notes_own`, `RD::test_an_unexpected_exception_prints_only_the_class_name`, `SE::test_unexpected_exception_exits_1_with_the_class_name_only`, `DL::test_cli_exit_codes_and_a_bare_class_name_on_stderr`, `SD::test_fail_names_the_step_and_the_error_class_on_stderr`, `S::test_rules_hold_each_line[privacy]`; **cost records**: no test — `docs/evolution/inbox-cost-log.md` §"Spec 045 — T6.3 live walk" and live-walk.md carry run ids, cost, duration, calls and counts only (checked by reading) | A marker from the daily text, a journal answer, a tracker value or a proposal reaching stderr, stdout outside the six allow-listed fields, `meta.json`, a setup input or any `tomo-tmp/` file other than `read.json` / `proposals.json`; a top-level handler printing an exception message. `test_user_text_fields_give_a_reason_each` checks the test's own allow-list and is not cited. The cost log is hand-written: a text leak there is a review finding, not a red test |
| F7-AC2 | document + script | `PD::test_names_every_place_read_content_rests`, `PD::test_removal_is_the_users_choice_and_protection_is_recommended`, `PD::test_metadata_only_is_scoped_to_tomos_own_records`, `PD::test_read_json_and_proposals_json_are_deleted_on_write_or_abort`, `PD::test_read_json_is_named_as_left_behind_by_an_unfinished_session`, `PD::test_removing_the_delivered_inbox_files_is_the_users_job`, `PD::test_setup_guide_links_to_the_privacy_section`, `PV::test_read_and_proposal_files_are_gone_after_write_and_abort_and_kept_after_a_refusal` (the behaviour the document describes); the wording is **DL 2026-11-11 "F7-AC2 cleanup promise replaced by documentation"** | `PRIVACY.md` losing the transcripts-in-the-container-home, `tomo-tmp` or inbox place, "your choice", or the encrypted-disk recommendation; `write` or `replace --abort` leaving `read.json` / `proposals.json` behind |
| F8-AC1 | lib + script | `HB::test_boolean_counts_days_true_over_days_with_value`, `HB::test_integer_average_over_days_with_value`, `HB::test_duration_averaged_in_minutes_and_rendered_back`, `HB::test_time_averaged_in_minutes_since_midnight_rendered_hh_mm`, `HB::test_time_average_is_circular_on_the_clock`, `HB::test_duration_average_is_arithmetic_not_circular`, `HB::test_text_trackers_are_skipped`, `HB::test_a_day_outside_the_period_is_ignored`, `HB::test_tracker_defs_reads_the_three_lists_in_order`, `DY::test_plain_and_bold_fields_parsed_as_raw_strings`, `DY::test_read_day_then_attribute_feeds_review_habits_as_is`, `CF::test_tracker_types_reads_all_three_lists_and_tolerates_junk`, `DC::test_groups_in_order_with_nothing_found_lines_and_ids` (`Sport: 6 von 6 Tagen (7 Tage im Zeitraum; fehlt: 2026-03-28)` from `read.json`), `DC::test_habits_come_from_the_tracker_values_and_are_absent_without_them` (a model-proposed `habits` group refused), `PV::test_a_readable_tracker_value_stays_in_read_json_and_the_document` (`Energy: average 434343.0 over 1 days`); R3/R6 (h12: twelve habit items per document) | A boolean not counted over the days with a value, a number / duration / time not averaged (a time arithmetically instead of circularly), a text tracker given an item, the habits taken from the model instead of the script |
| F8-AC2 | lib + script + e2e | `HB::test_boolean_dash_is_a_placeholder_listed_as_missing_not_false`, `HB::test_dash_is_missing_not_unreadable_for_every_type`, `HB::test_word_for_a_number_is_unreadable_never_zero`, `HB::test_boolean_number_is_unreadable_not_false`, `HB::test_empty_value_is_missing_not_unreadable`, `HB::test_unrun_templater_tag_is_unreadable_for_every_type`, `HB::test_huge_digit_runs_are_unreadable_never_a_raise`, `HB::test_yesterday_field_value_counts_for_the_day_it_is_listed_under`, `HB::test_unreadable_value_is_named_by_the_date_it_is_listed_under`, `HB::test_english_line_for_a_count_names_missing_and_unreadable`, `DY::test_a_bare_dash_value_passes_through_unchanged`, `DY::test_yesterday_fields_are_separated_from_todays`, `DY::test_attribute_yesterday_moves_fields_to_the_day_before`, `DY::test_attribute_yesterday_drops_fields_of_the_day_before_the_period`, `DY::test_attribute_yesterday_skips_a_gap_day`, `DY::test_read_day_then_attribute_feeds_review_habits_as_is`, `PR::test_day_after_period_is_read_for_its_yesterday_fields_only`, `PR::test_absent_day_after_leaves_the_last_days_value_missing`, `PR::test_real_review_day_reads_a_week_through_the_period_reader`, `GAP::test_a_month_reads_the_day_after_it_for_the_last_days_yesterday_fields` (new, §3), `DC::test_groups_in_order_with_nothing_found_lines_and_ids` (the `-` day named `fehlt`, not counted), `PV::test_every_marker_reached_the_scripts` (2026-03-24 / 25 named unreadable for Sleep / Sport in the document); INT `test_the_day_after_daily_is_read_for_the_week_and_absent_for_the_month` (the live vault has no 2026-04-01 daily, so the month's day after is absent there — a vault fact, §3) | A `-`, an empty or an unparsable value counted as zero or not named, a yesterday field left on the day it is written in, the day after the period not read for any period kind (gap, §3) |
| F8-AC3 | lib + script | `HB::test_no_trackers_gives_empty_result`, `HB::test_tracker_without_a_value_on_any_day_is_absent`, `HB::test_only_unreadable_values_give_no_item`, `HB::test_only_dashes_give_no_item_for_every_type`, `HB::test_no_values_at_all_gives_empty_result`, `HB::test_tracker_defs_without_trackers_is_empty`, `DC::test_habits_come_from_the_tracker_values_and_are_absent_without_them` (no `Gewohnheiten` heading without trackers) | An item for a tracker with no value, or the habits heading rendered for a vault without trackers |

## 3. Gaps the trace found

### Closed

Three criterion parts had no test that could fail. Each is closed by a test in `tests/test_045_close_out_gaps.py`. Each test was proven RED by applying the mutation below in a fresh isolated export (`git archive HEAD | tar -x -C $TMPDIR/045-co-mut-<name>`, the new test file copied in, `PYTHONDONTWRITEBYTECODE=1`), never in the worktree. Before the gap file existed, each mutation was run against the traced tests and left them green; with the gap file, each mutation turns exactly its own test red.

| # | Criterion | Part no test could fail | Test | Mutation → failure |
|---|---|---|---|---|
| M1 | F4-AC2 | the group definitions the model sorts by — what `done`, `open`, `themes` (at least two days), `growth`, `weekly_only` and `not_in_weekly` hold, and that an empty group is left out | `test_the_groups_are_defined_for_the_model_with_the_two_day_theme_rule` | `periodic-review/SKILL.md` step 5, the bullet `` - `done`: what happened and got done; … Leave out a group with nothing to propose. `` deleted → `test_review_skill.py`, `_pass2.py`, `_contract.py`, `test_review_why_docs.py`, `test_review_sdd_map.py`: `318 passed`; with the gap file: `1 failed, 221 passed` (`AssertionError` on the line) |
| M2 | F4-AC5 | "Every item is in `<language>`" — the only place the setup language reaches the model's proposal text | `test_every_proposal_is_written_in_the_setup_language` | step 5, `` - Every item is in `<language>`; its `sources` … `` reworded to `` - Its `sources` … `` (the language clause dropped) → the same five files `318 passed`; with the gap file: `1 failed, 221 passed` |
| M3 | F8-AC2 | the month's last day: the reader reads the day after the period for every period kind, so a yesterday field on 1 April counts for 31 March (inv point raised in the trace: the live vault has no 2026-04-01 daily, so `INT::test_the_day_after_daily_is_read_for_the_week_and_absent_for_the_month` pins a vault fact, not the reader) | `test_a_month_reads_the_day_after_it_for_the_last_days_yesterday_fields` | `lib/review_period.py` `_find_dailies`: `for day in self.period.days() + [self.after]:` → `… + ([self.after] if self.period.kind == "week" else []):` → every review test file plus `test_period.py`, `test_week_rule_inference.py`, `test_staged_delivery.py`, `test_instruction_render_section_actions.py`: `1 failed, 1784 passed, 13 skipped` — the gap test alone (`assert {} == {"Mood": "9"}`); the ten `-m integration` tests and three others skip as on HEAD |

The month fixture `tests/review_period_fixtures.py::month_vault` already held the 1 April daily with `Y-Mood:: 9`; no test read it. The gap test drives `lib.review_period.read_period` with the fixture's stub readers, so it pins the reader's orchestration (which day is read, where its fields go), not `lib.review_day`'s attribution, which `DY::test_attribute_yesterday_moves_fields_to_the_day_before` pins.

The two prose pins were found by script: every line of `periodic-review/SKILL.md` was checked against the string constants of the `test_review_skill*.py` files (`ast`-parsed, whitespace collapsed). Of 118 body lines, 5 had no pin at all and 2 of those name a criterion part (M1, M2); the other three are "Ask in the language the user writes in" (no PRD criterion; chat language is the owner's choice, DL 2026-11-12), the `<stem>` derivation and the `$ARGUMENTS` quoting line (script contract, covered by `SC::test_each_review_call_in_any_skill_parses_with_the_scripts_argparse`).

### Doubted tests, read

- `E::test_setup_abort_saves_nothing_and_writes_nothing` runs no abort path: the Abort is the absence of further calls after `match`. It proves `match` has no side effect, which is what F1-AC10 needs from the script; the skill's Abort line is the prose pin.
- `E::test_every_write_attempted_so_far_was_under_the_inbox_prefix` (and its two siblings) read a module-level list: run alone they pass on an empty list. The per-test inbox check is the `walk` / `ready` fixture teardown, which fails as an ERROR, not a FAIL; both are red in the invocation of §1.
- `RD::test_a_week_run_prints_the_per_day_report_and_writes_read_json` checks growth as `moc_folders == 1` only; F3-AC7's content is `PR::test_growth_lists_created_notes_with_links_mocs_changed_and_mocs_linked_across_pages`.
- `DL::test_deliver_new_note_writes_the_note_first_and_moves_it` and `EF::test_month_with_weekly_notes_new_note_waits_in_the_inbox_until_hashi_moves_it` pin F5-AC5's readable instruction as the word "Templater" in the MD; any mention passes.
- `PC::` Part 1 (16 tests over `tests/review_fake_vault.py`) tests the fake, not production; none is cited. `PC::test_fake_accounting_matches_the_real_client_on_one_429_scenario` ties the fake to `KadoClient` and is cited.
- `DY::test_unreadable_linked_note_reported_the_same_way` simulates "unreadable" as `read_note` → None, the same as missing; the period reader's `failed` state (`PE::test_a_linked_note_that_still_fails_is_marked_failed`) is what tells the two apart, so F3-AC8 cites both.

## 4. Live walk and the consumer's side

The model-behaviour criteria the plan named (F1-AC6, F4-AC5, F4-AC7, F5-AC2) are recorded in [`live-walk.md`](live-walk.md) "Model-behaviour criteria": F4-AC5 PASS, F5-AC2 PASS 3/3, F1-AC6 and F4-AC7 **not reachable** on the test vault (the weekly notes show the week rule; the setup lists no own sections) — prose pin only.

Beyond those four, the walk gives live evidence for F1-AC1, F1-AC2, F1-AC3, F1-AC7, F1-AC8, F1-AC9 (the save), F1-AC10, F2-AC1, F2-AC2, F2-AC3, F2-AC8, F3-AC1, F3-AC5, F3-AC7, F3-AC8, F3-AC9, F4-AC1, F4-AC2, F4-AC3 (KPI count), F4-AC4, F5-AC1, F5-AC3, F5-AC4, F5-AC5, F5-AC7, F5-AC8, F5-AC10, F6-AC1 (the question, not the answer) and F8-AC1 — the rows above cite the line. Not walked at all: F1-AC5, F2-AC4, F2-AC5, F2-AC6, F2-AC7, F2-AC9, F3-AC6, F3-AC10, F3-AC11, F3-AC12, F3-AC13, F4-AC6, F6-AC3 (applied), F6-AC4 (Tomo's line), F8-AC2 (unreadable values), F8-AC3.

Fixes the walk produced that were **not re-walked**: `88773c67` (`doc-changed` reason `open-unsaved`, the resume report) and `586277fa` answer 2 (the Tomo-variant stop); §7.

Consumer-owned halves: F5-AC8 "Hashi lists and validates it" and F6-AC4 "the apply refuses the move" are Hashi's behaviour. Evidence: every generated set validates against Hashi's vendored schema copy (`IN::test_actions_every_set_validates_against_both_schemas`, byte-identical to `tomo/schemas/hashi-instructions.schema.json`, README Phase 4), and Hashi's run logs `100 Inbox/tomo-hashi-run-log_2026-11-12T1816.md` (W13 insert applied) and `…_2026-11-13T1031.md` (month move `skipped-already`: the target existed, the inbox copy stayed).

## 5. KPIs

| KPI (requirements.md Success Metrics, v1.7) | Measured (live-walk.md) | Verdict |
|---|---|---|
| Adoption: 4 consecutive finished weeks in the live vault after release | not measured: every run was on `tomo-instance` and the test vault | open, measured from release |
| Engagement: ≤ 40 % of Tomo's proposals unticked or deleted (habits excluded) | 1 of 56 (1.8 %) over W13 and the first month delivery; the owner edited nothing | PASS; says little about the proposals' quality (live-walk.md caveat) |
| 0 writes to the vault outside the inbox before apply | Kado audit-log windows: inbox paths only, plus read probes of the target and the template. Vault side: Templater moved the raw-template month note and backlinking notes were restamped (65 notes changed mtime (31 dailies, 30 5-Year-Journal notes, 4 weekly notes; plus one hierarchy MOC); likely chain Templater move → Obsidian link updates → update-time-on-edit stamps (all sampled notes link `[[2026-03]]` and carry `Updated: 2026-11-13 09:01`), not fully proven) (DL 2026-11-13 "recorded as a vault-side caveat, not a Tomo write") | PASS for Tomo and Kado; vault-side caveat on the raw-template new-note path, now gated by the setup question (`586277fa`) |
| 0 delivered proposals without a source-day link | 0 of 21 / 35 / 24 | PASS |
| 0 periodic notes with two Tomo review sections | W13: 1 heading, 1 marker after apply; the March note vanished, not checkable | PASS for W13; month not checkable |
| Weekly Pass 1 ≤ $0.50 | R3 $0.469 / 48 s, warm session; cold not measured | PASS (margin $0.031, warm) |
| Monthly Pass 1 ≤ $2.00 and ≤ 7 min | R6 $0.909 / 161 s, R8 $0.532 / 92 s, R11 $0.869 / 155 s, R13 $0.682 / 132 s; 7 min is DL 2026-11-12 | PASS, all four |
| Pass 2 ≤ $0.75 (raised from $0.20, DL 2026-11-13) | R5 $0.322, R9 $0.663 (at the `deliver` call $0.270 / $0.526) | PASS under the raised KPI; FAIL under the original |
| Kado calls: week ≤ 45, month ≤ 170 (SDD Quality Requirements, DL 2026-11-12) | 41 / 165 live, 0 retried; `RD::test_a_week_stays_within_forty_five_calls_without_retries`, `RD::test_a_month_run_reports_the_weekly_notes_and_stays_within_the_call_budget` | PASS |

Costs are counted once per API message id (live-walk.md "Method"); `scripts/tomo-session-stats.py` overstates by about 2× (§7). **Spend:** the walk cost $7.51 over 19 runs; this close-out ran no paid eval: $0.

## 6. Validation

- **The single invocation (§1):** `725 passed in 8.34s`.
- **Gap tests on the real tree:** `3 passed in 0.09s`.
- **Mutations (§3):** M1 `1 failed, 221 passed`; M2 `1 failed, 221 passed`; M3 `1 failed, 1784 passed, 13 skipped` — each the gap test alone.
- **ruff:** `./venv/bin/ruff check tomo scripts tests` → `All checks passed!`
- **Full pytest (worktree, 2026-11-13, HEAD a2f1daa6 plus the gap file):** `9925 passed, 18 skipped, 1 deselected, 1 warning in 370.62s (0:06:10)` — the deselected one is the known unrelated `tests/ide_bridge/test_configure_ide_bridge.py::test_install_smoke_ide_bridge_block_exists`; the known clock flake `tests/test_039_t3_4_folder_not_consumed_yet.py::test_both_surfaces_agree_with_each_other` passed on this run; the 18 skips are the ten `-m integration` tests (`TOMO_LIVE_KADO` unset) and eight environment skips outside this spec (the eval probe's source trace, the gitignored `_outbox` attachment, the faster-whisper model directory, a garden-audit fixture not in the checkout, and the like), listed by `-rs` over the files that can skip.

## 7. Open items

Verbatim list for the owner (not fixed in this round), each marked **test/doc hygiene**, **behaviour gap** or **admin**:

- **Resume re-plan gap** (DL 2026-11-13 "Known gap"): a resume re-plans and writes still-undone set steps from the re-plan, so a vault change between stop and resume can land a set that contradicts the note already written. — **behaviour gap**
- **Not re-walked:** `88773c67` (open-unsaved reason, resume report) and `586277fa` answer 2 (variant stop). — **admin** (owner walk)
- **Cold-session weekly Pass 1 cost not measured;** `scripts/tomo-session-stats.py` double-counts repeated `usage` (≈2× cost); older cost-log rows unchecked. — **behaviour gap** (the stats script), **admin** (the measurement and the rows)
- **Skill text (~22k chars) loaded per `/review`** — Pass 2 cost cut to backlog. — **admin** (backlog)
- **Polish:** after answering `1` at the frontmatter question the model re-ran `match` and named `needs_template_ok` to the user (269b1964:83, :142). — **behaviour gap** (skill wording)
- **Resume without `--place-anchor` after a picked-heading delivery runs into `place-missing`.** — **behaviour gap**
- **Kado handoff:** both CONFLICT cases share one code and one hint ("file changed"). — **admin** (handoff to Kado)
- **File size:** `review-instructions.py` 577 lines, `review-session.py` 531 lines (L2 300–500) — extract helpers (`lib/review_match.py`, delivery helpers into `lib/review_delivery.py`); `DeliveryStop.reason` as a declared field; `test_review_deliver_report.py` fixture import → shared helper. — **test/doc hygiene** (refactor)
- **Earlier queue:** T6.2 test hygiene (duplicate assert in test_review_integration ~:214-218, the `-m integration` docstring, `KadoAuthError` should fail not skip) — **test/doc hygiene**; review_state step numbers vs SDD, named predicates, docstring order paragraph, the test_review_state_listing helper import — **test/doc hygiene**; the Directory Map test message — **test/doc hygiene**; the pacer constants test — **test/doc hygiene**; SDD Interface `place.level?` — **test/doc hygiene**; ruff-format not enforced — **admin**; `review_md` ➕ wording, `✅️` variation selector not stripped, docstring reflow — **behaviour gap** (the variation selector), **test/doc hygiene** (the rest); a typed template name not found is not reported — **behaviour gap**; a typed anchor wins after a template correction — **behaviour gap**; a bare "stop" inside an entry is ambiguous — **behaviour gap** (skill); a same-named heading costs one pick before the rename advice — **behaviour gap**; with a saved rule and disagreeing notes setup asks once per setup — **behaviour gap**; GitHub issue for a lone `%%` — **admin**; `docs/XDD/README.md` index entry — **admin**; tcs-git-helpers v2.2.43 update — **admin**; skill-author audit of periodic-review SKILL.md — **admin**.

Found by this trace, beside the list above:

- **F7-AC1 cost records** have no test; the cost log is hand-written. — **test/doc hygiene** (accepted: nothing to automate)
- **The Hashi vendored-schema check is silently conditional** on the sibling checkout (`HASHI_VENDORED.exists()` joins the parametrisation without a skip marker, `IN::test_actions_every_set_validates_against_both_schemas`, `DL::test_deliver_writes_the_set_in_order_and_marks_the_document_last`). — **test/doc hygiene**
- **`PV::test_user_text_fields_give_a_reason_each`** checks the test's own allow-list; no production change turns it red. — **test/doc hygiene**
- **`SE::test_start_stdout_carries_no_note_text`** cannot fail as things stand: `start` never reads note bodies, so the marker never reaches it. — **test/doc hygiene**
- **F5-AC5's readable instruction** is pinned as the word "Templater" only. — **test/doc hygiene**

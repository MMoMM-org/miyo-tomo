---
title: "Close-out — 046 /review: review material for the user's own template sections"
status: complete
---

# Close-out

## Standing rule for this document

Every acceptance criterion below traces to evidence that was **executed**, not to a task that mentions it:

- Criteria about scripts, libs, schemas, the writer, the documents and the fake-vault walks trace to pytest node ids, all run in the one invocation of §1. The test body was read for every cited id; a name or docstring was never taken as the evidence.
- Criteria about what the model does in the dialogue trace to a **prose pin** (a `tests/test_review_skill*.py` or `tests/test_046_t*_skill*.py` assertion that the imperative exists in `periodic-review/SKILL.md`). A prose pin is red when the imperative is deleted or reworded; it is never evidence that the model obeys it. Live evidence is a T6.3 walk note in [`plan/phase-6.md`](plan/phase-6.md) (rounds 1, 2, 3a, 3b) or a Hashi results handoff of the joint run. Where a dialogue criterion has a prose pin and no live evidence, the trace says so.
- The live walk was recorded in the T6.3 notes and in the joint-run handoffs, not in a `live-walk.md`; the walk did not record the planned section-fit rows (§4).
- `tests/test_review_integration.py` (`-m integration`, live Kado) is not in the invocation.

For each criterion the trace names the **mechanism** the evidence falsifies: the concrete change that would turn it red.

`requirements.md` and `solution.md` were not edited by this close-out.

## Criteria count

The plan says **49**. The PRD (v1.3) has **49**: F1:10 F2:12 F3:6 F4:7 F5:5 F6:6 F7:3, counted as the `- [ ] F<n>-AC<m>` lines under Feature Requirements. No difference.

**49/49 trace to executed evidence that can fail for their script part.** By class:

- **23 trace to script, lib, e2e, golden or schema tests alone, or with a prose pin only for wording**: F1-AC8, F1-AC10, F2-AC4, F2-AC5, F2-AC8, F3-AC1, F3-AC2, F3-AC3, F3-AC4, F3-AC5, F3-AC6, F4-AC1, F4-AC2, F4-AC3, F4-AC5, F4-AC7, F5-AC1, F5-AC2, F5-AC5, F6-AC3, F6-AC4, F6-AC5, F6-AC6.
- **26 have a model-behaviour part** that rests on a prose pin beside the script tests: F1-AC1 to F1-AC7, F1-AC9, F2-AC1, F2-AC2, F2-AC3, F2-AC6, F2-AC7, F2-AC9, F2-AC10, F2-AC11, F2-AC12, F4-AC4, F4-AC6, F5-AC3, F5-AC4, F6-AC1, F6-AC2, F7-AC1, F7-AC2, F7-AC3. Of these, **2 also have live evidence for the model part**: F1-AC6 (round 3b, a `double-placement` refusal pair, the one-rewrite stop held) and F2-AC11 (the W13 re-run stopped `landing-off-limits` beside "Check My Own Words"). The other **24 rest on the prose pin alone**. The three the plan named are among them: F2-AC10 "the request continues in the same session", F2-AC3 "one line per left-out heading with its reason", F2-AC2/F2-AC6 (the table and the suggestion descriptions as the model words them).
- **1 part has neither a pin nor an imperative**: F2-AC7 "may name one or more groups as the section's starting point". The row's `groups` reaches `read.json` (tested), but step 5 of `SKILL.md` never tells the model to use it. The criterion is a "may"; the permission has nothing behind it (§7).
- **0 OPEN.** The consumer-owned halves (Hashi applies `replace_between_markers`, keeps user text, cleans up) are evidenced by Hashi's vendored schema at `0.33.0` and the joint-run results, §4.

Eight criterion parts had no test that could fail; all eight are now closed by RED-proven tests (§3).

## 1. The single invocation

The **322 node ids** in the trace table ran **together in one `pytest` invocation** on 2026-11-19, branch `docs/263-review-template-sections` at `f0cb76e8` with `tests/test_046_close_out_gaps.py` added (uncommitted at the time of the run; committed with this document):

```
518 passed in 4.18s
```

322 node ids collect **518 items**; the difference is parametrisation. Nothing was skipped. Collection was checked by script: the sorted list of cited node ids and the sorted list of collected node ids (parameters stripped) are identical.

<details><summary>The command, exactly as run</summary>

```bash
PYTHONDONTWRITEBYTECODE=1 ./venv/bin/python -m pytest -q -p no:cacheprovider -rs \
  tests/test_046_close_out_gaps.py::test_a_mapped_document_still_names_the_notes_not_read_and_the_days_partly_read \
  tests/test_046_close_out_gaps.py::test_a_mapped_quarter_reads_the_same_days_weekly_and_monthly_notes_as_an_unmapped_one \
  tests/test_046_close_out_gaps.py::test_a_mapped_row_landing_off_limits_stops_the_delivery_of_an_existing_and_a_new_note \
  tests/test_046_close_out_gaps.py::test_a_quarter_computes_the_habits_from_the_trackers_of_all_three_months \
  tests/test_046_close_out_gaps.py::test_after_a_template_correction_the_rows_file_holds_only_the_new_templates_rows \
  tests/test_046_close_out_gaps.py::test_an_off_limits_mark_never_narrows_the_read_a_monthly_own_section_stays_a_source \
  tests/test_046_close_out_gaps.py::test_the_delivered_readable_instructions_carry_every_sections_block_first_and_on_a_rerun \
  tests/test_046_close_out_gaps.py::test_without_a_mapping_the_quarter_document_holds_every_group_each_empty_one_saying_so \
  tests/test_046_t4_2_doc_sections.py::test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items \
  tests/test_046_t4_2_doc_sections.py::test_a_quarter_renders_the_quarter_groups_once_it_read_monthly_notes \
  tests/test_046_t4_2_doc_sections.py::test_a_routed_section_stays_in_template_order_and_lands_in_tomo_review \
  tests/test_046_t4_2_doc_sections.py::test_an_analysis_part_alone_keeps_the_divider \
  tests/test_046_t4_2_doc_sections.py::test_an_over_cap_section_is_refused_naming_its_key \
  tests/test_046_t4_2_doc_sections.py::test_an_unmapped_meta_has_no_pass1_sections \
  tests/test_046_t4_2_doc_sections.py::test_no_group_and_no_analysis_part_left_means_no_divider \
  tests/test_046_t4_2_doc_sections.py::test_section_rejections_join_rejected_and_counts_carry_the_section_keys \
  tests/test_046_t4_2_doc_sections.py::test_the_english_labels_and_the_inside_place \
  tests/test_046_t4_2_doc_sections.py::test_the_mark_suffix_from_the_label_table_in_a_month \
  tests/test_046_t4_2_doc_sections.py::test_the_quarter_marks_and_the_english_month_marks \
  tests/test_046_t4_2_doc_sections.py::test_the_review_heading_comes_from_the_setup \
  tests/test_046_t4_2_doc_sections.py::test_write_and_replace_refuse_a_section_error_before_any_kado_call \
  tests/test_046_t4_2_unmapped_doc_golden.py::test_the_goldens_pin_what_they_claim \
  tests/test_046_t4_2_unmapped_doc_golden.py::test_the_unmapped_document_is_byte_identical_to_spec_045 \
  tests/test_046_t4_2_unmapped_doc_golden.py::test_the_unmapped_result_and_meta_are_unchanged \
  tests/test_046_t4_3_section_parse.py::test_a_broken_checkbox_stops \
  tests/test_046_t4_3_section_parse.py::test_a_checkbox_moved_out_of_its_part_stops \
  tests/test_046_t4_3_section_parse.py::test_a_deleted_checkbox_stops_naming_the_section_and_the_line_to_restore \
  tests/test_046_t4_3_section_parse.py::test_a_deleted_heading_stops_for_the_orphaned_checkbox \
  tests/test_046_t4_3_section_parse.py::test_a_second_checkbox_stops \
  tests/test_046_t4_3_section_parse.py::test_a_section_without_its_checkbox_lands_nothing \
  tests/test_046_t4_3_section_parse.py::test_a_ticked_empty_section_with_the_users_own_item_is_not_empty \
  tests/test_046_t4_3_section_parse.py::test_a_ticked_section_with_nothing_ticked_is_empty \
  tests/test_046_t4_3_section_parse.py::test_an_unticked_section_drops_everything_in_it_the_users_items_too \
  tests/test_046_t4_3_section_parse.py::test_only_items_in_unticked_sections_mean_nothing_to_deliver \
  tests/test_046_t4_3_section_parse.py::test_the_rendered_week_reads_by_section \
  tests/test_046_t4_3_section_parse.py::test_the_restore_line_is_english_for_an_english_or_broken_frontmatter \
  tests/test_046_t4_3_section_parse.py::test_the_restore_line_of_an_empty_section_is_unticked \
  tests/test_046_t4_3_unmapped_parse_golden.py::test_the_unmapped_parse_is_unchanged \
  tests/test_046_t4_4_section_stop.py::test_a_deleted_section_checkbox_plans_nothing_and_refuses \
  tests/test_046_t4_4_section_stop.py::test_another_expected_key_first_on_a_heading_with_that_section_ticked_delivers_nothing \
  tests/test_046_t4_4_section_stop.py::test_parse_prints_the_section_problems_and_counts_of_a_mapped_document \
  tests/test_046_t4_4_section_stop.py::test_section_checkbox_missing_is_refusing \
  tests/test_046_t4_4_section_stop.py::test_the_gate_refuses_a_missing_section_checkbox_after_the_approved_line \
  tests/test_046_t4_4_skill_sections.py::test_a_section_is_named_by_the_configured_heading_of_its_key \
  tests/test_046_t4_4_skill_sections.py::test_a_section_receives_what_its_description_and_keywords_ask_for_as_reminders_within_its_cap \
  tests/test_046_t4_4_skill_sections.py::test_analysis_rows_are_overviews_and_the_flag_is_the_one_review_read_writes \
  tests/test_046_t4_4_skill_sections.py::test_month_section_items_carry_the_child_note_marks \
  tests/test_046_t4_4_skill_sections.py::test_one_place_per_item_and_the_rest_in_the_groups \
  tests/test_046_t4_4_skill_sections.py::test_step_6_stops_on_a_missing_section_checkbox_naming_the_section_and_the_restore_line \
  tests/test_046_t4_4_skill_sections.py::test_step_7_runs_parse_for_the_section_stop \
  tests/test_046_t4_4_skill_sections.py::test_the_rewrite_names_a_fix_for_every_section_error \
  tests/test_046_t4_5_quarter_read.py::test_a_failed_quarter_write_keeps_every_read_file \
  tests/test_046_t4_5_quarter_read.py::test_a_mapped_quarter_checks_sections_and_renders_the_quarter_marks \
  tests/test_046_t4_5_quarter_read.py::test_a_quarter_document_renders_the_quarter_groups \
  tests/test_046_t4_5_quarter_read.py::test_a_quarter_whose_index_sections_differ_from_the_rows_is_sections_changed \
  tests/test_046_t4_5_quarter_read.py::test_a_quarter_write_resolves_sources_across_all_month_parts \
  tests/test_046_t4_5_quarter_read.py::test_a_written_quarter_removes_every_read_file_and_the_proposals \
  tests/test_046_t4_5_quarter_read.py::test_replace_abort_removes_every_read_file_of_a_quarter_and_keeps_meta \
  tests/test_046_t4_5_quarter_read.py::test_replace_needs_confirm_reads_the_quarter_through_the_loader \
  tests/test_046_t4_5_skill_quarter.py::test_a_set_up_quarter_request_goes_on_to_step3 \
  tests/test_046_t4_5_skill_quarter.py::test_review_setup_walks_the_quarter_like_the_week_and_month \
  tests/test_046_t4_5_skill_quarter.py::test_step4_prints_the_monthly_status_and_notes \
  tests/test_046_t4_5_skill_quarter.py::test_step5_names_the_quarter_keys_like_the_months \
  tests/test_046_t4_5_skill_quarter.py::test_step5_reads_the_index_then_each_part_in_turn_then_writes_one_proposals_file \
  tests/test_046_t4_5_skill_quarter.py::test_the_privacy_rule_covers_every_read_file \
  tests/test_046_t5_2_new_note_sections.py::test_a_heading_held_twice_by_the_template_routes \
  tests/test_046_t5_2_new_note_sections.py::test_a_heading_only_inside_templater_code_routes_and_the_variant_comes_first \
  tests/test_046_t5_2_new_note_sections.py::test_a_heading_the_new_note_lacks_routes_and_never_leaves_a_marker \
  tests/test_046_t5_2_new_note_sections.py::test_a_new_note_from_a_plain_template_gets_every_block_at_hashis_line_with_both_markers \
  tests/test_046_t5_2_new_note_sections.py::test_a_plain_note_routes_every_section_placed_in_the_note \
  tests/test_046_t5_2_new_note_sections.py::test_a_rerun_stops_when_the_existing_tomo_review_sits_off_limits \
  tests/test_046_t5_2_new_note_sections.py::test_an_existing_note_plans_its_sections_and_routes_only_on_the_review_choice \
  tests/test_046_t5_2_new_note_sections.py::test_analysis_rows_land_as_level_plus_one_sub_headings_inside_tomo_review_never_in_their_section \
  tests/test_046_t5_2_new_note_sections.py::test_landing_off_limits_refuses_at_delivery \
  tests/test_046_t5_2_new_note_sections.py::test_pass1_names_the_routed_section_of_a_new_note_in_its_landing_line \
  tests/test_046_t5_2_new_note_sections.py::test_pass1_routes_every_section_of_a_new_note_without_a_template \
  tests/test_046_t5_2_new_note_sections.py::test_sub_headings_are_display_neutralised \
  tests/test_046_t5_2_new_note_sections.py::test_the_habits_stay_in_tomo_review_with_a_mapping_after_the_sections \
  tests/test_046_t5_2_new_note_sections.py::test_the_next_run_finds_every_spliced_block_and_replaces_it \
  tests/test_046_t5_2_new_note_sections.py::test_tomo_review_inside_an_off_limits_section_is_landing_off_limits \
  tests/test_046_t5_3_readable_sections.py::test_document_shows_every_section_with_heading_placement_and_block \
  tests/test_046_t5_3_readable_sections.py::test_empty_replace_content_says_remove_every_line \
  tests/test_046_t5_3_readable_sections.py::test_replace_names_both_markers_and_the_scope \
  tests/test_046_t5_3_readable_sections.py::test_replace_without_scope_says_the_whole_note \
  tests/test_046_t5_4_section_set.py::test_a_new_notes_empty_section_gets_no_marker_pair \
  tests/test_046_t5_4_section_set.py::test_a_rerun_replaces_each_block_between_its_markers_then_tomo_review \
  tests/test_046_t5_4_section_set.py::test_an_empty_section_emits_no_action \
  tests/test_046_t5_4_section_set.py::test_sections_in_mapping_order_then_tomo_review_with_dense_ids \
  tests/test_046_t5_5_delivery_choices.py::test_a_broken_block_offers_skip_only \
  tests/test_046_t5_5_delivery_choices.py::test_a_missing_heading_stops_the_whole_delivery_before_any_write \
  tests/test_046_t5_5_delivery_choices.py::test_a_rerun_replaces_the_block_and_says_so \
  tests/test_046_t5_5_delivery_choices.py::test_an_ambiguous_heading_stops_with_skip_and_review \
  tests/test_046_t5_5_delivery_choices.py::test_dropped_and_empty_sections_are_named_with_the_users_own_count \
  tests/test_046_t5_5_delivery_choices.py::test_every_section_stop_refuses_with_its_offered_choices \
  tests/test_046_t5_5_delivery_choices.py::test_skip_leaves_the_section_out_and_review_routes_it \
  tests/test_046_t5_5_delivery_choices.py::test_the_preview_lists_every_section_with_lines_mode_and_lines \
  tests/test_046_t5_5_delivery_choices.py::test_the_preview_names_each_sections_configured_placement \
  tests/test_046_t5_6_skill_choices.py::test_a_stop_without_choices_ends_before_any_question \
  tests/test_046_t5_6_skill_choices.py::test_the_answers_rerun_preview_with_the_flags_and_end_in_the_deliver_question \
  tests/test_046_t5_6_skill_choices.py::test_the_flags_and_choices_the_skill_names_are_the_scripts \
  tests/test_046_t5_6_skill_choices.py::test_the_stop_lines_follow_the_plan_and_its_notices \
  tests/test_046_t5_7_one_block_per_section.py::test_a_renamed_heading_beside_an_intact_block_offers_skip_and_confirm_moved \
  tests/test_046_t5_7_one_block_per_section.py::test_a_stop_beside_a_broken_earlier_block_offers_skip_only \
  tests/test_046_t5_7_one_block_per_section.py::test_an_ambiguous_heading_beside_an_intact_block_offers_skip_only \
  tests/test_046_t5_7_place_off_limits.py::test_the_place_landing_off_limits_carries_no_section_stop \
  tests/test_046_t6_1_wire_v4.py::test_hashi_def_is_the_handoff_fragment \
  tests/test_046_t6_1_wire_v4.py::test_hashi_insert_vectors_through_the_reference \
  tests/test_046_t6_1_wire_v4.py::test_hashi_replace_vectors_through_the_reference \
  tests/test_046_t6_1_wire_v4.py::test_producer_defines_the_action_as_the_contract_does \
  tests/test_046_t6_2_e2e_sections.py::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers \
  tests/test_046_t6_2_e2e_sections.py::test_a_section_stop_beside_the_place_problem_takes_one_extra_round \
  tests/test_046_t6_2_e2e_sections.py::test_an_unmapped_review_keeps_the_spec_045_shape \
  tests/test_046_t6_3_end_own_text.py::test_an_off_limits_first_sub_heading_takes_the_parents_block_above_it \
  tests/test_046_t6_3_end_own_text.py::test_an_off_limits_parent_still_stops_end \
  tests/test_046_t6_4_unscoped_replace.py::test_the_built_action_is_unscoped \
  tests/test_046_t6_4_unscoped_replace.py::test_the_reference_applier_replaces_only_the_block \
  tests/test_046_t6_4_unscoped_replace.py::test_the_set_validates_against_both_committed_schemas \
  tests/test_period.py::test_a_bare_quarter_is_the_most_recent_finished_one_with_the_year_named \
  tests/test_period.py::test_a_bare_quarter_number_outside_1_to_4_is_invalid \
  tests/test_period.py::test_a_full_quarter_name_is_that_quarter \
  tests/test_period.py::test_a_kind_word_before_a_period_of_another_kind_is_invalid \
  tests/test_period.py::test_a_quarter_has_its_three_months \
  tests/test_period.py::test_a_quarter_is_three_calendar_months \
  tests/test_period.py::test_a_quarter_name_that_does_not_exist_does_not_parse \
  tests/test_period.py::test_a_quarter_number_outside_1_to_4_is_invalid \
  tests/test_period.py::test_a_quarter_outside_its_year_is_invalid_with_the_last_quarter_as_example \
  tests/test_period.py::test_a_quarter_year_outside_the_range_is_invalid \
  tests/test_period.py::test_an_at_picked_quarterly_note_follows_the_configured_format \
  tests/test_period.py::test_an_at_picked_quarterly_note_is_its_quarter \
  tests/test_period.py::test_an_unfinished_quarter_names_the_last_finished_one \
  tests/test_period.py::test_last_finished_quarter \
  tests/test_period.py::test_quarter_word_is_the_last_finished_quarter \
  tests/test_period.py::test_the_default_quarter_format_renders_and_parses \
  tests/test_period.py::test_the_grammar_names_the_quarter \
  tests/test_period.py::test_the_quarter_that_ends_today_is_not_finished \
  tests/test_period.py::test_the_quarter_word_is_case_insensitive \
  tests/test_period.py::test_the_weeks_overlapping_2026_q1_cross_both_ends \
  tests/test_review_children.py::test_a_link_to_a_monthly_or_quarterly_note_is_navigation_only_with_its_format_configured \
  tests/test_review_children.py::test_a_month_note_never_read_puts_its_days_in_no_mark \
  tests/test_review_children.py::test_a_monthly_listing_that_still_fails_is_not_read_without_an_access_hint \
  tests/test_review_children.py::test_a_quarter_reads_every_daily_and_the_day_after \
  tests/test_review_children.py::test_a_quarter_without_monthly_config_says_not_configured_and_lists_nothing \
  tests/test_review_children.py::test_a_quarter_without_monthly_or_weekly_notes_is_built_from_the_dailies \
  tests/test_review_children.py::test_a_rate_limited_monthly_listing_recovered_by_the_end_pass_reads_the_monthly_notes \
  tests/test_review_children.py::test_an_empty_monthly_listing_is_kado_empty_with_the_access_hint \
  tests/test_review_children.py::test_boundary_weeks_are_clipped_to_the_quarter_and_their_week_text_tagged \
  tests/test_review_children.py::test_monthly_notes_are_split_into_month_text_and_tagged \
  tests/test_review_children.py::test_quarter_marks_at_monthly_level \
  tests/test_review_children.py::test_sources_from_config_takes_the_monthly_and_quarterly_setup \
  tests/test_review_children.py::test_the_quarter_report_holds_no_note_text \
  tests/test_review_children.py::test_the_quarter_writes_no_weekly_marks \
  tests/test_review_children.py::test_the_report_names_absent_months_and_weeks \
  tests/test_review_children.py::test_the_same_notes_read_as_a_month_mark_at_weekly_level \
  tests/test_review_config.py::test_a_config_without_the_new_keys_reads_as_before \
  tests/test_review_config.py::test_groups_follow_the_kind \
  tests/test_review_config.py::test_input_problems_refuse_duplicate_heading_keys_and_ids \
  tests/test_review_config.py::test_off_limits_rows_with_and_without_subsections \
  tests/test_review_config.py::test_quarter_input_is_valid_and_forbids_the_week_keys \
  tests/test_review_config.py::test_quarter_setup_reads_the_quarterly_keys_with_the_profile_folder \
  tests/test_review_config.py::test_quarter_writer_edits_use_the_quarterly_keys \
  tests/test_review_config.py::test_review_setup_reads_only_the_configured_templates_rows_with_defaults \
  tests/test_review_config.py::test_rows_need_a_named_template \
  tests/test_review_config.py::test_schema_accepts_a_row_with_each_placement \
  tests/test_review_config.py::test_schema_refuses_a_bad_row_at_its_pointer \
  tests/test_review_config.py::test_writer_edits_touch_only_the_named_templates_entries \
  tests/test_review_deliver.py::test_cli_every_problem_name_is_pinned_to_refusing_or_notice \
  tests/test_review_mapping.py::test_a_heading_under_a_templater_heading_is_per_period \
  tests/test_review_mapping.py::test_a_heading_with_a_link_is_left_out_as_link \
  tests/test_review_mapping.py::test_a_heading_with_templater_code_is_left_out_as_templater \
  tests/test_review_mapping.py::test_a_row_names_only_its_own_identity \
  tests/test_review_mapping.py::test_a_section_of_automatic_lines_only_is_left_out_as_automatic \
  tests/test_review_mapping.py::test_an_empty_container_of_per_period_headings_only_is_per_period \
  tests/test_review_mapping.py::test_an_empty_container_whose_sub_headings_are_all_automatic_is_automatic \
  tests/test_review_mapping.py::test_automatic_and_own_lines_make_a_mixed_heading_that_is_offered \
  tests/test_review_mapping.py::test_duplicates_are_keyed_by_text_level_parent_and_occurrence \
  tests/test_review_mapping.py::test_landing_off_limits_named_row_ancestor_with_and_without_sub_sections \
  tests/test_review_mapping.py::test_nothing_is_off_limits_without_a_row \
  tests/test_review_mapping.py::test_off_limits_heading_only_leaves_its_children_offered_under_own \
  tests/test_review_mapping.py::test_off_limits_with_sub_sections_leaves_its_children_out \
  tests/test_review_mapping.py::test_templater_wins_over_link_first_rule_wins \
  tests/test_review_mapping.py::test_the_five_templates_give_the_sdd_sets \
  tests/test_review_mapping.py::test_the_same_heading_under_three_parents_is_per_period_two_are_not \
  tests/test_review_read_parts.py::test_a_quarter_is_an_index_and_one_part_per_month_in_order \
  tests/test_review_read.py::test_a_mapped_month_reads_the_same_notes_days_and_weekly_entries_as_an_unmapped_one \
  tests/test_review_read.py::test_a_mapped_week_carries_the_section_definitions_keyed_by_row_id \
  tests/test_review_read.py::test_a_quarter_run_reads_the_quarter_and_marks_against_the_monthly_notes \
  tests/test_review_read.py::test_a_quarter_writes_the_index_and_one_part_per_month_and_no_read_json \
  tests/test_review_read.py::test_a_stale_read_json_in_the_quarters_stage_folder_is_removed \
  tests/test_review_read.py::test_on_the_measured_shape_every_written_file_fits_and_loads_back \
  tests/test_review_read.py::test_without_a_mapping_read_json_has_no_sections_key \
  tests/test_review_section_plan.py::test_a_stop_beside_any_earlier_block_material_offers_skip_only \
  tests/test_review_section_plan.py::test_ambiguous_choices_skip_and_review \
  tests/test_review_section_plan.py::test_ambiguous_on_rerun_with_an_intact_block_offers_no_review \
  tests/test_review_section_plan.py::test_ambiguous_when_hashis_first_match_by_text_and_level_is_another_heading \
  tests/test_review_section_plan.py::test_broken_blocks \
  tests/test_review_section_plan.py::test_first_delivery_maps_the_placement_and_lands_where_hashi_puts_it \
  tests/test_review_section_plan.py::test_guard_every_applied_plan_goes_through_the_splice \
  tests/test_review_section_plan.py::test_insert_action_shape \
  tests/test_review_section_plan.py::test_item_line_holding_a_marker_is_escaped_and_the_next_run_is_not_broken \
  tests/test_review_section_plan.py::test_landing_off_limits_where_it_would_land_and_where_it_sits \
  tests/test_review_section_plan.py::test_layout_a_block_straddling_a_heading_is_broken \
  tests/test_review_section_plan.py::test_layout_before_at_the_top_lands_in_the_preamble \
  tests/test_review_section_plan.py::test_layout_same_text_at_another_level_is_ambiguous \
  tests/test_review_section_plan.py::test_layout_same_text_at_the_same_level_is_ambiguous_also_on_rerun \
  tests/test_review_section_plan.py::test_layout_under_with_user_text_keeps_it_below_the_block \
  tests/test_review_section_plan.py::test_mapped_by_level_parent_and_occurrence \
  tests/test_review_section_plan.py::test_markers_of_another_period_or_section_are_not_ours \
  tests/test_review_section_plan.py::test_missing_on_first_delivery_and_rerun_with_its_choices \
  tests/test_review_section_plan.py::test_missing_on_rerun_with_an_intact_block_offers_no_review \
  tests/test_review_section_plan.py::test_moved_into_the_preamble_is_never_replaced \
  tests/test_review_section_plan.py::test_moved_under_another_heading_stops_and_confirm_replaces_scoped \
  tests/test_review_section_plan.py::test_replace_action_shape_with_and_without_scope \
  tests/test_review_section_plan.py::test_rerun_twice_keeps_one_block_and_the_user_text \
  tests/test_review_section_plan.py::test_sdd_example_end_marker_lost_never_pairs_with_next_block \
  tests/test_review_section_plan.py::test_traced_1_end_with_subsections_is_replaced_in_the_range_with_scope \
  tests/test_review_section_plan.py::test_traced_1_spare_time_off_limits_stops_the_rerun \
  tests/test_review_section_plan.py::test_traced_2_end_marker_deleted_is_broken \
  tests/test_review_section_plan.py::test_traced_2_fenced_start_is_a_hidden_copy_and_broken \
  tests/test_review_section_plan.py::test_traced_2_under_rerun_replaced_with_scope \
  tests/test_review_section_plan.py::test_traced_3_before_off_limits_above_stops_first_delivery_and_rerun \
  tests/test_review_section_plan.py::test_traced_3_before_replaced_without_scope \
  tests/test_review_section_plan.py::test_trailing_feff_and_whitespace_still_count_as_the_marker \
  tests/test_review_section_plan.py::test_unknown_choice_or_placement_is_refused \
  tests/test_review_sections.py::test_a_mark_of_another_kind_is_not_allowed \
  tests/test_review_sections.py::test_a_mark_without_the_child_notes_read_is_not_allowed \
  tests/test_review_sections.py::test_a_review_only_mark_rests_on_the_weekly_or_monthly_note \
  tests/test_review_sections.py::test_a_section_item_needs_a_daily_of_the_period \
  tests/test_review_sections.py::test_a_theme_like_section_item_needs_only_one_day \
  tests/test_review_sections.py::test_an_echoed_rendered_line_loses_its_id_before_its_link_list \
  tests/test_review_sections.py::test_an_inline_link_with_the_same_target_is_a_double_whatever_its_alias \
  tests/test_review_sections.py::test_monthly_only_needs_a_monthly_note_and_the_quarter_groups_need_monthly_notes \
  tests/test_review_sections.py::test_more_items_than_the_cap_are_refused_never_truncated \
  tests/test_review_sections.py::test_the_cap_counts_the_proposed_items_before_the_source_rule \
  tests/test_review_sections.py::test_the_group_tables_keep_the_week_and_month_order_and_add_the_quarter_pair \
  tests/test_review_sections.py::test_the_same_first_line_with_other_sources_is_not_a_double \
  tests/test_review_sections.py::test_the_same_normalised_text_in_a_section_and_a_group_is_refused_on_the_later_one \
  tests/test_review_sections.py::test_the_same_sources_and_first_line_are_refused_and_a_different_first_line_is_not \
  tests/test_review_sections.py::test_the_same_text_in_two_sections_is_refused_on_the_later_one \
  tests/test_review_sections.py::test_two_identical_group_items_are_a_double_only_with_a_mapping \
  tests/test_review_sections.py::test_without_a_mapping_any_section_is_unknown \
  tests/test_review_sections.py::test_without_a_mapping_spec_045_proposals_give_no_section_result \
  tests/test_review_session_sections.py::test_a_configured_or_typed_quarter_format_beats_the_notes \
  tests/test_review_session_sections.py::test_a_configured_template_that_is_not_found_is_reported_as_configured \
  tests/test_review_session_sections.py::test_a_found_template_carries_no_not_found_key \
  tests/test_review_session_sections.py::test_a_quarter_format_follows_the_existing_quarterly_notes \
  tests/test_review_session_sections.py::test_a_quarter_without_setup_proposes_folder_format_template_place_language_and_rows \
  tests/test_review_session_sections.py::test_a_readable_template_gives_one_candidate_per_heading_with_key_state_reason_flags_and_defaults \
  tests/test_review_session_sections.py::test_a_same_template_rerun_drops_nothing_even_for_a_row_the_template_lacks \
  tests/test_review_session_sections.py::test_a_template_change_to_no_template_drops_every_earlier_row \
  tests/test_review_session_sections.py::test_a_template_with_only_automatic_headings_is_mappable_for_analysis_rows \
  tests/test_review_session_sections.py::test_a_typed_template_that_is_not_found_is_reported_with_the_candidates_and_a_null_template \
  tests/test_review_session_sections.py::test_after_a_template_change_dropped_names_the_earlier_rows_the_new_template_lacks \
  tests/test_review_session_sections.py::test_match_saves_nothing \
  tests/test_review_session_sections.py::test_no_template_or_no_eligible_heading_is_an_explicit_empty_mapping \
  tests/test_review_session_sections.py::test_rows_files_are_kept_per_kind \
  tests/test_review_session_sections.py::test_rows_saved_for_another_template_are_not_this_templates_rows \
  tests/test_review_session_sections.py::test_saved_rows_come_back_as_the_defaults_and_saved_off_limits_leave_their_heading_out \
  tests/test_review_session_sections.py::test_the_configured_anchor_counts_only_for_the_configured_template \
  tests/test_review_session_templates.py::test_match_for_a_quarter_without_a_configured_format_proposes_the_quarter_default \
  tests/test_review_session_templates.py::test_no_mapping_entry_lists_the_templates_whose_name_fits_the_kind \
  tests/test_review_session_templates.py::test_quarter_candidates_are_the_templates_named_quarter_or_quartal \
  tests/test_review_session_templates.py::test_the_flag_wins_over_the_mapping_and_a_missing_choice_is_reported_not_found \
  tests/test_review_session.py::test_start_every_bad_argument_yields_kind_expectation_and_example \
  tests/test_review_session.py::test_writer_input_for_a_quarter_drops_the_null_week_rule \
  tests/test_review_setup_input_rows.py::test_a_before_under_an_off_limits_previous_heading_is_refused \
  tests/test_review_setup_input_rows.py::test_a_heading_not_in_the_template_is_refused \
  tests/test_review_setup_input_rows.py::test_a_left_out_heading_is_refused_with_its_reason \
  tests/test_review_setup_input_rows.py::test_a_mixed_heading_is_accepted \
  tests/test_review_setup_input_rows.py::test_a_row_on_an_off_limits_heading_is_refused \
  tests/test_review_setup_input_rows.py::test_a_saved_off_limits_mark_refuses_a_row_too \
  tests/test_review_setup_input_rows.py::test_a_saved_row_whose_heading_the_template_lost_is_named_in_dropped \
  tests/test_review_setup_input_rows.py::test_a_template_correction_keeps_the_id_of_a_heading_the_new_template_keeps \
  tests/test_review_setup_input_rows.py::test_a_template_match_did_not_find_is_refused_even_when_put_back \
  tests/test_review_setup_input_rows.py::test_accepted_rows_reach_the_writer_input_with_ids_and_the_rows_file_is_deleted \
  tests/test_review_setup_input_rows.py::test_an_analysis_row_on_an_offered_heading_is_refused \
  tests/test_review_setup_input_rows.py::test_rows_for_a_template_match_did_not_show_are_refused \
  tests/test_review_setup_input_rows.py::test_rows_without_any_match_are_refused \
  tests/test_review_setup_input_rows.py::test_the_evidence_is_the_rows_file_not_the_confirmed_file \
  tests/test_review_setup_input_rows.py::test_the_tomo_review_place_inside_an_off_limits_subtree_is_refused \
  tests/test_review_skill_pass2.py::test_every_parse_warning_has_a_plain_language_line \
  tests/test_review_skill_pass2.py::test_every_preview_notice_is_one_line_and_the_question_still_follows \
  tests/test_review_skill_pass2.py::test_every_refusing_preview_problem_has_its_line \
  tests/test_review_skill_pass2.py::test_preview_prints_the_section_target_and_place_then_asks_deliver_or_abort_and_ends_the_turn \
  tests/test_review_skill_pass2.py::test_the_preview_prints_each_sections_lines_and_deliver_routes_choices_needed \
  tests/test_review_skill_sections.py::test_a_dropped_heading_is_said_kept_or_not_by_whether_the_save_writes_rows \
  tests/test_review_skill_sections.py::test_a_row_shows_level_and_parent_so_same_text_headings_are_told_apart \
  tests/test_review_skill_sections.py::test_a_table_correction_runs_no_match_and_a_template_change_rebuilds_the_table \
  tests/test_review_skill_sections.py::test_a_template_choice_rerun_adds_neither_the_old_template_nor_the_old_anchor \
  tests/test_review_skill_sections.py::test_a_template_not_found_is_named_before_the_candidates_are_asked \
  tests/test_review_skill_sections.py::test_a_template_not_found_without_candidates_asks_for_a_typed_name_or_none \
  tests/test_review_skill_sections.py::test_an_automatic_heading_with_a_description_becomes_an_analysis_row \
  tests/test_review_skill_sections.py::test_both_argument_hints_name_the_quarter \
  tests/test_review_skill_sections.py::test_confirm_writes_the_table_rows_and_the_off_limits_marks \
  tests/test_review_skill_sections.py::test_corrections_are_plain_text_in_the_existing_correct_step \
  tests/test_review_skill_sections.py::test_every_left_out_heading_gets_one_line_with_its_reason \
  tests/test_review_skill_sections.py::test_every_pointer_setup_input_returns_is_named_in_words \
  tests/test_review_skill_sections.py::test_forward_looking_sections_ask_for_suggestions_from_the_period \
  tests/test_review_skill_sections.py::test_no_mappable_heading_prints_no_table \
  tests/test_review_skill_sections.py::test_review_setup_includes_the_quarter \
  tests/test_review_skill_sections.py::test_the_anchor_is_not_carried_over_a_template_change \
  tests/test_review_skill_sections.py::test_the_correct_step_edits_removes_adds_and_marks_off_limits \
  tests/test_review_skill_sections.py::test_the_dropped_headings_are_named_after_a_template_change \
  tests/test_review_skill_sections.py::test_the_model_words_only_descriptions_keywords_and_groups \
  tests/test_review_skill_sections.py::test_the_off_limits_line_lists_the_saved_marks_or_none \
  tests/test_review_skill_sections.py::test_the_quarter_runs_the_same_setup_step \
  tests/test_review_skill_sections.py::test_the_reason_words_cover_every_reason_the_script_gives \
  tests/test_review_skill_sections.py::test_the_request_continues_in_the_same_session_after_the_save \
  tests/test_review_skill_sections.py::test_the_skill_names_per_kind_exactly_the_groups_the_schema_allows \
  tests/test_review_skill_sections.py::test_the_table_asks_no_question_of_its_own \
  tests/test_review_skill_sections.py::test_the_table_is_printed_from_the_match_sections_in_candidate_order \
  tests/test_review_skill.py::test_an_inferred_year_is_named_before_reading \
  tests/test_review_skill.py::test_open_reviews_are_handled_before_the_new_request_in_listed_order \
  tests/test_review_skill.py::test_start_errors_show_expected_and_example_and_write_nothing \
  tests/test_review_state_listing.py::test_a_quarter_period_is_inferred_as_quarter \
  tests/test_review_state_listing.py::test_open_reviews_lists_a_quarter_by_its_start_and_infers_its_kind \
  tests/test_vault_config_edit.py::test_instance_config_copy_keeps_every_other_line \
  tests/test_vault_config_edit.py::test_second_templates_rows_under_the_same_parent_stay_byte_identical \
  tests/test_vault_config_writer_review.py::test_a_corrected_mapping_saves_only_its_rows \
  tests/test_vault_config_writer_review.py::test_a_second_template_keeps_the_first_and_changes_nothing_else \
  tests/test_vault_config_writer_review.py::test_invalid_rows_are_refused_with_pointers_and_nothing_written \
  tests/test_vault_config_writer_review.py::test_quarter_setup_lands_under_the_quarterly_keys \
  tests/test_vault_config_writer_review.py::test_rows_round_trip_per_template_and_read_back_through_the_reader
```

</details>

## 2. Trace

Shorthand (`X::` = `tests/<file>::`): `RS` test_review_sections.py · `DS` test_046_t4_2_doc_sections.py · `SK` test_046_t4_4_skill_sections.py · `RD` test_review_read.py · `QR` test_046_t4_5_quarter_read.py · `SQ` test_046_t4_5_skill_quarter.py · `UG` test_046_t4_2_unmapped_doc_golden.py · `UP` test_046_t4_3_unmapped_parse_golden.py · `E6` test_046_t6_2_e2e_sections.py · `SS` test_review_session_sections.py · `ST` test_review_session_templates.py · `SE` test_review_session.py · `SKS` test_review_skill_sections.py · `S` test_review_skill.py · `P2` test_review_skill_pass2.py · `SI` test_review_setup_input_rows.py · `MP` test_review_mapping.py · `CF` test_review_config.py · `W` test_vault_config_writer_review.py · `VE` test_vault_config_edit.py · `SP` test_review_section_plan.py · `NN` test_046_t5_2_new_note_sections.py · `RM` test_046_t5_3_readable_sections.py · `SET` test_046_t5_4_section_set.py · `DC` test_046_t5_5_delivery_choices.py · `SCH` test_046_t5_6_skill_choices.py · `OB` test_046_t5_7_one_block_per_section.py · `PO` test_046_t5_7_place_off_limits.py · `EO` test_046_t6_3_end_own_text.py · `W4` test_046_t6_1_wire_v4.py · `UR` test_046_t6_4_unscoped_replace.py · `PS` test_046_t4_3_section_parse.py · `SST` test_046_t4_4_section_stop.py · `RDL` test_review_deliver.py · `P` test_period.py · `RL` test_review_state_listing.py · `CH` test_review_children.py · `RP` test_review_read_parts.py · `GAP` test_046_close_out_gaps.py. Live: `R1`, `R2`, `R3a`, `R3b` = the joint-run rounds (T6.3 notes; Hashi results handoffs of 2026-11-17/18).

| Criterion | Class | Evidence | Mechanism the evidence falsifies |
|---|---|---|---|
| F1-AC1 | script + prose pin | `RD::test_a_mapped_month_reads_the_same_notes_days_and_weekly_entries_as_an_unmapped_one`, `::test_a_mapped_week_carries_the_section_definitions_keyed_by_row_id`, `::test_without_a_mapping_read_json_has_no_sections_key`, `::test_a_quarter_run_reads_the_quarter_and_marks_against_the_monthly_notes`, `GAP::test_a_mapped_quarter_reads_the_same_days_weekly_and_monthly_notes_as_an_unmapped_one`; pin `SK::test_a_section_receives_what_its_description_and_keywords_ask_for_as_reminders_within_its_cap` | A day, note, weekly or monthly entry dropped or added in a mapped month's or quarter's read (whole-read equality once `sections` is popped); the definitions not written. "Looks for what the description asks" is the prose pin only; live the quarter was read partly (#270) |
| F1-AC2 | lib + e2e + prose pin | `DS::test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items` (rows with `groups: []`), `RS::test_a_review_only_mark_rests_on_the_weekly_or_monthly_note`; pin `SK::test_a_section_receives_what_its_description_and_keywords_ask_for_as_reminders_within_its_cap` ("whatever group they would fit") | A group filter added to `review_sections.check` (an empty `groups`, or a mark outside the row's groups, would be refused). What the model gathers: prose pin only; no section-fit row was walked |
| F1-AC3 | lib + prose pin | `RS::test_a_section_item_needs_a_daily_of_the_period`, `::test_a_review_only_mark_rests_on_the_weekly_or_monthly_note`, `::test_a_theme_like_section_item_needs_only_one_day`, `DS::test_section_rejections_join_rejected_and_counts_carry_the_section_keys`; pin `SK::test_a_section_receives_what_its_description_and_keywords_ask_for_as_reminders_within_its_cap` | `check_item` dropped from the section path (an out-of-period or weekly-only source accepted). "A reminder, not finished review text": prose pin only |
| F1-AC4 | lib + prose pin | the F1-AC3 source-rule ids; pins `SK::test_a_section_receives_what_its_description_and_keywords_ask_for_as_reminders_within_its_cap`, `SKS::test_forward_looking_sections_ask_for_suggestions_from_the_period` | One source rule covers every section item, forward-looking or not; the script cannot tell them apart. "A suggestion drawn from the period": prose pin only |
| F1-AC5 | lib + e2e + prose pin | `RS::test_more_items_than_the_cap_are_refused_never_truncated`, `::test_the_cap_counts_the_proposed_items_before_the_source_rule`, `DS::test_an_over_cap_section_is_refused_naming_its_key`, `DS::test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items` (a two-source item renders both links); pins `SK::test_a_section_receives_what_its_description_and_keywords_ask_for_as_reminders_within_its_cap`, `SK::test_the_rewrite_names_a_fix_for_every_section_error` | The `len(items) > cap` error deleted; links cut to the first source. The merging itself: prose pin only |
| F1-AC6 | lib + prose pin + live | `RS::test_the_same_normalised_text_in_a_section_and_a_group_is_refused_on_the_later_one`, `::test_the_same_text_in_two_sections_is_refused_on_the_later_one`, `::test_the_same_sources_and_first_line_are_refused_and_a_different_first_line_is_not`, `::test_the_same_first_line_with_other_sources_is_not_a_double`, `::test_two_identical_group_items_are_a_double_only_with_a_mapping`, `::test_an_inline_link_with_the_same_target_is_a_double_whatever_its_alias`, `::test_an_echoed_rendered_line_loses_its_id_before_its_link_list`, `DS::test_write_and_replace_refuse_a_section_error_before_any_kado_call`; pin `SK::test_one_place_per_item_and_the_rest_in_the_groups`; R3b Pass 1 ("written after one `double-placement` refusal pair") | `review_sections._double_placements` removed: 9 lib tests red (tracer mutation). "The one it fits best": prose pin only. The write-level refusal goes through the shared errors → `Refused` path that `DS::test_write_and_replace_…` proves for other section errors |
| F1-AC7 | e2e + prose pin | `DS::test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items` (open/themes/growth empty and absent, done and habits present), `::test_no_group_and_no_analysis_part_left_means_no_divider`, `::test_an_analysis_part_alone_keeps_the_divider`; pin `SK::test_one_place_per_item_and_the_rest_in_the_groups` | `render_parts` keeping empty groups (`keep_empty=True`: 4 red); the divider with nothing left for it. "Every group finding lands in a section or there": prose pin only |
| F1-AC8 | e2e | `DS::test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items` (s3 `- [ ] Abschnitt übernehmen`, `- nichts gefunden`), `::test_the_english_labels_and_the_inside_place` | The section box ticked for an empty section (`review_sections.py` render: 13 red) |
| F1-AC9 | lib + e2e + prose pin | `RS::test_a_review_only_mark_rests_on_the_weekly_or_monthly_note`, `::test_a_mark_of_another_kind_is_not_allowed`, `::test_a_mark_without_the_child_notes_read_is_not_allowed`, `DS::test_the_mark_suffix_from_the_label_table_in_a_month`, `::test_the_quarter_marks_and_the_english_month_marks`, `QR::test_a_mapped_quarter_checks_sections_and_renders_the_quarter_marks`; pins `SK::test_month_section_items_carry_the_child_note_marks`, `SQ::test_step5_names_the_quarter_keys_like_the_months` | The accepted `mark` dropped (3 red); a mark of another kind, or without the child notes read, accepted. Which items the model marks: prose pin only |
| F1-AC10 | e2e + golden | `UG::test_the_unmapped_document_is_byte_identical_to_spec_045`, `::test_the_unmapped_result_and_meta_are_unchanged`, `::test_the_goldens_pin_what_they_claim`, `E6::test_an_unmapped_review_keeps_the_spec_045_shape`, `RS::test_without_a_mapping_spec_045_proposals_give_no_section_result`, `::test_without_a_mapping_any_section_is_unknown`, `DS::test_an_unmapped_meta_has_no_pass1_sections`, `QR::test_a_quarter_document_renders_the_quarter_groups`, `DS::test_a_quarter_renders_the_quarter_groups_once_it_read_monthly_notes`, `GAP::test_without_a_mapping_the_quarter_document_holds_every_group_each_empty_one_saying_so` | Any byte change to the unmapped week or month document; the double check running without a mapping; an empty group left out of an unmapped quarter (gap M2) |
| F2-AC1 | script + prose pin | `SS::test_a_readable_template_gives_one_candidate_per_heading_with_key_state_reason_flags_and_defaults`, `::test_saved_rows_come_back_as_the_defaults_and_saved_off_limits_leave_their_heading_out`, `::test_match_saves_nothing`, `CF::test_schema_accepts_a_row_with_each_placement`; pins `SKS::test_the_table_is_printed_from_the_match_sections_in_candidate_order`, `::test_the_model_words_only_descriptions_keywords_and_groups` | `match` without `heading_key` (level, parent), `state`/`reason` or `defaults {placement, cap}` (full dict equality); `match` writing the config. Description and keywords as the model words them: prose pin only |
| F2-AC2 | prose pin + script | pins `SKS::test_the_table_asks_no_question_of_its_own`, `::test_corrections_are_plain_text_in_the_existing_correct_step`, `::test_the_correct_step_edits_removes_adds_and_marks_off_limits`; `SI::test_accepted_rows_reach_the_writer_input_with_ids_and_the_rows_file_is_deleted` | A question or option line in the table block, a second confirm question, the Correct-step operations removed; `setup-input` altering a confirmed row. "One table, no extra turn": prose pin only, not walked as a row |
| F2-AC3 | lib + prose pin | `MP::test_the_five_templates_give_the_sdd_sets`, `::test_a_heading_with_templater_code_is_left_out_as_templater`, `::test_a_heading_with_a_link_is_left_out_as_link`, `::test_templater_wins_over_link_first_rule_wins`, `::test_a_heading_under_a_templater_heading_is_per_period`, `::test_the_same_heading_under_three_parents_is_per_period_two_are_not`, `::test_an_empty_container_of_per_period_headings_only_is_per_period`, `::test_a_section_of_automatic_lines_only_is_left_out_as_automatic`, `::test_an_empty_container_whose_sub_headings_are_all_automatic_is_automatic`, `::test_off_limits_heading_only_leaves_its_children_offered_under_own`; pins `SKS::test_every_left_out_heading_gets_one_line_with_its_reason`, `::test_the_reason_words_cover_every_reason_the_script_gives` | Any of the five rules of `analyse_template` removed or its reason renamed (exact verdict lists over five real template structures). "One line per left-out heading with its reason": prose pin only (named by the plan) |
| F2-AC4 | script + prose pin | `SI::test_a_left_out_heading_is_refused_with_its_reason`, `::test_a_row_on_an_off_limits_heading_is_refused`, `::test_the_evidence_is_the_rows_file_not_the_confirmed_file`, `::test_a_mixed_heading_is_accepted`, `MP::test_automatic_and_own_lines_make_a_mixed_heading_that_is_offered`, `SI::test_accepted_rows_reach_the_writer_input_with_ids_and_the_rows_file_is_deleted`, `::test_a_heading_not_in_the_template_is_refused`; pin `SKS::test_every_pointer_setup_input_returns_is_named_in_words` | `setup-input` not refusing `section-left-out` with its reason or `section-off-limits`; the verdict taken from the model's confirmed file; a `mixed` heading refused |
| F2-AC5 | lib + script + prose pin | `MP::test_duplicates_are_keyed_by_text_level_parent_and_occurrence`, `CF::test_input_problems_refuse_duplicate_heading_keys_and_ids`, `SP::test_mapped_by_level_parent_and_occurrence`; pin `SKS::test_a_row_shows_level_and_parent_so_same_text_headings_are_told_apart` | The heading key losing level, parent or occurrence; delivery matching by text alone |
| F2-AC6 | lib + prose pin | `MP::test_the_five_templates_give_the_sdd_sets` (`t_month_privat`: the three forward-looking headings offered); pin `SKS::test_forward_looking_sections_ask_for_suggestions_from_the_period` | A rule leaving forward-looking headings out. The suggestion description: prose pin only (named by the plan) |
| F2-AC7 | schema + script + prose pin | `CF::test_groups_follow_the_kind`, `::test_schema_refuses_a_bad_row_at_its_pointer` (`habits` in `groups`), `W::test_invalid_rows_are_refused_with_pointers_and_nothing_written`, `RD::test_a_mapped_week_carries_the_section_definitions_keyed_by_row_id`, `DS::test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items`, `NN::test_the_habits_stay_in_tomo_review_with_a_mapping_after_the_sections`; pins `SKS::test_the_skill_names_per_kind_exactly_the_groups_the_schema_allows`, `SK::test_one_place_per_item_and_the_rest_in_the_groups` | The per-kind group enums changed or admitting `habits`; `groups` dropped from `read.json`; habits leaving "Tomo Review". **"Starting point": no imperative uses a row's `groups`** (§7) |
| F2-AC8 | lib + script | `CF::test_review_setup_reads_only_the_configured_templates_rows_with_defaults`, `SS::test_rows_saved_for_another_template_are_not_this_templates_rows`, `::test_rows_files_are_kept_per_kind`, `W::test_a_second_template_keeps_the_first_and_changes_nothing_else` | Rows of another template or kind read; the writer overwriting another template's key |
| F2-AC9 | script + e2e + prose pin | `SS::test_no_template_or_no_eligible_heading_is_an_explicit_empty_mapping`, `::test_a_template_with_only_automatic_headings_is_mappable_for_analysis_rows`, `SI::test_rows_without_any_match_are_refused`, `CF::test_rows_need_a_named_template`, `::test_a_config_without_the_new_keys_reads_as_before`, `RD::test_without_a_mapping_read_json_has_no_sections_key`, `UG::test_the_unmapped_document_is_byte_identical_to_spec_045`, `UP::test_the_unmapped_parse_is_unchanged`, `E6::test_an_unmapped_review_keeps_the_spec_045_shape`; pin `SKS::test_no_mappable_heading_prints_no_table` | `sections` omitted or `mappable` not false; rows accepted without a template; the unmapped document or parse differing from spec 045. "Tomo says no section can be mapped": prose pin only |
| F2-AC10 | script + e2e + prose pin | `W::test_a_corrected_mapping_saves_only_its_rows`, `::test_rows_round_trip_per_template_and_read_back_through_the_reader`, `CF::test_writer_edits_touch_only_the_named_templates_entries`, `VE::test_second_templates_rows_under_the_same_parent_stay_byte_identical`, `::test_instance_config_copy_keeps_every_other_line`, `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers`; pins `SKS::test_the_request_continues_in_the_same_session_after_the_save`, `::test_confirm_writes_the_table_rows_and_the_off_limits_marks` | The writer touching a key outside `sections.<template>` (whole-config equality); a description or keyword normalised on save. "Continues in the same session": prose pin only (named by the plan); the e2e proves the script chain match → setup-input → writer → start → Pass 1, not the session |
| F2-AC11 | lib + script + prose pin + live | `MP::test_nothing_is_off_limits_without_a_row`, `::test_a_row_names_only_its_own_identity`, `::test_off_limits_with_sub_sections_leaves_its_children_out`, `::test_landing_off_limits_named_row_ancestor_with_and_without_sub_sections`, `CF::test_off_limits_rows_with_and_without_subsections`, `SI::test_a_saved_off_limits_mark_refuses_a_row_too`, `::test_a_before_under_an_off_limits_previous_heading_is_refused`, `::test_the_tomo_review_place_inside_an_off_limits_subtree_is_refused`, `SP::test_traced_1_spare_time_off_limits_stops_the_rerun`, `::test_traced_3_before_off_limits_above_stops_first_delivery_and_rerun`, `::test_landing_off_limits_where_it_would_land_and_where_it_sits`, `EO::test_an_off_limits_parent_still_stops_end`, `::test_an_off_limits_first_sub_heading_takes_the_parents_block_above_it`, `NN::test_tomo_review_inside_an_off_limits_section_is_landing_off_limits`, `::test_landing_off_limits_refuses_at_delivery`, `::test_a_rerun_stops_when_the_existing_tomo_review_sits_off_limits`, `PO::test_the_place_landing_off_limits_carries_no_section_stop`, `GAP::test_a_mapped_row_landing_off_limits_stops_the_delivery_of_an_existing_and_a_new_note`, `GAP::test_an_off_limits_mark_never_narrows_the_read_a_monthly_own_section_stays_a_source`; live: the W13 re-run before R1 stopped `landing-off-limits`, R2 (off-limits headings untouched) | `landing_off_limits` ignoring `with_subsections` or the named row; `plan_section`'s covered check removed; `_sectioned` not handing `setup.off_limits` to the section planner (gap M7); the period sources leaving marked own sections out (gap M8). Marking in the confirm step: prose pin (`SKS::test_the_off_limits_line_lists_the_saved_marks_or_none`, `::test_the_correct_step_edits_removes_adds_and_marks_off_limits`) |
| F2-AC12 | script + lib + prose pin | `SI::test_accepted_rows_reach_the_writer_input_with_ids_and_the_rows_file_is_deleted`, `::test_an_analysis_row_on_an_offered_heading_is_refused`, `SS::test_a_readable_template_gives_one_candidate_per_heading_with_key_state_reason_flags_and_defaults` (Habits defaults `review`), `SP::test_unknown_choice_or_placement_is_refused`, `NN::test_analysis_rows_land_as_level_plus_one_sub_headings_inside_tomo_review_never_in_their_section`, `::test_sub_headings_are_display_neutralised`, `DS::test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items`, `::test_the_english_labels_and_the_inside_place`; pins `SKS::test_an_automatic_heading_with_a_description_becomes_an_analysis_row`, `SK::test_analysis_rows_are_overviews_and_the_flag_is_the_one_review_read_writes` | An analysis row planned into its own heading; the `####` sub-heading in "Tomo Review" changed; its checkbox leaving the byte golden; `plan_section` accepting placement `review`. "Overview or conclusion": prose pin only |
| F3-AC1 | script + lib | `DS::test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items`, `::test_no_group_and_no_analysis_part_left_means_no_divider`, `::test_an_analysis_part_alone_keeps_the_divider`, `::test_a_routed_section_stays_in_template_order_and_lands_in_tomo_review`, `::test_the_review_heading_comes_from_the_setup`, `GAP::test_a_mapped_document_still_names_the_notes_not_read_and_the_days_partly_read` | Parts in proposal order instead of row order; the divider wrong; title, target or Approved line changed; the callout dropping not-read notes or partly read days with a mapping (gap M4) |
| F3-AC2 | script | `DS::test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items`, `::test_the_english_labels_and_the_inside_place`, `PS::test_the_rendered_week_reads_by_section`, `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers` | A second or missing box (exact body equality); an empty section ticked; the de/en label swapped; an edited item not reaching the block |
| F3-AC3 | script | `DS::test_a_mapped_week_renders_parts_divider_analysis_and_only_the_groups_with_items`, `::test_the_english_labels_and_the_inside_place`, `::test_a_routed_section_stays_in_template_order_and_lands_in_tomo_review`, `::test_the_review_heading_comes_from_the_setup` | Any landing-line text changed (de, en, before/under/end, analysis and routed sections in "Tomo Review") |
| F3-AC4 | lib + script + e2e + prose pin | `PS::test_an_unticked_section_drops_everything_in_it_the_users_items_too`, `::test_only_items_in_unticked_sections_mean_nothing_to_deliver`, `DC::test_dropped_and_empty_sections_are_named_with_the_users_own_count`, `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers`, `RDL::test_cli_every_problem_name_is_pinned_to_refusing_or_notice`; pin `P2::test_every_preview_notice_is_one_line_and_the_question_still_follows` | `approved_review` keeping an item of an unticked section; `dropped` losing `added`; `section-dropped` leaving NOTICES. The one-line wording: prose pin |
| F3-AC5 | lib + script + prose pin | `PS::test_a_ticked_section_with_nothing_ticked_is_empty`, `::test_a_ticked_empty_section_with_the_users_own_item_is_not_empty`, `SET::test_an_empty_section_emits_no_action`, `::test_a_new_notes_empty_section_gets_no_marker_pair`, `DC::test_dropped_and_empty_sections_are_named_with_the_users_own_count`; pin `P2::test_every_preview_notice_is_one_line_and_the_question_still_follows` | `empty` not set; an empty section given an action or a marker pair; `empty` missing from the preview |
| F3-AC6 | lib + script + prose pin | `PS::test_a_deleted_checkbox_stops_naming_the_section_and_the_line_to_restore`, `::test_the_restore_line_of_an_empty_section_is_unticked`, `::test_a_broken_checkbox_stops`, `::test_a_checkbox_moved_out_of_its_part_stops`, `::test_a_second_checkbox_stops`, `::test_a_deleted_heading_stops_for_the_orphaned_checkbox`, `::test_the_restore_line_is_english_for_an_english_or_broken_frontmatter`, `::test_a_section_without_its_checkbox_lands_nothing`, `SST::test_the_gate_refuses_a_missing_section_checkbox_after_the_approved_line`, `::test_section_checkbox_missing_is_refusing`, `::test_a_deleted_section_checkbox_plans_nothing_and_refuses`, `::test_another_expected_key_first_on_a_heading_with_that_section_ticked_delivers_nothing`, `::test_parse_prints_the_section_problems_and_counts_of_a_mapped_document`; pins `P2::test_every_parse_warning_has_a_plain_language_line`, `::test_every_refusing_preview_problem_has_its_line`, `SK::test_step_6_stops_on_a_missing_section_checkbox_naming_the_section_and_the_restore_line`, `::test_step_7_runs_parse_for_the_section_stop` | The parser not reporting `(key, heading, restore)` for one of six broken forms; the gate not refusing; the plan keeping actions |
| F4-AC1 | e2e + lib + live | `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers`, `SET::test_sections_in_mapping_order_then_tomo_review_with_dense_ids`, `::test_an_empty_section_emits_no_action`, `DC::test_the_preview_lists_every_section_with_lines_mode_and_lines`, `SP::test_first_delivery_maps_the_placement_and_lands_where_hashi_puts_it`, `::test_guard_every_applied_plan_goes_through_the_splice`, `::test_layout_before_at_the_top_lands_in_the_preamble`; R1 10/10 applied (the 1 line outside a block was Obsidian's link update after the month move), R2 24/24, R3b 12/12 with 0 lines outside | A kept section left out of the set; "Tomo Review" first or emitted with nothing for it; the user's added or rewritten items not in the block; a block at another index than its placement; any change outside the blocks under the reference splice |
| F4-AC2 | lib + e2e | `SP::test_first_delivery_maps_the_placement_and_lands_where_hashi_puts_it`, `::test_insert_action_shape`, `::test_replace_action_shape_with_and_without_scope`, `::test_item_line_holding_a_marker_is_escaped_and_the_next_run_is_not_broken`, `DC::test_a_rerun_replaces_the_block_and_says_so`, `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers` | The content not exactly start marker + item lines + end marker; a visible marker form (tracer mutation: 10 red). "Hidden in reading view" is Obsidian's rendering of `%% … %%`, an assumption no test pins |
| F4-AC3 | lib + e2e + live | `SP::test_guard_every_applied_plan_goes_through_the_splice`, `::test_layout_under_with_user_text_keeps_it_below_the_block`, `::test_rerun_twice_keeps_one_block_and_the_user_text`, `UR::test_the_reference_applier_replaces_only_the_block`, `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers`, `::test_a_section_stop_beside_the_place_problem_takes_one_extra_round`, `W4::test_hashi_replace_vectors_through_the_reference`, `::test_hashi_insert_vectors_through_the_reference`; R2 and R3b (0 lines changed outside the blocks; Tomo's own re-check of R3b: 15 diff hunks, all inside) | A character outside the markers changing under the reference splice; another action kind for a mapped section; a user line removed. Against the real Hashi only R2/R3b are evidence (§3 doubted tests) |
| F4-AC4 | script + e2e + prose pin | `DC::test_a_missing_heading_stops_the_whole_delivery_before_any_write`, `::test_an_ambiguous_heading_stops_with_skip_and_review`, `::test_skip_leaves_the_section_out_and_review_routes_it`, `::test_every_section_stop_refuses_with_its_offered_choices`, `SP::test_missing_on_first_delivery_and_rerun_with_its_choices`, `NN::test_an_existing_note_plans_its_sections_and_routes_only_on_the_review_choice`, `SP::test_layout_same_text_at_another_level_is_ambiguous`, `::test_layout_same_text_at_the_same_level_is_ambiguous_also_on_rerun`, `::test_ambiguous_when_hashis_first_match_by_text_and_level_is_another_heading`, `::test_ambiguous_choices_skip_and_review`, `E6::test_a_section_stop_beside_the_place_problem_takes_one_extra_round`; pins `P2::test_every_refusing_preview_problem_has_its_line`, `SCH::test_a_stop_without_choices_ends_before_any_question`, `::test_the_answers_rerun_preview_with_the_flags_and_end_in_the_deliver_question`, `::test_the_flags_and_choices_the_skill_names_are_the_scripts`, `::test_the_stop_lines_follow_the_plan_and_its_notices` | `classify` not refusing a section stop (tracer mutation: 9 red); a missing or doubled heading not stopping or offering other than `skip`/`review`. Asking per section and Abort: prose pin only, not walked |
| F4-AC5 | lib + script + live | `NN::test_a_new_note_from_a_plain_template_gets_every_block_at_hashis_line_with_both_markers`, `::test_the_next_run_finds_every_spliced_block_and_replaces_it`, `::test_a_heading_the_new_note_lacks_routes_and_never_leaves_a_marker`, `::test_a_heading_held_twice_by_the_template_routes`, `::test_a_heading_only_inside_templater_code_routes_and_the_variant_comes_first`, `::test_a_plain_note_routes_every_section_placed_in_the_note`, `::test_pass1_names_the_routed_section_of_a_new_note_in_its_landing_line`, `::test_pass1_routes_every_section_of_a_new_note_without_a_template`, `SET::test_a_new_notes_empty_section_gets_no_marker_pair`; R3a (Q1 `move_note` applied; the note equals the inbox copy minus the 5 `tomo:` lines, 38 `<%` intact) | A block under a heading the new note lacks, holds twice or holds only inside Templater code; the `_tomo` variant not first; the routed landing line missing from the document |
| F4-AC6 | script + prose pin | `DC::test_the_preview_lists_every_section_with_lines_mode_and_lines`, `::test_the_preview_names_each_sections_configured_placement`, `::test_skip_leaves_the_section_out_and_review_routes_it`; pins `P2::test_the_preview_prints_each_sections_lines_and_deliver_routes_choices_needed`, `::test_preview_prints_the_section_target_and_place_then_asks_deliver_or_abort_and_ends_the_turn`, `SK::test_a_section_is_named_by_the_configured_heading_of_its_key` | The preview's `sections[]` without `placement`, `mode` or `lines`; the skill's print line deleted. The heading comes from the skill: prose pin |
| F4-AC7 | lib + e2e | `RM::test_replace_names_both_markers_and_the_scope`, `::test_replace_without_scope_says_the_whole_note`, `::test_empty_replace_content_says_remove_every_line`, `::test_document_shows_every_section_with_heading_placement_and_block`, `GAP::test_the_delivered_readable_instructions_carry_every_sections_block_first_and_on_a_rerun` | `render_md` falling back to "unknown action" for `replace_between_markers`; marker lines, scope, heading or placement missing; `set_md` rendering fewer actions than the set holds (gap M6) |
| F5-AC1 | lib + e2e + schema + live | `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers` (s2 unticked on the re-run keeps its block byte for byte), `SET::test_a_rerun_replaces_each_block_between_its_markers_then_tomo_review`, `SP::test_traced_1_end_with_subsections_is_replaced_in_the_range_with_scope`, `::test_traced_2_under_rerun_replaced_with_scope`, `::test_traced_3_before_replaced_without_scope`, `::test_trailing_feff_and_whitespace_still_count_as_the_marker`, `::test_replace_action_shape_with_and_without_scope`, `UR::test_the_built_action_is_unscoped`, `::test_the_set_validates_against_both_committed_schemas`, `W4::test_producer_defines_the_action_as_the_contract_does`, `::test_hashi_def_is_the_handoff_fragment`; R2 (re-runs of W13 and 2026-03, one section unticked each, 24/24 applied, the unticked round-1 block byte-identical), R3b (11 `replace_between_markers`) | The re-run emitting an insert for a section that holds its block; wrong markers or scope; anything emitted for a section unticked on the re-run; the producer `$def` drifting from Hashi's |
| F5-AC2 | lib + e2e | `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers` (s3 gets `insert_under_marker` on the re-run), `SP::test_markers_of_another_period_or_section_are_not_ours`, `SET::test_a_new_notes_empty_section_gets_no_marker_pair`; R2 (W13 s1's first block on the re-run) | A section without its own block planned as replace, moved or missing |
| F5-AC3 | lib + script + prose pin | `SP::test_traced_2_end_marker_deleted_is_broken`, `::test_sdd_example_end_marker_lost_never_pairs_with_next_block`, `::test_broken_blocks`, `::test_layout_a_block_straddling_a_heading_is_broken`, `::test_traced_2_fenced_start_is_a_hidden_copy_and_broken`, `DC::test_a_broken_block_offers_skip_only`, `::test_every_section_stop_refuses_with_its_offered_choices`; pins `P2::test_every_refusing_preview_problem_has_its_line`, `SCH::test_the_answers_rerun_preview_with_the_flags_and_end_in_the_deliver_question` | A start marker without its end yielding an action or pairing with the next section's end; `review` accepted for a broken block; the stop not refusing. The dialogue: prose pin only, not walked |
| F5-AC4 | script + prose pin | `DC::test_a_rerun_replaces_the_block_and_says_so`, `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers` (`block-replaced`), `SP::test_traced_1_end_with_subsections_is_replaced_in_the_range_with_scope`; pin `P2::test_every_preview_notice_is_one_line_and_the_question_still_follows` | The `block-replaced` notice not emitted on a replace (tracer mutation: 5 red); the skill sentence deleted. The wording: prose pin only |
| F5-AC5 | lib + script + e2e + live | `SP::test_rerun_twice_keeps_one_block_and_the_user_text`, `::test_missing_on_rerun_with_an_intact_block_offers_no_review`, `::test_ambiguous_on_rerun_with_an_intact_block_offers_no_review`, `::test_a_stop_beside_any_earlier_block_material_offers_skip_only`, `::test_moved_under_another_heading_stops_and_confirm_replaces_scoped`, `::test_moved_into_the_preamble_is_never_replaced`, `OB::test_a_renamed_heading_beside_an_intact_block_offers_skip_and_confirm_moved`, `::test_an_ambiguous_heading_beside_an_intact_block_offers_skip_only`, `::test_a_stop_beside_a_broken_earlier_block_offers_skip_only`, `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers` (`marker_count == (1, 1)`); R2 ("every sN exactly once"), R3b (1 + 1 markers per key) | `plan_section` offering `review` beside an earlier block (tracer mutation: 13 red); an insert planned while the block sits elsewhere; a second marker pair after a re-run |
| F6-AC1 | script + e2e + prose pin | `SS::test_a_quarter_without_setup_proposes_folder_format_template_place_language_and_rows`, `::test_a_quarter_format_follows_the_existing_quarterly_notes`, `::test_a_configured_or_typed_quarter_format_beats_the_notes`, `::test_match_saves_nothing`, `ST::test_quarter_candidates_are_the_templates_named_quarter_or_quartal`, `::test_match_for_a_quarter_without_a_configured_format_proposes_the_quarter_default`, `SE::test_writer_input_for_a_quarter_drops_the_null_week_rule`, `CF::test_quarter_input_is_valid_and_forbids_the_week_keys`, `::test_quarter_writer_edits_use_the_quarterly_keys`, `::test_quarter_setup_reads_the_quarterly_keys_with_the_profile_folder`, `W::test_quarter_setup_lands_under_the_quarterly_keys`, `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers[quarter]`; pins `SKS::test_the_quarter_runs_the_same_setup_step`, `::test_review_setup_includes_the_quarter`, `SQ::test_review_setup_walks_the_quarter_like_the_week_and_month`, `::test_a_set_up_quarter_request_goes_on_to_step3` | `match --kind quarter` not proposing folder, `YYYY-[Q]Q`, template, place, language and rows, or not taking the format from existing quarterly notes; the quarter saved under other keys. "One confirm step": prose pin only; the quarter setup ran live (session `19dd9084`) but no walk row records it |
| F6-AC2 | lib + prose pin | `P::test_quarter_word_is_the_last_finished_quarter`, `::test_the_quarter_word_is_case_insensitive`, `::test_a_full_quarter_name_is_that_quarter`, `::test_a_bare_quarter_is_the_most_recent_finished_one_with_the_year_named`, `::test_an_at_picked_quarterly_note_is_its_quarter`, `::test_an_at_picked_quarterly_note_follows_the_configured_format`, `::test_last_finished_quarter`, `::test_a_quarter_is_three_calendar_months`, `::test_the_default_quarter_format_renders_and_parses`, `CF::test_quarter_setup_reads_the_quarterly_keys_with_the_profile_folder`, `RL::test_a_quarter_period_is_inferred_as_quarter`, `::test_open_reviews_lists_a_quarter_by_its_start_and_infers_its_kind`, `SKS::test_both_argument_hints_name_the_quarter`; pins `S::test_an_inferred_year_is_named_before_reading`, `::test_open_reviews_are_handled_before_the_new_request_in_listed_order` | `quarter` not the last finished quarter; `Q4` not 2025-Q4 with `year_inferred`; an @ note not parsed under the quarter format. Naming the year: prose pin only, no year-less quarter walked |
| F6-AC3 | lib + prose pin | `P::test_a_quarter_outside_its_year_is_invalid_with_the_last_quarter_as_example`, `::test_a_bare_quarter_number_outside_1_to_4_is_invalid`, `::test_a_quarter_year_outside_the_range_is_invalid`, `::test_a_quarter_number_outside_1_to_4_is_invalid`, `::test_a_quarter_name_that_does_not_exist_does_not_parse`, `::test_an_unfinished_quarter_names_the_last_finished_one`, `::test_the_quarter_that_ends_today_is_not_finished`, `::test_a_kind_word_before_a_period_of_another_kind_is_invalid`, `::test_the_grammar_names_the_quarter`, `SE::test_start_every_bad_argument_yields_kind_expectation_and_example` (the shared early return); pin `S::test_start_errors_show_expected_and_example_and_write_nothing` | `2026-Q5` not `invalid-period` with its expectation and example; an unfinished quarter accepted or refused without `last_finished` |
| F6-AC4 | lib + script + schema + prose pin + live (partial) | `CH::test_quarter_marks_at_monthly_level`, `::test_the_quarter_writes_no_weekly_marks`, `::test_the_same_notes_read_as_a_month_mark_at_weekly_level`, `::test_a_month_note_never_read_puts_its_days_in_no_mark`, `::test_a_link_to_a_monthly_or_quarterly_note_is_navigation_only_with_its_format_configured`, `::test_a_quarter_reads_every_daily_and_the_day_after`, `::test_boundary_weeks_are_clipped_to_the_quarter_and_their_week_text_tagged`, `::test_monthly_notes_are_split_into_month_text_and_tagged`, `::test_sources_from_config_takes_the_monthly_and_quarterly_setup`, `P::test_the_weeks_overlapping_2026_q1_cross_both_ends`, `::test_a_quarter_has_its_three_months`, `RD::test_a_quarter_run_reads_the_quarter_and_marks_against_the_monthly_notes`, `RS::test_monthly_only_needs_a_monthly_note_and_the_quarter_groups_need_monthly_notes`, `::test_a_review_only_mark_rests_on_the_weekly_or_monthly_note`, `::test_a_mark_of_another_kind_is_not_allowed`, `::test_the_group_tables_keep_the_week_and_month_order_and_add_the_quarter_pair`, `DS::test_the_quarter_marks_and_the_english_month_marks`, `::test_a_quarter_renders_the_quarter_groups_once_it_read_monthly_notes`; pin `SQ::test_step5_names_the_quarter_keys_like_the_months`; R3b (90/90 days, 454 Kado calls, 0 retries, 3 `not_in_monthly` items) | The child level of a quarter set to the week; fewer than 90 dailies or no day after; boundary weeks not clipped; monthly notes not split into `month_text`; `[[2026-02]]` counted as content; a `monthly_only` item without a monthly source. Live the model read the files partly (#270) |
| F6-AC5 | lib + script + prose pin | `CH::test_the_report_names_absent_months_and_weeks`, `::test_a_quarter_without_monthly_or_weekly_notes_is_built_from_the_dailies`, `::test_an_empty_monthly_listing_is_kado_empty_with_the_access_hint`, `::test_a_quarter_without_monthly_config_says_not_configured_and_lists_nothing`, `::test_a_rate_limited_monthly_listing_recovered_by_the_end_pass_reads_the_monthly_notes`, `::test_a_monthly_listing_that_still_fails_is_not_read_without_an_access_hint`, `RD::test_a_quarter_run_reads_the_quarter_and_marks_against_the_monthly_notes`; pin `SQ::test_step4_prints_the_monthly_status_and_notes` | Absent months missing from `monthly_notes`; the wrong `monthly_status`; the quarter not built from the dailies alone. The print: prose pin |
| F6-AC6 | e2e + script + prose pin + live (partial) | `E6::test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers[quarter]`, `E6::test_an_unmapped_review_keeps_the_spec_045_shape[quarter]`, `QR::test_a_quarter_write_resolves_sources_across_all_month_parts`, `::test_a_quarter_document_renders_the_quarter_groups`, `::test_a_mapped_quarter_checks_sections_and_renders_the_quarter_marks`, `::test_a_quarter_whose_index_sections_differ_from_the_rows_is_sections_changed`, `::test_replace_needs_confirm_reads_the_quarter_through_the_loader`, `::test_a_written_quarter_removes_every_read_file_and_the_proposals`, `::test_a_failed_quarter_write_keeps_every_read_file`, `::test_replace_abort_removes_every_read_file_of_a_quarter_and_keeps_meta`, `RD::test_a_quarter_writes_the_index_and_one_part_per_month_and_no_read_json`, `::test_a_stale_read_json_in_the_quarters_stage_folder_is_removed`, `::test_on_the_measured_shape_every_written_file_fits_and_loads_back`, `RP::test_a_quarter_is_an_index_and_one_part_per_month_in_order`, `CH::test_the_quarter_report_holds_no_note_text`, `GAP::test_a_quarter_computes_the_habits_from_the_trackers_of_all_three_months`; pins `SQ::test_step5_reads_the_index_then_each_part_in_turn_then_writes_one_proposals_file`, `::test_the_privacy_rule_covers_every_read_file`; R3a, R3b (first delivery and re-run applied, 0 lines outside) | The quarter Pass 1 → document → Pass 2 → apply chain; `review-doc.py` reading only `read.json`; parts left after clean-up; note text in the report; the quarter's habits left out (gap M3). `RD::test_on_the_measured_shape_…` checks bytes (≤ 256,000), not the Read tool's 25k-token limit, which the live read exceeded (#270) |
| F7-AC1 | script + prose pin | `SS::test_a_typed_template_that_is_not_found_is_reported_with_the_candidates_and_a_null_template`, `::test_a_configured_template_that_is_not_found_is_reported_as_configured`, `::test_a_found_template_carries_no_not_found_key`, `::test_match_saves_nothing`, `ST::test_no_mapping_entry_lists_the_templates_whose_name_fits_the_kind`, `::test_the_flag_wins_over_the_mapping_and_a_missing_choice_is_reported_not_found`, `SI::test_a_template_match_did_not_find_is_refused_even_when_put_back`; pins `SKS::test_a_template_not_found_is_named_before_the_candidates_are_asked`, `::test_a_template_not_found_without_candidates_asks_for_a_typed_name_or_none`, `::test_a_template_choice_rerun_adds_neither_the_old_template_nor_the_old_anchor` | `match` not setting `template_not_found`, keeping the name, or not listing candidates of the kind; `setup-input` accepting the name when put back. "Says" and "asks again": prose pin |
| F7-AC2 | script + prose pin | `SS::test_the_configured_anchor_counts_only_for_the_configured_template`, `::test_rows_saved_for_another_template_are_not_this_templates_rows`, `SI::test_a_template_correction_keeps_the_id_of_a_heading_the_new_template_keeps`, `::test_rows_for_a_template_match_did_not_show_are_refused`, `GAP::test_after_a_template_correction_the_rows_file_holds_only_the_new_templates_rows`; pins `SKS::test_a_table_correction_runs_no_match_and_a_template_change_rebuilds_the_table`, `::test_the_anchor_is_not_carried_over_a_template_change` | The configured-anchor guard removed (tracer run: red); saved rows leaking across templates; `match` carrying the earlier template's rows into the rows file (gap M5) |
| F7-AC3 | script + prose pin | `SS::test_after_a_template_change_dropped_names_the_earlier_rows_the_new_template_lacks`, `::test_a_template_change_to_no_template_drops_every_earlier_row`, `::test_a_same_template_rerun_drops_nothing_even_for_a_row_the_template_lacks`, `SI::test_a_saved_row_whose_heading_the_template_lost_is_named_in_dropped`; pins `SKS::test_the_dropped_headings_are_named_after_a_template_change`, `::test_a_dropped_heading_is_said_kept_or_not_by_whether_the_save_writes_rows` | `dropped` not computed after a change, or computed on a same-template re-run. The naming in the dialogue: prose pin |

## 3. Gaps the trace found

### Closed

Eight criterion parts had no test that could fail. Each is closed by a test in `tests/test_046_close_out_gaps.py`. Each test was proven RED by applying the mutation below in a fresh isolated export (`git archive HEAD | tar -x -C $TMPDIR/co046-mut-<name>-…`, the gap file copied in, `PYTHONDONTWRITEBYTECODE=1`), never in the worktree. Without the gap file every mutation left `tests/test_review_*.py tests/test_046_t*.py tests/test_period.py` green (`2744 passed, 15 skipped` each); with it, each mutation turned exactly its own test red (`1 failed, 7 passed` over the gap file).

| # | Criterion | Part no test could fail | Test | Mutation → RED line |
|---|---|---|---|---|
| M1 | F1-AC1 | a mapping never narrows a **quarter's** read (only the month had an equality test) | `test_a_mapped_quarter_reads_the_same_days_weekly_and_monthly_notes_as_an_unmapped_one` | `review-read.py`, after `result["sections"] = section_definitions(setup)`: `if period.kind == QUARTER: result.pop("monthly", None)` → `FAILED tests/test_046_close_out_gaps.py::test_a_mapped_quarter_reads_the_same_days_weekly_and_monthly_notes_as_an_unmapped_one` |
| M2 | F1-AC10 | the unmapped quarter keeps **every** group, each empty one with its nothing-found line (the quarter tests checked the last two headings) | `test_without_a_mapping_the_quarter_document_holds_every_group_each_empty_one_saying_so` | `review_sections.group_parts`: `if items or keep_empty:` → keep empty groups of a quarter only for `monthly_only` / `not_in_monthly` → `FAILED …::test_without_a_mapping_the_quarter_document_holds_every_group_each_empty_one_saying_so`. A cruder mutation (no empty group for a quarter) is already red in `QR::test_a_quarter_document_renders_the_quarter_groups` and `DS::test_a_quarter_renders_the_quarter_groups_once_it_read_monthly_notes` |
| M3 | F6-AC6 | the **habits** apply to a quarter (every quarter test ran with `trackers=False`) | `test_a_quarter_computes_the_habits_from_the_trackers_of_all_three_months` | `review-doc.py`, after the habits line: `if period.kind == "quarter": accepted[rd.HABITS] = []` → `FAILED …::test_a_quarter_computes_the_habits_from_the_trackers_of_all_three_months` |
| M4 | F3-AC1 | "what was read and missing" stays **with a mapping** (only unmapped goldens render the not-read / partly-read callout) | `test_a_mapped_document_still_names_the_notes_not_read_and_the_days_partly_read` | `review_doc._callout`: `if inp.not_read:` → `if inp.not_read and inp.sections is None:` → `FAILED …::test_a_mapped_document_still_names_the_notes_not_read_and_the_days_partly_read` |
| M5 | F7-AC2 | "no row from the earlier template remains" in the **rows file** `match` keeps for `setup-input` | `test_after_a_template_correction_the_rows_file_holds_only_the_new_templates_rows` | `review_match.py`, after `lost = …`: `if changed: shown = [r for r in previous["rows"] if r not in shown] + shown` → `FAILED …::test_after_a_template_correction_the_rows_file_holds_only_the_new_templates_rows` |
| M6 | F4-AC7 | the readable file **`deliver` writes** carries every section's block (the `RM` tests call `render_md` directly) | `test_the_delivered_readable_instructions_carry_every_sections_block_first_and_on_a_rerun` | `review_delivery.set_md`: `render_instructions_md(plan.actions, …)` → the actions without `replace_between_markers` → `FAILED …::test_the_delivered_readable_instructions_carry_every_sections_block_first_and_on_a_rerun` |
| M7 | F2-AC11 | "never writes into that section" **at delivery** for a mapped row (every delivery-side test called `plan_section` directly or covered only the "Tomo Review" place) | `test_a_mapped_row_landing_off_limits_stops_the_delivery_of_an_existing_and_a_new_note` | `review_actions._sectioned`: both `off_limits=setup.off_limits` → `off_limits=[]` → `FAILED …::test_a_mapped_row_landing_off_limits_stops_the_delivery_of_an_existing_and_a_new_note` (found by the F2 tracer: `2574 passed` under the mutation) |
| M8 | F2-AC11 | "Tomo may still read the user's own text there as a source" (the reader has no off-limits code, so nothing caught a filter added there) | `test_an_off_limits_mark_never_narrows_the_read_a_monthly_own_section_stays_a_source` | `review_period._own_sections`: leave out own sections named by an off-limits row of that kind → `FAILED …::test_an_off_limits_mark_never_narrows_the_read_a_monthly_own_section_stays_a_source` |

Tracer mutations that confirmed existing tests (not gaps): the double-placement check (9 red), the empty-section box (13 red), `keep_empty=True` (4 red), the dropped mark (3 red), `classify` without stops (9 red), `review` always routable (13 red), a visible marker form (10 red), the `block-replaced` notice renamed (5 red), the configured-anchor guard removed (red).

### Not closed by a test

- **F2-AC7 "starting point":** `SKILL.md` step 5 says a section's items are what its description and keywords ask for, "whatever group they would fit", and never uses a row's `groups`. Deleting `groups` from the definitions turns only the `read.json` equality test red. There is no behaviour to pin; §7.
- **F4-AC2 "hidden in reading view":** Obsidian's rendering of `%% … %%`; no test can reach it. The exact marker strings are pinned, so a change to another form is red.
- **F1-AC9 (SDD only):** no Pass 2 test asserts that a mark suffix reaches the delivered block; the PRD criterion ("stay on the items") is met by the document tests.

### Doubted tests, read

- `SP::hashi_apply` (the splice behind the lib-level F4-AC3 guard) is a second Tomo model of Hashi, separate from `e2e_046_sections_walk._replace_between_markers`, and only the latter runs Hashi's own vectors (`W4`). Against the real Hashi only R2 and R3b are evidence.
- `E6`'s `user_text` drops the whole "Tomo Review" range, so a change inside Tomo's own section is not seen by the F4-AC1 "nothing else changes" check. Accepted: that section is Tomo's.
- `DS::test_write_and_replace_refuse_a_section_error_before_any_kado_call` proves the refusal path for duplicate / unknown keys, not for double placement; the path is shared.
- `RD::_run`'s MARKER check is hollow for `quarter_vault()`, which holds no MARKER; the quarter's privacy evidence is `CH::test_the_quarter_report_holds_no_note_text`.
- `CH::test_the_report_names_absent_months_and_weeks` does not assert that the 11 weeks not read are `absent`.
- `SE::test_start_every_bad_argument_yields_kind_expectation_and_example` and `SS::test_match_saves_nothing` have no quarter rows; cited for the kind-agnostic path only.
- `DC::test_every_section_stop_refuses_with_its_offered_choices` builds its `SectionPlan` by hand: it proves `classify`, not `plan_section` (SP covers that).
- `SKS::test_the_table_asks_no_question_of_its_own` is red only for a question inside its slice; `SKS::test_the_request_continues_in_the_same_session_after_the_save` rests on its exact-line half; `SKS::test_a_row_shows_level_and_parent_so_same_text_headings_are_told_apart` half-asserts its own constant.
- `SCH` line 63 (`"then step 8" not in QUESTION`) checks its own constant (the Phase 5 note); only its order and spelling assertions are cited.
- `SKS::test_a_table_correction_runs_no_match_and_a_template_change_rebuilds_the_table` is named for F7-AC2 but pins prose only; F7-AC2's script evidence is the `SS` / `SI` ids and M5.

## 4. Live walk and the consumer's side

The walk ran with Hashi's `feat/179` build (released as `0.33.0` on 2026-11-18, the vendored schema byte-identical at sha256 `51b80e49…c23c91`) in the test vault, owner-run, in four rounds:

| Round | What | Result (Hashi results handoff and T6.3 note) |
|---|---|---|
| R1 (2026-11-17) | first deliveries: week 2026-W13 and month 2026-03 | 10/10 applied; W13 passed every check; 1 line changed outside the blocks: Obsidian's link update after the month move |
| R2 (2026-11-17) | re-runs of W13 and 2026-03, wire v4, one section unticked each | 24/24 applied (week 9, month 15); 0 lines outside the blocks; every replaced block equals its content; the unticked blocks byte-identical; off-limits sections untouched; cleanup trashed all 6 inbox files |
| R3a (2026-11-18) | quarter 2026-Q1, new note | `move_note` applied; the note equals the inbox copy minus the 5 `tomo:` lines, 38 `<%` intact; cleanup by exact path |
| R3b (2026-11-18) | quarter re-run, `target_exists`, 12 markers in the note | 12/12 applied (11 `replace_between_markers` + 1 `replace_section`); 0 lines outside the blocks and "Tomo Review"; 1 + 1 markers per key; Tomo's own re-check: 15 diff hunks, all inside |

Before R1, the W13 re-run stopped `landing-off-limits` on spec 045's old "Tomo Review" right after the off-limits "Check My Own Words" (intended; the owner removed the old section). Before R3a, a quarter delivery stopped at `doc_mark` (`open-unsaved`), the resume refused from a re-plan and the model hand-wrote the mark; fixed by `f9585ca4` (resume from `payloads.json`) and re-walked green in R3a / R3b.

**Not recorded.** The walk notes and handoffs record delivery outcomes. They do not record the planned section-fit rows ("a section whose description no group covers received sourced items", "items read as reminders"), any setup dialogue, a section stop answered in the Deliver step, a template correction, or a year-less quarter. That is why 24 model parts rest on the prose pin alone (Criteria count). No `live-walk.md` was written; this document and the T6.3 notes are the walk record.

**Known limit — the quarter read.** Both round-3 quarter Pass 1 runs (11:16, 14:52) fell back to `grep` on parts of the read files, and the model reported the read as partial. The files exceed the Read tool's 25k-token limit: 717 KB, about 390k tokens in all, the index alone about 82.5k tokens. The earlier 08:30 run handed the read to 4 `general-purpose` subagents it started itself ($2.83). Owner decision 2026-11-19: the redesign moves to #270. The quarter's live evidence for F1-AC1, F6-AC4 and F6-AC6 is therefore evidence on a partial read.

**Owner decisions recorded, not reopened:** `section-ambiguous` stays strict ("found exactly once", also when the anchor is the first copy of its text; Hashi resolves by first match, strict stays safe if that ever changes); Hashi #180 (`cachedRead` splice in older handlers) stays open on Hashi's side and does not touch `replace_between_markers`, which resolves its markers inside the write callback.

Consumer-owned halves: "Hashi applies only between Tomo's markers", "the user's text around it is unchanged" and the cleanup are Hashi's behaviour. Evidence: the vendored schema at `0.33.0` (`W4::test_hashi_def_is_the_handoff_fragment`, `UR::test_the_set_validates_against_both_committed_schemas`), Hashi's vectors through Tomo's reference (`W4::test_hashi_replace_vectors_through_the_reference`), and the R1–R3b results.

## 5. KPIs

Measured from the Tomo session transcripts of 2026-11-17 and 2026-11-18 (`tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance/`, sessions `19dd9084`, `42c0baa6`, `e0aa1fc5`, `97854f11`, `efc53872`, `88e4b1d2`, `ac4c1d09` with its 4 subagents, `07ac4fe2`). Model: Sonnet 5.5 (`claude-sonnet-5-5`), main session; the only subagents are the four `general-purpose` agents the model started itself in `ac4c1d09` for the quarter read.

**Method.** `scripts/tomo-session-stats.py` 0.1.1 counts each API reply once (#262), at $3 / $15 / $3.75 / $0.30 per M tokens; it reports a whole session, and a walk session holds several passes. The per-pass split applied the same counting to the replies between one typed `/review` and the next, with subagent replies joined by timestamp. Which pass a span is comes from the `review-*.py` subcommands the model ran (`read` + `doc write` = Pass 1; `doc parse` + `instructions preview` / `deliver` = Pass 2) and their `--kind` / `--period` / `--stem`. **Active** = the sum over the owner's prompts in the pass of prompt → the model's last record before the next prompt (model and script time, without the owner's reading and answering). **Wall** = first prompt to the last record of the pass (given for Pass 1). **Peak context** = the largest single-turn context (input + cache read + cache write). Only counts, costs and times were read; no transcript text was copied.

### Per pass

| Session | Start | Pass | Prompts | Cost | Active | Wall | Peak context |
|---|---|---|---|---|---|---|---|
| `19dd9084` | 11-17 08:27 | setup week + month + quarter (mapping, off-limits, analysis row) | 21 | $1.718 | 180 s | 20 min | 108,969 |
| `42c0baa6` | 11-17 08:59 | **Pass 1 week W13**, cold (+ Replace) | 2 | $0.839 (Pass 1 alone $0.749) | 81 s | 1.3 min (Pass 1 part) | 141,371 |
| `42c0baa6` | 11-17 09:23 | Pass 1 week W13, warm (+ Replace) | 2 | $0.327 | 25 s | 1.5 min | 144,618 |
| `42c0baa6` | 11-17 09:27 | Pass 2 W13 preview; stop `landing-off-limits`; Pass 1 rewrite after the owner removed the spec 045 section | 3 | $0.999 | 83 s | — | 186,013 |
| `e0aa1fc5` | 11-17 09:33 | **Pass 1 month 2026-03**, cold | 2 | $1.035 | 149 s | 5.5 min | 154,901 |
| `97854f11` | 11-17 09:43 | two parse-only starts (month) | 4 | $0.321 | 17 s | — | 68,113 |
| `efc53872` | 11-17 09:48 | **Pass 2 month** (round 1) + a W13 preview | 4 | $0.464 | 36 s | — | 77,949 |
| `efc53872` | 11-17 13:02 | **Pass 2 week W13** (round 1) | 4 | $0.814 | 57 s | — | 127,617 |
| `88e4b1d2` | 11-17 15:17 | **Pass 1 week W13** re-run (round 2), cold | 1 | $0.686 | 73 s | 1.2 min | 122,764 |
| `88e4b1d2` | 11-17 15:38 | **Pass 2 week W13** re-run | 3 | $0.463 | 29 s | — | 146,239 |
| `88e4b1d2` | 11-17 16:20 | **Pass 1 month** re-run (round 2), warm | 1 | $1.392 | 209 s | 3.5 min | 243,332 |
| `88e4b1d2` | 11-17 16:29 | **Pass 2 month** re-run | 4 | $0.799 | 41 s | — | 272,144 |
| `88e4b1d2` | 11-18 08:15 | **Pass 1 quarter 2026-Q1** (new note), resumed session | 2 | $1.412 | 246 s | 4.3 min | 159,555 |
| `ac4c1d09` | 11-18 08:30 | **Pass 1 quarter**, cold, 4 subagents ($2.833 of it) | 5 | $4.256 | 372 s | 6.4 min | 192,262 |
| `ac4c1d09` | 11-18 10:13 | Pass 2 quarter: `doc_mark` stop, resume refused, hand-written mark (fixed in `f9585ca4`) | 7 | $3.328 | 154 s | — | 285,810 |
| `07ac4fe2` | 11-18 11:16 | **Pass 1 quarter** (round 3a), cold | 2 | $1.463 | 269 s | 5.8 min | 182,498 |
| `07ac4fe2` | 11-18 11:24 | **Pass 2 quarter** (round 3a) | 4 | $0.654 | 39 s | — | 211,405 |
| `07ac4fe2` | 11-18 14:52 | **Pass 1 quarter** re-run (round 3b), compacted session; one `double-placement` refusal pair | 4 | $1.305 | 124 s | 16.8 min | 119,588 |
| `07ac4fe2` | 11-18 15:17 | **Pass 2 quarter** re-run (round 3b) | 3 | $0.478 | 33 s | — | 146,229 |

Total over the walk: **$22.75** (main $19.92, subagents $2.83).

### Verdicts

| KPI (requirements.md Success Metrics, v1.3) | Measured | Verdict |
|---|---|---|
| Weekly Pass 1 ≤ $0.50 | W13 cold $0.749 (08:59) and $0.686 (15:17, fresh session); warm $0.236 (09:23) | **FAIL cold**, PASS warm. Spec 045's $0.469 was a warm run; a fresh session starts at ~62k tokens of context (skill + system) before the first read |
| Monthly Pass 1 ≤ $2.00 and ≤ 7 min | 2026-03: $1.035 / 149 s active / 5.5 min wall (cold); $1.392 / 209 s / 3.5 min (warm, 122k context at start) | PASS, both |
| Pass 2 ≤ $0.75 | W13 $0.814 (first, 4 prompts, two previews) and $0.463 (re-run); month $0.464 (first, with a W13 preview) and $0.799 (re-run, session at 256k context); quarter $0.654 (R3a) and $0.478 (R3b); the stopped quarter delivery $3.328 (the bug path fixed in `f9585ca4`) | **FAIL for 3 of 7** ($0.814, $0.799, $3.328); PASS for the 4 others. The two near misses ran in long sessions; the third is the fixed stop |
| Quarterly Pass 1 ≤ $5.00 and ≤ 20 min | 2026-Q1: $1.412 / 4.3 min; $4.256 / 6.4 min (incl. $2.833 subagents); $1.463 / 5.8 min; $1.305 / 16.8 min wall (124 s active; one `double-placement` refusal pair and the owner's retry) | PASS on all four, **on partial reads** (#270): not the cost of a full read |
| Quarter context use (Phase 4 note) | peak single turn 159,555 / 192,262 / 182,498 / 119,588 tokens; a fresh session starts at ~62k, so the quarter Pass 1 added ~95k–130k on partial reads. The full read is ~390k tokens (owner measurement, 2026-11-19), above a 200k context | recorded; the redesign is #270 |
| 0 changed characters of the user's text outside the markers | R2: 0 lines outside the blocks (week and month); R3b: 0, Tomo's re-check 15 hunks all inside; R1: 1 line, Obsidian's link update after the month move, not an apply | PASS |
| 0 sections with two Tomo blocks | R2 every `sN` exactly once; R3b 1 + 1 markers per key | PASS |
| 0 writes to an off-limits section | R2: the off-limits headings untouched (week `Reflections`, `Check My Own Words`; month `I look forward to`) | PASS |
| 0 items proposed in two places | the script refuses them (F1-AC6); live, one refusal pair in R3b Pass 1, then a document without one | PASS |
| 0 writes outside the inbox before apply | every vault change came from Hashi's apply (T6.3 rule); the e2e fixtures assert inbox-only writes | PASS (not separately audited against Kado's log in this walk) |
| Adoption, section fit (≥ 70 % of sections kept), items (≤ 40 % unticked) | not measured: every run was on `tomo-instance` and the test vault | open, measured after release |

**Spend:** the walk cost **$22.75** over 21 `/review` spans (merged into the 19 rows above) (main $19.92, subagents $2.83); setup for three kinds $1.718. This close-out ran no paid eval and no live run: $0. Cost log: `docs/evolution/inbox-cost-log.md` §"Spec 046 — T6.3 joint walk".

## 6. Validation

- **The single invocation (§1):** `518 passed in 4.18s`.
- **Gap tests on the real tree:** `8 passed` (`tests/test_046_close_out_gaps.py`).
- **Mutations (§3):** M1–M8 each `1 failed, 7 passed` over the gap file — each the gap test alone; without the gap file each left `tests/test_review_*.py tests/test_046_t*.py tests/test_period.py` at `2744 passed, 15 skipped`.
- **ruff:** `./venv/bin/ruff check tests/test_046_close_out_gaps.py` → `All checks passed!`
- **Full pytest:** (worktree, 2026-11-19, HEAD `f0cb76e8` plus the gap file and this document) `11040 passed, 19 skipped, 1 deselected, 1 warning in 414.79s (0:06:54)`; the deselected one is the known unrelated `tests/ide_bridge/test_configure_ide_bridge.py::test_install_smoke_ide_bridge_block_exists` (registry pollution); the skips are the `-m integration` tests and environment skips outside this spec.

## 7. Open items

Verbatim list for the owner (not fixed in this round), each marked **test/doc hygiene**, **behaviour gap** or **admin**:

- **Quarter read size** (#270): the read files exceed the Read limit, the quarter Pass 1 runs on partial `grep` reads or improvised subagents. Redesign (chunked data, agents tiered by model) after brainstorming. — **behaviour gap** (owner decision 2026-11-19, moved out of this spec)
- **KPI misses → limits raised** (owner decision 2026-11-19): weekly Pass 1 cold ($0.749, $0.686 > $0.50) and Pass 2 ($0.814, $0.799 > $0.75) are measured against the amended limits: weekly Pass 1 ≤ $0.80 and Pass 2 ≤ $0.85 (PRD Success Metrics). All measured runs pass them, apart from the stopped delivery ($3.328, which the stored-payload resume fixes). — **resolved**
- **F2-AC7 "starting point" → fixed** (owner decision 2026-11-19): `SKILL.md` 0.2.13 step 5 says "A section whose `groups` names groups starts from what those groups would hold; such a finding goes into the section, not into the group", pinned by `tests/test_046_t4_4_skill_sections.py::test_a_sections_groups_are_its_starting_point_and_the_field_is_the_one_review_read_writes` (RED before the line). Model behaviour: not walked yet. — **resolved, walk pending**
- **Model parts on the prose pin alone (24):** no section-fit row, setup dialogue, Deliver-step section choice, template correction or year-less quarter was walked. The section-fit KPI and the release walk can record them. — **admin** (owner walk)
- **No `live-walk.md`:** the walk lives in the T6.3 notes, the joint-run handoffs (gitignored, ephemeral) and §4–§5 here. — **admin** (accept or write it)
- **Hashi #180** (`cachedRead` splice in older handlers): open on Hashi's side. — **admin**
- **`section-ambiguous` stays strict** also when the anchor is the first copy of its text. — accepted (owner decision 2026-11-19)
- **Mapped callout target stem and not-read / partly-read paths are raw** (path-derived, low risk; Phase 4 note): not checked in the walk. — **test/doc hygiene**
- **"Hidden in reading view"** (F4-AC2) rests on Obsidian's `%% … %%` rendering; no test, no walk row. — **test/doc hygiene** (accepted: platform behaviour)
- **Two Tomo models of Hashi's splice** (`SP::hashi_apply` and the e2e applier) differ (indented markers); only the e2e applier runs Hashi's vectors. — **test/doc hygiene**
- **Weak tests found by the trace:** `SCH` line 63 checks its own constant; `RD::_run`'s MARKER check is hollow for the quarter fixture; `CH::test_the_report_names_absent_months_and_weeks` does not assert the absent weeks; `SE` / `SS` bad-argument and saves-nothing tests have no quarter rows; `SKS::test_the_table_asks_no_question_of_its_own` checks one slice. — **test/doc hygiene**
- **F1-AC9 (SDD wording):** no Pass 2 test asserts the mark suffix reaches the delivered block. — **test/doc hygiene**
- **T6.4 still to do before merge:** the drift check spec vs code; the PR naming spec 046, #263, #256, #267 and Hashi `0.33.0`; spec README Finalize after merge; the Kokoro FYIs (2026-11-14, 2026-11-18 and the follow-up 2026-11-19 on wire v4) are pending on Kokoro's side. — **admin**

Closed in this spec's T6.4 rounds before this document (for the record): `dailies_not_in_*` leaves out attachment embeds (`bc6e1e5c`); peer `sources` stay inside the inbox and the guard is wired into `deliver` (`e681afca`, `61b47872`); the `end` landing wording names the heading's own text (`dc173fa1`); `review-instructions.py` split into run and deliver libs (`c4fecf4b`); the step 7 stop bullet split and the `tomo-help` line reworded (`7b7ddf63`); `load_run` reads the set before the note (T6.2).

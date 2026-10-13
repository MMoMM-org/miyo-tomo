---
title: "Close-out — 039 attachment conflict hardening"
status: draft
---

# Close-out

## Standing rule for this document

Every PRD criterion below traces to a test that was **executed**, named by node
id, not to a task that mentions it. Where no test can hold a criterion, it
traces to the live run (`live-runbook.md` "Evidence table", row numbers below)
or to the consumer's reply, and it says so.

`requirements.md` carries **53** criterion ids (`rg -o '\*\*((F[1-6]|S1|C1)-AC[0-9]+)'`,
deduplicated): F1:11 F2:9 F3:7 F4:8 F5:7 F6:8 S1:2 C1:1. **50 trace to executed
tests**, 2 to documentation (S1), and 1 (F6-AC2) to the live run and the
consumer's own test, because only an executor can fail a move.

The **172 node ids** (the trace tables', three CON-1 ids, and at the end the
three "Not a gap" projection tests) were run **together in one
`pytest` invocation on 2026-10-13**, against `2ab4698e` plus the review-round
changes committed with this revision (§4):

```
308 passed in 2.68s
```

172 node ids collect **308 items**: the difference is parametrisation
(`test_refusal_reason` alone is 48 cases). Checked by script, not by eye:
every listed node id collects at least one item, and every collected item
belongs to a listed node id — nothing deselected, nothing extra. The full suite
on the same tree: **4969 passed, 4 skipped** (4973 items). Three skips are
standing and environmental: the gitignored `_outbox/` attachment, a fixture
absent from this checkout, and the voice model directory. The fourth comes and
goes with the network — the upstream-schema fetch 038's close-out describes
(the first close-out's two runs saw it skip once and pass once). None is a 039
test. `ruff` is clean on every file this close-out touched.

The command, exactly as run (paths relative to the repo root):

```bash
./venv/bin/python -m pytest -q \
  tests/test_039_t3_1_wire_v4.py::test_emitted_wire_carries_proposed_dir_null_and_version_4 \
  tests/test_039_t3_1_wire_v4.py::test_proposed_dir_is_required_and_marked_editable \
  tests/test_039_t3_1_wire_v4.py::test_missing_proposed_dir_fails \
  tests/test_039_t3_1_wire_v4.py::test_a_version_3_wire_fails \
  tests/test_039_t3_1_wire_v4.py::test_vendored_consumer_copy_declares_version_4 \
  tests/test_039_t3_2_folder_line.py::test_detect_records_carry_proposed_dir_none \
  tests/test_039_t3_2_folder_line.py::test_ordinary_conflict_folder_line_directly_after_rename_line \
  tests/test_039_t3_2_folder_line.py::test_no_free_name_variant_renders_folder_line_too \
  tests/test_039_t3_2_folder_line.py::test_folder_line_is_not_a_checkbox \
  tests/test_039_t3_2_folder_line.py::test_folder_text_is_dirname_of_destination_verbatim \
  tests/test_039_t3_2_folder_line.py::test_folder_line_changes_only_the_folder_never_the_tick_or_the_name \
  tests/test_039_t3_3_parser_reads_folder.py::test_edited_folder_is_verbatim_and_owner_supplied \
  tests/test_039_t3_3_parser_reads_folder.py::test_wire_projects_a_non_null_folder_as_owner_supplied \
  tests/test_039_t3_3_parser_reads_folder.py::test_a_folder_typed_inside_the_rename_backticks_is_still_refused_separator \
  tests/test_039_t3_3_parser_reads_folder.py::test_inventory_row_d26_names_the_wire_field_and_the_folder_literal \
  tests/test_039_t3_4_folder_not_consumed_yet.py::test_markdown_edited_folder_line_moves_into_that_folder \
  tests/test_039_t3_4_folder_not_consumed_yet.py::test_both_surfaces_agree_with_each_other \
  tests/test_038_t4_4_the_two_paths_converge.py::test_a_typed_folder_alone_yields_the_identical_instruction_set \
  tests/test_038_t4_4_the_two_paths_converge.py::test_a_typed_folder_and_a_typed_name_yield_the_identical_instruction_set \
  tests/test_038_t4_4_the_two_paths_converge.py::test_the_default_folder_yields_the_identical_instruction_set \
  tests/test_038_t4_4_the_two_paths_converge.py::test_a_refused_folder_is_refused_identically_on_both_paths \
  tests/test_038_t4_4_the_two_paths_converge.py::test_a_folder_equal_to_the_asset_folder_yields_the_identical_instruction_set \
  tests/test_039_t4_6_paths_converge_on_destinations.py::test_untouched_default_folder_lands_on_one_destination \
  tests/test_039_t4_6_paths_converge_on_destinations.py::test_typed_folder_lands_on_one_destination \
  tests/test_039_t4_6_paths_converge_on_destinations.py::test_default_folder_with_trailing_separator_is_refused_on_both \
  tests/test_039_t4_6_paths_converge_on_destinations.py::test_typed_folder_equal_to_the_asset_folder_is_the_default_on_both \
  tests/test_038_inventory_schema_validation.py::test_wire_schema_marks_exactly_26_editable_fields \
  tests/test_038_decision_inventory_join.py::test_real_artefacts_schema_side_join_passes \
  tests/test_038_decision_inventory_join.py::test_real_artefacts_parser_side_join_passes \
  tests/test_039_t1_4_vault_folder_lookup.py::test_absent_is_only_kados_path_not_found \
  tests/test_039_t1_4_vault_folder_lookup.py::test_an_endpoint_404_is_unanswered_not_absent \
  tests/test_039_t1_4_vault_folder_lookup.py::test_any_other_error_is_unanswered \
  tests/test_039_t1_4_vault_folder_lookup.py::test_one_list_dir_per_folder_however_many_views_read_it \
  tests/test_039_t1_5_refusal_reason_no_blank_default.py::test_unknown_code_raises_instead_of_reporting_blank \
  tests/test_039_t1_5_refusal_reason_no_blank_default.py::test_every_member_of_refusal_reasons_is_handled \
  tests/test_039_t1_6_computed_names_pass_typed_rules.py::test_every_computed_name_is_accepted_by_the_typed_name_rules \
  tests/test_039_t1_6_computed_names_pass_typed_rules.py::test_the_join_detects_a_bad_proposer \
  tests/test_039_t1_6_computed_names_pass_typed_rules.py::test_each_source_yields_a_name_for_the_first_free_slot \
  tests/test_039_t2_1_breaks_link_and_unsafe_sequence.py::test_edge_whitespace_breaks_link \
  tests/test_039_t2_1_breaks_link_and_unsafe_sequence.py::test_link_breaking_characters_anywhere \
  tests/test_039_t2_1_breaks_link_and_unsafe_sequence.py::test_breaks_link_sentence_says_link_not_obsidian_forbids \
  tests/test_039_t2_1_breaks_link_and_unsafe_sequence.py::test_breaks_link_sentence_exact \
  tests/test_039_t2_1_breaks_link_and_unsafe_sequence.py::test_sanitize_stem_unchanged \
  tests/test_039_t2_1_breaks_link_and_unsafe_sequence.py::test_unsafe_sequences \
  tests/test_039_t2_1_breaks_link_and_unsafe_sequence.py::test_existing_order_is_kept \
  tests/test_039_t2_1_breaks_link_and_unsafe_sequence.py::test_unsafe_sequence_sentence_exact \
  tests/test_039_t2_1_breaks_link_and_unsafe_sequence.py::test_unsafe_typed_name_does_not_abort_pass_2 \
  tests/test_039_t2_2_check_typed_folder.py::test_refusal_reason \
  tests/test_039_t2_2_check_typed_folder.py::test_accepted_unchanged \
  tests/test_039_t2_2_check_typed_folder.py::test_property_every_path_shape_rejection_is_refused \
  tests/test_039_t2_2_check_typed_folder.py::test_every_reason_is_exercised_and_set_is_closed \
  tests/test_039_t2_2_check_typed_folder.py::test_inbox_path_normalised_for_comparison_only \
  tests/test_039_t2_2_check_typed_folder.py::test_inbox_comparison_ignores_unicode_normalisation \
  tests/test_039_t2_2_check_typed_folder.py::test_order_of_overlapping_inputs \
  tests/test_039_t2_2_check_typed_folder.py::test_sentence_per_reason \
  tests/test_039_t2_2_check_typed_folder.py::test_sentences_are_distinct_and_escape_control_chars \
  tests/test_039_t2_2_check_typed_folder.py::test_unknown_sentence_reason_raises \
  tests/test_039_t4_1_basename_census.py::test_one_search_per_distinct_casefolded_basename \
  tests/test_039_t4_1_basename_census.py::test_searches_two_for_differing_forms_one_for_ascii \
  tests/test_039_t4_1_basename_census.py::test_third_page_is_never_requested_and_none_is_cached \
  tests/test_039_t4_1_basename_census.py::test_budget_exhausted_on_one_variant_is_none \
  tests/test_039_t4_1_basename_census.py::test_error_is_none_and_cached_as_none_not_zero \
  tests/test_039_t4_2_attachment_plan.py::test_row1_no_basename_is_withheld \
  tests/test_039_t4_2_attachment_plan.py::test_row3_refused_typed_folder_is_withheld_without_fallback \
  tests/test_039_t4_2_attachment_plan.py::test_row3_rejected_usable_typed_folder_is_used_f1_ac3 \
  tests/test_039_t4_2_attachment_plan.py::test_row4_empty_name_with_typed_folder_is_refused_blank \
  tests/test_039_t4_2_attachment_plan.py::test_row4_rejected_folder_not_typed_degrades_to_held \
  tests/test_039_t4_2_attachment_plan.py::test_row7_second_source_onto_a_claimed_target_is_a_collision \
  tests/test_039_t4_2_attachment_plan.py::test_row7_two_ignores_onto_one_target_second_is_a_collision \
  tests/test_039_t4_2_attachment_plan.py::test_row8_occupied_rename_target_is_withheld_f3_ac1 \
  tests/test_039_t4_2_attachment_plan.py::test_row8_rejected_ignore_onto_occupied_moves_f3_ac4 \
  tests/test_039_t4_2_attachment_plan.py::test_row8_non_conflict_attachment_onto_now_occupied_target_f3_ac2 \
  tests/test_039_t4_2_attachment_plan.py::test_row8_case_only_occupier_is_occupied_and_named_as_spelled \
  tests/test_039_t4_2_attachment_plan.py::test_row8_a_folder_at_the_target_name_occupies_it \
  tests/test_039_t4_2_attachment_plan.py::test_occupied_target_sentence_variants \
  tests/test_039_t4_2_attachment_plan.py::test_row9_unanswered_folder_moves_unchecked \
  tests/test_039_t4_2_attachment_plan.py::test_row9_rejected_listed_folder_is_checked \
  tests/test_039_t4_2_attachment_plan.py::test_row9_one_folder_unanswered_other_answered_each_judged_by_its_own \
  tests/test_039_t4_2_attachment_plan.py::test_row10_absent_typed_folder_moves_and_will_be_created \
  tests/test_039_t4_2_attachment_plan.py::test_row10_rejected_existing_folder_is_not_created \
  tests/test_039_t4_2_attachment_plan.py::test_row11_plain_attachment_onto_free_target_moves \
  tests/test_039_t4_2_attachment_plan.py::test_row11_rejected_taken_target_is_not_row_11 \
  tests/test_039_t4_2_attachment_plan.py::test_f1_ac5_untouched_folder_line_resolves_to_pass_2_asset_folder \
  tests/test_039_t4_2_attachment_plan.py::test_owner_supplied_folder_equal_to_asset_folder_is_the_default \
  tests/test_039_t4_2_attachment_plan.py::test_f1_ac6_folder_under_keep_or_ignore_is_ignored \
  tests/test_039_t4_2_attachment_plan.py::test_f1_ac10_original_name_in_a_new_folder_is_a_valid_rename \
  tests/test_039_t4_2_attachment_plan.py::test_f2_ac7_a_bad_folder_refuses_one_source_and_plans_the_rest \
  tests/test_039_t4_2_attachment_plan.py::test_f4_ac1_unique_renamed_is_bare_unique_unrenamed_is_untouched \
  tests/test_039_t4_2_attachment_plan.py::test_f4_ac2_the_occupier_of_the_original_makes_it_ambiguous \
  tests/test_039_t4_2_attachment_plan.py::test_f4_ac2_another_in_run_target_counts_even_when_planned_later \
  tests/test_039_t4_2_attachment_plan.py::test_f4_an_undercounting_census_cannot_cancel_another_in_run_target \
  tests/test_039_t4_2_attachment_plan.py::test_f4_ac3_unrenamed_default_folder_ambiguous_is_qualified \
  tests/test_039_t4_2_attachment_plan.py::test_f4_ac4_moved_inbox_sources_are_not_counted \
  tests/test_039_t4_2_attachment_plan.py::test_f4_census_key_is_nfc_a_decomposed_inbox_source_is_subtracted \
  tests/test_039_t4_2_attachment_plan.py::test_f4_ac4_rejected_a_withheld_inbox_copy_stays_and_counts \
  tests/test_039_t4_2_attachment_plan.py::test_a_target_withheld_late_in_pass_a_is_not_counted_in_pass_b \
  tests/test_039_t4_2_attachment_plan.py::test_f4_ac6_census_unanswered_qualifies \
  tests/test_039_t4_2_attachment_plan.py::test_no_attachment_makes_no_vault_call \
  tests/test_039_t4_2_attachment_plan.py::test_one_listing_per_folder_one_search_per_basename_none_for_withheld \
  tests/test_039_t4_3_move_builder_projection.py::test_a_projection_matches_the_pre_change_builder \
  tests/test_039_t4_3_move_builder_projection.py::test_a_entry_key_order_matches_the_pre_change_builder \
  tests/test_039_t4_3_move_builder_projection.py::test_b_typed_folder_refused_carries_every_owner \
  tests/test_039_t4_3_move_builder_projection.py::test_b_vault_occupied_carries_every_owner \
  tests/test_039_t4_3_move_builder_projection.py::test_c_move_ids_by_origin_names_every_owner \
  tests/test_039_t4_3_move_builder_projection.py::test_c_withheld_moves_get_no_id \
  tests/test_039_t4_3_move_builder_projection.py::test_d_typed_folder_refused_holds_the_notes \
  tests/test_039_t4_3_move_builder_projection.py::test_d_vault_occupied_holds_the_notes \
  tests/test_039_t4_3_move_builder_projection.py::test_e_new_kinds_get_their_own_sentence \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_renamed_and_unique_writes_the_bare_new_name_byte_identical_to_037 \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_unrenamed_and_unique_leaves_the_body_untouched \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_ambiguous_unrenamed_default_folder_gets_the_full_path \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_ambiguous_renamed_gets_the_full_new_path \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_suffixes_and_extension_survive_qualification_and_no_alias_is_added \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_original_name_into_a_new_folder_is_qualified_when_ambiguous \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_original_name_into_a_new_folder_is_untouched_when_unique \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_a_run_level_collision_rewrites_nothing \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_a_kept_or_refused_attachment_rewrites_nothing \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_every_owning_note_gets_the_qualified_embed_through_the_render_loop \
  tests/test_039_t4_4_embed_rewrite_reads_plan.py::test_a_unique_unrenamed_attachment_leaves_the_written_note_untouched \
  tests/test_039_t4_5_wire_plan_into_pass_2.py::test_a_folder_shared_by_an_attachment_and_a_note_is_listed_once \
  tests/test_039_t4_5_wire_plan_into_pass_2.py::test_a_run_with_no_attachment_spends_no_census_and_no_extra_listing \
  tests/test_039_t4_5_wire_plan_into_pass_2.py::test_a_bad_typed_folder_refuses_one_item_and_never_reaches_the_path_shape_guard \
  tests/test_039_t4_5_wire_plan_into_pass_2.py::test_the_cost_history_entry_carries_the_three_counters \
  tests/test_039_t4_5_wire_plan_into_pass_2.py::test_no_cost_history_entry_without_the_flag \
  tests/test_039_t4_5_wire_plan_into_pass_2.py::test_garden_audit_and_daily_only_runs_are_byte_identical_to_before \
  tests/test_039_t4_5_wire_plan_into_pass_2.py::test_a_daily_only_run_records_measured_zeros_without_a_client \
  tests/test_039_t4_5_wire_plan_into_pass_2.py::test_an_aborted_render_records_no_cost_entry \
  tests/test_039_t4_7_nfc_target_keys.py::test_typed_nfd_target_is_occupied_by_an_nfc_vault_file \
  tests/test_039_t4_7_nfc_target_keys.py::test_nfd_source_basename_is_occupied_by_an_nfc_vault_file \
  tests/test_039_t4_7_nfc_target_keys.py::test_typed_folder_inside_an_nfd_spelled_inbox_is_refused \
  tests/test_039_t5_1_reporting.py::test_occupied_bullet_names_attachment_target_and_occupier \
  tests/test_039_t5_1_reporting.py::test_unchecked_target_notices_follow_the_final_actions \
  tests/test_039_t5_1_reporting.py::test_refused_folder_bullet_names_attachment_and_rule \
  tests/test_039_t5_1_reporting.py::test_each_folder_reason_has_its_own_sentence_in_the_notice \
  tests/test_039_t5_1_reporting.py::test_unreadable_folder_line_is_not_reported_as_left_blank \
  tests/test_039_t5_1_reporting.py::test_unchecked_target_is_reported_not_checked_and_never_free \
  tests/test_039_t5_1_reporting.py::test_folder_to_be_created_is_listed \
  tests/test_039_t5_1_reporting.py::test_qualified_embeds_are_reported_with_their_reason \
  tests/test_039_t5_1_reporting.py::test_ignore_disclosure_says_the_origin_is_kept \
  tests/test_039_t5_1_reporting.py::test_relay_carries_one_line_per_withheld_and_per_unchecked \
  tests/test_039_t5_1_reporting.py::test_no_executor_internals_in_any_new_sentence \
  tests/test_039_t5_1_reporting.py::test_conductor_relays_unchecked_lines_and_passes_cost_history \
  tests/test_039_t5_1_reporting.py::test_the_conductor_relays_withheld_lines_character_for_character \
  tests/test_039_t5_1_reporting.py::test_inbox_passes_the_conductor_report_through_unchanged \
  tests/test_039_t5_2_delete_waits_for_attachment_moves.py::test_origin_and_audio_peer_delete_name_notes_then_both_assets \
  tests/test_039_t5_2_delete_waits_for_attachment_moves.py::test_shared_attachment_is_named_by_both_origins_deletes \
  tests/test_039_t5_2_delete_waits_for_attachment_moves.py::test_withheld_attachment_id_appears_in_no_delete \
  tests/test_039_t5_2_delete_waits_for_attachment_moves.py::test_keep_in_inbox_leaves_depends_on_unchanged \
  tests/test_039_t5_2_delete_waits_for_attachment_moves.py::test_036_contract_still_holds_with_attachments \
  tests/test_039_t5_2_delete_waits_for_attachment_moves.py::test_instructions_schema_description_names_move_asset \
  tests/test_039_t5_3_executor_needs_no_change.py::test_fixture_covers_the_cases \
  tests/test_039_t5_3_executor_needs_no_change.py::test_every_delete_depends_on_id_names_an_action_in_the_set \
  tests/test_039_t5_3_executor_needs_no_change.py::test_every_depended_on_kind_is_a_kind_the_vendored_schema_allows \
  tests/test_039_t5_3_executor_needs_no_change.py::test_produced_set_validates_against_vendored_schema \
  tests/test_039_t5_3_executor_needs_no_change.py::test_vendored_schema_records_no_kind_order \
  tests/test_039_t5_4_owner_wording.py::test_one_remedy_per_withheld_kind_in_every_surface \
  tests/test_039_t5_4_owner_wording.py::test_ignore_is_reported_once_at_its_move \
  tests/test_039_t5_4_owner_wording.py::test_case_only_occupied_sentence_does_not_put_the_occupier_at_the_target \
  tests/test_039_t5_4_owner_wording.py::test_unchecked_target_gives_an_owner_action \
  tests/test_039_t6_2_vendored_v4.py::test_depends_on_description_says_applied_or_already_in_place \
  tests/test_039_t6_2_vendored_v4.py::test_vendored_instructions_copy_is_the_consumer_file_plus_the_one_string_patch \
  tests/test_039_t6_2_vendored_v4.py::test_vendored_suggestions_copy_is_byte_identical_to_the_live_v4_schema \
  tests/test_039_t6_2_vendored_v4.py::test_suggestions_parity_delta_is_empty \
  tests/test_039_t6_3_qualified_embeds_are_recognised.py::test_triage_resolves_the_qualified_embed_past_a_namesake \
  tests/test_039_t6_3_qualified_embeds_are_recognised.py::test_triage_reports_an_unindexed_qualified_embed_as_unresolved \
  tests/test_039_t6_3_qualified_embeds_are_recognised.py::test_a_note_rendered_by_pass_2_with_a_qualified_embed_is_recognised \
  tests/test_039_t6_3_qualified_embeds_are_recognised.py::test_alias_and_fragment_suffixes_survive_the_round_trip \
  tests/test_039_t6_3_untouched_document_baseline.py::test_an_untouched_document_renders_todays_output_apart_from_two_sanctioned_changes \
  tests/test_039_t6_3_unsafe_folder_does_not_abort_pass_2.py::test_an_unsafe_typed_folder_is_refused_and_the_run_is_produced \
  tests/test_039_t4_3_move_builder_projection.py::test_h_the_builder_holds_no_decision_logic \
  tests/test_039_t4_6_paths_converge_on_destinations.py::test_only_the_attachment_plan_calls_the_typed_guards \
  tests/test_039_t4_6_paths_converge_on_destinations.py::test_the_two_projections_hold_no_decision_token
```

Test ids below are given without the `tests/` prefix. "Live row N" is row N of
`live-runbook.md`'s Evidence table (2026-10-13, Privat-Test, Hashi 0.26.1).

---

## What the trace found

Four gaps, all closed by test and document changes on this branch (§4 in the
review round after the first close-out commit). None needed a production
change.

### 1. F1-AC7 had no test that could fail for it — and its text was not literally true (before the 2026-10-13 amendment)

*"Given an untouched suggestions document, When Pass 2 reads it on either path,
Then its output is byte-identical to today's apart from the wire's version
stamp."* Plan T4.3 named its evidence as *"the full 036/037/038 suite green with
no assertion changed"*. That evidence does not exist: across the branch, 42 test
files of specs 031–038 changed, with 102 added or removed `assert` lines — every
one legitimate (version 3 → 4, `rewrite_renamed_embeds` → the plan-reading
rewrite, the T5.4 wording), and every one a reason the suite could not be the
trace. What was traced instead were parts: the move builder against a capture
from `9e2cb307`, the embed rewrite for unique names, and runs that file no
note. Nothing compared Pass 2's **whole** output for an untouched document with
the output of the code before 039.

`test_039_t6_3_untouched_document_baseline.py` does. One harness runs the real
Pass-1 conflict block, the real parser join and the real `instruction-render.py
main()`; `tests/fixtures/039-t6-3-untouched-baseline/record.py` ran it on the
merge-base `d583cd31` and froze `expected.json`; the test replays it here. The
document has a conflict left on its pre-ticked Rename, a conflict-free
attachment, and a conflict left on Keep in inbox — every basename unique, every
target free, Kado answering.

**The measurement found two differences the criterion did not name** before the
amendment, and the
test pins both exactly, so a third fails it:

1. **Each origin's `delete_source.depends_on` gains the `move_asset` id of the
   attachment its note embeds** — F6-AC1, ADR-10, Kokoro ADR-029 §7. F1-AC7's
   proviso named only F3 and F4 as the deliberate exceptions, not F6.
2. **The Keep-in-inbox bullet's remedy reads as T5.4 worded it** — *"To file
   it after all, tick Rename … and run `/inbox --pass2 --force` before you
   apply. If you have already applied, rename the attachment in the inbox and
   run `/inbox` again."* CON-5 records T5.4's supersessions; this sentence is
   one of them, but F1-AC7 was not narrowed to match.

Notes, manifest, every `move_asset`, every embed: byte-identical to the
baseline. **The owner amended F1-AC7's proviso (decision 2026-10-13):** it now
names both changes — the `delete_source` that also depends on the origin's
`move_asset` (F6-AC1) and the T5.4 Keep-in-inbox wording — as holding even
when every basename is unique, every target free and Kado answering. The
criterion and the test now say the same thing.

**Proven RED by the mutation its docstring names** (isolated `git archive`
copy): drop the census subtraction of this run's moved inbox copies
(`lib/attachment_plan.py:221`, `max(hits - moved_sources[key], 0)` →
`max(hits, 0)`). `plan.png` then counts its own inbox copy and reads as
ambiguous:

```
E   AssertionError: 2026-10-12_0900_zwei.md
1 failed in 0.10s

the line that differs (zwei.md, printed from the harness on the mutated copy):
baseline: Map: ![[karte.png]] ![[plan.png]] ![[foto.png]]
mutated:  Map: ![[karte.png]] ![[Atlas/290 Assets/295 Attachments/plan.png]] ![[foto.png]]
```

Restored, the same copy passes again (`1 passed`).

### 2. F2-AC9's second half was never driven for a folder

*"… it is refused with the same reason F5-AC7 uses, And the rest of the run is
produced."* The reason was pinned on the checker alone
(`test_039_t2_2_…::test_refusal_reason`); the run half was pinned for a typed
**name** (`test_039_t2_1_…::test_unsafe_typed_name_does_not_abort_pass_2`) and
for a folder refused as `escapes_vault`. No test sent `{{`, `<%` or a control
character in a typed **folder** through Pass 2 — the case that, unguarded,
reaches `_check_path_shape` and aborts the whole run.

`test_039_t6_3_unsafe_folder_does_not_abort_pass_2.py` runs `main()` with one
unsafe folder per case and a second, conflict-free item, and asserts the other
item is filed, its attachment moved, and the refusal reported with the
`unsafe_sequence` sentence. **Proven RED** by deleting the `unsafe_sequence`
branch of `check_typed_folder` in an isolated copy:

```
FAILED …[double-brace]  — assert 2 == 0   (Pass 2 aborted, exit 2)
FAILED …[template-tag]  — reported as forbidden_character ('<' is forbidden)
FAILED …[control-char]  — assert 2 == 0   (Pass 2 aborted, exit 2)
3 failed in 0.11s
```

Restored, `3 passed`.

### 3. Six trace tests compared a wall clock

The five F1-AC4 convergence tests (`test_038_t4_4_…`, spec 039 T6.3 section)
and `test_039_t3_4_…::test_both_surfaces_agree_with_each_other` compare two
Pass-2 renders byte for byte. Both renders carry `updated_at`, which the
tomo-block builder stamps from its own clock (`lib/doc_frontmatter._utc_now`),
not from the `datetime` the harness froze. **Measured, not argued:** a pytest
plugin that advances that clock one second per call (simulating two renders
straddling a second boundary) failed all six; with `_utc_now` frozen in
`tests/pass2_harness.py` and in the T3.4 file, the same plugin run gives 76
passed across every harness user. Before the fix they would have failed
whenever a reviewer's run crossed a second boundary between the two renders.
Spec 039 T4.5 had already normalised `updated_at` for its own fixture; the
paths-converge tests had not.

### 4. F4-AC7 was traced to a function production triage does not call

The first close-out traced F4-AC7 to `test_039_t6_3_qualified_embeds_are_recognised.py`,
whose two tests fed what Pass 2 wrote to `attachment_index.extract_attachment_embeds`.
Production triage does not call that extractor: `inbox-triage.py`'s embed
targets come from Kado's `listNotes(fields=["links"])` metadataCache, read by
`resolve_inbox_attachments` (`_strip_alias_and_anchor` → `_is_attachment_target`
→ `resolve_attachments` / `narrow_candidates`). Review proved the gap: adding
`if "/" in target: continue` to `resolve_inbox_attachments` — a later run that
drops every qualified embed — left both tests green. `solution.md` had named the
same wrong owner ("F4-AC7 is owned by the existing `extract_attachment_embeds`");
that line now names `resolve_inbox_attachments`.

Two tests now drive the real reader. They take the body `main()` wrote (with the
`|300`, `|Karte` and `#p2` variants through the same plan-reading rewrite), turn
its embeds into Kado `kind: embed` links, return them from a fake `list_notes`
and call `resolve_inbox_attachments(client, INBOX, index)`. Index holding the
qualified path and a namesake `Archive/karte.png` → `attachments ==
[qualified path]`, nothing unresolved (the suffix narrowing, not ambiguity).
Index lacking it → the note is present with one `unresolved` embed naming the
qualified target, never attachment-free. **Proven RED** by exactly the
reviewer's mutation in an isolated copy:

```
E       AssertionError: {}
FAILED …::test_triage_resolves_the_qualified_embed_past_a_namesake
FAILED …::test_triage_reports_an_unindexed_qualified_embed_as_unresolved
2 failed, 2 passed in 0.12s
```

Restored, `4 passed`. The extractor tests stay; they cover the extractor, not
F4-AC7. One limit, stated rather than hidden: triage's index is the **inbox**
listing, so an attachment Pass 2 filed into the asset folder is never in it.
On a real later run the second case — present, `unresolved`, named — is the
outcome to expect. The first case pins the resolution path for a qualified
target the index does hold.

### Not a gap, recorded so it is not mistaken for one

Many F1–F4 criteria trace to **plan-level** tests (`test_039_t4_2_…`, K1), not
to `instructions.json`. That is valid only because the two projections that
turn the plan into the wire are pinned to decide nothing:
`test_039_t4_3_…::test_h_the_builder_holds_no_decision_logic` and
`test_039_t4_6_…::test_only_the_attachment_plan_calls_the_typed_guards` /
`::test_the_two_projections_hold_no_decision_token` — all three run in the
single invocation above — plus the whole-set convergence tests and the new
baseline test, which see the emitted bytes.

---

## PRD criteria — all 53, traced

### F1 — The target folder is editable on both surfaces

| Criterion | Executed test(s) | Live |
|---|---|---|
| AC1 — wire carries a target-folder field, always present, empty by default; version 4 | `test_039_t3_1_wire_v4.py::test_emitted_wire_carries_proposed_dir_null_and_version_4` + `::test_proposed_dir_is_required_and_marked_editable` + `::test_missing_proposed_dir_fails` + `::test_a_version_3_wire_fails` + `test_039_t3_2_folder_line.py::test_detect_records_carry_proposed_dir_none` | row 1 |
| AC2 — own folder line under the remedy, pre-filled, separate from the rename line | `test_039_t3_2_folder_line.py::test_ordinary_conflict_folder_line_directly_after_rename_line` + `::test_no_free_name_variant_renders_folder_line_too` + `::test_folder_line_is_not_a_checkbox` + `::test_folder_text_is_dirname_of_destination_verbatim` + `::test_folder_line_changes_only_the_folder_never_the_tick_or_the_name` | row 2 |
| AC3 — edited folder + Rename → that folder plus the rename line's name | `test_039_t3_3_parser_reads_folder.py::test_edited_folder_is_verbatim_and_owner_supplied` + `test_039_t3_4_folder_not_consumed_yet.py::test_markdown_edited_folder_line_moves_into_that_folder` + `test_039_t4_2_attachment_plan.py::test_row3_rejected_usable_typed_folder_is_used_f1_ac3` + `test_038_t4_4_the_two_paths_converge.py::test_a_typed_folder_and_a_typed_name_yield_the_identical_instruction_set` | row 3 |
| AC4 — editor folder, rebuilt from the wire alone, identical to the markdown path | `test_038_t4_4_the_two_paths_converge.py::test_a_typed_folder_alone_yields_the_identical_instruction_set` + `::test_a_typed_folder_and_a_typed_name_yield_the_identical_instruction_set` + `::test_the_default_folder_yields_the_identical_instruction_set` + `::test_a_refused_folder_is_refused_identically_on_both_paths` + `::test_a_folder_equal_to_the_asset_folder_yields_the_identical_instruction_set` (whole `instructions.json` and every note file) + the four `test_039_t4_6_paths_converge_on_destinations.py` tests + `test_039_t3_4_…::test_both_surfaces_agree_with_each_other` + `test_039_t3_3_…::test_wire_projects_a_non_null_folder_as_owner_supplied` | Editor run H1: the stub `.md` had no Folder line, so `293 Excalidraw` came from the `.json` |
| AC5 — empty folder, or the destination's own folder → target as today | `test_039_t4_2_…::test_f1_ac5_untouched_folder_line_resolves_to_pass_2_asset_folder` + `::test_owner_supplied_folder_equal_to_asset_folder_is_the_default` + `test_038_t4_4_…::test_the_default_folder_yields_the_identical_instruction_set` + `::test_a_folder_equal_to_the_asset_folder_yields_the_identical_instruction_set` + `test_039_t6_3_untouched_document_baseline.py::test_an_untouched_document_renders_todays_output_apart_from_two_sanctioned_changes` | — |
| AC6 — folder ignored under Keep in inbox / Ignore; Ignore's move unchanged | `test_039_t4_2_…::test_f1_ac6_folder_under_keep_or_ignore_is_ignored` (a refusable `../bad` folder that would be refused if read) | row 12 |
| AC7 — untouched document byte-identical to today | `test_039_t6_3_untouched_document_baseline.py::test_an_untouched_document_renders_todays_output_apart_from_two_sanctioned_changes` (**added by this close-out**, §1) + `test_038_t4_4_…::test_the_default_folder_yields_the_identical_instruction_set` (the wire path equals the markdown path) + `test_039_t4_3_…::test_a_projection_matches_the_pre_change_builder` + `test_039_t4_4_…::test_renamed_and_unique_writes_the_bare_new_name_byte_identical_to_037` + `::test_unrenamed_and_unique_leaves_the_body_untouched` + `test_039_t4_5_…::test_garden_audit_and_daily_only_runs_are_byte_identical_to_before`. The two differences the test pins are the ones the amended proviso names (owner decision 2026-10-13, §1) | — |
| AC8 — folder typed in the rename backticks still refused `separator_present` | `test_039_t3_3_…::test_a_folder_typed_inside_the_rename_backticks_is_still_refused_separator` | — |
| AC9 — one new inventory row; editable fields 25 → 26, both join directions agree | `test_039_t3_3_…::test_inventory_row_d26_names_the_wire_field_and_the_folder_literal` + `test_038_inventory_schema_validation.py::test_wire_schema_marks_exactly_26_editable_fields` + `test_038_decision_inventory_join.py::test_real_artefacts_schema_side_join_passes` + `::test_real_artefacts_parser_side_join_passes` | — |
| AC10 — original basename, only the folder changed → a valid rename | `test_039_t4_2_…::test_f1_ac10_original_name_in_a_new_folder_is_a_valid_rename` + `test_038_t4_4_…::test_a_typed_folder_alone_yields_the_identical_instruction_set` + `test_039_t4_4_embed_rewrite_reads_plan.py::test_original_name_into_a_new_folder_is_qualified_when_ambiguous` + `::test_original_name_into_a_new_folder_is_untouched_when_unique` | rows 3–4 (`leipzig-plan.png` into `296 Karten`) |
| AC11 — no free name, folder set, name empty → refused blank, never filled in | `test_039_t4_2_…::test_row4_empty_name_with_typed_folder_is_refused_blank` (`None` and `""`) + `::test_row4_rejected_folder_not_typed_degrades_to_held` | — |

### F2 — An unusable folder is refused, never repaired

| Criterion | Executed test(s) | Live |
|---|---|---|
| AC1 — `..`, `/`, `~`, `./`, `\`, empty or `.` segment refused, not normalised | `test_039_t2_2_check_typed_folder.py::test_refusal_reason` (`escapes_vault`, `empty_segment` cases; `v.name == folder` proves no normalisation) + `::test_accepted_unchanged` + `::test_property_every_path_shape_rejection_is_refused` (69 000-string corpus: nothing the wire's path-shape guard rejects is accepted) | — |
| AC2 — blank, trailing `/`, segment-edge whitespace, forbidden character, `# ^ [ ]` | `test_039_t2_2_…::test_refusal_reason` + `::test_every_reason_is_exercised_and_set_is_closed` | — |
| AC3 — the inbox or inside it | `test_039_t2_2_…::test_refusal_reason` (`inside_inbox`) + `::test_inbox_path_normalised_for_comparison_only` + `::test_inbox_comparison_ignores_unicode_normalisation` + `test_039_t4_7_nfc_target_keys.py::test_typed_folder_inside_an_nfd_spelled_inbox_is_refused` + `test_039_t4_2_…::test_row3_refused_typed_folder_is_withheld_without_fallback` (the plan passes the vault-relative inbox path) | row 10 (`100 Inbox/Karten`) |
| AC4 — no move; embedding notes held | `test_039_t4_2_…::test_row3_refused_typed_folder_is_withheld_without_fallback` + `test_039_t4_3_move_builder_projection.py::test_b_typed_folder_refused_carries_every_owner` + `::test_d_typed_folder_refused_holds_the_notes` | row 11 |
| AC5 — document and shell name the attachment and the rule, only what was verified | `test_039_t5_1_reporting.py::test_refused_folder_bullet_names_attachment_and_rule` + `::test_each_folder_reason_has_its_own_sentence_in_the_notice` + `::test_unreadable_folder_line_is_not_reported_as_left_blank` + `::test_relay_carries_one_line_per_withheld_and_per_unchecked` + `::test_no_executor_internals_in_any_new_sentence` + `test_039_t2_2_…::test_sentence_per_reason` + `::test_sentences_are_distinct_and_escape_control_chars` + `test_039_t5_4_owner_wording.py::test_one_remedy_per_withheld_kind_in_every_surface` + `test_039_t5_1_…::test_the_conductor_relays_withheld_lines_character_for_character` + `::test_inbox_passes_the_conductor_report_through_unchanged` (the shell relay reaches the owner verbatim through the conductor and `/inbox`; added in T6.3) | rows 10, 21 |
| AC6 — the default folder is not a fallback | `test_039_t4_2_…::test_row3_refused_typed_folder_is_withheld_without_fallback` (`destination: None`) + `test_038_t4_4_…::test_a_refused_folder_is_refused_identically_on_both_paths` (no `move_asset` on either path) + `test_039_t4_6_…::test_default_folder_with_trailing_separator_is_refused_on_both` | row 11 (`100 Inbox/Karten` never created) |
| AC7 — one bad folder never aborts the run | `test_039_t4_2_…::test_f2_ac7_a_bad_folder_refuses_one_source_and_plans_the_rest` + `test_039_t4_5_wire_plan_into_pass_2.py::test_a_bad_typed_folder_refuses_one_item_and_never_reaches_the_path_shape_guard` | — |
| AC8 — non-existent usable folder: move emitted, "will be created" stated | `test_039_t4_2_…::test_row10_absent_typed_folder_moves_and_will_be_created` + `::test_row10_rejected_existing_folder_is_not_created` + `test_039_t5_1_…::test_folder_to_be_created_is_listed` + `test_039_t1_4_vault_folder_lookup.py::test_absent_is_only_kados_path_not_found` | rows 5, 7 |
| AC9 — `{{`, `<%`, control character refused as `unsafe_sequence`; the run is produced | `test_039_t2_2_…::test_refusal_reason` (incl. `\x1c` at a segment edge → `edge_whitespace`) + `::test_order_of_overlapping_inputs` + `test_039_t6_3_unsafe_folder_does_not_abort_pass_2.py::test_an_unsafe_typed_folder_is_refused_and_the_run_is_produced` (**added by this close-out**, §2) | — |

### F3 — Pass 2 checks every attachment target against the vault

| Criterion | Executed test(s) | Live |
|---|---|---|
| AC1 — Rename target taken (any case): no move, notes held | `test_039_t4_2_…::test_row8_occupied_rename_target_is_withheld_f3_ac1` + `::test_row8_case_only_occupier_is_occupied_and_named_as_spelled` + `::test_row8_a_folder_at_the_target_name_occupies_it` + `test_039_t4_3_…::test_d_vault_occupied_holds_the_notes` + `test_039_t4_7_…::test_typed_nfd_target_is_occupied_by_an_nfc_vault_file` | row 17 |
| AC2 — conflict-free destination occupied since Pass 1 → as AC1 | `test_039_t4_2_…::test_row8_non_conflict_attachment_onto_now_occupied_target_f3_ac2` + `test_039_t4_3_…::test_b_vault_occupied_carries_every_owner` (no remedy at all) + `test_039_t4_7_…::test_nfd_source_basename_is_occupied_by_an_nfc_vault_file` | optional probe, **not run** |
| AC3 — free target: move as today | `test_039_t4_2_…::test_row11_plain_attachment_onto_free_target_moves` + `::test_row11_rejected_taken_target_is_not_row_11` + `test_039_t4_3_…::test_a_projection_matches_the_pre_change_builder` + `::test_a_entry_key_order_matches_the_pre_change_builder` (captured from the pre-change builder at `9e2cb307`) | rows 4, 19 |
| AC4 — Ignore: move sent unchanged to the occupied destination | `test_039_t4_2_…::test_row8_rejected_ignore_onto_occupied_moves_f3_ac4` + `::test_row7_two_ignores_onto_one_target_second_is_a_collision` (exempt from the vault half only) | row 12 |
| AC5 — document names attachment, target, occupier, in attachment wording | `test_039_t5_1_…::test_occupied_bullet_names_attachment_target_and_occupier` + `test_039_t4_2_…::test_occupied_target_sentence_variants` + `test_039_t5_4_…::test_case_only_occupied_sentence_does_not_put_the_occupier_at_the_target` + `test_039_t4_3_…::test_e_new_kinds_get_their_own_sentence` | row 18 |
| AC6 — Kado cannot answer: move emitted, reported "not checked", never "free" | `test_039_t4_2_…::test_row9_unanswered_folder_moves_unchecked` + `::test_row9_rejected_listed_folder_is_checked` + `::test_row9_one_folder_unanswered_other_answered_each_judged_by_its_own` + `test_039_t1_4_…::test_an_endpoint_404_is_unanswered_not_absent` + `::test_any_other_error_is_unanswered` + `test_039_t5_1_…::test_unchecked_target_is_reported_not_checked_and_never_free` + `::test_unchecked_target_notices_follow_the_final_actions` + `test_039_t5_4_…::test_unchecked_target_gives_an_owner_action` | row 22: **not reproduced** (see Open) |
| AC7 — one listing per target folder, one or two searches per filed basename, page budget, zero for no attachment | `test_039_t1_4_…::test_one_list_dir_per_folder_however_many_views_read_it` + `test_039_t4_1_basename_census.py::test_one_search_per_distinct_casefolded_basename` + `::test_searches_two_for_differing_forms_one_for_ascii` + `::test_third_page_is_never_requested_and_none_is_cached` + `::test_budget_exhausted_on_one_variant_is_none` + `test_039_t4_2_…::test_no_attachment_makes_no_vault_call` + `::test_one_listing_per_folder_one_search_per_basename_none_for_withheld` + `test_039_t4_5_…::test_a_run_with_no_attachment_spends_no_census_and_no_extra_listing` + `::test_a_folder_shared_by_an_attachment_and_a_note_is_listed_once` | rows 23–24: 3 listings / 3 folders, 4 searches / 4 filed basenames |

### F4 — The embed carries a path only when the basename would be ambiguous

| Criterion | Executed test(s) | Live |
|---|---|---|
| AC1 — unique after the run → bare basename, as today | `test_039_t4_2_…::test_f4_ac1_unique_renamed_is_bare_unique_unrenamed_is_untouched` + `test_039_t4_4_…::test_renamed_and_unique_writes_the_bare_new_name_byte_identical_to_037` + `::test_unrenamed_and_unique_leaves_the_body_untouched` + `::test_a_unique_unrenamed_attachment_leaves_the_written_note_untouched` | editor run H2 (bare embed) |
| AC2 — basename also exists elsewhere (existing file, the occupier, another in-run target) → full path | `test_039_t4_2_…::test_f4_ac2_the_occupier_of_the_original_makes_it_ambiguous` + `::test_f4_ac2_another_in_run_target_counts_even_when_planned_later` + `::test_f4_an_undercounting_census_cannot_cancel_another_in_run_target` + `test_039_t4_4_…::test_ambiguous_renamed_gets_the_full_new_path` | row 6 |
| AC3 — unrenamed, default folder, ambiguous → qualified too | `test_039_t4_2_…::test_f4_ac3_unrenamed_default_folder_ambiguous_is_qualified` + `test_039_t4_4_…::test_ambiguous_unrenamed_default_folder_gets_the_full_path` + `::test_every_owning_note_gets_the_qualified_embed_through_the_render_loop` | rows 8–9 (owner confirmed in Obsidian) |
| AC4 — own inbox copy and other moved inbox files not counted | `test_039_t4_2_…::test_f4_ac4_moved_inbox_sources_are_not_counted` + `::test_f4_census_key_is_nfc_a_decomposed_inbox_source_is_subtracted` + `::test_f4_ac4_rejected_a_withheld_inbox_copy_stays_and_counts` + `::test_a_target_withheld_late_in_pass_a_is_not_counted_in_pass_b` + `test_039_t6_3_untouched_document_baseline.py::…` (RED on exactly this mutation, §1) | — |
| AC5 — extension, size, alias, anchor kept | `test_039_t4_4_…::test_suffixes_and_extension_survive_qualification_and_no_alias_is_added` + `test_039_t6_3_qualified_embeds_are_recognised.py::test_alias_and_fragment_suffixes_survive_the_round_trip` | — |
| AC6 — uniqueness unanswered → qualified | `test_039_t4_2_…::test_f4_ac6_census_unanswered_qualifies` + `test_039_t4_1_…::test_error_is_none_and_cached_as_none_not_zero` + `test_039_t5_1_…::test_qualified_embeds_are_reported_with_their_reason` | — |
| AC7 — a later run still recognises a qualified embed as an attachment | `test_039_t6_3_qualified_embeds_are_recognised.py::test_triage_resolves_the_qualified_embed_past_a_namesake` + `::test_triage_reports_an_unindexed_qualified_embed_as_unresolved` (what `main()` and the rewrite wrote, as Kado embed links, through triage's real reader `resolve_inbox_attachments`; **added by this close-out**, §4) | — |
| AC8 — withheld move rewrites no embed | `test_039_t4_4_…::test_a_kept_or_refused_attachment_rewrites_nothing` + `::test_a_run_level_collision_rewrites_nothing` + the K1 rows that assert `embed is None` on every withheld kind (`_held`): `test_039_t4_2_…::test_row1_no_basename_is_withheld`, `::test_row3_refused_typed_folder_is_withheld_without_fallback`, `::test_row7_second_source_onto_a_claimed_target_is_a_collision`, `::test_row8_occupied_rename_target_is_withheld_f3_ac1` | row 20 |

### F5 — A typed name that would break the link is refused (#185)

| Criterion | Executed test(s) |
|---|---|
| AC1 — leading/trailing whitespace refused, not trimmed | `test_039_t2_1_breaks_link_and_unsafe_sequence.py::test_edge_whitespace_breaks_link` (`v.name == name`) |
| AC2 — `# ^ [ ]` refused | `test_039_t2_1_…::test_link_breaking_characters_anywhere` (4 characters × 3 positions) |
| AC3 — one shared reason; the sentence says "would break the link", never "forbidden" | `test_039_t2_1_…::test_breaks_link_sentence_says_link_not_obsidian_forbids` + `::test_breaks_link_sentence_exact`; AC1 and AC2's tests assert the same `breaks_link` code |
| AC4 — a note title with `#` derives the same filename | `test_039_t2_1_…::test_sanitize_stem_unchanged` (`sanitize_stem("C# Notizen")`, the function `_dest_join` uses) |
| AC5 — an unknown reason is never reported as blank | `test_039_t1_5_refusal_reason_no_blank_default.py::test_unknown_code_raises_instead_of_reporting_blank` + `::test_every_member_of_refusal_reasons_is_handled` + `test_039_t2_2_…::test_unknown_sentence_reason_raises` (the folder sentences too) |
| AC6 — every computed name passes the typed-name rules | `test_039_t1_6_computed_names_pass_typed_rules.py::test_every_computed_name_is_accepted_by_the_typed_name_rules` + `::test_the_join_detects_a_bad_proposer` (negative control) + `::test_each_source_yields_a_name_for_the_first_free_slot` |
| AC7 — `{{`, `<%`, control character refused, one reason; the run is produced | `test_039_t2_1_…::test_unsafe_sequences` + `::test_existing_order_is_kept` + `::test_unsafe_sequence_sentence_exact` + `::test_unsafe_typed_name_does_not_abort_pass_2` (real `main()`) |

### F6 — An origin is deleted only after its attachments have arrived (#186)

| Criterion | Evidence |
|---|---|
| AC1 — origin's delete (and its audio peer's) waits for every attachment move | `test_039_t5_2_delete_waits_for_attachment_moves.py::test_origin_and_audio_peer_delete_name_notes_then_both_assets` + `::test_036_contract_still_holds_with_attachments` + `test_039_t6_3_untouched_document_baseline.py::…` (exact `depends_on` per origin through `main()`). Live rows 13, 19 |
| AC2 — attachment move fails at apply → delete skipped, origin and attachment stay | **Live only — no Tomo test can fail a move.** Live row 15: I10 failed *"both source and destination present"*, I16 `skipped-dependency (dependsOn: I10)`, `Radebeul.md` + jpg still in the inbox. Repeated in the editor run (H3: I11 failed, I17 skipped) and in Hashi's QA vault on a different failure (*Source missing*: I07 failed, I11 skipped). **Consumer's own test:** `assetDependsOn.test.ts` (Hashi `c217f66`), "your cascade probe: I03 fails and I05 and I06 are skipped … both origins and the inbox `karte.png` stay". Tomo's half is AC1's tests: the delete names the move |
| AC3 — attachment shared by two origins: both deletes wait for its one move | `test_039_t5_2_…::test_shared_attachment_is_named_by_both_origins_deletes` + `test_039_t4_3_…::test_c_move_ids_by_origin_names_every_owner` |
| AC4 — a move withheld at build time is named by no delete | `test_039_t5_2_…::test_withheld_attachment_id_appears_in_no_delete` + `test_039_t4_3_…::test_c_withheld_moves_get_no_id` |
| AC5 — kept in inbox: delete unchanged, embed still resolves to the inbox file | `test_039_t5_2_…::test_keep_in_inbox_leaves_depends_on_unchanged` + `test_039_t4_4_…::test_a_kept_or_refused_attachment_rewrites_nothing` |
| AC6 — the contract's description names attachment moves, in Tomo's and the vendored copy | Tomo half: `test_039_t5_2_…::test_instructions_schema_description_names_move_asset` + `test_039_t6_2_vendored_v4.py::test_depends_on_description_says_applied_or_already_in_place` (both files) + `::test_vendored_instructions_copy_is_the_consumer_file_plus_the_one_string_patch` (sha256 `9c9565d0…826f`). **Consumer half, by reply:** Hashi applied the patch as `a0d88f8` and reports *"our file is sha256 `9c9565d08caa…826f`, the same as your `771a8a7a` copy"* — a hash comparison, because Hashi cannot `cmp` against our tree from its container |
| AC7 — the consumer's executor needs no change, asserted against its cascade | Tomo half: `test_039_t5_3_executor_needs_no_change.py::test_fixture_covers_the_cases` + `::test_every_delete_depends_on_id_names_an_action_in_the_set` + `::test_every_depended_on_kind_is_a_kind_the_vendored_schema_allows` + `::test_produced_set_validates_against_vendored_schema` + `::test_vendored_schema_records_no_kind_order`. **Consumer half, by reply:** *"your reading of our tree is correct on every point"* (`KIND_ORDER`, merged `depends_on`, the `failed` → `skipped-dependency` cascade), now `assetDependsOn.test.ts` on their side. Live row 16: Hashi 0.26.1 unchanged |
| AC8 — Ignore disclosure: the origin is kept if the move fails | `test_039_t5_1_…::test_ignore_disclosure_says_the_origin_is_kept` + `test_039_t5_4_…::test_ignore_is_reported_once_at_its_move`. Live row 14 |

### S1 — documentation, which no test can hold

Verified by read-through on 2026-10-13:

| Criterion | Where it lives |
|---|---|
| S1-AC1 — the folder line, the refusal rules for folders and names, the editor sanitising | `docs/usage.md:90-104` (Folder line; a folder never goes into the Rename line; the editor's picker), `:120-125` (*"the editor cleans the name up for you, visibly … Tomo itself never does"*), `:127-152` (six name and nine folder refusal classes in owner terms) |
| S1-AC2 — no "checked only in Pass 1"; "occupied" and "not checked" explained | `docs/troubleshooting.md:242-247` (*"Pass 2 looks at the vault again for the final path"*), `:265-292` ("Pass 2 Says a Target Is Occupied or Not Checked", both messages, the remedy before and after apply) |

### C1 — the run reports how many vault lookups the checks cost

| Criterion | Executed test(s) | Live |
|---|---|---|
| AC1 — lookups recorded alongside the run's existing call counts | `test_039_t4_5_…::test_the_cost_history_entry_carries_the_three_counters` (counters read off the shared instances, and equal to the fake's own call log) + `::test_no_cost_history_entry_without_the_flag` + `::test_a_daily_only_run_records_measured_zeros_without_a_client` + `::test_an_aborted_render_records_no_cost_entry` + `test_039_t5_1_…::test_conductor_relays_unchecked_lines_and_passes_cost_history` (the conductor passes `--cost-history`) | row 23 |

### CON-1 — not a criterion, run with the trace

`test_039_t3_1_…::test_vendored_consumer_copy_declares_version_4` +
`test_039_t6_2_…::test_vendored_suggestions_copy_is_byte_identical_to_the_live_v4_schema` +
`::test_suggestions_parity_delta_is_empty`. The consumer reports the same file
`cmp`-identical at `c217f66`.

---

## Success Metrics

| KPI | Met by |
|---|---|
| Adoption — every criterion traced to a test executed in one run | This document: 50 of 53 to the single invocation above; S1 to documentation; F6-AC2 to the live run and the consumer's test, by necessity |
| Quality — no delete can apply after a failed attachment move, asserted for every delete Tomo emits | Every delete, by construction of the test set: `test_039_t5_3_…::test_every_delete_depends_on_id_names_an_action_in_the_set` and `test_039_t5_2_…::test_036_contract_still_holds_with_attachments` (`set(move_asset ids) <= set(origin depends_on)`). Observed live (row 15) |
| Quality — no bare embed for a basename the run knew to be non-unique | F4-AC2/AC3/AC6's tests, the render loop test, and the baseline test in the other direction (unique stays bare) |
| Cost — calls bounded by distinct folders + distinct filed basenames (×2 for NFC/NFD), zero without an attachment | F3-AC7's tests; live rows 23–24 |

---

## Open — recorded rather than closed

1. **F3-AC6 has never happened live.** Row 22 is n/a by design: no run has met a
   Kado listing that errors with something other than `Path not found`. Whether
   Kado answers a **denied** `listDir` with an error ("not checked") or with an
   empty listing ("will be created") is unknown; if the latter, that is a
   finding against PRD Rule 5. The runbook's optional probe needs a change to
   the Kado key's permissions and was not run.
2. **F3-AC2 live** is likewise an optional probe, not run. The tests drive it
   end to end through the plan and the projection; no run has seen a
   destination taken between Pass 1 and Pass 2.
3. **F1-AC7's text** — closed: the owner amended the proviso on 2026-10-13 (§1).
   Listed here so the earlier recommendation is not read as still open.
4. **F6-AC2's Tomo-side assurance is structural.** Tomo proves the delete
   names the move; only the executor proves the skip. Both were observed
   (live, three times, and in Hashi's test), but a future executor change is
   guarded by Hashi's `assetDependsOn.test.ts`, not by anything in this repo.
5. **F4-AC7's realistic later-run outcome is "present, unresolved".** Triage's
   index holds inbox files only, so a qualified embed whose target already
   left the inbox is reported present but unresolved, not resolved.
6. **The Adoption KPI is met for 50 of 53** (S1 by documentation, F6-AC2 by
   the live run). The Quality KPI "every delete" is a fixture-set assertion:
   it holds for every delete in the test set, not for every delete a vault can
   produce.
7. **`/inbox`'s stop-on-failed-triage rule (`e9a7adff`) has no live evidence.**
   It is backed by its runtime text and a string test
   (`test_inbox_step_1_stops_when_triage_fails`) only.
8. **The vendored instructions copy led the consumer by one patch.** `771a8a7a`
   (= `c217f66` + patch) was ahead of Hashi until Hashi applied it as `a0d88f8`;
   hash `9c9565d0…826f` was confirmed equal on both sides. Accepted inversion.

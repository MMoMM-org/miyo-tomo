---
title: "Close-out — 040 relevant MOCs per item"
status: complete
---

# Close-out

## Standing rule for this document

Every PRD criterion below traces to a test that was **executed**, named by node
id, not to a task that mentions it. Where the PRD's verification table names
the live run as the method, the criterion traces to the after-runs recorded in
[`baseline.md`](baseline.md), and the close-out says so. Per-item details (MOC
titles, item stems) stay in the gitignored `tomo-instance/spec-040-baseline/`;
this document cites counts and item numbers only.

`requirements.md` carries **30** criteria: F1:7 F2:5 F3:3 F4:4 F5:3 F6:3 S1:2
S2:2 C1:1. **28 trace to executed tests** (deterministic or prose-contract,
as the PRD's table assigns them), 2 (S2) to document review. F1-AC1 and F3-AC1
also carry the live evidence the PRD requires. F1-AC1's live evidence is
**partial** (§3).

## 1. The single invocation

The **64 node ids** in the trace table were run **together in one `pytest`
invocation on 2026-10-24**, against `7b2b707e`:

```
90 passed in 25.97s
```

64 node ids collect **90 items**. The difference is parametrisation.
Collection was checked by script, not by eye: every listed node id collects at
least one item, and every collected item belongs to a listed node id. Nothing
was deselected and nothing extra was collected.

The full suite ran on `8b12aefb` (then `06cdbb7d`: the branch was rewritten afterwards to strip vault titles from `baseline.md`, and the trees differ only there), the same tree minus the three gap assertions
of §4: **5093 passed, 4 skipped**. All four skips are environmental:

- the gitignored `_outbox/` attachment;
- a fixture absent from this checkout;
- the upstream-schema fetch, offline at the time;
- the voice model directory.

None is a 040 test. The gap assertions ran in the invocation above and in their
own files (28 passed). `ruff` is clean on every file this close-out touched.

<details><summary>The command, exactly as run</summary>

```bash
./venv/bin/python -m pytest -q \
  tests/integration/test_040_relevant_mocs_e2e.py::test_an_existing_moc_reaches_the_owner_as_an_unticked_link \
  tests/test_040_analyst_prose.py::test_a_failing_reader_fails_the_item \
  tests/test_040_analyst_prose.py::test_every_reader_call_checks_the_run_id \
  tests/test_040_analyst_prose.py::test_step_4_anchors_read_the_fetched_detail \
  tests/test_040_analyst_prose.py::test_step_4_decision_table_rows_in_order \
  tests/test_040_analyst_prose.py::test_step_4_keeps_the_guard_and_placeholder_rules \
  tests/test_040_analyst_prose.py::test_step_4_nominates_by_meaning_with_the_cap \
  tests/test_040_analyst_prose.py::test_step_4_placement_fallback_tiers_are_kept \
  tests/test_040_analyst_prose.py::test_step_4_reads_names_and_placeholder_targets \
  tests/test_040_analyst_prose.py::test_step_75b_derives_the_filename_before_writing_names \
  tests/test_040_analyst_prose.py::test_step_75b_drops_unresolved_names_with_an_issue \
  tests/test_040_analyst_prose.py::test_step_75b_fetches_detail_once_or_skips \
  tests/test_040_analyst_prose.py::test_the_full_moc_list_is_never_read \
  tests/test_040_duplicate_proposals.py::test_converted_actions_drop_the_new_moc_offer \
  tests/test_040_duplicate_proposals.py::test_converted_actions_list_the_existing_moc_unticked \
  tests/test_040_duplicate_proposals.py::test_exactly_the_four_duplicates_are_converted \
  tests/test_040_duplicate_proposals.py::test_only_unconverted_topics_reach_proposed_mocs \
  tests/test_040_duplicate_proposals.py::test_unconverted_and_suppressed_actions_are_unchanged \
  tests/test_040_duplicate_proposals.py::test_wire_projection_shows_the_appended_moc_unselected \
  tests/test_040_duplicate_proposals.py::test_without_a_usable_context_nothing_converts \
  tests/test_040_moc_folders_and_exclude.py::test_in_moc_folders_compares_with_the_vault_path_key \
  tests/test_040_moc_folders_and_exclude.py::test_in_moc_folders_is_true_for_direct_and_nested_paths \
  tests/test_040_moc_folders_and_exclude.py::test_in_moc_folders_rejects_sibling_folders_sharing_a_prefix \
  tests/test_040_moc_folders_and_exclude.py::test_in_moc_folders_with_no_folders_is_false \
  tests/test_040_moc_folders_and_exclude.py::test_is_excluded_moc_accepts_the_tag_in_any_spelling \
  tests/test_040_moc_folders_and_exclude.py::test_is_excluded_moc_rejects_near_misses_and_empty_input \
  tests/test_040_moc_folders_and_exclude.py::test_moc_folder_prefixes_normalises_every_config_shape \
  tests/test_040_moc_folders_and_exclude.py::test_moc_folder_prefixes_without_concepts_is_empty \
  tests/test_040_reader_modes.py::test_512_moc_names_stay_under_12_kb \
  tests/test_040_reader_modes.py::test_a_case_whitespace_nfc_variant_resolves_when_unique \
  tests/test_040_reader_modes.py::test_a_matching_run_id_changes_nothing \
  tests/test_040_reader_modes.py::test_a_variant_matching_two_names_is_unresolved \
  tests/test_040_reader_modes.py::test_an_exact_name_wins_over_its_ambiguous_variants \
  tests/test_040_reader_modes.py::test_each_delivered_name_returns_exactly_its_entry \
  tests/test_040_reader_modes.py::test_moc_names_prints_every_name_in_mocs_order_compact \
  tests/test_040_reader_modes.py::test_run_id_mismatch_fails_in_every_mode \
  tests/test_040_reader_modes.py::test_the_21st_distinct_name_is_omitted \
  tests/test_040_reader_modes.py::test_unknown_names_are_unresolved_with_exit_zero \
  tests/test_040_scale_512.py::test_512_distinct_typical_titles \
  tests/test_040_scale_512.py::test_512_duplicated_as_in_173_still_arrive_whole \
  tests/test_040_scale_512.py::test_long_titles_raise_the_names_warning \
  tests/test_040_shared_ctx_names.py::test_an_excluded_moc_frees_its_title_for_the_other_holder \
  tests/test_040_shared_ctx_names.py::test_classification_mocs_keep_a_bare_name_and_their_flag \
  tests/test_040_shared_ctx_names.py::test_every_name_is_unique \
  tests/test_040_shared_ctx_names.py::test_exclude_note_alone_keeps_a_moc_eligible \
  tests/test_040_shared_ctx_names.py::test_excluded_moc_is_not_eligible \
  tests/test_040_shared_ctx_names.py::test_moc_propose_link_pool_still_contains_an_excluded_moc \
  tests/test_040_shared_ctx_names.py::test_placeholder_targets_are_sorted_unique_moc_names \
  tests/test_040_shared_ctx_names.py::test_placeholder_targets_is_an_empty_list_without_placeholders \
  tests/test_040_shared_ctx_names.py::test_titles_differing_only_in_case_collide \
  tests/test_040_shared_ctx_names.py::test_traced_example_yields_exactly_the_sdd_names \
  tests/test_040_shared_ctx_names.py::test_two_colliding_mocs_both_inside_the_folders_both_carry_paths \
  tests/test_040_shared_ctx_names.py::test_without_moc_folders_every_colliding_moc_carries_its_path \
  tests/test_040_size_guards.py::test_512_mocs_keep_their_full_detail \
  tests/test_040_size_guards.py::test_names_over_threshold_warns_once_and_still_writes \
  tests/test_040_size_guards.py::test_size_guards_never_alter_the_context \
  tests/test_040_size_guards.py::test_summary_line_carries_exactly_the_sdd_fields \
  tests/test_040_skill_prose.py::test_both_builder_commands_are_identical \
  tests/test_040_skill_prose.py::test_both_paths_dispatch_the_same_analyst \
  tests/test_040_skill_prose.py::test_reset_pass1_clears_the_context_and_names_files \
  tests/test_040_skill_prose.py::test_the_context_is_deleted_before_it_is_built \
  tests/test_040_skill_prose.py::test_the_report_relays_the_duplicate_count \
  tests/test_moc_tree_builder_inline_tags.py::test_frontmatter_and_inline_merged_deduped \
  tests/test_moc_tree_builder_inline_tags.py::test_inline_exclude_moc_matches_constant
```

</details>

## 2. Trace

| Criterion | Method | Node ids |
|---|---|---|
| F1-AC1 | deterministic + prose contract; live: §3 (partial) | `tests/test_040_reader_modes.py::test_moc_names_prints_every_name_in_mocs_order_compact`<br>`tests/test_040_analyst_prose.py::test_step_4_reads_names_and_placeholder_targets`<br>`tests/test_040_analyst_prose.py::test_the_full_moc_list_is_never_read` |
| F1-AC2 | deterministic | `tests/test_040_shared_ctx_names.py::test_traced_example_yields_exactly_the_sdd_names`<br>`tests/test_040_scale_512.py::test_512_distinct_typical_titles` |
| F1-AC3 | deterministic | `tests/test_040_shared_ctx_names.py::test_traced_example_yields_exactly_the_sdd_names`<br>`tests/test_040_shared_ctx_names.py::test_titles_differing_only_in_case_collide`<br>`tests/test_040_moc_folders_and_exclude.py::test_in_moc_folders_is_true_for_direct_and_nested_paths`<br>`tests/test_040_moc_folders_and_exclude.py::test_in_moc_folders_rejects_sibling_folders_sharing_a_prefix`<br>`tests/test_040_moc_folders_and_exclude.py::test_in_moc_folders_compares_with_the_vault_path_key`<br>`tests/test_040_moc_folders_and_exclude.py::test_moc_folder_prefixes_normalises_every_config_shape` |
| F1-AC4 | deterministic | `tests/test_040_shared_ctx_names.py::test_two_colliding_mocs_both_inside_the_folders_both_carry_paths`<br>`tests/test_040_shared_ctx_names.py::test_without_moc_folders_every_colliding_moc_carries_its_path`<br>`tests/test_040_moc_folders_and_exclude.py::test_moc_folder_prefixes_without_concepts_is_empty`<br>`tests/test_040_moc_folders_and_exclude.py::test_in_moc_folders_with_no_folders_is_false` |
| F1-AC5 | deterministic | `tests/test_040_shared_ctx_names.py::test_every_name_is_unique`<br>`tests/test_040_reader_modes.py::test_each_delivered_name_returns_exactly_its_entry`<br>`tests/test_040_reader_modes.py::test_a_case_whitespace_nfc_variant_resolves_when_unique`<br>`tests/test_040_reader_modes.py::test_a_variant_matching_two_names_is_unresolved`<br>`tests/test_040_reader_modes.py::test_an_exact_name_wins_over_its_ambiguous_variants` |
| F1-AC6 | deterministic | `tests/test_040_scale_512.py::test_512_distinct_typical_titles`<br>`tests/test_040_scale_512.py::test_512_duplicated_as_in_173_still_arrive_whole`<br>`tests/test_040_scale_512.py::test_long_titles_raise_the_names_warning`<br>`tests/test_040_reader_modes.py::test_512_moc_names_stay_under_12_kb`<br>`tests/test_040_size_guards.py::test_names_over_threshold_warns_once_and_still_writes` |
| F1-AC7 | deterministic | `tests/test_040_shared_ctx_names.py::test_classification_mocs_keep_a_bare_name_and_their_flag` |
| F2-AC1 | deterministic + prose contract | `tests/test_040_reader_modes.py::test_each_delivered_name_returns_exactly_its_entry`<br>`tests/test_040_reader_modes.py::test_the_21st_distinct_name_is_omitted`<br>`tests/test_040_scale_512.py::test_512_distinct_typical_titles`<br>`tests/test_040_analyst_prose.py::test_step_4_nominates_by_meaning_with_the_cap`<br>`tests/test_040_analyst_prose.py::test_step_75b_derives_the_filename_before_writing_names`<br>`tests/test_040_analyst_prose.py::test_step_4_anchors_read_the_fetched_detail` |
| F2-AC2 | deterministic | `tests/test_040_size_guards.py::test_512_mocs_keep_their_full_detail`<br>`tests/test_040_size_guards.py::test_size_guards_never_alter_the_context`<br>`tests/test_040_scale_512.py::test_512_distinct_typical_titles` |
| F2-AC3 | prose contract | `tests/test_040_analyst_prose.py::test_step_4_placement_fallback_tiers_are_kept` |
| F2-AC4 | prose contract | `tests/test_040_analyst_prose.py::test_step_75b_fetches_detail_once_or_skips` |
| F2-AC5 | deterministic + prose contract | `tests/test_040_reader_modes.py::test_unknown_names_are_unresolved_with_exit_zero`<br>`tests/test_040_reader_modes.py::test_a_variant_matching_two_names_is_unresolved`<br>`tests/test_040_analyst_prose.py::test_step_75b_drops_unresolved_names_with_an_issue` |
| F3-AC1 | prose contract; live: seeded item, both after-runs | `tests/test_040_analyst_prose.py::test_step_4_decision_table_rows_in_order` |
| F3-AC2 | prose contract | `tests/test_040_analyst_prose.py::test_step_4_decision_table_rows_in_order` |
| F3-AC3 | prose contract | `tests/test_040_analyst_prose.py::test_step_4_decision_table_rows_in_order`<br>`tests/test_040_analyst_prose.py::test_step_4_keeps_the_guard_and_placeholder_rules` |
| F4-AC1 | deterministic | `tests/test_040_duplicate_proposals.py::test_exactly_the_four_duplicates_are_converted`<br>`tests/test_040_duplicate_proposals.py::test_converted_actions_drop_the_new_moc_offer`<br>`tests/test_040_duplicate_proposals.py::test_only_unconverted_topics_reach_proposed_mocs`<br>`tests/integration/test_040_relevant_mocs_e2e.py::test_an_existing_moc_reaches_the_owner_as_an_unticked_link` |
| F4-AC2 | deterministic | `tests/test_040_duplicate_proposals.py::test_converted_actions_list_the_existing_moc_unticked`<br>`tests/test_040_duplicate_proposals.py::test_wire_projection_shows_the_appended_moc_unselected`<br>`tests/integration/test_040_relevant_mocs_e2e.py::test_an_existing_moc_reaches_the_owner_as_an_unticked_link` |
| F4-AC3 | deterministic | `tests/test_040_duplicate_proposals.py::test_unconverted_and_suppressed_actions_are_unchanged`<br>`tests/test_040_duplicate_proposals.py::test_only_unconverted_topics_reach_proposed_mocs`<br>`tests/test_040_duplicate_proposals.py::test_without_a_usable_context_nothing_converts` |
| F4-AC4 | deterministic + prose contract | `tests/test_040_duplicate_proposals.py::test_exactly_the_four_duplicates_are_converted`<br>`tests/test_040_skill_prose.py::test_the_report_relays_the_duplicate_count`<br>`tests/integration/test_040_relevant_mocs_e2e.py::test_an_existing_moc_reaches_the_owner_as_an_unticked_link` |
| F5-AC1 | deterministic | `tests/test_040_shared_ctx_names.py::test_excluded_moc_is_not_eligible`<br>`tests/test_040_shared_ctx_names.py::test_exclude_note_alone_keeps_a_moc_eligible`<br>`tests/test_040_shared_ctx_names.py::test_an_excluded_moc_frees_its_title_for_the_other_holder`<br>`tests/test_040_moc_folders_and_exclude.py::test_is_excluded_moc_accepts_the_tag_in_any_spelling`<br>`tests/test_040_moc_folders_and_exclude.py::test_is_excluded_moc_rejects_near_misses_and_empty_input`<br>`tests/test_moc_tree_builder_inline_tags.py::test_inline_exclude_moc_matches_constant`<br>`tests/test_moc_tree_builder_inline_tags.py::test_frontmatter_and_inline_merged_deduped`<br>`tests/integration/test_040_relevant_mocs_e2e.py::test_an_existing_moc_reaches_the_owner_as_an_unticked_link` |
| F5-AC2 | deterministic | `tests/test_040_shared_ctx_names.py::test_moc_propose_link_pool_still_contains_an_excluded_moc` |
| F5-AC3 | deterministic | `tests/test_040_duplicate_proposals.py::test_unconverted_and_suppressed_actions_are_unchanged`<br>`tests/test_040_duplicate_proposals.py::test_only_unconverted_topics_reach_proposed_mocs`<br>`tests/test_040_shared_ctx_names.py::test_excluded_moc_is_not_eligible` |
| F6-AC1 | prose contract | `tests/test_040_skill_prose.py::test_both_builder_commands_are_identical`<br>`tests/test_040_skill_prose.py::test_both_paths_dispatch_the_same_analyst`<br>`tests/test_040_skill_prose.py::test_the_context_is_deleted_before_it_is_built`<br>`tests/test_040_skill_prose.py::test_the_report_relays_the_duplicate_count` |
| F6-AC2 | deterministic + prose contract | `tests/test_040_reader_modes.py::test_run_id_mismatch_fails_in_every_mode`<br>`tests/test_040_reader_modes.py::test_a_matching_run_id_changes_nothing`<br>`tests/test_040_analyst_prose.py::test_every_reader_call_checks_the_run_id`<br>`tests/test_040_analyst_prose.py::test_a_failing_reader_fails_the_item`<br>`tests/test_040_skill_prose.py::test_the_context_is_deleted_before_it_is_built` |
| F6-AC3 | prose contract | `tests/test_040_skill_prose.py::test_reset_pass1_clears_the_context_and_names_files` |
| S1-AC1 | deterministic | `tests/test_040_shared_ctx_names.py::test_placeholder_targets_are_sorted_unique_moc_names`<br>`tests/test_040_shared_ctx_names.py::test_placeholder_targets_is_an_empty_list_without_placeholders` |
| S1-AC2 | prose contract | `tests/test_040_analyst_prose.py::test_step_4_decision_table_rows_in_order`<br>`tests/test_040_analyst_prose.py::test_step_4_keeps_the_guard_and_placeholder_rules` |
| C1-AC1 | deterministic | `tests/test_040_size_guards.py::test_summary_line_carries_exactly_the_sdd_fields` |
| S2-AC1 | document review | `PRIVACY.md` "What reaches the model": MOC names go to every item; headings, callouts and `has_footer` go only for picked MOCs; the exclude tag "is **not an access control**" |
| S2-AC2 | document review | tier-2 `workflows/inbox-processing.md` Phase A note (names, per-MOC detail); tier-3 `inbox/inbox-analysis.md` "Post-040 Update" (names, nomination, `--mocs-from`, the exclude tag for the inbox) |

**F5-AC3 is traced through a contract, not one test.** The builder never emits
an excluded MOC (`test_excluded_moc_is_not_eligible`). The mutator only offers
MOCs from the built context, so a proposal named after an excluded MOC is shown
unchanged (the `excluded-index` row in `test_040_duplicate_proposals.py`). The
end-to-end test runs both halves together but proposes a different name.

## 3. Live evidence and the KPIs

There were two after-runs on the identical 12-item set, against two
before-runs:

| Run | Run id |
|---|---|
| after-1 | `2026-10-24T15-41-07Z-f1879d` |
| after-2 | `2026-10-24T18-21-04Z-d23bfc` |

[`baseline.md`](baseline.md) holds every figure. A first attempt at after-2 died
in triage on Kado HTTP 429 and a read timeout under host load, before any
analyst ran, and is not counted.

| KPI | Target | after-1 | after-2 | Verdict |
|---|---|---|---|---|
| Candidate agreement vs before-1 | ≥ 70% | 67% | 67% | 🔴 missed |
| Candidate agreement vs before-2 | ≥ 70% | 60% | 50% | 🔴 missed |
| Proposed MOCs equal to an eligible title | 0 | 0 | 0 | 🟢 |
| MOC reads delivered as a preview (scanner) | 0 | 0 of 36 | 0 of 41 | 🟢 |
| Cache-write / item | ≤ 106,490 | 95,792 | 98,863 | 🟢 mean 97,328 (−18%) |
| $ / item | ≤ 0.603 | 0.538 | 0.567 | 🟢 mean 0.553 (−9%) |
| Nominated MOCs with headings carry them | at 65 and 512 | detail fetched whole in every `--mocs-from` | | 🟢 (512: `test_040_scale_512.py`) |
| Seeded item (F3-AC1) | existing MOC linked, no proposal | 0.9, pre-checked | 0.9, pre-checked | 🟢 |

**F1-AC1 live: partial.** 8 of 12 analysts read the names in after-1, and 10 of
12 in after-2. The two that never did in either run are the two empty test
notes. They read Step 1 only and skip MOC matching altogether, as they did in
both before-runs. That behaviour predates this spec.

The other two misses were in after-1 only:

- the daily-log item, which has no MOC step;
- a content-free control note. It read the placeholder targets but not the
  names. Its proposal never reached the document, because the reducer
  suppresses atomics under 0.5 worthiness.

The prose contract that every analysis reads the names is in force
(`test_step_4_reads_names_and_placeholder_targets`). It does not bind an
analyst that decides an empty note has nothing to match.

### Agreement KPI: missed, owner decision 2026-10-24

The owner chose to document the miss rather than re-tune before close-out.
Follow-up: #200.

**Not run noise alone.** The two after-runs agree with each other less (62% and
50%) than the two before-runs did (78% and 70%).

**More candidates.** The after analysts keep more secondary candidates: 13 and
16, against 9 and 10. They also pre-check more (3 and 2, against 1 and 1).

**Thematic candidates only:** after-1 agrees 86% with before-1 and 71% with
before-2; after-2 agrees 71% and 57%.

**Every difference, with its reason.** Item numbers follow the item order of
`before-1.json`. Every dropped candidate was a secondary pick, scored 0.15–0.3.
No pre-checked candidate of a before-run was dropped.

| Pair | Dropped | Items: kind, score |
|---|---|---|
| before-1 → after-1 | 3 | 2: thematic 0.2 · 3: classification 0.3 · 9: classification 0.18 |
| before-1 → after-2 | 3 | 2: thematic 0.2 · 3: classification 0.3 · 9: thematic 0.22 |
| before-2 → after-1 | 4 | 2: thematic 0.17 · 3: classification 0.2 · 4: thematic 0.17 · 10: classification 0.3 |
| before-2 → after-2 | 5 | 2: classification 0.15, thematic 0.17 · 3: classification 0.2 · 4: thematic 0.17 · 9: thematic 0.2 |

Reasons, per item:

- **Item 2.** The after-runs matched this note to a placeholder target
  (decision row 1) and, in one run, to a classification MOC. They did not keep
  the travel MOC the before-runs listed at 0.17–0.2.
- **Item 3.** The after-runs nominated one or two thematic travel MOCs by meaning
  and dropped the classification MOC at 0.2–0.3. That is the trade the spec wants
  (thematic over classification), but it counts against agreement.
- **Item 4.** One before-run listed a travel MOC at 0.17. The after-runs listed
  a classification MOC and the same thematic MOC instead.
- **Item 9.** This item's secondary set changes in every run, before-runs
  included. The after-runs kept a different secondary each time.
- **Item 10.** One before-run listed a classification MOC at 0.3 beside the
  pre-checked primary. after-2 lists it again, after-1 did not.

## 4. Gaps the trace found

Three criteria had no test that could fail. Each was closed by an assertion,
committed as `7b2b707e`. Each assertion was proven RED by applying the
mutation its docstring names, then restoring the file from git:

| Criterion | Assertion | Mutation that turns it red |
|---|---|---|
| F2-AC1 (up to three candidates per thread) | `test_step_4_nominates_by_meaning_with_the_cap` pins `Keep the top 3 with \`score ≥ 0.15\`` | "top 3" → "top 5" |
| F2-AC3 (fallback without headings or callouts) | `test_step_4_placement_fallback_tiers_are_kept` (new) | TIER-3 removed; TIER-4's body-line fallback removed |
| F6-AC1 (both paths behave the same) | `test_both_paths_dispatch_the_same_analyst` (new) | force path dispatches `general-purpose` |

Before this, F6-AC1 rested on identical builder commands. Those prove the
context is the same, not that the same analyst reads it.

## 5. Found on the way, filed

- **#199** — the analyst branches on `daily_log.enabled`, which no context
  carries. Found when T2.2 built the reader's contract fixture with the real
  builder. Pinned in `tests/test_read_shared_ctx.py` as a known dead reference.
- **#200** — secondary-candidate stability since this spec (§3).

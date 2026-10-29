---
title: "Close-out — 042 /moc-propose finds MOC members through the link graph"
status: complete
---

# Close-out

## Standing rule for this document

Every criterion below traces to a test that was **executed**, named by node id,
not to a task that mentions it. Where only a real run can show the behaviour
(budget and 429 in a live scan, the owner's tick ratio), the criterion also
traces to [`live-validation.md`](live-validation.md), and the line relied on is
quoted from there unedited. Where a criterion's wording predates a Phase 5
owner decision, §3 says so and cites the README Decisions Log row.
`requirements.md` was not edited.

## Criteria count

- **PRD (`requirements.md` v1.4): 29 criteria.** F1:5 F2:4 F3:5 F4:4 F5:5 F6:4
  F7:2. The plan's 29 still holds: the v1.4 amendment rewrote F5-AC1 in place
  (fair share instead of all-or-nothing), it added none.
- **SDD (`solution.md` v1.2): 30 EARS criteria.** The same 29 IDs, 1:1 with the
  PRD and restated at component level, plus **F2-AC5** (the parsers skip
  `around:` and `**Extends:**` sections, so neither discovery nor rejection
  touches the squelch registry). F2-AC5 has no PRD criterion. It records the
  README decision of 2026-10-28 ("around: rejection writes no squelch entry").
- One table covers both documents (§2). Each row is a PRD criterion. The SDD
  criterion with the same ID is traced by the same node ids; where the SDD
  restatement is stricter (F5-AC2 names 120 and 0.3 s, F6-AC4 adds "never log"),
  the stricter form is what the ids test. F2-AC5 has its own row.

## 1. The single invocation

The **119 node ids** in the trace table ran **together in one `pytest`
invocation on 2026-10-29**, against `91f7fad6`:

```
140 passed in 1.49s
```

119 node ids collect **140 items**; the difference is parametrisation.
Collection was checked by script, not by eye: every listed node id collects at
least one item, and every collected item belongs to a listed node id
(`ids 119 items 140 unique-items 140`, no id collecting nothing, no item
outside the list).

<details><summary>The command, exactly as run</summary>

The ids are in the trace table, one per line in the file given to `xargs`. One
list of 119 ids fits in one command line, so `xargs` made one invocation; the
single `140 passed` line above is its only summary.

```bash
xargs ./venv/bin/python -m pytest -q < "$TMPDIR/co042/ids.txt"
```

</details>

## 2. Trace

Method: **det** = deterministic test of a script or library; **prose** = the
runtime-prose contract (`tests/test_042_prose.py`); **e2e** = the
`tests/integration/test_moc_propose_e2e.py` pipeline from discovery through
`instruction-render` and `instructions-diff`; **live** = `live-validation.md`.
The RED column names the mutation under which the cited test was run and went
red (§4). "—" means the test asserts the behaviour by name and was not
doubted.

| Criterion | Method | Node ids | RED proof |
|---|---|---|---|
| F1-AC1 note linked with ≥ 2 members → unticked `- [ ]` Children line, any mode | det + e2e; live | `tests/test_link_members.py::TestAugment::test_traced_example`<br>`tests/test_moc_discovery_links.py::test_top_cluster_gets_note_linked_with_two_members`<br>`tests/test_reducer_moc_proposal_mode.py::test_link_members_render_after_topic_members`<br>`tests/integration/test_moc_propose_e2e.py::test_042_tag_run_ticked_link_member_reaches_the_instructions` | M5 |
| F1-AC2 exactly 1 member → not added | det | `tests/test_link_members.py::TestAugment::test_node_in_one_member_list_is_not_added`<br>`tests/test_moc_discovery_links.py::test_top_cluster_gets_note_linked_with_two_members` | — |
| F1-AC3 topic member also linked → once, as topic member | det | `tests/test_link_members.py::TestAugment::test_existing_member_is_not_added`<br>`tests/test_moc_discovery_links.py::test_stem_collision_builds_lookup_map_by_path` | M1 |
| F1-AC4 qualifies for two clusters → in each, unticked | det | `tests/test_link_members.py::TestAugment::test_node_qualifying_in_two_clusters_is_in_both`<br>`tests/test_moc_discovery_links.py::test_note_qualifying_for_two_rendered_clusters_listed_in_each`<br>`tests/test_reducer_moc_proposal_mode.py::test_link_members_render_after_topic_members` | M5 |
| F1-AC5 ticked link members get topic-member `up::`/`related::`/Override handling, unticked nothing | det + e2e; live | `tests/test_moc_proposal_parser.py::test_ticked_link_line_is_supporting_item`<br>`tests/test_moc_proposal_parser.py::test_unticked_link_line_is_not_supporting_item`<br>`tests/test_around_proposal_consumers.py::test_ticked_neighbour_line_is_a_supporting_item_and_unticked_is_not`<br>`tests/test_042_t4_4_extension_render.py::test_member_gets_the_same_rule_4x_outcome_as_a_new_mocs_child`<br>`tests/test_042_t5_3d_up_always_kept.py::test_override_unticked_keeps_any_existing_up_as_related`<br>`tests/integration/test_moc_propose_e2e.py::test_042_tag_run_ticked_link_member_reaches_the_instructions` | — |
| F2-AC1 `around:<note>` → one new-MOC proposal, seed ticked, neighbours unticked | det | `tests/test_moc_discovery_around.py::test_two_eligible_neighbours_build_one_new_moc_cluster`<br>`tests/test_reducer_moc_proposal_mode.py::test_around_report_renders_seed_ticked_and_neighbours_linked`<br>`tests/test_moc_discovery_around.py::test_ineligible_note_seed_is_refused_with_its_reason` | — |
| F2-AC2 < 2 neighbours → no proposal, "fewer than 3 notes" | det | `tests/test_moc_discovery_around.py::test_fewer_than_two_eligible_neighbours_abort` | — |
| F2-AC3 uncached seed → not found; refused/unreadable seed → seed lookup failure naming it | det | `tests/test_moc_discovery_around.py::test_uncached_target_is_not_found_with_remedy`<br>`tests/test_moc_discovery_around.py::test_cached_seed_that_kado_refuses_is_a_seed_lookup_failure` | — |
| F2-AC4 `Around:` and other casings → free text | prose + det | `tests/test_042_prose.py::test_command_whitelist_lists_around`<br>`tests/test_042_prose.py::test_command_keeps_capitalised_variants_as_free_text_for_around`<br>`tests/test_042_prose.py::test_agent_maps_lowercase_around_to_around_mode`<br>`tests/test_042_prose.py::test_agent_routes_capitalised_around_to_free_text`<br>`tests/test_moc_discovery_around.py::test_route_input_leaves_around_prefix_in_free_text_alone` | M6 |
| SDD F2-AC5 `around:` / `**Extends:**` sections never reach the squelch registry | det | `tests/test_around_proposal_consumers.py::test_rejecting_an_around_doc_writes_no_registry_entry`<br>`tests/test_around_proposal_consumers.py::test_unticked_around_section_is_not_handed_to_squelch_unticked`<br>`tests/test_around_proposal_consumers.py::test_rejecting_an_extend_section_writes_no_registry_entry`<br>`tests/test_around_proposal_consumers.py::test_extend_section_is_in_no_split_list_ticked_or_not`<br>`tests/test_around_proposal_consumers.py::test_rejecting_a_topic_doc_still_writes_a_registry_entry` (control)<br>`tests/test_moc_discovery_around.py::test_around_never_reads_or_writes_the_squelch_registry` | — |
| F3-AC1 `around:<MOC>` lists linked notes without `up::` to it, unticked | det + e2e; live | `tests/test_moc_discovery_around.py::test_moc_target_lists_neighbours_without_up_to_it`<br>`tests/test_moc_discovery_around.py::test_extension_members_carry_no_tick`<br>`tests/test_moc_discovery_around.py::test_frontmatter_up_list_naming_the_moc_later_is_present`<br>`tests/test_moc_discovery_around.py::test_parent_moc_among_neighbours_is_never_a_member`<br>`tests/test_moc_discovery_around.py::test_one_missing_member_is_enough`<br>`tests/integration/test_moc_propose_e2e.py::test_042_around_moc_extension_reaches_the_instructions` | — |
| F3-AC2 no missing members → no proposal, reported | det | `tests/test_moc_discovery_around.py::test_moc_without_missing_members_writes_no_proposal` | — |
| F3-AC3 accepted extension → `up:: [[MOC]]` per ticked member, one MOC line per member not yet linked; diff verifies | det + e2e | `tests/test_moc_proposal_parser.py::test_accepted_extension_is_extend_moc_with_only_its_fields`<br>`tests/test_042_t4_4_extension_render.py::test_three_member_extension_emits_up_for_all_and_lines_for_unlinked`<br>`tests/test_042_t4_4_extension_render.py::test_member_gets_the_same_rule_4x_outcome_as_a_new_mocs_child`<br>`tests/test_042_t5_3d_up_always_kept.py::test_extension_member_with_unresolved_up_keeps_it_as_related`<br>`tests/test_042_t4_4_extension_render.py::test_main_moc_without_anchor_still_emits_the_line`<br>`tests/test_042_t4_4_extension_render.py::test_main_withholds_an_extension_whose_moc_is_gone`<br>`tests/test_042_t4_4_extension_render.py::test_diff_accepts_three_ticked_with_one_already_linked`<br>`tests/test_042_t4_4_extension_render.py::test_diff_fails_on_a_missing_add_relationship`<br>`tests/test_042_t4_4_extension_render.py::test_diff_fails_on_an_extra_link_to_moc`<br>`tests/integration/test_moc_propose_e2e.py::test_042_around_moc_extension_reaches_the_instructions` | — |
| F3-AC4 member the MOC already links → `up::`, no duplicate line | det + e2e | `tests/test_042_t4_4_extension_render.py::test_member_already_linked_by_the_moc_gets_up_but_no_line`<br>`tests/test_042_t4_4_extension_render.py::test_a_backlink_alone_does_not_count_as_linked`<br>`tests/test_042_t4_4_extension_render.py::test_already_linked_is_asked_once_with_outgoing_and_no_limit`<br>`tests/integration/test_moc_propose_e2e.py::test_042_around_moc_extension_reaches_the_instructions` | M9 |
| F3-AC5 extension visibly distinct: names the MOC, no title/location/template | det | `tests/test_reducer_moc_proposal_mode.py::test_extension_section_shape`<br>`tests/test_reducer_moc_proposal_mode.py::test_extension_has_no_create_fields` | — |
| F4-AC1 link line names the members (or seed / MOC) it is linked with | det | `tests/test_reducer_moc_proposal_mode.py::test_link_members_render_after_topic_members`<br>`tests/test_reducer_moc_proposal_mode.py::test_around_report_renders_seed_ticked_and_neighbours_linked` | — |
| F4-AC2 link member with existing `up::` shows both (§3: label wording) | det | `tests/test_reducer_moc_proposal_mode.py::test_existing_up_annotation_precedes_link_suffix`<br>`tests/test_042_t5_3d_up_always_kept.py::test_link_member_labels_carry_the_reason` | M4 |
| F4-AC3 "Why this proposal" counts link members | det | `tests/test_reducer_moc_proposal_mode.py::test_why_counts_link_members_only_when_present` | — |
| F4-AC4 any member line parses back as the same note | det | `tests/test_reducer_moc_proposal_mode.py::test_link_lines_round_trip_through_the_suggestion_parser`<br>`tests/test_suggestion_parser_moc_branch.py::test_link_line_is_child_not_candidate_stem`<br>`tests/test_squelch_rejection.py::test_link_lines_do_not_change_the_squelch_signature`<br>`tests/test_moc_proposal_parser.py::test_ticked_link_line_is_supporting_item`<br>`tests/test_moc_proposal_howto_block.py::test_readers_give_identical_results_with_and_without_the_block`<br>`tests/test_042_close_out_gaps.py::test_t53d_labels_do_not_change_which_note_a_line_is` (gap G1) | G1 |
| F5-AC1 over budget → fair share, larger cluster `sampled`, share 0 `skipped_budget`, proposals written, both counted | det + prose + e2e; live | `tests/test_link_members.py::TestAugment::test_big_cluster_is_sampled_in_item_order_and_small_still_runs`<br>`tests/test_link_members.py::TestAugment::test_hits_count_looked_up_members_only`<br>`tests/test_link_members.py::TestAugment::test_zero_share_with_uncached_members_is_skipped_budget`<br>`tests/test_link_members.py::TestAugment::test_unused_share_flows_to_later_clusters`<br>`tests/test_link_members.py::TestAugment::test_budget_refused_mid_cluster_is_skipped_budget_and_counted`<br>`tests/test_moc_discovery_links.py::test_small_budget_samples_the_first_cluster_and_reports_it`<br>`tests/test_moc_discovery_links.py::test_retries_spending_the_budget_skip_the_cluster_and_the_rest`<br>`tests/test_moc_discovery_links.py::test_fair_share_looks_up_every_rendered_cluster_under_120`<br>`tests/test_042_prose.py::test_discovery_template_carries_sampled_suffix_before_skipped`<br>`tests/test_042_prose.py::test_discovery_fill_rule_shows_sampled_suffix_only_when_clusters_sampled`<br>`tests/test_042_prose.py::test_discovery_fill_rule_shows_budget_suffix_only_when_clusters_skipped`<br>`tests/test_042_prose.py::test_step3c_stops_only_on_exit_2_and_parses_stdout_on_exit_1`<br>`tests/integration/test_moc_propose_e2e.py::test_042_budget_zero_still_writes_the_doc_and_reports_skipped` | — |
| F5-AC2 ≤ 120 attempts per run (retries and seed included), ≥ 0.3 s pacing, no rate-limit abort | det; live | `tests/test_link_members.py::TestAugment::test_budget_constant_is_120`<br>`tests/test_link_members.py::TestLookup::test_gate_refuses_send_past_budget`<br>`tests/test_link_members.py::TestLookup::test_installs_gate_and_pacing_and_counts_attempts`<br>`tests/test_kado_client_attempts.py::test_gate_false_before_first_send_sends_nothing`<br>`tests/test_kado_client_attempts.py::test_min_interval_sleeps_the_difference_between_sends`<br>`tests/test_moc_discovery_links.py::test_retries_spending_the_budget_skip_the_cluster_and_the_rest`<br>`tests/test_moc_discovery_around.py::test_seed_lookup_failure_is_reported_not_as_too_few` | M3 |
| F5-AC3 429 with `Retry-After` → wait, retry, each attempt counted, stop when the budget is spent | det | `tests/test_kado_client_retry.py::test_retry_after_header_honored`<br>`tests/test_kado_client_attempts.py::test_retries_count_as_attempts_but_one_call`<br>`tests/test_kado_client_attempts.py::test_gate_false_before_retry_stops_further_sends`<br>`tests/test_link_members.py::TestLookupCounting::test_lookup_refused_on_retry_after_one_send_still_counts` | M8 |
| F5-AC4 failed lookup → that cluster `failed`, no link members, counted, nothing else changes | det + prose | `tests/test_link_members.py::TestAugment::test_failed_lookup_fails_only_its_cluster`<br>`tests/test_link_members.py::TestAugment::test_kado_error_lookup_is_failed_not_skipped_budget`<br>`tests/test_moc_discovery_links.py::test_failed_lookup_marks_only_that_cluster`<br>`tests/test_moc_discovery_links.py::test_null_kado_client_fails_every_rendered_cluster_exit_unchanged`<br>`tests/test_042_prose.py::test_discovery_fill_rule_names_failed_lookups`<br>`tests/test_042_close_out_gaps.py::test_a_failed_lookup_changes_nothing_but_its_link_fields` (gap G3) | G3 |
| F5-AC5 seed lookup fails → no proposal, failure reported, not "fewer than 3" | det | `tests/test_moc_discovery_around.py::test_seed_lookup_failure_is_reported_not_as_too_few`<br>`tests/test_moc_discovery_around.py::test_moc_lookup_failure_is_seed_lookup_failed` | — |
| F6-AC1 periodic, MOC, attachment, inbox, non-atomic never a link member | det; live | `tests/test_link_members.py::TestEligibility::test_non_md_path`<br>`tests/test_link_members.py::TestEligibility::test_outside_atomic_note_paths`<br>`tests/test_link_members.py::TestEligibility::test_sibling_prefix_is_not_in_scope`<br>`tests/test_link_members.py::TestEligibility::test_inbox_path`<br>`tests/test_link_members.py::TestEligibility::test_inbox_from_vault_config_overrides_profile`<br>`tests/test_link_members.py::TestEligibility::test_periodic_path`<br>`tests/test_link_members.py::TestEligibility::test_vault_config_calendar_base_path`<br>`tests/test_link_members.py::TestEligibility::test_real_profile_and_trailing_space_daily`<br>`tests/test_link_members.py::TestEligibility::test_moc_by_cache_kind`<br>`tests/test_link_members.py::TestEligibility::test_moc_by_map_notes`<br>`tests/test_link_members.py::TestEligibility::test_moc_by_name_suffix`<br>`tests/test_link_members.py::TestAugment::test_traced_example`<br>`tests/test_moc_discovery_around.py::test_parent_moc_among_neighbours_is_never_a_member` | M2b |
| F6-AC2 `exclude/note` never a link member | det | `tests/test_link_members.py::TestEligibility::test_exclude_note_tag`<br>`tests/test_link_members.py::TestEligibility::test_exclude_moc_tag_does_not_exclude_a_note` | — |
| F6-AC3 a periodic note is no bridge | det | `tests/test_link_members.py::TestAugment::test_periodic_hub_never_counts`<br>`tests/test_link_members.py::TestAugment::test_moc_hub_never_counts`<br>`tests/test_moc_discovery_links.py::test_phase1_input_members_rechecked_by_eligibility` | M2, M2b |
| F6-AC4 out-of-scope note never proposed or named | det | `tests/test_link_members.py::TestEligibility::test_uncached_path`<br>`tests/test_link_members.py::TestEligibility::test_module_never_prints_or_logs`<br>`tests/test_link_members.py::TestAugment::test_uncached_neighbours_are_counted_not_added`<br>`tests/test_link_members.py::TestAugment::test_never_prints`<br>`tests/test_042_close_out_gaps.py::test_ineligible_and_uncached_neighbours_are_never_named` (gap G2) | G2 |
| F7-AC1 report states link members proposed and lookups made | prose + det; live | `tests/test_042_prose.py::test_strict_block_still_has_six_fields`<br>`tests/test_042_prose.py::test_discovery_template_carries_link_counts`<br>`tests/test_042_prose.py::test_discovery_fill_rule_reads_members_and_lookups_from_link_stats`<br>`tests/test_042_prose.py::test_success_example_shows_link_counts`<br>`tests/test_moc_discovery_links.py::test_link_stats_count_lookups_attempts_members_and_uncached`<br>`tests/test_moc_discovery_around.py::test_stderr_link_stats_equal_the_reports` | — |
| F7-AC2 no link members → states 0 | prose | `tests/test_042_prose.py::test_discovery_fill_rule_keeps_zero_member_form_when_k_is_zero`<br>`tests/test_042_prose.py::test_abort_example_shows_zero_link_counts`<br>`tests/test_042_prose.py::test_step3a_abort_reports_zero_link_counts` | — |

**F6-AC4 is traced through a contract, not one test.** Kado omits nodes outside
the key's scope from `kado-graph` (verified live 2026-10-27, README Context), so
Tomo never receives such a name. What Tomo owns is the other half: a node it
does receive but may not propose (ineligible, or not in the cache) is never
written to stderr, the report or the doc. That half is G2.

**F2-AC4 and F7 are prose contracts.** The tests pin the sentences
`moc-architect` and `moc-propose` route and report by. They prove the
instruction is there, not that the model follows it. The live runs show the
`Discovery:` line filled correctly in all four runs (§5). F2-AC4 was then run
live once (2026-10-29, owner request): `/moc-propose Around:Mapping Method`
routed to free text and wrote no around doc:

```
Mode: free-text | Trigger: Around:Mapping Method
Discovery: zero-candidates; links: 0 members, 0 lookups
Proposal-doc: no doc written (abort)
```

## 3. Criteria whose wording predates the shipped behaviour

| Criterion | PRD text | Shipped | Owner decision |
|---|---|---|---|
| F4-AC2 | "shows both the link reason and the existing-`up::` note shown today" | Both are shown, link reason after the annotation. The annotation itself is no longer "today's": `not-a-moc` reads `(existing up:: [[X]] → becomes \`related::\`)` and `unresolved` reads `(existing up:: [[X]] — note not found → becomes \`related::\`)`; the old "existing up:: broken — ignored" is gone. | Decisions Log 2026-10-29, **T5.3d** |
| F1-AC5, F3-AC3 | "the same `up::` / `related::` / Override handling as topic members" / "under the same existing-`up::` and Override rules as a new MOC's children" | Still the same rules for both, which is what the criteria require. The rules themselves changed: Rule 4.3 (drop a dangling `up::`) is retired, so every existing target is kept as `related::` or kept as `up::` per Rule 4.2 / 4.5. | Decisions Log 2026-10-29, **T5.3d** |
| F5-AC1 | v1.4 text: fair share, `sampled`, both counted | Matches. Listed because the plan (`plan/README.md` ADR-4: "60 attempts … all-or-nothing per cluster") and the README Documents table (PRD v1.1, SDD v1.0) still describe the pre-v1.2 design. | Decisions Log 2026-10-29, **ADR-4 v1.2 / T5.3b** |
| F5-AC1 ("proposals are still written") | — | Live, this also depended on `moc-architect` treating Pass 2 exit 1 as a partial result; run 1a stopped there. | Decisions Log 2026-10-29, **T5.3a** |
| F7-AC1 | "the number of link members proposed … and the number of link lookups made" | Matches; the line also carries `(P sampled: budget)`, `(S skipped: budget)` and a failed-lookup count when non-zero. For `around:<MOC>` the members count was wrong in the first live run (the stderr line was printed before the extension overwrote the count) and fixed in `moc-discovery` 0.24.3 (`test_stderr_link_stats_equal_the_reports`). | live-validation.md, Run 3 |

T5.3c (the `> **How to use this proposal**` block) changes no criterion's
wording. It adds text to every doc the parsers read, so F4-AC4 also traces to
`test_readers_give_identical_results_with_and_without_the_block`.

## 4. RED proofs

Every proof ran in a mutation copy: `git archive HEAD` extracted into
`$TMPDIR/co042-<name>`, one edit applied, the named tests run from the copy
with the repo's `venv/bin/python`. The worktree was never mutated.

### Existing tests, doubted and confirmed

| ID | Criterion | Mutation | Result |
|---|---|---|---|
| M1 | F1-AC3 | `lib/link_members.py`: delete `if node in member_paths: continue` | `FAILED tests/test_link_members.py::TestAugment::test_existing_member_is_not_added` — `1 failed, 1 passed` |
| M2 | F6-AC3 | `moc-discovery.py`: candidate members no longer re-checked by `NodeEligibility` (`if cand.path not in paths:`) | `FAILED tests/test_moc_discovery_links.py::test_phase1_input_members_rechecked_by_eligibility` — `1 failed` |
| M2b | F6-AC1, F6-AC3 | `lib/link_members.py`: ineligible (not uncached) neighbours count as hits | `test_periodic_hub_never_counts`, `test_moc_hub_never_counts`, `test_traced_example` — `3 failed` |
| M3 | F5-AC2 | `LOOKUP_PACING_S = 0.0` | `FAILED …TestLookup::test_installs_gate_and_pacing_and_counts_attempts` — `1 failed` |
| M4 | F4-AC2 | reducer: link suffix before the `up::` annotation | `test_existing_up_annotation_precedes_link_suffix`, `test_link_member_labels_carry_the_reason` — `2 failed` |
| M5 | F1-AC1, F1-AC4 | reducer: link member lines rendered `- [x]` | `test_link_members_render_after_topic_members`, `test_042_tag_run_ticked_link_member_reaches_the_instructions` — `2 failed` |
| M6 | F2-AC4 | `moc-architect.md`: "Prefixes match case-insensitively." | `FAILED tests/test_042_prose.py::test_agent_routes_capitalised_around_to_free_text` — `1 failed` |
| M8 | F5-AC3 | `kado_client._retry_delay` ignores a numeric `Retry-After` | `FAILED tests/test_kado_client_retry.py::test_retry_after_header_honored` — `1 failed` |
| M9 | F3-AC4 | `render_actions`: `link_to_moc` for every member, already linked or not | `test_member_already_linked_by_the_moc_gets_up_but_no_line`, `test_042_around_moc_extension_reaches_the_instructions` — `2 failed` |

**One docstring overclaims.** `test_top_cluster_gets_note_linked_with_two_members`
says it covers F1-AC3 ("beta … is not duplicated") and stayed **green** under M1:
in its fixture every topic member is linked by only one other member, so none
reaches 2 hits. F1-AC3 rests on `test_existing_member_is_not_added`, which went
red; the discovery test is not cited for F1-AC3.

### Gaps the trace found

Three criteria had no test that could fail. For each, the mutation was applied
in a copy and the **full suite** was run there. Its failures were the same four
as in an unmutated copy (`test_install_smoke_ide_bridge_block_exists`,
`test_no_ref_resolves_the_canonical_url_to_the_producer_copy`, two
`test_garden_audit_render.py` byte-identity tests), all environmental in a
copy without `.git` and gitignored files. Four modules (`test_031_t6_2…`,
`test_032_t6_2…`, `test_032_t6_3…`, `test_garden_audit_render_con3…`) could not
be collected in any copy because they call `git` at import. None is a 042 test.

```
unmutated copy: 4 failed, 5777 passed, 6 skipped, 2 warnings, 4 errors in 235.11s (0:03:55)
G1 mutated:     4 failed, 5778 passed, 5 skipped, 2 warnings, 4 errors in 235.14s (0:03:55)
G2 mutated:     4 failed, 5777 passed, 6 skipped, 2 warnings, 4 errors in 235.18s (0:03:55)
G3 mutated:     4 failed, 5776 passed, 7 skipped, 2 warnings, 4 errors in 235.29s (0:03:55)
```

Each gap was closed by a test in `tests/test_042_close_out_gaps.py`, committed
as `91f7fad6`, and proven RED in a fresh copy under the same mutation:

| Gap | Criterion | Mutation | New test → RED output |
|---|---|---|---|
| G1 | F4-AC4 | `suggestion-parser.py`: the link-member check keys on a bare `" — "` instead of `LINK_MEMBER_MARKER` (both readers). The T5.3d label `— note not found` carries that dash, so a labelled **topic** member drops out of the squelch signature input and the split lists. | `test_t53d_labels_do_not_change_which_note_a_line_is` → `test_042_close_out_gaps.py:85: AssertionError: assert [('MOC01', 'E..., ['energy'])] == [('MOC01', 'E..., ['energy'])]` |
| G2 | F6-AC4 | `lib/link_members.py`: print each uncached neighbour's path to stderr | `test_ineligible_and_uncached_neighbours_are_never_named` → `test_042_close_out_gaps.py:116: AssertionError: Atlas/202 Notes/uncached.md` |
| G3 | F5-AC4 | `moc-discovery.py`: a `failed` cluster's confidence set to 0.0 | `test_a_failed_lookup_changes_nothing_but_its_link_fields` → `test_042_close_out_gaps.py:152: AssertionError: assert [{'candidate_... None}], ...}] == [{'candidate_... None}], ...}]` |

Unmutated, the three tests pass (`3 passed`). Before G3, F5-AC4's "no other
part of the proposal changes" rested on the cluster count and the exit code;
before G1, every parse test fed only link lines and pre-T5.3d labels.

## 5. Live evidence and the KPIs

From [`live-validation.md`](live-validation.md) (2026-10-29, `tomo-instance`,
test vault). Lines quoted byte for byte from there.

Default scan after T5.3a/T5.3b (run 1b):

```
Discovery: OK — 214 candidates → 45 clusters; links: 20 members, 102 lookups (3 sampled: budget)
```

`around:Mapping Method` (run 2) and `around:Idea Emergence (MOC)` after the
stderr fix (run 3):

```
Discovery: OK — 1 candidates → 1 clusters; links: 17 members, 1 lookups
Discovery: OK — 0 candidates → 1 clusters; links: 7 members, 1 lookups
```

| KPI (PRD Success Metrics) | Target | Result | Verdict |
|---|---|---|---|
| Adoption: default-scan proposals with a link member | ≥ 3 | 4 of 5 rendered (run 1b) | 🟢 |
| Adoption: `around:` on a real hub note and a real MOC | 1 each | `Mapping Method` (17 members), `Idea Emergence (MOC)` (7 missing members) | 🟢 |
| Engagement: owner ticks ≥ half of the link members shown | ≥ 50 % | 5 of 14 in "Definition (MOC)" (36 %) | 🔴 missed |
| Quality: link-lookup budget | ≤ 120 attempts | 102 (scan), 1 (each `around:`) | 🟢 |
| Quality: Kado rate-limit aborts | 0 | 0; about 18 HTTP 429 on Phase 6.5 `kado-read`, all retried, `lookups failed: 0` | 🟢 |
| Quality: periodic notes, MOCs, attachments, out-of-scope notes proposed | 0 | 0; all 20 scan link members pass `NodeEligibility`, all under `Atlas/202 Notes/` | 🟢 |
| Business impact: every ticked member reaches the instructions | all | 44 / 44 ticked → `add_relationship`; 0 of 15 unticked; `create_moc 1 1 [OK]`, `TOTAL 1 1 [OK]` | 🟢 |

**Engagement missed.** `live-validation.md` records the tick ratio with a ✅
because T5.3 asked only that it be recorded. Against the PRD target it is a
miss: 36 % on one doc and one cluster (14 link members). This is one review,
not a precision measurement. Owner decision pending: accept as recorded or
track as a follow-up.

**Live gaps, recorded rather than hidden.**
- The 429s in run 1b fell on Phase 6.5 reads, outside the graph budget. The
  `Retry-After` path of F5-AC3 for a **graph** lookup was not exercised live;
  it rests on the unit tests (M8 and the attempt-count tests). `Retry-After` is
  honoured up to `_RETRY_AFTER_CAP` (60 s), at most 4 retries.
- All ticked members in the owner's apply had no prior `up::`, so the
  `related::` path of F1-AC5 / F3-AC3 ran in the e2e and render tests only.
- The four live docs predate the T5.3c how-to block and the T5.3d labels. The
  T5.3d labels were checked live by a host render of `around:Mapping Method`
  (two lines quoted in `live-validation.md`).

## 6. Validation

- **Full suite** (`./venv/bin/python -m pytest -q`, on `91f7fad6`):

  ```
  1 failed, 5803 passed, 4 skipped, 1 warning in 194.80s (0:03:14)
  ```

  The one failure is `tests/ide_bridge/test_configure_ide_bridge.py::test_install_smoke_ide_bridge_block_exists`,
  the known failure unrelated to 042. The warning is the existing `return` in a
  test that pytest flags ("Did you mean to use `assert` instead of `return`?").
  The skips are environmental.
- **ruff** (`./venv/bin/ruff check .`): `All checks passed!`

## 7. Open items

The backlog candidates in [`live-validation.md`](live-validation.md)
"Observations outside spec 042" stand as written there; none blocks this spec:

- topic-cluster titles such as "(Quote) (MOC)" and "§ (MOC)";
- the agent skipping Step 2 on repeated runs and using `date +%s` for the run id;
- the agent attributing Phase 6.5 429s to link lookups;
- the `around:` Discovery line's "1 candidates → 1 clusters" / "0 candidates → 1 clusters";
- sampled members follow Kado's listing order, not guaranteed across fresh scans;
- code-review suggestions not taken (stderr tests for the seed-lookup and
  fewer-than-3 aborts, a WHY sentence on resolve aborts, the pinned mid-cluster
  budget stop discarding a sampled cluster's partial hits);
- the `not-a-moc` / `unresolved` classification mirrored in `moc-discovery.py`
  Phase 6.5 and `moc-tree-builder._resolve_up_state` with no parity test.

Added by this close-out:

- **Engagement KPI missed** (§5): owner decision.
- **Stale plan metadata.** `plan/README.md` still lists ADR-4 as "60 attempts …
  all-or-nothing" and the README Documents table PRD v1.1 / SDD v1.0.
- **`test_top_cluster_gets_note_linked_with_two_members` docstring** claims
  F1-AC3 coverage its fixture cannot give (§4).

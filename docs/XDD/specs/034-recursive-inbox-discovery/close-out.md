# Spec 034 — close-out record (T6.5)

Written 2026-09-09, after T6.4's live validation passed end to end (six Pass-1/Pass-2 runs on
2026-09-08, one A/B re-validation and one Hashi apply on 2026-09-09). Recorded here rather than
in the plan because it walks two tables the plan only points at.

## Quality Requirements (SDD)

| Quality | Target | Measured |
|---|---|---|
| Correctness | A note at any depth is triaged | ✅ Live: `Reise/Tschechien/Prager Burg.md` (two levels) 2026-09-08 16:08; three subfolder notes filed end-to-end in the 2026-09-09 apply. Offline: `t3_2::test_deeply_nested_notes_are_discovered_no_depth_limit` |
| No silent loss | Zero overwritten per-item results, zero masked state entries | ✅ `t2_3::test_two_items_sharing_a_filename_read_their_own_result_file`, `t2_4::test_replay_does_not_let_one_items_status_hide_the_other`. Live: the 18:12 clash run |
| No wrong vault write | Zero captured marks on a non-approved note | ✅ `t2_5::test_collision_marks_the_approved_note_and_leaves_the_namesake_untouched`. Live: after the 2026-09-09 apply, `Fotos/Kai.md` still `captured` from its own run, untouched by the withheld move |
| Cost | Base Kado calls ≤ 2 per Pass 1, down from 3 | ✅ **`base_kado_calls: 2` on seven consecutive runs**, observed not derived (`state/inbox-cost-history.jsonl`) |
| Per-item cost | ≤ $0.65 subagent, ≤ $0.70 total against the 21-item baseline | ⚠️ **Not measured.** See below |
| Flat-inbox regression | Byte-identical suggestions document | ✅ `t3_4::TestFlatInboxGolden::test_rendered_document_matches_the_pre_phase_1_render` |
| Suite | Green, `ruff` clean | ✅ **3774 passed, 1 skipped, 0 failed** (3775 collected, 442s), `ruff` clean across `tomo/ tests/ scripts/` |

The one skip is the model-gated voice transcriber (`tests/voice/test_transcriber.py`) — the
suite's one standing skip, unrelated to this spec. It runs or skips depending on whether the
model is present locally, which is why the passed/skipped split moves by one between runs while
the collected total stays at 3775.

### The one row without a measurement

**Per-item cost was not measured for this spec.** `measure-f47-token-cost.py --session-latest`
keys on a `lifecycle.discovery` marker; the runs that exercised this spec's paths do not all
carry it, and no 21-item run was made under the tool. Two of the six live runs came close (19
and 14 items) but neither was measured.

This is a gap, stated rather than papered over. It does not block the spec: the cost claim this
spec actually makes is the **base Kado call count** (F9/ADR-3, 3 → 2), which is measured seven
times over. The per-item dollar figure is a standing budget inherited from F-47, not a claim
034 introduced. Carried to `docs/XDD/backlog.md`.

## PRD Acceptance Criteria — all 40

Numbered in document order. "Live" means observed in the vault during T6.4; every other row
names a test that is green in the run above.

### F1 — Notes in inbox subfolders are discovered (1–5)

| # | Criterion | Evidence |
|---|---|---|
| 1 | Subfolder note appears as a source item | `t3_2::test_subfolder_note_becomes_an_item` · Live 16:08 |
| 2 | Root and subfolder notes treated alike | `t6_2::TestBoundary1Discovery::test_a_root_level_note_and_a_two_level_note_are_both_discovered` |
| 3 | Two levels deep, no depth limit | `t3_2::test_deeply_nested_notes_are_discovered_no_depth_limit`, `::test_no_depth_argument_is_sent_on_the_listing` |
| 4 | Flat inbox unchanged | `t3_4::TestFlatInboxGolden::test_rendered_document_matches_the_pre_phase_1_render` + `::test_the_golden_is_not_trivially_empty` |
| 5 | Subfolder non-note not partitioned as a source | `t3_2::test_subfolder_png_is_classified_exactly_as_a_root_png`, `::test_folder_entries_are_never_items` |

### F2 — Same-named notes stay independent (6–10)

| # | Criterion | Evidence |
|---|---|---|
| 6 | Two distinct suggestions, one per note | `t3_4::TestSameNamePairSurvivesPass1::test_both_reach_the_suggestions_document_as_distinct_sections` · Live 17:08 |
| 7 | Neither per-item result overwrites the other | `t2_3::test_two_items_sharing_a_filename_read_their_own_result_file`, `t3_4::test_each_namesake_owns_a_distinct_result_file` |
| 8 | Only the approved one is acted on and marked | `t2_5::test_collision_marks_the_approved_note_and_leaves_the_namesake_untouched` |
| 9 | Run state records a distinct outcome per note | `t2_4::test_two_same_stem_items_record_independent_entries_and_transitions`, `::test_replay_does_not_let_one_items_status_hide_the_other` |
| 10 | Coverage audit accounts for two items, not one | `t2_3b::test_adversarial_duplicate_render_is_reported_not_a_false_pass`, `t2_7` |

### F3 — Titles and source links (11–17)

| # | Criterion | Evidence |
|---|---|---|
| 11 | Suggested name reads `Dresden`, not a path | `t2_3::test_no_rendered_title_or_link_carries_a_path_derived_key` |
| 12 | Source link is `[[Dresden]]`, never path-derived | `t5_1::TestUniqueFilenameStaysBare::test_the_source_link_is_the_plain_filename`, `::test_no_source_link_carries_a_path_or_an_alias` |
| 13 | Applied note titled from filename/frontmatter | `t2_3b::test_emitted_stems_stay_bare_filenames` · Live: `Alberthafen Dresden — Umschlagplatz vs. Anleger.md` |
| 14 | Colliding filenames carry enough location | `t5_1::TestCollidingFilenamesAreDistinguishable::test_the_two_links_resolve_to_different_notes` · Live 17:08 |
| 15 | A unique filename stays bare | `t5_1::test_the_unique_note_in_the_same_run_stays_bare` |
| 16 | Path-qualified embeds resolve per note | `t5_4::test_a_namesake_at_the_inbox_root_keeps_its_move` |
| 17 | Bare-name embed with two candidates is ambiguous | `t5_5_ambiguous_wikilinks` (whole module) |

### F3b — The captured mark (18–19)

| # | Criterion | Evidence |
|---|---|---|
| 18 | Frontmatter written to the approved note only | `t2_5::test_collision_with_both_done_marks_each_note_at_its_own_path`, `::test_collision_where_the_namesake_belongs_to_another_run_writes_nothing_wrong` |
| 19 | Declines to write rather than guessing | `t2_5::test_entry_without_item_key_is_never_written`, `::test_entry_without_path_is_declined_and_reported` |

### F4 — Force Atomic in a subfolder (20–21)

| # | Criterion | Evidence |
|---|---|---|
| 20 | Atomic proposal built from the subfolder note | `t4_1::TestSubfolderNoteCarriesRealPath::test_extract_fan_items_resolves_subfolder_note`, `t2_6::test_165_suppressed_force_atomic_resolves_for_a_subfolder_source` |
| 21 | Applied note reflects that note, not another | `t6_4a::TestTheKeyReachesTheInstructionSet::test_the_move_origin_is_the_subfolder_path_not_the_inbox_root` · **Live 19:27 — this is the defect T6.4a fixed** |

### F5 — Audio pairs by note (22–23)

| # | Criterion | Evidence |
|---|---|---|
| 22 | Unrelated namesake does not satisfy the pairing | `t3_3::test_root_audio_not_satisfied_by_namesake_in_archive`, `::test_voice_audio_not_satisfied_by_archive_namesake` |
| 23 | Same-folder pair is recognised | `t3_3::test_same_folder_pairing_is_recognised`, `::test_sanitized_stem_pairing_in_same_folder` |

Live coverage gap, deliberate: no audio fixture was placed in the vault — see T6.4's note on the
model-gated transcription pipeline.

### F6 — Every run records its cost (24–27)

| # | Criterion | Evidence |
|---|---|---|
| 24 | Item and Kado call counts in the run output | `t6_1` · Live: seven rows |
| 25 | Appended to durable state inside the instance | `t6_1::TestHistoryFile` |
| 26 | One entry per run, never overwritten | `t6_1::TestHistoryFile::test_several_runs_accumulate_and_none_is_overwritten` |
| 27 | Survives the working directory being cleared | `t6_1` (path is `state/`, not `tomo-tmp/`) · Live: rows span 2026-09-08 and 2026-09-09 |

### F7 — No two notes claim one destination (28–33)

| # | Criterion | Evidence |
|---|---|---|
| 28 | Pass 1 proposes a distinct name | `t5_2::test_second_claimant_on_one_destination_gets_a_distinct_name` |
| 29 | The user's edit wins | `t5_3::test_the_users_edit_to_a_pass1_adjusted_name_is_used_verbatim`, `t5_2::test_the_adjusted_name_is_an_ordinary_editable_field` |
| 30 | A vault-occupied destination is surfaced | `t5_2::test_a_destination_occupied_in_the_vault_is_renamed`, `::test_the_vault_clash_surfaces_the_occupied_path` |
| 31 | Pass 2 emits **neither** and reports it | `t5_3::test_two_items_claiming_one_destination_lose_both_moves`, `::test_the_clash_report_names_both_claimants_by_their_source_notes` · **Live 18:12** |
| 32 | A vault collision is not emitted either | `t5_3::test_a_destination_occupied_in_the_vault_is_not_emitted` |
| 33 | Correcting one name and re-running emits both | `t5_3::test_the_guard_carries_nothing_between_invocations` · **Live: the 2026-09-09 A/B re-run** |

### F8 — A note stays with its attachment (34–37)

| # | Criterion | Evidence |
|---|---|---|
| 34 | The second file is refused | `t5_4::test_the_unfiled_attachments_note_does_not_move` · **Live 19:27 and 2026-09-09** |
| 35 | The first note and its attachment file normally | `t5_4::test_the_first_note_and_its_attachment_are_filed_normally` · Live: `Hafen` filed, `Images/karte.png` moved |
| 36 | One file embedded twice is filed once, both notes move | `t5_4::test_build_actions_still_emits_the_recorded_duplicate_reference_baseline`, `::test_the_suppression_pass_is_a_no_op_on_a_duplicate_reference` |
| 37 | Renaming one file files everything on the re-run | `t5_4::test_renaming_one_file_files_everything_on_the_next_invocation`, `::test_the_clean_invocation_does_not_prime_the_next_one` |

### F9 / F10 — Listing cost and filter agreement (38–40)

| # | Criterion | Evidence |
|---|---|---|
| 38 | No more inbox listings than before | `t3_4::TestObservedCallCount::test_exactly_one_inbox_listing_per_run`, `::test_the_count_does_not_grow_with_subfolders` |
| 39 | Base call count ≤ 3, and the actual figure recorded | `t3_4::test_base_calls_are_two`, `t3_2::test_base_calls_are_two` · **Live: 2 on seven runs** |
| 40 | The two file-type checks agree on case-differing types | `t3_1::test_discover_files_and_build_inbox_index_agree` |

**40/40 map to something green.** Machine-checked at the feature level by
`test_034_feature_coverage_map.py`, which runs each referenced node rather than collecting it —
its stated residual limit is that it proves a test passes, not that the test still asserts the
claim it is named for.

## Defects found live that the offline suite did not

Three, all fixed on the branch:

1. **T6.4a** — the fan document was never joined to its own identity map; a subfolder note taken
   through Force Atomic reached the renderer with `item_key: null`.
2. **T6.4b** — `source_note_title` carried a sanitised filename where a display title belonged,
   so a note with a colon in its title failed its own link-coverage audit.
3. **T6.4c** — a move withheld by either guard left its staging note in the inbox with nothing
   left to move it. The plan's two proposed directions both rested on a wrong premise: Pass 2
   does not write to the vault at all; a separate upload step does.

## Live-coverage gaps, recorded not hidden

- **The audio namesake.** Covered offline (F5, 22–23); placing one live would route a validation
  run for this spec through a model-gated transcription pipeline with a known infinite-loop mode.
- **Per-item token cost.** See the Quality Requirements note above.

## Out of scope, found during T6.4

`t_moc_tomo.md` opens with `<%await tp.file.include("[[x_frontmatter]]")-%>`, delegating its
opening `---` fence to a Templater include. `docs/template-syntax.md` (Rule 1) forbids exactly
this and names the consequence: Tomo prepends its own block and the template's keys become body
text. Confirmed in the vault on `Atlas/200 Maps/Engineering (MOC).md`. **Not a 034 regression** —
`doc_frontmatter.py` is untouched on this branch, and templates are vault-installed. The remedy
is the user's: inline the frontmatter with a literal `---`, as `t_note_tomo.md` already does.

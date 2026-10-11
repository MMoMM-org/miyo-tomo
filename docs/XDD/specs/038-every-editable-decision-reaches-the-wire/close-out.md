---
title: "Close-out — 038 every editable decision reaches the wire"
status: complete
---

# Close-out

## Standing rule for this document

Every PRD criterion below traces to a test that was **executed**, named by node
id, not to a task that mentions it. The 95 node ids cited in the trace tables
were run **together in one `pytest` invocation on 2026-10-11** — `95 passed in
1.22s` — against `aec05c0`. The full suite on the same commit: **4527 passed, 4
skipped**.

**The skip count is network-dependent, and that is the open item rather than noise.**
Three full runs in one hour on 2026-10-11 returned 4 skips twice and 5 once — the extra
one being an upstream-schema fetch that succeeded on two runs and truncated on the
third (`IncompleteRead(8268 bytes read, 4306 more expected)`). The four standing skips
are all environmental: a gitignored `_outbox/` attachment, a fixture absent from this
checkout, the upstream fetch, and the voice model directory. None is a 038 test.

The rule is inherited from spec 037's close-out, where it caught **S2-AC1** being
claimed by a parser task that structurally could not render anything. In this
spec it caught one thing of its own: **F4-AC4 had no executed test behind it at
all.** The property was true by construction and nothing would have noticed a
refactor breaking it. That is recorded in §F4 below and was closed by `aec05c0`
rather than annotated away.

Test ids are given without the `tests/` prefix.

---

## The three traces spot-checked by execution

T5.5 step 4 asks for three criteria verified by running their node ids rather
than by trusting the table. Picked across three different features and three
different files, run on 2026-10-11, `3 passed in 0.10s`:

| Criterion | Node id | Why this one is worth the spot-check |
|---|---|---|
| F1-AC8 — the owning notes are **not** carried | `test_038_t2_2_attachment_conflicts_wire_projection.py::test_conflict_run_wire_carries_remedy_defaulted_as_the_markdown_pre_ticks` | The test's input dict carries `owner_source_items` and the asserted output does not. It is an **exact-equality** assertion on the whole list, so the absence is proven by the same line that proves the presence of everything else. A leak could not pass. |
| F3-AC4 — a usable name that collides run-locally | `test_038_t3_2_typed_name_refusal.py::test_usable_owner_supplied_name_that_collides_run_locally_is_collision_not_refused` | This is the criterion whose vault-side reading is **not decidable in Pass 2** (see §F3). The test pins the run-local reading and, by its name, pins that a collision is *not* reclassified as a refusal. |
| F4-AC6 — a retired row stays, with `editable: false` | `test_038_decision_inventory_join.py::test_injection_d_legitimate_retirement_passes` | Exercised on a **synthetic** row, because no real row is `editable: false` yet. The spot-check confirms the proof runs; §F4 records that it cannot yet run on real data. |

---

## Evidence that is not pinned by a test, recorded here because it cannot be

### F1-AC9 — the instructions wire is untouched

Measured 2026-10-11 on `aec05c0`:

```
git diff main...HEAD -- tomo/schemas/instructions.schema.json \
                        tomo/schemas/hashi-instructions.schema.json
→ 0 lines
```

**This confirms no edit was made. It is not proof of the design** — the files are
untouched by construction, so the check would pass whether or not the boundary
held. The same caveat spec 037's close-out recorded for its own schema check.

One other schema did change and is worth naming rather than leaving for a reader
to find: `tomo/schemas/routing-plan.schema.json` gained one enum member,
`wire_sibling_unreadable`. It is **not a published wire** —
`lib/wire_shape.PUBLISHED_WIRES` holds exactly three (`suggestions-wire`,
`instructions`, `garden-audit-wire`), and routing-plan's producer and all five of
its consumers are Tomo scripts. So it owes no handoff, and saying so here is
cheaper than letting a future reader of ADR-029's channel register wonder.

### S1 — both criteria are documentation, and no test can hold them

S1-AC1 and S1-AC2 trace to `docs/usage.md` and `docs/troubleshooting.md`, verified
by read-through against CON-6 (effect not mechanism) and CON-7 (never implying the
owning-note list is exhaustive). Re-verified on 2026-10-11 after `bf4f192` touched
the same files for an unrelated defect:

| Criterion | Where it lives | Verified |
|---|---|---|
| S1-AC1 — the precedence rule is stated plainly | `docs/usage.md:51,55` — *"that run in the editor, the editor's values are what Pass 2 uses"*, and the sibling-document caveat | present after `bf4f192` |
| S1-AC2 — the name is editable, and a refusal is described | `docs/usage.md:84-123` (the Rename bullet, the three refusal classes in owner terms, `taken` explicitly excluded, padding called out as *not* a refusal) + `docs/troubleshooting.md:261` (*"I Typed a Name Pass 2 Could Not Use"*) | present after `bf4f192` |

**S1-AC1 took two review FAILs to state correctly**, and the first draft is the
one worth recording: it said the editor wins *"for anything you changed there"*,
which promises a per-field merge. ADR-026's precedence is **whole-document** — the
digest can answer only *edited at all*, and there is no field provenance on the
wire to merge against. Spec compliance found it from the spec's own decisions log;
the orchestrator found it from the control flow, where `build_from_wire` runs and
`main` returns before the split-and-parse block that reads the markdown.

### T5.4's handoff — delivered and processed, not merely written

Recorded because the mechanism is easy to get wrong in the other direction:
`_outbox/for-hashi` is symlinked as Hashi's `_inbox/from-tomo`, so **writing the
handoff is delivering it.** There is no send step. Hashi set
`2026-10-11_tomo-to-hashi_wire-v3-ships-coordinated-your-five-asks-answered.md`
to `status: done` themselves and vendored our schema `cmp`-identical in their
PR #145. CON-8's discharge was confirmed from Kokoro's 2026-09-29 reply rather
than re-sent, and Kokoro **re-confirmed it unprompted** on 2026-10-11.

### The three live runs

Run A (F1), Run B (F2), Run C (F3) all **PASSED** on 2026-10-10, measured against
`tomo-instance` and never `tomo-privat`. Full per-check tables are in
`live-runbook.md:370-429` and are not duplicated here. The four results that no
test could have produced:

1. **Both provenance paths were observed live, with their different reasons.** Run
   A set `name_is_owner_supplied: true` *unconditionally*, from the wire path. Run
   B set the same `true` *by comparison*, because the typed name differed from the
   computed one. One flag, two mechanisms, each seen in the run that exercises it.
2. **The right file moved.** Run B's filed asset hashes `fa86a6e447ff`, the inbox
   original — **not** the occupier's `0fb588dae23c`. Two files shared one name;
   this is the check that separates *"a file arrived"* from *"the file arrived"*.
3. **Run C's evidence is a gap in the id sequence.** 4 actions, all `skip`, ids
   starting at **I03** — `I01` and `I02` were built and then suppressed. The
   absence is the proof that `suppress_moves_for_unfiled_attachments` and
   `withdraw_unjustified_deletes` both fired.
4. **T4.5 has the only verification it can ever get.** `tomo-tmp/withheld-attachments.md`
   came out byte-identical to a prediction produced by *executing* the renderer —
   twice, on two different notice kinds, with Run C's `run_id` sidecar proving the
   second was its own line and not Run A's. No pytest can capture
   `synthesis-conductor.md` Step 4, because a model produces it at runtime.

Run A also cost **one failed attempt**, kept because the wrong turns transfer: a
correctly edited wire that Pass 2 never looked at, because a Hashi save does *two*
things — writes the wire **and** ticks `- [x] Approved` — while the helper script
only did the first.

---

## PRD criteria — all 38, traced

Counts: `F1:9 F2:7 F3:9 F4:9 S1:2 C1:1 C2:1`. Of these, **35 trace to executed
tests**, 2 to documentation (S1, above), and 1 to a closure ruling plus T4.5's
tests (C1, below).

### F1 — The chosen remedy survives the JSON-only path

| Criterion | Executed test |
|---|---|
| AC1 — the wire carries the remedy for a conflict | `test_038_t2_2_attachment_conflicts_wire_projection.py::test_conflict_run_wire_carries_remedy_defaulted_as_the_markdown_pre_ticks` |
| AC2 — the default is the one the markdown pre-ticks | same test — it asserts **both** defaults in one exact-equality: `rename` when `proposed_name` is non-null, `keep_in_inbox` when it is null, mirroring `suggestions-reducer.py:1512-1524` |
| AC3 — one entry per attachment however many notes embed it | `test_037_t1_5_one_entry_one_file.py::test_one_attachment_three_owners_still_one_entry` — the property is established inside `detect_attachment_conflicts`, *before* this spec's projection runs, so 038 inherits it rather than re-proving it |
| AC4 — an edited wire rebuilds remedies identical to the markdown path | `test_037_remedy_lost_on_the_wire_path.py::test_the_wire_path_carries_the_chosen_remedy_too` + `::test_the_markdown_path_carries_the_chosen_remedy` + `test_038_t4_4_the_two_paths_converge.py::test_a_computed_name_converges_on_one_destination` |
| AC5 — a conflict-free run is unchanged apart from the version stamp | `test_038_t2_4_wire_baseline_diff.py::test_conflict_free_payload_differs_from_pre_038_baseline_in_exactly_two_ways` + `::test_digest_reconstructs_from_baseline_plus_only_the_two_intended_changes` + `::test_input_fixture_matches_the_captured_baseline_input` + `test_038_t2_2_…::test_conflict_free_run_wire_carries_empty_array_not_absent` |
| AC6 — the version is moved and a handoff is owed, because the nodes are closed | `test_035_wire_gate.py::test_affecting_change_with_version_unmoved_fails_and_demands_both_actions` (proves the gate demands **both** `move_version` and `handover`) + `::test_affecting_change_with_version_moved_and_manifest_regenerated_passes` + `test_038_suggestions_wire_schema_move.py::test_live_schema_and_manifest_agree_on_version_and_attachment_conflicts` |
| AC7 — the occupied destination and byte-identity are carried | `test_038_t2_2_…::test_conflict_run_wire_carries_remedy_defaulted_as_the_markdown_pre_ticks` — `destination` and `same_file` are in the asserted dict, including `same_file: None` on the second entry, which is the nullable-by-design case |
| AC8 — the owning notes are **not** carried | same test. The input carries `owner_source_items`; the asserted output does not. Belt and braces: the wire schema's `additionalProperties: false` on the `attachment_conflicts[].items` node means a leak would also fail this test's `jsonschema.validate` call |
| AC9 — the instructions wire is untouched | not a test — `git diff main...HEAD` is 0 lines on both instructions schemas. See the caveat above; and `test_wire_snapshot_parity.py::TestVendoredCopies::test_instructions_comparison_a_is_clean_apart_from_sanctioned` keeps the vendored copy honest independently |

### F2 — The rename target is owner-editable, on both surfaces

| Criterion | Executed test |
|---|---|
| AC1 — a typed name in the markdown is what Pass 2 proposes | `test_038_t4_2_parser_reads_the_typed_name.py::test_an_overtyped_name_with_the_folder_left_in_place_is_honoured` + `::test_an_overtyped_name_with_the_folder_deleted_too_is_the_same_name` |
| AC2 — an untouched computed name is byte-identical to today | `test_038_t4_2_…::test_the_untouched_default_is_byte_identical_to_the_computed_name` (the parse side) + `test_038_t4_1_markdown_offers_a_place_to_type.py::test_ordinary_conflict_renders_byte_identically_to_today` (the render side) |
| AC3 — a typed name in the editor survives the wire rebuild | `test_038_t3_2_typed_name_refusal.py::test_usable_typed_name_emits_the_move_when_owner_supplied` + `test_037_typed_rename_target_is_ignored.py::test_a_typed_rename_target_is_honoured` — the second is the test whose **name still records the pre-038 defect**, and it is now green; see §"What the names of two tests record" |
| AC4 — the same rules apply to both surfaces, not two implementations | `test_038_t4_3_refused_name_rewrites_no_embed.py::test_both_halves_accept_the_same_typed_name` + `::test_both_halves_refuse_the_same_typed_name` + `test_038_t4_4_the_two_paths_converge.py::test_a_typed_accepted_name_converges_on_one_destination` + `::test_an_unusable_computed_name_is_refused_on_the_wire_and_filed_in_the_markdown` |
| AC5 — a name supplied on the "no free name" line is read and used | `test_038_t4_2_…::test_the_no_free_name_line_honours_a_typed_name` + `test_038_t4_1_…::test_no_free_name_line_carries_empty_backticks` (the render side: the line has to offer somewhere to type before a parser can read it) |
| AC6 — that line with no name supplied is unchanged from today | `test_038_t4_2_…::test_the_no_free_name_line_left_alone_keeps_the_attachment_in_the_inbox` + `::test_the_no_free_name_line_ticked_but_still_empty_stays_ignore` |
| AC7 — an accepted typed name rewrites the embed in every owning note | `test_038_t4_3_…::test_accepted_typed_name_rewrites_every_embed_including_the_sized_one` — the test asserts **both** occurrences and that the `|300` size suffix survives — the sized form is the one an unanchored substitution mangles |

### F3 — An unusable typed name is refused and recorded, never substituted

| Criterion | Executed test |
|---|---|
| AC1 — a path separator is refused, not truncated | `test_038_t3_1_typed_name_check.py::test_relative_separator_is_refused` + `::test_absolute_path_separator_is_refused` + `::test_parent_traversal_separator_is_refused` + `test_038_t4_2_…::test_a_different_folder_typed_is_refused_separator_present` |
| AC2 — a forbidden character is refused, not substituted | `test_038_t3_1_…::test_each_forbidden_character_is_refused` (the **nine** non-separator members of `FORBIDDEN_CHARS`, which has ten; `/` is covered by AC1's separator tests) + `::test_nul_byte_is_refused` + `test_038_t4_2_…::test_a_forbidden_character_with_the_folder_left_is_refused` |
| AC3 — empty or whitespace-only is refused | `test_038_t3_1_…::test_empty_string_is_refused` + `::test_whitespace_only_is_refused` + `::test_whitespace_only_tabs_and_newlines_is_refused` + `test_038_t3_2_…::test_whitespace_only_proposed_name_reaches_the_rename_branch_and_is_refused` |
| AC4 — a name already taken at the destination is refused | `test_038_t3_2_…::test_usable_owner_supplied_name_that_collides_run_locally_is_collision_not_refused`. **Run-local only, and that is a measured boundary rather than a shortfall:** Pass 2 has no vault listing — `path_exists` appears nowhere in `render_actions.py` or `render_md.py`, and the wire carries only `destination`, `same_file`, `proposed_name` per ADR-3 — so the vault-side reading is not decidable in Pass 2 by any module. Pass 1 owns occupancy. The markdown's `Ignore` line already tells the owner as much |
| AC5 — no move is emitted and the attachment stays put | `test_038_t3_2_…::test_refused_source_produces_no_move_asset_anywhere_in_actions` + `test_038_t3_3_owning_note_held.py::test_typed_name_refused_skip_holds_its_owning_note` |
| AC6 — the document records it, naming the attachment | `test_038_t3_4_refusal_reported.py::test_separator_present_renders_the_exact_bullet` + `::test_forbidden_character_renders_the_exact_bullet` + `::test_blank_renders_the_exact_bullet` + `::test_two_owning_notes_still_render_a_singular_attachment_remedy`. Scope ruled by the owner 2026-10-02: *"refused name"* here is the three string classes, **not** AC4's run-local collision, which is reported by the pre-existing shared collision sentence |
| AC7 — the text states only what was verified | `test_038_t3_2_…::test_owner_facing_suppression_sentence_names_no_inbox_path_and_no_refusal_code` + `::test_skipped_entry_reason_is_prose_and_refusal_reason_is_the_bare_code` + `test_038_t3_1_…::test_reason_tokens_are_not_prose` — three tests, because the failure mode has two halves: leaking an internal into owner-facing prose, and leaking prose into a machine field |
| AC8 — the computed name is **not** used as a fallback | `test_038_t4_3_…::test_refused_blank_leaves_body_byte_identical` + `::test_refused_separator_present_leaves_body_byte_identical` + `::test_refused_forbidden_character_leaves_body_byte_identical`. Byte-identity is the right assertion here: a fallback would show up as a rewritten embed, and only "nothing changed at all" excludes every fallback |
| AC9 — a name Tomo computed is unchanged from today | `test_038_t3_2_…::test_unusable_computed_name_behaves_exactly_as_today_when_not_owner_supplied` + `::test_unusable_typed_name_behaves_exactly_as_today_when_flag_absent` + `test_038_t4_3_…::test_computed_name_still_rewrites_when_flag_is_absent` + `::test_computed_name_still_rewrites_when_flag_is_false`. Absent and `false` are tested separately on purpose — they are different states of `name_is_owner_supplied` and a `.get()` default could make one pass while the other fails |

### F4 — The inventory of editable decisions exists, as a file the consumer can vendor

| Criterion | Executed test |
|---|---|
| AC1 — one row per editable decision the markdown offers | `test_038_inventory_schema_validation.py::test_wire_schema_marks_exactly_25_editable_fields` (`== 25`, catches a **deleted** marker) + `test_038_decision_inventory_join.py::test_real_artefacts_schema_side_join_passes` + `::test_real_artefacts_parser_side_join_passes` + `::test_parser_harvest_meets_the_measured_floor`. The two-sided join is the mechanism: schema-side catches a marked field with no row, parser-side catches a recognised control with no row |
| AC2 — a decision with no wire field records the absence explicitly | `test_038_inventory_schema_validation.py::test_conforming_row_with_null_wire_field_validates` + `::test_row_rejects_missing_wire_field` — nullable, but **required**, so a row cannot omit the key. **And the mechanism is evidenced on real data, historically:** at `8964a76` (T1.1) the inventory had 24 rows and **D24's `wire_field` was `null`**, noted *"037 state: the remedy has no wire field yet. This is the row F4's acceptance criteria name explicitly."* Today D24 reads `attachment_conflicts[].remedy`, noted *"The remedy's wire field arrived, as this row once predicted it would."* The absence was recorded, then this spec closed it — which is the criterion working end to end, not a vacuous pass |
| AC3 — a stable opaque `id` | `::test_inventory_ids_are_unique` + `::test_row_rejects_id_wrong_pattern` + `::test_row_rejects_id_wrong_type` (pattern `^D[0-9]{2,}$`) |
| AC4 — a reworded label leaves the `id` unchanged | `test_038_decision_inventory_join.py::test_rewording_every_label_changes_no_row_id_and_breaks_no_join` — **added by this close-out**, see §"The one criterion the trace caught" |
| AC5 — a read-only decision does not appear | `::test_absence_rules_never_shadow_a_real_control_label` + `::test_injection_b_unmapped_harvested_literal_fails`. `ABSENCE_RULES` carries an explicit `"read-only field key"` rule, and the first test is the guard that an absence rule cannot swallow a *real* control label — without it, excusing fields would be a way to hide rows |
| AC6 — a retired control keeps its row, with `editable: false` | `::test_injection_d_legitimate_retirement_passes` + `::test_injection_c_stale_exemption_fails` + `test_038_inventory_schema_validation.py::test_conforming_retired_row_validates` + `::test_conforming_row_with_editable_false_and_no_parser_label_validates`. **Synthetic rows only** — see the open items |
| AC7 — the change is a diff to a file, not prose in a handoff | `test_038_inventory_schema_validation.py::test_inventory_file_exists` + the file is committed at `tomo/schemas/suggestions-decision-inventory.json` and was delivered as an attachment, not described. Hashi vendored it |
| AC8 — a malformed row fails Tomo's own tests | `::test_inventory_file_validates_against_schema` + the `row_rejects_*` family (19 tests, of which `::test_decisions_item_rejects_non_object`, `::test_row_rejects_additional_property`, `::test_row_rejects_missing_id`, `::test_row_rejects_missing_editable` are cited in the run) + `::test_a_deleted_editable_marker_is_caught` + `test_038_decision_inventory_join.py::test_injection_a_marked_schema_field_with_no_row_fails` |
| AC9 — the rows agree with the wire as this spec leaves it, remedy included | `::test_wire_schema_marks_exactly_25_editable_fields` + `test_038_decision_inventory_join.py::test_real_artefacts_schema_side_join_passes` + `test_038_inventory_schema_validation.py::test_wire_schema_editable_markers_use_uniform_dash_form`. The count moved 23 → 25 when T2.1 added two editable fields, and the join went red the moment it did — which is why T5.2 was pulled forward into Phase 2 as T2.1b |

### C1 — Pass 2's summary counts refused names

**The checkbox stays unticked, and that is the finding, not an omission.** Its
literal text — *"the count appears alongside the existing skip counts"* — did not
happen and will not: there are no existing skip counts for a new count to appear
alongside, and counting in that region is argued against **twice** in the file it
would have touched (`render_md.py:1031-1034` and `:871-874`, both ruling that
skipped items are *"named individually, never counted"* under CON-2). T3.4's own
undercount, found in review and fixed in `6c176ef`, is the concrete evidence those
rulings are right — a singular note-count contradicted the suppression block's
correct plural one in the same document.

What C1 **asked for** was delivered twice, by two different mechanisms:

- in the **document**, by F3's own bullet under *"Attachments still in the inbox
  — none of these were filed:"* (T3.4, `render_md.py:1115`);
- in the **shell**, by T4.5's line-per-item relay —
  `test_038_t4_5_withheld_attachment_relay.py::TestWithheldAttachmentsReachTheRelayFile::test_all_four_kinds_are_relayed_as_whole_lines`
  + `::test_relay_lines_are_the_documents_own_bullets`
  + `TestSharedCodePathUnderMutation::test_mutating_the_notice_function_moves_both_surfaces`
  + `TestAgentWiringGuard::test_conductor_cats_the_path_the_writer_writes`
  + `TestNothingWithheldRemovesAPreviousRunsFile::test_a_new_run_with_nothing_withheld_removes_both_files`
  + `test_038_t4_5_asset_notice_extraction.py::TestExtractionIsBehaviourPreserving::test_extraction_preserves_rendered_document_byte_identical`.

**The shell half exists because closing C1 the first time was wrong.** It was
closed 2026-10-02 against the *document* when its own words say *"run summary"* —
a conclusion drawn from reading the producing end (the script's stderr) and
inferring the consuming end without reading it. The owner re-raised exactly that
on 2026-10-03, and T4.5 is the result. **Read the box as "this mechanism was not
built" and this section as "the capability was delivered twice, and the second
time only because the first closure was audited."**

### C2 — An inventory row can carry a short note

| Criterion | Executed test |
|---|---|
| AC1 — the note is a single short string, optional on every other row | `test_038_inventory_schema_validation.py::test_conforming_row_with_note_validates` + `::test_row_rejects_note_empty_string` + `::test_row_rejects_note_wrong_type` + `::test_inventory_notes_carry_no_task_phase_feature_or_spec_identifier` |

Exercised on real data: three rows carry a note (**D22**, **D24**, **D25**), and
the fourth test is the guard that a note stays consumer-facing rather than
becoming a place to leak our own task numbers into a vendored file.

---

## The one criterion the trace caught

**F4-AC4 had no executed test.** *"Given a control's label is reworded, When the
inventory is regenerated, Then the row's `id` is unchanged."*

The property was true: the join keys on `parser_label`, never on
`markdown_control` prose (T1.1b), and `id` is opaque. The schema's own description
pins the contract. But **nothing executed would have noticed** a future refactor
deriving `id` from the label — the kind of refactor someone proposes as a
readability improvement.

The criterion also has an antecedent with no referent: ADR-7 chose a hand-written
registry, so there is no generator to *regenerate* the inventory. What it actually
wants is row identity independent of prose, and that is what the new test asserts
— reword every label, assert every id holds, assert both join directions still
pass.

**Proven RED by the mutation its docstring names** — a prose-derived id scheme —
failing at `'D31' != 'D01'`. Closed in `aec05c0`.

This is the second spec in a row where the close-out's trace rule found a real
gap rather than confirming the work. In 037 it was a criterion asserted by **no
test at all**; here it was a criterion asserted by **no test that could fail**.
Both were invisible to a green suite and to every per-task review.

---

## What the names of two tests record

Two test names are deliberately not updated, and a reader will otherwise think
they are stale:

- `test_037_typed_rename_target_is_ignored.py` — the file name states the pre-038
  defect. Both its tests are now green and prove the opposite of the name. It is
  the RED-first artefact for F2-AC3, kept under its original name so the history
  of the defect survives in the suite rather than only in a commit message.
- `test_037_remedy_lost_on_the_wire_path.py` — likewise for F1. The remedy is no
  longer lost; the file is named for what it caught.

Renaming them would make the suite read better and lose the only in-repo record
that these two paths once failed.

---

## Open — recorded rather than closed

### 1. The inventory is hand-written, and two of its columns have never been exercised on real data

ADR-7 chose a hand-written registry over a generator. The two-sided join defends
it from both directions, and the five injections prove the join bites. But two
columns are proven **only on synthetic rows**, because today's data has no
instance of either:

- **No row is `editable: false`.** F4-AC6's staleness guard and its legitimate-retirement
  counterpart run against fabricated rows appended to a copy of the real list. As
  the join test's own docstring puts it: *"the exemption cannot be proven honest
  until a real control is retired, and that is the point of writing the proof now
  rather than when the first one is."*
- **No row has `wire_field: null` any more.** D24 was the one, and this spec closed
  it. The capability is kept alive by `test_conforming_row_with_null_wire_field_validates`
  alone.

Both are fine. Both are worth knowing before someone reads a green F4 as "proven
in production".

Three further known limitations are documented in the join test's module docstring
and not repeated here: it catches a *missing* row but not a *wrong* one (backlog:
*"the inventory join could now catch a wrong `wire_field`"*); it catches a
literal-matched control but not a pattern-matched one; and four row labels cannot
be harvested by any AST filter over the shapes used and are simply unguarded from
the parser side.

### 2. A renamed attachment breaks the embed in any note filed by an earlier run

Backlog: *"a renamed attachment breaks the embed in any note that was filed
earlier"*. 038 rewrites embeds in every note **in this run** — CON-7 is why every
sentence about it is scoped that way. A note filed last week that embeds the same
attachment is not reached. Unchanged by this spec, and now reachable through one
more surface than before, because the name can be typed.

### 3. The two Pass-2 paths normalise `delete_source` differently

Pre-existing, measured, and still open: the markdown parser forces
`delete_source` to `False` on an approved item (`suggestion-parser.py:932` —
*"If Accept is checked, Delete is irrelevant"*); `build_from_wire` copies it
through unchanged. **Inert today** only because no consumer reads a confirmed
item's copy of the flag. The wire can hold a state the markdown cannot express,
and the invariant holds on one path only — the same shape as the defect this spec
exists to close, in a field this spec did not touch.

Adjacent and from the same measurement: `(skip, keep_source=true,
delete_source=true)` is contradictory and **the delete wins** — not by precedence,
but because `build_from_wire` never copies `keep_source` into a skipped entry, so
the builder cannot see it. A control offering both would let the owner tick "keep"
and lose the file.

### 4. What Phase 1's discrepancy list did not absorb

Phase 1 produced **20 findings, none from a failing test** — every one from
counting or executing something a document asserted. Seventeen were resolved
inside the phase; `phase-1-findings.md` disposes of the rest. Three left the spec
as standing backlog rather than being absorbed:

- **No honesty check on an absence rule's stated *reason*** (finding 19) — nothing
  notices if a field excused as read-only later becomes `Editable`. The dangerous
  end state is caught anyway by the schema-side count equality; closing the
  reason-level gap would mean reintroducing `wire_field` path-string matching,
  which this spec deliberately rejected.
- **The upstream-parity check skips silently, on the one wire 038 changes.**
  `_fetch_or_skip` turns a partial read into `pytest.skip`, and Hashi's live
  `suggestions-wire.schema.json` truncates at the **same byte offset on repeated
  attempts** (`IncompleteRead(8268 read, 4306 more expected)`). The hermetic
  offline comparison still pins the six-entry delta, so drift between our two
  local files is caught; drift between our snapshot and what Hashi actually
  publishes is **not**, and the suite is green either way. Hashi's reply says the
  truncation is client-side. **Do not read a green suite as evidence the vendored
  snapshot matches upstream.**
- **`suggestions-reducer.py` is 2514 LOC**, with the extraction seam spec 037 T1.1
  made visible still unextracted.

### 5. Three issues opened during Phase 5, all deliberately after 038

| Issue | What it is |
|---|---|
| **#185** | Two open refusal-class rulings for owner-typed names: whitespace padding is accepted verbatim, and four link-breaking characters (`# ^ [ ]`) pass `check_typed_name`. Measured: `extract_attachment_embeds` cannot match a `# ^ [ ]` embed in any of five ordinary forms, so the rewrite silently misses it |
| **#186** | ADR-029's open item: a `delete_source` justified only by its note move survives a failed `move_asset`. `_build_delete_source_actions` site 3 names `move_note` ids only, by construction. **Two live runs were exposed to this shape and both survived because the destination happened to be free** — a measured near-miss, not a theoretical path. Owed to Kokoro as a design-time handoff |
| **#187** | Nothing on our side implements ADR-029 §2's channel-naming rule, and nothing tracked that we owed it. The options are priced against what exists, which notably **excludes CI** — this repo has no `.github/workflows/` at all |

All three exist because an accepted obligation was **untracked**. Three instances
in one day; #187 records the pattern as well as its own case.

### 6. The fixture cannot clean an owner-typed asset name

Found during Run C's cleanup, and the near-miss is the valuable half.
`CREATED_GLOBS` carries `Atlas/290 Assets/295 Attachments/karte (*).png` — the
*computed* name pattern, which cannot match an owner-typed name. Run B's filed
asset survived the restore.

**The obvious fix is wrong, and a dry run is what caught it.** Broadening the glob
to the whole attachments folder would have deleted **67 real vault files**, the
fixture's own occupier among them: `preexisting.txt` is generated *from* the globs
at snapshot time, and the narrow glob matched nothing there, so that folder has
**zero** protected entries. Glob and baseline are coupled; broadening one without
re-taking the other removes the safety net instead of extending it. Backlogged
rather than fixed mid-validation.

### 7. One backlog entry this spec closed and left marked OPEN

*"a withheld attachment never reaches the shell, only the document"* was written
2026-10-03 and **closed by T4.5** — which built exactly the relay the entry
proposed, down to copying spec 036's line-per-item shape. The entry even named a
filename (`withheld-assets.md`); the built one is `withheld-attachments.md`.
Marked CLOSED as part of this close-out. Recorded here because the inverse of a
quietly-closed open item is an open item quietly left open, and this spec's whole
subject is records that disagree with behaviour.

---

## What this spec cost, and what is worth recording

**182 commits, 93 files, +15094 / -488, 2026-09-29 to 2026-10-11.** Three new
artefacts under `tomo/`: `lib/typed_name_check.py`,
`suggestions-decision-inventory.json` and its schema. **19 new test files.** Three
live runs plus one failed attempt. Five handoffs out in Phase 5 alone, all
delivered and processed.

Four things are worth more than the figures:

**The inventory was the point and the artefact was the side effect.** Phase 1 was
sequenced first specifically so what it found could reshape Phases 2–4 before they
were committed. It produced 20 findings and **not one came from a failing test** —
every one came from counting or executing something a document asserted. It also
*removed* a phantom Phase 2 obligation (finding 4: `classification` is parsed but
unreachable, so it owes no wire field). The most transferable sentence in this
spec is `phase-1-findings.md`'s own: *"a plan's claims about a codebase are
hypotheses, not facts, until something runs against the real artefact."*

**A task moved phases because the mechanism worked.** T5.2 was scheduled for
Phase 5, but T2.1 made the wire field exist and Phase 1's two-sided join went red
the moment it did — `25` marked against `23` backed. T5.2's own step 2 predicted
that failure and called it the mechanism working. Left in Phase 5 it would have
run red through two phases whose gates demand a green suite, so the owner pulled
it forward. It also had to widen: T2.1 added **two** editable fields, not one.

**Two defects were caught by the owner reading shipped output**, which is also how
037's four defective sentences were caught. Neither came from review and neither
could have. The read-through in T5.3 step 4 is not ceremony.

**The consumer found the defect this spec exists to close, and then kept finding
things.** ADR-029 came from Hashi reading our schema. ADR-018 §4's five-month
non-implementation came from Hashi reading a Kokoro ADR against their own
behaviour. The `kado-write`/ADR-009 contradiction inside that clause was reachable
from two accepted ADRs since 2026-05-27 and was found on 2026-10-11. Every
cross-component defect this week was found by a person cross-reading two
documents, and none by a gate — which is the argument #187 exists to settle.

---

## Where this spec's history lives

Recorded because this document cites four shas and **none of them is an ancestor of
`main`**. Spec 038 was squash-merged as `ce410fa` (PR #188), which is the repo's
practice — spec 037 was squashed the same way as `b2132d7` — and the branch was then
removed by delete-branch-on-merge.

So `git log main` will not find `8964a76`, `6c176ef`, `aec05c0` or `bf4f192`. They are
reachable from:

- **`history/spec-038`**, an annotated tag at `94fbf9b`, pushed 2026-10-11. Tags are
  untouched by delete-branch-on-merge and clone by default, which is why this is the
  ref to use. Spec 037's equivalent is `history/spec-037` at `39abd73`.
- **`refs/pull/188/head`**, GitHub's own retained PR head. Also `94fbf9b`, also
  surviving branch deletion — but not fetched by default, not named, and a GitHub
  convention rather than a git guarantee. The tag's own annotation overstates this by
  calling itself *"the only remote-reachable record"*; it is not, and this paragraph is
  the correction, because rewriting a pushed tag costs more than it is worth.

**Specs 035 and 036 need no such note.** 035 landed as a merge commit (`039b8e4`), 036
as individual commits on `main` — both histories are ancestors of `main` already.
Verified with `git merge-base --is-ancestor` rather than inferred from the commit
subjects.

One method note, since it cost a wrong claim in this session: `git branch -a` lists
**stale local tracking refs** and showed spec branches that the remote had already
deleted. `git ls-remote origin` is the only thing that answers what the remote holds.
Reading a local cache and concluding about a remote is the same error as reading a
producing end and concluding about a consuming end, which this spec caught three times.

---

## Closing condition

The invariant this spec restores is written in our own schema and was violated by
the spec before it: *"every editable decision the markdown offers is carried
here."* As 038 leaves it, the suggestions wire carries **25** editable fields, the
inventory carries **25** rows, the two-sided join holds in both directions with
five injections proving it bites, and the consumer holds our schema
`cmp`-identical.

And the invariant's wording itself got corrected in the process: Kokoro's ADR-029
§3 had extended it to *"an owner's edit made on either surface reaches the Pass-2
reader on every path"*, which ADR-026's whole-document precedence makes false.
**Kokoro accepted the push-back and reworded §3 to our text**, and recorded the
save-stales-digest loss path as known and deliberately unfixed rather than closed.
A spec that ends by fixing the sentence it set out to satisfy is the right kind of
ending.

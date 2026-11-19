---
title: "Phase 6: Wire v4, integration, live walk and close-out"
status: in_progress
version: "1.0"
phase: 6
---

# Phase 6: Wire v4, integration, live walk and close-out

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Deployment View/Multi-Component Coordination]` — order (1)–(7)
- `[ref: SDD/Technical Debt]` — the ~14 tests with `"schema_version": "3"`, `test_review_sdd_map.py`
- `[ref: SDD/Quality Requirements]`; `[ref: PRD/Success Metrics]`
- `[ref: SDD/Architecture Decisions; ADR-5]`
- Spec 045 `close-out.md` and `live-walk.md` (precedent)

**Key Decisions**:
- All instruction-schema changes happen here, together, after Hashi's release: producer schema, `schema_version` "4", the shape manifest, and the vendored copy (byte-identical, never edited) (ADR-5, owner 2026-11-14).
- The PR merges only after Tomo and Hashi work together in the test vault: week, month, quarter; first delivery and re-run (PRD Constraints).
- Paid evals and live runs only on the owner's instruction; sync with `--instance tomo-instance` only.

**Dependencies**: Phase 5. T6.1 waits for Hashi's reply to `_outbox/for-hashi/2026-11-14_tomo-to-hashi_replace-between-markers.md` and its release.

---

## Tasks

Ships the wire bump with Hashi, proves the whole flow end to end and in the test vault, and closes the spec.

- [x] **T6.1 Wire v4 after Hashi's release** `[activity: integration]`

  1. Prime: Hashi's reply in `_inbox/from-hashi/` and its released `src/schema/instructions.schema.json`; spec 039 `test_039_t3_1_wire_v4` precedent (live schema, version and manifest moved together; only the vendored copy lagged); `tomo/schemas/instructions.schema.json`, `tomo/schemas/shapes/instructions.shape.json`; the form-agnostic search `rg -n "schema_version.{0,8}['\"]3['\"]" tests tomo/scripts` (never truncated; each hit checked per wire — e.g. `tests/test_review_instructions.py:729`); `docs/instructions-json.md` `[ref: SDD/Cross-Component Boundaries; ADR-5]`
  2. Test: diff the released `replace_between_markers` `$def` against the handoff fragment — any difference becomes a fix task with a RED test before anything else; the vendored copy is byte-identical to Hashi's released file (sha256 recorded); the producer schema gains the action and `schema_version` "4" in the same commit as the manifest regeneration; `/inbox`, `/note` and `/review` producers emit "4" through `wire_schema_version`; every instructions-wire hit of the search moves to "4" (list recorded in this task); the 038 wire baselines regenerated; the T5.3 test-only schema and its helper switch removed, Phase 5 tests now validating against the committed schemas; a few vectors from Hashi's own `replaceBetweenMarkers` / `insertUnderMarker` tests re-run through Tomo's reference splice (T5.1); `test_tomo_schema_parity`, wire gate and manifests green; Hashi's answer on v3 sets reflected in the release notes text.
  3. Implement: producer schema, version, manifest, vendored copy, the listed tests, removal of the test-only schema; `docs/instructions-json.md` (version and the new action); WHY docs first; version bumps.
  4. Validate: the full suite GREEN with no named exception.
  5. Success: Tomo and Hashi share wire v4 `[ref: SDD/ADR-5; PRD/Constraints]`

  Note (2026-11-17, owner decision): vendored **pre-release** from Hashi `feat/179-replace-between-markers` commit `abd92d6` (PR #181), sha256 `51b80e494493c08ac2f03c90b4002e5ad1dd44d4dac1348b5bd22983bec23c91`, because Hashi releases only after the joint test-vault run, which needs Tomo's v4 sets. **Re-check byte-identity against the released tag before merge** (`tests/test_046_t6_1_wire_v4.py`, `tests/test_039_t6_2_vendored_v4.py` pin the hash). The released `$def` equals the handoff fragment (no fix task). Hashi's `schema_version` is `{"enum": ["3", "4"]}`; the producer keeps `{"const": "4"}`, the form `wire_schema_version` reads. Manifest regenerated with `scripts/wire-shape.py --regenerate` (`'3' -> '4'`). The 038 wire baseline (`tests/fixtures/038-wire-baseline/`) is the suggestions wire and did not move; the two instruction-wire baselines recorded from pre-039 trees (`039-t4-5-unaffected-runs`, `039-t6-3-untouched-baseline`) cannot absorb the bump by re-recording, so their replays pin the one version line as a sanctioned change. The snapshot-parity report names the one enum-vs-const delta (`removed_enum_value` "3") exactly. Hashi's v3 answer is in `tomo/CHANGELOG.md` and `docs/instructions-json.md`. Search hits moved "3" → "4" (instructions wire): `test_027_t4_1_schema_wire_rename.py:47,76`, `test-resolve-section-names.py:752,1118`, `test_037_t3_0_remedy_transport.py:301`, `test_031_t6_1_end_to_end.py:266`, `test-008-phase1.py:337`, `test_031_t2_6_phase2_validation.py:73` (+ const pin :108), `test_instruction_render_wire_hygiene.py:120,140,166,175`, `test_edit_note_text_action.py:47`, `test_instructions_diff_skipped_daily.py:145`, `test_037_t4_1_no_consumer_change.py:100`, `test_tag_handler_e2e.py:251`, `test_034_t6_4b_display_title_not_filename.py:277`, `test_spec022_schema_additions.py:110`, `test_tag_handler_group_instruction_linkage.py:118`, `test_review_instructions.py:725`, `test_027_coverage_audio_peer.py:78,162`, `test_027_t4_2_3_renderer_diff_rename.py:130,152,155,156,297,299`, `test_032_t6_1_end_to_end_routing.py:205`, `test_hashi_instructions_schema.py:53`, `test_garden_audit_hashi_example.py:54`; outside the search, `test_edit_frontmatter_schema.py:187`, `test_note_actions.py:95`, `test_039_t5_3_executor_needs_no_change.py:157` (read the vendored `const`). Left: `test_garden_audit_parser.py:262,1535` (garden-audit wire), `test_031_t3_1_attachments_schema.py:213`, `test_039_t3_1_wire_v4.py:128`, `test_038_t2_4_wire_baseline_diff.py:6` (suggestions wire), `test_031_t2_6_phase2_validation.py:103` (history text), `test_046_t5_6_fresh_delivery.py:44` (a waiting pre-v4 set, kept "3" on purpose); `test_046_t5_3_candidate_schema.py:55` was removed with the test-only schema.

  Done (2026-11-17): 445e9ffc; spec compliance and code quality PASS (mutations: producer const, manifest node type RED). Full suite 10913 passed, the one failure the polluted-registry ide_bridge smoke. Open for T6.4: an unscoped `replace_between_markers` happy path against both committed schemas; the merge-time byte-identity re-check (the hash test skips without a Hashi checkout).

- [x] **T6.2 End-to-end tests and documentation** `[activity: testing]`

  1. Prime: `tests/test_review_e2e*.py`, `tests/review_e2e_walk.py`, `tests/test_review_sdd_map.py:35-50`, `tests/test_review_why_docs.py`; README, `docs/tomo/`, PRIVACY.md `[ref: SDD/Directory Map; PRD/F6-AC6]`
  2. Test: e2e on fake Kado for week, month and quarter: setup with a mapping → Pass 1 document → edits (untick one section, add a user item, edit an item) → Pass 2 → set; then a re-run producing `replace_between_markers` for kept sections and nothing for an unticked one; a reference applier implementing Hashi's documented semantics shows the user's text unchanged and one block per section; the unmapped e2e paths unchanged; `test_review_sdd_map.py` repointed to spec 046's Directory Map (or both maps); WHY-doc mirror test covers the new libs.
  3. Implement: e2e fixtures; README feature text (#263, #256, #267 parts), `docs/tomo` mirrors complete, PRIVACY.md (rows file, read parts), `commands/review.md`, `vault-example.yaml`; version bumps.
  4. Validate: the full suite GREEN; ruff clean.
  5. Success: week, month and quarter run end to end as a month does `[ref: PRD/F6-AC6]`

  Carried from Phase 5: PRIVACY.md rows for the mapped stdout fields (`sections[].lines` in preview, `block_at.heading`); the `review-instructions.py` `SECTION_KEY` pattern is looser than the real `^s\d{1,3}$`; file room is nil (`review-instructions.py` 536/540, `review_section_set.py` 199/200, `review_delivery.py` 348/350), so split before adding; `_Note.read` walks the heading tree a second time like `review_mapping._tree` (share it); an `under` insert can leave two blank lines; the e2e walk covers a section stop beside the "Tomo Review" place problem, which asks the section choices first (one extra round).

  Done (2026-11-17): debt pass 808c94ce…0de1ca7e; docs 0fef6f55 + 63c232ba (README, PRIVACY, tomo-help 0.2.24, vault-example 1.11, SDD component rows); e2e 88696093 + 6fcabb9c (`tests/test_046_t6_2_e2e_sections.py`, `tests/e2e_046_sections_walk.py`, WHY-mirror glob in `test_review_why_docs.py`; 9 mutations RED). Correction to the note above: the first preview reports `place-missing` and `section-missing` together and the skill asks the place first; still one extra round, both answer orders tested. Open for T6.4: `tomo-help.md:123` "a rerun replaces Tomo's section" could read as covering mapped blocks — say "Tomo's review section" when T6.1 lands.

- [x] **T6.3 Live walk with Hashi in the test vault (owner-run)** `[activity: validate]`

  1. Prime: spec 045 `live-walk.md` format; reference memories on test-vault plugins (update-time-on-edit, Templater on create)
  2. Test, as explicit owner-gated steps:
     1. Sync on the owner's instruction: `scripts/update-tomo.sh --instance tomo-instance --yolo`.
     2. Restart the Tomo session so the synced skill loads.
     3. The owner walks, with the released Hashi:
        - setup for week, month and quarter (mapping, one off-limits mark, one analysis row) and the review continuing in the same session after the save;
        - week 2026-W13, month 2026-03 and quarter 2026-Q1, Pass 1 and Pass 2, then apply;
        - a re-run with one section unticked and one block edited.
     4. Walk rows record the section fit:
        - a section whose description no group covers received sourced items;
        - items read as reminders, not finished review text;
        - costs and durations per pass from `tomo-session-stats.py`.
     Writes reach the test vault only through Hashi's apply; nothing edits it directly.
  3. Implement: record every run in `live-walk.md` (counts only, no journal text); file walk-found fixes as tasks with RED tests. Notes from Phase 4: record the context use (tokens) and cost of the quarter's Pass 1 beside the ≤ $5 / ≤ 20 min KPI; the mapped callout's target stem and not-read / partly-read paths are still raw (path-derived, low risk) — check them in the walk or note them in the close-out.
  Carried from Phase 5: the live walk records the quarter's context use (tokens) and cost beside the KPI (already named above from Phase 4; check it is recorded); a section stop beside the "Tomo Review" place problem is reported together with it and costs one extra round (the skill asks the place first) — watch for it.

  Walk so far (2026-11-17, details go to `live-walk.md`):
  - W13 re-run stopped `landing-off-limits` on the old spec 045 "Tomo Review" right after off-limits "Check My Own Words". This is intended (SDD Complex Logic, test `sibling-body`). The owner removed the old section, and W13 was delivered as a first delivery.
  - Joint run round 1 (Hashi `feat/179`, own test vault): 10/10 actions applied; W13 passed every check. The 1 line changed outside the blocks was Obsidian's link update after the month move.
  - Fixes from round 1, owner decisions:
    - Review peers carry `tomo.sources` for Hashi's cleanup (01e75566, e5f6f95d).
    - `end` at a heading with sub-headings is sent `before` the first sub-heading (ada56fc6, 408b457f).
    - Quality review: PASS after the level-jump test.
  - Quarter 2026-Q1 (2026-11-18, new-note): `deliver` stopped at `doc_mark` (`doc-changed`, `open-unsaved`). A file then landed on the target path, and Resume refused `place-missing` + `section-missing` from the rebuilt plan. The model hand-wrote the mark and edited `meta.json`. Fix, owner decision: a resume of an open delivery uploads the payloads the first attempt stored in `payloads.json`, with no re-plan; step 8 asks `1 Retry · 2 Drop · 3 Abort` on `stopped`, plus one STRICT line against hand writes (`tests/test_046_t6_3_resume_stored_payloads.py`).
  - Joint run round 3a (2026-11-18, Hashi `feat/179`): Q1 new-note `move_note` applied; the note equals the inbox copy minus the 5 `tomo:` lines, 38 `<%` intact. Cleanup checks each source at its exact path and logged the moved inbox copy as "source already gone"; the target stayed intact.
  - Round 3b Pass 1 (Q1 re-run, `target_exists: true`, 12 markers in the note): written after one `double-placement` refusal pair (the model's rewrite dropped the wrong item; the one-rewrite stop held, the owner's retry fixed it). 90/90 days, 454 Kado calls, 0 retries. Findings for T6.4:
    - **Quarter read files exceed the Read tool's 25k-token limit** (`read-index.json` ~82.5k tokens; the month parts are too large as well; compact single-line JSON, so `offset`/`limit` don't help). Both Q1 Pass 1 runs (11:20, 15:02) fell back to `grep` on the Highlights / Disappointments / To Improve fields; the model reported the read as partial. Suspected size driver: `growth.created` (746 notes with links). Measure per key, then split or trim so every file fits.
    - `dailies_not_in_monthly` lists image embeds (`.png`) and sub-notes (`DP-…`) because it counts wiki-links and embeds, as in spec 045's weekly variant; only 3 `not_in_monthly` items resulted.
    - A reused, compacted Tomo session answered from stale memory ("set still waits for Hashi") and asked an extra Continue/Abort; `start` itself was right. Walk practice: a fresh session per run.
  - Round 3b Pass 2 + apply (Q1 re-run): `deliver` had no stops (steps set_json, set_md, doc_mark; `payloads.json` cleared). Set v4 with 12 actions: 11 `replace_between_markers` + 1 `replace_section` (`Tomo Review`). Hashi: 12/12 applied. 0 lines changed outside the blocks and the review section, including 5 frontmatter lines Obsidian plugins added before the run. 1 + 1 markers per key, 38 `<%` intact. Tomo re-checked this: 15 diff hunks, all inside. The cleanup trashed all 3 files. **Joint run complete: rounds 1, 2, 3a, 3b passed.**
  - Advisory for T6.4:
    - `section-ambiguous` also stops when the first sub-heading is the first occurrence of its text.
    - `peer_sources` does not check that paths are under the inbox.
    - The landing wording in `review_doc.py` ("at the end of").

  4. Validate: KPIs — weekly Pass 1 ≤ $0.50, monthly Pass 1 ≤ $2.00 and ≤ 7 min, Pass 2 ≤ $0.75, quarterly Pass 1 ≤ $5.00 and ≤ 20 min; 0 changed characters of user text outside markers; 0 sections with two blocks; 0 writes to off-limits.
  5. Success: Tomo and Hashi work together on all three kinds, first delivery and re-run `[ref: PRD/Success Metrics; PRD/Constraints]`

  Ticked at T6.4 (2026-11-19) on the Success line: R1 (week, month first delivery), R2 (both re-runs), R3a / R3b (quarter first delivery and re-run) applied with 0 lines outside the blocks, 1 + 1 markers per key, off-limits untouched. Not met inside this task, recorded in `close-out.md` §4, §5, §7: weekly Pass 1 cold $0.749 / $0.686 and Pass 2 $0.814 / $0.799 / $3.328 over their KPIs (owner decision open); the quarter Pass 1 KPI passes on partial reads only (#270); no section-fit rows and no `live-walk.md` were recorded (the walk record is the notes above, the joint-run handoffs and the close-out).

- [ ] **T6.4 Close-out** `[activity: validate]`

  1. Prime: spec 045 `close-out.md` and spec 044's (method)
  2. Test: every one of the 49 PRD criteria traced to node ids run in ONE pytest invocation, or to a recorded live-walk row for model behaviour; criteria parts no test can fail closed by RED-proven tests in `tests/test_046_close_out_gaps.py`; inbox cost log updated. Known prose-pin-only parts to trace to live-walk rows (Phase 2 drift check): F2-AC10 "the request continues in the same session", F2-AC3 "one line per left-out heading with its reason", F2-AC2/F2-AC6 (the table and suggestion descriptions as the model words them).
  3. Implement: `close-out.md`; spec README Finalize after merge; memory index entry (Critical Documentation). Carried from Phase 5: `load_run` reads the note before the set (a millisecond window where an applied set plus a stale note could plan a second insert; read the set first); the skill step 7 stop bullet is one ~1,100-character sentence (split into sub-bullets, re-pin `QUESTION` / `STOPS_HEAD`); the negative pin in `tests/test_046_t5_6_skill_choices.py` has a tautological half; the file-size debt above. Carried from T6.3: `dailies_not_in_*` should leave out non-note embeds. The quarter read size moved out of this spec to #270 (owner 2026-11-19). Measured: 717 KB, ~390k tokens in total; the index alone is 82.5k tokens against the Read limit of 25k. The redesign (chunked data, agents tiered by model) goes through brainstorming. The close-out records the quarter's Pass 1 as running on partial `grep` reads, a known limit.
  4. Validate: drift check spec vs code; the Kokoro FYI (`_outbox/for-kokoro/2026-11-14_…`) status checked and, if the contract changed at T6.1, a follow-up FYI; the PR carries the spec ID, the issues (#263, #256, #267) and the Hashi release.
  5. Success: the spec closes with its evidence `[ref: PRD all criteria]`

  Close-out written (2026-11-19): `close-out.md` — 49 criteria (as planned), 322 node ids in one invocation (518 passed), 8 gaps closed by RED-proven tests in `tests/test_046_close_out_gaps.py`, inbox cost log updated, Kokoro follow-up FYI `_outbox/for-kokoro/2026-11-19_tomo-to-kokoro_spec-046-wire-v4-released-v3-stays-valid.md` (the 2026-11-14 FYI still pending on Kokoro's side). Not ticked: the drift check spec vs code, the PR (spec ID, #263, #256, #267, Hashi 0.33.0) and the README Finalize after merge are still open.

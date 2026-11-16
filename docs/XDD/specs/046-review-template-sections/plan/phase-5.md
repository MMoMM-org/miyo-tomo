---
title: "Phase 5: Pass 2 — delivery into the user's sections"
status: in_progress
version: "1.1"
phase: 5
---

# Phase 5: Pass 2 — delivery into the user's sections

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View/Complex Logic]` — `plan_section` steps 1–8 and the three traced examples
- `[ref: SDD/Integration Points]` — the `replace_between_markers` contract and Hashi's kind order
- `[ref: SDD/Implementation Examples/The block in the note]`
- `[ref: SDD/Runtime View/Error Handling]` — Pass 2 rows
- `[ref: SDD/Architecture Decisions; ADR-4, ADR-5, ADR-10, ADR-12]`
- Hashi (read-only): `src/actions/insertUnderMarker.ts`, `markdownStructure.ts`, `blockInsert.ts`, `executor/planner.ts:39-56`

**Key Decisions**:
- Tomo mirrors Hashi's parse exactly (`review_hashi_text`: `hashi_headings`, `fenced_mask`, `JS_WS`) and stops instead of writing blind (ADR-10, Rule 9).
- Hashi runs inserts before `replace_section` before `replace_between_markers`; a section never lands in or at the "Tomo Review" range (ADR-12).
- Choices are flags on `preview` and `deliver`; `delivered_plan.sections` keeps keys and modes only; a partly applied set can be overwritten (ADR-12).
- **No committed schema changes in this phase (ADR-5, owner 2026-11-14):** Tomo's producer schema, `schema_version`, the shape manifest and the vendored Hashi copy all change in T6.1 after Hashi's release. Until then the new action is validated against a test-only schema built from the handoff fragment, and the full suite stays GREEN.

**Dependencies**: Phase 4 (T4.3 parse records). Order: T5.1 ∥ T5.3 → T5.2 (needs T5.1) → T5.4 (needs T5.1, T5.2, T5.3) → T5.5 → T5.6.

---

## Tasks

Delivers each kept section into the user's note as a marked block, replaces it on a re-run, and never changes the user's own text.

- [x] **T5.1 Section planning on an existing note (`lib/review_section_plan.py`)** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `lib/review_hashi_text.py` (`JS_WS`, `fenced_mask`, `hashi_headings`, `bare`, `marker_index`; moved there from `lib/review_actions.py` at T5.2, where they sat at lines 76-82, 223, 237, 252, 257) and `lib/review_actions.py` (`_first`/`_resolved`, `_insertion`); `lib/review_mapping.landing_off_limits`; Hashi files above `[ref: SDD/Runtime View/Complex Logic; ADR-4; ADR-10]`
  2. Test: `tests/test_review_section_plan.py` with numbered-line fixtures:
     - the three SDD traced examples, and the seven layouts of the second SDD validation (end three levels deep, before at the top, under with user text, a same-text heading at another level and at the same level, a block straddling a heading, a block inside "Tomo Review", "Tomo Review" placed inside an off-limits heading);
     - first delivery for each placement (`before`→`before`, `under`→`after`, `end`→`inside`); replace with and without scope;
     - stops: `section-missing` (also on a re-run), `section-ambiguous` (first delivery, re-run, and when Hashi's first match by (text, level) is another heading), `section-broken` (start without end, duplicates, out of order, a heading between the markers, a fenced, indented or quoted copy), `section-moved` (the confirm path always scoped), `block-in-review-section` (insert inside or at the Tomo Review range, block inside it), `landing-off-limits` (where the block would land and where it actually sits);
     - an item line equal to a marker line is escaped; JS `trimEnd` vs Python `rstrip` cases (U+0085, U+FEFF);
     - for every applied plan, a reference splice in the test helper shows every character outside the markers unchanged (its vectors are re-checked against Hashi's own tests in T6.1);
     - each stop RED-proven by reverting its rule.
  3. Implement: `lib/review_section_plan.py` (`plan_section`, SectionPlan, notices `block-replaced`, `block-moved-confirmed`); WHY doc first; version bump.
  4. Validate: tests green; module ≤ 350 lines; ruff clean.
  5. Success: a section is inserted once, replaced only between its own markers, and never lands in off-limits or Tomo Review text `[ref: PRD/F4-AC2, F4-AC3, F4-AC4, F5-AC1, F5-AC2, F5-AC3, F5-AC5; Rules 3, 4, 8, 9]`

- [x] **T5.2 New note, analysis rows and the "Tomo Review" interplay** `[activity: domain-modeling]`

  1. Prime: `lib/review_actions.py` (`_own` 276, `_templated_note` 411, `_new_note` 426-449, the rerun branch of `build_review_plan`); spec 045 ADR-8 (Templater rule); T5.1's `SectionPlan` `[ref: SDD/Runtime View/Complex Logic "New note"; PRD F2-AC12, F4-AC5]`
  2. Test: a new note from a plain template gets blocks spliced under headings found once, both markers present; a heading the new note lacks, or holds only as Templater code, routes the section to "Tomo Review" with its landing line saying so; the spec 045 Templater rule (the `_tomo` variant or the template as it is) applies first; analysis rows land as `<level+1>` sub-headings inside "Tomo Review" and never in the script-only section; the habits stay in "Tomo Review" with a mapping; the "Tomo Review" placement passes the landing check (else `landing-off-limits`); `review-section-kept` when a re-run leaves nothing for an earlier "Tomo Review" section; spec 045's unmapped "Tomo Review" output unchanged (existing tests green).
  3. Implement: new-note splicing via `plan_section` on the templated text; analysis sub-parts and routed sections in `review_actions.py`; WHY docs first; version bumps. Notes from Phase 4: delivery planning sets `review_sections.SectionPart.routed` for a section that routes to "Tomo Review" (the renderer already words its landing line); the rendered section order keeps template order for routed parts (`render_parts` selects by `placement != review`, not by `in_review`) — check that is what delivery wants. Notes from T5.1: `plan_section(row, note_text, period, items, *, choice=None, off_limits=(), review_at=None)` returns a `SectionPlan` (mode, `.stop`, `.action(action_id, target_path)`, `start_marker`/`end_marker`, `escaped_lines`, `block_at`); `review_at` is the planned insertion index of a new "Tomo Review" — the caller supplies it; `place_off_limits` is the landing check for the "Tomo Review" placement; `review_actions.split_lines` / `marker_index` are public now; `_Note.read` re-walks the heading tree like `review_mapping._tree` (drift risk — share it if this task touches either); an `under` insert can leave two blank lines (cosmetic); SDD corrections for the phase drift check: step 7 comment "step 6" → "step 5", drop the redundant "no leading space", "unless skip" on 3b and the straddle, the exact "p inside TR" rule, the signature and SectionPlan fields, stale `_marker_index` (solution.md ~174), the escape rule "contains marker text" (~1138), landing-off-limits offers no choice.
  4. Validate: `test_review_instructions.py`, `test_review_deliver*.py` green; `review_actions.py` ≤ 500 lines (move helpers to `review_section_plan` if not); ruff clean.
  5. Success: new notes and script-only sections get their material in the right place `[ref: PRD/F4-AC5, F2-AC12]`

- [x] **T5.3 Readable instructions and the test-only schema** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `lib/render_md.py` (`insert_under_marker` 312, `replace_section` 336); `tests/review_deliver_helpers.py:36-40` (`SCHEMAS`, the sibling Hashi checkout); the handoff fragment in `solution.md` Integration Points `[ref: SDD/Integration Points; ADR-5]`
  2. Test: `render_md` shows per section the copy-ready block, heading, placement and, for a replace, both marker lines and the scope; a test-only schema `tests/fixtures/instructions-v4-candidate.schema.json` (the vendored copy plus the handoff `$def`, built by a helper so it tracks the vendored file) validates a set with `replace_between_markers`, and the helpers used by Phase 5 tests validate new-action sets against it while sets without the new action keep validating against the committed schemas.
  3. Implement: the `render_md` branch; the fixture builder and the helper switch; WHY doc first; version bump. Do **not** touch `tomo/schemas/*` (T6.1).
  4. Validate: the full suite GREEN; ruff clean.
  5. Success: a user without Hashi can apply each section by hand `[ref: PRD/F4-AC7]`

- [x] **T5.4 Composing the set** `[activity: backend-api]`

  1. Prime: `lib/review_actions.py` (`ACTION_ID` 60, `build_review_plan`); `lib/review_state.py` (`SECTION_ACTIONS` 83, `all_applied`/`any_applied` 123-131, `review_state` steps 185-209); T5.1, T5.2 outputs `[ref: SDD/Architecture Decisions; ADR-12]`
  2. Test: ids `I01…In` in mapping order then "Tomo Review", independent of which sections had stops and of dict order (two runs byte-identical); one action per kept non-empty section plus "Tomo Review" when anything is left; `SECTION_ACTIONS` includes the new kind; `review_state` reports a set with I01 applied and I02 failed as partly applied (not delivered) — what `start`/status show for it; validated against the T5.3 test-only schema.
  3. Implement: composition in `review_actions.py`, `review_state.py`; WHY docs first; version bumps. Notes from T5.3: the test-only schema is built in memory by `candidate_schema()` in `tests/review_deliver_helpers.py` (not a committed `tests/fixtures/instructions-v4-candidate.schema.json`; `write_candidate_schema(tmp_path)` writes it on request) and keeps `schema_version` const "3" until T6.1; `schema_errors` switches to it only for a set carrying `replace_between_markers`, so validate the composed sets through that helper; render_md renders the new action in the `tag_handler_updates` bucket; advisory nits: the scope sentence "level N or higher" reads better as "level N or above (N or fewer `#`)" (pinned in test_046_t5_3_readable_sections.py), and `schema_errors` assumes dict actions. Notes from T5.2: `build_review_plan(..., choices=None)` returns `ReviewPlan.sections` (per-row SectionPlans) and `ReviewPlan.notices` (bare names, incl. `review-section-kept`); on an existing note the INSERT/REPLACE entries of `plan.sections` still produce no action — compose them here with `SectionPlan.action(id, target)` and count their `escaped_lines` (same defect class as T5.2's fix 1, add a test); a new note stays one `move_note` with blocks spliced in; module layout after the owner-approved split: review_actions (410 lines before T5.4) → review_new_note → review_section_plan (350/350, full, before T5.4) → review_hashi_text; new composition code goes into a new module above review_section_plan (candidate: move `plan_existing`, `plan_new_note`, `routed_keys`, `splice_blocks`, `review_parts` there, extend the import-direction test's `FORBIDDEN` map and the SDD Directory Map); stale prose refs to `review_actions.hashi_headings`/`fenced_mask`/`JS_WS` (solution.md ~939, this file's T5.1/T5.2 prime) go to the drift check.
  4. Validate: tests green; `review_actions.py` ≤ 500 lines; ruff clean.
  5. Success: the set carries every kept section in a stable order `[ref: PRD/F4-AC1]`

- [x] **T5.5 `review-instructions.py`: choices, stops, notices, resume and partly applied sets** `[activity: backend-api]`

  1. Prime: `review-instructions.py` (`load_run` 254, `preview` 294, `_overwrite_step` 322, `deliver` 342, `drop` 398); `lib/review_delivery.py` (`REFUSING`/`NOTICES` 70, `classify` 85, `ReviewMeta.second_set` 141, `plan_record` 262, `replan_differs` 274, `resume_refusal` 284); `lib/staged_delivery.py` `[ref: SDD/Internal API Changes; SDD/Runtime View/Error Handling; ADR-12]`
  2. Test: `--section-choice <key>=skip|review` and `--confirm-moved <key>` on `preview` and `deliver`; every new stop and notice reaches the output, unknown names refuse; the preview lists per section heading, placement, mode, lines and notices, the "edits inside Tomo's block are replaced" sentence for a replace, dropped sections with the user's own item count, empty sections; `nothing-to-deliver` counts sections and the part; `delivered_plan.sections` and `choices_given` hold keys and enums only (privacy test); `replan_differs` compares sections; `choices-needed` refuses a resume without the original choices; a partly applied set is overwritten through `_overwrite_step` with the `modified` guard, and `drop` on it behaves as the SDD says; a resume over an uploaded v3 set yields `exists`.
  3. Implement: as tested, helpers in `review_delivery.py` / `review_section_plan.py`; WHY docs first; version bumps. Notes from Phase 4: `section-dropped` comes from `ParsedDoc.section_counts()[key]` with `ticked is False` and `added` (the user's own items), `section-empty` from `empty`; the stop `section-checkbox-missing` is already a gate refusal (T4.4); `unlanded-items` today fires for kept section items because section keys are not in `rd.GROUPS` — Phase 5 must decide how a mapped document's section items count as landed. Wherever this phase edits `review_actions.py` (T5.2/T5.5; it was 463 lines before T5.2) an advisory nit: `_gate`'s loop reads better as `next((w for w in (...) if w in warnings), None)`, and SKILL.md step 5's rewrite-fix line could be a sub-bullet. Notes from T5.4: `lib/review_section_set.py` composes the set (`compose`, `lands`, `landed_escapes`, `action_id`; ids dense over emitted actions, mapping order, "Tomo Review" last); section stops stay only in `ReviewPlan.sections` while the other sections are composed — a delivery today would quietly leave a stopped section out, so here every stop must refuse or ask before writing; `review_state` reads a partly applied set as `open` (step 6a), but `preview`/`deliver` still refuse it `set-exists` (`second_set` fed `all_applied`) and `drop` refuses `already-applied` — widen `_overwrite_step` with the `modified` guard and add a test that a partly applied set reads `open` AND is deliverable (`test_review_deliver_rerun.py[partly-applied]` pins `set-exists` today); `delivered_plan.sections` + `replan_differs` must cover section keys and modes (that keeps a resume byte-identical with dense ids); still to wire: `unlanded-items` for section items, notices `block-replaced`, `block-moved-confirmed`, `review-section-kept`, and `landing-off-limits` in REFUSING with a skill line (T5.6).
  4. Validate: `test_review_instructions.py`, `test_review_deliver*.py` (resume, rerun, report) green; `review-instructions.py` ≤ 540 lines and no new top-level function besides the flag parsing; ruff clean.
  5. Success: every stop asks before writing, and no review gets stuck `[ref: PRD/F4-AC6, F5-AC4, F3-AC4 preview line]`

- [x] **T5.6 Skill steps 7 and 8: preview and per-section choices** `[activity: prompt-authoring]`

  1. Prime: SKILL.md steps 7-8 (163-205); WHY doc; `tests/test_review_skill_pass2.py` `[ref: SDD/User Interface & UX; ADR-12]`
  2. Test: pins for: wording each stop with its choices in the review language, passing the choices as flags on `deliver`, the replace sentence, the dropped/empty lines, `review-section-kept`, a fresh delivery offered after `exists`.
  3. Implement: WHY first; SKILL.md through `tcs-helper:skill-author`; version bump. Notes from T5.5: SKILL.md is 0.2.7 (33,133 bytes); it already carries one plain line per new stop/notice token, the stop line ends "Nothing is delivered; stop" — replace that with the per-section choice dialogue (offer each `sections[]` entry's `choices`, name the section by key from the step 5 rows, its `placement`), then pass the answers as `--section-choice <key>=skip|review` / `--confirm-moved <key>` on `preview` and `deliver`; the `choices-needed` branch (step 8) is dead until those flags are passed; re-pin the replace sentence and `review-section-kept` lines (`test_review_skill_pass2.PREVIEW_NOTICES`); after `name-taken` with `exists_path` (a waiting earlier set) offer a fresh delivery — SKILL.md's "a note is not Tomo's" wording is wrong for that case; `choice-invalid` (`choices_invalid: [keys]`) means the note changed since the preview → preview again. Script-side nits for T5.7 or close-out: `second_set`'s docstring/parameter still say "every action applied" while it is fed `any_applied`; `SECTION_KEY` in review-instructions.py is looser than the real `^s\d{1,3}$` key; `load_run` reads the note before the set (ms window where an applied set plus a stale note could plan a second insert — read the set first); file room is nil: review-instructions.py 536/540, review_section_set.py 199/200, review_delivery.py 348/350; the privacy walk covers only the unmapped path (preview `sections[].lines`, `block_at.heading`).
  4. Validate: skill tests green.
  5. Success: the user decides every ambiguous case in the existing Deliver step `[ref: PRD/F4-AC4, F4-AC6]`

- [ ] **T5.7 Phase Validation** `[activity: validate]`

  - Notes from T5.6: SKILL.md 0.2.9, 34,626 bytes; advisory nits for #259 or the close-out: the step 7 stop bullet is one ~1,100-character sentence (split into sub-bullets, "per stopped section named on a line, using only the choices that line listed"; re-pin `QUESTION` / `STOPS_HEAD`); one half of a negative pin in `test_046_t5_6_skill_choices.py` checks its own constant (tautology).

  - Run all Phase 5 tests and the full suite: GREEN, no named exception. If the sibling Hashi checkout already carries v4 (`tests/review_deliver_helpers.py:38-40`), name which tests that affects instead of skipping them. Drift check against the Complex Logic algorithm. WHY-first order (git log) and no eval-gated file changed. Lint clean.

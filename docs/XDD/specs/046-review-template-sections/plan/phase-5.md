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
- Tomo mirrors Hashi's parse exactly (`hashi_headings`, `fenced_mask`, `JS_WS`) and stops instead of writing blind (ADR-10, Rule 9).
- Hashi runs inserts before `replace_section` before `replace_between_markers`; a section never lands in or at the "Tomo Review" range (ADR-12).
- Choices are flags on `preview` and `deliver`; `delivered_plan.sections` keeps keys and modes only; a partly applied set can be overwritten (ADR-12).
- **No committed schema changes in this phase (ADR-5, owner 2026-11-14):** Tomo's producer schema, `schema_version`, the shape manifest and the vendored Hashi copy all change in T6.1 after Hashi's release. Until then the new action is validated against a test-only schema built from the handoff fragment, and the full suite stays GREEN.

**Dependencies**: Phase 4 (T4.3 parse records). Order: T5.1 ∥ T5.3 → T5.2 (needs T5.1) → T5.4 (needs T5.1, T5.2, T5.3) → T5.5 → T5.6.

---

## Tasks

Delivers each kept section into the user's note as a marked block, replaces it on a re-run, and never changes the user's own text.

- [x] **T5.1 Section planning on an existing note (`lib/review_section_plan.py`)** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `lib/review_actions.py` (`JS_WS` 76-82, `fenced_mask` 223, `hashi_headings` 237, `bare` 252, `_marker_index` 257, `_first`/`_resolved` 264-273, `_insertion` 295); `lib/review_mapping.landing_off_limits`; Hashi files above `[ref: SDD/Runtime View/Complex Logic; ADR-4; ADR-10]`
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

- [ ] **T5.2 New note, analysis rows and the "Tomo Review" interplay** `[activity: domain-modeling]`

  1. Prime: `lib/review_actions.py` (`_own` 276, `_templated_note` 411, `_new_note` 426-449, the rerun branch of `build_review_plan`); spec 045 ADR-8 (Templater rule); T5.1's `SectionPlan` `[ref: SDD/Runtime View/Complex Logic "New note"; PRD F2-AC12, F4-AC5]`
  2. Test: a new note from a plain template gets blocks spliced under headings found once, both markers present; a heading the new note lacks, or holds only as Templater code, routes the section to "Tomo Review" with its landing line saying so; the spec 045 Templater rule (the `_tomo` variant or the template as it is) applies first; analysis rows land as `<level+1>` sub-headings inside "Tomo Review" and never in the script-only section; the habits stay in "Tomo Review" with a mapping; the "Tomo Review" placement passes the landing check (else `landing-off-limits`); `review-section-kept` when a re-run leaves nothing for an earlier "Tomo Review" section; spec 045's unmapped "Tomo Review" output unchanged (existing tests green).
  3. Implement: new-note splicing via `plan_section` on the templated text; analysis sub-parts and routed sections in `review_actions.py`; WHY docs first; version bumps. Notes from Phase 4: delivery planning sets `review_sections.SectionPart.routed` for a section that routes to "Tomo Review" (the renderer already words its landing line); the rendered section order keeps template order for routed parts (`render_parts` selects by `placement != review`, not by `in_review`) — check that is what delivery wants. Notes from T5.1: `plan_section(row, note_text, period, items, *, choice=None, off_limits=(), review_at=None)` returns a `SectionPlan` (mode, `.stop`, `.action(action_id, target_path)`, `start_marker`/`end_marker`, `escaped_lines`, `block_at`); `review_at` is the planned insertion index of a new "Tomo Review" — the caller supplies it; `place_off_limits` is the landing check for the "Tomo Review" placement; `review_actions.split_lines` / `marker_index` are public now; `_Note.read` re-walks the heading tree like `review_mapping._tree` (drift risk — share it if this task touches either); an `under` insert can leave two blank lines (cosmetic); SDD corrections for the phase drift check: step 7 comment "step 6" → "step 5", drop the redundant "no leading space", "unless skip" on 3b and the straddle, the exact "p inside TR" rule, the signature and SectionPlan fields, stale `_marker_index` (solution.md ~174), the escape rule "contains marker text" (~1138), landing-off-limits offers no choice.
  4. Validate: `test_review_instructions.py`, `test_review_deliver*.py` green; `review_actions.py` ≤ 500 lines (move helpers to `review_section_plan` if not); ruff clean.
  5. Success: new notes and script-only sections get their material in the right place `[ref: PRD/F4-AC5, F2-AC12]`

- [ ] **T5.3 Readable instructions and the test-only schema** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `lib/render_md.py` (`insert_under_marker` 312, `replace_section` 336); `tests/review_deliver_helpers.py:36-40` (`SCHEMAS`, the sibling Hashi checkout); the handoff fragment in `solution.md` Integration Points `[ref: SDD/Integration Points; ADR-5]`
  2. Test: `render_md` shows per section the copy-ready block, heading, placement and, for a replace, both marker lines and the scope; a test-only schema `tests/fixtures/instructions-v4-candidate.schema.json` (the vendored copy plus the handoff `$def`, built by a helper so it tracks the vendored file) validates a set with `replace_between_markers`, and the helpers used by Phase 5 tests validate new-action sets against it while sets without the new action keep validating against the committed schemas.
  3. Implement: the `render_md` branch; the fixture builder and the helper switch; WHY doc first; version bump. Do **not** touch `tomo/schemas/*` (T6.1).
  4. Validate: the full suite GREEN; ruff clean.
  5. Success: a user without Hashi can apply each section by hand `[ref: PRD/F4-AC7]`

- [ ] **T5.4 Composing the set** `[activity: backend-api]`

  1. Prime: `lib/review_actions.py` (`ACTION_ID` 60, `build_review_plan`); `lib/review_state.py` (`SECTION_ACTIONS` 83, `all_applied`/`any_applied` 123-131, `review_state` steps 185-209); T5.1, T5.2 outputs `[ref: SDD/Architecture Decisions; ADR-12]`
  2. Test: ids `I01…In` in mapping order then "Tomo Review", independent of which sections had stops and of dict order (two runs byte-identical); one action per kept non-empty section plus "Tomo Review" when anything is left; `SECTION_ACTIONS` includes the new kind; `review_state` reports a set with I01 applied and I02 failed as partly applied (not delivered) — what `start`/status show for it; validated against the T5.3 test-only schema.
  3. Implement: composition in `review_actions.py`, `review_state.py`; WHY docs first; version bumps.
  4. Validate: tests green; `review_actions.py` ≤ 500 lines; ruff clean.
  5. Success: the set carries every kept section in a stable order `[ref: PRD/F4-AC1]`

- [ ] **T5.5 `review-instructions.py`: choices, stops, notices, resume and partly applied sets** `[activity: backend-api]`

  1. Prime: `review-instructions.py` (`load_run` 254, `preview` 294, `_overwrite_step` 322, `deliver` 342, `drop` 398); `lib/review_delivery.py` (`REFUSING`/`NOTICES` 70, `classify` 85, `ReviewMeta.second_set` 141, `plan_record` 262, `replan_differs` 274, `resume_refusal` 284); `lib/staged_delivery.py` `[ref: SDD/Internal API Changes; SDD/Runtime View/Error Handling; ADR-12]`
  2. Test: `--section-choice <key>=skip|review` and `--confirm-moved <key>` on `preview` and `deliver`; every new stop and notice reaches the output, unknown names refuse; the preview lists per section heading, placement, mode, lines and notices, the "edits inside Tomo's block are replaced" sentence for a replace, dropped sections with the user's own item count, empty sections; `nothing-to-deliver` counts sections and the part; `delivered_plan.sections` and `choices_given` hold keys and enums only (privacy test); `replan_differs` compares sections; `choices-needed` refuses a resume without the original choices; a partly applied set is overwritten through `_overwrite_step` with the `modified` guard, and `drop` on it behaves as the SDD says; a resume over an uploaded v3 set yields `exists`.
  3. Implement: as tested, helpers in `review_delivery.py` / `review_section_plan.py`; WHY docs first; version bumps. Notes from Phase 4: `section-dropped` comes from `ParsedDoc.section_counts()[key]` with `ticked is False` and `added` (the user's own items), `section-empty` from `empty`; the stop `section-checkbox-missing` is already a gate refusal (T4.4); `unlanded-items` today fires for kept section items because section keys are not in `rd.GROUPS` — Phase 5 must decide how a mapped document's section items count as landed. Wherever this phase edits `review_actions.py` (T5.2/T5.5; it is 463 lines) an advisory nit: `_gate`'s loop reads better as `next((w for w in (...) if w in warnings), None)`, and SKILL.md step 5's rewrite-fix line could be a sub-bullet.
  4. Validate: `test_review_instructions.py`, `test_review_deliver*.py` (resume, rerun, report) green; `review-instructions.py` ≤ 540 lines and no new top-level function besides the flag parsing; ruff clean.
  5. Success: every stop asks before writing, and no review gets stuck `[ref: PRD/F4-AC6, F5-AC4, F3-AC4 preview line]`

- [ ] **T5.6 Skill steps 7 and 8: preview and per-section choices** `[activity: prompt-authoring]`

  1. Prime: SKILL.md steps 7-8 (163-205); WHY doc; `tests/test_review_skill_pass2.py` `[ref: SDD/User Interface & UX; ADR-12]`
  2. Test: pins for: wording each stop with its choices in the review language, passing the choices as flags on `deliver`, the replace sentence, the dropped/empty lines, `review-section-kept`, a fresh delivery offered after `exists`.
  3. Implement: WHY first; SKILL.md through `tcs-helper:skill-author`; version bump.
  4. Validate: skill tests green.
  5. Success: the user decides every ambiguous case in the existing Deliver step `[ref: PRD/F4-AC4, F4-AC6]`

- [ ] **T5.7 Phase Validation** `[activity: validate]`

  - Run all Phase 5 tests and the full suite: GREEN, no named exception. If the sibling Hashi checkout already carries v4 (`tests/review_deliver_helpers.py:38-40`), name which tests that affects instead of skipping them. Drift check against the Complex Logic algorithm. WHY-first order (git log) and no eval-gated file changed. Lint clean.

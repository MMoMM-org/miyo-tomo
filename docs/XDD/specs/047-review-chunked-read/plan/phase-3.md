---
title: "Phase 3: Previous notes"
status: completed
version: "1.1"
phase: 3
---

# Phase 3: Previous notes

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples/Previous periods per kind; lines: 753-776]` — the table and the set-up check
- `[ref: SDD/Data Storage Changes; lines: 560-563]` — `previous/<kind>-<name>.json`
- `[ref: SDD/Error Handling; lines: 946, 949]` — refused / failed / kado-none; a previous note over the ceiling
- `[ref: SDD/Complex Logic (a), (b); lines: 966-1015]` — Kado calls per kind, the W14 trace
- `[ref: SDD/Architecture Decisions; ADR-5; lines: 1188-1192]`
- `[ref: SDD/ADR-5, amended v1.3]` — Kado's per-path denial is a `FORBIDDEN` tool error (`KadoToolError`, kado_client.py:948-954), verified in T1.4; `[ref: SDD/Implementation Gotchas]` — previous notes through the reader before `finish()`

**Key Decisions**:
- Found only through the setup's folder and format, flat or year subfolder, by the folder listing — no search (F3-AC4).
- Five states; `not-read` carries the cause (`refused`, `failed`, `kado-none`); a `KadoToolError` whose text names `FORBIDDEN` is caught per previous-note call → `refused`; any other `KadoToolError` is not swallowed; a `KadoAuthError` (401/403, wrong token) is never caught and stops the read as today (ADR-5 v1.3, T1.4 outcome (3)).
- The whole body cleaned by `review_md`, off-limits headings included as source text, cut by `review_day.cut_at_boundary` at `max_chars_per_day` (F3-AC10, F4-AC5).
- Previous notes join the single pass under the same `PacedReader` before `finish()`; ≤ 4 extra calls.

**Dependencies**: Phase 2. T3.1 needs only T2.1 and may start early; T3.2 needs T2.4 and T3.1.

---

> **Amended 2026-11-23 (owner, during T3.2):** an empty previous-note listing is `missing` ("no note found"), not `not-read` / `kado-none`; the cause `kado-none` was removed (PRD v1.2 F3-AC9, SDD v1.6 ADR-5/ADR-12, README Decisions Log). Mentions of `kado-none` below are the original plan text.

## Tasks

Reads the review notes of the period before inside the same paced pass and records each one's state.

- [x] **T3.1 Finding and reading previous notes (`lib/review_previous.py`)** `[activity: domain-modeling]`

  1. Prime: `lib/period.py` (`Period.previous` 176-177, `containing` 159, `note_paths` 196-200), `lib/review_config.py` (`GRANULARITY` 53, `folder_for` 173-186, `configured_formats` 194-201), `lib/review_children.py` (`find`/`prefetch`/`read`/`status` 58-106 — the pattern), `lib/review_reader.py` (`PacedReader` 39-141), `lib/kado_client.py` (`KadoAuthError` 51-52 / 761, `KadoToolError` 948-954), `_inbox/from-kado/2026-11-11_kado-to-tomo_tag-access-rules.md` (`FORBIDDEN`), `lib/review_md.py`, `lib/review_mapping.py` (off-limits); T1.4 outcome (3) `[ref: SDD/ADR-5]` `[ref: SDD/Implementation Examples; lines: 753-776]`
  2. Test: `tests/test_review_previous.py`:
     - `previous_periods` for every row of the SDD table: 2026-W14 → 2026-W13 + 2026-02; 2026-W01 → 2025-W52 + 2025-11; 2026-W01 under a Sunday/1-day rule; 2026-03 → 2026-02 + 2025-Q4; 2026-01 → 2025-12 + 2025-Q4; 2026-Q1 → 2025-Q4 (F3-AC1, F3-AC2, F3-AC3);
     - found flat and in the year subfolder; a note under another name (format changed) is `missing` (F3-AC4);
     - each of the five states, exactly one per note, and the review continues in every state (F3-AC5); a skeleton-only note is `empty`, a note with any user text or only a Tomo block is `found` (F3-AC7); no folder or format → `not-set-up` with no setup call (F3-AC8); a `KadoToolError` with `FORBIDDEN` on the note's read → `not-read` / `refused`; a `KadoAuthError` on a previous-note call stops the read (`stopped kado-auth`), not caught; a `KadoToolError` without `FORBIDDEN` is not turned into `refused`; still pending after the end pass → `failed`; an empty listing → `kado-none` (F3-AC9); the period's own dailies refused still stop the read;
     - a note over `max_chars_per_day` cut at a heading boundary, `partly_read` true (F3-AC10); off-limits headings kept as text;
     - the note is read as it stands now (an item removed after applying is absent from the text; F4-AC9); the target note of the period is never among the previous notes, also on a start over (F6-AC7);
     - `test_previous_notes_add_at_most_four_calls` on the fake Kado for a week review.
  3. Implement: WHY doc `docs/tomo/scripts/lib/review_previous.md` first; `lib/review_previous.py` (`previous_periods`, `set_up`, `prefetch` before `finish()`, `resolve` after it, the state and the cut text); `# version: 0.1.0`.
  4. Validate: tests green; module ≤ 300 lines; ruff clean.
  5. Success: each previous note is found by setup only and has exactly one named state `[ref: PRD/F3-AC1, F3-AC2, F3-AC3, F3-AC4, F3-AC5, F3-AC7, F3-AC8, F3-AC9, F3-AC10, F4-AC9, F6-AC7]`

- [x] **T3.2 Previous notes in the period read and the stage** `[activity: backend-api]`

  1. Prime: `lib/review_period.py` (`PeriodSources` 68-87, `CHILD` 61, the single pass and `reader.finish()` 369-391, result keys 400-427), `review-read.py` report, `lib/review_stage.py` (T2.3), `tests/test_review_period_golden.py`, `docs/tomo/scripts/lib/review_period.md` `[ref: SDD/ADR-5]` `[ref: SDD/Internal API Changes; lines: 592-594]` `[ref: SDD/Implementation Gotchas; lines: 1304, 1309]`
  2. Test: `PeriodSources.quarterly_folder` resolved config over profile; `review_period` calls `review_previous` before `reader.finish()` and resolves after it, so a 429 on a previous note is retried in the end pass; the result gains `previous` and nothing else (`test_review_period_golden.py` changes by that key only); the stage writes `previous/<kind>-<name>.json` with `read_id` and line-array sections (found only) and the manifest lists them; `report.previous` lists kind, name, role, path, state, cause, `partly_read` with no text; one retry/wait report covers the period's notes and the previous notes together (F2-AC6); the month walkthrough (2026-03: 2026-02 found, 2025-Q4 missing) and the quarter walkthrough (2025-Q4 missing) on the fake vault; the baseline e2e still GREEN (the old fingerprint does not show previous notes yet).
  3. Implement: WHY docs first; `lib/review_period.py` 0.5.1 → 0.6.0 (call sites and `quarterly_folder` only, CON-5); `review-read.py` report field; `review_stage` writes and lists `previous/`.
  4. Validate: `test_review_period*.py`, `test_review_read.py`, `test_review_stage.py` green; full suite green; ruff clean.
  5. Success: the period and its previous notes are read in one paced pass with one report `[ref: PRD/F2-AC6, F3-AC1, F3-AC2, F3-AC3]`

  - **Carry-over from the T2.4 review (2026-11-23):** in `review-read.py` `_units` reads `weeks.json["units"]` outside `_stored`'s try, so a stamped `weeks.json` without `units` exits 1 instead of discarding as `stage-invalid`; move the call inside the try (or catch KeyError) with a test, while this task edits `review-read.py`.

- [x] **T3.3 Phase Validation** `[activity: validate]`

  - Full suite in ONE invocation — GREEN; ruff clean. Trace F2-AC6, F3-AC1 … F3-AC5, F3-AC7 … F3-AC10, F4-AC9, F6-AC7 to node ids. RED proofs: revert the year-subfolder lookup, the per-call `FORBIDDEN` `KadoToolError` catch and the skeleton check one at a time and record which test fails. WHY docs before code; no eval-gated file changed; `lib/review_period.py` within CON-5.

  - **Outcome (2026-11-23):** full suite in ONE invocation at the phase-3 head: 11,243 passed, 18 skipped, 1 failed — `tests/ide_bridge/test_configure_ide_bridge.py::test_install_smoke_ide_bridge_block_exists`, the baseline failure (failing ⊆ baseline); baseline e2e green, goldens unchanged. `ruff check tomo/scripts scripts tests` clean. No file under `tomo/dot_claude/` changed in this phase; `lib/review_period.py` changed by call sites, `quarterly_folder` and `previous_notes` only (CON-5; reviewer-checked). WHY docs edited before code in each commit (implementer reports). RED proofs (T3.1 implementer and reviewers, isolated copies): year-subfolder lookup off → `tests/test_review_previous.py::test_found_in_the_year_subfolder`; per-call FORBIDDEN catch off → `::test_forbidden_read_is_not_read_refused`, `::test_forbidden_listing_is_not_read_refused`; skeleton check off → `::test_skeleton_only_note_is_empty`; resolve before `finish()` → `tests/test_review_period_previous.py::test_a_previous_note_turned_away_is_retried_by_the_end_pass`. Trace: F2-AC6 `tests/test_review_period_previous.py::test_one_summary_covers_the_period_and_the_previous_notes`, `tests/test_review_read_previous.py::test_one_summary_covers_the_period_and_the_previous_notes`; F3-AC1/AC2/AC3 `tests/test_review_previous.py::test_previous_periods_per_kind[*]`, `::test_previous_periods_week_under_sunday_one_day_rule`, `::test_week_previous_month_is_decided_by_the_week_start`, `tests/test_review_read_previous.py::test_the_month_reads_its_previous_month_and_quarter`, `::test_the_quarter_reads_its_previous_quarter`; F3-AC4 `tests/test_review_previous.py::test_found_flat`, `::test_found_in_the_year_subfolder`, `::test_note_under_another_name_is_missing_and_never_searched`; F3-AC5 `::test_each_state_once_per_note_and_review_continues[*]`; F3-AC7 `::test_skeleton_only_note_is_empty`, `::test_any_user_text_is_found`, `::test_only_a_tomo_block_is_found`; F3-AC8 `::test_no_folder_or_format_is_not_set_up_without_a_call`, `tests/test_review_period_previous.py::test_a_kind_not_set_up_costs_no_call`; F3-AC9 (amended v1.2) `tests/test_review_previous.py::test_forbidden_read_is_not_read_refused`, `::test_still_pending_after_the_end_pass_is_failed`, `::test_empty_listing_is_missing[*]`, `tests/test_review_period_previous.py::test_a_refused_previous_note_does_not_stop_the_read`, `::test_refused_dailies_still_stop_the_read[*]`; F3-AC10 `tests/test_review_previous.py::test_note_over_the_limit_cut_at_a_heading_boundary`, `tests/test_review_period_previous.py::test_previous_rows_use_the_day_settings_limit`; F4-AC9 `tests/test_review_previous.py::test_note_is_read_as_it_stands_now`; F6-AC7 `::test_target_note_is_never_a_previous_note[*]`.


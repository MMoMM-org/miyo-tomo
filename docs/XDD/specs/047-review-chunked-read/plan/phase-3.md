---
title: "Phase 3: Previous notes"
status: in_progress
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

- [ ] **T3.2 Previous notes in the period read and the stage** `[activity: backend-api]`

  1. Prime: `lib/review_period.py` (`PeriodSources` 68-87, `CHILD` 61, the single pass and `reader.finish()` 369-391, result keys 400-427), `review-read.py` report, `lib/review_stage.py` (T2.3), `tests/test_review_period_golden.py`, `docs/tomo/scripts/lib/review_period.md` `[ref: SDD/ADR-5]` `[ref: SDD/Internal API Changes; lines: 592-594]` `[ref: SDD/Implementation Gotchas; lines: 1304, 1309]`
  2. Test: `PeriodSources.quarterly_folder` resolved config over profile; `review_period` calls `review_previous` before `reader.finish()` and resolves after it, so a 429 on a previous note is retried in the end pass; the result gains `previous` and nothing else (`test_review_period_golden.py` changes by that key only); the stage writes `previous/<kind>-<name>.json` with `read_id` and line-array sections (found only) and the manifest lists them; `report.previous` lists kind, name, role, path, state, cause, `partly_read` with no text; one retry/wait report covers the period's notes and the previous notes together (F2-AC6); the month walkthrough (2026-03: 2026-02 found, 2025-Q4 missing) and the quarter walkthrough (2025-Q4 missing) on the fake vault; the baseline e2e still GREEN (the old fingerprint does not show previous notes yet).
  3. Implement: WHY docs first; `lib/review_period.py` 0.5.1 → 0.6.0 (call sites and `quarterly_folder` only, CON-5); `review-read.py` report field; `review_stage` writes and lists `previous/`.
  4. Validate: `test_review_period*.py`, `test_review_read.py`, `test_review_stage.py` green; full suite green; ruff clean.
  5. Success: the period and its previous notes are read in one paced pass with one report `[ref: PRD/F2-AC6, F3-AC1, F3-AC2, F3-AC3]`

  - **Carry-over from the T2.4 review (2026-11-23):** in `review-read.py` `_units` reads `weeks.json["units"]` outside `_stored`'s try, so a stamped `weeks.json` without `units` exits 1 instead of discarding as `stage-invalid`; move the call inside the try (or catch KeyError) with a test, while this task edits `review-read.py`.

- [ ] **T3.3 Phase Validation** `[activity: validate]`

  - Full suite in ONE invocation — GREEN; ruff clean. Trace F2-AC6, F3-AC1 … F3-AC5, F3-AC7 … F3-AC10, F4-AC9, F6-AC7 to node ids. RED proofs: revert the year-subfolder lookup, the per-call `FORBIDDEN` `KadoToolError` catch and the skeleton check one at a time and record which test fails. WHY docs before code; no eval-gated file changed; `lib/review_period.py` within CON-5.

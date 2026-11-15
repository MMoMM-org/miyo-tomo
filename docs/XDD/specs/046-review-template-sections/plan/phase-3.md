---
title: "Phase 3: Reading — child-review level, quarter, read files"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Reading — child-review level, quarter, read files

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View/Complex Logic]` — "Quarter marks"
- `[ref: SDD/Implementation Examples/Test Examples as Interface Documentation]` — golden month, disagreeing-notes quarter
- `[ref: SDD/Internal API Changes]` — `review-read.py` (`sections`, quarter keys, `--measure`, parts)
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-6, ADR-7]`

**Key Decisions**:
- The month's keys stay (`only_in_weekly_links`, `dailies_not_in_weekly`, `weekly`); the quarter adds `only_in_monthly_links`, `dailies_not_in_monthly`, `monthly` (ADR-6).
- Golden test first, refactor second; the golden file is captured from `main`'s code (ADR-6).
- Measure before splitting: `--measure` on 2026-Q1 runs only on the owner's go (perf-test rule: announce, wait, report done) (ADR-7).

**Dependencies**: Phase 1 and Phase 2 (T3.3 needs the saved rows of T1.3/T2.2). Order inside the phase: T3.1 → T3.2 → T3.3 → T3.4; T3.4 (owner-gated) may run alongside Phase 4.

---

## Tasks

Reads a quarter like a month one level up, and hands the model the section definitions in a file it can read.

- [x] **T3.1 Golden characterisation of the month read** `[activity: testing]`

  1. Prime: `tomo/scripts/lib/review_period.py` (`run` 346, `_link_differences` 259, report block 397-401); `tests/test_review_period.py`, `test_review_period_end_pass.py`, `test_review_read.py:185` fixtures `[ref: SDD/Implementation Examples/Test Examples; ADR-6]`
  2. Test: `tests/test_review_period_golden.py` captures the whole `read_period` result (days, weekly, both marks, report) for the fake month and fake week fixtures as committed JSON, generated from the unchanged code; it passes on the current code.
  3. Implement: the golden fixtures and the test only; no production change.
  4. Validate: test green on the unchanged code; mutating `_link_differences` (one line) turns it RED, then restore.
  5. Success: any change to the month or week read shape is caught `[ref: SDD/Constraints; CON-2]`

- [x] **T3.2 Child-review level and quarter reading** `[activity: domain-modeling]`

  1. Prime: `lib/review_period.py` (`PeriodSources` 63, `sources_from_config` 95, `_find_weeklies` 214, `_weekly_entries` 227, `_is_periodic` 245, `_link_differences` 259, `_after_end_pass` 331, `run` 346); `lib/review_weekly.py` (`weekly_content` 139); `lib/review_pacer.py` `[ref: SDD/Runtime View/Complex Logic "Quarter marks"; ADR-6]`
  2. Test: the golden test (T3.1) stays green; the disagreeing-notes quarter fixture (a link only in a weekly, only in a monthly, only in a daily, a link to stem `2026-02`) gives `only_in_monthly_links` = the monthly-only link, the weekly-only link in no mark, the monthly stem in no list; read as a month the same notes give `only_in_weekly_links` = the weekly-only link; boundary weeks clipped to the quarter's days (week-level own-section text tagged `overlap_days`, the accepted deviation); `monthly_status` / `monthly_notes` report absent months (F6-AC5) and `kado-empty`; the end pass recovers a monthly listing; the CHILD level is RED-proven (revert to WEEK → quarter test RED).
  3. Implement: `lib/review_children.py` (finding and reading child notes, their status report); `CHILD` table and parameterised marks in `review_period.py`; `_is_periodic` knows daily, weekly, monthly, quarterly formats; monthly notes split with `weekly_content`'s logic; WHY docs first; version bumps.
  4. Validate: `test_review_period*.py`, `test_review_read.py` green; `review_period.py` ≤ 450 lines; ruff clean.
  5. Success: a quarter reads its dailies, weekly notes as sources and monthly notes with marks `[ref: PRD/F6-AC4, F6-AC5]`

- [x] **T3.3 Read files: section definitions, compact JSON, quarter period, `--measure`** `[activity: backend-api]`

  1. Prime: `tomo/scripts/review-read.py` (`_PERIOD_RE` 78, `period_from` 91, `run` 164-199, `indent=2` 195); `lib/review_config.ReviewSetup.sections` (T1.3) `[ref: SDD/Internal API Changes; ADR-1; ADR-7]`
  2. Test: `read.json` carries `sections` (key, heading, level, parent, description, keywords, groups, cap; analysis rows included) only with a mapping; written compact; `--kind quarter --period 2026-Q1` reads the quarter; `--measure` writes no file for the model and prints calls, waits and bytes only (privacy test: no note text on stdout or stderr); without a mapping the result equals the golden content apart from the compact encoding (CON-2 difference pinned).
  3. Implement: `review-read.py` changes — for the quarter: `QUARTER: ^(\d{4})-Q([1-4])$` in `_PERIOD_RE`, `period_from` through `period.build`, which re-opens `--kind quarter` (limited to `tuple(_PERIOD_RE)` since T1.4), remove the `--kind quarter` case from `test_a_bad_invocation_exits_2` and the "until Phase 3" WHY paragraph in `docs/tomo/scripts/review-read.md`; WHY doc first; version bump.
  4. Validate: `test_review_read.py` green; ruff clean.
  5. Success: the model gets the definitions in the file it already reads `[ref: PRD/F1-AC1]`

- [x] **T3.4 Measure 2026-Q1, then split a quarter's read per month** `[activity: performance]`

  1. Prime: `[ref: SDD/Quality Requirements; ADR-7]`; spec 045 `live-walk.md` (R6/R8 March numbers)
  2. Test: (after the measurement) a quarter writes `read-index.json` (period, report, sections, part list) and one `read-<YYYY-MM>.json` per month; every part ≤ 256 KB on the measured data shape (fixture scaled to the measured bytes); week and month still write one `read.json`; a loader joins the parts back into one result equal to the unsplit one.
  3. Implement: announce the measurement and wait for the owner's go; run `--measure` against the test vault (sandbox permitting, host script against live Kado); record calls, wait, bytes per month in `plan/phase-3.md` under this task; then the split and the loader; WHY doc first; version bump. If a part still exceeds 256 KB, stop and bring the quarter character budget (SDD Technical Debt) to the owner.
  4. Validate: tests green; measurement recorded.
  5. Success: a quarter's read fits the model's Read limit per part
  - Measurement (2026-11-15, owner go; host `review-read.py --kind quarter --period 2026-Q1 --measure` against live Kado on the test vault, quarterly setup in a scratch copy of the tomo-instance config; read-only): wall 137 s, 453 calls, 0 retried, 133.1 s pacing wait, 0 not read; unsplit compact `read.json` 710,106 bytes; days per month 2026-01 179,969 / 2026-02 164,293 / 2026-03 181,763 bytes; non-day content (weekly, monthly, growth, report, open tasks) 184,081 bytes. An even third of the non-day content per month part gives ≈ 243 KB for March — under the 256 KB limit with little headroom, so the split decides where weekly / monthly / growth entries go by their own month. `[ref: PRD/Success Metrics cost and time; SDD/Quality Requirements]`
  - Split (`lib/review_read_parts.py`): days by date, monthly notes by their month, weekly notes by the majority month of their in-quarter days (tie: earlier month); period, report, sections, open tasks, growth, `not_read` and both mark lists in the index (none carries a date). Per-part bytes on 2026-Q1 scaled to the measured totals (`tests/review_scaled_quarter.py`, written through `review-read.py`), two shapes because the non-day breakdown was not measured — non-day bytes in the weekly/monthly notes (3 : 1): index 17,710 / 01 238,492 / 02 213,908 / 03 240,227; non-day bytes in growth and open tasks: index 178,833 / 01 181,905 / 02 165,954 / 03 183,645. Every part ≤ 256,000 bytes; the tightest, March, has 15.8 KB headroom.
  - Re-measured after the split (2026-11-15, owner go; same command and scratch config, live Kado, read-only): wall 138 s, 453 calls, 0 retried, 133.0 s wait; real per-part bytes: read-index.json 144,294 / read-2026-01.json 193,079 / read-2026-02.json 176,710 / read-2026-03.json 196,218. Every part ≤ 256,000 bytes; the tightest, March, has 59.8 KB headroom. The real shape lies between the two fixture shapes (most non-day bytes sit in the index's growth and open tasks).

- [x] **T3.5 Phase Validation** `[activity: validate]`

  - Run all Phase 3 tests and the full suite (GREEN). Golden test green. Drift check against SDD ADR-6/ADR-7. WHY-first order (git log) and no eval-gated file changed. Lint clean. T3.4 may still be waiting for the owner's go; the phase closes only when it is done.

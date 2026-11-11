---
title: "Phase 3: Reading the period and the review document"
status: in_progress
version: "1.1"
phase: 3
---

# Phase 3: Reading the period and the review document

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples/same-day reading of one daily]`: the algorithm and its trace.
- `[ref: SDD/Implementation Examples/pacer]`
- `[ref: SDD/Complex Logic (month reading)]`
- `[ref: SDD/Application Data Models]`: ReadResult, Proposals, ReviewDoc (frontmatter outside `tomo:`), item identity, the 80/20 boundary.
- `[ref: SDD/User Interface & UX]`: the document layout.
- `[ref: SDD/Runtime View/Error Handling]`: rows for `review-read`, `write`, `parse`, `replace`.
- `[ref: SDD/Architecture Decisions; ADR-2, ADR-4, ADR-9, ADR-12, ADR-13]`

**Key Decisions**:
- Same-day links and embeds are collected from the whole daily before the section filter; they count only when their name carries the day's date.
- Tasks count by ✅ date; `yesterday_fields` belong to the previous day; "has content" means text beyond the template skeleton.
- Habits, growth and link differences are computed by scripts; the model only writes `proposals.json` (ADR-12).
- Tomo items carry `%%t<n>%%` ids (ADR-13); the review keys are top-level frontmatter (ADR-2 amendment).
- `read.json` and `proposals.json` are deleted once the document is written or the run is aborted; stdout and stderr carry no content (ADR-9).
- Each lib stays one responsibility (Constitution L2 ≤ 300–500 LOC): `review_pacer`, `review_day`, `review_period`, `review_habits`, `review_doc`, `review_doc_parse`.

**Dependencies**:
- Phase 1 (T1.1 period, T1.2 client), Phase 2 (T2.1 config). T3.5 may start as soon as T2.1 is done.

---

## Tasks

This phase turns a period into a report, a fact file for the model and an editable review document, and reads the edited document back.

- [ ] **T3.1 Fake vault and pacer** `[activity: backend-api]`

  1. Prime: `tests/note_fake_vault.py`; `tomo/scripts/lib/link_members.py:40-41, 185-257` `[ref: SDD/Implementation Examples/pacer; ADR-4]`
  2. Test: `tests/review_fake_vault.py` supports `list_notes` with `filter` and cursor pages, `byName` globs, `byFrontmatter` (empty frontmatter like Kado), and injected 429 bursts, 503 and connection errors; `tests/test_review_pacer.py` — start at 0.3 s, doubling up to 2 s after retries, failed paths retried once at 2 s at the end, only those failing then reported, connection and auth errors propagate, `summary()` reports calls, retried (`attempt_count - call_count`), waited, not-read and `advice: raise-kado-limit` when retries happened; the client's `min_interval` is restored afterwards.
  3. Implement: `review_fake_vault.py`; `tomo/scripts/lib/review_pacer.py`; WHY doc `lib/review_pacer.md` first.
  4. Validate: tests green; RED proven by removing the slow-down and the end pass in an isolated copy.
  5. Success: rate limits slow the run instead of stopping it `[ref: PRD/F3-AC10, F3-AC11, F3-AC12]`

- [ ] **T3.2 Reading a day** `[activity: domain-modeling]`

  1. Prime: `[ref: SDD/Implementation Examples/same-day reading of one daily]`; structure of `Privat-Test/Calendar/301 Daily/2026-03-26.md`, `Efforts/300 Planner/DP-2026-03-26.md`, `Calendar/305 5 Year Journal/5J-2026-03-26.md`, `Efforts/500 OnGoing/Next Todos.md` (read only; never copy journal text into fixtures — write synthetic fixtures with the same structure)
  2. Test: `tests/test_review_day.py` — the quoth embed under the daily-changing `## [[DP-…|Dayplanner]]` heading is collected and read, tomorrow's planner link ignored; configured sections kept, "On This Day" skipped (its embed not collected); dataview/dataviewjs blocks and inline queries dropped; the 5J note read with its earlier-years subsections dropped; `Name:: v` and `**Name**:: v` fields parsed; yesterday fields attributed to D-1; tasks counted by ✅ date across files and next-day ✅ handled; task-note open tasks labelled "open today"; a plain-text daily still yields content; a skeleton-only daily has no content; a day over `max_chars_per_day` is cut at a section boundary and marked `partly-read`; a missing or unreadable linked note is reported for that day.
  3. Implement: `tomo/scripts/lib/review_day.py`; WHY doc first.
  4. Validate: tests green; ruff clean.
  5. Success: a day yields exactly its own content `[ref: PRD/F3-AC1, F3-AC2, F3-AC3, F3-AC4, F3-AC8]`

- [ ] **T3.3 Period sources, month and vault growth** `[activity: domain-modeling]`

  1. Prime: `[ref: SDD/Complex Logic (month reading)]`; structure of `Privat-Test/Calendar/302 Weekly/2026-W13.md` (read only)
  2. Test: `tests/test_review_period.py` — dailies found flat and in `<folder>/<YYYY>/`; the daily of the day after the period is read for its `yesterday_fields` only (they land on the period's last day; its content, links and tasks are not counted; absent → that day's value is missing); two dailies for one date both read and reported as duplicate; overlapping weekly notes resolved (flat and `<folder>/<week year>/`); day blocks keyed by the linked date and ending at the next heading of their level, out-of-month blocks dropped, `#### Review Check` and `## Organisation` not counted; week-level text tagged with week and overlap; `only_in_weekly_links` and `dailies_not_in_weekly` computed; no weekly notes → "no weekly notes found"; an empty weekly-folder listing → `kado_empty` with the access hint (not "no weekly notes"); growth: notes created in the period with their links, MOCs changed in the period, MOCs linked by new notes, from two filtered `list_notes` queries across pages; an empty Kado result is reported as "Kado returned none".
  3. Implement: `tomo/scripts/lib/review_period.py`; WHY doc first.
  4. Validate: tests green; ruff clean.
  5. Success: a month reads its weekly reviews and reports vault growth `[ref: PRD/F3-AC5, F3-AC6, F3-AC7, F3-AC9]`

- [ ] **T3.4 `review-read.py` CLI and report** `[activity: backend-api]`

  1. Prime: `[ref: SDD/Internal API Changes (review-read.py); SDD/Runtime View/Error Handling]`; `inbox-triage.py:1218-1262` (call-count snapshots)
  2. Test: week and month runs on the fake vault print the per-day report (dailies, duplicate, linked states), calls, retried, waited, not-read, `kado_empty` and `advice`; with injected 429s the report carries `raise-kado-limit`; `read.json` written under `tomo-tmp/review/<stem>/`; no daily with content → `nothing_to_review: true` with the `check-key-access` advice and no document later; Kado unreachable → `status: stopped`, nothing written; an unexpected exception prints only the class name; a week stays ≤ 40 calls and a month ≤ 140 on the fake vault without retries.
  3. Implement: `tomo/scripts/review-read.py` (top-level exception handler); WHY doc `review-read.md` first.
  4. Validate: tests green; ruff clean.
  5. Success: the reviewer sees what was read per day and why something is missing `[ref: PRD/F3-AC8, F3-AC9, F3-AC10, F3-AC11, F3-AC12, F3-AC13; SDD/Quality Requirements]`

- [ ] **T3.5 Habits as numbers** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `[ref: SDD/Data Storage Changes (trackers reuse)]`; `shared-ctx-builder.py:578`
  2. Test: `tests/test_review_habits.py` — booleans as day counts, integer/duration/time as averages over days with a value; missing and unreadable days named (an unrun `<% … %>` is unreadable), never zero; yesterday fields shifted; no trackers or no values → item or group absent; output in the setup language (de/en labels, en otherwise).
  3. Implement: `tomo/scripts/lib/review_habits.py`; WHY doc first.
  4. Validate: tests green; ruff clean.
  5. Success: habits show as numbers without Dataview `[ref: PRD/F8-AC1, F8-AC2, F8-AC3]`

- [ ] **T3.6 Writing the review document** `[activity: backend-api]`

  1. Prime: `[ref: SDD/Application Data Models (Proposals, ReviewDoc, item identity); SDD/User Interface & UX]`; `lib/doc_frontmatter.py`; `suggestions-reducer.py` `render_moc_proposal_doc` (:1657-1721) as a style reference
  2. Test: `tests/test_review_doc.py` — `review-proposals.schema.json` validation; an item without a source inside the period is rejected and listed; a theme naming fewer than two days is rejected; habits come from T3.5, never from the proposals; groups in order, month-only groups (`weekly_only`, `not_in_weekly`) only for months; empty groups show one "nothing found" line; every Tomo item ends with a unique `%%t<n>%%`; group labels and lines from the de/en table with en fallback; info callout names target, existence (also `target_found_elsewhere`), place and not-read parts; unticked Approved; frontmatter = a schema-valid `tomo:` block (`review`, `pending-approval`, run_id, updated_at) plus the top-level `review_*` keys; the path comes from `review_config.inbox_path()`; an existing non-Tomo `<name> Review.md` gives `doc-name-taken` and nothing is overwritten; a refused or failed Kado write gives `status: stopped` and no document is reported; an invalid proposals file gives `proposals-invalid`; no text for own sections; Pass 1 counts written to `meta.json`; `read.json` and `proposals.json` deleted after writing.
  3. Implement: `tomo/schemas/review-proposals.schema.json`, `tomo/scripts/lib/review_doc.py`, `tomo/scripts/review-doc.py write`; WHY docs first.
  4. Validate: tests green; ruff clean.
  5. Success: one editable document per period lands in the inbox `[ref: PRD/F4-AC1, F4-AC2, F4-AC3, F4-AC4, F4-AC5, F4-AC7, F3-AC13]`

- [ ] **T3.7 Parsing the edited document and starting over** `[activity: backend-api]`

  1. Prime: `[ref: SDD/Application Data Models (ReviewDoc, ApprovedReview, item identity, 80/20 boundary); SDD/Runtime View/Error Handling]`; `moc-proposal-parser.py:28-33`
  2. Test: `tests/test_review_doc_parse.py` — Approved ticked, unticked, or the line missing (`approved-line-missing`); kept, unticked and deleted Tomo items counted by id; a Tomo item rewritten without its source links keeps `origin: tomo, edited: true`; a ticked line without id is a user item; edited text kept verbatim, continuation lines included; everything unticked → nothing to deliver; unknown or duplicated group headings and broken frontmatter → warnings; the "nothing found" line never kept; a missing document → `status: not-found`; `replace` without `--confirm` returns `needs-confirm` and names the document, with it replaces; counts only on stdout.
  3. Implement: `tomo/scripts/lib/review_doc_parse.py`; parse and replace in `review-doc.py`; WHY doc first.
  4. Validate: tests green; ruff clean.
  5. Success: Pass 2 reads exactly what the user left `[ref: PRD/F5-AC1, F5-AC6, F6-AC1; PRD/Business Rules 1-3, 7; PRD/Edge Cases]`

- [ ] **T3.8 Phase Validation** `[activity: validate]`

  - Run Phase 1–3 tests, the full suite and ruff. Confirm no fixture contains text copied from the test vault's dailies, and no new lib exceeds ~500 lines.

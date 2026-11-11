---
title: "Phase 3: Reading the period and the review document"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Reading the period and the review document

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples; lines: 648-668]`: same-day reading algorithm and its trace.
- `[ref: SDD/Implementation Examples; lines: 692-719]`: `ReviewPacer`.
- `[ref: SDD/Complex Logic; lines: 816-825]`: month reading.
- `[ref: SDD/Application Data Models; lines: 541-584]`: ReadResult, Proposals, ReviewDoc, ApprovedReview.
- `[ref: SDD/User Interface & UX; lines: 860-900]`: the document layout.
- `[ref: SDD/Architecture Decisions; ADR-2, ADR-4, ADR-9, ADR-12]`

**Key Decisions**:
- Dailies are read whole, once per day, and split locally; linked notes count only when their name carries the day's date (ADR-12 facts, SDD read_day).
- Tasks count by ✅ date; `yesterday_fields` belong to the previous day.
- Habits, growth and link differences are computed by scripts; the model only writes `proposals.json` (ADR-12).
- `read.json` and `proposals.json` are deleted once the document is written or the run is aborted; stdout and stderr carry no content (ADR-9).

**Dependencies**:
- Phase 1 (T1.1 period, T1.2 client), Phase 2 (T2.1 config). T3.5 may start after T2.1.

---

## Tasks

This phase turns a period into a report, a fact file for the model and an editable review document, and reads the edited document back.

- [ ] **T3.1 Fake vault and pacer** `[activity: backend-api]`

  1. Prime: `tests/note_fake_vault.py`; `tomo/scripts/lib/link_members.py:40-41, 185-257` `[ref: SDD/Implementation Examples (pacer); ADR-4]`
  2. Test: `tests/review_fake_vault.py` supports `list_notes` with `filter`, `byName` globs, `byFrontmatter`, and injected 429 bursts, 503 and connection errors; `tests/test_review_read.py::pacer*` — start at 0.3 s, doubling up to 2 s after retries, `KadoRateLimitError` paths land in `not_read` and the run continues, connection and auth errors propagate, `summary()` reports calls, retried, waited, not-read; the client's `min_interval` is restored afterwards.
  3. Implement: `review_fake_vault.py`; `ReviewPacer` in `tomo/scripts/lib/review_read.py`; WHY doc `lib/review_read.md` first.
  4. Validate: tests green; RED proven by removing the slow-down in an isolated copy.
  5. Success: rate limits slow the run instead of stopping it `[ref: PRD/F3-AC10, F3-AC11, F3-AC12]`

- [ ] **T3.2 Reading a day** `[activity: domain-modeling]`

  1. Prime: `[ref: SDD/Implementation Examples (same-day reading)]`; structure of `Privat-Test/Calendar/301 Daily/2026-03-26.md`, `Efforts/300 Planner/DP-2026-03-26.md`, `Calendar/305 5 Year Journal/5J-2026-03-26.md`, `Efforts/500 OnGoing/Next Todos.md` (read only; never copy journal text into fixtures — write synthetic fixtures with the same structure)
  2. Test: configured sections kept, "On This Day" skipped; dataview/dataviewjs blocks and inline queries dropped; the quoth-embedded same-day planner read, tomorrow's planner link ignored; the 5J note read with its earlier-years subsections dropped; `Name:: v` and `**Name**:: v` fields parsed; yesterday fields attributed to D-1; tasks counted by ✅ date across files and next-day ✅ handled; task-note open tasks labelled "open today"; a plain-text daily still yields content; a missing or unreadable linked note is reported for that day.
  3. Implement: day reader functions in `lib/review_read.py`.
  4. Validate: tests green; ruff clean.
  5. Success: a day yields exactly its own content `[ref: PRD/F3-AC1..AC4, F3-AC8]`

- [ ] **T3.3 Month sources and vault growth** `[activity: domain-modeling]`

  1. Prime: `[ref: SDD/Complex Logic (month reading)]`; structure of `Privat-Test/Calendar/302 Weekly/2026-W13.md` (read only)
  2. Test: overlapping weekly notes resolved (flat and `<YYYY>/` folders); day blocks keyed by the linked date, out-of-month blocks dropped, `#### Review Check` and `## Organisation` not counted as day content; week-level text tagged with week and overlap; `only_in_weekly_links` and `dailies_not_in_weekly` computed; no weekly notes → "no weekly notes found"; growth: notes created in the period with their links, MOCs changed in the period, MOCs linked by new notes, from two filtered `list_notes` calls; an empty Kado result is reported as "Kado returned none".
  3. Implement: month and growth readers in `lib/review_read.py`.
  4. Validate: tests green; ruff clean.
  5. Success: a month reads its weekly reviews and reports vault growth `[ref: PRD/F3-AC5, F3-AC6, F3-AC7]`

- [ ] **T3.4 `review-read.py` CLI and report** `[activity: backend-api]`

  1. Prime: `[ref: SDD/Internal API Changes (review-read.py)]`; `inbox-triage.py:1218-1258` (call-count snapshots)
  2. Test: week and month runs on the fake vault print the per-day report, calls, retried, waited, not-read and `kado_empty`; `read.json` written under `tomo-tmp/review/<stem>/`; no daily with content → `nothing_to_review: true` and no document later; Kado unreachable → `status: stopped`, nothing written; a week stays ≤ 40 calls and a month ≤ 140 on the fake vault without retries.
  3. Implement: `tomo/scripts/review-read.py`; WHY doc `review-read.md` first.
  4. Validate: tests green; ruff clean.
  5. Success: the reviewer sees what was read per day `[ref: PRD/F3-AC8, F3-AC9, F3-AC10, F3-AC13; SDD/Quality Requirements]`

- [ ] **T3.5 Habits as numbers** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `[ref: SDD/Data Storage Changes (trackers reuse)]`; `shared-ctx-builder.py:578`
  2. Test: `tests/test_review_habits.py` — booleans as day counts, integer/duration/time as averages over days with a value; missing and unreadable days named (an unrun `<% … %>` is unreadable), never zero; yesterday fields shifted; no trackers or no values → item or group absent; output in the setup language.
  3. Implement: `tomo/scripts/lib/review_habits.py`; WHY doc first.
  4. Validate: tests green; ruff clean.
  5. Success: habits show as numbers without Dataview `[ref: PRD/F8-AC1, F8-AC2, F8-AC3]`

- [ ] **T3.6 Writing the review document** `[activity: backend-api]`

  1. Prime: `[ref: SDD/Application Data Models (Proposals, ReviewDoc); SDD/User Interface & UX]`; `lib/doc_frontmatter.py`; `suggestions-reducer.py` `render_moc_proposal_doc` (:1657-1721) as a style reference
  2. Test: `tests/test_review_doc.py::write*` — `review-proposals.schema.json` validation; an item without a source inside the period is rejected and listed; habits come from T3.5, never from the proposals; groups in order, month-only groups only for months; empty groups show one "nothing found" line; group labels and lines from the de/en table with en fallback; info callout names target, existence, place and not-read parts; unticked Approved; frontmatter `tomo.doc_type: review`, `pending-approval`, period, kind, target, language, stem; written to `<inbox>/<period-name> Review.md` only; no text for own sections; `read.json` and `proposals.json` deleted after writing.
  3. Implement: `tomo/schemas/review-proposals.schema.json`, `tomo/scripts/lib/review_doc.py`, `tomo/scripts/review-doc.py write`; WHY docs first.
  4. Validate: tests green; ruff clean.
  5. Success: one editable document per period lands in the inbox `[ref: PRD/F4-AC1..AC5, F4-AC7, F3-AC13]`

- [ ] **T3.7 Parsing the edited document and starting over** `[activity: backend-api]`

  1. Prime: `[ref: SDD/Application Data Models (ReviewDoc, ApprovedReview); SDD/Error Handling]`; `moc-proposal-parser.py:28-33`
  2. Test: `tests/test_review_doc.py::parse*` — Approved ticked or not; kept Tomo items, unticked and deleted items counted, user-added items kept with origin `user`; edited text kept verbatim; continuation lines; a deleted source link still lands; everything unticked → nothing to deliver; unknown or duplicated group headings → warning; the "nothing found" line never kept; `replace` names the document and replaces it only with `--confirm`; counts only on stdout.
  3. Implement: parse and replace in `lib/review_doc.py` / `review-doc.py`.
  4. Validate: tests green; ruff clean.
  5. Success: Pass 2 reads exactly what the user left `[ref: PRD/F5-AC1, F5-AC6, F6-AC1; PRD/Business Rules 1-3, 7]`

- [ ] **T3.8 Phase Validation** `[activity: validate]`

  - Run Phase 1–3 tests, the full suite and ruff. Confirm no fixture contains text copied from the test vault's dailies.

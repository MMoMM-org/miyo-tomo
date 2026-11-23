---
title: "Phase 4: Condensing — units, digests, carryover, plan and check"
status: in_progress
version: "1.1"
phase: 4
---

# Phase 4: Condensing — units, digests, carryover, plan and check

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Application Data Models; lines: 638-666]` — Digest, Carryover, the ids' two homes
- `[ref: SDD/Internal API Changes; lines: 602-626]` — `review-digest.py plan | check`, error codes, `condense-incomplete`
- `[ref: SDD/Data Storage Changes; lines: 572-582]` — `weeks.json`, `condensed.json`, `digests/`, `carryover.json`
- `[ref: SDD/Error Handling; lines: 951-957, 962]` — retry, failed, nothing-condensed, carryover whole-file and per-note failure, throttling
- `[ref: SDD/Complex Logic (b), (c), (d); lines: 991-1049]`
- `[ref: SDD/Test Examples; lines: 871-886]`
- `[ref: SDD/Architecture Decisions; ADR-4, ADR-8 (rounds); lines: 1182-1186, 1206-1210]`

**Key Decisions**:
- Deviation 2026-11-23 (owner, T1.5; SDD ADR-4 amended): the digest gains `growth` candidates `{text, sources: [day stem] ≥ 1, notes: [created-note path] 1..10}` ≤ 15; a candidate's source is the creation day (today's growth group needs a daily source, `review_doc.py:274-275`); `notes` ⊆ the unit's created notes. `proposer.inputs` never names `manifest.json`, `days/` or `growth/`.
- `review_digest` checks a file (schema, read id, unit, days, sources inside the unit, theme days, section keys, growth notes and creation days, size; carryover notes = found notes, sources among them, ids unique, ≤ 12 KB); document-level coverage of carryover ids is `review_carried`'s (Phase 5) — neither repeats the other.
- Each `check` is one attempt per job not passed: 1st failure `retry`, 2nd `failed`. A failed unit is "not condensed", named, and its days are never sources. All taking-part units failed → `stopped nothing-condensed`.
- `condensed.json` is written only by `review-digest.py`. `plan` validates files already present without counting an attempt, deletes a leftover `proposals.json`, and splits jobs into rounds of ≤ `MAX_PARALLEL` (16).
- T1.4 outcome decides whether `plan` pre-creates `digests/`.

**Dependencies**: Phase 3. T4.1 → T4.2 → T4.3 → T4.4.

---

## Tasks

Turns the stage into dispatchable jobs, checks every agent file before anything uses it, and names what could not be condensed.

- [ ] **T4.1 Digest and carryover schemas** `[activity: data-architecture]`

  1. Prime: `tomo/schemas/review-proposals.schema.json` (closed-schema style), SDD Digest and Carryover entities `[ref: SDD/Application Data Models; lines: 641-652]` `[ref: SDD/ADR-4]`
  2. Test: `tests/test_review_digest_schemas.py` — the W14 example digest and carryover of walkthrough (b) validate; refused: an unknown field, an empty `text`, an entry without sources, more than 25 `done`, a section key outside `^s[0-9]{1,3}$`, a carryover id outside `^c[0-9]{1,3}$`, an item `type` outside open/intention/theme, more than 30 carryover items; a single-day theme is allowed in a digest; a `growth` candidate validates with ≥ 1 source and 1–10 `notes`; refused: a growth candidate without `notes`, with more than 10 `notes`, more than 15 candidates.
  3. Implement: `tomo/schemas/review-digest.schema.json`, `tomo/schemas/review-carryover.schema.json` (`additionalProperties: false`); WHY notes in `docs/tomo/scripts/review-digest.md` (created here, completed in T4.3); add `tests/test_review_digest_schemas.py` to the Tests block of spec 047's `solution.md` Directory Map in the same commit.
  4. Validate: tests green; `test_review_sdd_map.py` green; `update-tomo.sh` schema glob (`schemas/*.json`, :535-538) covers the new files (read only); ruff clean.
  5. Success: the agents' file contracts are machine-checkable `[ref: SDD/ADR-4]`

- [x] **T4.2 File validation and the job state (`lib/review_digest.py`)** `[activity: domain-modeling]`

  1. Prime: T4.1 schemas; `lib/review_stage.py` (`weeks.json`, `growth/`, the manifest's previous files); `lib/review_weeks.py` `takes_part`; `lib/review_doc.py` `check_item` 252-278 (the day-source rule the growth candidates follow) `[ref: SDD/Building Block View; lines: 383]` `[ref: SDD/Internal API Changes; lines: 620-623]`
  2. Test: `tests/test_review_digest.py` (lib part) — every error code of the SDD list is produced by exactly one fixture: `digest-missing`, `not-json`, `schema (<pointer>)`, `read-id-mismatch`, `unit-mismatch`, `days-mismatch` (a digest whose `days` miss a taking-part day of the unit; F1-AC1), `source-outside-unit` (a W14 day in W13's digest), `theme-day-outside-unit`, `unknown-section`, `growth-note-outside-unit` (a created note of W14 named in W13's digest, or a path not created in the period), `growth-source-not-created-day` (a unit day on which none of the candidate's notes was created), `digest-too-large`, `carryover-notes-mismatch`, `carry-source-unknown`, `carry-id-duplicate`, `carryover-too-large`; the weekly-note stem is a valid source for `child_notes` only; the state model: pending → retry → failed, pending → passed, a present valid file passes without an attempt; carryover per-note failure removes only that note's items; no error string holds note text.
  3. Implement: WHY doc `docs/tomo/scripts/lib/review_digest.md` first; `lib/review_digest.py` (pure validation, the `condensed.json` state model); `# version: 0.1.0`.
  4. Validate: tests green; module ≤ 300 lines; ruff clean.
  5. Success: a digest that leaves out or goes beyond its unit's days is refused `[ref: PRD/F1-AC1]` `[ref: SDD/ADR-4]`

- [x] **T4.3 `review-digest.py plan | check`** `[activity: backend-api]`

  1. Prime: T4.2; `review-read.py` CLI conventions (one JSON object on stdout, exit 0 for usable output, ASCII stdout); T1.4 outcome (1); SDD plan/check shapes `[ref: SDD/Internal API Changes; lines: 602-623]` `[ref: SDD/Complex Logic (b), (c), (d)]` `[ref: SDD/ADR-4, ADR-8]`
  2. Test: `tests/test_review_digest.py` (CLI part):
     - `plan` for W14: one round [digester 2026-W14, carryover]; for 2026-03: 6 digesters + carryover; for 2026-Q1 with no found note: 14 digesters, `carryover_state: none`; `test_plan_rounds`: one round for ≤ 15 units + carryover, two rounds above `MAX_PARALLEL`; only taking-part units and only the period's days are dispatched (F1-AC6); each job names its day files, its `growth_files` (a unit's creation days only), weekly note, `sections` flag, `out` and `cap_bytes`; `proposer.inputs` in read order, holding `context*.json`, digests, carryover and child notes but never `manifest.json`, a `days/` or a `growth/` file, and `carried` false when the carryover is not passed;
     - `plan` on a continued read validates present files without an attempt and lists only the jobs not passed (walkthrough (c); F6-AC4); a leftover `proposals.json` is deleted;
     - `test_digest_naming_a_day_outside_its_unit_is_retried_then_failed` (SDD test example); the failed unit appears in `not_condensed` with its days (F6-AC1);
     - every taking-part unit failed → `stopped nothing-condensed` naming every unit, the stage kept (F6-AC8);
     - carryover whole-file failure after the retry → `carry_failed: true`; one note's items invalid after the retry → that note `failed`, its items removed, the other note's items kept (walkthrough (d); F6-AC2);
     - `stage-missing`, `stage-invalid`, `read-stale` refusals; the leak guard of `test_review_privacy.py` picks up `review-digest.py` and finds no note text in stdout or stderr.
  3. Implement: WHY doc `docs/tomo/scripts/review-digest.md` completed first; `tomo/scripts/review-digest.py` (`plan`, `check`, `MAX_PARALLEL = 16`, writes `condensed.json`; pre-creates `digests/` if T1.4 required it); `# version: 0.1.0`.
  4. Validate: tests green; ruff clean.
  5. Success: every job is checked, retried once, and a failure is named, never a partial read `[ref: PRD/F6-AC1, F6-AC2, F6-AC8]`

- [ ] **T4.4 The document waits for the condensing; the walk condenses** `[activity: backend-api]`

  1. Prime: `review-doc.py` (T2.4 state), `lib/review_stage.load`, `lib/review_doc.py` `Sources.of` 203-221, `tests/review_e2e_walk.py`, `tests/review_privacy_fixture.py` `[ref: SDD/Internal API Changes; lines: 626-627]` `[ref: SDD/Application Data Models; lines: 668-671]` `[ref: SDD/Implementation Gotchas; lines: 1305]`
  2. Test: `write` refuses `condense-incomplete` with no `condensed.json` or a unit `pending`/`retry`; `load` returns `condensed` (read-id-checked) and `carryover` only when its state is `passed`; `Sources` leaves out the dailies of a `failed` unit, so a proposal citing one is rejected as spec 045 does; `replace --confirm` keeps `condensed.json` and `carryover.json`; the walk runs `plan` → fixture digests (growth candidates derived from the fixture's `growth/` files, sourced by creation day) and carryover (derived from the fixture's day data, written by a test helper as the agents would) → `check` → fixture proposals → `write`; the baseline e2e stays GREEN for all three kinds.
  3. Implement: WHY docs first; `review-doc.py` refusal (version bump); `review_stage.load` completed (version bump); `review_doc.Sources` failed-unit rule (`lib/review_doc.py` 0.5.3 → 0.5.4); the walk's condense step and the fixture digest/carryover builder in `tests/review_privacy_fixture.py`.
  4. Validate: full suite green; ruff clean.
  5. Success: no document is written before every unit is passed or named as not condensed `[ref: PRD/F6-AC1; SDD/ADR-4]`

- [ ] **T4.5 Phase Validation** `[activity: validate]`

  - Full suite in ONE invocation — GREEN (baseline e2e unchanged); ruff clean. Trace F6-AC1, F6-AC2, F6-AC8 and the F1-AC1 / F1-AC6 / F6-AC4 collaborations to node ids. RED proofs: revert the `days-mismatch` check, the second-attempt `failed` transition, the per-note item removal and the `growth-note-outside-unit` check one at a time. WHY docs before code; no eval-gated file changed.

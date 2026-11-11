---
title: "Phase 1: Shared foundations"
status: pending
version: "1.1"
phase: 1
---

# Phase 1: Shared foundations

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View/Components]`: `lib/period.py`, `lib/staged_delivery.py`, `lib/kado_client.py`, `lib/render_md.py`, `inbox-triage.py`.
- `[ref: SDD/Implementation Examples/the week rule and ISO week 53]`
- `[ref: SDD/Implementation Examples/pacer]`: what the client must expose.
- `[ref: SDD/Implementation Boundaries]`
- `[ref: SDD/Architecture Decisions; ADR-3, ADR-4, ADR-7, ADR-10, ADR-11]`

**Key Decisions**:
- `KadoRateLimitError` subclasses `KadoError`; retries are derived as `attempt_count - call_count`; only the wait counters are new (ADR-4).
- The deliver-loop extraction is behaviour-preserving, takes the step set and target map from the caller, and lands as its own commit with `/note`'s suite green before and after (ADR-11).
- `replace_section` enters the producer schema only; the Hashi contract mirror is not edited (ADR-3).
- `/inbox` skips `review` documents before any read; no new Kado query in triage (ADR-10).

**Dependencies**:
- None. T1.1, T1.2, T1.3, T1.4, T1.6 and T1.7 run in parallel; T1.5 follows T1.4.

---

## Tasks

This phase builds the libraries and the small changes to shared code that every later phase uses.

- [ ] **T1.1 Period and week rule** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `[ref: SDD/Application Data Models (Period, WeekRule)]`; `[ref: SDD/Implementation Examples/the week rule and ISO week 53]`; PRD F2.
  2. Test: `tests/test_period.py` — every row of the SDD walkthrough table (2026-W13 days, 2026-W53 to 2027-01-03, 2027-01-01 → 2026-W53, 2025-12-29 → 2026-W01, 2025-W53 invalid, Sunday/1-day rule gives 2026-W10 for 2026-03-01); ISO equals `date.isocalendar()` for every day 2020–2030; months and `weeks_overlapping` (March 2026 ISO → W09..W14; January 2027 includes 2026-W53; December 2026 ends with 2026-W53); `is_finished`; `note_paths` flat then `<folder>/<week year>/` for weeks and `<folder>/<year>/` otherwise; name-format render/parse for `GGGG-[W]WW`, `gggg-[W]ww`, `YYYY-MM`, literals; `check_format` refuses `YYYY` with a week token (year-end example) and literals containing `/`, `\` or `..`; argument parsing for `''`, `month`, `setup`, `W13`, `2026-W13`, `M03`, `2026-03`, `@<path>`, and the invalid forms `2026-W54`, `2026-13`, `month 2026-W13`; a missing year picks the latest finished period; unfinished/future periods are refused with the last finished one named.
  3. Implement: `tomo/scripts/lib/period.py` (stdlib only, header docstring, `# version: 0.1.0`); WHY doc `docs/tomo/scripts/lib/period.md` first.
  4. Validate: tests pass; ruff clean; RED proven by mutating `min_days` handling in an isolated copy.
  5. Success: period arithmetic and arguments match the PRD `[ref: PRD/F2-AC2, F2-AC3, F2-AC4, F2-AC5, F2-AC6, F2-AC7, F2-AC9; PRD/F1-AC3, F1-AC4, F1-AC5]`

- [ ] **T1.2 Kado client: rate-limit accounting and filter** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `tomo/scripts/lib/kado_client.py:34-38, 94-149, 243-273, 638-682, 721-753, 835-853`; `tests/test_kado_client_retry.py`, `tests/test_kado_client_attempts.py`; `Kado/docs/api-reference.md:41-84, 1066-1092, 1515-1540`; `Kado/src/mcp/server.ts:139, 191` `[ref: SDD/Architecture Decisions; ADR-4]`
  2. Test (extend the two existing files): `retry_wait_s` and `pace_wait_s` grow on 429/503 retries and pacing (fake transport, patched sleep); a 429 or 503 surviving all retries raises `KadoRateLimitError` with `.status`, still caught by `except KadoError`; `Retry-After` honoured on 429, backoff on 503; `list_notes(..., filter={createdAfter, createdBefore})` and `_search_all` pass `filter` through and follow cursor pages; existing kado_client tests unchanged and green.
  3. Implement: additive changes in `kado_client.py`; update `docs/tomo/scripts/lib/kado_client.md` first; version bump.
  4. Validate: full suite green (existing callers); ruff clean.
  5. Success: callers can read retries and waiting and tell a rate-limit failure apart `[ref: PRD/F3-AC10, F3-AC11, F3-AC12; SDD/Implementation Examples/pacer]`

- [ ] **T1.3 Extract the staged deliver loop** `[activity: refactor]` `[parallel: true]`

  1. Prime: `tomo/scripts/note-instructions.py:384-596`; `tomo/scripts/lib/note_meta.py:39-41, 174-192`; `docs/tomo/scripts/note-instructions.md`; spec 044 SDD ADR-2 `[ref: SDD/Architecture Decisions; ADR-11]`
  2. Test: `tests/test_staged_delivery.py` — ordered caller-supplied steps; identical text (trailing newline normalised) counts as done; different text stops with `EXISTS`; a step in `steps_done` whose target is absent is never rewritten; `failed_step` is recorded before the upload; a step name the caller did not declare is refused; `_stable_block` pins `updated_at`. Run the whole `/note` suite before the change and keep it green after.
  3. Implement: `tomo/scripts/lib/staged_delivery.py` (steps, step → target map and meta accessor from the caller); `note_meta` accepts the caller's step set; `note-instructions.py` calls the lib with its own steps; WHY docs `lib/staged_delivery.md`, the pointers in `note-instructions.md` and `lib/note_meta.md` first; version bumps.
  4. Validate: `/note` tests (incl. `test_044_close_out_gaps.py`, `test_note_privacy.py`) green before and after; ruff clean; own commit.
  5. Success: one deliver loop serves both commands with unchanged `/note` behaviour `[ref: PRD/F5-AC10; SDD/Pattern Documentation]`

- [ ] **T1.4 Doc type, lifecycle and producer schema** `[activity: data-architecture]` `[parallel: true]`

  1. Prime: `tomo/schemas/doc-frontmatter.schema.json:12-17, 54-104`; `tomo/scripts/lib/doc_frontmatter.py:87-130`; `tomo/scripts/lib/tomo_lifecycle.py`; `tests/test_tomo_lifecycle.py:157-161`; `tomo/schemas/instructions.schema.json`; `tomo/schemas/hashi-instructions.schema.json:288-300`; `tomo/scripts/lib/wire_snapshot_parity.py:58-62`; `tests/test_tomo_schema_parity.py:84-90`; `tests/test_wire_snapshot_parity.py:776-806`; `tests/test_hashi_instructions_schema.py:219-227`; `tests/test_035_schema_identity.py:10` `[ref: SDD/Integration Points; ADR-3, ADR-10]`
  2. Test: `build_tomo_block("review", "pending-approval"|"approved", …)` validates under `TOMO_SCHEMA_STRICT`, other states are refused, and the block holds only the schema's keys (the review keys are top-level frontmatter); lifecycle doc-type set includes `review`; an instruction set with `replace_section` validates against the producer schema and the Hashi mirror; `replace_section` is no longer mirror-only in the schema-parity test, the wire-snapshot sanctioned set no longer exempts it, and `test_hashi_instructions_schema.py` asserts it is **present** in the producer (inverted, not deleted).
  3. Implement: schema enum + state branch, `STATE_MACHINE` entry, `replace_section` definition copied from the contract, parity exemption removed, the four tests updated, the `test_035` docstring corrected; WHY in the matching `docs/tomo/` files first; version bumps.
  4. Validate: schema and parity tests green; ruff clean.
  5. Success: the review document and `replace_section` are valid Tomo artefacts `[ref: PRD/F4-AC6, F5-AC8, F6-AC3; SDD/Data Storage Changes]`

- [ ] **T1.5 Copy-ready rendering of section actions** `[activity: backend-api]`

  1. Prime: `tomo/scripts/lib/render_md.py:44-61, 297-308, 370-374`; `note-instructions.py:175-189` (`_fence_for`); `docs/tomo/scripts/instruction-render.md` `[ref: SDD/Known Technical Issues; ADR-3]`
  2. Test: `insert_under_marker` content renders inside a fence long enough for its own backticks, with "before"/"inside" wording; `replace_section` renders the same way under its own heading with "replace the body of"; each action still gets `### Inn …` + `- [ ] Applied`; a backtick in the anchor does not break the line; existing render tests green.
  3. Implement: branches in `render_md.py` (changes only, no new logic cluster); WHY in `instruction-render.md` first; version bump.
  4. Validate: render tests green; ruff clean.
  5. Success: a user without Hashi can copy the section and knows the exact place `[ref: PRD/F5-AC9]`

- [ ] **T1.6 `/inbox` skips review documents** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `tomo/scripts/inbox-triage.py:357-395, 434-459, 574-599, 939-951`; `docs/tomo/scripts/inbox-triage.md` `[ref: SDD/Architecture Decisions; ADR-10]`
  2. Test: `tests/test_inbox_triage_review_skip.py` — a stamped `2026-W13 Review.md` in `pending-approval` and in `approved` is neither a new source nor read nor applied, and causes no warning; a user note "Book Review.md" without a tomo block stays a new item; a renamed stamped review document gives the existing unknown-doc_type warning only; a new periodic note stamped `rendered-note`/`pending-move` is not a new source; triage call counters unchanged.
  3. Implement: filename rule in `_get_doc_type`, silent skip before `read_note` in the pending loop; WHY in `inbox-triage.md` first; version bump. `commands/inbox.md` is not touched. A voluntary (paid, owner-run) eval suite run is offered at the phase gate because the change alters `/inbox` input.
  4. Validate: the full triage suite green; ruff clean.
  5. Success: `/inbox` ignores review documents and the waiting new note `[ref: PRD/F4-AC6, F5-AC4]`

- [ ] **T1.7 Kokoro FYI handoff** `[activity: documentation]` `[parallel: true]`

  1. Prime: `~/Kouzou/projects/miyo/miyo-handoff-protocol.md`; Kokoro ADR-028 (:160-162) and ADR-018 (:33, :119); `global/architecture/06-miyo-tomo-hashi.md:374` (read only) `[ref: SDD/Cross-Component Boundaries]`
  2. Test: the handoff file exists in `_outbox/for-kokoro/` with status `pending`, names spec 045 and #31, the first producer state of `replace_section`, the new doc_type `review` with its states, and that no Hashi or Kado change is asked.
  3. Implement: the handoff (gitignored buffer, via the miyo-outbox skill).
  4. Validate: the file follows the protocol's front matter.
  5. Success: Kokoro's records can be updated alongside the implementation `[ref: Constitution Architecture L2]`

- [ ] **T1.8 Phase Validation** `[activity: validate]`

  - Run the full suite and ruff. Confirm `/note` and `/inbox` tests unchanged and green, no eval-gated file in `git diff main --stat`, every edited managed file has a bumped version, every new file has a header docstring and `# version: 0.1.0`.

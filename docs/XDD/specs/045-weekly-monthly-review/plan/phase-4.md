---
title: "Phase 4: Delivery and open-review state"
status: pending
version: "1.1"
phase: 4
---

# Phase 4: Delivery and open-review state

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples/the review section and the heading-level rule]`: placement, levels, escaping, marker-based rerun detection, target lookup.
- `[ref: SDD/Internal API Changes]`: `review-instructions.py preview|deliver|drop|status`, the canonical states.
- `[ref: SDD/Complex Logic (review_state)]`
- `[ref: SDD/Runtime View/Error Handling]`: rows for `preview`, `deliver`, `drop`, `status`.
- `Hashi/src/actions/anchorResolver.ts:30-40, 100-107`, `insertUnderMarker.ts`, `replaceSection.ts`, `moveNote.ts:71-114`, `executor/jsonAppliedWriter.ts` (read only)
- `[ref: SDD/Architecture Decisions; ADR-3, ADR-6, ADR-8, ADR-11, ADR-13]`

**Key Decisions**:
- Section content is a pure function of the approved document — no clock values — so Hashi's identical-block check makes a resumed insert idempotent (ADR-3).
- Rerun detection is by the marker line under any heading; a same-named heading without the marker is never replaced (ADR-3).
- Delivery uses `lib/staged_delivery.py` with the steps `note → set_json → set_md → doc_mark` (ADR-11).
- `drop` withdraws a set Tomo already wrote (ADR-13); applied state comes from `applied` in the set JSON (ADR-6).

**Dependencies**:
- Phase 1 (T1.3, T1.4, T1.5), Phase 2 (T2.1, T2.3), Phase 3 (T3.6, T3.7).

---

## Tasks

This phase turns an approved document into an instruction set, readable instructions and, when needed, a new periodic note, and lets every later `/review` know where each review stands.

- [ ] **T4.1 Review actions** `[activity: domain-modeling]`

  1. Prime: `[ref: SDD/Implementation Examples/the review section and the heading-level rule]`; `tomo/schemas/hashi-instructions.schema.json:88-104, 259-300`; `lib/note_actions.py`; `lib/render_withhold.py`; `note-instructions.py:424-437` (stamping the waiting note)
  2. Test: `tests/test_review_instructions.py::actions*` — existing target without marker → one `insert_under_marker` with `before` or `inside` (never `after`); target with the marker of the same period → one `replace_section` on the heading above it, also when that heading was renamed (`heading-renamed`); same heading without marker → `user-heading-collision`, no action; target absent at its path but found by name elsewhere → that note is the target (`target_moved`); target absent everywhere → new note (template variant, raw Templater template with `templater_hint`, a vanished variant falling back to raw with `variant_missing`, or plain note) stamped `rendered-note`/`pending-move`, plus one `move_note`; heading levels from `review_config.place_level`; every line of an item, continuation lines included, starting with `#`, `- [`, `>` or a fence escaped and counted; ids stripped from the landed text; content ends with one blank line and is byte-identical across two builds; only kept items land, empty groups leave no heading; own sections never targeted; place missing → `place-missing` with the note's headings; every set validates against both schemas.
  3. Implement: `tomo/scripts/lib/review_actions.py`; WHY doc first.
  4. Validate: tests green; RED proven for the collision guard, the marker search and the level rule by mutation in an isolated copy.
  5. Success: the section lands at the right place once and never swallows the user's own section `[ref: PRD/F4-AC7, F5-AC3, F5-AC4, F5-AC5, F5-AC6, F5-AC7, F6-AC3; PRD/Edge Cases]`

- [ ] **T4.2 `review-instructions.py` preview, deliver, drop** `[activity: backend-api]`

  1. Prime: `[ref: SDD/Internal API Changes; SDD/Runtime View]`; `lib/staged_delivery.py` (T1.3); `lib/render_md.py` (T1.5)
  2. Test: `preview` returns mode, target, place, `section_md`, escaped count, `templater_hint`, problems (`not-approved`, `approved-line-missing`, `nothing-to-deliver`, `place-missing`, `heading-renamed`, `user-heading-collision`); `deliver` refuses an unapproved document and a second set for the same stem (`status: refused`, nothing written); writes (note,) `<stem>_instructions.json`, `<stem>_instructions.md` in that order through `inbox_path()`, the MD carrying copy-ready text and the place; switches from new-note to insert when the target appeared since Pass 1; marks the document `approved` and its first line "delivered" with a guarded `expected_modified` write as the last step; an `expected_modified` mismatch stops with `doc-changed` and a resumable `failed_step`; a refused or failed Kado write stops with `kado-write-failed`; an interrupted delivery (fault injected at each step) resumes without duplicates; `drop` after a partial delivery rewrites the set JSON with an empty `actions` list and marks the MD withdrawn (the result validates and has nothing to apply), and without a set removes only the stage; `--place-anchor` uses the user's chosen heading; stderr has problem classes only; an unexpected exception prints only the class name.
  3. Implement: `tomo/scripts/review-instructions.py`; the delivered-mark function in `lib/review_doc.py`; WHY doc first.
  4. Validate: tests green; ruff clean.
  5. Success: an approved review becomes an instruction set and readable instructions, resumably, and a dropped one stays unapplicable `[ref: PRD/F5-AC1, F5-AC2, F5-AC8, F5-AC9, F5-AC10, F5-AC11, F6-AC2, F6-AC4]`

- [ ] **T4.3 Applied reader and open-review states** `[activity: backend-api]`

  1. Prime: `[ref: SDD/Complex Logic (review_state); ADR-6]`; Hashi `executor/jsonAppliedWriter.ts`, `moveNote.ts:71-107` (read only)
  2. Test: `tests/test_review_state.py` — `review_state` returns exactly the canonical states `open`, `failed-delivery`, `delivered`, `applied`, `move-refused`, `target-missing` from the document, `meta.json`, the set JSON (`applied` per action) and the probes; `approved` without a set JSON is `failed-delivery`; a withdrawn set is not listed; `applied` is reported once (`meta.applied_reported`) and then not offered; `review-instructions.py status` and `review-session.py start` return the same state for the same inputs; the list is ordered by period.
  3. Implement: complete `lib/review_state.py`; `status` and `start` call it; WHY doc first.
  4. Validate: tests green; ruff clean.
  5. Success: every open review is offered first, and a set waiting for Hashi blocks a second one `[ref: PRD/F2-AC1, F5-AC10, F6-AC2, F6-AC4]`

- [ ] **T4.4 Phase Validation** `[activity: validate]`

  - Run Phase 1–4 tests, the full suite and ruff. Validate one generated set with Hashi's schema copy and its `instructions.md` peer-checkbox format (`### Inn …` + `- [ ] Applied`).

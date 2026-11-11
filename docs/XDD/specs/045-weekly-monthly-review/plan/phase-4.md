---
title: "Phase 4: Delivery and open-review state"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Delivery and open-review state

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples; lines: 669-690]`: review section, heading-level rule, escaping, rerun detection.
- `[ref: SDD/Internal API Changes; lines: 495-540]`: `review-instructions.py preview|deliver|drop|status`.
- `[ref: SDD/Complex Logic; lines: 801-815]`: open-review state.
- `[ref: SDD/Error Handling; lines: 786-800]`
- `Hashi/src/actions/insertUnderMarker.ts`, `replaceSection.ts`, `moveNote.ts` (read only)
- `[ref: SDD/Architecture Decisions; ADR-3, ADR-6, ADR-8, ADR-11]`

**Key Decisions**:
- Section content is a pure function of the approved document — no clock values — so Hashi's identical-block check makes a resumed insert idempotent (ADR-3).
- A same-named heading without Tomo's marker is never replaced (ADR-3).
- Delivery uses `lib/staged_delivery.py` from T1.3 (ADR-11).
- Applied state comes from `applied` in the set JSON (ADR-6).

**Dependencies**:
- Phase 1 (T1.3, T1.4, T1.5), Phase 3 (T3.6, T3.7).

---

## Tasks

This phase turns an approved document into an instruction set, readable instructions and, when needed, a new periodic note, and lets every later `/review` know where each review stands.

- [ ] **T4.1 Review actions** `[activity: domain-modeling]`

  1. Prime: `[ref: SDD/Implementation Examples (review section)]`; `tomo/schemas/hashi-instructions.schema.json:88-104, 259-300`; `lib/note_actions.py`; `lib/render_withhold.py`
  2. Test: `tests/test_review_instructions.py::actions*` — existing target without section → one `insert_under_marker` at the configured anchor and placement; target with the marked section of the same period → one `replace_section`; same heading without marker → `user-heading-collision`, no action; missing target → new note (template variant, raw Templater template with `templater_hint`, or plain note) plus one `move_note`; heading levels follow the place (before/after → same level, inside → +1, groups deeper); lines starting with `#`, `- [`, `>` or a fence escaped and counted; content ends with one blank line and is byte-identical across two builds; empty groups leave no heading; place missing → `place-missing` with the note's headings; every set validates against both schemas.
  3. Implement: `tomo/scripts/lib/review_actions.py`; WHY doc first.
  4. Validate: tests green; RED proven for the collision guard and the level rule by mutation in an isolated copy.
  5. Success: the section lands at the right place once and never swallows the user's own section `[ref: PRD/F5-AC3..AC7, F6-AC3, F4-AC7]`

- [ ] **T4.2 `review-instructions.py` preview, deliver, drop** `[activity: backend-api]`

  1. Prime: `[ref: SDD/Internal API Changes; SDD/Runtime View]`; `lib/staged_delivery.py` (T1.3); `lib/render_md.py` (T1.5)
  2. Test: `preview` returns mode, target, place, `section_md`, escaped count, `templater_hint`, problems; `deliver` refuses an unapproved document and a second set for the same stem; writes (note,) `<stem>_instructions.json`, `<stem>_instructions.md` in order, the MD carrying copy-ready text and the place; switches from new-note to insert when the target appeared since Pass 1; marks the document `approved` and its first line "delivered" with a guarded write; an interrupted delivery (fault injected at each step) resumes without duplicates; `drop` removes the stage and leaves vault files as they are; `--place-anchor` uses the user's chosen heading; stderr has problem classes only.
  3. Implement: `tomo/scripts/review-instructions.py`; WHY doc first.
  4. Validate: tests green; ruff clean.
  5. Success: an approved review becomes an instruction set and readable instructions, resumably `[ref: PRD/F5-AC1, F5-AC2, F5-AC8..AC11, F6-AC2, F6-AC4]`

- [ ] **T4.3 Applied reader and open-review states** `[activity: backend-api]`

  1. Prime: `[ref: SDD/Complex Logic (open-review state); ADR-6]`; Hashi `executor/jsonAppliedWriter.ts`, `moveNote.ts:71-107` (read only)
  2. Test: `review-instructions.py status` and `review-session.py start` classify `open`, `failed-delivery`, `delivered`, `applied`, `move-refused` from the document, `meta.json` and the set JSON (`applied` per action, inbox copy vs. existing target); `applied` reviews are reported once and not offered; the list is ordered by period.
  3. Implement: applied reader in `lib/review_actions.py`; wire the states into `start` (T2.3).
  4. Validate: tests green; ruff clean.
  5. Success: every open review is offered first, and a set waiting for Hashi blocks a second one `[ref: PRD/F2-AC1, F5-AC10, F6-AC2, F6-AC4]`

- [ ] **T4.4 Phase Validation** `[activity: validate]`

  - Run Phase 1–4 tests, the full suite and ruff. Validate one generated set with Hashi's schema copy and its `instructions.md` peer-checkbox format (`### Inn …` + `- [ ] Applied`).

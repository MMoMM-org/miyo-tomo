---
title: "Phase 6: Reduce / Review Surface"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Reduce / Review Surface

## Phase Context

**GATE**: Read before starting.
- `[ref: SDD/User Interface & UX]` (preview spec), `[ref: SDD/ADR-11 preview shape]`, `[ref: SDD/ADR-8 fallback]`
- `tomo/scripts/suggestions-reducer.py` (`render_tag_handler_group` :641, guards `annotate_tag_handler_group_guards` :1167)
- Memory: daily-note-existence ⚠️ reducer pattern; no executor internals in user-facing text.

**Key Decisions**: when `output_format` is present render a VERBATIM row/item preview + a one-line mode
descriptor (table/list, append/newest, per_item/merged); when `fallback` is set render a ⚠️ line (handler,
target, reason) and gate the Approve box consistent with existing guard branches. No "Hashi"/action/script
names.

**Dependencies**: **Phase 1** (group-result schema), **Phase 4** (group-results carry output_format/fallback).

---

## Tasks

Makes the structure-aware output reviewable and the fallback explicit before approval.

- [ ] **T6.1 Verbatim preview + mode descriptor** `[activity: backend-logic]`
  1. Prime: read `render_tag_handler_group` + the daily-note ⚠️ pattern `[ref: SDD/User Interface & UX]`
  2. Test (RED): an output_format group renders the literal row(s)/item(s) and a one-line mode descriptor;
     per_item shows all N lines, merged shows one; output text contains NO executor internals.
  3. Implement (GREEN): branch in `render_tag_handler_group` when `output_format` present. Bump version.
     WHY → `docs/tomo/scripts/suggestions-reducer.md`.
  4. Validate: `./venv/bin/python -m pytest tests/ -k suggestions_reducer -q`; ruff clean.
  - Success: `[ref: PRD/FR-20]` mode + verbatim preview; no-executor-internals rule honored.

- [ ] **T6.2 Fallback ⚠️ + Approve-box gating** `[activity: backend-logic]`
  1. Prime: existing guard branches (ok/target_missing/marker_missing) `[ref: SDD/Error Handling]`
  2. Test (RED): a group-result with `fallback.reason` renders a ⚠️ line naming handler/target/reason and a
     prose-block preview; Approve box behaviour matches existing guard convention; marker_missing still uses
     the existing guard.
  3. Implement (GREEN): render the ⚠️ + keep/drop Approve box consistently. Bump version.
  4. Validate: reducer tests green for each fallback reason; ruff clean.
  - Success: `[ref: PRD/FR-19]` warning surfaced; user approves the fallback knowingly.

- [ ] **T6.3 Phase Validation** `[activity: validate]`
  - Reducer renders correctly for every mode + every fallback reason; no executor internals; ruff clean.

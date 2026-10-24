---
title: "Phase 3: Reducer duplicate mutator"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Reducer duplicate mutator

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-6]` — mutator placement, key, collision handling
- `[ref: SDD/Implementation Examples; "duplicate mutator (traced)"]`
- `[ref: SDD/Interface Specifications; "suggestions-reducer.py"]`

**Key Decisions**:
- One mutation per action, before render, persist and cluster collection — so C3, C4 and the proposed-MOC list agree by construction (precedent: `demote_structural_anchors`, #71).
- The reducer reads eligibility from the context; it never recomputes it.

**Dependencies**: Phase 1 (T1.3 — eligible `mocs[]` with `name`, `path`, `title`, `is_classification`). Independent of Phase 2.

---

## Tasks

A proposed MOC that already exists by name never reaches the owner; the item is offered the existing MOC instead, unticked.

- [ ] **T3.1 `convert_duplicate_proposal` and its loader** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `suggestions-reducer.py:182-290` (`moc_link_line`, `persist_candidate_anchors`, `demote_structural_anchors`), `:790-822` (render), `:1756-1769` (`load_asset_folder`), `:2104-2118`, `:2440-2660` (action loop, clusters), `:2818-2830` (summary); `lib/topic_clusters.py:96-155`; `tests/test_suggestions_reducer_*` patterns `[ref: SDD/ADR-6]`
  2. Test (RED): the four rows of the traced example (Vacations → converted; Project → both paths appended; Urlaub → unchanged; Dewey title → unchanged); an existing candidate with the same path is not duplicated; appended candidates come after the analyst's own (`mocs[0]` unchanged); the "No good thematic MOC matched … Proposed MOCs" note disappears and no `proposed_mocs` entry forms for a converted action; a cluster of two items ("Project", "Projects") converts all-or-nothing; a suppressed atomic is untouched; a proposal equal only to an excluded MOC title stays a proposal (the excluded MOC is absent from the context); missing or invalid context → zero conversions, no error; rendered markdown shows `- [ ] [[path]]` without a Placement line; C3 wire candidate is `selected:false, source:"tomo"`; summary line has `duplicate_proposals_converted=<n>`
  3. Implement: `load_eligible_mocs` (fail-open, thematic only, key → [paths]); `convert_duplicate_proposal` called next to `demote_structural_anchors`; counter into the summary line; fix the stale docstring threshold (`:12` says 3, code uses 1); WHY into `docs/tomo/scripts/suggestions-reducer.md`; bump version
  4. Validate: RED on main; GREEN here; existing reducer and render tests green; ruff clean
  5. Success: `[ref: PRD/F4-AC1, F4-AC2, F4-AC3, F4-AC4 (count), F5-AC3]`

- [ ] **T3.2 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean. Pass-2 tests (`suggestion-parser`, `instruction-render`, `instructions-diff`) unchanged and green — a converted action produces no `create_moc` downstream.

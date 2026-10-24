---
title: "Phase 3: Reducer duplicate mutator"
status: completed
version: "1.1"
phase: 3
---

# Phase 3: Reducer duplicate mutator

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-6]` — placement, key, collision handling, lib module
- `[ref: SDD/Implementation Examples; "duplicate mutator (traced)"]`
- `[ref: SDD/Interface Specifications; "lib/duplicate_proposals.py"]`

**Key Decisions**:
- One mutation per action, before render, persist and cluster collection — so C3, C4 and the proposed-MOC list agree by construction (precedent: `demote_structural_anchors`, #71).
- The logic lives in `lib/duplicate_proposals.py`; the 2835-line reducer gets one call and one counter.
- Eligibility comes from the context; it is never recomputed.

**Dependencies**: Phase 1 (T1.4). Independent of Phase 2.

---

## Tasks

A proposed MOC that already exists by name never reaches the owner; the item is offered the existing MOC instead, unticked.

- [x] **T3.1 `lib/duplicate_proposals.py` and the reducer call** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `suggestions-reducer.py` `moc_link_line`, `persist_candidate_anchors`, `demote_structural_anchors`, the render of "Link to MOC" / "No good thematic MOC matched", `load_asset_folder`, the action loop, cluster collection, the summary print; `lib/topic_clusters.py` `strip_moc_marker`, `normalise_topic`; `suggestions-render.py` `_wire_selected` and the candidate projection (the C3 shape is built there, not in the reducer) `[ref: SDD/ADR-6]`
  2. Test (RED via the exact count — the summary key `duplicate_proposals_converted` does not exist on `main`):
     - one fixture holding all four traced rows at once (Vacations → converted; Project → both paths appended; Urlaub → unchanged; Dewey title → unchanged) plus a suppressed atomic proposing "Vacation", an action that already lists the Vacation path, and a proposal equal only to an excluded MOC's title; assert `duplicate_proposals_converted=2` exactly and each action's resulting state
     - appended candidates follow the analyst's own (`mocs[0]` unchanged); no duplicate path
     - the "No good thematic MOC matched … Proposed MOCs" note is absent and no `proposed_mocs` entry forms for converted actions; a two-item cluster ("Project", "Projects") converts all-or-nothing
     - rendered markdown shows `- [ ] [[path]]` without a Placement line; through `suggestions-render.py`, the C3 wire candidate is `selected:false, source:"tomo"`
     - missing or invalid context → `duplicate_proposals_converted=0`, no error
  3. Implement: `lib/duplicate_proposals.py` (`load_eligible_mocs`, `convert_duplicate_proposal`; WHY docstring; `# version: 0.1.0`); one call next to `demote_structural_anchors`; counter into the summary line; fix the stale threshold docstring (`:12`); `docs/tomo/scripts/lib/duplicate_proposals.md` and a pointer in `docs/tomo/scripts/suggestions-reducer.md`; bump the reducer version
  4. Validate: RED on `main`; GREEN here; existing reducer and render tests green; ruff clean
  5. Success: `[ref: PRD/F4-AC1, F4-AC2, F4-AC3, F4-AC4 (count), F5-AC3]`

  6. Deviations recorded during implementation (2026-10-24):
     - `load_eligible_mocs(shared_ctx_path, suffix)` takes the profile's MOC suffix, because the cluster key strips it. The SDD signature has one argument.
     - The fixture in `tests/test_040_duplicate_proposals.py` converts **4** actions, not the 2 the plan's wording implies:
       - "Vacations"
       - "Project"
       - its cluster partner "Projects", which proves all-or-nothing
       - the action that already lists the Vacation path, which must itself propose a duplicate, otherwise "no duplicate path" is untested
     - RED: 7 of 8 tests fail against `main`'s reducer. The one that passes is the guard: unconverted and suppressed actions stay unchanged.
     - The reducer call site has its own comment, placed above the existing #71 comment rather than under it.

- [x] **T3.2 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean. Pass-2 tests (`suggestion-parser`, `instruction-render`, `instructions-diff`) unchanged and green — a converted action produces no `create_moc` downstream; `instruction-render` with no context file still falls back to default tracker syntax (guard).
  - Result (2026-10-24, at faf6776e): 5064 passed, 3 skipped; ruff clean. The Pass-2 tests ran in that same suite, unchanged and green. A converted action seeds no `proposed_mocs` entry, so no `create_moc` can follow (`test_only_unconverted_topics_reach_proposed_mocs`). `instruction-render` without a context file still falls back to default tracker syntax (`test_162_tracker_syntax_and_section.py:158`, existing guard).

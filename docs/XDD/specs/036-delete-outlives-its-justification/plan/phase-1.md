---
title: "Phase 1: Declare — depends_on at every emission site"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Declare — depends_on at every emission site

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Solution Strategy]` — declare-then-collect, and the boundary it does not cross
- `[ref: SDD/Architecture Decisions; ADR-1]`
- `[ref: SDD/Implementation Gotchas]` — the three traps in this phase live there
- `[ref: PRD/Feature 5]` and its six acceptance criteria
- `tomo/scripts/lib/render_actions.py` — `_build_delete_source_actions` and its four sites

**Key Decisions**:
- **ADR-1** — the field is populated at build time, before any guard runs. A builder that adds it
  afterwards reintroduces the ordering bug this spec exists to fix.
- The field is **required** on every `delete_source`, with `[]` where nothing conditions the delete.
  Absence is never valid; `[]` is an assertion. (Confirmed by the consumer, 2026-09-09.)
- Semantics are **AND** over the list: if any named id fails, the delete does not run.

**Dependencies**:
- None. This phase is the foundation.

**What this phase does NOT do**: nothing consumes `depends_on` yet. At the end of Phase 1 the field
is emitted and correct, and behaviour is otherwise unchanged. That is deliberate — it makes Phase 2
a pure behaviour change with the data already in place and independently tested.

---

## Tasks

Establishes the dependency relation as data: every conditional delete knows what justifies it.

- [ ] **T1.1 Site 3 and site 1 declare their dependencies** `[activity: domain-modeling]`

  Site 3 (`move_note` origin plus audio peer) already has the partner ids in hand — the completion
  gate buckets the actual move action dicts. Site 1 (user-requested deletion) has no partner and
  declares that explicitly.

  1. Prime: read `_build_delete_source_actions` sites 1 and 3 `[ref: SDD/Complex Logic]`; note that
     `moves_by_origin` holds the move dicts themselves, each carrying `id`.
  2. Test: a single-atomic origin emits a delete naming exactly its one move id; a three-atomic
     origin names **all three**; an origin with an audio peer emits **two** deletes and both name
     the same move-id set; a user-requested deletion emits `depends_on: []`; an item marked
     "Keep source files" still emits no delete at all.
  3. Implement: populate `depends_on` at both sites in `tomo/scripts/lib/render_actions.py`.
  4. Validate: `./venv/bin/python -m pytest tests/test_036_depends_on_emission.py`; ruff clean.
  5. Success:
     - [ ] Every emitted `delete_source` from these two sites carries `depends_on` `[ref: PRD/F5-AC1]`
     - [ ] An N-atomic origin names N ids, not one `[ref: PRD/F5-AC3]`
     - [ ] The user-requested case is `[]`, not absent `[ref: PRD/F5-AC2]`
     - [ ] The audio-peer delete names the same ids as its origin delete `[ref: SDD/Implementation Gotchas]`

- [ ] **T1.2 Site 2 receives daily action ids** `[activity: backend-api]`

  Site 2 does not have partner ids today: `_build_delete_source_actions` receives the *suggestion
  entries*, not the emitted daily actions. `build_actions` builds those separately and never passes
  them to the delete builder.

  1. Prime: read `_build_daily_update_actions` and the site-2 origin-key resolution `[ref: SDD/Application Data Models]`.
  2. Test: an origin with one accepted daily entry names that entry's action id; an origin with
     entries across **several buckets and several days** names all of them; an origin whose daily
     entries are all unaccepted emits no delete; two origins with the same display stem in different
     folders do not cross-contaminate.
  3. Implement: return `{origin_key: [action_id]}` from `_build_daily_update_actions`, keyed with
     the same `_origin_key(resolve_source_path(...))` the delete site already computes; thread it
     through `build_actions` into `_build_delete_source_actions`.
  4. Validate: unit tests pass; ruff clean; no change to emitted action *counts* in any existing test.
  5. Success:
     - [ ] Site 2 deletes carry the ids of every daily action for that origin `[ref: PRD/F2-AC2]`
     - [ ] The join is on the resolved path, not the display stem `[ref: SDD/Implementation Gotchas]`
     - [ ] `_build_daily_update_actions`' existing return value is unchanged for all current callers

- [ ] **T1.3 Site 4 receives the insert action id** `[activity: backend-api]`

  A cheaper version of T1.2: both loops already iterate the same groups under the same approval
  filter, so the map is a return-shape change rather than a re-plumb.

  1. Prime: read `_build_insert_under_marker_actions` and site 4 `[ref: SDD/Complex Logic]`.
  2. Test: an approved group with a resolvable target emits deletes naming the insert's id; a group
     of three sources emits three deletes **all naming the same insert id**; a group opted out via
     "Keep source files" emits no delete.
  3. Implement: return `{group_id: action_id}` from `_build_insert_under_marker_actions`; thread it
     through.
  4. Validate: unit tests pass; ruff clean.
  5. Success:
     - [ ] Every site-4 delete names its group's insert id `[ref: PRD/F5-AC1]`
     - [ ] One insert id is shared by every delete in the group `[ref: SDD/Complex Logic]`

  **Note**: the unresolvable-target case is **not** handled here — no insert is built, so no id
  exists to name. That is Phase 3, and it is a design boundary rather than an omission
  `[ref: SDD/The boundary this design does NOT cross]`.

- [ ] **T1.4 Phase Validation** `[activity: validate]`

  - Run the full suite: `./venv/bin/python -m pytest`. Every pre-existing test must still pass —
    Phase 1 changes emitted *content*, never emitted *counts* or ordering.
  - Run `./venv/bin/python -m ruff check tomo/ tests/`.
  - Confirm by inspection of a rendered instruction set that **every** `delete_source` carries
    `depends_on`, and that no id in any of them is absent from the set. The audit that enforces this
    lands in Phase 4; here it is a manual check that the data is right before anything consumes it.

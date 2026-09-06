---
title: "Phase 5: Display and destination guards"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Display and destination guards

## Phase Context

**GATE**: read these before starting.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-4, ADR-6]`
- `[ref: SDD/Complex Logic]` — the traced walkthrough of the validation pass
- `[ref: PRD/Feature 2, Feature 7, Feature 8]`
- `[ref: PRD/Business Rule 5, Business Rule 8]`

**Key Decisions**:
- Source links are path-qualified **only** when two items in the run share a filename. A bare
  link is not merely terse in that case — the vault resolves by name, so clicking or hovering
  either of two identical links opens whichever it picks.
- A Pass-1 check is advisory. The user edits the document afterwards, so the binding guard
  belongs in Pass 2 `[ref: PRD/Business Rule 8]`.
- On a destination clash, **both** claimants are dropped. Choosing between two names the user
  set deliberately would itself be a guess.
- An attachment clash suppresses its own note's move, reversing spec 031.

**Dependencies**: Phases 3 and 4 complete.

---

## Tasks

- [ ] **T5.1 Source links disambiguate on collision** `[activity: backend]`

  1. **Prime**: Read the display sites in `suggestions-reducer.py` — enumerate them yourself
     rather than working from a count `[ref: SDD/Implementation Gotchas]`. Read the verified
     evidence in the spec README: when two files share a basename the vault itself writes
     `[[100 Inbox/Images/Test|Test]]`, path plus alias.
  2. **Test** (RED):
     - one item with a given filename → its source link is the plain filename
       `[ref: PRD/AC Feature 2]`
     - two items sharing a filename → each link carries enough location to be distinct, and
       each resolves to its own note
     - the suggested name shown for a subfolder note is still `Dresden`, never a path-derived
       string `[ref: PRD/AC Feature 2]`
     - a run with no collision produces a byte-identical document to before this task
  3. **Implement**: detect same-filename groups while rendering — the renderer already sees
     every item — and path-qualify only those.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] The user can tell two same-named suggestions apart, and each link goes to the right
           note `[ref: PRD/Business Rule 5]`

- [ ] **T5.2 Pass 1 proposes a distinct name on a destination clash** `[activity: backend]`

  1. **Prime**: Read `_dest_join` (`lib/render_actions.py:484`) — it builds the destination from
     the title with no collision check — and `_disambiguate_filename` (`:444`), which guards
     only the intermediate rendered file within one render run, not the vault destination.
  2. **Test** (RED):
     - two items whose names would produce one destination → the second gets a distinct
       proposed name `[ref: PRD/AC Feature 7]`
     - the user's own edit to that name is honoured — the proposal is a starting point
     - an item whose destination already exists in the target folder is surfaced too
     - a run with no clash proposes nothing new
  3. **Implement**: detect the clash while rendering the suggestions document and adjust the
     proposed name, leaving it editable exactly as any other suggested name.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] The common case never reaches the Pass-2 guard `[ref: SDD/ADR-4]`

- [ ] **T5.3 Pass 2 validates destinations** `[activity: backend]`

  1. **Prime**: Read `[ref: SDD/Complex Logic]` — the four-action walkthrough — and
     `_build_move_asset_actions` (`lib/render_actions.py:630-690`) as the reporting pattern to
     follow. Note the deliberate difference: that guard is first-claim-wins, this one drops both
     `[ref: SDD/ADR-4]`.
  2. **Test** (RED):
     - the user edits two approved items to one name → **neither** move is emitted, and the
       clash is reported prominently `[ref: PRD/AC Feature 7]`
     - a name clashing with a note already in the target folder → same treatment
     - the user corrects one name and re-runs → both are emitted normally, no need to restart
       the run
     - a run with no clash emits exactly the actions it emits today — whole-list comparison,
       not selected fields
  3. **Implement**: a validation pass over the built action list, run after `build_actions`,
     that removes clashing claimants and records a report. Check surviving destinations against
     the vault.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] A clash cannot reach the executor `[ref: PRD/AC Feature 7]`
     - [ ] The halt is recoverable by renaming and re-running Pass 2

- [ ] **T5.4 An attachment clash keeps its note in the inbox** `[activity: backend]`

  1. **Prime**: Read `[ref: SDD/ADR-6]`. Read `_build_move_asset_actions`, particularly the
     `seen` set (same file referenced twice — a duplicate, **not** a clash) versus `claimed`
     (two different files, one destination). Read
     `tests/test_031_t2_4_destination_collision_guard.py:121`, which asserts the behaviour being
     reversed.
  2. **Test** (RED):
     - two different files sharing a basename, each embedded by its own note → the second file
       is not filed **and neither is its note** `[ref: PRD/AC Feature 8]`
     - the first note and its attachment are filed normally — one clash does not hold up another
     - one file embedded by two notes → filed once, both notes move. Unchanged; this is a
       duplicate reference, not a clash
     - the user renames one file and re-runs → everything files normally
  3. **Implement**: link the attachment clash to its note's move. **Invert**
     `test_collision_does_not_suppress_the_notes_own_move_note` — a red test here is the
     intended change, not a regression in your own work `[ref: SDD/ADR-6]`.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] No note is filed into the permanent collection while depending on a file left in the
           inbox `[ref: PRD/AC Feature 8]`
     - [ ] The duplicate-reference path is provably untouched

- [ ] **T5.5 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Read the rendered output as prose. Render a suggestions document containing every
    combination — no clash, a name clash, an attachment clash, a subfolder note, a namesake
    pair — and read it end to end as English. This finds a class of defect no test reaches;
    spec 033 found five that way after a 3000-test suite and two review gates had passed.
    An agent reporting "I read it and it is fine" reproduces the failure — render, then have
    the orchestrator or the user read it.
  - Mutation-prove each guard: disable it, confirm the specific test dies, restore.
  - Bump `# version:` on every modified file.

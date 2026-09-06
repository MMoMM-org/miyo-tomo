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

- [ ] **T5.0 Pass 2 reads `item_key` — the feature does not work without this** `[activity: backend]`

  **BLOCKING, added 2026-09-06 by the Phase 3 gate.** Recursion is live and the key is threaded
  through Pass 1, but **every subfolder note is silently dropped in Pass 2**, so nothing the
  recursion discovers reaches the instruction set. PRD Feature 1's acceptance criterion —
  "subfolder notes are triaged" — is not met end to end until this lands.

  **The mechanism.** `filter_missing_source_notes` (`lib/render_resolve.py:672-683`), called from
  `instruction-render.py:320`, reconstructs a path from the bare display stem:

  ```python
  if item.get("template") and source_path:
      full_path = source_path
      if "/" not in full_path:
          full_path = f"{inbox_path.rstrip('/')}/{full_path}"
      if not full_path.endswith(".md"):
          full_path += ".md"
      if not _exists(full_path):
          dropped.append(item)
  ```

  For `100 Inbox/Places/Kaffee.md` the item's `source_path` is `Kaffee`, so it probes
  `100 Inbox/Kaffee.md`, finds nothing, and drops the item. **This is the same
  `<inbox_path>/<stem>.md` reconstruction T4.1 removed from `force-atomic-handling/SKILL.md`**,
  living in a file no task pointed at. A second copy sits at `instruction-render.py:381-386`
  (the body read); subfolder items never reach it because they are already gone.

  **It is not a markdown-versus-wire problem.** Both parser paths emit a bare `source_path` by
  Phase 2's deliberate design — `item_key` carries identity, `source_path` stays display text
  (ADR-2). The defect is on the **consumer** side: the whole Pass-2 render stage never adopted
  the key.

  ```
  tomo/scripts/instruction-render.py     0 occurrences of "item_key"
  tomo/scripts/lib/render_resolve.py     0
  tomo/scripts/lib/render_io.py          0
  ```

  T2.3b landed `item_key` one hop short of the stage that needs it.

  **Blast radius: every subfolder note carrying a `template`** — every atomic-note suggestion —
  not only ones whose filename collides. The guard branches on `"/" not in source_path`, a plain
  "is this a bare stem" test with no collision awareness. Demonstrated on three globally unique
  filenames (`Kaffee`, `Level2`, `Root Note`): the two in subfolders were dropped, the root one
  kept, and every path the guard probed exists in the vault — it probed none of them.

  **T5.1 does not close this.** T5.1 path-qualifies source links *on collision*; this drops every
  subfolder note regardless. They are independent.

  1. **Prime**: Read `filter_missing_source_notes` (`lib/render_resolve.py:672-683`), its caller
     (`instruction-render.py:320`), and the body read at `instruction-render.py:381-386`. Read the
     `#116` rationale the guard exists for — it is right, it is only addressing the item wrongly.
  2. **Test** (RED):
     - a subfolder note with a globally unique filename survives Pass 2 and reaches the
       instruction set `[ref: PRD/AC Feature 1]`
     - a note nested two levels deep survives
     - a root-level note is unchanged
     - the `#116` guard still drops an item whose source note is genuinely gone — the guard must
       keep working, not be removed
     - no path is composed from a bare stem anywhere in the Pass-2 render stage
  3. **Implement**: address the item by `item_key`, falling back to the reconstruction only when
     the key is absent, so a document produced before this spec still renders. Fix both sites.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] A subfolder note reaches the instruction set `[ref: PRD/AC Feature 1]`
     - [ ] The `#116` guard still catches a genuinely missing source note
     - [ ] No `<inbox_path>/<stem>` composition survives in the Pass-2 render stage

- [ ] **T5.1 Source links disambiguate on collision** `[activity: backend]`

  **Inherited from Phase 2 — this task closes the markdown path's identity gap.** T2.3b closed the
  coverage-audit collapse for the ADR-026 **wire** path by threading `item_key` into
  `confirmed_items` in `build_from_wire` (`suggestion-parser.py:267`). The **markdown** path —
  `main()` at `:1854`, which `synthesis-conductor.md` actually invokes as
  `--file <CACHE_PATH>` in the normal flow — mints no `item_key` at any of its four
  `confirmed_items.append` sites (`:2034`, `:2247`, `:2272`, `:2330`), because the rendered document
  carries only a bare display stem and a path cannot be recovered from one.

  Path-qualifying the source link on collision is exactly what this task does, so it is also what
  makes the markdown path's identity recoverable. When it lands:
  - Thread the qualified path into `confirmed_items` as `item_key` on the markdown path too, using
    the module-level `_item_key_of` — no second derivation.
  - Re-run T2.7's adversarial case through the **markdown** path (two confirmed items for
    `100 Inbox/Places/Dresden.md` and `100 Inbox/Reise/Dresden.md`, one with a duplicated
    `move_note`, one with none) and assert the audit **reports the missing item**. Through the wire
    path this already returns `RESULT: FAIL … RC=1`; through the markdown path it still returns
    `RESULT: OK … RC=0` today.

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
